#!/bin/bash
cd ~/go2_ros2_ws

# Source the workspace
source install/setup.bash

# Launch the robot
ros2 launch go2_core go2_startup.launch.py