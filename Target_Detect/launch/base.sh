#!/bin/bash

PYTHON=/home/lxc/anaconda3/envs/target_detect/bin/python

# 打开新终端运行第一个脚本
# gnome-terminal -- bash -c "$PYTHON '/home/lxc/Target_Detect/monitor_png.py'; exec bash"

# 打开新终端运行第二个脚本
gnome-terminal -- bash -c "$PYTHON '/home/lxc/Target_Detect/monitor_detect_target.py'; exec bash"

# 打开新终端运行 go2_video_client
# gnome-terminal -- bash -c "~/unitree_sdk2/build/bin/go2_video_client enx0826ae38e743; exec bash"

gnome-terminal -- bash -c "'/home/lxc/anaconda3/envs/video/bin/python' '/home/lxc/go2_ros2_ws/display_video.py'; exec bash"

