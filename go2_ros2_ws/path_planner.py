#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, math, yaml, cv2, numpy as np
from heapq import heappop, heappush

# -------------------- 参数 --------------------
INFLATION_RADIUS = 3
TARGET_PIX       = 900
# --------------------------------------------

# -------------------- Theta* 任意角度规划 --------------------
class ThetaStar:
    def __init__(self, occ_grid, inflation):
        self.grid = occ_grid
        h, w = occ_grid.shape
        self.h, self.w = h, w
        self.inflated = self._inflate(inflation)
        self.moves = [(1,0),(-1,0),(0,1),(-1,1),(1,1),(1,-1),(-1,1),(-1,-1)]
        self.costs = [1,1,1,1, math.sqrt(2), math.sqrt(2), math.sqrt(2), math.sqrt(2)]

    def _inflate(self, r):
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*r+1, 2*r+1))
        occupied = (self.grid < 127).astype(np.uint8)
        inflated = cv2.dilate(occupied, kernel, iterations=2)
        return inflated

    def line_of_sight(self, p1, p2):
        """Bresenham 检查两点之间是否有障碍"""
        x0, y0 = p1
        x1, y1 = p2
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x1 > x0 else -1
        sy = 1 if y1 > y0 else -1
        err = dx - dy
        x, y = x0, y0
        while True:
            if self.inflated[y, x]:
                return False
            if (x, y) == (x1, y1):
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy
        return True

    def plan(self, start, goal):
        sx, sy = int(round(start[0])), int(round(start[1]))
        gx, gy = int(round(goal[0])), int(round(goal[1]))
        if self.inflated[sy, sx] or self.inflated[gy, gx]:
            return None

        open_ = []
        g_score = np.full((self.h, self.w), np.inf)
        parent = {}

        def h(a,b): return math.hypot(a[0]-b[0], a[1]-b[1])

        g_score[sy, sx] = 0
        parent[(sx, sy)] = (sx, sy)
        heappush(open_, (h((sx,sy),(gx,gy)), (sx, sy)))

        while open_:
            _, current = heappop(open_)
            if current == (gx, gy):
                path=[]
                c = current
                while parent[c] != c:
                    path.append(c)
                    c = parent[c]
                path.append((sx, sy))
                return path[::-1]

            x, y = current
            for idx, (dx, dy) in enumerate(self.moves):
                nx, ny = x+dx, y+dy
                if not (0<=nx<self.w and 0<=ny<self.h): continue
                if self.inflated[ny, nx]: continue
                new_g = g_score[y, x] + self.costs[idx]

                if self.line_of_sight(parent[(x,y)], (nx, ny)):
                    px, py = parent[(x,y)]
                    tentative_g = g_score[py, px] + math.hypot(nx-px, ny-py)
                    if tentative_g < g_score[ny, nx]:
                        g_score[ny, nx] = tentative_g
                        parent[(nx, ny)] = parent[(x,y)]
                        heappush(open_, (tentative_g + h((nx, ny), (gx, gy)), (nx, ny)))
                else:
                    if new_g < g_score[ny, nx]:
                        g_score[ny, nx] = new_g
                        parent[(nx, ny)] = (x, y)
                        heappush(open_, (new_g + h((nx, ny), (gx, gy)), (nx, ny)))
        return None

# -------------------- 地图 IO & 坐标转换 --------------------
def load_map(yaml_path):
    with open(yaml_path,'r',encoding='utf-8') as f:
        meta=yaml.safe_load(f)
    img_path=os.path.join(os.path.dirname(yaml_path),meta['image'])
    img=cv2.imread(img_path,cv2.IMREAD_GRAYSCALE)
    if img is None: raise FileNotFoundError(img_path)
    origin=meta.get('origin',[0.,0.,0.])[:2]; res=meta['resolution']
    return img,res,origin,meta

def pixel2world(pt, origin, res, h):
    return [origin[0]+pt[0]*res, origin[1]+(h-pt[1])*res]
def world2pixel(pt, origin, res, h):
    return [int(round((pt[0]-origin[0])/res)), int(round(h-(pt[1]-origin[1])/res))]

