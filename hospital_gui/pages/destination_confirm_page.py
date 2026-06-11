"""
目的地确认页：
  左侧（60%）：地图视图，显示机器人位置
  右侧（40%）：搜索框 + 全部分类地点列表 + 底部操作栏
点击地图上的点也可选目的地。
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QInputDialog, QLineEdit, QScrollArea,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QColor

from hospital_gui.config import (
    SCREEN_W, SCREEN_H,
    COLOR_WHITE, COLOR_TEXT, COLOR_PRIMARY, COLOR_GRAY,
    COLOR_WARNING, COLOR_SUCCESS,
    FONT_H1, FONT_H3, FONT_H4, FONT_BODY,
    BTN_SIZE_LARGE,
    ROOM_DISPLAY, QUICK_DESTINATIONS, ROOM_COORDS,
)
from hospital_gui.widgets.rviz_view import RvizView as NavView


# ── 分类地点（优先级从高到低）───────────────────────────────────────────────
_DEST_CATEGORIES = [
    {
        "title": "公共服务",
        "color": "#1565c0",
        "items": [
            {"id": "nurse",        "name": "护士站",        "floor": "1楼"},
            {"id": "registration", "name": "挂号处",        "floor": "1楼"},
            {"id": "payment",      "name": "缴费处",        "floor": "1楼"},
            {"id": "pharmacy",     "name": "药房",          "floor": "1楼"},
            {"id": "elevator",     "name": "电梯",          "floor": "1楼"},
            {"id": "surgery_a",   "name": "手术室A",       "floor": "1楼"},
            {"id": "rest_room",    "name": "休息室",         "floor": "1楼"},
            {"id": "office_a",     "name": "医生办公室A",   "floor": "1楼"},
            {"id": "office_b",     "name": "医生办公室B",   "floor": "1楼"},
        ],
    },
    {
        "title": "左侧病房",
        "color": "#00897b",
        "items": [
            {"id": "room_101", "name": "101病房", "floor": "1楼"},
            {"id": "room_102", "name": "102病房", "floor": "1楼"},
            {"id": "room_103", "name": "103病房", "floor": "1楼"},
            {"id": "room_104", "name": "104病房", "floor": "1楼"},
        ],
    },
    {
        "title": "右侧病房",
        "color": "#6a1b9a",
        "items": [
            {"id": "room_201", "name": "201病房", "floor": "1楼"},
            {"id": "room_202", "name": "202病房", "floor": "1楼"},
            {"id": "room_203", "name": "203病房", "floor": "1楼"},
            {"id": "room_204", "name": "204病房", "floor": "1楼"},
            {"id": "room_205", "name": "205病房", "floor": "1楼"},
        ],
    },
]


# ── 配色主题 ────────────────────────────────────────────────────────────────
_THEME = {
    "panel_bg":   "#1a2332",   # 右侧面板深蓝黑
    "panel_top":  "#243447",   # 面板顶部
    "accent":     "#3dabff",   # 强调蓝
    "text_main":  "#ffffff",   # 主文字纯白
    "text_sub":   "#8da4be",   # 次要文字灰蓝
    "badge_bg":   "#2a3a4e",   # 标签背景
    "divider":    "#2a3a4e",   # 分隔线
}


class DestinationConfirmPage(QWidget):
    """目的地确认页"""

    destination_selected = pyqtSignal(str)   # dest_id
    back_home            = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(SCREEN_W, SCREEN_H)
        self._selected_dest: str = ""
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("background-color: #0f1923;")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 左侧地图（60%）────────────────────────────────────────
        self._map_view = NavView(parent=self)
        self._map_view.map_clicked.connect(self._on_map_clicked)
        root.addWidget(self._map_view, stretch=6)

        # ── 右侧面板（40%）────────────────────────────────────────
        panel = self._build_panel()
        root.addWidget(panel, stretch=4)

    def _build_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background-color: {_THEME['panel_bg']};")

        vl = QVBoxLayout(panel)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        # 顶部蓝条
        top_bar = QWidget()
        top_bar.setFixedHeight(5)
        top_bar.setStyleSheet(f"background-color: {_THEME['accent']};")

        # ── 搜索框行 ────────────────────────────────────────────────
        search_row = QWidget()
        search_row.setFixedHeight(80)
        search_row.setStyleSheet(f"background-color: {_THEME['panel_top']};")
        sr = QHBoxLayout(search_row)
        sr.setContentsMargins(16, 12, 16, 12)
        sr.setSpacing(12)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索科室或地点...")
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {_THEME['badge_bg']};
                color: {_THEME['text_main']};
                border: none;
                border-radius: 10px;
                padding: 0 16px 0 16px;
                font: 24px "Microsoft YaHei";
            }}
            QLineEdit::placeholder {{
                color: {_THEME['text_sub']};
            }}
        """)
        self._search_input.returnPressed.connect(self._on_search_input)

        btn_search = QPushButton("搜索")
        btn_search.setFixedWidth(90)
        btn_search.setStyleSheet(f"""
            QPushButton {{
                background-color: {_THEME['accent']};
                color: #ffffff;
                border: none;
                border-radius: 10px;
                font: bold 22px "Microsoft YaHei";
            }}
            QPushButton:pressed {{ background-color: #2a8acc; }}
        """)
        btn_search.clicked.connect(self._on_search_input)
        sr.addWidget(self._search_input, stretch=1)
        sr.addWidget(btn_search)

        # ── 标题行 ────────────────────────────────────────────────
        title_row = QWidget()
        title_row.setFixedHeight(56)
        title_row.setStyleSheet(f"background-color: {_THEME['panel_bg']};")
        tr = QHBoxLayout(title_row)
        tr.setContentsMargins(20, 0, 20, 0)

        title_lbl = QLabel("请选择目的地")
        title_lbl.setStyleSheet(f"""
            color: {_THEME['text_main']};
            font: bold 28px "Microsoft YaHei";
        """)
        hint_lbl = QLabel("点击卡片导航")
        hint_lbl.setStyleSheet(f"""
            color: {_THEME['text_sub']};
            font: 20px "Microsoft YaHei";
        """)
        tr.addWidget(title_lbl)
        tr.addStretch()
        tr.addWidget(hint_lbl)

        # ── 可滚动地点列表 ──────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: transparent;
                width: 6px;
                margin: 4px 2px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {_THEME['badge_bg']};
                border-radius: 3px;
            }}
        """)

        list_container = QWidget()
        list_vl = QVBoxLayout(list_container)
        list_vl.setContentsMargins(14, 10, 14, 10)
        list_vl.setSpacing(14)

        self._dest_widgets: dict = {}   # dest_id -> widget

        for cat in _DEST_CATEGORIES:
            # 分类标题
            cat_lbl = QLabel(cat["title"])
            cat_lbl.setStyleSheet(f"""
                color: {cat["color"]};
                font: bold 22px "Microsoft YaHei";
            """)
            list_vl.addWidget(cat_lbl)

            # 分类内卡片网格（2列）
            grid = QHBoxLayout()
            grid.setSpacing(10)

            left_col = QVBoxLayout()
            right_col = QVBoxLayout()
            left_col.setSpacing(10)
            right_col.setSpacing(10)

            for idx, item in enumerate(item for item in cat["items"]):
                card = self._make_dest_card(item, cat["color"])
                if idx % 2 == 0:
                    left_col.addWidget(card)
                else:
                    right_col.addWidget(card)
                self._dest_widgets[item["id"]] = card

            # 奇数时补一个占位空widget保持对齐
            if len(cat["items"]) % 2 == 1:
                pad = QWidget()
                pad.setFixedHeight(80)
                right_col.addWidget(pad)

            grid.addLayout(left_col, stretch=1)
            grid.addLayout(right_col, stretch=1)
            list_vl.addLayout(grid)

        list_vl.addStretch()

        scroll.setWidget(list_container)

        # ── 底部操作栏 ──────────────────────────────────────────────
        bottom = QWidget()
        bottom.setFixedHeight(80)
        bottom.setStyleSheet(f"background-color: {_THEME['panel_bg']};")
        br = QHBoxLayout(bottom)
        br.setContentsMargins(20, 10, 20, 14)

        btn_confirm = QPushButton("确认导航")
        btn_confirm.setFixedHeight(56)
        btn_confirm.setStyleSheet(f"""
            QPushButton {{
                background-color: {_THEME['accent']};
                color: #ffffff;
                border: none;
                border-radius: 28px;
                font: bold 26px "Microsoft YaHei";
                padding-left: 36px;
                padding-right: 36px;
            }}
            QPushButton:pressed {{ background-color: #2a8acc; }}
        """)
        btn_confirm.clicked.connect(self._on_confirm)

        btn_back = QPushButton("返回首页")
        btn_back.setFixedHeight(56)
        btn_back.setStyleSheet(f"""
            QPushButton {{
                background-color: {_THEME['badge_bg']};
                color: {_THEME['text_sub']};
                border: none;
                border-radius: 28px;
                font: bold 24px "Microsoft YaHei";
                padding-left: 24px;
                padding-right: 24px;
            }}
            QPushButton:hover {{
                background-color: #3d5068;
                color: {_THEME['text_main']};
            }}
        """)
        btn_back.clicked.connect(lambda: self.back_home.emit())

        self._btn_confirm = btn_confirm
        br.addWidget(btn_back)
        br.addStretch()
        br.addWidget(btn_confirm)

        vl.addWidget(top_bar)
        vl.addWidget(search_row)
        vl.addWidget(title_row)
        vl.addWidget(scroll, stretch=1)
        vl.addWidget(bottom)

        return panel

    def _make_dest_card(self, item: dict, accent_color: str) -> QWidget:
        card = QWidget()
        card.setFixedHeight(80)
        card.setCursor(Qt.PointingHandCursor)
        card.setStyleSheet(f"""
            background-color: {_THEME['badge_bg']};
            border-radius: 12px;
            border-left: 4px solid {accent_color};
        """)
        card._dest_id = item["id"]

        hl = QHBoxLayout(card)
        hl.setContentsMargins(12, 0, 12, 0)
        hl.setSpacing(8)

        name_lbl = QLabel(item["name"])
        name_lbl.setStyleSheet(f"""
            color: {_THEME['text_main']};
            font: bold 24px "Microsoft YaHei";
        """)

        floor_lbl = QLabel(item["floor"])
        floor_lbl.setAlignment(Qt.AlignRight)
        floor_lbl.setStyleSheet(f"""
            color: {accent_color};
            font: 20px "Microsoft YaHei";
        """)

        hl.addWidget(name_lbl, stretch=1)
        hl.addWidget(floor_lbl)

        card.mousePressEvent = lambda e, did=item["id"]: self._select_dest(did)
        for child in card.findChildren((QLabel,)):
            child.mousePressEvent = lambda e, did=item["id"]: self._select_dest(did)

        return card

    def _select_dest(self, dest_id: str):
        """选中某个目的地，高亮并更新确认按钮。"""
        self._selected_dest = dest_id

        # 重置所有卡片样式
        for did, card in self._dest_widgets.items():
            accent = self._get_accent_for_dest(did)
            is_sel = (did == dest_id)
            if is_sel:
                card.setStyleSheet(f"""
                    background-color: #1e3a5c;
                    border-radius: 12px;
                    border-left: 4px solid {_THEME['accent']};
                """)
            else:
                card.setStyleSheet(f"""
                    background-color: {_THEME['badge_bg']};
                    border-radius: 12px;
                    border-left: 4px solid {accent};
                """)

    def _get_accent_for_dest(self, dest_id: str) -> str:
        for cat in _DEST_CATEGORIES:
            for item in cat["items"]:
                if item["id"] == dest_id:
                    return cat["color"]
        return _THEME["accent"]

    def _on_confirm(self):
        if self._selected_dest:
            self.destination_selected.emit(self._selected_dest)

    def _on_search_input(self):
        text = self._search_input.text().strip()
        if not text:
            return
        matches = self._search_dests(text)
        if matches:
            self._select_dest(matches[0])
            self._on_confirm()
        else:
            self._show_fail_dialog()

    def _search_dests(self, keyword: str) -> list:
        kw = keyword.lower()
        results = []
        for cat in _DEST_CATEGORIES:
            for item in cat["items"]:
                name = item["name"].lower()
                if kw in name or kw in item["id"].lower():
                    results.append(item["id"])
        return results

    def _show_fail_dialog(self):
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.warning(self, "未找到", "未找到匹配的目的地，请重试", QMessageBox.Ok)

    def _on_map_clicked(self, wx: float, wy: float):
        """用户点击地图时，自动选最近的目的地。"""
        best_id, best_dist = None, float("inf")
        for dest_id, (x, y, _) in ROOM_COORDS.items():
            d = (wx - x) ** 2 + (wy - y) ** 2
            if d < best_dist:
                best_dist = d
                best_id = dest_id
        if best_id and best_dist < 25:   # 5m 半径内
            self._select_dest(best_id)

    # ── ROS 数据更新 ───────────────────────────────────────────────

    def set_ros_bridge(self, ros):
        ros.map_updated.connect(self._map_view.on_map)

    def update_robot(self, x: float, y: float, yaw: float):
        self._map_view.set_robot(x, y, yaw)

    def update_scan(self, scan: list):
        self._map_view.set_scan(scan)

    # ── 重置 ───────────────────────────────────────────────────────

    def reset(self):
        self._selected_dest = ""
        for did, card in self._dest_widgets.items():
            accent = self._get_accent_for_dest(did)
            card.setStyleSheet(f"""
                background-color: {_THEME['badge_bg']};
                border-radius: 12px;
                border-left: 4px solid {accent};
            """)
        if hasattr(self, "_search_input"):
            self._search_input.clear()
        self._map_view.clear_destination()
        self._map_view.set_path([])
        self._map_view.set_scan([])
