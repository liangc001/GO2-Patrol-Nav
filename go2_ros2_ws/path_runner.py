#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import logging
import json
import sys
import yaml
import time
import numpy as np
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from go2_webrtc_driver.constants import RTC_TOPIC, SPORT_CMD

# --- 配置参数 ---
WALK_SPEED_MPS = 1.0
TURN_SPEED_RADPS = 1.4
COMMAND_FREQUENCY_HZ = 20
Kp_YAW = 1.5
DISTANCE_TOLERANCE_M = 0.05
ANGLE_TOLERANCE_RAD = 0.05
ACTION_TIMEOUT_S = 20

# --- 日志 ---
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 全局状态 ---
robot_state = {
    "position": np.array([0.0, 0.0, 0.0]),
    "yaw": 0.0,
    "last_update_time": 0.0
}
state_lock = asyncio.Lock()
first_message_received = False

# --- 工具函数 ---
def normalize_angle(angle):
    return (angle + np.pi) % (2 * np.pi) - np.pi

async def send_move_command(conn, vx=0.0, vy=0.0, vyaw=0.0):
    await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["SPORT_MOD"],
        {"api_id": SPORT_CMD["Move"], "parameter": {"x": vx, "y": vy, "z": vyaw}},
    )

async def stop_movement(conn):
    logging.info("发送停止指令")
    await send_move_command(conn, 0, 0, 0)

def print_robot_status(current_pos, current_yaw, target_pos=None, target_yaw=None):
    status = f"位置: ({current_pos[0]:.2f}, {current_pos[1]:.2f})  yaw: {np.degrees(current_yaw):.1f}°"
    if target_pos is not None:
        dist_remain = np.linalg.norm(current_pos[:2] - target_pos[:2])
        status += f"  剩余距离: {dist_remain:.3f} m"
    if target_yaw is not None:
        yaw_remain = np.degrees(normalize_angle(target_yaw - current_yaw))
        status += f"  偏航剩余: {yaw_remain:.1f}°"
    print(status, end="\r")

# --- 数据回调 ---
def odometry_callback(message):
    global robot_state, first_message_received
    try:
        payload = message["data"]
        if not first_message_received:
            logging.info(f"成功收到第一条状态消息, 数据键: {list(payload.keys())}")
            first_message_received = True
        current_yaw = payload['imu_state']['rpy'][2]
        position = payload['position']
        async def update_state():
            async with state_lock:
                robot_state["yaw"] = current_yaw
                robot_state["position"] = np.array(position)
                robot_state["last_update_time"] = time.time()
        asyncio.create_task(update_state())
    except (KeyError, IndexError, TypeError) as e:
        logging.warning(f"解析状态数据失败: {e}")

# --- 控制函数 ---
async def execute_turn_by_angle(conn, target_angle_rad):
    logging.info(f"开始执行旋转: {target_angle_rad:.4f} 弧度")
    start_time = time.time()
    async with state_lock:
        start_yaw = robot_state["yaw"]
    target_yaw = normalize_angle(start_yaw + target_angle_rad)
    while time.time() - start_time < ACTION_TIMEOUT_S:
        async with state_lock:
            current_yaw = robot_state["yaw"]
            current_position = robot_state["position"]
        remaining_angle = normalize_angle(target_yaw - current_yaw)
        print_robot_status(current_position, current_yaw, target_yaw=target_yaw)

        turn_speed = TURN_SPEED_RADPS * np.sign(remaining_angle)

        if abs(remaining_angle) < ANGLE_TOLERANCE_RAD:
            logging.info(f"\n成功到达目标角度. 当前: {current_yaw:.4f}, 目标: {target_yaw:.4f}")
            await stop_movement(conn)
            return True
        await send_move_command(conn, vyaw=turn_speed)
        await asyncio.sleep(1.0 / COMMAND_FREQUENCY_HZ)

    logging.error("\n旋转动作超时!")
    await stop_movement(conn)
    return False

