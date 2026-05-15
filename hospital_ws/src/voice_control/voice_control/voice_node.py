import rclpy
from openai import OpenAI
from rclpy.node import Node
from std_msgs.msg import String
import pyaudio
import wave
import asyncio
import os
import json
from datetime import datetime
from faster_whisper import WhisperModel

DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY")

SYSTEM_PROMPT = """
规则：
你是一个医院导航助手，你需要从用户话语中提取导航目的地，且你只能从以下已知房间里选择。

已知房间：
room_101=101病房, room_102=102病房, info_desk=咨询台,
lab_01=化验室, emergency=急诊, pharmacy=药房

需要考虑同义词/相似范围;
当问询人在寻求帮助或问问题时，如果你无法确定具体目的地时，一律建议去咨询台(info_desk);
只有当用户在说和医院导航完全无关的废话（如‘今天天气不错’'）时，才返回 unknown。”
只输出JSON，不要进行任何解释。

如果提取成功，
成功：{"action":"navigation","destination":"room_id"}
如果提取失败，
失败：{"action":"unknown","destination":null}
"""

ROOM_MAP = {
    "101": "room_101",
    "102": "room_102",
    "咨询台": "info_desk",
    "化验室": "lab_01",
    "急诊": "emergency",
    "药房": "pharmacy"
}

ROOM_NAME = {
    "room_101": "101病房",
    "room_102": "102病房",
    "info_desk": "咨询台",
    "lab_01": "化验室",
    "emergency": "急诊",
    "pharmacy": "药房"
}

class VoiceNode(Node):
    def __init__(self):
        super().__init__('voice_node')
        if not DEEPSEEK_KEY:
            self.get_logger().error("未检测到API_KEY，请先配置")
        self.publisher = self.create_publisher(String, '/voice_to_nav', 10)
        self.model = WhisperModel("small", device="cuda", compute_type="float16")
        self.client = OpenAI(api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com")
        self.get_logger().info("节点启动完成！")
        self.run()

    def transcribe(self, filename="test.wav"):
        self.get_logger().info("识别中...")
        segments, _ = self.model.transcribe(filename, language="zh", beam_size=10, initial_prompt="简体中文")
        text = "".join([s.text for s in segments])
        self.get_logger().info(f"识别结果：{text}")
        return text

    def parse_with_llm(self, text):
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text}
                ],
                max_tokens=100,
                timeout=5
            )
            raw = response.choices[0].message.content.strip()
            result = json.loads(raw)
            if result.get("destination"):
                return result
        except Exception as e:
            self.get_logger().warn(f"LLM失败：{e}")
        return None

    def parse_with_regex(self, text):
        destination = None
        last_pos = -1
        for key, val in ROOM_MAP.items():
            pos = text.rfind(key)
            if pos > last_pos:
                last_pos = pos
                destination = val
        if destination:
            return {"action": "navigation", "destination": destination}
        return None

    def parse_intent(self, text):
        result = self.parse_with_llm(text)
        if result:
            self.get_logger().info("解析成功")
        else:
            result = self.parse_with_regex(text)
            if result:
                self.get_logger().warn("解析失败")

        if result:
            result["raw_text"] = text
            result["timestamp"] = int(datetime.now().strftime("%y%m%d%H%M%S"))
            return result

        self.get_logger().warn("未识别到目的地")
        return None

    def speak(self, text):
        import edge_tts
        async def _say():
            comm = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
            await comm.save("/tmp/feedback.mp3")
            os.system("mpg123 /tmp/feedback.mp3 > /dev/null 2>&1")
        asyncio.run(_say())

    def run(self):
        while rclpy.ok():
            filename = input("\n输入测试文件名,按回车开始识别（后续换成唤醒词触发）...").strip()
            filename = f"/root/{filename}"
            text = self.transcribe(filename)
            result = self.parse_intent(text)
            if result:
                msg = String(data=json.dumps(result, ensure_ascii=False))
                self.publisher.publish(msg)
                self.get_logger().info(f"已发布：{msg.data}")
                cn_name = ROOM_NAME.get(result['destination'], result['destination'])
                self.get_logger().info(f"好的，正在为您导航至{cn_name}")
                self.speak(f"好的，正在为您导航至{cn_name}")
            else:
                self.get_logger().warn("未识别到目的地")
                self.speak("抱歉，我没有听清楚，请再说一次")

def main(args=None):
    rclpy.init(args=args)
    node = VoiceNode()
    rclpy.shutdown()
