"""
内嵌网页页面：顶部返回按钮 + QWebEngineView。
"""

from PyQt5.QtCore import pyqtSignal, QUrl
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PyQt5.QtWebEngineWidgets import QWebEngineView
from hospital_gui.config import SCREEN_W, SCREEN_H, COLOR_PRIMARY, COLOR_WHITE


class WebPage(QWidget):
    back_home = pyqtSignal()

    def __init__(self, url: str = ""):
        super().__init__()
        self._url = url
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 返回按钮
        self._back_btn = QPushButton("← 返回首页")
        self._back_btn.setFixedHeight(60)
        self._back_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_PRIMARY};
                color: {COLOR_WHITE};
                font-size: 20px;
                font-weight: bold;
                border: none;
            }}
            QPushButton:pressed {{
                background-color: #1a6fb4;
            }}
        """)
        self._back_btn.clicked.connect(self._on_back)

        layout.addWidget(self._back_btn)

        # 浏览器视图
        self._web_view = QWebEngineView()
        layout.addWidget(self._web_view, stretch=1)

        if self._url:
            self._web_view.load(QUrl(self._url))

    def load_url(self, url: str):
        self._url = url
        self._web_view.load(QUrl(url))

    def _on_back(self):
        self._web_view.stop()
        self.back_home.emit()
