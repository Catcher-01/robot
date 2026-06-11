"""
全局配置：分辨率、颜色、房间数据、路径。
固定 1280×800 竖屏，无需响应式。
"""

from PyQt5.QtCore import QSize

# ─── 屏幕 ───────────────────────────────────────────────────────────
SCREEN_W = 1280
SCREEN_H = 800

# ─── 颜色 ───────────────────────────────────────────────────────────
COLOR_PRIMARY    = "#1a237e"   # 深蓝（快捷按钮背景）
COLOR_SECONDARY  = "#e8eaf6"   # 浅蓝灰（卡片背景）
COLOR_ACCENT     = "#d32f2f"   # 红色（紧急求助）
COLOR_SUCCESS    = "#2e7d32"   # 绿色（到达/确认）
COLOR_WARNING    = "#f9a825"   # 黄色（推荐标签）
COLOR_GRAY       = "#9e9e9e"   # 灰色（返回按钮）
COLOR_WHITE      = "#ffffff"
COLOR_BLACK      = "#000000"
COLOR_TEXT       = "#212121"

COLOR_VOICE_DEFAULT    = "#c62828"  # 红色（按住说话）
COLOR_VOICE_ACTIVE     = "#2e7d32"  # 绿色（正在听）
COLOR_VOICE_PROCESSING = "#1565c0"  # 蓝色（正在识别）

# ─── 字体 ───────────────────────────────────────────────────────────
FONT_TITLE  = ("Microsoft YaHei", 48, "bold")
FONT_H1     = ("Microsoft YaHei", 40, "bold")
FONT_H2     = ("Microsoft YaHei", 36, "bold")
FONT_H3     = ("Microsoft YaHei", 32, "normal")
FONT_H4     = ("Microsoft YaHei", 28, "bold")
FONT_BODY   = ("Microsoft YaHei", 24, "normal")
FONT_SMALL  = ("Microsoft YaHei", 20, "normal")
FONT_BTN    = ("Microsoft YaHei", 28, "bold")

# ─── 按钮尺寸 ───────────────────────────────────────────────────────
BTN_SIZE_BIG   = (220, 120)    # 快捷按钮
BTN_SIZE_LARGE = (150, 80)     # 返回/手动输入
BTN_SIZE_XL    = (200, 100)    # 返回首页（大页）
BTN_VOICE_D    = 400           # 语音按钮直径
BTN_EMERGENCY  = (100, 100)    # 紧急求助

# ─── 外部链接 ─────────────────────────────────────────────────────────
EXTERNAL_URLS = {
    "reg":     "https://yuyue.renji.com:8889/booking/",
    "website": "https://www.renji.com/",
    "query":   "https://yuyue.renji.com:8889/booking/",
    "report":  "https://yuyue.renji.com:8889/booking/",
}

# ─── 菜单项（首页主菜单）───────────────────────────────────────────────
MENU_ITEMS = [
    {
        "id":   "nav",
        "name": "地图导航",
        "sub":  "院内精准导航",
        "color": "#1565c0",
    },
    {
        "id":   "reg",
        "name": "自助挂号",
        "sub":  "快速预约科室",
        "color": "#00897b",
    },
    {
        "id":   "query",
        "name": "自助查询",
        "sub":  "费用与报告查询",
        "color": "#6a1b9a",
    },
    {
        "id":   "report",
        "name": "校验单查询",
        "sub":  "化验检验报告",
        "color": "#ef6c00",
    },
    {
        "id":   "website",
        "name": "医院官网",
        "sub":  "了解更多资讯",
        "color": "#37474f",
    },
]

# ─── 快捷目的地（导航菜单内部快捷入口）─────────────────────────────
QUICK_DESTINATIONS = [
    {"id": "elevator",     "name": "电梯",       "floor": "1楼", "detail": "电梯"},
    {"id": "payment",      "name": "缴费处",      "floor": "1楼", "detail": "缴费处"},
    {"id": "registration", "name": "挂号处",      "floor": "1楼", "detail": "挂号处"},
    {"id": "nurse",       "name": "护士站",      "floor": "1楼", "detail": "护士站"},
    {"id": "surgery_a",   "name": "手术室A",    "floor": "1楼", "detail": "手术室A"},
    {"id": "pharmacy",    "name": "药房",        "floor": "1楼", "detail": "药房"},
]

# ─── 房间坐标（map 坐标系）────────────────────────────────────────────
ROOM_COORDS = {
    # 左侧病房（x ≈ -8.5）
    "room_101": (-8.5,  11.0, 0.0),
    "room_102": (-8.5,   4.75, 0.0),
    "room_103": (-8.5,  -4.75, 0.0),
    "room_104": (-8.5, -18.0,  0.0),
    # 右侧病房（x ≈ +8.5）
    "room_201": ( 8.5,  11.0, 3.14159),
    "room_202": ( 8.5,   4.75, 3.14159),
    "room_203": ( 8.5,  -4.75, 3.14159),
    "room_204": ( 8.5, -18.0,  3.14159),
    # 特殊房间
    "room_205": ( 6.0, -28.0, 3.14159),   # 205病房
    # 公共区域
    "elevator":     ( 0.0,  15.0, 0.0),   # 电梯
    "payment":      (-3.5,  5.5,  0.0),   # 缴费处
    "registration": ( 3.5,  5.5,  0.0),   # 挂号处
    "nurse":        ( 0.0,  10.0, 0.0),   # 护士站
    "surgery_a":    (-3.0, -15.0, 0.0),   # 手术室A
    "pharmacy":     ( 3.0, -15.0, 0.0),   # 药房
    "rest_room":    (-10.0,-27.0, 0.0),   # 休息室
    "office_a":     (-1.0, -3.0,  0.0),   # 医生办公室A
    "office_b":     ( 1.0, -3.0,  0.0),   # 医生办公室B
}

# ─── 显示名称 ────────────────────────────────────────────────────────
ROOM_DISPLAY = {
    "room_101": ("1楼", "101病房"),
    "room_102": ("1楼", "102病房"),
    "room_103": ("1楼", "103病房"),
    "room_104": ("1楼", "104病房"),
    "room_201": ("1楼", "201病房"),
    "room_202": ("1楼", "202病房"),
    "room_203": ("1楼", "203病房"),
    "room_204": ("1楼", "204病房"),
    "room_205": ("1楼", "205病房"),
    "elevator":     ("1楼", "电梯"),
    "payment":      ("1楼", "缴费处"),
    "registration": ("1楼", "挂号处"),
    "nurse":        ("1楼", "护士站"),
    "surgery_a":    ("1楼", "手术室A"),
    "pharmacy":     ("1楼", "药房"),
    "rest_room":    ("1楼", "休息室"),
    "office_a":     ("1楼", "医生办公室A"),
    "office_b":     ("1楼", "医生办公室B"),
}

# ─── 地图 ───────────────────────────────────────────────────────────
MAP_IMAGE_PATH = "/home/hyh/robot/src/地图.jpeg"
# 地图坐标系参数（world → image pixel）
# 图片尺寸 501×1126，世界坐标 x∈[-12,12]，y∈[-32,18]
# resolution = 24/501 ≈ 0.048 m/px（宽），28/1126 ≈ 0.025 m/px（高）
# 取平均约 0.048，origin 取地图左下角 (-12, -32)
MAP_RESOLUTION = 0.048
MAP_ORIGIN_X  = -12.0
MAP_ORIGIN_Y  = -32.0
