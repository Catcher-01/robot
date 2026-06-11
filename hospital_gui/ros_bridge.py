"""
ROS2 桥接：在独立线程中运行 rclpy，通过 Nav2 action client 控制导航，
订阅 /amcl_pose、/plan 获取实时位置和路径，通过 Qt 信号推送 UI 更新。
"""

import math
import threading
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseWithCovarianceStamped, PoseStamped, Quaternion
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Path, OccupancyGrid
from nav2_msgs.action import NavigateToPose
from std_msgs.msg import String
from PyQt5.QtCore import QObject, pyqtSignal, Qt


GoalStatus = type('GoalStatus', (), {
    'SUCCEEDED': 4,
    'CANCELED': 5,
    'ABORTED': 6,
})()


class SignalEmitter(QObject):
    """纯 QObject，持所有 Qt 信号。避免与 rclpy.Node 的多继承冲突。"""
    sig_pose      = pyqtSignal(float, float, float)
    sig_path      = pyqtSignal(object)
    sig_scan      = pyqtSignal(object)
    sig_nav_fb    = pyqtSignal(float, str)
    sig_nav_done  = pyqtSignal(int)
    sig_nav_start = pyqtSignal(bool)
    sig_voice     = pyqtSignal(str)
    sig_map       = pyqtSignal(object)


class ROSNode(Node):
    """运行在 ROS2 线程中的节点，仅通过 Qt 信号与主线程通信。"""

    def __init__(self, emitter: SignalEmitter):
        super().__init__('hospital_gui_bridge')
        self._emitter = emitter

        self.create_subscription(
            PoseWithCovarianceStamped, '/amcl_pose',
            self._pose_cb, 10,
        )
        self.create_subscription(
            Path, '/plan',
            self._plan_cb, 10,
        )
        self.create_subscription(
            LaserScan, '/scan',
            self._scan_cb, 10,
        )
        self.create_subscription(
            String, '/voice_to_nav',
            self._voice_cb, 10,
        )
        self.create_subscription(
            OccupancyGrid, '/map',
            self._map_cb, 1,
        )

        self._action_client        = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self._action_future        = None
        self._action_result_future = None
        self._goal_handle          = None

        self.get_logger().info('Hospital GUI bridge 启动，等待 Nav2 action server…')

    # ── 订阅回调 ─────────────────────────────────────────────────────

    def _pose_cb(self, msg: PoseWithCovarianceStamped):
        ori = msg.pose.pose.orientation
        yaw = self._quaternion_to_yaw(ori)
        self._emitter.sig_pose.emit(msg.pose.pose.position.x, msg.pose.pose.position.y, yaw)

    def _plan_cb(self, msg: Path):
        self._emitter.sig_path.emit([(p.pose.position.x, p.pose.position.y) for p in msg.poses])

    def _scan_cb(self, msg: LaserScan):
        scan = []
        angle = msg.angle_min
        for dist in msg.ranges:
            if msg.range_min < dist < msg.range_max:
                scan.append((angle, float(dist)))
            angle += msg.angle_increment
        self._emitter.sig_scan.emit(scan)

    def _voice_cb(self, msg: String):
        self._emitter.sig_voice.emit(msg.data)

    def _map_cb(self, msg: OccupancyGrid):
        self._emitter.sig_map.emit(msg)

    # ── Nav2 Action ─────────────────────────────────────────────────

    def send_navigate_goal(self, x: float, y: float, yaw: float):
        if not self._action_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error('Nav2 action server 不可用')
            self._emitter.sig_nav_start.emit(False)
            return

        goal = NavigateToPose.Goal()
        goal.pose.header.stamp    = self.get_clock().now().to_msg()
        goal.pose.header.frame_id = 'map'
        goal.pose.pose.position.x = float(x)
        goal.pose.pose.position.y = float(y)
        goal.pose.pose.position.z = 0.0
        q = self._yaw_to_quaternion(float(yaw))
        goal.pose.pose.orientation.x = q.x
        goal.pose.pose.orientation.y = q.y
        goal.pose.pose.orientation.z = q.z
        goal.pose.pose.orientation.w = q.w

        self._action_future = self._action_client.send_goal_async(goal)
        self._action_future.add_done_callback(self._goal_response_cb)

    def _goal_response_cb(self, future):
        goal_handle = future.result()
        self._emitter.sig_nav_start.emit(goal_handle.accepted)
        if not goal_handle.accepted:
            self.get_logger().warn('Nav2 目标被拒绝')
            return
        self.get_logger().info('Nav2 目标已接受')
        self._goal_handle           = goal_handle
        self._action_result_future  = goal_handle.get_result_async()
        self._action_result_future.add_done_callback(self._result_cb)

    def _result_cb(self, future):
        status = future.result().status
        self.get_logger().info(f'Nav2 action 完成，状态: {status}')
        self._emitter.sig_nav_done.emit(status)

    def _action_feedback_cb(self, feedback_msg):
        dist = float(feedback_msg.feedback.distance_remaining)
        if dist > 5.0:
            instr = "前方直行"
        elif dist > 2.0:
            instr = "前方转弯，注意方向"
        else:
            instr = "即将到达，请准备下车"
        self._emitter.sig_nav_fb.emit(dist, instr)

    def cancel_navigate_goal(self):
        if self._goal_handle is not None:
            try:
                self._goal_handle.cancel_goal_async()
            except Exception as e:
                self.get_logger().warn(f'取消导航失败: {e}')
        self._goal_handle           = None
        self._action_future         = None
        self._action_result_future  = None

    # ── 工具 ───────────────────────────────────────────────────────

    @staticmethod
    def _quaternion_to_yaw(q: Quaternion) -> float:
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        return math.atan2(siny_cosp, cosy_cosp)

    @staticmethod
    def _yaw_to_quaternion(yaw: float) -> Quaternion:
        q = Quaternion()
        q.x, q.y = 0.0, 0.0
        q.z = math.sin(yaw / 2.0)
        q.w = math.cos(yaw / 2.0)
        return q


