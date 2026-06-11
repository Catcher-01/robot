cmake_minimum_required(VERSION 3.8)
project(turtlebot3_gazebo_local)

if(CMAKE_POLICY_VERSION_MAY_BE_NEWER)
  cmake_policy(SET CMP0048 NEW)
endif()

find_package(ament_cmake REQUIRED)

install(DIRECTORY launch rviz urdf worlds models environment
  DESTINATION share/${PROJECT_NAME}/
)

ament_package()
