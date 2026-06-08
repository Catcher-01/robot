#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
import cv2
import mediapipe as mp
import time
import math
import subprocess
from std_msgs.msg import String
import json

# ── 鼠标控制 ──────────────────────────────────────────────────────────────────
try:
    from pynput.mouse import Button, Controller as MouseController
    _mouse = MouseController()
    def _move(x, y):    _mouse.position = (int(x), int(y))
    def _click_left():  _mouse.click(Button.left)
    def _click_right(): _mouse.click(Button.right)
    def _scroll(dy):    _mouse.scroll(0, dy)
    MOUSE_BACKEND = "pynput"
except Exception:
    def _move(x, y):    subprocess.Popen(["xdotool", "mousemove", str(int(x)), str(int(y))])
    def _click_left():  subprocess.Popen(["xdotool", "click", "1"])
    def _click_right(): subprocess.Popen(["xdotool", "click", "3"])
    def _scroll(dy):    subprocess.Popen(["xdotool", "click", "4" if dy > 0 else "5"])
    MOUSE_BACKEND = "xdotool"

# ── 屏幕分辨率 ────────────────────────────────────────────────────────────────
def _get_screen_size():
    try:
        out = subprocess.check_output(["xdpyinfo"], stderr=subprocess.DEVNULL).decode()
        for line in out.splitlines():
            if "dimensions:" in line:
                w, h = line.strip().split()[1].split("x")
                return int(w), int(h)
    except Exception:
        pass
    return 1920, 1080

def _dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)

def _finger_up(lm, tip, pip_):
    return lm[tip].y < lm[pip_].y

class ExpSmooth:
    def __init__(self, alpha=0.18):
        self.alpha = alpha
        self.val   = None
    def update(self, v):
        self.val = v if self.val is None else self.alpha * v + (1 - self.alpha) * self.val
        return self.val