class ROSBridge(QObject):
    position_updated   = pyqtSignal(float, float, float)
    path_updated       = pyqtSignal(list)
    scan_updated       = pyqtSignal(list)
    nav_status_changed = pyqtSignal(str)
    nav_instruction    = pyqtSignal(str, float, float)
    arrived_at_dest    = pyqtSignal(str)
    voice_result_ready = pyqtSignal(list)
    map_updated        = pyqtSignal(object)

    _instance = None

    def __init__(self):
        super().__init__()
        self._running  = False
        self._node: ROSNode = None
        self._thread: threading.Thread = None
        self._emitter = SignalEmitter()

        self._cur_x = self._cur_y = self._cur_yaw = 0.0
        self._target_x = self._target_y = 0.0
        self._target_id = ""

        ROSBridge._instance = self

    @classmethod
    def instance(cls):
        return cls._instance

    # ── 启动 / 停止 ───────────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._spin_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)

    def _spin_loop(self):
        rclpy.init()
        self._node = ROSNode(self._emitter)
        conn = Qt.QueuedConnection
        self._emitter.sig_pose.connect(self._on_pose,      type=conn)
        self._emitter.sig_path.connect(self._on_path,      type=conn)
        self._emitter.sig_scan.connect(self._on_scan,      type=conn)
        self._emitter.sig_nav_fb.connect(self._on_nav_fb,  type=conn)
        self._emitter.sig_nav_done.connect(self._on_nav_done, type=conn)
        self._emitter.sig_nav_start.connect(self._on_nav_start, type=conn)
        self._emitter.sig_voice.connect(self._on_voice_result, type=conn)
        self._emitter.sig_map.connect(self._on_map,        type=conn)
        try:
            while self._running and rclpy.ok():
                rclpy.spin_once(self._node, timeout_sec=0.05)
        finally:
            self._node.destroy_node()
            rclpy.shutdown()

    # ── 导航控制 ─────────────────────────────────────────────────────

    def navigate_to(self, dest_id: str, x: float, y: float, yaw: float):
        self._target_id = dest_id
        self._target_x  = x
        self._target_y  = y
        self.nav_status_changed.emit("navigating")
        if self._node:
            self._node.send_navigate_goal(x, y, yaw)

    def cancel_navigation(self):
        if self._node:
            self._node.cancel_navigate_goal()
        self.nav_status_changed.emit("cancelled")

    # ── 内部回调 ─────────────────────────────────────────────────────

    def _on_pose(self, x: float, y: float, yaw: float):
        self._cur_x   = x
        self._cur_y   = y
        self._cur_yaw = yaw
        self.position_updated.emit(x, y, yaw)

        if self._target_id:
            dist = math.sqrt((x - self._target_x)**2 + (y - self._target_y)**2)
            if dist < 0.8:
                self.nav_status_changed.emit("arrived")
                self.arrived_at_dest.emit(self._target_id)

    def _on_path(self, path: list):
        self.path_updated.emit(path)

    def _on_scan(self, scan: list):
        self.scan_updated.emit(scan)

    def _on_nav_start(self, accepted: bool):
        if not accepted:
            self.nav_status_changed.emit("cancelled")

    def _on_nav_fb(self, dist: float, instr: str):
        self.nav_instruction.emit(instr, dist, dist / 0.3)

    def _on_nav_done(self, status: int):
        if status == GoalStatus.SUCCEEDED:
            pass
        elif status == GoalStatus.CANCELED:
            self.nav_status_changed.emit("cancelled")
        else:
            self.nav_status_changed.emit("failed")
        self._target_id = ""
        self._target_x  = 0.0
        self._target_y  = 0.0

    def _on_voice_result(self, msg: str):
        import json
        try:
            data = json.loads(msg)
            dest = data.get("destination", "")
            if dest:
                self.voice_result_ready.emit([dest])
        except Exception:
            pass

    def _on_map(self, msg: OccupancyGrid):
        self.map_updated.emit(msg)
