"""
HospitalGUI 主窗口：管理5个页面的切换 + 全局紧急按钮。
页面：首页 | 目的地确认页 | 导航执行页 | 到达完成页
"""

import sys
import time
import subprocess
import threading
import math

from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QLabel
from PyQt5.QtCore import Qt, QTimer, pyqtSlot
from PyQt5.QtGui import QFont

from hospital_gui.config import (
    SCREEN_W, SCREEN_H,
    COLOR_WHITE, COLOR_TEXT,
    FONT_H2, FONT_H4,
    ROOM_COORDS, ROOM_DISPLAY, QUICK_DESTINATIONS,
    EXTERNAL_URLS,
)
from hospital_gui.ros_bridge import ROSBridge
from hospital_gui.pages.home_page import HomePage
from hospital_gui.pages.destination_confirm_page import DestinationConfirmPage
from hospital_gui.pages.navigation_page import NavigationPage
from hospital_gui.pages.arrival_page import ArrivalPage
from hospital_gui.pages.web_page import WebPage
from hospital_gui.widgets.emergency_button import EmergencyButton
from hospital_gui.widgets.ai_assistant import AIAssistant


class HospitalGUI(QMainWindow):
    """
    主窗口：1280×800 竖屏。
    管理页面栈 + 全局紧急求助按钮 + ROS 桥接。
    """

    PAGE_HOME          = 0
    PAGE_DEST_CONFIRM  = 1
    PAGE_NAVIGATION    = 2
    PAGE_ARRIVAL       = 3
    PAGE_WEB           = 4

    def __init__(self):
        super().__init__()
        self.setFixedSize(SCREEN_W, SCREEN_H)
        self.setWindowTitle("医院导诊机器人")
        self.setStyleSheet(f"background-color: {COLOR_WHITE};")
        self._current_page = self.PAGE_HOME
        self._last_nav_instruction_time = 0.0
        self._last_path = []

        self._init_ui()
        self._init_ros()
        self._init_connections()

        # 位置每秒刷新
        self._pos_timer = QTimer(self)
        self._pos_timer.timeout.connect(self._update_position_label)
        self._pos_timer.start(1000)

    # ── UI 初始化 ─────────────────────────────────────────────────

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 页面栈
        self._stack = QStackedWidget()
        self._home_page         = HomePage()
        self._dest_confirm_page = DestinationConfirmPage()
        self._nav_page          = NavigationPage()
        self._arrival_page      = ArrivalPage()

        self._stack.addWidget(self._home_page)          # 0
        self._stack.addWidget(self._dest_confirm_page)  # 1
        self._stack.addWidget(self._nav_page)            # 2
        self._stack.addWidget(self._arrival_page)        # 3
        self._web_page = WebPage()
        self._stack.addWidget(self._web_page)            # 4

        root_layout.addWidget(self._stack, stretch=1)

        # 全局紧急求助按钮：左下角（屏幕底部往上留边距，不遮挡右侧面板底栏）
        self._emergency_btn = EmergencyButton()
        self._emergency_btn.setParent(central)
        self._emergency_btn.move(10, SCREEN_H - 100)
        self._emergency_btn.raise_()

        # 全局悬浮AI助手"小智"：右上角（AIAssistant 本身不可见，由其内部的
        # FloatingButton / ChatPanel 两个独立窗口实现悬浮交互）
        self._ai_assistant = AIAssistant(self)

    def _init_ros(self):
        self._ros = ROSBridge()
        self._ros.start()

    def _init_connections(self):
        # 首页
        self._home_page.quick_destination_clicked.connect(self._on_quick_destination)
        self._home_page.voice_pressed.connect(self._on_voice_pressed)
        self._home_page.voice_released.connect(self._on_voice_released)
        self._home_page.menu_clicked.connect(self._on_menu_clicked)
        self._home_page.search_submitted.connect(self._on_search_submitted)

        # 目的地确认页
        self._dest_confirm_page.destination_selected.connect(self._on_destination_selected)
        self._dest_confirm_page.back_home.connect(self._go_home)
        self._dest_confirm_page.set_ros_bridge(self._ros)

        # 导航页
        self._nav_page.cancel_navigation.connect(self._on_cancel_navigation)
        self._nav_page.back_home.connect(self._go_home)

        # 到达页
        self._arrival_page.back_home.connect(self._go_home)

        # 网页内嵌页
        self._web_page.back_home.connect(self._go_home)

        # 紧急按钮
        self._emergency_btn.clicked_emergency.connect(self._on_emergency)

        # ROS 信号
        self._ros.position_updated.connect(self._on_ros_position)
        self._ros.path_updated.connect(self._on_ros_path)
        self._ros.scan_updated.connect(self._on_ros_scan)
        self._ros.nav_instruction.connect(self._on_nav_instruction)
        self._ros.arrived_at_dest.connect(self._on_arrived)
        self._ros.voice_result_ready.connect(self._on_voice_result)
        self._ros.nav_status_changed.connect(self._on_nav_status_changed)
        self._nav_page.set_ros_bridge(self._ros)

    # ── 页面切换 ──────────────────────────────────────────────────

    def _switch_page(self, idx: int):
        self._current_page = idx
        self._stack.setCurrentIndex(idx)

    def _go_home(self):
        self._home_page.reset()
        self._dest_confirm_page.reset()
        self._nav_page.reset()
        self._arrival_page.reset()
        self._ros.cancel_navigation()
        self._switch_page(self.PAGE_HOME)

    # ── 快捷目的地（首页按钮）────────────────────────────────────

    def _on_quick_destination(self, dest_id: str):
        self._start_navigation(dest_id)

    # ── 菜单项点击 ─────────────────────────────────────────────────
    def _on_menu_clicked(self, item_id: str):
        if item_id == "nav":
            self._switch_page(self.PAGE_DEST_CONFIRM)
        elif item_id in EXTERNAL_URLS:
            self._show_web(EXTERNAL_URLS[item_id])

    def _show_web(self, url: str):
        self._web_page.load_url(url)
        self._switch_page(self.PAGE_WEB)

    # ── 搜索框 ──────────────────────────────────────────────────────
    def _on_search_submitted(self, keyword: str):
        self._speak(f"正在搜索{keyword}，请稍候")

    # ── 语音 ──────────────────────────────────────────────────────

    def _on_voice_pressed(self):
        self._start_recording()

    def _on_voice_released(self):
        self._stop_recording_and_recognize()

    def _start_recording(self):
        pass  # 现在由 record_until_silence 在停止时统一处理

    def _stop_recording_and_recognize(self):
        def recognize():
            try:
                sys.path.insert(0, "/home/hyh/robot/hospital_ws/src/voice_control")
                from voice_control import voice_node
                _, text = voice_node.record_until_silence(timeout_s=6)
            except Exception as e:
                print(f"[Voice] 识别失败: {e}")
                text = ""

            dest_ids = self._match_text_to_dest(text) if text.strip() else []
            self._on_voice_result_signal(dest_ids, text)

        threading.Thread(target=recognize, daemon=True).start()

    def _on_voice_result_signal(self, dest_ids: list, text: str = ""):
        from PyQt5.QtCore import QMetaObject, Qt, Q_ARG
        if text.strip():
            QMetaObject.invokeMethod(
                self._home_page, "set_search_text",
                Qt.QueuedConnection, Q_ARG(str, text)
            )
        if dest_ids:
            QMetaObject.invokeMethod(
                self._dest_confirm_page, "set_results",
                Qt.QueuedConnection, Q_ARG(list, dest_ids)
            )
            QMetaObject.invokeMethod(self, "_switch_page", Qt.QueuedConnection, Q_ARG(int, self.PAGE_DEST_CONFIRM))
        elif text.strip():
            QMetaObject.invokeMethod(self, "_switch_page", Qt.QueuedConnection, Q_ARG(int, self.PAGE_HOME))

    @pyqtSlot(str, str)
    def _show_error(self, title: str, msg: str):
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.warning(self, title, msg, QMessageBox.Ok)
        self._go_home()

    def _match_text_to_dest(self, text: str) -> list:
        text = text.lower()
        matches = []
        keywords = {
            # 公共服务
            "挂号": "registration", "guahao": "registration",
            "缴费": "payment", "jiaofei": "payment",
            "取药": "pharmacy", "quyao": "pharmacy", "药房": "pharmacy",
            "电梯": "elevator", "dianti": "elevator",
            "护士": "nurse", "hushi": "nurse",
            "手术": "surgery_a", "手术室": "surgery_a",
            "休息": "rest_room", "休息室": "rest_room",
            "办公室": "office_a", "医生办公室": "office_a",
            # 病房
            "101": "room_101",
            "102": "room_102",
            "103": "room_103",
            "104": "room_104",
            "201": "room_201",
            "202": "room_202",
            "203": "room_203",
            "204": "room_204",
            "205": "room_205",
        }
        for keyword, dest_id in keywords.items():
            if keyword in text and dest_id not in matches:
                matches.append(dest_id)
        return matches[:3]

    # ── 目的地确认 ────────────────────────────────────────────────

    def _on_destination_selected(self, dest_id: str):
        self._start_navigation(dest_id)

    def _start_navigation(self, dest_id: str):
        if dest_id not in ROOM_COORDS:
            return
        x, y, yaw = ROOM_COORDS[dest_id]
        floor, name = ROOM_DISPLAY.get(dest_id, ("?", dest_id))
        dest_label = f"{floor} {name}"

        # 启动新导航前，强制清理旧状态，防止二次导航残留
        self._nav_page.reset()
        self._ros.cancel_navigation()

        self._nav_page.set_destination(dest_id, x, y, dest_label)
        self._switch_page(self.PAGE_NAVIGATION)
        if self._last_path:
            self._nav_page.update_path(self._last_path)
        self._ros.navigate_to(dest_id, x, y, yaw)

    # ── 取消导航 ─────────────────────────────────────────────────

    def _on_cancel_navigation(self):
        self._ros.cancel_navigation()
        self._go_home()

    # ── ROS 回调 ──────────────────────────────────────────────────

    def _on_ros_position(self, x: float, y: float, yaw: float):
        if self._current_page == self.PAGE_NAVIGATION:
            self._nav_page.update_robot(x, y, yaw)
        elif self._current_page == self.PAGE_DEST_CONFIRM:
            self._dest_confirm_page.update_robot(x, y, yaw)

    def _on_ros_path(self, path: list):
        self._last_path = path
        if self._current_page == self.PAGE_NAVIGATION:
            self._nav_page.update_path(path)

    def _on_ros_scan(self, scan: list):
        if self._current_page == self.PAGE_NAVIGATION:
            self._nav_page.update_scan(scan)
        elif self._current_page == self.PAGE_DEST_CONFIRM:
            self._dest_confirm_page.update_scan(scan)

    def _on_nav_instruction(self, instruction: str, distance: float, eta: float):
        now = time.time()
        # ≥3秒间隔播报
        if now - self._last_nav_instruction_time >= 3.0:
            self._last_nav_instruction_time = now
            if self._current_page == self.PAGE_NAVIGATION:
                self._nav_page.update_instruction(instruction, distance, eta)
            self._speak(instruction)

    def _on_arrived(self, dest_id: str):
        floor, name = ROOM_DISPLAY.get(dest_id, ("?", dest_id))
        self._arrival_page.show_arrival(f"{floor} {name}")
        self._switch_page(self.PAGE_ARRIVAL)
        self._speak(f"已到达{name}，请您慢走")

    def _on_nav_status_changed(self, status: str):
        pass  # 已在各处理方法中覆盖

    def _on_voice_result(self, dest_ids: list):
        self._on_voice_result_signal(dest_ids)

    # ── 紧急求助 ─────────────────────────────────────────────────

    def _on_emergency(self):
        x = self._ros._cur_x
        y = self._ros._cur_y
        self._speak("正在发起紧急求助")
        # 调用医院电话或 ROS 服务
        try:
            subprocess.Popen(["bash", "-c",
                f'echo "紧急求助！机器人位置：({x:.1f}, {y:.1f})" | '
                f'mutt -s "紧急求助" nurse@hospital.local || '
                f'notify-send "紧急求助" "机器人位置：({x:.1f}, {y:.1f})"'
            ])
        except Exception:
            pass

    # ── 位置标签刷新 ─────────────────────────────────────────────

    def _update_position_label(self):
        x = self._ros._cur_x
        y = self._ros._cur_y
        if y > 10:
            floor, area = "1楼", "大厅"
        elif y > 2:
            floor, area = "1楼", "护士站附近"
        elif y > -8:
            floor, area = "1楼", "手术室走廊"
        else:
            floor, area = "1楼", "深处走廊"
        self._home_page.set_location(f"{floor} {area}，坐标 ({x:.1f}, {y:.1f})")

    # ── 语音播报 ─────────────────────────────────────────────────

    def _speak(self, text: str):
        def run():
            try:
                import edge_tts
                import asyncio

                async def main():
                    communicate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
                    await communicate.save("/tmp/tts_output.mp3")

                asyncio.run(main())
                subprocess.Popen(["mpg123", "-q", "/tmp/tts_output.mp3"])
            except Exception as e:
                print(f"[TTS] 播报失败: {e}")

        threading.Thread(target=run, daemon=True).start()

    # ── 窗口关闭 ─────────────────────────────────────────────────

    def closeEvent(self, event):
        self._ros.stop()
        super().closeEvent(event)