async def execute_walk_by_distance(conn, target_distance_m):
    logging.info(f"开始执行直行: {target_distance_m:.4f} 米")
    start_time = time.time()
    async with state_lock:
        start_position = robot_state["position"].copy()
        target_yaw = robot_state["yaw"]
    while time.time() - start_time < ACTION_TIMEOUT_S:
        async with state_lock:
            current_position = robot_state["position"]
            current_yaw = robot_state["yaw"]
        distance_traveled = np.linalg.norm(current_position[:2] - start_position[:2])
        distance_remaining = abs(target_distance_m) - distance_traveled
        yaw_error = normalize_angle(target_yaw - current_yaw)
        print(f"行走剩余: {distance_remaining:.3f} m, yaw 偏差: {np.degrees(yaw_error):.1f}°", end="\r")

        walk_speed_current = WALK_SPEED_MPS if target_distance_m > 0 else -WALK_SPEED_MPS

        if distance_traveled >= abs(target_distance_m):
            logging.info(f"\n成功到达目标距离. 行走距离: {distance_traveled:.4f} 米")
            await stop_movement(conn)
            return True
        await send_move_command(conn, vx=walk_speed_current, vyaw=Kp_YAW*yaw_error)
        await asyncio.sleep(1.0 / COMMAND_FREQUENCY_HZ)

    logging.error("\n直行动作超时!")
    await stop_movement(conn)
    return False

# --- 主程序 ---
async def main():
    try:
        with open('commands.yaml', 'r') as file:
            robot_commands = yaml.safe_load(file).get('robot_commands', [])
            if not robot_commands:
                logging.error("YAML 文件中没有找到 'robot_commands' 或为空")
                return
    except Exception as e:
        logging.error(f"加载 YAML 文件失败: {e}")
        return
    logging.info("成功加载YAML文件。")

    conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip="192.168.123.161")
    await conn.connect()
    logging.info("已成功连接到机器狗")

    state_topic = RTC_TOPIC["LF_SPORT_MOD_STATE"]
    conn.datachannel.pub_sub.subscribe(state_topic, odometry_callback)
    logging.info(f"已订阅机器人状态主题: {state_topic}")

    logging.info("等待接收第一条状态消息...")
    elapsed = 0
    timeout = 5
    while not first_message_received and elapsed < timeout:
        await asyncio.sleep(0.5)
        elapsed += 0.5
    if not first_message_received:
        logging.error("未能收到机器人状态数据，请检查网络或机器人状态。程序退出。")
        await conn.disconnect()
        return

    # 设置运动模式
    response = await conn.datachannel.pub_sub.publish_request_new(RTC_TOPIC["MOTION_SWITCHER"], {"api_id": 1001})
    if response["data"]["header"]["status"]["code"] == 0:
        data = json.loads(response["data"]["data"])
        if data.get("name") != "normal":
            logging.info("当前非 normal 模式，正在切换...")
            await conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["MOTION_SWITCHER"], {"api_id": 1002, "parameter": {"name": "normal"}}
            )
            await asyncio.sleep(5)

    logging.info("开始基于反馈执行 YAML 指令...")
    try:
        for i, (command, value) in enumerate(robot_commands):
            logging.info(f"\n--- 指令 {i+1}/{len(robot_commands)}: {command} {value:.4f} ---")
            success = False
            if command == 'turn':
                success = await execute_turn_by_angle(conn, value)
            elif command == 'walk':
                success = await execute_walk_by_distance(conn, value)
            if not success:
                logging.error(f"指令 '{command} {value}' 执行失败或超时。终止任务序列。")
                break
            await asyncio.sleep(0.5)
    finally:
        await stop_movement(conn)
        conn.datachannel.pub_sub.unsubscribe(state_topic)
        await conn.disconnect()
        logging.info("\n已断开连接")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        sys.exit(0)