# -------------------- 生成“转向-直走”指令 (已修改) --------------------
def generate_robot_commands(waypoints_world, path_pixels, origin, res, h, min_dist=0.05):
    """
    根据Theta*生成的路径和用户定义的航向点，生成机器人动作指令。
    新逻辑: 转向路径方向 -> 直走 -> 到达航向点后转向指定姿态 -> ... 循环
    """
    if not waypoints_world or len(waypoints_world) < 2 or len(path_pixels) < 2:
        return []

    # 将完整像素路径转换为世界坐标
    path_world = [pixel2world(p, origin, res, h) for p in path_pixels]

    # 创建一个从航向点像素坐标到其指定姿态(yaw)的映射
    # 使用元组(tuple)作为字典的键，因为列表(list)是不可哈希的
    waypoint_pixel_coords = [tuple(world2pixel(wp[:2], origin, res, h)) for wp in waypoints_world]
    waypoint_yaw_map = {pixel: yaw for pixel, (_, _, yaw) in zip(waypoint_pixel_coords, waypoints_world)}

    commands = []
    # 机器人初始姿态为第一个航向点的姿态
    current_yaw = waypoints_world[0][2]

    # 遍历生成的路径中的每一段
    for i in range(len(path_world) - 1):
        p1_world = path_world[i]
        p2_world = path_world[i+1]
        
        # --- 动作 1: 转向(turn)至下一路径点的方向 ---
        dx = p2_world[0] - p1_world[0]
        dy = p2_world[1] - p1_world[1]
        distance = math.hypot(dx, dy)
        
        # 忽略过短的路径段
        if distance < min_dist:
            continue
        
        # 计算当前路径段的朝向(yaw)
        travel_yaw = math.atan2(dy, dx)
        
        # 计算需要转动的角度
        turn_angle = travel_yaw - current_yaw
        # 将角度归一化到 [-pi, pi] 范围内
        if turn_angle > math.pi: turn_angle -= 2 * math.pi
        if turn_angle < -math.pi: turn_angle += 2 * math.pi
        
        # 如果转动角度足够大，则添加'turn'指令
        if abs(turn_angle) > 1e-4:
            commands.append(['turn', turn_angle])
            
        # --- 动作 2: 直走(walk)当前路径段 ---
        commands.append(['walk', distance])
        
        # 更新机器人的朝向为当前行进方向
        current_yaw = travel_yaw

        # --- 检查是否到达了一个用户定义的航向点 ---
        # 获取当前路径段终点的像素坐标
        end_of_segment_pixel = tuple(path_pixels[i+1])
        
        # 如果该点是一个航向点 (且不是起点), 则执行特定于该航向点的转向动作
        if end_of_segment_pixel in waypoint_yaw_map and end_of_segment_pixel != waypoint_pixel_coords[0]:
            
            # --- 动作 3: 转向(turn)至航向点预设的姿态(yaw) ---
            waypoint_target_yaw = waypoint_yaw_map[end_of_segment_pixel]
            
            # 计算从当前行进方向转向航向点预设姿态所需的角度
            turn_to_waypoint_yaw_angle = waypoint_target_yaw - current_yaw
            # 角度归一化
            if turn_to_waypoint_yaw_angle > math.pi: turn_to_waypoint_yaw_angle -= 2 * math.pi
            if turn_to_waypoint_yaw_angle < -math.pi: turn_to_waypoint_yaw_angle += 2 * math.pi
            
            # 如果转动角度足够大，则添加'turn'指令
            if abs(turn_to_waypoint_yaw_angle) > 1e-4:
                commands.append(['turn', turn_to_waypoint_yaw_angle])
            
            # 更新机器人的姿态为航向点的预设姿态
            # 这将作为计算下一段"转向路径"动作的起始姿态
            current_yaw = waypoint_target_yaw
            
    return commands