class GestureMouseNode(Node):
    PINCH_THRESH   = 0.20
    RCLICK_THRESH  = 0.20
    SCROLL_STEP    = 0.04

    def __init__(self):
        super().__init__('gesture_mouse_node')
        # 创建一个手势命令发布者
        self.gesture_pub = self.create_publisher(String, '/gesture_command', 10)
        self.screen_w, self.screen_h = _get_screen_size()
        self.get_logger().info(f'屏幕分辨率: {self.screen_w}×{self.screen_h}，后端: {MOUSE_BACKEND}')

        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False, max_num_hands=1,
            min_detection_confidence=0.7, min_tracking_confidence=0.6)

        self.cap = cv2.VideoCapture('/dev/video0', cv2.CAP_V4L2)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        if not self.cap.isOpened():
            raise RuntimeError('摄像头打开失败')

        self.ROI_X1, self.ROI_X2 = 0.10, 0.90
        self.ROI_Y1, self.ROI_Y2 = 0.10, 0.90
        self.smooth_x    = ExpSmooth()
        self.smooth_y    = ExpSmooth()
        self.is_pinching_l = False
        self.is_pinching_r = False
        self.scroll_ref_y  = None
        self.scroll_accum  = 0.0

        self.timer = self.create_timer(0.05, self._cb)
        self.get_logger().info('手势鼠标节点启动！')

    def _cb(self):
        ok, frame = self.cap.read()
        if not ok:
            return

        frame = cv2.flip(frame, 1)
        res   = self.hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        # ── 没检测到手 ────────────────────────────────────────────────────
        if not res.multi_hand_landmarks:
            self.scroll_ref_y  = None
            self.scroll_accum  = 0.0
            self.is_pinching_l = False
            self.is_pinching_r = False
            self._show(frame, None, 0, 0, 0, "no hand")
            return

        lm = res.multi_hand_landmarks[0].landmark

        index_up  = _finger_up(lm, 8,  6)
        middle_up = _finger_up(lm, 12, 10)
        ring_up   = _finger_up(lm, 16, 14)
        pinky_up  = _finger_up(lm, 20, 18)
        thumb_up  = lm[4].x < lm[3].x

        fingers_up   = sum([thumb_up, index_up, middle_up, ring_up, pinky_up])
        non_thumb_up = sum([index_up, middle_up, ring_up, pinky_up])

        palm_size   = _dist(lm[0], lm[9]) + 1e-6
        pinch_dist  = _dist(lm[4], lm[8])  / palm_size
        rclick_dist = _dist(lm[8], lm[12]) / palm_size

        # ── 决定当前手势状态（用于调试显示）─────────────────────────────
        state = "?"

        # ── 1. 手掌张开 → 冻结 ──────────────────────────────────
        if fingers_up >= 4:
            state = "freeze"
            self.scroll_ref_y = None
            self.scroll_accum = 0.0
            self._show(frame, lm, pinch_dist, rclick_dist, fingers_up, state)
            return

        # ── 2. 双指状态（食指和中指都伸出） ──────────────────────────────
        if index_up and middle_up and not ring_up and not pinky_up:
            # 检查是否触发右键（中指和拇指捏合，或者食指中指靠得很近）
            now_r = rclick_dist < self.RCLICK_THRESH
            if now_r:
                if not self.is_pinching_r:
                    _click_right()
                    ev_msg = {"event": "click_right", "x": float(lm[8].x), "y": float(lm[8].y)}
                    self.gesture_pub.publish(String(data=json.dumps(ev_msg, ensure_ascii=False)))
                    self.get_logger().info('右键单击')
                self.is_pinching_r = True
                state = "R-CLICK"
                # 右键时清除滚动状态
                self.scroll_ref_y = None
                self.scroll_accum = 0.0
            else:
                # 双指没有捏合，那就是【滚动模式】
                self.is_pinching_r = False
                
                # 使用中指根部 Y 坐标作为滚动参照
                wrist_y = lm[9].y  
                if self.scroll_ref_y is None:
                    self.scroll_ref_y = wrist_y
                
                self.scroll_accum += (self.scroll_ref_y - wrist_y)
                self.scroll_ref_y = wrist_y
                
                if abs(self.scroll_accum) >= self.SCROLL_STEP:
                    ticks = int(self.scroll_accum / self.SCROLL_STEP)
                    _scroll(ticks)
                    direction = "up" if ticks > 0 else "down"
                    ev_msg = {"event": "scroll", "direction": direction, "ticks": abs(ticks)}
                    self.gesture_pub.publish(String(data=json.dumps(ev_msg, ensure_ascii=False)))
                    self.scroll_accum -= ticks * self.SCROLL_STEP
                    
                state = f"scroll({'up' if self.scroll_accum >= 0 else 'dn'})"
            
            self._show(frame, lm, pinch_dist, rclick_dist, fingers_up, state)
            return

        # 只要离开双指状态，就清空右键和滚动的状态
        self.is_pinching_r = False
        self.scroll_ref_y = None
        self.scroll_accum = 0.0

        # ── 3. 单指状态（控制鼠标移动与左键） ────────────────────────────
        if index_up and not middle_up:
            now_l = pinch_dist < self.PINCH_THRESH
            if now_l:
                if not self.is_pinching_l:
                    _click_left()
                    ev_msg = {"event": "click_left", "x": float(lm[8].x), "y": float(lm[8].y)}
                    self.gesture_pub.publish(String(data=json.dumps(ev_msg, ensure_ascii=False)))
                    self.get_logger().info('左键单击')
                self.is_pinching_l = True
                state = "L-CLICK"
                self._show(frame, lm, pinch_dist, rclick_dist, fingers_up, state)
            else:
                self.is_pinching_l = False
                state = "move"
                self._do_move(lm)  # 只有在非捏合状态下才移动鼠标，避免点击时指针乱飘
                cx = max(0.0, min(1.0, (lm[8].x - self.ROI_X1) / (self.ROI_X2 - self.ROI_X1)))
                cy = max(0.0, min(1.0, (lm[8].y - self.ROI_Y1) / (self.ROI_Y2 - self.ROI_Y1)))
                ev_msg = {"event": "move", "x": float(cx), "y": float(cy)}
                self.gesture_pub.publish(String(data=json.dumps(ev_msg, ensure_ascii=False)))
            self._show(frame, lm, pinch_dist, rclick_dist, fingers_up, state)
            return

        # 离开单指状态
        self.is_pinching_l = False
        self._show(frame, lm, pinch_dist, rclick_dist, fingers_up, "other")

    def _do_move(self, lm):
        cx = max(0.0, min(1.0, (lm[8].x - self.ROI_X1) / (self.ROI_X2 - self.ROI_X1)))
        cy = max(0.0, min(1.0, (lm[8].y - self.ROI_Y1) / (self.ROI_Y2 - self.ROI_Y1)))
        sx = self.smooth_x.update(cx * self.screen_w)
        sy = self.smooth_y.update(cy * self.screen_h)
        _move(sx, sy)

    def _show(self, frame, lm, pinch_dist, rclick_dist, fingers_up, state):
        h, w = frame.shape[:2]

        if lm is not None:
            # 连线
            for a, b in [
                (0,1),(1,2),(2,3),(3,4),
                (0,5),(5,6),(6,7),(7,8),
                (0,9),(9,10),(10,11),(11,12),
                (0,13),(13,14),(14,15),(15,16),
                (0,17),(17,18),(18,19),(19,20),
                (5,9),(9,13),(13,17),
            ]:
                cv2.line(frame,
                    (int(lm[a].x*w), int(lm[a].y*h)),
                    (int(lm[b].x*w), int(lm[b].y*h)),
                    (0,255,0), 2)
            # 关键点
            for i, p in enumerate(lm):
                color = (0,0,255) if i in [4,8,12] else (255,255,0)
                cv2.circle(frame, (int(p.x*w), int(p.y*h)), 5, color, -1)

        # 文字信息
        l_color = (0,255,255) if pinch_dist  < self.PINCH_THRESH  else (200,200,200)
        r_color = (0,255,255) if rclick_dist < self.RCLICK_THRESH else (200,200,200)
        s_color = (0,255,0)   if "CLICK" in state else (255,200,0)

        cv2.putText(frame, f'pinch L: {pinch_dist:.3f}  thresh:{self.PINCH_THRESH}',
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, l_color, 2)
        cv2.putText(frame, f'pinch R: {rclick_dist:.3f}  thresh:{self.RCLICK_THRESH}',
                    (10, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.65, r_color, 2)
        cv2.putText(frame, f'fingers: {fingers_up}',
                    (10, 86), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255,200,0), 2)
        cv2.putText(frame, f'state:   {state}',
                    (10,114), cv2.FONT_HERSHEY_SIMPLEX, 0.75, s_color, 2)

        cv2.imshow('Gesture Debug', frame)
        cv2.waitKey(1)

    def __del__(self):
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
        if hasattr(self, 'hands'):
            self.hands.close()

def main(args=None):
    rclpy.init(args=args)
    node = GestureMouseNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()