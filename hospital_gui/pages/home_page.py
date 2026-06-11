"""
首页：
  - 顶部：仁济医院欢迎您 + 右上角搜索框
  - 中部：5宫格主菜单（地图导航 / 自助挂号 / 自助查询 / 校验单查询 / 医院官网）
  - 可拖动悬浮AI助手"小智"：全局浮动在所有页面之上
"""

import threading

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QSizePolicy,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont, QColor, QPainter, QLinearGradient, QPalette, QPixmap

from hospital_gui.config import (
    SCREEN_W, SCREEN_H,
    COLOR_WHITE, COLOR_TEXT,
    FONT_H2, FONT_H4, FONT_BTN, FONT_BODY,
    BTN_SIZE_BIG,
    QUICK_DESTINATIONS, MENU_ITEMS, EXTERNAL_URLS,
)


# ── 主题配色 ────────────────────────────────────────────────────────────────
_THEME = {
    "header_bg":    "#1a3a5c",    # 顶部深蓝背景
    "header_text":  "#ffffff",    # 顶部白色文字
    "search_bg":    "#2a5080",    # 搜索框背景
    "search_txt":   "#ffffff",    # 搜索框文字
    "search_ph":    "#8ab4d8",    # 搜索框占位符
    "card_bg":      "#f0f4f8",    # 卡片白灰背景
    "card_shadow":  "#d0d8e0",    # 卡片阴影
    "card_text":    "#1a2a3a",    # 卡片主文字
    "card_sub":     "#6a8090",    # 卡片副文字
    "body_bg":      "#e8edf2",    # 页面整体背景
    "divider":      "#c8d4de",    # 分隔线
}