# -------------------- GUI 主类 --------------------
class PathGUI:
    def __init__(self, img, resolution, origin, meta):
        self.img=img; self.res=resolution; self.origin=origin; self.meta=meta
        self.h,self.w=img.shape
        self.vis=cv2.cvtColor(img,cv2.COLOR_GRAY2BGR)
        self.astar=ThetaStar(img,INFLATION_RADIUS)
        inf_mask=self.astar.inflated.astype(bool)
        overlay = self.vis.copy(); overlay[inf_mask] = overlay[inf_mask]*0.3+np.array([0,0,120])*0.7
        self.vis=overlay.astype(np.uint8)
        self.way_px=[]; self.path_px=[]
        scale=TARGET_PIX/max(self.w,self.h)
        self.show_size=(int(self.w*scale), int(self.h*scale))
        self.window='map'
        cv2.namedWindow(self.window)
        cv2.setMouseCallback(self.window,self.on_mouse)
        self.point_radius = max(2, int(self.show_size[0]/400))
        self.arrow_len = max(10, int(self.show_size[0]/120))
        self.arrow_thickness= max(1, int(self.show_size[0]/500))
        self.selecting_orientation=False; self.tmp_point=None; self.tmp_yaw=0.0
        self.redraw()

    def on_mouse(self,event,x,y,flags,param):
        x_orig=int(round(float(x)*(self.w/self.show_size[0])))
        y_orig=int(round(float(y)*(self.h/self.show_size[1])))
        if event==cv2.EVENT_LBUTTONDOWN:
            self.tmp_point=(x_orig,y_orig); self.tmp_yaw=0.0; self.selecting_orientation=True
        elif event==cv2.EVENT_MOUSEMOVE and self.selecting_orientation:
            cx,cy=self.tmp_point
            self.tmp_yaw = math.atan2(cy - y_orig, x_orig - cx)
        elif event==cv2.EVENT_RBUTTONDOWN:
            if self.way_px:
                self.way_px.pop(); print('撤销上一笔'); self.replan()

    def replan(self):
        self.path_px=[]
        if len(self.way_px)<2: self.redraw(); return
        full_px=[]
        for i in range(len(self.way_px)-1):
            seg=self.astar.plan(self.way_px[i][:2], self.way_px[i+1][:2])
            if seg is None:
                print(f'警告：第{i+1}段路径规划失败'); self.redraw(); return
            if i!=0: seg=seg[1:]
            full_px.extend(seg)
        self.path_px=full_px
        print(f'规划完成，共 {len(self.path_px)} 像素路径点'); self.redraw()

    def redraw(self):
        canvas=self.vis.copy()
        if len(self.path_px)>1:
            for i in range(len(self.path_px)-1):
                px1,py1=self.path_px[i]; px2,py2=self.path_px[i+1]
                cv2.line(canvas,(px1,py1),(px2,py2),(0,255,255),1)
        for i,(x,y,yaw) in enumerate(self.way_px):
            color=(0,255,0) if i==0 else (0,0,255) if i==len(self.way_px)-1 else (255,0,0)
            ex=int(x+self.arrow_len*math.cos(yaw)); ey=int(y-self.arrow_len*math.sin(yaw))
            cv2.circle(canvas,(x,y),self.point_radius,color,-1)
            cv2.arrowedLine(canvas,(x,y),(ex,ey),color,self.arrow_thickness,tipLength=0.3)
        if self.selecting_orientation and self.tmp_point is not None:
            x,y=self.tmp_point; ex=int(x+self.arrow_len*math.cos(self.tmp_yaw)); ey=int(y-self.arrow_len*math.sin(self.tmp_yaw))
            cv2.circle(canvas,(x,y),self.point_radius,(0,0,0),-1)
            cv2.arrowedLine(canvas,(x,y),(ex,ey),(0,0,0),self.arrow_thickness,tipLength=0.3)
        show=cv2.resize(canvas,self.show_size,interpolation=cv2.INTER_AREA)
        cv2.imshow(self.window,show)

    def spin(self):
        print('左键：选点并拖动朝向；空格/Enter确认；ESC取消临时点；右键撤销；q保存退出')
        while True:
            k=cv2.waitKey(10)&0xFF
            if k in (ord(' '),13):
                if self.selecting_orientation and self.tmp_point is not None:
                    x,y=self.tmp_point; yaw=self.tmp_yaw
                    self.way_px.append((x,y,yaw))
                    wx,wy=pixel2world((x,y),self.origin,self.res,self.h)
                    print(f'选点 #{len(self.way_px)}  [{wx:.3f}, {wy:.3f}, {math.degrees(yaw):.1f}度]')
                    self.replan(); self.selecting_orientation=False; self.tmp_point=None
            elif k==27:
                if self.selecting_orientation: self.selecting_orientation=False; self.tmp_point=None
            elif k==ord('q'): self.save(); break
            self.redraw()
        cv2.destroyAllWindows()

    def save(self):
        if len(self.way_px)<2: print('无完整路径'); return
        way_world=[pixel2world((x,y),self.origin,self.res,self.h)+[yaw] for x,y,yaw in self.way_px]
        robot_commands=generate_robot_commands(way_world, self.path_px, self.origin, self.res, self.h)
        self.meta['waypoints']=way_world
        self.meta['robot_commands']=robot_commands

        out_yaml = 'commands.yaml'
        with open(out_yaml,'w',encoding='utf-8') as f:
            yaml.dump(self.meta,f,default_flow_style=False,allow_unicode=True)
        print(f'已保存 → {out_yaml}')
        print('机器人指令序列:')
        if not robot_commands: print('  (无指令生成)')
        for cmd,val in robot_commands:
            if cmd=='turn': print(f"  - 动作: {cmd:<5}, 数值: {math.degrees(val):.2f} 度")
            else: print(f"  - 动作: {cmd:<5}, 数值: {val:.3f} 米")

# -------------------- main --------------------
if __name__=='__main__':
    if len(sys.argv)!=2:
        print(f'用法: python {os.path.basename(__file__)} map.yaml'); exit(1)
    img,res,origin,meta=load_map(sys.argv[1])
    gui=PathGUI(img,res,origin,meta)
    gui.spin()