"""
MapCanvas：渲染地图、路径、机器人、目的地。
显示：彩色底图（来自 src/地图.jpeg）、绿色路径、红色目标、蓝色机器人箭头。
"""

import math
import numpy as np
from PIL import Image

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import QTimer, Qt, QRectF, QPointF, QPoint
from PyQt5.QtGui import QPainter, QPixmap, QPen, QBrush, QColor, QPolygonF, QImage, QTransform

from hospital_gui.config import SCREEN_W, SCREEN_H, MAP_IMAGE_PATH, MAP_RESOLUTION, MAP_ORIGIN_X, MAP_ORIGIN_Y

_ROBOT_ICON_PATH = "/home/hyh/robot/src/机器人.jpeg"


class MapCanvas(QWidget):
    """
    地图画布（导航执行页专用）。

    坐标系：
      world 坐标系：Y轴朝上，原点为地图 yaml origin。
      widget 坐标系：letterbox 居中（短边对齐，两侧留黑边）。
      世界坐标 → 画布像素 统一由 _world_to_widget 完成。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: #cccccc;")

        # 地图参数（来自 config）
        self._res    = MAP_RESOLUTION
        self._orig_x = MAP_ORIGIN_X
        self._orig_y = MAP_ORIGIN_Y

        # 地图图片像素尺寸（需保持引用以防 QImage 失效）
        self._map_pixmap: QPixmap = None
        self._map_w = 0
        self._map_h = 0

        self._load_map()
        self._robot_icon = QPixmap(_ROBOT_ICON_PATH)

        # 导航数据
        self._robot_x  = 0.0
        self._robot_y  = 0.0
        self._robot_yaw = 0.0
        self._dest_x    = None
        self._dest_y    = None
        self._path: list = []

        # 10fps 刷新
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(100)

    # ── 加载地图 ─────────────────────────────────────────────────

    def _load_map(self):
        # 直接加载 JPEG 彩色底图
        try:
            img = Image.open(MAP_IMAGE_PATH).convert("RGB")
            self._map_w = img.width
            self._map_h = img.height
            # 转 numpy RGB 数组 → QImage
            rgb = np.array(img, dtype=np.uint8)
            h, w = rgb.shape[:2]
            qimage = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
            if qimage.isNull():
                raise RuntimeError("QImage 构建失败")
            qimage = qimage.copy()   # 深拷贝，确保 numpy 数组释放后 QImage 仍然有效
            self._map_pixmap = QPixmap.fromImage(qimage)
            print(f"[MapCanvas] 加载地图成功: {w}×{h}")
        except Exception as e:
            print(f"[MapCanvas] 加载地图失败: {e}")
            self._map_pixmap = QPixmap()

    # ── 公开接口 ─────────────────────────────────────────────────

    def set_robot(self, x: float, y: float, yaw: float):
        self._robot_x   = x
        self._robot_y   = y
        self._robot_yaw = yaw

    def set_destination(self, x: float, y: float):
        self._dest_x = x
        self._dest_y = y

    def clear_destination(self):
        self._dest_x = None
        self._dest_y = None

    def set_path(self, path: list):
        self._path = path

    def set_scan(self, scan: list):
        pass

    # ── 世界坐标 → 画布像素 ──────────────────────────────────────
    #
    # 地图坐标系（world，Y轴朝上）：
    #   图片像素 X = (world_x - orig_x) / res
    #   图片像素 Y = (world_y - orig_y) / res  （JPEG 是俯视图，Y轴同向）
    #
    # 画布坐标系（letterbox 居中，Y轴朝下）：
    #   以短边为准缩放地图，两侧留黑边
    #   canvas_x = offset_x + img_px_x * scale
    #   canvas_y = offset_y + img_px_y * scale

    def _world_to_widget(self, wx: float, wy: float) -> QPointF:
        w = self.width()
        h = self.height()

        # 地图像素坐标
        img_px_x = (wx - self._orig_x) / self._res
        img_px_y = (wy - self._orig_y) / self._res

        # letterbox scale（与 paintEvent 保持一致）
        scale = min(w / self._map_w, h / self._map_h)
        offset_x = (w - self._map_w * scale) / 2.0
        offset_y = (h - self._map_h * scale) / 2.0

        cx = offset_x + img_px_x * scale
        cy = offset_y + img_px_y * scale
        return QPointF(cx, cy)

    # ── 绘制 ─────────────────────────────────────────────────────

    def paintEvent(self, event):
        w = self.width()
        h = self.height()
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)

            # 地图底图：letterbox 居中，保持宽高比
            if self._map_pixmap and not self._map_pixmap.isNull():
                map_w = self._map_pixmap.width()
                map_h = self._map_pixmap.height()
                # 以短边为准计算缩放，保持宽高比
                scale = min(w / map_w, h / map_h)
                draw_w = map_w * scale
                draw_h = map_h * scale
                dest_rect = QRectF(
                    (w - draw_w) / 2, (h - draw_h) / 2,
                    draw_w, draw_h
                )
                src_rect = QRectF(0, 0, map_w, map_h)
                painter.drawPixmap(dest_rect, self._map_pixmap, src_rect)

            # 绿色路径线
            if self._path and len(self._path) >= 2:
                pen = QPen(QColor("#2e7d32"), 4)
                pen.setCapStyle(Qt.RoundCap)
                painter.setPen(pen)
                pts = [(int(p.x()), int(p.y()))
                       for p in (self._world_to_widget(px, py) for px, py in self._path)]
                for i in range(len(pts) - 1):
                    x1, y1 = pts[i]
                    x2, y2 = pts[i + 1]
                    painter.drawLine(x1, y1, x2, y2)

            # 红色目的地圆点
            if self._dest_x is not None and self._dest_y is not None:
                dp = self._world_to_widget(self._dest_x, self._dest_y)
                dpx, dpy = int(dp.x()), int(dp.y())
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(QColor("#d32f2f")))
                painter.drawEllipse(QPoint(dpx, dpy), 14, 14)
                # 外圈白边
                painter.setPen(QPen(QColor("#ffffff"), 2))
                painter.setBrush(QBrush())
                painter.drawEllipse(QPoint(dpx, dpy), 14, 14)

            # 机器人图标
            if self._robot_x != 0.0 or self._robot_y != 0.0:
                rp = self._world_to_widget(self._robot_x, self._robot_y)
                self._draw_robot_icon(painter, rp)
        finally:
            painter.end()

    def _draw_robot_icon(self, painter: QPainter, center: QPointF):
        """用机器人图片绘制，尺寸根据地图分辨率自适应（约0.6米）。"""
        painter.save()
        painter.translate(center)
        # 地图分辨率 0.05 m/px，机器人约 0.6m → 12px
        size = int(0.6 / self._res)
        icon = self._robot_icon.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        painter.drawPixmap(-icon.width() // 2, -icon.height() // 2, icon)
        painter.restore()
