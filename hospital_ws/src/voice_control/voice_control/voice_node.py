import os
import sys
import wave
import asyncio
import json
import threading
import numpy as np
from datetime import datetime

import sounddevice as sd

import rclpy
from openai import OpenAI
from rclpy.node import Node
from std_msgs.msg import String
from faster_whisper import WhisperModel
import whisper

DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY")

# 唤醒词列表
WAKE_WORDS = ["小智", "你好", "机器人"]

# 语音检测阈值（能量 RMS）
RMS_THRESHOLD = 300
# 静默帧数阈值（超过此值视为用户已说完）
SILENT_FRAMES_THRESHOLD = 80
# 唤醒阶段静默超时帧数
WAKE_SILENT_THRESHOLD = 80
# 唤醒阶段最大 buffer 帧数（防长时间噪声）
MAX_WAKE_BUFFER_FRAMES = 800
# 录音阶段最大帧数（防止录音过长）
MAX_RECORD_FRAMES = 1600

SYSTEM_PROMPT = """
规则：
你是一个医院导航助手，从用户话语中提取导航目的地，只能从以下已知地点中选择。

已知地点（地图坐标）：
elevator=电梯(0,15)，registration=挂号处(3.5,5.5)，payment=缴费处(-3.5,5.5)，
nurse=护士站(0,10)，surgery_a=手术室A(-3,-15)，pharmacy=药房(3,-15)，
room_101=101病房(-8.5,11)，room_102=102病房(-8.5,4.75)，room_103=103病房(-8.5,-4.75)，room_104=104病房(-8.5,-18)，
room_201=201病房(8.5,11)，room_202=202病房(8.5,4.75)，room_203=203病房(8.5,-4.75)，room_204=204病房(8.5,-18)，room_205=205病房(6,-28)，
rest_room=休息室(-10,-27)，office_a=医生办公室A(-1,-3)，office_b=医生办公室B(1,-3)。

只输出JSON，不做任何解释。
成功：{"action":"navigation","destination":"room_id"}
失败：{"action":"unknown","destination":null}
"""

# 地点ID → 中文名称（用于语音播报）
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
}

# 唤醒词后手动输入（用于调试，正式用VAD时可改为自动录音）
# 按 Ctrl+C 停止，按回车开始录音

