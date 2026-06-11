"""
可拖动悬浮 AI 助手"小智"：
  - 收起态：右下角圆形悬浮按钮，显示机器人图标
  - 展开态：弹出独立聊天面板，支持拖动定位
  - AI 聊天：DeepSeek API（环境变量 DEEPSEEK_API_KEY）
"""

import os
import sys
import wave
import threading
import requests

import requests
import wave
import threading
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit,
    QLineEdit,
)
from PyQt5.QtCore import Qt, QPoint, pyqtSignal, QTimer
from PyQt5.QtGui import (
    QFont, QPainter, QPixmap, QBrush, QColor, QPen,
)
from hospital_gui.config import SCREEN_W, SCREEN_H

try:
    _sys_path_backup = sys.path[:]
    sys.path.insert(0, "/home/hyh/robot/hospital_ws/src/voice_control")
    from voice_control import voice_node as _voice_node
    HAS_VOICE = True
except Exception:
    HAS_VOICE = False
    _voice_node = None
finally:
    sys.path = _sys_path_backup

# ── 颜色主题 ──────────────────────────────────────────────────────────────
_COLOR_PANEL_BG  = "#1a2332"
_COLOR_HEADER_BG = "#243044"
_COLOR_ACCENT    = "#e53935"    # 红色（呼应医院紧急色）
_COLOR_BUBBLE_U  = "#1565c0"    # 用户消息 蓝
_COLOR_BUBBLE_A  = "#2d3e50"    # AI 消息 暗青
_COLOR_TEXT      = "#f0f4f8"
_COLOR_TEXT_DIM  = "#8a9bb0"
_COLOR_INPUT_BG  = "#1d2b3a"
_COLOR_BORDER    = "#3a4a5c"


# ── 独立悬浮圆形按钮（始终可见）───────────────────────────────────────────

