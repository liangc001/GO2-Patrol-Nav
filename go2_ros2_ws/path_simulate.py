#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, os, math, yaml, cv2, numpy as np

# ---------- 参数 ----------
STEP_TIME = 0.2         # 每一步之间自动播放的延迟（秒），手动按键时无效
ARROW_LEN_RATIO = 0.015 # 机器人姿态箭头长度相对于地图尺寸的比例
# --------------------------

def load_map(yaml_path):
    """加载地图元数据和图像"""
    with open(yaml_path, 'r', encoding='utf-8') as f:
        meta = yaml.safe_load(f)
    img_path = os.path.join(os.path.dirname(yaml_path), meta['image'])
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(img_path)
    origin = meta.get('origin', [0., 0., 0.])[:2]
    res = meta['resolution']
    return img, res, origin, meta

def world2pixel(pt, origin, res, h):
    """将世界坐标转换为像素坐标"""
    return [int(round((pt[0] - origin[0]) / res)),
            int(round(h - (pt[1] - origin[1]) / res))]

def draw_pose(canvas, x, y, yaw, color, arrow_len, thickness=1):
    """在画布上绘制一个带方向的姿态"""
    cv2.circle(canvas, (x, y), 3, color, -1)
    end_x = int(x + arrow_len * math.cos(yaw))
    end_y = int(y - arrow_len * math.sin(yaw))
    cv2.arrowedLine(canvas, (x, y), (end_x, end_y),
                    color, thickness, tipLength=0.3)

def replay(meta, img, res, origin):
    """
    回放并可视化机器人动作指令。
    新版: 可视化每一个'turn'和'walk'动作。
    """
    h, w = img.shape
    waypoints = meta['waypoints']
    cmds = meta['robot_commands']

    # --- 生成包含所有步骤（包括转向）的详细历史记录 ---
    history = []
    x, y, yaw = waypoints[0]
    # 添加初始状态
    history.append({'x': x, 'y': y, 'yaw': yaw, 'cmd': 'start', 'val': 0.0})

    for cmd, val in cmds:
        if cmd == 'turn':
            yaw += val
            # 转向时，位置不变，只有姿态更新
            history.append({'x': x, 'y': y, 'yaw': yaw, 'cmd': cmd, 'val': val})
        elif cmd == 'walk':
            # 行走时，姿态不变，只有位置更新
            x += val * math.cos(yaw)
            y += val * math.sin(yaw)
            history.append({'x': x, 'y': y, 'yaw': yaw, 'cmd': cmd, 'val': val})

    # --- 可视化设置 ---
    vis = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    scale = 900 / max(w, h)
    show_size = (int(w * scale), int(h * scale))
    arrow_len = max(10, int(show_size[0] * ARROW_LEN_RATIO))
    
    idx = 0
    while True:
        canvas = vis.copy()

        # 1. 绘制所有预设的航向点 (waypoints)
        for i, (wx, wy, wyaw) in enumerate(waypoints):
            px, py = world2pixel([wx, wy], origin, res, h)
            color = (0, 255, 0) if i == 0 else (0, 0, 255) if i == len(waypoints) - 1 else (255, 0, 0)
            draw_pose(canvas, px, py, wyaw, color, arrow_len)

        # 2. 绘制已经走过的轨迹
        for i in range(1, idx + 1):
            p_prev = history[i-1]
            p_curr = history[i]
            # 只有'walk'动作才会产生可见的轨迹线
            if p_curr['cmd'] == 'walk':
                px1, py1 = world2pixel([p_prev['x'], p_prev['y']], origin, res, h)
                px2, py2 = world2pixel([p_curr['x'], p_curr['y']], origin, res, h)
                cv2.line(canvas, (px1, py1), (px2, py2), (255, 100, 100), 2)

        # 3. 绘制机器人当前姿态
        current_state = history[idx]
        cx, cy, cyaw = current_state['x'], current_state['y'], current_state['yaw']
        px, py = world2pixel([cx, cy], origin, res, h)
        # 使用醒目的蓝色绘制当前机器人
        draw_pose(canvas, px, py, cyaw, (255, 0, 0), arrow_len, 2)

        # 4. 在屏幕上显示详细信息
        show = cv2.resize(canvas, show_size, interpolation=cv2.INTER_AREA)
        cmd_info = current_state['cmd']
        val_info = current_state['val']
        if cmd_info == 'turn':
            status_text = f"Action: Turn ({math.degrees(val_info):+.1f} deg)"
        elif cmd_info == 'walk':
            status_text = f"Action: Walk ({val_info:.2f} m)"
        else:
            status_text = "Action: Start"
            
        full_info = f"Step {idx}/{len(history)-1} | {status_text} | Pos:({cx:.2f}, {cy:.2f}) Yaw:{math.degrees(cyaw):.1f}"
        cv2.putText(show, full_info, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        cv2.imshow('Replay Simulator', show)

        # 5. 按键控制
        key = cv2.waitKey(int(STEP_TIME * 1000)) & 0xFF
        if key == ord('q'):
            break
        elif key in (ord(' '), ord('d'), 83): # 空格, 'd', 右箭头 -> 下一步
            idx = min(idx + 1, len(history) - 1)
        elif key in (ord('a'), 81): # 'a', 左箭头 -> 上一步
            idx = max(idx - 1, 0)

    cv2.destroyAllWindows()

def main():
    try:
        img, res, origin, meta = load_map('commands.yaml')
        replay(meta, img, res, origin)
    except FileNotFoundError:
        print("\n错误: 未找到 'commands.yaml' 文件。")
        print("请先运行路径规划脚本来生成该文件。")
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == '__main__':
    print("\n--- 机器人动作回放模拟器 ---")
    print("  [空格] 或 [d] 或 [→]: 下一步")
    print("  [a] 或 [←]:          上一步")
    print("  [q]:                 退出")
    print("---------------------------------")
    main()