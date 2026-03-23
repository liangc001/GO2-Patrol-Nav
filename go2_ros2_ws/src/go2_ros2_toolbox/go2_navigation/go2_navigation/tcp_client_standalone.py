 #!/usr/bin/env python3
import socket
import json
import struct
import time
import yaml
import os

class TcpClient:
    def __init__(self, config_path=None):
        # 如果没有提供配置文件路径，使用默认路径
        if config_path is None:
            # 获取当前脚本所在目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # 配置文件路径为脚本目录的上一级目录下的config文件夹
            config_path = os.path.join(os.path.dirname(current_dir), 'config', 'tcp_config.yaml')
        
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            self.host = config['nav_server']['host']
            self.port = config['nav_server']['port']
            self.socket = None
            self.connected = False
        except Exception as e:
            print(f'读取配置文件失败: {str(e)}')
            # 使用默认配置
            self.host = '127.0.0.1'
            self.port = 5432
            self.socket = None
            self.connected = False
        
    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            print(f'已连接到服务器 {self.host}:{self.port}')
        except Exception as e:
            print(f'连接失败: {str(e)}')
            print(f'host: {self.host}')
            print(f'port: {self.port}')
            self.connected = False
            
    def send_goal(self, goal_data):
        if not self.connected:
            print('未连接到服务器')
            return False
            
        try:
            # 将目标数据转换为JSON
            data = json.dumps(goal_data).encode()
            length = struct.pack('!I', len(data))
            
            # 发送数据
            self.socket.sendall(length + data)
            return True
            
        except Exception as e:
            print(f'发送数据失败: {str(e)}')
            return False
            
    def close(self):
        if self.socket:
            self.socket.close()
            self.connected = False
            print('连接已关闭')

def main():
    # 创建TCP客户端，可以指定配置文件路径
    # client = TcpClient('/path/to/your/config.yaml')  # 使用自定义配置文件
    client = TcpClient()  # 使用默认配置文件
    
    # 连接到服务器
    client.connect()
    
    if not client.connected:
        return
        
    try:
        while True:
            # 示例：发送目标
            goal_data = {
                'position': {
                    'x': -6.0,
                    'y': -6.0,
                    'z': 0.0
                },
                'orientation': {
                    'x': 0.0,
                    'y': 0.0,
                    'z': 0.0,
                    'w': 1.0
                }
            }
            
            if client.send_goal(goal_data):
                print('目标已发送')
                
            time.sleep(1)  # 避免过于频繁的通信
            
    except KeyboardInterrupt:
        print('\n程序终止')
    finally:
        client.close()
    
if __name__ == '__main__':
    main()