#!/usr/bin/env python3
import tkinter as tk
import subprocess
import os

# 四个脚本绝对路径，按你实际位置改
SCRIPTS = [
    "/home/lxc/go2_launch_sh/1_slam.sh",
    "/home/lxc/go2_launch_sh/2_path_plan.sh",
    "/home/lxc/go2_launch_sh/3_path_run.sh",
    "/home/lxc/go2_launch_sh/4_target_detect.sh",
]

LABELS = [
    "1. 启动建图",
    "2. 规划路线",
    "3. 执行路径",
    "4. 启动识别",
]

def run_in_new_terminal(script):
    """在新 gnome-terminal 中执行脚本"""
    # 如果脚本没执行权限先加
    os.chmod(script, 0o755)
    # gnome-terminal 保持窗口不退出
    cmd = [
        "gnome-terminal",
        "--",
        "bash", "-c",
        f"{script}; echo '按回车关闭...'; read"
    ]
    subprocess.Popen(cmd)

root = tk.Tk()
root.title("Go2 脚本启动器")
root.geometry("300x280")

for idx, (label, script) in enumerate(zip(LABELS, SCRIPTS)):
    btn = tk.Button(root, text=label, font=("Arial", 14),
                    command=lambda s=script: run_in_new_terminal(s))
    btn.pack(fill='both', expand=True, padx=20, pady=10)

root.mainloop()