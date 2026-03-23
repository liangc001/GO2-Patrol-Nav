# GO2-Patrol-Nav 部署指南

本文档提供详细的部署步骤和故障排查指南。

## 目录
1. [硬件准备](#硬件准备)
2. [软件环境](#软件环境)
3. [网络配置](#网络配置)
4. [项目部署](#项目部署)
5. [功能验证](#功能验证)
6. [生产部署](#生产部署)
7. [故障排查](#故障排查)

---

## 硬件准备

### 必需硬件
- [ ] Unitree Go2 机器人 (Air/Pro/EDU 版本)
- [ ] 控制电脑 (Ubuntu 20.04)
- [ ] 路由器 (支持WiFi)
- [ ] 网线 (推荐用于控制电脑)

### 可选硬件
- [ ] 激光雷达 (用于更好的SLAM效果)
- [ ] 外置摄像头
- [ ] NVIDIA Jetson (用于边缘计算)

---

## 软件环境

### 1. 安装ROS2

**Ubuntu 20.04 + ROS2 Foxy**

```bash
# 设置软件源
sudo apt update && sudo apt install -y curl gnupg lsb-release
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu focal main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# 安装ROS2 Foxy
sudo apt update
sudo apt install -y ros-foxy-desktop ros-foxy-ros-base

# 设置环境
echo "source /opt/ros/foxy/setup.bash" >> ~/.bashrc
source ~/.bashrc

# 安装rosdep
sudo apt install -y python3-rosdep
sudo rosdep init
rosdep update
```

> **⚠️ 注意**: 本项目**仅支持 Ubuntu 20.04 + ROS2 Foxy**，请勿在 Ubuntu 22.04 或其他版本上尝试安装。

### 2. 安装colcon构建工具

```bash
sudo apt update
sudo apt install -y python3-colcon-common-extensions python3-vcstool
```

### 3. 检查Python版本

```bash
# Ubuntu 20.04 自带 Python 3.8
python3 --version  # 应显示 Python 3.8.x

# 如果安装了多个Python版本，确保使用 Python 3.8
sudo update-alternatives --config python3
```

### 3. 安装Python依赖

```bash
# 创建Python虚拟环境 (推荐)
python3 -m venv ~/go2_env
source ~/go2_env/bin/activate

# 基础依赖
pip install torch torchvision opencv-python-headless numpy scipy pyyaml

# ROS2 Python接口
pip install rclpy

# WebRTC相关
pip install aiortc aiohttp

# 监控和日志
pip install watchdog
```

### 4. 安装系统依赖

```bash
sudo apt install -y \
    libopencv-dev \
    python3-opencv \
    cmake \
    build-essential \
    git \
    wget
```

---

## 网络配置

### 1. 机器人网络设置

**Go2 机器人默认配置：**
- IP: `192.168.123.161`
- 端口: `8080` (WebRTC)

**修改机器人IP (可选):**
1. 连接机器人热点 `Go2-XXXX`
2. 访问 `http://192.168.12.1` 进入管理界面
3. 在网络设置中修改IP

### 2. 控制电脑网络配置

**静态IP设置：**
```bash
# 编辑网络配置
sudo nano /etc/netplan/00-installer-config.yaml
```

```yaml
network:
  version: 2
  ethernets:
    eth0:
      dhcp4: no
      addresses:
        - 192.168.123.10/24
      gateway4: 192.168.123.1
      nameservers:
        addresses: [8.8.8.8, 8.8.4.4]
```

```bash
# 应用配置
sudo netplan apply
```

### 3. 网络连通性测试

```bash
# 测试与机器人连接
ping 192.168.123.161

# 测试WebRTC端口
telnet 192.168.123.161 8080

# 查看ROS2话题 (需在ROS2环境)
ros2 topic list
```

---

## 项目部署

### 1. 克隆项目

```bash
# 选择部署目录
cd ~
git clone https://github.com/你的用户名/GO2-Patrol-Nav.git
cd GO2-Patrol-Nav
```

### 2. 修改配置文件

**A. 修改启动脚本路径**

编辑所有 `.sh` 文件，替换路径：

```bash
# 一键替换 (在项目根目录执行)
PROJECT_PATH=$(pwd)
find go2_launch_sh -name "*.sh" -exec sed -i "s|/home/lxc/go2_ros2_ws|$PROJECT_PATH/go2_ros2_ws|g" {} \;
find go2_launch_sh -name "*.sh" -exec sed -i "s|~/go2_ros2_ws|$PROJECT_PATH/go2_ros2_ws|g" {} \;
```

**B. 修改Python解释器路径**

如果你有特定的Python环境：
```bash
# 查看当前Python路径
which python3

# 替换脚本中的Python路径
PYTHON_PATH=$(which python3)
find go2_launch_sh -name "*.sh" -exec sed -i "s|/home/lxc/anaconda3/envs/video/bin/python|$PYTHON_PATH|g" {} \;
```

**C. 修改机器人IP**

```bash
# 替换为你的机器人IP
ROBOT_IP="192.168.123.161"
sed -i "s/ip=\"192.168.123.161\"/ip=\"$ROBOT_IP\"/g" go2_ros2_ws/path_runner.py
```

**D. 创建环境配置文件**

创建 `.env` 文件：
```bash
cat > .env << EOF
# GO2-Patrol-Nav 环境配置
PROJECT_PATH=$PROJECT_PATH
PYTHON_PATH=$PYTHON_PATH
ROBOT_IP=$ROBOT_IP
ROS_DISTRO=foxy
EOF
```

### 3. 编译ROS2工作空间

```bash
cd go2_ros2_ws

# 安装依赖
rosdep install --from-paths src --ignore-src -r -y --skip-keys="cyclonedds"

# 编译
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release

# 检查编译结果
if [ $? -eq 0 ]; then
    echo "✅ 编译成功"
else
    echo "❌ 编译失败，检查错误信息"
    exit 1
fi

# Source环境
source install/setup.bash
```

### 4. 创建工作目录

```bash
# 创建必要的目录
mkdir -p Target_Detect/img/{pred,true,false}
mkdir -p go2_ros2_ws/maps
mkdir -p logs
```

---

## 功能验证

### 1. 基础连接测试

```bash
# 1. 测试ROS2环境
ros2 --version

# 2. 测试Python环境
python3 --version
python3 -c "import rclpy; print('ROS2 Python OK')"

# 3. 测试OpenCV
python3 -c "import cv2; print(f'OpenCV version: {cv2.__version__}')"

# 4. 测试PyTorch
python3 -c "import torch; print(f'PyTorch version: {torch.__version__}')"
```

### 2. 机器人连接测试

```bash
cd go2_ros2_ws
source install/setup.bash

# 测试连接 (仅测试，不执行)
python3 -c "
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
import asyncio

async def test():
    conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip='192.168.123.161')
    await conn.connect()
    print('✅ 机器人连接成功')
    await conn.disconnect()

asyncio.run(test())
"
```

### 3. SLAM测试

```bash
# 启动SLAM (终端1)
./go2_launch_sh/1_slam.sh

# 在RViz中查看 (终端2)
rviz2

# 检查话题
ros2 topic echo /map --once
ros2 topic list | grep slam
```

### 4. 路径规划测试

```bash
# 创建测试地图
cd go2_ros2_ws

# 如果没有真实地图，创建空白地图进行测试
cat > test_map.yaml << EOF
image: test_map.pgm
resolution: 0.05
origin: [0.0, 0.0, 0.0]
occupied_thresh: 0.65
free_thresh: 0.25
negate: 0
EOF

# 创建空白地图图像
python3 << 'PYEOF'
import numpy as np
import cv2
# 创建100x100的空白地图 (白色=自由空间)
img = np.ones((100, 100), dtype=np.uint8) * 255
cv2.imwrite('test_map.pgm', img)
print('测试地图创建完成')
PYEOF

# 测试路径规划
python3 path_planner.py test_map.yaml
```

### 5. 目标检测测试

```bash
cd Target_Detect

# 检查模型文件
ls -la model/best.pt

# 如果没有模型，下载示例模型或训练
# 测试YOLOv5加载
python3 << 'PYEOF'
import torch
try:
    model = torch.hub.load('./yolov5', 'custom', source='local', path='./model/best.pt')
    print('✅ 模型加载成功')
except Exception as e:
    print(f'❌ 模型加载失败: {e}')
PYEOF

# 创建测试图片目录
mkdir -p img/pred img/true img/false

# 启动监控 (保持运行)
python3 monitor_detect_target.py
```

---

## 生产部署

### 1. 系统服务配置

创建系统服务实现开机自启动：

```bash
# 创建服务文件
sudo tee /etc/systemd/system/go2-slam.service << 'EOF'
[Unit]
Description=GO2 SLAM Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/path/to/GO2-Patrol-Nav/go2_ros2_ws
Environment="HOME=/home/$USER"
ExecStart=/bin/bash -c 'source /opt/ros/foxy/setup.bash && source install/setup.bash && ros2 launch go2_slam go2_slamtoolbox.launch.py'
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 启用服务
sudo systemctl daemon-reload
sudo systemctl enable go2-slam.service
sudo systemctl start go2-slam.service

# 查看状态
sudo systemctl status go2-slam.service
```

### 2. 日志管理

```bash
# 配置日志轮转
sudo tee /etc/logrotate.d/go2-patrol-nav << 'EOF'
/path/to/GO2-Patrol-Nav/logs/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    create 0644 $USER $USER
}
EOF
```

### 3. 监控脚本

创建健康检查脚本：

```bash
cat > health_check.sh << 'EOF'
#!/bin/bash
# 健康检查脚本

# 检查ROS2进程
if ! pgrep -f "ros2" > /dev/null; then
    echo "$(date): ROS2进程未运行" >> logs/health.log
    # 发送告警 (邮件/钉钉/Slack)
fi

# 检查机器人连接
if ! ping -c 1 192.168.123.161 > /dev/null 2>&1; then
    echo "$(date): 机器人连接中断" >> logs/health.log
fi

# 检查磁盘空间
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 80 ]; then
    echo "$(date): 磁盘空间不足: ${DISK_USAGE}%" >> logs/health.log
fi
EOF

chmod +x health_check.sh

# 添加定时任务
echo "*/5 * * * * /path/to/GO2-Patrol-Nav/health_check.sh" | crontab -
```

---

## 故障排查

### 常见问题速查表

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| 编译失败 | 依赖缺失 | `rosdep install --from-paths src --ignore-src -r -y` |
| 找不到包 | 未source | `source install/setup.bash` |
| 连接超时 | IP错误 | 检查并修改path_runner.py中的IP |
| 模型加载失败 | 文件不存在 | 检查model/best.pt是否存在 |
| 摄像头无图像 | 设备未识别 | `ls /dev/video*` 检查设备 |
| SLAM不更新 | 无里程计数据 | `ros2 topic echo /odom` 检查 |
| 路径执行偏差大 | 坐标系不匹配 | 检查map.yaml的origin和resolution |

### 调试模式

```bash
# 启用详细日志
export RCUTILS_LOGGING_SEVERITY=DEBUG

# 记录所有话题
ros2 bag record -a -o logs/debug.bag

# Python调试
python3 -m pdb path_runner.py
```

### 联系支持

如果问题无法解决：
1. 查看项目 [Issues](https://github.com/你的用户名/GO2-Patrol-Nav/issues)
2. 提交新Issue，附带：
   - 操作系统版本
   - ROS2版本
   - 错误日志
   - 复现步骤

---

## Ubuntu 20.04 特定说明

> **⚠️ 重要提醒**: 本项目**仅支持 Ubuntu 20.04 + ROS2 Foxy**，请勿在其他系统版本上使用。

### 环境特点

本项目在 **ROS2 Foxy** (Ubuntu 20.04) 上开发和测试，主要环境特点：

| 组件 | 版本/说明 |
|------|----------|
| 操作系统 | Ubuntu 20.04 LTS |
| ROS2 | Foxy |
| Python | 3.8 (系统自带) |
| Nav2 | 2.1.x |
| 状态 | 稳定运行 |

### 已知问题与解决

**1. Python 3.8 兼容性**
```bash
# Ubuntu 20.04 自带 Python 3.8，确保使用系统Python
which python3  # 应显示 /usr/bin/python3
python3 --version  # 应显示 Python 3.8.x
```

**2. PyTorch 版本选择**
```bash
# Ubuntu 20.04 推荐使用 PyTorch 1.9+ CPU版本
pip install torch==1.12.1 torchvision==0.13.1 --index-url https://download.pytorch.org/whl/cpu

# 或使用CUDA 11.3 (如果显卡支持)
pip install torch==1.12.1 torchvision==0.13.1 --index-url https://download.pytorch.org/whl/cu113
```

**3. OpenCV 版本**
```bash
# Ubuntu 20.04 仓库中的OpenCV版本较旧，建议编译安装或使用pip
pip install opencv-python==4.5.5.64
```

**4. 网络配置工具**
```bash
# Ubuntu 20.04 默认使用 ifupdown，但 netplan 也可用
# 推荐使用 netplan 进行网络配置
sudo apt install -y netplan.io
```

### Foxy 环境变量

确保正确设置 Foxy 环境：
```bash
# 添加到 ~/.bashrc
echo "source /opt/ros/foxy/setup.bash" >> ~/.bashrc

# 如果同时安装了多个ROS2版本，使用以下命令切换
source /opt/ros/foxy/setup.bash
```

---

## 更新维护

### 更新项目

```bash
cd GO2-Patrol-Nav
git pull

# 重新编译
cd go2_ros2_ws
rm -rf build install log
colcon build --symlink-install
```

### 备份配置

```bash
# 备份重要文件
tar -czf backup_$(date +%Y%m%d).tar.gz \
    go2_ros2_ws/commands.yaml \
    go2_ros2_ws/*.yaml \
    Target_Detect/model/ \
    .env
```

---

**文档版本**: 1.0
**最后更新**: 2026-03-23
