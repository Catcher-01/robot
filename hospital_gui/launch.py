#!/usr/bin/env python3
"""
启动医院导诊机器人 GUI 前端。
用法：cd /home/hyh/robot
     python3 -m hospital_gui
"""

import sys
import os

# 确保 UTF-8 locale，防止中文路径/配置在 ASCII codec 下崩溃
os.environ.setdefault("LANG", "zh_CN.UTF-8")
os.environ.setdefault("LC_ALL", "zh_CN.UTF-8")

# Qt 平台 + ALSA
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
os.environ.pop("QT_PLUGIN_PATH",   None)
os.environ.pop("QT_DEBUG_PLUGINS", None)
os.environ.pop("ALSA_CONF_PATH",   None)   # 不干扰 ALSA 正常初始化

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
from hospital_gui.main_window import HospitalGUI


def main():
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    window = HospitalGUI()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