class FloatingButton(QWidget):
    """独立圆形悬浮按钮，始终显示在屏幕上，短按开面板，长按拖动松开后留在原地。"""

    clicked = pyqtSignal(object)   # 附带点击时的全局位置 QPoint

    RADIUS = 32          # 按钮半径 px
    SIZE   = RADIUS * 2   # 窗口尺寸
    LONG_PRESS_MS = 400   # 长按判定阈值（ms）

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.PointingHandCursor)
        self._load_icon()

        self._press_pos     = None   # 鼠标按下时的全局位置
        self._long_pressing = False  # 是否已进入长按拖动模式
        self._long_press_timer = QTimer(self)
        self._long_press_timer.setSingleShot(True)
        self._long_press_timer.timeout.connect(self._on_long_press)

    def _load_icon(self):
        path = "/home/hyh/robot/src/机器人.jpeg"
        if os.path.exists(path):
            pm = QPixmap(path)
            if not pm.isNull():
                self._icon = pm.scaled(
                    self.RADIUS * 2 - 10, self.RADIUS * 2 - 10,
                    Qt.KeepAspectRatio, Qt.SmoothTransformation,
                )
                return
        self._icon = QPixmap()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)

        # 圆形背景
        r = self.RADIUS
        painter.setBrush(QBrush(QColor(_COLOR_ACCENT)))
        painter.drawEllipse(0, 0, r * 2, r * 2)

        # 白色内描边
        pen = QPen(QColor(220, 220, 220, 60))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(1, 1, r * 2 - 2, r * 2 - 2)

        # 机器人图标（居中）
        if hasattr(self, "_icon") and not self._icon.isNull():
            icon_size = self.RADIUS * 2 - 12
            scaled = self._icon.scaled(
                icon_size, icon_size,
                Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
            x = r - scaled.width() // 2
            y = r - scaled.height() // 2
            painter.drawPixmap(int(x), int(y), scaled)

    def _on_long_press(self):
        """计时器到期 → 进入长按拖动模式"""
        self._long_pressing = True
        self._drag_start_global = self._press_pos
        self._drag_start_win = self.pos()
        self.setCursor(Qt.ClosedHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_pos = event.globalPos()
            self._long_pressing = False
            self._long_press_timer.start(self.LONG_PRESS_MS)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._long_pressing and self._press_pos is not None:
            delta = event.globalPos() - self._press_pos
            self.move(self._drag_start_win + delta)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._long_press_timer.stop()
        self.setCursor(Qt.PointingHandCursor)
        if event.button() == Qt.LeftButton:
            if self._long_pressing:
                pass   # 长按拖动后松开，什么都不做，按钮留在原地
            else:
                self.clicked.emit(event.globalPos())
        self._press_pos     = None
        self._long_pressing = False
        super().mouseReleaseEvent(event)


# ── 聊天面板（可拖动）─────────────────────────────────────────────────────

class ChatPanel(QWidget):
    """展开态的 AI 聊天面板，支持拖动定位。"""

    WIDTH  = 320
    HEIGHT = 440

    submit = pyqtSignal()   # 用户点击发送时触发，由 AIAssistant._send 处理
    closed = pyqtSignal()   # 用户关闭面板时触发，由 AIAssistant._collapse 处理

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._dragging = False
        self._drag_start = QPoint()
        self._messages = []
        self._init_ui()

    # ── UI ──────────────────────────────────────────────────────────────

    def _init_ui(self):
        root = QWidget()
        root.setFixedSize(self.WIDTH, self.HEIGHT)
        root.setStyleSheet(f"""
            QWidget {{
                background-color: {_COLOR_PANEL_BG};
                border-radius: 14px;
                border: 1px solid {_COLOR_BORDER};
            }}
        """)

        shadow_hack = QWidget(self)
        shadow_hack.setFixedSize(self.WIDTH, self.HEIGHT)
        shadow_hack.setAttribute(Qt.WA_TranslucentBackground)
        shadow_hack_layout = QVBoxLayout(shadow_hack)
        shadow_hack_layout.setContentsMargins(0, 0, 0, 0)
        shadow_hack_layout.addWidget(root)

        lay = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        lay.addWidget(self._make_header(root))
        lay.addWidget(self._make_chat_area(root))
        lay.addWidget(self._make_input_bar(root))

    def _make_header(self, parent):
        bar = QWidget(parent)
        bar.setFixedHeight(52)
        bar.setStyleSheet(f"""
            QWidget {{
                background-color: {_COLOR_HEADER_BG};
                border-radius: 14px 14px 0 0;
            }}
        """)
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(14, 0, 10, 0)

        icon_lbl = QLabel(parent=bar)
        icon_lbl.setFixedSize(32, 32)
        icon_lbl.setStyleSheet("background: transparent;")
        pm = QPixmap("/home/hyh/robot/src/机器人.jpeg")
        if not pm.isNull():
            icon_lbl.setPixmap(pm.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        hl.addWidget(icon_lbl)

        title = QLabel("小智 AI 助手", parent=bar)
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        title.setStyleSheet(f"color: {_COLOR_TEXT}; background: transparent;")
        hl.addWidget(title)
        hl.addStretch()

        close_btn = QPushButton("✕", parent=bar)
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {_COLOR_TEXT_DIM};
                border: none;
                font-size: 16px;
            }}
            QPushButton:hover {{ color: {_COLOR_ACCENT}; }}
        """)
        close_btn.clicked.connect(self._on_close)
        hl.addWidget(close_btn)
        return bar

    def _make_chat_area(self, parent):
        self._chat = QTextEdit(parent)
        self._chat.setReadOnly(True)
        self._chat.setStyleSheet(f"""
            QTextEdit {{
                background-color: {_COLOR_PANEL_BG};
                color: {_COLOR_TEXT};
                border: none;
                font-family: 'Microsoft YaHei';
                font-size: 14px;
                padding: 10px 12px;
            }}
            QTextEdit QScrollBar:vertical {{
                background: transparent;
                width: 5px;
            }}
            QTextEdit QScrollBar::handle {{
                background: {_COLOR_BORDER};
                border-radius: 2px;
            }}
            QTextEdit QScrollBar::add-line, QTextEdit QScrollBar::sub-line {{
                height: 0px;
            }}
        """)
        return self._chat

    def _make_input_bar(self, parent):
        bar = QWidget(parent)
        bar.setFixedHeight(54)
        bar.setStyleSheet(f"""
            QWidget {{
                background-color: {_COLOR_HEADER_BG};
                border-radius: 0 0 14px 14px;
            }}
        """)
        il = QHBoxLayout(bar)
        il.setContentsMargins(10, 6, 10, 6)
        il.setSpacing(8)

        self._input = QLineEdit(parent=bar)
        self._input.setPlaceholderText("输入您的问题...")
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {_COLOR_INPUT_BG};
                color: {_COLOR_TEXT};
                border: none;
                border-radius: 16px;
                padding: 0 14px;
                font-family: 'Microsoft YaHei';
                font-size: 14px;
            }}
            QLineEdit::placeholder {{ color: {_COLOR_TEXT_DIM}; }}
        """)
        self._input.returnPressed.connect(self._on_send)
        il.addWidget(self._input, stretch=1)

        if HAS_VOICE:
            self._voice_btn = QPushButton("🎙", parent=bar)
            self._voice_btn.setFixedSize(38, 38)
            self._voice_btn.setToolTip("语音输入")
            self._voice_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2d3e50;
                    color: white;
                    border: none;
                    border-radius: 19px;
                    font-size: 17px;
                }
                QPushButton:pressed { background-color: #1a2a3a; }
            """)
            self._voice_btn.clicked.connect(self._on_voice_input)
            il.addWidget(self._voice_btn)

        send_btn = QPushButton("➤", parent=bar)
        send_btn.setFixedSize(38, 38)
        send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {_COLOR_ACCENT};
                color: white;
                border: none;
                border-radius: 19px;
                font-size: 16px;
            }}
            QPushButton:pressed {{ background-color: #c62828; }}
        """)
        send_btn.clicked.connect(self._on_send)
        il.addWidget(send_btn)
        return bar

    def _on_send(self):
        self.submit.emit()

    def append_user(self, content: str):
        self._messages.append({"role": "user", "content": content})
        self._render()

    def _on_voice_input(self):
        if not HAS_VOICE or _voice_node is None:
            self.append_assistant("⚠️ 语音模块不可用，请检查配置。")
            return
        self._set_voice_listening(True)
        self._chat.setHtml(
            self._chat.toHtml().rsplit("</body>", 1)[0]
            + '<div style="text-align:center;margin:8px 0;">'
            + '<span style="display:inline-block;background:#1565c0;color:white;border-radius:10px;'
            + 'padding:10px 20px;font-family:Microsoft YaHei;font-size:14px;">🎙 正在聆听，请说话...</span>'
            + '</div></body></html>'
        )

        def do():
            wav_path, text = _voice_node.record_until_silence(timeout_s=6)

            def done():
                self._set_voice_listening(False)
                if not text.strip():
                    self.append_assistant("未检测到语音，请重试。")
                else:
                    self._input.setText(text)
                    self._on_send()

            QTimer.singleShot(0, done)

        threading.Thread(target=do, daemon=True).start()

    def _set_voice_listening(self, listening: bool):
        if hasattr(self, "_voice_btn"):
            self._voice_btn.setEnabled(not listening)
            self._voice_btn.setText("⏳" if listening else "🎙")
            self._voice_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1565c0;
                    color: white;
                    border: none;
                    border-radius: 19px;
                    font-size: 17px;
                }
                QPushButton:disabled { background-color: #2d3e50; }
            """ if listening else """
                QPushButton {
                    background-color: #2d3e50;
                    color: white;
                    border: none;
                    border-radius: 19px;
                    font-size: 17px;
                }
                QPushButton:pressed { background-color: #1a2a3a; }
            """)

    def _on_close(self):
        self.closed.emit()

    # ── 拖动 ───────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_start = event.globalPos() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging:
            new_pos = event.globalPos() - self._drag_start
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, _):
        self._dragging = False

    # ── 聊天 API（暴露给外部调用）────────────────────────────────────

    def on_send(self, callback):
        """返回 (user_text, clear_input_fn) 或 (None, None)。"""
        text = self._input.text().strip()
        if not text:
            return None, None

        def clear():
            self._input.clear()

        self._input.clear()
        self._messages.append({"role": "user", "content": text})
        self._render()
        callback(text)
        return text, clear

    def append_assistant(self, content: str):
        self._messages.append({"role": "assistant", "content": content})
        self._render()

    def set_welcome(self):
        self._messages.append({
            "role": "assistant",
            "content": "您好！我是小智，您的智能健康助手。有什么可以帮您的吗？",
        })
        self._render()

    def _render(self):
        parts = []
        for m in self._messages:
            is_user = m["role"] == "user"
            bg   = _COLOR_BUBBLE_U if is_user else _COLOR_BUBBLE_A
            algn = "right" if is_user else "left"
            pad  = "10px 14px" if is_user else "10px 14px"
            html = (
                f'<div style="text-align:{algn}; margin:4px 0;">'
                f'<span style="display:inline-block; background:{bg}; '
                f'color:{_COLOR_TEXT}; border-radius:10px; padding:{pad}; '
                f'font-family:Microsoft YaHei;font-size:14px;max-width:82%;'
                f'word-break:break-all;line-height:1.5;">'
                f'{m["content"]}</span></div>'
            )
            parts.append(html)
        self._chat.setHtml("\n".join(parts))
        QTimer.singleShot(0, lambda: self._chat.verticalScrollBar().setValue(
            self._chat.verticalScrollBar().maximum()
        ))


# ── AIAssistant 主组件 ────────────────────────────────────────────────────

class AIAssistant(QWidget):
    """
    悬浮 AI 助手管理器：
      - 圆形悬浮按钮始终贴在右下角
      - 点击按钮 → 弹出聊天面板
      - 聊天面板可自由拖动
      - 支持 DeepSeek API 对话
    """

    PANEL_W = ChatPanel.WIDTH
    PANEL_H = ChatPanel.HEIGHT
    BTN_R   = FloatingButton.RADIUS

    def __init__(self, parent=None):
        super().__init__(parent)

        # 独立圆形按钮窗口（始终置顶，不依赖父窗口）
        self._btn = FloatingButton()
        self._btn.clicked.connect(self._toggle)
        self._btn.move(
            SCREEN_W - FloatingButton.SIZE - 14,
            SCREEN_H - FloatingButton.SIZE - 14,
        )
        self._btn.show()

        # 独立聊天面板窗口
        self._panel = ChatPanel()
        self._panel.set_welcome()
        self._panel.submit.connect(self._send)
        self._panel.closed.connect(self._collapse)
        self._panel.hide()

        self._expanded = False

    def _toggle(self, pos=None):
        if self._expanded:
            self._collapse()
        else:
            self._expand(pos)

    def _expand(self, click_pos=None):
        self._expanded = True
        self._btn.hide()

        # 面板出现在点击位置，左上角对齐，不超出屏幕
        x = click_pos.x() if click_pos else (SCREEN_W - self.PANEL_W - 14)
        y = click_pos.y() if click_pos else (SCREEN_H - self.PANEL_H - FloatingButton.SIZE - 14)
        x = max(0, min(x, SCREEN_W - self.PANEL_W))
        y = max(0, min(y, SCREEN_H - self.PANEL_H))
        self._panel.move(x, y)

        self._panel.show()
        self._panel.raise_()

    def _collapse(self):
        self._expanded = False
        self._panel.hide()
        self._btn.show()
        self._panel._input.clear()

    # ── 聊天逻辑 ─────────────────────────────────────────────────────

    _SYSTEM_PROMPT = (
        "你叫小智，是医院的智能导诊助手。你说话亲切、专业、简洁，"
        "帮助患者指引科室、解答健康问题。"
        "注意：如果患者描述的症状严重或紧急，请建议尽快就医。"
    )

    def _send(self):
        result = self._panel.on_send(self._do_request)
        _, clear_fn = result
        if clear_fn is None:
            return  # 空消息

    def _do_request(self, _):
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            self._panel.append_assistant("⚠️ 未配置 DeepSeek API Key，请联系管理员。")
            return

        # 先加一条"思考中"提示
        self._panel.append_assistant("小智正在思考...")

        def do():
            try:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                msgs = [{"role": "system", "content": self._SYSTEM_PROMPT}]
                for m in self._panel._messages[:-1]:
                    if m["content"] not in ("小智正在思考...",
                        "您好！我是小智，您的智能健康助手。有什么可以帮您的吗？"):
                        msgs.append({"role": m["role"], "content": m["content"]})

                payload = {
                    "model": "deepseek-chat",
                    "messages": msgs,
                    "max_tokens": 512,
                    "temperature": 0.7,
                }
                resp = requests.post(
                    "https://api.deepseek.com/chat/completions",
                    headers=headers, json=payload, timeout=20,
                )
                resp.raise_for_status()
                reply = resp.json()["choices"][0]["message"]["content"].strip()
            except Exception as e:
                reply = f"⚠️ 网络异常：{e}"
                print(f"[AIAssistant] DeepSeek API error: {e}")

            # 替换"思考中"消息
            self._panel._messages[-1]["content"] = reply
            QTimer.singleShot(0, self._panel._render)

        QTimer.singleShot(50, do)
