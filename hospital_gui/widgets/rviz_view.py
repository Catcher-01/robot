"""
RvizView：纯 Qt 地图渲染控件（无独立 ROS 线程）。

底图：PNG 文件（启动时瞬间加载）。
动态障碍层：/map OccupancyGrid msg（叠加在底图上方，描绘实时障碍）。

交互：
  滚轮       — 缩放（以鼠标位置为中心）
  拖拽       — 平移
  Shift+拖拽 — 旋转
  右键       — 重置视图
"""

import math

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QTimer, QMutex, QMutexLocker, pyqtSlot, pyqtSignal, QPointF
from PyQt5.QtGui import (
    QPainter, QPen, QBrush, QColor, QPixmap, QFont,
    QPolygonF, QImage, QPainterPath, QTransform,
)

_ROBOT_ICON_PATH = "/home/hyh/robot/src/机器人.jpeg"


# ── 地图参数（与 config.py 保持同步）──────────────────────────────────────────────
MAP_RESOLUTION = 0.048         # 米/像素（宽方向平均）
MAP_ORIGIN_X   = -12.0        # world 左边界
MAP_ORIGIN_Y   = -32.0        # world 下边界
MAP_JPEG_PATH  = "/home/hyh/robot/src/地图.jpeg"
MAP_W, MAP_H   = 501, 1126   # 地图像素尺寸


# ─────────────────────────────────────────────────────────────────────────────
# 地图数据（线程安全）
#  - 底图：PNG（静态，尺寸固定 1401×1401，启动时一次性加载）
#  - 障碍层：OccupancyGrid（动态，/map msg → 半透明障碍覆盖）
# ─────────────────────────────────────────────────────────────────────────────

class MapData:
    def __init__(self):
        self._lock       = QMutex()
        self._occ_grid   = None   # list of int  (动态障碍数据)
        self._occ_w      = 0
        self._occ_h      = 0
        self._occ_qpix   = None   # cached QPixmap for overlay

        self._base_pixmap = None  # PNG 底图 QPixmap（只创建一次）
        self._load_png()
        self._robot_icon = QPixmap(_ROBOT_ICON_PATH)

    # ── 底图加载（JPEG）───────────────────────────────────────────────

    def _load_png(self):
        try:
            img = QImage(MAP_JPEG_PATH)
            if img.isNull():
                print(f"[MapData] JPEG 加载失败: {MAP_JPEG_PATH}")
                return
            self._base_pixmap = QPixmap.fromImage(img)
            print(f"[MapData] 地图底图加载成功: {self._base_pixmap.width()}×{self._base_pixmap.height()}")
        except Exception as e:
            print(f"[MapData] 地图加载异常: {e}")

    # ── 动态障碍层（来自 /map msg）────────────────────────────────────────

    def set_occupancy(self, w: int, h: int, data):
        with QMutexLocker(self._lock):
            self._occ_w = w
            self._occ_h = h
            self._occ_grid = data
            self._occ_qpix = None   # invalidate cache

    # ── 查询 ────────────────────────────────────────────────────────────

    def base_pixmap(self):
        return self._base_pixmap

    def occupancy_qpixmap(self):
        with QMutexLocker(self._lock):
            if self._occ_qpix:
                return self._occ_qpix
            if not self._occ_grid or self._occ_w == 0 or self._occ_h == 0:
                return None
            try:
                img = QImage(self._occ_w, self._occ_h, QImage.Format_ARGB32)
                img.fill(Qt.transparent)
                for i, v in enumerate(self._occ_grid):
                    if v < 0:
                        continue
                    g = 255 - int(v * 2.55)
                    img.setPixel(i % self._occ_w, i // self._occ_w,
                                 (g << 24) | (g << 16) | (g << 8) | 80)   # A=80 透明
                self._occ_qpix = QPixmap.fromImage(img)
                print(f"[MapData] 障碍层 QPixmap built: {self._occ_qpix.width()}×{self._occ_qpix.height()}")
                return self._occ_qpix
            except Exception as e:
                print(f"[MapData] 障碍层 QPixmap 构建失败: {e}")
                return None

    def w(self):
        return MAP_W   # PNG 底图尺寸固定

    def h(self):
        return MAP_H

    def occ_w(self):
        with QMutexLocker(self._lock): return self._occ_w

    def occ_h(self):
        with QMutexLocker(self._lock): return self._occ_h


# ─────────────────────────────────────────────────────────────────────────────
# 主控件
# ─────────────────────────────────────────────────────────────────────────────

