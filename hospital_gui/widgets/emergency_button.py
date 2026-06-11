"""
全局悬浮紧急求助按钮：右下角偏上，圆形红色电话图标按钮。
"""

from PyQt5.QtWidgets import QPushButton, QMessageBox, QWidget
from PyQt5.QtCore import Qt, pyqtSignal


class EmergencyButton(QWidget):
    clicked_emergency = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(80, 80)

        self._btn = QPushButton(self)
        self._btn.setFixedSize(80, 80)
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.raise_()

        self._update_style()
        self._btn.clicked.connect(self._on_click)

        # 悬浮阴影效果（用额外边框模拟）
        self._btn.setGraphicsEffect(None)

    def _update_style(self):
        self._btn.setStyleSheet("""
            QPushButton {
                background-color: #c62828;
                border: none;
                border-radius: 40px;
                font: 42px "Segoe UI Symbol", "Apple Symbols", sans-serif;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #b71c1c;
            }
        """)
        self._btn.setText("\U0000260E")   # ☎ 电话符号

    def _on_click(self):
        reply = QMessageBox.question(
            self,
            "紧急求助确认",
            "确定要发起紧急求助吗？\n将自动拨打护士站电话并发送当前位置。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.clicked_emergency.emit()

    def enterEvent(self, event):
        self._btn.setStyleSheet("""
            QPushButton {
                background-color: #e53935;
                border: none;
                border-radius: 40px;
                font-family: "Segoe UI Symbol", "Apple Symbols", sans-serif;
            }
        """)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._update_style()
        super().leaveEvent(event)