class HomePage(QWidget):
    """首页（主界面）"""

    # 信号
    quick_destination_clicked = pyqtSignal(str)   # 地图导航 → dest_id
    menu_clicked            = pyqtSignal(str)   # 菜单项点击 → item id
    voice_pressed           = pyqtSignal()       # 按下开始录音
    voice_released          = pyqtSignal()       # 松开停止录音
    search_submitted        = pyqtSignal(str)    # 搜索框回车 → 关键词

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(SCREEN_W, SCREEN_H)
        self._location_text = "正在获取位置..."
        self._voice_state   = "idle"
        self._init_ui()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_location)
        self._timer.start(1000)

    # ─────────────────────────────────────────────────────────────────────
    # UI 初始化
    # ─────────────────────────────────────────────────────────────────────

    def _init_ui(self):
        self.setStyleSheet(f"background-color: {_THEME['body_bg']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 顶部横幅 ───────────────────────────────────────────────────
        header = self._build_header()
        root.addWidget(header, stretch=0)

        # ── 菜单网格 ───────────────────────────────────────────────────
        menu_grid = self._build_menu_grid()
        root.addWidget(menu_grid, stretch=1)

    # ── 顶部横幅 ─────────────────────────────────────────────────────────

    def _build_header(self):
        header = QWidget()
        header.setFixedHeight(90)
        header.setStyleSheet(f"""
            background-color: {_THEME['header_bg']};
        """)

        hl = QHBoxLayout(header)
        hl.setContentsMargins(32, 0, 24, 0)
        hl.setSpacing(16)

        # 左侧：医院名称
        welcome_lbl = QLabel("仁济医院欢迎您")
        welcome_lbl.setStyleSheet(f"""
            color: {_THEME['header_text']};
            font: bold 38px "Microsoft YaHei";
        """)

        # 中间弹性空白（推搜索框到右侧）
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # 右侧：搜索框
        search_widget = self._build_search_box()

        hl.addWidget(welcome_lbl)
        hl.addWidget(spacer)
        hl.addWidget(search_widget)

        return header

    def _build_search_box(self):
        wrap = QWidget()
        wrap.setFixedSize(300, 52)

        self._search_input = QLineEdit(wrap)
        self._search_input.setFixedSize(300, 52)
        self._search_input.setPlaceholderText("搜索科室、医生、症状...")
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {_THEME['search_bg']};
                color: {_THEME['search_txt']};
                border: none;
                border-radius: 26px;
                padding: 0 28px 0 28px;
                font: 22px "Microsoft YaHei";
                selection-background-color: #4a80b0;
            }}
            QLineEdit::placeholder {{
                color: {_THEME['search_ph']};
            }}
        """)
        self._search_input.setCursorPosition(0)
        self._search_input.returnPressed.connect(self._on_search)

        return wrap

    def _on_search(self):
        text = self._search_input.text().strip()
        if text:
            self.search_submitted.emit(text)

    # ── 菜单网格 ─────────────────────────────────────────────────────────

    def _build_menu_grid(self):
        container = QWidget()

        # 背景图：直接显示原图，透过度由你自行调整
        self._bg_label = QLabel(container)
        self._bg_label.lower()                       # 放最底层
        self._bg_label.setScaledContents(True)
        self._bg_label.setStyleSheet("background-color: #e8eaf0;")

        def _update_bg():
            self._bg_label.resize(container.size())
            pm = QPixmap("/home/hyh/robot/src/背景.jpeg")
            if not pm.isNull():
                self._bg_label.setPixmap(pm.scaled(
                    container.size(),
                    Qt.KeepAspectRatioByExpanding,
                    Qt.SmoothTransformation,
                ))
                self._bg_label.setAlignment(Qt.AlignCenter)

        container.resizeEvent = lambda e: _update_bg()
        container.setStyleSheet("background-color: transparent;")
        QTimer.singleShot(0, _update_bg)

        # ── 外层 VBox：两行卡片（整体垂直居中）──────────────────────────
        vb = QVBoxLayout(container)
        vb.setContentsMargins(24, 10, 24, 10)
        vb.setSpacing(0)

        # 上方弹性（自动均分上下空间，实现两行组垂直居中）
        vb.addStretch(1)

        # 第一行：3 个均分
        row1 = QHBoxLayout()
        row1.setSpacing(16)
        for i in range(3):
            row1.addWidget(self._make_menu_card(MENU_ITEMS[i]), stretch=1)
        vb.addLayout(row1)

        # 两行间距 14px
        spacer = QWidget()
        spacer.setFixedHeight(14)
        vb.addWidget(spacer)

        # 第二行：2 个居中（两侧加弹性）
        row2 = QHBoxLayout()
        row2.addStretch(1)
        for i, idx in enumerate([3, 4]):
            row2.addWidget(self._make_menu_card(MENU_ITEMS[idx]), stretch=1)
        row2.addStretch(1)
        vb.addLayout(row2)

        # 下方弹性（配合上方 stretch=1 实现垂直居中）
        vb.addStretch(1)

        return container

    def _make_menu_card(self, item: dict) -> QWidget:
        card = QWidget()
        card.setFixedHeight(175)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        card.setCursor(Qt.PointingHandCursor)

        base_color = QColor(item["color"])
        light_color = base_color.lighter(145)
        dark_color  = base_color.darker(115)

        card.setStyleSheet(f"""
            QWidget {{
                background-color: {item["color"]};
                border-radius: 18px;
            }}
        """)

        vl = QVBoxLayout(card)
        vl.setContentsMargins(18, 16, 18, 14)
        vl.setSpacing(6)
        vl.addStretch()

        # 图标：emoji，系统字体均支持
        icons = {
            "nav":     "\U0001f5fa",   # 🗺 世界地图
            "reg":     "\U0001f3db",   # 🏛 建筑/挂号
            "query":   "\U0001f50d",   # 🔍 放大镜
            "report":  "\U0001f4cb",   # 📋 剪贴板
            "website": "\U0001f310",   # 🌐 地球
        }
        icon_lbl = QLabel(icons.get(item["id"], "\u2753"))
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setFont(QFont("Segoe UI Emoji, Apple Color Emoji, Noto Color Emoji, sans-serif", 36))
        icon_lbl.setStyleSheet("""
            background: transparent;
            color: rgba(255,255,255,0.95);
        """)

        name_lbl = QLabel(item["name"])
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setStyleSheet(f"""
            color: #ffffff;
            font: bold 30px "Microsoft YaHei";
            background: transparent;
        """)

        sub_lbl = QLabel(item["sub"])
        sub_lbl.setAlignment(Qt.AlignCenter)
        sub_lbl.setStyleSheet(f"""
            color: rgba(255,255,255,0.7);
            font: 20px "Microsoft YaHei";
            background: transparent;
        """)

        vl.addWidget(icon_lbl)
        vl.addWidget(name_lbl)
        vl.addWidget(sub_lbl)
        vl.addStretch()

        # 覆盖整卡点击
        card.mousePressEvent = lambda _, sid=item["id"]: self._on_menu(sid)
        for child in card.findChildren((QLabel,)):
            child.mousePressEvent = lambda _, sid=item["id"]: self._on_menu(sid)

        return card

    def _on_menu(self, item_id: str):
        self.menu_clicked.emit(item_id)

    # ─────────────────────────────────────────────────────────────────────
    # 外部接口
    # ─────────────────────────────────────────────────────────────────────

    def set_location(self, text: str):
        self._location_text = text

    def _refresh_location(self):
        pass  # 主窗口通过 set_location 更新

    @pyqtSlot()
    def reset(self):
        if hasattr(self, "_search_input"):
            self._search_input.clear()

    def set_search_text(self, text: str):
        """供主窗口把语音识别结果填入搜索框。"""
        if hasattr(self, "_search_input"):
            self._search_input.setText(text)
            self._search_input.setFocus()
            self._search_input.selectAll()