class RvizView(QWidget):

    map_clicked = pyqtSignal(float, float)   # 世界坐标 (wx, wy)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: #1a1a2e;")
        self.setMinimumSize(500, 500)
        self.setMouseTracking(True)

        self._map_data  = MapData()
        self._robot_x   = 0.0
        self._robot_y   = 0.0
        self._robot_yaw = 0.0
        self._dest_x    = None
        self._dest_y    = None
        self._path      = []
        self._scan      = []

        # 视图状态（可手动修改以调整初始视图位置）
        # _pan_x/_pan_y：恒定偏移量（始终生效，不会被交互覆盖）
        #   粗略换算：想偏移 N 米 ≈ N / MAP_RESOLUTION 个像素
        # _center_pan_x/_center_pan_y：自动对中产生的追加偏移（可被交互覆盖）
        # _zoom：缩放比例，1.0=地图撑满控件，<1=缩小显示全貌，>1=放大
        # _rot_deg：初始旋转角度（度），正值=逆时针
        self._pan_x    = 55.0
        self._pan_y    = 25.0
        self._center_pan_x = 20.0
        self._center_pan_y = 0.0
        self._zoom     = 1.0
        self._rot_deg  = 0.0
        self._view_centered = False   # 是否已自动对准机器人（仅首次有效）
        self._drag_mode        = None
        self._drag_last        = None
        self._drag_rot_origin  = 0.0

        self._scr_timer = QTimer(self)
        self._scr_timer.timeout.connect(self.update)
        self._scr_timer.start(50)

    # ── 外部调用（由 ROSBridge 信号触发）─────────────────────────────

    @pyqtSlot(object)
    def on_map(self, msg):
        """槽：接收 OccupancyGrid msg，叠加为动态障碍层。"""
        w = msg.info.width
        h = msg.info.height
        self._map_data.set_occupancy(w, h, list(msg.data))

    # ── ROS 数据 ─────────────────────────────────────────────────

    def set_robot(self, x: float, y: float, yaw: float):
        self._robot_x   = x
        self._robot_y   = y
        self._robot_yaw = yaw
        # 首次收到机器人坐标时，自动将视图平移至以机器人为中心（追加在校准偏移之上）
        if not self._view_centered and self._map_data.w() > 0:
            self._view_centered = True
            mw, mh = self._map_data.w(), self._map_data.h()
            rx, ry = self._world_to_pixel(x, y)
            self._center_pan_x = mw / 2.0 - rx
            self._center_pan_y = mh / 2.0 - ry
        self.update()

    def set_destination(self, x: float, y: float):
        self._dest_x = x
        self._dest_y = y
        self.update()

    def clear_destination(self):
        self._dest_x = None
        self._dest_y = None
        self.update()

    def set_path(self, path: list):
        self._path = path
        self.update()

    def set_scan(self, scan: list):
        self._scan = scan
        self.update()

    # ── 坐标变换 ─────────────────────────────────────────────────

    def _world_to_pixel(self, wx: float, wy: float):
        h = self._map_data.h()
        if h == 0:
            return 0, 0
        ix = (wx - MAP_ORIGIN_X) / MAP_RESOLUTION
        iy = (wy - MAP_ORIGIN_Y) / MAP_RESOLUTION
        return ix, h - iy

    def _to_screen(self, wx: float, wy: float):
        """世界坐标 → 屏幕像素。"""
        mw = self._map_data.w()
        mh = self._map_data.h()
        if mw == 0 or mh == 0:
            return 0, 0

        # 世界 → 地图像素
        ix = (wx - MAP_ORIGIN_X) / MAP_RESOLUTION
        iy = (wy - MAP_ORIGIN_Y) / MAP_RESOLUTION
        px = ix
        py = mh - iy

        cx, cy = mw / 2.0, mh / 2.0

        # 平移（恒定偏移 + 自动对中偏移）
        total_pan_x = self._pan_x + self._center_pan_x
        total_pan_y = self._pan_y + self._center_pan_y
        sx = px + total_pan_x
        sy = py + total_pan_y

        # 缩放
        sx = (sx - cx) * self._zoom + cx
        sy = (sy - cy) * self._zoom + cy

        # 旋转
        if abs(self._rot_deg) > 0.01:
            rad = math.radians(self._rot_deg)
            cos_r, sin_r = math.cos(rad), math.sin(rad)
            dx, dy = sx - cx, sy - cy
            sx = cx + dx * cos_r + dy * sin_r
            sy = cy - dx * sin_r + dy * cos_r

        return int(sx), int(sy)

    def _from_screen(self, sx: float, sy: float):
        """屏幕像素 → 世界坐标。"""
        mw = self._map_data.w()
        mh = self._map_data.h()
        if mw == 0 or mh == 0:
            return 0.0, 0.0

        cx, cy = mw / 2.0, mh / 2.0

        # 逆旋转
        if abs(self._rot_deg) > 0.01:
            rad = math.radians(-self._rot_deg)
            cos_r, sin_r = math.cos(rad), math.sin(rad)
            dx, dy = sx - cx, sy - cy
            sx = cx + dx * cos_r + dy * sin_r
            sy = cy - dx * sin_r + dy * cos_r

        # 逆缩放
        if self._zoom != 0:
            sx = (sx - cx) / self._zoom + cx
            sy = (sy - cy) / self._zoom + cy

        # 逆平移（恒定偏移 + 自动对中偏移）
        total_pan_x = self._pan_x + self._center_pan_x
        total_pan_y = self._pan_y + self._center_pan_y
        sx -= total_pan_x
        sy -= total_pan_y

        # 地图像素 → 世界
        ix = sx
        iy = mh - sy
        return ix * MAP_RESOLUTION + MAP_ORIGIN_X, iy * MAP_RESOLUTION + MAP_ORIGIN_Y

    # ── 绘制 ─────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)

            base = self._map_data.base_pixmap()
            mw = self._map_data.w()
            mh = self._map_data.h()

            if base and mw > 0 and mh > 0:
                # ── 底图 + 障碍层：统一的世界坐标变换 ──────────────────────────
                painter.save()

                # 世界原点 → 屏幕中心
                painter.translate(self.width() // 2, self.height() // 2)

                # 平移（恒定偏移 + 自动对中偏移）
                total_pan_x = self._pan_x + self._center_pan_x
                total_pan_y = self._pan_y + self._center_pan_y
                painter.translate(total_pan_x, total_pan_y)

                # 缩放（zoom 以鼠标位置为中心，在 mousePress/mouseMove/mouseWheel 处理）
                painter.scale(self._zoom, self._zoom)

                # 旋转
                painter.rotate(self._rot_deg)

                # 地图像素原点（左上角）→ 世界原点 (-MAP_ORIGIN_X, -MAP_ORIGIN_Y)
                # 世界原点(0,0) → 地图像素(mw/2, mh/2)，所以要 translate(-mw/2, -mh/2)
                painter.translate(-mw / 2.0, -mh / 2.0)

                # 底图 PNG
                painter.drawPixmap(0, 0, base)

                # 障碍叠加层（如果有 /map 数据）
                occ = self._map_data.occupancy_qpixmap()
                if occ:
                    painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
                    painter.drawPixmap(0, 0, occ)

                painter.restore()

                # ── 世界坐标 overlay：路径、激光、目标、机器人 ───────────────────
                self._draw_overlay(painter, self.width(), self.height())
            else:
                self._draw_waiting(painter)

            self._draw_indicator(painter)
        finally:
            painter.end()

    def _draw_waiting(self, p: QPainter):
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#1a1a2e"))
        p.setPen(QColor("#8888cc"))
        p.setFont(QFont("monospace", 14))
        p.drawText(w // 2 - 200, h // 2 - 20, "等待地图数据...")
        p.drawText(w // 2 - 240, h // 2 + 20,
                   "请确保导航节点已启动并发布 /map topic")

    def _draw_indicator(self, p: QPainter):
        lines = [
            f"缩放：{int(self._zoom * 100)}%",
            f"旋转：{int(self._rot_deg)}°",
            "滚轮-缩放  拖拽-平移",
            "Shift+拖拽-旋转  右键-重置",
        ]
        p.save()
        p.setFont(QFont("monospace", 11))
        line_h = 18
        pad_x, pad_y = 8, 6
        max_w = max(p.fontMetrics().horizontalAdvance(l) for l in lines)
        bx = self.width()  - max_w - pad_x * 2 - 4
        by = self.height() - len(lines) * line_h - pad_y * 2 - 4
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(0, 0, 0, 160)))
        p.drawRoundedRect(bx, by, max_w + pad_x * 2, len(lines) * line_h + pad_y * 2, 4, 4)
        p.setPen(QPen(QColor("#e0e0e0"), 1))
        for i, line in enumerate(lines):
            p.drawText(bx + pad_x, by + pad_y + (i + 1) * line_h - 2, line)
        p.restore()

    def _draw_overlay(self, p: QPainter, vp_w: int, vp_h: int):
        mw = self._map_data.w()
        mh = self._map_data.h()

        # 世界坐标(m) → 屏幕像素：经 MAP_RESOLUTION 转换后用 paintEvent 同等的变换链
        def world_to_screen(wx, wy):
            # world → map 像素（与 paintEvent drawPixmap 坐标系一致）
            px = (wx - MAP_ORIGIN_X) / MAP_RESOLUTION
            py = (mh - (wy - MAP_ORIGIN_Y) / MAP_RESOLUTION)
            # 地图居中 + pan + scale（同 paintEvent 的 translate→scale→rotate→translate(-mw/2,-mh/2)）
            total_pan_x = self._pan_x + self._center_pan_x
            total_pan_y = self._pan_y + self._center_pan_y
            sx = vp_w / 2.0 + total_pan_x + (px - mw / 2.0) * self._zoom
            sy = vp_h / 2.0 + total_pan_y + (py - mh / 2.0) * self._zoom
            if abs(self._rot_deg) > 0.01:
                rad = math.radians(self._rot_deg)
                dx, dy = sx - vp_w / 2.0, sy - vp_h / 2.0
                sx = vp_w / 2.0 + dx * math.cos(rad) + dy * math.sin(rad)
                sy = vp_h / 2.0 - dx * math.sin(rad) + dy * math.cos(rad)
            return int(sx), int(sy)

        # 路径（使用 cosmetic pen，宽度固定为屏幕像素）
        if len(self._path) >= 2:
            pen = QPen(QColor("#4caf50"), 3)
            pen.setCapStyle(Qt.RoundCap)
            pen.setCosmetic(True)
            p.setPen(pen)
            for i in range(len(self._path) - 1):
                x1, y1 = world_to_screen(self._path[i][0],     self._path[i][1])
                x2, y2 = world_to_screen(self._path[i + 1][0], self._path[i + 1][1])
                p.drawLine(x1, y1, x2, y2)

        # 激光点
        if self._scan:
            p.setPen(Qt.NoPen)
            laser_color = QColor("#64b5f6")
            laser_color.setAlpha(100)
            p.setBrush(QBrush(laser_color))
            for angle, dist in self._scan:
                if dist <= 0 or dist > 30:
                    continue
                wx = self._robot_x + dist * math.cos(angle + self._robot_yaw)
                wy = self._robot_y + dist * math.sin(angle + self._robot_yaw)
                sx, sy = world_to_screen(wx, wy)
                r = int(0.05 / MAP_RESOLUTION * self._zoom)
                p.drawEllipse(sx - r, sy - r, r * 2, r * 2)

        # 目的地
        if self._dest_x is not None:
            dx, dy = world_to_screen(self._dest_x, self._dest_y)
            r_d = int(0.15 / MAP_RESOLUTION * self._zoom)
            p.setPen(QPen(QColor("#ffffff"), 2))
            p.setBrush(QBrush(QColor("#d32f2f")))
            p.drawEllipse(dx - r_d, dy - r_d, r_d * 2, r_d * 2)
            p.drawLine(dx - r_d, dy, dx + r_d, dy)
            p.drawLine(dx, dy - r_d, dx, dy + r_d)

        # 机器人：先变换到世界坐标，再局部旋转yaw
        rx, ry = world_to_screen(self._robot_x, self._robot_y)
        p.save()
        p.translate(rx, ry)
        p.rotate(math.degrees(self._robot_yaw))
        # 世界坐标 0.6m 宽 → 像素尺寸
        world_size = 0.6  # meters
        px_size = int(world_size / MAP_RESOLUTION)
        icon = self._map_data._robot_icon.scaled(
            px_size, px_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        p.drawPixmap(-icon.width() // 2, -icon.height() // 2, icon)
        p.restore()

    # ── 鼠标事件 ─────────────────────────────────────────────────

    def wheelEvent(self, event):
        if self._map_data.w() == 0:
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.15 if delta > 0 else 1.0 / 1.15
        mx, my = event.x(), event.y()
        total_pan_x = self._pan_x + self._center_pan_x
        total_pan_y = self._pan_y + self._center_pan_y
        self._center_pan_x = mx - (mx - total_pan_x) * factor
        self._center_pan_y = my - (my - total_pan_y) * factor
        self._zoom  *= factor
        self._zoom    = max(0.1, min(20.0, self._zoom))
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self._center_pan_x = 0.0
            self._center_pan_y = 0.0
            self._zoom  = 1.0
            self._rot_deg = 0.0
            self.update()
            return
        if event.button() == Qt.LeftButton:
            if self._map_data.w() > 0:
                if event.modifiers() & Qt.ShiftModifier:
                    self._drag_mode       = 'rotate'
                    self._drag_last       = event.pos()
                    self._drag_rot_origin = self._rot_deg
                else:
                    self._drag_mode = 'pan'
                    self._drag_last = event.pos()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_mode is None or self._drag_last is None:
            return
        dx = event.x() - self._drag_last.x()
        dy = event.y() - self._drag_last.y()
        if self._drag_mode == 'pan':
            self._center_pan_x += dx
            self._center_pan_y += dy
            self._drag_last = event.pos()
            self.update()
        elif self._drag_mode == 'rotate':
            cx, cy = self.width() / 2.0, self.height() / 2.0
            def angle(p):
                return math.degrees(math.atan2(p.y() - cy, p.x() - cx))
            da = angle(event.pos()) - angle(self._drag_last)
            self._rot_deg  = self._drag_rot_origin - da
            self._drag_last = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        self._drag_mode = None
        self._drag_last = None
        super().mouseReleaseEvent(event)
