"""
导航控制器：接收 /voice_to_nav 话题，将房间名转换为 Nav2 导航目标。

订阅话题：
    /voice_to_nav (std_msgs/String) — JSON: {"action":"navigation","destination":"room_id"}

发送目标：
    /navigate_to_pose (NavigateToPose action) — map 坐标系下的 (x, y, yaw)

房间坐标来源：坐标.md（map 坐标系）
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
import json


# map 坐标系下的房间目标点（与 voice_node.py SYSTEM_PROMPT 保持一致）
# yaw: 左侧房间朝右(0), 右侧房间朝左(π), 前方房间朝下(0)
# yaw = 0  → 朝 +x 方向（地图右侧/东）
# yaw = π  → 朝 -x 方向（地图左侧/西）
ROOM_COORDS = {
    # 特殊地点
    "elevator":    ( 0.0,  15.0,  0.0),   # 电梯
    "registration": ( 3.5,   5.5,  0.0),   # 挂号处
    "payment":      (-3.5,   5.5,  0.0),   # 缴费处
    "nurse":        ( 0.0,  10.0,  0.0),   # 护士站
    "surgery_a":    (-3.0, -15.0,  0.0),   # 手术室A
    "pharmacy":     ( 3.0, -15.0,  0.0),   # 药房
    "rest_room":    (-10.0,-27.0,  0.0),   # 休息室
    "office_a":     (-1.0,  -3.0,  0.0),   # 医生办公室A
    "office_b":     ( 1.0,  -3.0,  0.0),   # 医生办公室B
    # 左侧病房 x ≈ -8.5（朝右）
    "room_101": (-8.5,  11.0,  0.0),
    "room_102": (-8.5,   4.75, 0.0),
    "room_103": (-8.5,  -4.75, 0.0),
    "room_104": (-8.5, -18.0,  0.0),
    # 右侧病房 x ≈ 8.5 / 6（朝左）
    "room_201": ( 8.5,  11.0,  3.14159),
    "room_202": ( 8.5,   4.75, 3.14159),
    "room_203": ( 8.5,  -4.75, 3.14159),
    "room_204": ( 8.5, -18.0,  3.14159),
    "room_205": ( 6.0, -28.0,  3.14159),
    # 大门 / 走廊（不在 SYSTEM_PROMPT，但原 nav_controller 有定义）
    "door":      ( 0.0,  22.0,  0.0),
    "corridor":  ( 0.0,   0.0,  0.0),
}

ROOM_NAME = {
    "room_101": "101病房", "room_102": "102病房",
    "room_103": "103病房", "room_104": "104病房",
    "room_201": "201病房", "room_202": "202病房",
    "room_203": "203病房", "room_204": "204病房",
    "room_205": "205病房",
    "elevator": "电梯",    "registration": "挂号处",
    "payment": "缴费处",   "nurse": "护士站",
    "surgery_a": "手术室A", "pharmacy": "药房",
    "rest_room": "休息室",  "office_a": "医生办公室A",
    "office_b": "医生办公室B",
    "door": "医院大门",     "corridor": "走廊中央",
}


class NavController(Node):
    def __init__(self):
        super().__init__('nav_controller')

        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.sub = self.create_subscription(
            String,
            '/voice_to_nav',
            self._on_voice_command,
            10
        )

        # 等待 Nav2 action server 就绪
        self.get_logger().info("等待 Nav2 navigate_to_pose 服务...")
        self.nav_client.wait_for_server()
        self.get_logger().info("Nav2 导航服务已就绪！")

    def _on_voice_command(self, msg: String):
        try:
            data = json.loads(msg.data)
        except Exception as e:
            self.get_logger().error(f"JSON 解析失败: {e}")
            return

        action = data.get("action")
        dest   = data.get("destination")

        if action != "navigation" or not dest:
            self.get_logger().warn(f"无效指令: {data}")
            return

        if dest not in ROOM_COORDS:
            self.get_logger().warn(f"未知目的地: {dest}")
            return

        x, y, yaw = ROOM_COORDS[dest]
        self.get_logger().info(f"收到导航指令 → {dest} ({ROOM_NAME.get(dest, dest)})")
        self._send_goal(x, y, yaw, dest)

    def _send_goal(self, x: float, y: float, yaw: float, dest_id: str):
        goal = NavigateToPose.Goal()
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.header.frame_id = "map"

        goal.pose.pose.position.x = x
        goal.pose.pose.position.y = y
        goal.pose.pose.position.z = 0.0

        # yaw → quaternion
        import math
        goal.pose.pose.orientation.x = 0.0
        goal.pose.pose.orientation.y = 0.0
        goal.pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal.pose.pose.orientation.w = math.cos(yaw / 2.0)

        self.get_logger().info(
            f"发送导航目标: ({x:.1f}, {y:.1f}), yaw={math.degrees(yaw):.0f}°"
        )

        self.nav_client.send_goal_async(
            goal,
            feedback_callback=lambda fb: self._on_feedback(fb, dest_id)
        ).add_done_callback(
            lambda future: self._on_goal_done(future, dest_id)
        )

    def _on_feedback(self, fb, dest_id):
        self.get_logger().debug(f"导航反馈: {fb.feedback}")

    def _on_goal_done(self, future, dest_id):
        result = future.result()
        status = result.status if result else -1
        if status == 4:
            self.get_logger().info(f"✅ 已到达 {ROOM_NAME.get(dest_id, dest_id)}！")
        else:
            self.get_logger().warn(
                f"导航未完成，状态码={status}（4=成功，1=已接收，2=正在执行）"
            )


def main(args=None):
    rclpy.init(args=args)
    node = NavController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