class VoiceNode(Node):
    def __init__(self):
        super().__init__('voice_node')
        if not DEEPSEEK_KEY:
            self.get_logger().warn("未检测到 DEEPSEEK_API_KEY，LLM 解析将不可用")
        self.publisher = self.create_publisher(String, '/voice_to_nav', 10)

        # 优先离线模式，避免联网失败导致节点崩溃
        self.model = None
        for offline in (True, False):
            for device, compute_type in [("cuda", "float16"), ("cpu", "int8")]:
                try:
                    self.model = WhisperModel(
                        "/home/hyh/.cache/huggingface/hub/models--Systran--faster-whisper-small",
                        device=device, compute_type=compute_type,
                        local_files_only=True,
                    )
                    self.get_logger().info(f"Whisper 模型加载完成（{device}，offline={offline}）")
                    break
                except Exception:
                    pass
            if self.model:
                break
        if self.model is None:
            self.get_logger().error("Whisper 模型加载失败，请检查网络或缓存")
            raise RuntimeError("Whisper 模型加载失败")

        self.client = None
        if DEEPSEEK_KEY:
            self.client = OpenAI(api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com")

        self.get_logger().info("语音节点启动完成！")

        # 在单独线程中运行麦克风监听
        self.running = True
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()

    def _listen_loop(self):
        """持续监听麦克风，检测到唤醒词后录音"""
        self.get_logger().info("麦克风监听线程已启动，说 '小智' 或 '你好' 唤醒...")
        while self.running:
            try:
                wake_buffer, triggered = self._wait_for_wake()
                if not self.running:
                    break
                if triggered and wake_buffer:
                    self._record_and_process(wake_buffer)
            except Exception as e:
                self.get_logger().error(f"监听循环异常: {e}")

    def _wait_for_wake(self):
        """监听唤醒词（简单能量检测 + 关键词匹配）"""
        wake_buffer = []
        silent_frames = 0
        triggered = False

        with sd.InputStream(samplerate=16000, channels=1, dtype='int16',
                            blocksize=1024, device=None) as stream:
            for _ in range(16000):
                data, _ = stream.read(1024)
                audio_data = data.flatten()
                rms = np.sqrt(np.mean(audio_data.astype(float) ** 2))

                if rms > RMS_THRESHOLD:
                    triggered = True

                if triggered:
                    wake_buffer.append(data.tobytes())
                    silent_frames = 0
                else:
                    silent_frames += 1

                if triggered and silent_frames > WAKE_SILENT_THRESHOLD:
                    break

                if len(wake_buffer) > MAX_WAKE_BUFFER_FRAMES:
                    # 重置所有状态，重新监听（防止噪声长时间占用 buffer）
                    wake_buffer.clear()
                    silent_frames = 0
                    triggered = False

        return wake_buffer, triggered

    def _record_and_process(self, wake_buffer=None):
        """录制一句话并处理"""
        self.get_logger().info("检测到唤醒，开始录音...")
        frames = list(wake_buffer) if wake_buffer else []
        silent_frames = 0
        speaking = False

        with sd.InputStream(samplerate=16000, channels=1, dtype='int16',
                            blocksize=1024, device=None) as stream:
            for i in range(MAX_RECORD_FRAMES):
                data, _ = stream.read(1024)
                frames.append(data.tobytes())
                audio_data = data.flatten()
                rms = np.sqrt(np.mean(audio_data.astype(float) ** 2))

                if rms > RMS_THRESHOLD:
                    speaking = True
                    silent_frames = 0
                elif speaking:
                    silent_frames += 1
                    if silent_frames > SILENT_FRAMES_THRESHOLD:
                        break

        # 保存为 wav
        wav_path = "/tmp/voice_input.wav"
        wf = wave.open(wav_path, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b''.join(frames))
        wf.close()

        self.get_logger().info("录音结束，开始识别...")
        text = self.transcribe(wav_path)
        if text.strip():
            result = self.parse_intent(text)
            if result:
                self._publish_and_speak(result, text)
            else:
                self.speak("抱歉，我没有听清楚，请再说一次。")
        else:
            self.get_logger().warn("识别结果为空")
            self.speak("我没有听到声音，请再说一次。")

    def transcribe(self, filename="/tmp/voice_input.wav"):
        self.get_logger().info("正在识别...")
        try:
            segments, _ = self.model.transcribe(
                filename,
                language="zh",
                beam_size=5,
                initial_prompt="简体中文，医院导航相关"
            )
            text = "".join([s.text for s in segments])
            self.get_logger().info(f"识别结果：{text}")
            return text
        except Exception as e:
            self.get_logger().error(f"识别失败: {e}")
            return ""

    def parse_with_llm(self, text):
        if not self.client:
            return None
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text}
                ],
                max_tokens=100,
                timeout=10
            )
            raw = response.choices[0].message.content.strip()
            result = json.loads(raw)
            if result.get("destination"):
                return result
        except Exception as e:
            self.get_logger().warn(f"LLM 解析失败: {e}")
        return None

    def parse_with_regex(self, text):
        """关键词匹配 fallback，与 SYSTEM_PROMPT 覆盖的房间保持一致"""
        import re
        # 与 SYSTEM_PROMPT 中的房间列表完全对齐
        match = re.search(r'(10[1-4]|20[1-5])', text)
        if match:
            return {"action": "navigation", "destination": f"room_{match.group(1)}"}
        # 特殊地点关键词（注意：长的放前面，避免短词先匹配）
        for keyword, dest_id in [
            ("休息室", "rest_room"),
            ("医生办公室A", "office_a"),
            ("医生办公室B", "office_b"),
            ("医生办公室", "office_a"),
            ("手术室A", "surgery_a"),
            ("手术室", "surgery_a"),
            ("护士站", "nurse"),
            ("电梯", "elevator"),
            ("挂号处", "registration"),
            ("缴费处", "payment"),
            ("药房", "pharmacy"),
        ]:
            if keyword in text:
                return {"action": "navigation", "destination": dest_id}
        # 走廊 / 大门
        if "走廊" in text or "中央" in text:
            return {"action": "navigation", "destination": "corridor"}
        if "门" in text:
            return {"action": "navigation", "destination": "door"}
        return None

    def parse_intent(self, text):
        result = self.parse_with_llm(text)
        if result:
            self.get_logger().info(f"LLM 解析成功: {result}")
            return result
        result = self.parse_with_regex(text)
        if result:
            self.get_logger().warn(f"使用关键词匹配: {result}")
            return result
        return None

    def _publish_and_speak(self, result, text=""):
        result["raw_text"] = text
        result["timestamp"] = int(datetime.now().strftime("%y%m%d%H%M%S"))
        msg = String(data=json.dumps(result, ensure_ascii=False))
        self.publisher.publish(msg)
        self.get_logger().info(f"已发布: {msg.data}")

        dest = result.get("destination", "")
        cn_name = ROOM_NAME.get(dest, dest)
        self.speak(f"好的，正在为您导航至{cn_name}。")

    def speak(self, text):
        def _play_in_background(mp3_path: str):
            """在后台线程中播放音频，不阻塞调用者"""
            try:
                import subprocess
                subprocess.run(
                    ["mpg123", "-q", mp3_path],
                    check=True,
                    stderr=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                )
            except Exception:
                pass

        try:
            import edge_tts
            import concurrent.futures

            async def _say():
                comm = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
                await comm.save("/tmp/feedback.mp3")
                # 在后台线程播放，不阻塞 ROS spin
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                executor.submit(_play_in_background, "/tmp/feedback.mp3")
                executor.shutdown(wait=False)

            asyncio.run(_say())
        except Exception as e:
            self.get_logger().warn(f"TTS 失败: {e}")

    def destroy_node(self):
        self.running = False
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = VoiceNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


