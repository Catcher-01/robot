"""
到达完成页：全屏居中。
绿色对勾图标 + 文字 + 返回首页按钮。
30秒无操作自动返回首页。
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QGraphicsScene, QGraphicsView, QGraphicsPixmapItem
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QPainter, QColor, QPen, QPixmap, QPainterPath

from hospital_gui.config import (
    SCREEN_W, SCREEN_H,
    COLOR_WHITE, COLOR_SUCCESS, COLOR_TEXT, COLOR_PRIMARY,
    FONT_H1, FONT_H3, FONT_BODY,
    BTN_SIZE_XL,
)


class ArrivalPage(QWidget):
    """到达完成页"""

    back_home = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(SCREEN_W, SCREEN_H)
        self._dest_name = ""
        self._auto_timer = QTimer(self)
        self._auto_timer.timeout.connect(self._on_auto_back)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet(f"background-color: {COLOR_WHITE};")

        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)
        main_layout.setSpacing(30)

        # 绿色对勾（用 QPixmap 画一个简单图标）
        check_pixmap = self._draw_check_icon(150)
        check_label = QLabel()
        check_label.setPixmap(check_pixmap)
        check_label.setAlignment(Qt.AlignCenter)

        # 主文字
        self._title_label = QLabel("已到达目的地")
        self._title_label.setAlignment(Qt.AlignCenter)
        self._title_label.setStyleSheet(f"""
            color: {COLOR_SUCCESS};
            font: bold 48px "Microsoft YaHei";
        """)

        # 目的地名
        self._dest_label = QLabel("")
        self._dest_label.setAlignment(Qt.AlignCenter)
        self._dest_label.setStyleSheet(f"""
            color: {COLOR_TEXT};
            font: 32px "Microsoft YaHei";
        """)

        # 返回按钮
        btn_home = QPushButton("返回首页")
        btn_home.setFixedSize(*BTN_SIZE_XL)
        btn_home.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_PRIMARY};
                color: {COLOR_WHITE};
                border: none;
                border-radius: 10px;
                font: bold 28px "Microsoft YaHei";
            }}
            QPushButton:pressed {{ background-color: #0d1447; }}
        """)
        btn_home.clicked.connect(self._on_back)

        main_layout.addWidget(check_label)
        main_layout.addWidget(self._title_label)
        main_layout.addWidget(self._dest_label)
        main_layout.addWidget(btn_home)

    def _draw_check_icon(self, size: int) -> QPixmap:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        # 绿色圆
        painter.setBrush(QColor("#2e7d32"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, size, size)
        # 白色勾
        pen = QPen(QColor("#ffffff"))
        pen.setWidth(10)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        path = QPainterPath()
        s = size * 0.25
        e = size * 0.45
        path.moveTo(size * 0.25, size * 0.50)
        path.lineTo(size * 0.42, size * 0.68)
        path.lineTo(size * 0.75, size * 0.30)
        painter.drawPath(path)
        painter.end()
        return pixmap

    def show_arrival(self, dest_name: str):
        self._dest_name = dest_name
        self._dest_label.setText(dest_name)
        self._auto_timer.start(30000)   # 30秒自动返回

    def _on_back(self):
        self._auto_timer.stop()
        self.back_home.emit()

    def _on_auto_back(self):
        self._auto_timer.stop()
        self.back_home.emit()

    def reset(self):
        self._auto_timer.stop()
