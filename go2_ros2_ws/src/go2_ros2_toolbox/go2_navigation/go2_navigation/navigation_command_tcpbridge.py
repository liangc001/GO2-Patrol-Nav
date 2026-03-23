#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
import socket
import json
import threading
import struct
import yaml
import os
from ament_index_python.packages import get_package_share_directory

class Nav2TcpBridge(Node):
    def __init__(self):
        super().__init__('nav2_tcp_bridge')

        # 读取配置文件
        config_path = os.path.join(
            get_package_share_directory('go2_tcp_toolbox'),
            'config',
            'tcp_config.yaml'
        )
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        self.host = config['nav_server']['host']
        self.port = config['nav_server']['port']
        
        # 添加重试相关属性
        self.max_retries = 3  # 最大重试次数
        self.current_goal = None  # 存储当前目标点
        self.retry_count = 0  # 当前重试次数

        self._action_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

        # TCP服务器设置
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(1)

        # 启动TCP服务器线程
        self.tcp_thread = threading.Thread(target=self.tcp_server_loop)
        self.tcp_thread.daemon = True
        self.tcp_thread.start()

        self.get_logger().info(f'Nav2 TCP Bridge节点已启动，监听地址: {self.host}:{self.port}')

    def tcp_server_loop(self):
        while rclpy.ok():
            self.get_logger().info('等待TCP客户端连接...')
            client_socket, addr = self.server_socket.accept()
            self.get_logger().info(f'客户端已连接: {addr}')

            try:
                while True:
                    # 接收数据长度
                    length_data = client_socket.recv(4)
                    if not length_data:
                        break

                    length = struct.unpack('!I', length_data)[0]

                    # 接收JSON数据
                    data = b''
                    while len(data) < length:
                        chunk = client_socket.recv(length - len(data))
                        if not chunk:
                            break
                        data += chunk

                    if not data:
                        break

                    # 解析JSON数据
                    goal_data = json.loads(data.decode())

                    # 创建导航目标
                    goal_msg = NavigateToPose.Goal()
                    goal_msg.pose.header.frame_id = "odom"
                    goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
                    goal_msg.pose.pose.position.x = goal_data['position']['x']
                    goal_msg.pose.pose.position.y = goal_data['position']['y']
                    goal_msg.pose.pose.position.z = goal_data['position']['z']
                    goal_msg.pose.pose.orientation.x = goal_data['orientation']['x']
                    goal_msg.pose.pose.orientation.y = goal_data['orientation']['y']
                    goal_msg.pose.pose.orientation.z = goal_data['orientation']['z']
                    goal_msg.pose.pose.orientation.w = goal_data['orientation']['w']

                    # 重置重试计数
                    self.retry_count = 0
                    self.current_goal = goal_msg

                    self.get_logger().info(
                        f"收到目标点: x={goal_msg.pose.pose.position.x}, y={goal_msg.pose.pose.position.y}"
                    )

                    # 等待action server
                    if not self._action_client.wait_for_server(timeout_sec=5.0):
                        self.get_logger().error('NavigateToPose action server 未启动')
                        continue

                    # 发送导航目标
                    self.send_navigation_goal(goal_msg)

            except Exception as e:
                self.get_logger().error(f'TCP通信错误: {str(e)}')
            finally:
                client_socket.close()
                self.get_logger().info('客户端连接已关闭')

    def send_navigation_goal(self, goal_msg):
        """发送导航目标点"""
        send_goal_future = self._action_client.send_goal_async(
            goal_msg,
            feedback_callback=self.feedback_callback
        )
        send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().info('目标点被拒绝')
            return
        self.get_logger().info('目标点已接受，等待结果...')
        get_result_future = goal_handle.get_result_async()
        get_result_future.add_done_callback(self.get_result_callback)

    def feedback_callback(self, feedback_msg):
        feedback = feedback_msg.feedback
        self.get_logger().info(f'导航中，距离目标点剩余: {feedback.distance_remaining:.2f} 米')

    def get_result_callback(self, future):
        result = future.result().result
        status = future.result().status
        if status == 4:  # SUCCEEDED
            self.get_logger().info('导航成功到达目标点！')
            self.retry_count = 0  # 重置重试计数
        else:
            self.get_logger().info(f'导航失败，状态码: {status}')
            if self.retry_count < self.max_retries and self.current_goal is not None:
                self.retry_count += 1
                self.get_logger().info(f'尝试重新发送目标点，第 {self.retry_count} 次重试')
                self.send_navigation_goal(self.current_goal)
            else:
                self.get_logger().error(f'导航失败，已达到最大重试次数 {self.max_retries}')
                self.retry_count = 0
                self.current_goal = None

def main(args=None):
    rclpy.init(args=args)
    node = Nav2TcpBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()