# ─────────────────────────────────────────────────────────────────────────────
# 供 GUI 直接调用的同步识别接口
# 用法：from hospital_ws.src.voice_control.voice_control import voice_node
#       result = voice_node.recognize_audio("/tmp/voice_input.wav")
#       # result: {"action": "navigation", "destination": "room_103"}
#       # 或 None
# ─────────────────────────────────────────────────────────────────────────────
# 离线语音引擎（不依赖 ROS2，供 GUI 直接调用）
# ─────────────────────────────────────────────────────────────────────────────
class _VoiceOffline:
    """
    与 VoiceNode API 兼容的离线版：
      - transcribe(wav_path) -> str
      - parse_intent(text) -> dict | None
    不依赖 rclpy，不发布 ROS 话题。

    模型加载优先级：
      1. faster-whisper small（CPU/GPU），优先联网下载（可从 HF Hub 拉取）；
         网络不可用时使用本地缓存（需提前下载到 HF Hub 缓存目录）。
      2. openai-whisper base，本地 .pt 权重兜底（/home/hyh/.cache/whisper/base.pt）。

    _engine: 存储 ("fast", WhisperModel) 或 ("whisper", whisper_model)
    """

    _engine = None   # ("fast", WhisperModel) 或 ("whisper", whisper_model)
    _model_lock = threading.Lock()

    def __init__(self):
        self._ensure_model()

    @classmethod
    def _ensure_model(cls):
        if cls._engine is not None:
            return
        with cls._model_lock:
            if cls._engine is not None:
                return
            # ── 优先：faster-whisper small ─────────────────────────────────────
            # 尝试 1：允许联网下载（HF Hub）
            cls._try_load(offline=False)
            # 尝试 2：仅本地（网络异常时使用已缓存模型）
            if cls._engine is None:
                print("[voice_node] faster-whisper 本地缓存未找到，尝试强制离线...")
                cls._try_load(offline=True)
            # ── 兜底：openai-whisper base（本地 base.pt） ─────────────────────
            if cls._engine is None:
                print("[voice_node] 尝试 openai-whisper base 兜底...")
                cls._try_load_whisper()
            if cls._engine is None:
                raise RuntimeError(
                    "所有离线语音引擎均不可用："
                    "faster-whisper small 未缓存且网络不可达，"
                    "openai-whisper base 权重不存在"
                )

    @classmethod
    def _try_load(cls, offline: bool):
        for device, compute_type in [("cuda", "float16"), ("cpu", "int8")]:
            try:
                print(f"[voice_node] 加载 faster-whisper small（{device}，offline={offline}）...")
                model = WhisperModel(
                    "/home/hyh/.cache/huggingface/hub/models--Systran--faster-whisper-small",
                    device=device,
                    compute_type=compute_type,
                    local_files_only=True,
                )
                cls._engine = ("fast", model)
                print(f"[voice_node] faster-whisper small ({device}) 就绪")
                return
            except Exception as e:
                print(f"[voice_node] {device} 加载失败: {e}")
        # 两个后端都失败
        cls._engine = None

    @classmethod
    def _try_load_whisper(cls):
        """使用 openai-whisper + 本地 base.pt 作为最后兜底。"""
        base_path = "/home/hyh/.cache/whisper/base.pt"
        if not os.path.exists(base_path):
            print(f"[voice_node] 找不到本地权重: {base_path}")
            return
        try:
            import whisper
            print(f"[voice_node] 加载 openai-whisper base（{base_path}）...")
            model = whisper.load_model("base", device="cpu", download_root="/home/hyh/.cache/whisper")
            cls._engine = ("whisper", model)
            print("[voice_node] openai-whisper base 就绪（CPU）")
        except Exception as e:
            print(f"[voice_node] openai-whisper base 加载失败: {e}")
            cls._engine = None

    def transcribe(self, wav_path: str) -> str:
        import traceback as _tb
        self._ensure_model()
        try:
            engine_type, model = self._engine
            if engine_type == "fast":
                segments, _ = model.transcribe(
                    wav_path,
                    language="zh",
                    beam_size=5,
                    vad_filter=True,
                )
                return "".join(seg.text for seg in segments).strip()
            else:  # whisper
                result = model.transcribe(wav_path, language="zh", beam_size=5)
                return result.get("text", "").strip()
        except Exception as e:
            import sys as _sys
            _tb.print_exc()
            with open("/tmp/voice_err.log", "a") as f:
                f.write(f"[voice_node] ASR 异常: {e}\n")
                f.write(_tb.format_exc())
            return ""

    def parse_intent(self, text: str):
        if not text or not text.strip():
            return None
        if DEEPSEEK_KEY:
            try:
                return self._llm_parse(text)
            except Exception as e:
                print(f"[voice_node] LLM 解析异常: {e}")
        return self._keyword_parse(text)

    # ── LLM 路径 ─────────────────────────────────────────────────────────────
    def _llm_parse(self, text: str):
        client = OpenAI(api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.0,
            max_tokens=64,
        )
        raw = response.choices[0].message.content.strip()
        try:
            obj = json.loads(raw)
            return {"action": obj.get("action"), "destination": obj.get("destination")}
        except Exception:
            return None

    # ── 关键词回退 ───────────────────────────────────────────────────────────
    def _keyword_parse(self, text: str):
        # 长的放前面优先匹配，避免短词覆盖长词
        for keyword, dest_id in [
            ("休息室", "rest_room"),
            ("医生办公室A", "office_a"),
            ("医生办公室B", "office_b"),
            ("医生办公室", "office_a"),
            ("手术室A", "surgery_a"),
            ("手术室", "surgery_a"),
            ("护士站", "nurse"),
            ("电梯", "elevator"),
            ("挂号处", "registration"),
            ("缴费处", "payment"),
            ("药房", "pharmacy"),
        ]:
            if keyword in text:
                return {"action": "navigation", "destination": dest_id}
        # 房间号匹配（与 SYSTEM_PROMPT 一致）
        import re
        m = re.search(r"(10[1-4]|20[1-5])", text)
        if m:
            return {"action": "navigation", "destination": f"room_{m.group(1)}"}
        return None


