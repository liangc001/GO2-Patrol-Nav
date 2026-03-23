from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():
    # 获取slam_toolbox包的路径
    slam_toolbox_dir = get_package_share_directory('slam_toolbox')
    
    # 设置配置文件路径
    slam_toolbox_config = os.path.join(
        get_package_share_directory('go2_slam'),
        'config',
        'mapper_params_online_async.yaml'
    )

    # 包含slam_toolbox的launch文件
    slam_toolbox_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(slam_toolbox_dir, 'launch', 'online_async_launch.py')
        ]),
        launch_arguments={
            'params_file': slam_toolbox_config,
            'use_sim_time': 'false',
        }.items(),
    )

    return LaunchDescription([
        slam_toolbox_launch
    ])