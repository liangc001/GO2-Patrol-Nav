#!/bin/bash
cd ~/go2_ros2_ws
# 模拟执行
/home/lxc/anaconda3/envs/video/bin/python /home/lxc/go2_ros2_ws/path_simulate.py
# 真实执行
/home/lxc/anaconda3/envs/video/bin/python /home/lxc/go2_ros2_ws/path_runner.py