# ─────────────────────────────────────────────────────────────────────────────
_instance = None
_instance_lock = threading.Lock()


def _ensure_instance():
    """
    初始化 _instance（只执行一次，线程安全）。
    优先尝试离线模式（GUI / 非 ROS 进程），失败后再尝试 ROS2（ros_bridge 环境）。
    """
    global _instance

    if _instance is not None:
        return

    with _instance_lock:
        if _instance is not None:
            return

        # 路径一：离线引擎（GUI 直接导入时走这里，最常见）
        try:
            _instance = _VoiceOffline()
            print("[voice_node] 使用离线语音引擎（无 ROS2 依赖）")
            return
        except Exception as e:
            print(f"[voice_node] 离线引擎初始化失败: {e}")

        # 路径二：ROS2（ros_bridge 已 init rclpy 的环境）
        try:
            rclpy_ok = rclpy.utilities.ok()
        except Exception:
            rclpy_ok = False
        try:
            if rclpy_ok:
                _instance = VoiceNode()
            else:
                rclpy.init()
                _instance = VoiceNode()
            print("[voice_node] 使用 ROS2 语音节点")
            import time
            time.sleep(1.5)
        except Exception as e:
            print(f"[voice_node] ROS2 节点初始化失败: {e}")
            _instance = None


