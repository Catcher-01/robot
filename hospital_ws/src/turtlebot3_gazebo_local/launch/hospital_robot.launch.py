#!/usr/bin/env python3
#
# Hospital world + TurtleBot3 combined launch
# Starts the AWS hospital simulation environment with a TurtleBot3 robot.
#

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    # ── Packages ──────────────────────────────────────────────────────────────
    pkg_gazebo_ros = get_package_share_directory('gazebo_ros')
    pkg_hospital   = get_package_share_directory('aws_robomaker_hospital_world')
    pkg_turtlebot3 = get_package_share_directory('turtlebot3_gazebo')
    pkg_tb3_local  = get_package_share_directory('turtlebot3_gazebo_local')

    # ── Hospital world ───────────────────────────────────────────────────────
    hospital_world = os.path.join(pkg_hospital, 'worlds', 'hospital.world')

    gzserver_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_gazebo_ros, 'launch', 'gzserver.launch.py')
        ),
        launch_arguments={'world': hospital_world}.items()
    )

    gzclient_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_gazebo_ros, 'launch', 'gzclient.launch.py')
        )
    )

    # ── Robot state publisher (uses system turtlebot3_gazebo URDF) ────────────
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    TURTLEBOT3_MODEL = os.environ['TURTLEBOT3_MODEL']
    urdf_file_name = 'turtlebot3_' + TURTLEBOT3_MODEL + '.urdf'
    urdf_path = os.path.join(pkg_turtlebot3, 'urdf', urdf_file_name)

    with open(urdf_path, 'r') as infp:
        robot_desc = infp.read()

    rsp_cmd = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'robot_description': robot_desc,
        }],
    )

    # ── Spawn TurtleBot3 (uses local 10m-lidar sdf from turtlebot3_gazebo_local) ──
    x_pose = LaunchConfiguration('x_pose', default='0.0')
    y_pose = LaunchConfiguration('y_pose', default='1.0')
    z_pose = '0.2'

    model_folder = 'turtlebot3_' + TURTLEBOT3_MODEL
    # Point to the local sdf (turtlebot3_gazebo_local) which has the 10m lidar
    urdf_sdf_path = os.path.join(pkg_tb3_local, 'models', model_folder, 'model.sdf')

    spawn_cmd = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        arguments=[
            '-entity', TURTLEBOT3_MODEL,
            '-file', urdf_sdf_path,
            '-x', x_pose,
            '-y', y_pose,
            '-z', z_pose,
        ],
        output='screen',
    )

    # ── Declare arguments ────────────────────────────────────────────────────
    ld = LaunchDescription([
        DeclareLaunchArgument(
            'use_sim_time', default_value='true',
            description='Use simulation (Gazebo) clock if true'),
        DeclareLaunchArgument(
            'x_pose', default_value='0.0',
            description='Robot initial X position (m)'),
        DeclareLaunchArgument(
            'y_pose', default_value='1.0',
            description='Robot initial Y position (m)'),
    ])

    ld.add_action(gzserver_cmd)
    ld.add_action(gzclient_cmd)
    ld.add_action(rsp_cmd)
    ld.add_action(spawn_cmd)

    return ld
