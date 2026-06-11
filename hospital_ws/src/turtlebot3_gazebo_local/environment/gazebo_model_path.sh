# Add local 10m-lidar burger sdf to GAZEBO_MODEL_PATH
ament_prepend_unique_value GAZEBO_MODEL_PATH "$AMENT_CURRENT_PREFIX/share/turtlebot3_gazebo_local/models"