def recognize_audio(wav_path: str):
    """
    在当前进程中初始化 ROS（一次性），对 wav_path 执行转写+意图解析，
    返回解析结果 dict 或 None。
    """
    global _instance

    _ensure_instance()

    if _instance is None:
        print("[voice_node] 语音引擎不可用，跳过 ASR")
        return None

    try:
        text = _instance.transcribe(wav_path)
    except Exception as e:
        print(f"[voice_node] 转写异常: {e}")
        return None

    if not text.strip():
        return None
    result = _instance.parse_intent(text)
    return result


def _get_mic_device_index():
    """返回 sounddevice 默认输入设备索引。"""
    try:
        info = sd.query_devices(kind='input')
        return info['index']
    except Exception:
        return None


_MIC_DEVICE_INDEX = _get_mic_device_index()
print(f"[voice_node] 麦克风设备: {_MIC_DEVICE_INDEX}")


def record_and_recognize_voice(timeout_s=10):
    """
    同步接口，供 GUI 调用：
      - 打开麦克风等待唤醒（能量 > 300）
      - 10s 内检测到唤醒则继续录音；超时则返回空
      - 录音结束后做 ASR + 意图解析
      - 返回 dict {"action":..., "destination":..., "raw_text":...} 或 None
    """
    # ── 阶段一：等待唤醒（带 10s 超时）─────────────────────────────
    wake_buffer = []
    triggered = False
    silent_frames = 0
    max_wait_frames = int(timeout_s * 16000 / 1024)

    with sd.InputStream(samplerate=16000, channels=1, dtype='int16',
                        blocksize=1024, device=_MIC_DEVICE_INDEX) as stream:
        for _ in range(max_wait_frames):
            data, _ = stream.read(1024)
            audio_data = data.flatten()
            rms = np.sqrt(np.mean(audio_data.astype(float) ** 2))

            if rms > RMS_THRESHOLD:
                triggered = True

            if triggered:
                wake_buffer.append(data.tobytes())
                silent_frames = 0
            else:
                silent_frames += 1

            if triggered and silent_frames > WAKE_SILENT_THRESHOLD:
                break

    if not triggered or not wake_buffer:
        return None

    # ── 阶段二：录制一句话 ──────────────────────────────────────────
    frames = list(wake_buffer)
    silent_frames = 0
    speaking = False

    with sd.InputStream(samplerate=16000, channels=1, dtype='int16',
                        blocksize=1024, device=_MIC_DEVICE_INDEX) as stream:
        for _ in range(MAX_RECORD_FRAMES):
            data, _ = stream.read(1024)
            frames.append(data.tobytes())
            audio_data = data.flatten()
            rms = np.sqrt(np.mean(audio_data.astype(float) ** 2))

            if rms > RMS_THRESHOLD:
                speaking = True
                silent_frames = 0
            elif speaking:
                silent_frames += 1
                if silent_frames > SILENT_FRAMES_THRESHOLD:
                    break

    # ── 保存 WAV ────────────────────────────────────────────────────
    wav_path = "/tmp/voice_input_gui.wav"
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"".join(frames))

    # ── ASR + 意图解析（直接在当前线程做，不启动 ROS spin）────────
    text = _recognize_wav(wav_path)
    if not text or not text.strip():
        return None

    result = _parse_intent_text(text)
    if result:
        result["raw_text"] = text
        result["timestamp"] = int(datetime.now().strftime("%y%m%d%H%M%S"))
    return result


