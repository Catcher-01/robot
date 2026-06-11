# 医院导诊机器人系统

基于 ROS 2 Humble 和 Gazebo 11 的医院环境智能导诊机器人系统，融合语音交互、手势识别、自然语言理解和自主导航，为患者提供智能化引导服务。

[![ROS 2 Humble](https://img.shields.io/badge/ROS%202-Humble-blue)](https://docs.ros.org/en/humble/)
[![Gazebo 11](https://img.shields.io/badge/Gazebo-11-orange)](https://gazebosim.org/)
[![Python 3.10](https://img.shields.io/badge/Python-3.10-green)](https://www.python.org/)

---

## 目录

- [系统简介](#系统简介)
- [功能特性](#功能特性)
- [系统架构](#系统架构)
- [项目结构](#项目结构)
- [环境要求](#环境要求)
- [安装配置](#安装配置)
- [快速开始](#快速开始)
- [模块说明](#模块说明)
- [地图与导航](#地图与导航)
- [常见问题](#常见问题)
- [许可证](#许可证)

---

## 系统简介

本项目实现一套完整的医院智能导诊机器人系统，核心功能包括：

- 在 Gazebo 11 构建的医院仿真环境中进行机器人导航仿真
- 基于 PyQt5 的 1280×800 竖屏触控界面，支持地图导航、自助挂号、查询等患者服务
- 语音交互：唤醒词检测 → 录音 → ASR（faster-whisper）→ 意图解析（DeepSeek API）→ TTS 语音反馈
- 手势控制：MediaPipe 手部关键点检测，映射为鼠标/触控操作
- AI 助手"小智"：集成 DeepSeek 大语言模型，提供智能导诊对话服务
- Nav2 导航栈：A* 全局规划 + DWA/TEB 局部规划 + AMCL 定位

---

## 功能特性

### 交互方式

- **触控界面**：1280×800 竖屏，5 页面栈式切换（首页、目的地确认、导航执行、到达完成、网页内嵌）
- **语音交互**：唤醒词（"小智"/"你好"/"机器人"）→ 语音录制 → 自动识别 → 导航意图解析 → TTS 确认播报
- **手势控制**：USB 摄像头 + MediaPipe，支持鼠标移动、左键/右键点击、滚轮滚动操作
- **AI 助手**：悬浮式"小智"聊天面板，支持文字和语音双输入

### 导航与感知

- **激光雷达感知**：360° LDS 激光扫描，实时障碍物检测
- **全局路径规划**：A* 算法，基于预生成医院占据栅格地图
- **局部路径规划**：DWA（动态窗口法）和 TEB（时间弹性带）双策略
- **实时定位**：AMCL 自适应蒙特卡洛定位，粒子数自适应 500-3000
- **地图可视化**：静态底图 + 动态障碍叠加 + 激光扫描点 + 规划路径

### 应用场景

- **病房送药导航**：护士站 → 多目标病房配送任务
- **巡逻巡检**：周期性自主巡视医院各关键区域
- **多机器人协同**（进阶）：最多 4 台 TurtleBot3 并行部署

---

## 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                    用户交互层 (User Layer)                     │
│  1280×800 触控界面  │  语音交互  │  手势控制  │  AI 助手  │
└─────────────────────────────┬────────────────────────────────┘
┌─────────────────────────────▼────────────────────────────────┐
│                    业务逻辑层 (Business Layer)                  │
│  hospital_gui (PyQt5)  │  voice_node  │  nav_controller     │
│  页面管理/UI渲染/ROS桥接  │  ASR/TTS/意图解析  │  坐标映射/导航下发 │
└─────────────────────────────┬────────────────────────────────┘
┌─────────────────────────────▼────────────────────────────────┐
│                    导航决策层 (Navigation Layer)                │
│            Nav2 导航栈 (NavigateToPose Action)                │
│  全局规划 (A*)  │  局部规划 (DWA/TEB)  │  AMCL 定位        │
└─────────────────────────────┬────────────────────────────────┘
┌─────────────────────────────▼────────────────────────────────┐
│                    感知层 (Perception Layer)                   │
│  /scan (LaserScan)  │  /amcl_pose  │  /map  │  /plan       │
└─────────────────────────────┬────────────────────────────────┘
┌─────────────────────────────▼────────────────────────────────┐
│                  基础设施层 (Infrastructure Layer)               │
│     ROS 2 Humble  │  Gazebo 11  │  TurtleBot3  │  DDS       │
└──────────────────────────────────────────────────────────────┘
```

### 进程间通信拓扑

```
hospital_gui 进程（独立 GUI）
  ├── PyQt5 主线程（UI 渲染 + 用户交互）
  ├── ROS Bridge 线程（rclpy spin_once，订阅 /scan、/amcl_pose、/plan、/map）
  └── 语音线程（调用 voice_node 离线接口）

voice_node 进程（可与 GUI 共用）
  ├── 麦克风监听线程（持续检测唤醒词）
  ├── ASR 推理（faster-whisper small）
  └── TTS 合成（edge-tts，XiaoxiaoNeural）

nav_controller 进程（ROS 节点）
  └── 订阅 /voice_to_nav → 调用 NavigateToPose action → Nav2

gesture_node 进程（ROS 节点）
  └── VideoCapture → MediaPipe HandLandmarker → /gesture_command
```

---

## 项目结构

```
robot/
├── README.md                    # 本文件
├── 项目报告.md                    # 详细项目报告
├── 组件架构图.drawio             # 架构图（draw.io）
├── 启动.md                      # 快速启动命令
│
├── hospital_gui/               # PyQt5 GUI 应用
│   ├── main_window.py         # 主窗口（5页面管理、全局按钮、ROS桥接）
│   ├── ros_bridge.py          # ROS Bridge（独立线程 + Qt 信号）
│   ├── config.py              # 全局配置（颜色/字体/房间坐标/URL）
│   ├── launch.py             # 启动脚本
│   ├── requirements.txt      # Python 依赖
│   ├── pages/
│   │   ├── home_page.py             # 首页（5宫格菜单、快捷入口、语音按钮）
│   │   ├── destination_confirm_page.py  # 目的地确认页
│   │   ├── navigation_page.py       # 导航执行页（地图+信息卡片）
│   │   ├── arrival_page.py          # 到达完成页
│   │   └── web_page.py             # 网页内嵌页
│   └── widgets/
│       ├── rviz_view.py            # 实时地图渲染控件（RvizView）
│       ├── map_canvas.py           # 备用地图控件
│       ├── ai_assistant.py          # AI 助手"小智"（DeepSeek + 语音）
│       └── emergency_button.py     # 紧急求助按钮
│
├── hospital_ws/                # ROS 2 工作空间
│   └── src/
│       ├── voice_control/     # 语音交互包
│       │   ├── voice_control/
│       │   │   ├── voice_node.py    # 语音节点（唤醒/ASR/TTS/意图解析）
│       │   │   └── nav_controller.py # 意图→坐标映射
│       │   └── package.xml
│       ├── gesture_control/    # 手势控制包
│       │   ├── gesture_control/
│       │   │   └── gesture_node.py  # MediaPipe 手势检测
│       │   └── models/
│       │       └── hand_landmarker.task
│       ├── turtlebot3_gazebo_local/  # 机器人本地配置
│       │   ├── launch/
│       │   │   └── hospital_robot.launch.py  # 医院+机器人联合启动
│       │   └── worlds/             # DQN 强化学习仿真世界
│       └── aws-robomaker-hospital-world/  # AWS 医院仿真世界
│
├── src/                       # 静态资源
│   ├── 地图.jpeg             # 医院俯视图底图
│   ├── 背景.jpeg             # 首页背景图
│   └── 机器人.jpeg           # 机器人图标
│
├── map/                       # 生成的地图文件
│   ├── hospital_map.pgm      # 2D 占据栅格地图
│   └── hospital_map.yaml      # 地图元数据
│
└── map_output/               # 增强地图输出
    ├── hospital_map.pgm       # 2D 地图
    ├── hospital_map.pcd       # 3D 点云地图
    ├── hospital_map.png       # PNG 预览图
    ├── hospital_map.yaml     # 地图元数据
    └── rviz_map.config       # RViz 配置
```

---

## 环境要求

| 组件 | 版本 | 说明 |
|------|------|------|
| 操作系统 | Ubuntu 22.04 (Jammy) | |
| ROS 2 | Humble Hawksbill | |
| Gazebo | Gazebo 11 (Classic) | |
| Python | 3.8+ | 推荐 3.10 |
| TurtleBot3 | burger / waffle / waffle_pi | 本项目使用 burger |

---

## 安装配置

### 1. 配置环境变量

建议将以下内容添加到 `~/.bashrc`：

```bash
# ROS 2 Humble
source /opt/ros/humble/setup.bash

# TurtleBot3 型号
export TURTLEBOT3_MODEL=burger

# Gazebo 模型路径
export GAZEBO_MODEL_PATH=$GAZEBO_MODEL_PATH:$HOME/robot/hospital_ws/src/aws-robomaker-hospital-world/model

# 工作空间
export ROBOT_WS=$HOME/robot/hospital_ws
source $ROBOT_WS/install/setup.bash
```

### 2. 安装系统依赖

```bash
sudo apt update
sudo apt install -y \
    ros-humble-gazebo-ros-pkgs \
    ros-humble-turtlebot3-simulations \
    ros-humble-navigation2 \
    ros-humble-nav2-bringup \
    mpg123 \
    portaudio19-dev
```

### 3. 安装 Python 依赖

```bash
pip install PyQt5 PyYAML numpy opencv-python-headless Pillow edge-tts requests sounddevice
pip install faster-whisper
```

### 4. 构建工作空间

```bash
cd ~/robot/hospital_ws
colcon build
source install/setup.bash
```

### 5. 配置 DeepSeek API Key（可选，AI 助手功能需要）

```bash
export DEEPSEEK_API_KEY=your_api_key_here
```

---

## 快速开始

### 启动顺序（6 个终端）

**Terminal 1 — 医院仿真 + 机器人**

```bash
source /opt/ros/humble/setup.bash
source ~/robot/hospital_ws/install/setup.bash
export TURTLEBOT3_MODEL=burger
ros2 launch turtlebot3_gazebo_local hospital_robot.launch.py
```
> 等 Gazebo 窗口完全出现、机器人加载完毕后，再开下一个终端。

**Terminal 2 — 导航栈（地图 + 定位 + Nav2）**

```bash
source /opt/ros/humble/setup.bash
export TURTLEBOT3_MODEL=burger
ros2 launch turtlebot3_navigation2 navigation2.launch.py \
    use_sim_time:=true \
    map:=/home/hyh/robot/map_output/hospital_map.yaml
```

**Terminal 3 — RViz 可视化（可选，将被前端嵌入）**

```bash
source /opt/ros/humble/setup.bash
rviz2 -d /home/hyh/robot/map_output/rviz_map.config --fixed-frame map
```

**Terminal 4 — 键盘遥控（可选）**

```bash
source /opt/ros/humble/setup.bash
export TURTLEBOT3_MODEL=burger
ros2 run turtlebot3_teleop teleop_keyboard
```

**Terminal 5 — 手势控制（可选）**

```bash
cd ~/robot/hospital_ws
ros2 run gesture_control gesture_node
```

**Terminal 6 — 前端 GUI**

```bash
cd /home/hyh/robot
python3 -m hospital_gui
```

### 关闭所有进程

```bash
killall -9 gzserver gzclient rviz2 ros2
```

### 键盘遥控指令

| 按键 | 动作 |
|------|------|
| W | 前进 |
| X | 后退 |
| A | 左转 |
| D | 右转 |
| 空格 | 停止 |
| Ctrl+C | 退出 |

---

## 模块说明

### hospital_gui — 前端界面

1280×800 竖屏触控应用，包含 5 个页面和多个全局控件：

- **首页**：5 宫格主菜单（地图导航、自助挂号、自助查询、校验单查询、医院官网）+ 快捷目的地入口 + 语音按钮
- **目的地确认页**：地图点击选点 + 分类地点列表（公共服务区、左右两侧病房）
- **导航执行页**：实时地图（机器人位置/规划路径/激光扫描/障碍物）+ 底部导航信息卡片
- **到达完成页**：全屏到达提示，30 秒无操作自动返回首页
- **网页内嵌页**：QWebEngineWidgets 嵌入外部 URL
- **AI 助手"小智"**：右下角悬浮圆形按钮，点击弹出可拖动聊天面板

ROS Bridge 采用独立线程运行 rclpy，通过 Qt QueuedConnection 信号向主线程推送数据，解决 PyQt5 与 rclpy 事件循环冲突。

### voice_node — 语音交互

语音流水线五阶段实现：

1. **唤醒检测**：RMS 能量阈值法（阈值 300），唤醒词 `["小智", "你好", "机器人"]`
2. **VAD**：静默帧数阈值（80 帧，约 5.3 秒自动停止）
3. **ASR**：faster-whisper small 模型，优先 CUDA/GPU，回退 CPU int8 量化
4. **意图解析**：DeepSeek API（deepseek-chat）为主，正则关键词匹配兜底
5. **TTS**：edge-tts XiaoxiaoNeural 音色，mpg123 后台播放

意图解析支持 17 个目的地：病房 101-205、电梯、护士站、挂号处、缴费处、药房、手术室、休息室、医生办公室等。

### gesture_node — 手势控制

基于 MediaPipe HandLandmarker（21 个手部关键点），20Hz 帧率处理 USB 摄像头视频流：

| 手势 | 操作 |
|------|------|
| 食指伸出 + 捏合 | 左键单击 |
| 食指+中指伸出 + 捏合 | 右键单击 |
| 食指+中指伸出 + 移动 | 鼠标移动（指数平滑） |
| 食指+中指伸出 + 手腕 Y 变化 | 滚轮滚动 |
| 4+ 手指伸出 | 冻结鼠标控制 |

### nav_controller — 导航控制器

ROS 节点，订阅 `/voice_to_nav`（JSON 格式意图消息），提取目的地坐标后通过 NavigateToPose Action Client 向 Nav2 发送导航目标。

---

## 地图与导航

### 预生成地图

系统使用预生成的医院占据栅格地图，无需每次启动时重建：

- **地图文件**：`map_output/hospital_map.pgm` + `map_output/hospital_map.yaml`
- **分辨率**：0.05 m/像素
- **覆盖范围**：约 35m × 35m
- **地图原点**：世界坐标 (-12, -32)

### 目的地坐标

预定义了 17 个导航目标点：

| 目的地 ID | 名称 | 世界坐标 (x, y, yaw) |
|-----------|------|---------------------|
| room_101 ~ room_104 | 左侧病房 101-104 | (-8.5, 11.0 ~ -18.0, 0.0) |
| room_201 ~ room_205 | 右侧病房 201-205 | (8.5, 11.0 ~ -28.0, 3.14) |
| elevator | 电梯 | (0.0, 15.0, 0.0) |
| nurse | 护士站 | (0.0, 10.0, 0.0) |
| registration | 挂号处 | (3.5, 5.5, 0.0) |
| payment | 缴费处 | (-3.5, 5.5, 0.0) |
| pharmacy | 药房 | (3.0, -15.0, 0.0) |
| surgery_a | 手术室A | (-3.0, -15.0, 0.0) |
| rest_room | 休息室 | (-10.0, -27.0, 0.0) |
| office_a / office_b | 医生办公室 | (-1.0/1.0, -3.0, 0.0) |

### 导航流程

```
GUI 目的地选择
  → ROOM_COORDS 查表（dest_id → world x, y, yaw）
  → ROSBridge.navigate_to(x, y, yaw)
    → NavigateToPose Action Client
      → Nav2 navigate_to_pose Action Server
        → 全局规划（A* on /map）
        → 局部规划（DWA/TEB on /scan）
          → /cmd_vel (Twist)
            → TurtleBot3 motor controller
```

到达判定条件：机器人与目标点欧氏距离 < 0.8m。

---

## 常见问题

### Gazebo 无法启动

```bash
sudo apt install gazebo11 gazebo11-dev
export GAZEBO_MODEL_PATH=$GAZEBO_MODEL_PATH:~/robot/hospital_ws/src/aws-robomaker-hospital-world/model
```

### 找不到 TurtleBot3 模型

```bash
sudo apt install ros-humble-turtlebot3-gazebo
```

### 前端 GUI 启动失败

确保已安装所有 Python 依赖：

```bash
pip install PyQt5 PyYAML numpy opencv-python-headless Pillow edge-tts requests sounddevice
pip install faster-whisper
```

### 语音识别不可用

检查麦克风设备是否正常，确认 faster-whisper 模型已下载到缓存目录（`~/.cache/huggingface/`）。

### AI 助手无法对话

确认已设置 `DEEPSEEK_API_KEY` 环境变量。

### Gazebo 退出时崩溃

这是 Gazebo 11 的已知问题。正确退出顺序：先在终端按 Ctrl+C 关闭仿真，再关闭 Gazebo 窗口。必要时使用 `killall -9 gzserver gzclient` 强制终止。

---

## 许可证

本项目使用了以下开源组件：

- [AWS RoboMaker Hospital World](https://github.com/aws-robotics/aws-robomaker-hospital-world) — Apache 2.0
- [TurtleBot3](https://github.com/ROBOTIS-GIT/turtlebot3) — Apache 2.0
- [ROS 2 / Nav2](https://navigation.ros.org/) — Apache 2.0
- [faster-whisper](https://github.com/SYSTRON/faster-whisper) — MIT
- [MediaPipe](https://google.github.io/mediapipe/) — Apache 2.0
- [edge-tts](https://github.com/rany2/edge-tts) — GPLv3
