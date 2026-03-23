import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition

def generate_launch_description():
    ld = LaunchDescription()

    ld.add_action(DeclareLaunchArgument(
        'video_enable',
        default_value='false',
        description='是否启用视频功能'
    ))

    ld.add_action(DeclareLaunchArgument(
        'tcp_enable',
        default_value='false',
        description='是否启用TCP转发功能'
    ))

    ld.add_action(DeclareLaunchArgument(
        'tcp_host',
        default_value='127.0.0.1',
        description='TCP服务器主机地址'
    ))

    ld.add_action(DeclareLaunchArgument(
        'tcp_port',
        default_value='5432',
        description='TCP服务器端口'
    ))

    ld.add_action(DeclareLaunchArgument(
        'target_fps',
        default_value='30',
        description='目标帧率'
    ))

    ld.add_action(DeclareLaunchArgument(
        'image_topic',
        default_value='/camera/image_raw',
        description='图像发布话题'
    ))

    go2_base_node = Node(
        package='go2_core',
        executable='go2_base',
        name='go2_base',
        output='screen'
    )

    video_stream_node = Node(
        package='go2_core',
        executable='video_stream_node.py',
        name='video_stream_node',
        output='screen',
        condition=IfCondition(LaunchConfiguration('video_enable')),
        parameters=[{
            'tcp_enable': LaunchConfiguration('tcp_enable'),
            'tcp_host': LaunchConfiguration('tcp_host'),
            'tcp_port': LaunchConfiguration('tcp_port'),
            'target_fps': LaunchConfiguration('target_fps'),
            'image_topic': LaunchConfiguration('image_topic')
        }]
    )

    ld.add_action(go2_base_node)
    ld.add_action(video_stream_node)

    return ld
