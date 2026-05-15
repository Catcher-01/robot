# 医院机器人仿真项目

基于 ROS 2 Humble 和 Gazebo 11 的医院环境导航与建图仿真项目，使用 TurtleBot3 机器人。

ROS 2
Gazebo
License

---

## 目录

- [项目概述](#项目概述)
- [功能特性](#功能特性)
- [系统架构](#系统架构)
- [项目结构](#项目结构)
- [环境配置](#环境配置)
- [安装指南](#安装指南)
- [快速开始](#快速开始)
- [地图生成](#地图生成)
- [机器人导航](#机器人导航)
- [语音交互](#语音交互)
- [配置说明](#配置说明)
- [常见问题](#常见问题)
- [进阶用法](#进阶用法)
- [依赖参考](#依赖参考)
- [许可证](#许可证)
- [致谢](#致谢)

---

## 项目概述

本项目实现以下功能：

- 在 Gazebo 11 构建的医院仿真环境中模拟 TurtleBot3 机器人
- 直接从 Gazebo 仿真世界生成 2D/3D 地图
- 通过键盘控制机器人进行遥控
- 在真实的医院场景中进行导航规划与测试

---

## 功能特性

- **真实医院环境**：预构建的医院模型，包含病房、走廊、电梯、床位、医疗设备等
- **多楼层支持**：支持单层、双层、三层医院变体
- **多机器人仿真**：支持同时部署多个 TurtleBot3 机器人
- **地图生成**：支持基于 SDF 的离线地图生成和基于 Gazebo 插件的实时地图生成
- **3D 建图**：生成 PCD 点云和二进制八叉树地图用于 3D 导航
- **多种机器人型号**：支持 burger、waffle、waffle_pi 三种变体
- **快速遥控**：自定义键盘控制，速度加倍

---

## 系统架构

本项目采用分层架构，各模块职责清晰、耦合度低：

```
┌─────────────────────────────────────────────────────────┐
│                      用户层 (User Layer)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  键盘遥控     │  │  地图查看器   │  │  Nav2 导航   │  │
│  │  (Teleop)   │  │  (RViz)      │  │  (Nav2)      │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│                    应用层 (Application Layer)            │
│  ┌──────────────────────┐  ┌──────────────────────┐    │
│  │   turtlebot3_gazebo  │  │   gazebo_map_creator │    │
│  │   _local (机器人配置) │  │     (地图生成插件)    │    │
│  └──────────────────────┘  └──────────────────────┘    │
│  ┌──────────────────────────────────────────────────┐  │
│  │         aws-robomaker-hospital-world             │  │
│  │                    (医院仿真世界)                   │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│                    通信层 (Communication Layer)         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Topic      │  │   Service    │  │   Action     │  │
│  │  /cmd_vel    │  │ /map_request │  │ /navigate    │  │
│  │  /scan       │  │ /spawn_robot │  │              │  │
│  │  /odom       │  │              │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│                    基础层 (Infrastructure Layer)        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   ROS 2      │  │   Gazebo 11  │  │  TurtleBot3  │  │
│  │   Humble     │  │   (物理引擎)  │  │   机器人模型  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│  ┌──────────────┐  ┌──────────────┐                    │
│  │    PCL       │  │   OctoMap    │                    │
│  │ (点云处理)    │  │ (3D 地图)    │                    │
│  └──────────────┘  └──────────────┘                    │
└─────────────────────────────────────────────────────────┘
```

### 架构说明


| 层级      | 组件                                                                      | 说明                         |
| ------- | ----------------------------------------------------------------------- | -------------------------- |
| **用户层** | Teleop、RViz、Nav2                                                        | 直接面向用户的交互工具和导航堆栈           |
| **应用层** | gazebo_map_creator、turtlebot3_gazebo_local、aws-robomaker-hospital-world | 核心业务逻辑，包含地图生成插件、机器人配置、仿真环境 |
| **通信层** | ROS 2 Topic/Service/Action                                              | 节点间通信机制                    |
| **基础层** | ROS 2 Humble、Gazebo 11、TurtleBot3                                       | 底层基础设施和仿真引擎                |


### 数据流

```
地图生成流程：

用户请求 ──Service──▶ gazebo_map_creator ──Ray Cast──▶ Gazebo World
                                        │
                                        ▼
                              ┌─────────────────┐
                              │  地图数据生成     │
                              │ (PGM/PCD/BT)   │
                              └─────────────────┘
                                        │
                                        ▼
                              ┌─────────────────┐
                              │  输出文件保存    │
                              │  map_output/   │
                              └─────────────────┘

导航流程：

地图加载 ──▶ Nav2 ──▶ 路径规划 ──▶ 速度指令 ──▶ cmd_vel ──▶ TurtleBot3
                                      │
                                      ▼
                              ┌─────────────────┐
                              │  里程计/Scan     │
                              │   反馈数据       │
                              └─────────────────┘
```

---

## 项目结构

```
robot/
├── README.md                    # 本文件
├── gen_hospital_map.py         # Python 脚本：从 SDF 世界文件生成 2D 地图
├── 地图                          # 中文文档
├── 地图.docx                     # 中文文档 (Word 格式)
├── map/                         # 生成的地图输出目录
│   ├── hospital_map.pgm        # 2D 占据栅格地图
│   └── hospital_map.yaml        # 地图元数据 (Nav2 用)
└── map_output/                  # 备选地图输出目录
    ├── hospital_map.pcd         # 3D 点云地图
    ├── hospital_map.bt          # 二进制八叉树地图
    ├── hospital_map.pgm         # 2D 地图
    ├── hospital_map.png         # PNG 预览图
    └── hospital_map.yaml        # 地图元数据

hospital_ws/                     # 主 ROS 2 工作空间
├── src/
│   ├── gazebo_map_creator/      # Gazebo 地图生成插件
│   │   ├── gazebo_map_creator/  # C++ 插件实现
│   │   ├── gazebo_map_creator_interface/  # ROS 服务定义
│   │   ├── scripts/             # Python 工具脚本
│   │   └── launch/              # 启动文件
│   ├── aws-robomaker-hospital-world/     # 医院 Gazebo 世界
│   │   ├── world/               # 世界文件 (.world)
│   │   └── model/               # Gazebo 模型
│   ├── turtlebot3_gazebo_local/ # 本地 TurtleBot3 配置
│   │   ├── launch/              # 启动文件
│   │   ├── urdf/                # 机器人描述
│   │   └── worlds/              # 测试环境
│   ├── voice_control/             # 语音交互模块
│   │   ├── voice_control/         # 核心源码 (voice_node.py)
│   │   ├── package.xml            # 依赖声明
│   │   └── setup.py               # 安装配置
│   └── turtlebot3_models/       # TurtleBot3 模型定义
│   
│ 
├── build/                       # 构建产物
├── install/                    # 安装产物
└── log/                        # 构建日志
```

---

## 环境配置

### 系统要求

- **操作系统**: Ubuntu 22.04 (Jammy Jellyfish)
- **ROS 2**: Humble Hawksbill
- **Gazebo**: Gazebo 11 (Classic)
- **Python**: 3.8+

### 环境变量配置

建议将以下环境变量添加到 `~/.bashrc`：

```bash
# ROS 2 Humble
source /opt/ros/humble/setup.bash

# TurtleBot3 模型选择
export TURTLEBOT3_MODEL=waffle_pi

# Gazebo 模型路径
export GAZEBO_MODEL_PATH=$GAZEBO_MODEL_PATH:$HOME/robot/hospital_ws/src/aws-robomaker-hospital-world/model

# 工作空间路径
export ROBOT_WS=$HOME/robot/hospital_ws
source $ROBOT_WS/install/setup.bash
```

---

## 安装指南

### 1. 安装系统依赖

```bash
sudo apt update
sudo apt install -y \
    libboost-dev \
    libpcl-dev \
    ros-humble-gazebo-ros-pkgs \
    ros-humble-turtlebot3-simulations
```

### 2. 安装 Python 依赖

```bash
pip3 install Pillow numpy
```

### 3. 构建工作空间

```bash
cd ~/robot/hospital_ws
source /opt/ros/humble/setup.bash
colcon build
```

### 4. 配置环境

```bash
source install/setup.bash
```

---

## 快速开始

### 启动医院仿真 + TurtleBot3

```bash
cd ~/robot/hospital_ws
source install/setup.bash

# 启动仿真
ros2 launch turtlebot3_gazebo_local turtlebot3_hospital.launch.py
```

### 仅启动医院世界（不含机器人）

```bash
cd ~/robot/hospital_ws
source install/setup.bash
ros2 launch gazebo_map_creator view_hospital.launch.py
```

### 启动多机器人仿真

```bash
cd ~/robot/hospital_ws
source install/setup.bash
ros2 launch turtlebot3_gazebo_local multi_robot.launch.py
```

### 键盘遥控机器人

```bash
# 在新终端中
source install/setup.bash
ros2 run gazebo_map_creator teleop_keyboard_fast
```

键盘控制说明：

- `W` - 前进
- `X` - 后退
- `A` - 左转
- `D` - 右转
- `空格` - 停止
- `Ctrl+C` - 退出

---

## 地图生成

### 方式一：SDF 世界文件离线生成

直接从 SDF 世界文件生成 2D 地图（无需运行仿真）：

```bash
cd ~/robot
python3 gen_hospital_map.py
```

此脚本执行以下操作：

1. 解析 hospital.world SDF 文件
2. 提取静态几何体（墙壁、家具、设备）
3. 光栅化为 2D 占据栅格
4. 输出 PGM、YAML 和 PNG 预览文件

**输出文件：**

- `map/hospital_map.pgm` - 2D 占据栅格地图
- `map/hospital_map.yaml` - 地图元数据
- `map_output/hospital_map.pgm` - 备选位置
- `map_output/hospital_map.png` - 可视化预览

### 方式二：Gazebo 插件实时生成

在仿真运行时通过 ROS 2 服务接口生成地图：

```bash
# 启动仿真
ros2 launch gazebo_map_creator turtlebot3_hospital.launch.py

# 在另一终端请求地图生成
ros2 service call /map_request gazebo_map_creator_interface/srv/MapRequest "{ \
    lowerright_x: 0.0, \
    lowerright_y: 0.0, \
    upperleft_x: 50.0, \
    upperleft_y: 50.0, \
    resolution: 0.01, \
    range_multiplier: 1.5, \
    filename: 'hospital_map', \
    is_3d: false \
}"
```

**地图请求参数：**


| 参数                 | 类型     | 默认值   | 说明           |
| ------------------ | ------ | ----- | ------------ |
| `lowerright_x`     | float  | 0.0   | 右下角 X 坐标     |
| `lowerright_y`     | float  | 0.0   | 右下角 Y 坐标     |
| `upperleft_x`      | float  | 50.0  | 左上角 X 坐标     |
| `upperleft_y`      | float  | 50.0  | 左上角 Y 坐标     |
| `resolution`       | float  | 0.01  | 地图分辨率 (米/像素) |
| `range_multiplier` | float  | 1.5   | 传感器范围乘数      |
| `filename`         | string | "map" | 输出文件名前缀      |
| `is_3d`            | bool   | false | 是否生成 3D 点云   |


### 地图格式说明


| 格式      | 说明     | 用途                |
| ------- | ------ | ----------------- |
| `.pgm`  | 便携式灰度图 | Nav2 2D 导航        |
| `.yaml` | 地图元数据  | ROS map_server 加载 |
| `.pcd`  | 点云数据   | 3D SLAM、可视化       |
| `.bt`   | 二进制八叉树 | 3D 路径规划           |
| `.png`  | 图片预览   | 快速可视化             |


---

## 机器人导航

### 使用 Navigation2 导航栈

```bash
# 启动仿真
ros2 launch gazebo_map_creator turtlebot3_hospital.launch.py

# 在另一终端启动导航
ros2 launch nav2_bringup bringup_launch.py \
    map:=$(pwd)/../map_output/hospital_map.yaml
```

### 启动文件参考


| 启动文件                            | 说明               |
| ------------------------------- | ---------------- |
| `turtlebot3_hospital.launch.py` | 医院 + TurtleBot3  |
| `view_hospital.launch.py`       | 仅医院环境            |
| `hospital.launch.py`            | 医院仿真             |
| `turtlebot3_world.launch.py`    | 默认 TurtleBot3 世界 |
| `spawn_turtlebot3.launch.py`    | 仅部署机器人           |
| `multi_robot.launch.py`         | 多机器人模式           |


---

## 语音交互


---

## 配置说明

### 地图 YAML 配置

```yaml
image: hospital_map.pgm
mode: trinary
resolution: 0.05
origin: [0.0, 0.0, 0.0]
negate: 0
occupied_thresh: 0.65
free_thresh: 0.196
```

### TurtleBot3 型号选择

启动前设置机器人型号：

```bash
export TURTLEBOT3_MODEL=waffle_pi
ros2 launch gazebo_map_creator turtlebot3_hospital.launch.py
```

可选型号：

- `burger` - 基础型号
- `waffle` - 宽型
- `waffle_pi` - 带 Pi 摄像头

### Gazebo 物理参数配置

修改世界文件以调整物理仿真参数：

```xml
<physics type="ode">
  <max_step_size>0.001</max_step_size>
  <real_time_factor>1.0</real_time_factor>
  <real_time_update_rate>1000</real_time_update_rate>
</physics>
```

---

## 常见问题

### 问题：Gazebo 无法启动

**解决方案：**

```bash
# 安装 Gazebo 依赖
sudo apt install gazebo11 gazebo11-dev

# 设置 Gazebo 模型路径
export GAZEBO_MODEL_PATH=$GAZEBO_MODEL_PATH:~/robot/hospital_ws/src/aws-robomaker-hospital-world/model

# 或添加到 ~/.bashrc 持久化
echo 'export GAZEBO_MODEL_PATH=$GAZEBO_MODEL_PATH:~/robot/hospital_ws/src/aws-robomaker-hospital-world/model' >> ~/.bashrc
```

### 问题：找不到 TurtleBot3 模型

**解决方案：**

```bash
# 安装 TurtleBot3 模型
sudo apt install ros-humble-turtlebot3-gazebo

# 或手动克隆
cd ~/robot/hospital_ws/src
git clone https://github.com/ROBOTIS-GIT/turtlebot3_simulations.git
colcon build --packages-select turtlebot3_gazebo
```

### 问题：地图服务不可用

**解决方案：**

```bash
# 确保插件已加载
ros2 node list | grep map_creator

# 检查服务可用性
ros2 service list | grep map_request

# 如需重新加载
ros2 launch gazebo_map_creator gazebo_map_creator.launch.py
```

### 问题：colcon 构建报错

**解决方案：**

```bash
# 清理并重新构建
cd ~/robot/hospital_ws
rm -rf build install log
colcon build --cmake-clean-cache
source /opt/ros/humble/setup.bash
colcon build
```

### 问题：退出时 Gazebo 段错误

这是 Gazebo 11 的已知问题。可通过以下方式减少发生：

- 按正确顺序关闭终端（关闭 Gazebo 窗口前先按 Ctrl+C）
- 必要时使用 `killall gzserver`

---

## 进阶用法

### 自定义医院世界

1. 编辑世界文件：

```bash
nano ~/robot/hospital_ws/src/aws-robomaker-hospital-world/world/hospital.world
```

1. 添加自定义模型或修改几何体
2. 使用更新后的世界重新生成地图：

```bash
cd ~/robot
python3 gen_hospital_map.py
```

### 3D 地图生成

生成 3D 点云用于高级导航：

```bash
# 启用 3D 模式
ros2 service call /map_request gazebo_map_creator_interface/srv/MapRequest "{ \
    lowerright_x: 0.0, \
    lowerright_y: 0.0, \
    upperleft_x: 50.0, \
    upperleft_y: 50.0, \
    resolution: 0.05, \
    filename: 'hospital_map', \
    is_3d: true \
}"
```

### 多楼层导航

对于多楼层世界，需按楼层分别生成地图：

```bash
# 第一层
ros2 service call /map_request ... is_3d: false

# 生成第二层地图
# （调用前先移动机器人位置）
```

---

## 依赖参考

### ROS 2 包


| 包名                    | 版本     | 用途             |
| --------------------- | ------ | -------------- |
| rclcpp                | Humble | C++ ROS 客户端    |
| rclpy                 | Humble | Python ROS 客户端 |
| gazebo_ros_pkgs       | Humble | Gazebo-ROS 集成  |
| turtlebot3            | Humble | TurtleBot3 支持  |
| navigation2           | Humble | 导航堆栈           |
| robot_state_publisher | Humble | 机器人状态发布        |
| xacro                 | Humble | URDF 处理        |


### 外部库


| 库名        | 用途      |
| --------- | ------- |
| Boost     | C++ 工具库 |
| PCL       | 点云处理    |
| OctoMap   | 3D 占据地图 |
| Gazebo 11 | 物理仿真引擎  |


---

## 许可证

本项目使用了以下开源组件：

- [AWS RoboMaker Hospital World](https://github.com/aws-robotics/aws-robomaker-hospital-world) - Apache 2.0
- [TurtleBot3](https://github.com/ROBOTIS-GIT/turtlebot3) - Apache 2.0
- [Gazebo](https://gazebosim.org/) - Apache 2.0

---

## 致谢

- AWS RoboMaker 提供的医院仿真环境
- ROBOTIS 提供的 TurtleBot3 平台及相关文档
- 开源机器人软件基金会 (OSRF) 提供的 Gazebo 和 ROS

