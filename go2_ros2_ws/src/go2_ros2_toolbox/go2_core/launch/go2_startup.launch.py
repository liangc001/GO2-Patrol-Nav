from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():
    ld = LaunchDescription()

    # 获取包路径
    go2_core_dir = get_package_share_directory('go2_core')
    go2_navigation_dir = get_package_share_directory('go2_navigation')
    go2_slam_dir = get_package_share_directory('go2_slam')
    go2_perception_dir = get_package_share_directory('go2_perception')

    # 设置配置文件路径
    rviz_config_path = os.path.join(go2_core_dir, 'config', 'default.rviz')

    # 1. 启动基础节点
    go2_base_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(go2_core_dir, 'launch', 'go2_base.launch.py')
        ]),
        launch_arguments={
            'video_enable': 'true',
            'image_topic': '/camera/image_raw',
            'tcp_enable': 'true',
            'tcp_host': '127.0.0.1',
            'tcp_port': '5432',
            'target_fps': '30',
        }.items()
    )

    # 2. 启动点云处理节点
    pointcloud_process_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(go2_perception_dir, 'launch', 'go2_pointcloud_process.launch.py')
        ])
    )

    # 3. 启动SLAM工具箱
    slam_toolbox_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(go2_slam_dir, 'launch', 'go2_slamtoolbox.launch.py')
        ])
    )

    # 4. 启动导航系统
    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(go2_navigation_dir, 'launch', 'go2_nav2.launch.py')
        ])
    )

    # 5. 启动可视化工具
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', rviz_config_path],
        output='screen'
    )

    ld.add_action(go2_base_launch)
    ld.add_action(pointcloud_process_launch)
    ld.add_action(slam_toolbox_launch)
    ld.add_action(nav2_launch)
    ld.add_action(rviz_node)

    return ld
