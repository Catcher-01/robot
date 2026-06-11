"""
导航执行页：地图区（固定高度）+ 底部信息卡片。
卡片内包含目的地、导航指令、剩余距离、预计时间、取消按钮。
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from hospital_gui.config import (
    SCREEN_W, SCREEN_H,
)
from hospital_gui.widgets.rviz_view import RvizView as NavView


# ── 现代配色 ────────────────────────────────────────────────────────────────
_THEME = {
    "card_bg":    "#1a2332",    # 深邃蓝黑卡片
    "card_top":   "#243447",    # 卡片顶部高亮条
    "text_main":  "#ffffff",    # 主文字纯白
    "text_sub":   "#8da4be",    # 次要文字灰蓝
    "accent":     "#3dabff",    # 亮蓝强调色
    "progress":   "#3dabff",    # 进度条蓝
    "cancel_bg":  "#2d3a4d",    # 取消按钮背景
    "cancel_hv":  "#3d5068",    # 取消按钮悬停
    "divider":    "#2a3a4e",    # 分隔线
    "badge_bg":   "#2a3a4e",    # 标签背景
    "badge_text": "#3dabff",    # 标签文字
}


class NavigationPage(QWidget):
    """导航执行页"""

    cancel_navigation = pyqtSignal()
    back_home        = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(SCREEN_W, SCREEN_H)
        self._dest_name = ""
        self._last_dist = 999.0
        self._init_ui()

    def _init_ui(self):
        # 全页深色背景，与地图底色融为一体
        self.setStyleSheet(f"background-color: #0f1923;")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── 地图区：撑满上方，底部留出卡片空间 ────────────────────
        map_h = SCREEN_H - 220   # 220px 给底部卡片
        self._rviz_view = NavView(parent=self)
        self._rviz_view.setFixedHeight(map_h)
        main_layout.addWidget(self._rviz_view, stretch=1)

        # ── 底部信息卡片（悬浮感） ─────────────────────────────────
        card = QWidget()
        card.setFixedHeight(220)
        card.setStyleSheet(f"""
            QWidget {{
                background-color: {_THEME["card_bg"]};
                border-top-left-radius: 20px;
                border-top-right-radius: 20px;
            }}
        """)
        # 顶部圆角遮罩（QSS 无法单独控制上圆角，用内嵌渐变模拟）
        top_bar = QWidget(card)
        top_bar.setGeometry(0, 0, SCREEN_W, 4)
        top_bar.setStyleSheet(f"""
            background-color: {_THEME["accent"]};
            border-top-left-radius: 20px;
            border-top-right-radius: 20px;
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 14, 28, 18)
        card_layout.setSpacing(0)

        # ── 第一行：目的地 + 楼层徽章 ────────────────────────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        self._dest_label = QLabel("正在规划路径...")
        self._dest_label.setStyleSheet(f"""
            color: {_THEME["text_main"]};
            font: bold 32px "Microsoft YaHei";
        """)

        self._floor_badge = QLabel("1楼")
        self._floor_badge.setAlignment(Qt.AlignCenter)
        self._floor_badge.setStyleSheet(f"""
            background-color: {_THEME["badge_bg"]};
            color: {_THEME["badge_text"]};
            font: bold 20px "Microsoft YaHei";
            border-radius: 8px;
            padding: 2px 14px;
        """)

        top_row.addWidget(self._dest_label)
        top_row.addWidget(self._floor_badge)
        top_row.addStretch()

        # ── 第二行：导航指令 ─────────────────────────────────────────
        self._instruction_label = QLabel("")
        self._instruction_label.setStyleSheet(f"""
            color: {_THEME["text_sub"]};
            font: 24px "Microsoft YaHei";
            margin-top: 4px;
        """)

        # ── 第三行：剩余距离 + 预计时间 ─────────────────────────────
        info_row = QHBoxLayout()
        info_row.setSpacing(16)

        # 左侧：剩余距离
        self._dist_label = QLabel("")
        self._dist_label.setStyleSheet(f"""
            color: {_THEME["accent"]};
            font: bold 26px "Microsoft YaHei";
        """)

        # 右侧：预计时间
        self._eta_label = QLabel("")
        self._eta_label.setAlignment(Qt.AlignRight)
        self._eta_label.setStyleSheet(f"""
            color: {_THEME["text_sub"]};
            font: 24px "Microsoft YaHei";
        """)

        info_row.addWidget(self._dist_label)
        info_row.addWidget(self._eta_label)

        # ── 第四行：操作按钮 ─────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 10, 0, 0)

        # 取消按钮（胶囊形 pill button）
        btn_cancel = QPushButton("取消导航")
        btn_cancel.setFixedHeight(64)
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {_THEME["cancel_bg"]};
                color: {_THEME["text_sub"]};
                border: none;
                border-radius: 32px;
                font: bold 26px "Microsoft YaHei";
                padding-left: 36px;
                padding-right: 36px;
            }}
            QPushButton:hover {{
                background-color: {_THEME["cancel_hv"]};
                color: {_THEME["text_main"]};
            }}
            QPushButton:pressed {{
                background-color: #1e2a3a;
            }}
        """)
        btn_cancel.clicked.connect(lambda: self.cancel_navigation.emit())

        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()

        # 组装卡片
        card_layout.addLayout(top_row)
        card_layout.addWidget(self._instruction_label)
        card_layout.addLayout(info_row)
        card_layout.addLayout(btn_row)

        main_layout.addWidget(card)

    # ── 公开接口 ───────────────────────────────────────────────────

    def set_ros_bridge(self, ros):
        """连接 ROSBridge 的 map_updated 信号。"""
        ros.map_updated.connect(self._rviz_view.on_map)

    def set_destination(self, dest_id: str, x: float, y: float, name: str = ""):
        self._dest_name = name
        self._rviz_view.set_destination(x, y)
        if name:
            parts = name.rsplit(" ", 1)
            if len(parts) == 2:
                self._floor_badge.setText(parts[0])
                self._dest_label.setText(parts[1])
            else:
                self._dest_label.setText(name)

    def update_robot(self, x: float, y: float, yaw: float):
        self._rviz_view.set_robot(x, y, yaw)

    def update_path(self, path: list):
        self._rviz_view.set_path(path)

    def update_scan(self, scan: list):
        self._rviz_view.set_scan(scan)

    def update_instruction(self, instruction: str, distance: float, eta: float):
        self._instruction_label.setText(instruction)
        self._last_dist = distance
        if distance >= 0:
            self._dist_label.setText(f"剩余 {distance:.1f} 米")
        if eta >= 0:
            self._eta_label.setText(f"预计 {int(eta)} 秒")

    def set_idle(self):
        self._dest_label.setText("正在规划路径...")
        self._instruction_label.setText("")
        self._dist_label.setText("")
        self._eta_label.setText("")

    def reset(self):
        self._rviz_view.clear_destination()
        self._rviz_view.set_path([])
        self._rviz_view.set_scan([])
        self._dest_label.setText("正在规划路径...")
        self._instruction_label.setText("")
        self._dist_label.setText("")
        self._eta_label.setText("")

