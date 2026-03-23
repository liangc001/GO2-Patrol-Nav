#!/usr/bin/env python3
#-*- coding:utf-8 -*-

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
import cv2
from cv_bridge import CvBridge
import socket
import time

# GStreamer流配置
GSTREAMER_STR = "udpsrc address=230.1.1.1 port=1720 multicast-iface=eth0 ! application/x-rtp, media=video, encoding-name=H264 ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! video/x-raw,width=1280,height=720,format=BGR ! appsink drop=1"

class VideoStreamNode(Node):
    def __init__(self):
        super().__init__('video_stream_node')
        
        # 从参数服务器获取配置
        self.declare_parameter('tcp_enable', False)
        self.declare_parameter('tcp_host', '127.0.0.1')
        self.declare_parameter('tcp_port', 5432)
        self.declare_parameter('target_fps', 30)
        self.declare_parameter('image_topic', '/camera/image_raw')
        
        self.tcp_enable = self.get_parameter('tcp_enable').value
        self.host = self.get_parameter('tcp_host').value
        self.port = self.get_parameter('tcp_port').value
        self.target_fps = self.get_parameter('target_fps').value
        self.image_topic = self.get_parameter('image_topic').value
        
        # 初始化ROS2 Publisher
        self.publisher = self.create_publisher(Image, self.image_topic, 10)
        self.bridge = CvBridge()
        
        # 帧率控制参数
        self.frame_interval = 1.0 / self.target_fps if self.target_fps > 0 else 0
        self.get_logger().info(f'帧率控制帧数: {self.target_fps}')
        self.get_logger().info(f'图像发布话题: {self.image_topic}')

        # 初始化TCP服务器（如果启用）
        self.server_socket = None
        self.client_socket = None
        self.client_address = None
        
        if self.tcp_enable:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
            self.server_socket.settimeout(0.01)  # 设置为10ms超时，非阻塞accept
            self.get_logger().info(f'TCP服务器启动在 {self.host}:{self.port}')
        else:
            self.get_logger().info('TCP转发功能已禁用')

    def wait_for_client(self):
        """非阻塞等待客户端连接"""
        if not self.tcp_enable:
            return False
            
        if self.client_socket is None:
            try:
                self.client_socket, self.client_address = self.server_socket.accept()
                self.get_logger().info(f'客户端已连接: {self.client_address}')
            except socket.timeout:
                # 没有客户端连接，直接返回
                return False
            except Exception as e:
                self.get_logger().error(f'等待客户端连接时出错: {str(e)}')
                return False
        return True

    def send_frame_tcp(self, frame):
        """将图像编码为JPEG并通过TCP发送"""
        if not self.tcp_enable:
            return
            
        try:
            _, jpeg_data = cv2.imencode('.jpg', frame)
            size = len(jpeg_data)
            # 发送4字节长度
            self.client_socket.sendall(size.to_bytes(4, byteorder='big'))
            # 发送图像数据
            self.client_socket.sendall(jpeg_data.tobytes())
        except (socket.error, BrokenPipeError) as e:
            self.get_logger().error(f'TCP发送数据时出错: {str(e)}')
            if self.client_socket:
                try:
                    self.client_socket.close()
                except:
                    pass
            self.client_socket = None
            time.sleep(1)  # 等待一秒后重试

    def publish_ros2_image(self, frame):
        """发布ROS2 Image消息"""
        try:
            ros_image = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
            self.publisher.publish(ros_image)
        except Exception as e:
            self.get_logger().error(f'发布ROS2 Image时出错: {str(e)}')

    def run(self):
        # 打开GStreamer视频流
        cap = cv2.VideoCapture(GSTREAMER_STR, cv2.CAP_GSTREAMER)
        if not cap.isOpened():
            self.get_logger().error('无法打开GStreamer视频流')
            return
        self.get_logger().info('GStreamer视频流已打开')
        # 获取视频流自带帧率
        stream_fps = cap.get(cv2.CAP_PROP_FPS)
        self.get_logger().info(f'视频流自带帧率: {stream_fps}')
        # 帧率统计
        frame_count = 0
        start_time = time.time()
        last_report_time = start_time
        try:
            while rclpy.ok() and cap.isOpened():
                loop_start = time.time()
                ret, frame = cap.read()
                if not ret:
                    self.get_logger().warning('未获取到视频帧，尝试重连...')
                    time.sleep(0.1)
                    continue
                # 1. 发布ROS2 Image
                self.publish_ros2_image(frame)
                rclpy.spin_once(self, timeout_sec=0)  # 保证回调处理
                # 2. TCP发送（如果启用）
                if self.tcp_enable and self.wait_for_client():
                    self.send_frame_tcp(frame)
                # 帧率统计
                frame_count += 1
                now = time.time()
                if now - last_report_time >= 5.0:
                    actual_fps = frame_count / (now - last_report_time)
                    self.get_logger().debug(f'5秒内实际帧率: {actual_fps:.2f}')
                    frame_count = 0
                    last_report_time = now
                # 帧率控制
                elapsed = time.time() - loop_start
                sleep_time = self.frame_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
        finally:
            cap.release()
            if self.tcp_enable:
                if self.client_socket:
                    self.client_socket.close()
                if self.server_socket:
                    self.server_socket.close()
            cv2.destroyAllWindows()
            self.destroy_node()
            rclpy.shutdown()


def main():
    rclpy.init()
    node = VideoStreamNode()
    node.run()

if __name__ == '__main__':
    main() 