def _recognize_wav(wav_path: str) -> str:
    """对本地 wav 做 ASR，返回识别的文字。"""
    import traceback as _tb
    import sys as _sys
    _ensure_instance()
    if _instance is None:
        return ""
    try:
        return _instance.transcribe(wav_path)
    except Exception as e:
        with open("/tmp/voice_err.log", "a") as f:
            f.write(f"[_recognize_wav] 异常: {e}\n")
            f.write(_tb.format_exc())
        return ""


def _parse_intent_text(text: str):
    """对给定文字做意图解析，返回 dict 或 None。"""
    _ensure_instance()
    if _instance is None:
        return None
    return _instance.parse_intent(text)


# ─────────────────────────────────────────────────────────────────────────────
# 直接录音识别（无唤醒词，直接录音到静默停止）
# ─────────────────────────────────────────────────────────────────────────────

def record_until_silence(timeout_s=8, min_speech_frames=3):
    """
    直接录音，直到检测到静默为止。

    参数:
        timeout_s:            最长录音秒数
        min_speech_frames:    至少需要检测到多少帧语音才认为是有效录音

    返回:
        (wav_path: str, text: str) 或 (None, None)
        - wav_path: 保存的 wav 文件路径，失败时为 None
        - text:     ASR 识别结果，失败或空时为 ""
    """
    frames = []
    silent_frames = 0
    speaking = False
    speech_frame_count = 0
    max_frames = int(timeout_s * 16000 / 1024)

    with sd.InputStream(samplerate=16000, channels=1, dtype='int16',
                        blocksize=1024, device=_MIC_DEVICE_INDEX) as stream:
        for _ in range(max_frames):
            data, _ = stream.read(1024)
            audio_data = data.flatten()
            rms = np.sqrt(np.mean(audio_data.astype(float) ** 2))

            if rms > RMS_THRESHOLD:
                speaking = True
                speech_frame_count += 1
                silent_frames = 0
            elif speaking:
                silent_frames += 1
                if silent_frames > SILENT_FRAMES_THRESHOLD:
                    break

            if speaking:
                frames.append(data.tobytes())

    # 有效语音帧数不足，视为无效
    if speech_frame_count < min_speech_frames or not frames:
        return None, ""

    wav_path = "/tmp/voice_direct.wav"
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"".join(frames))

    # ASR
    text = _recognize_wav(wav_path)
    return wav_path, text
