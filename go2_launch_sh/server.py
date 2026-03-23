#!/usr/bin/env python3
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import subprocess, os
import threading

app = Flask(__name__)
CORS(app)

IMAGE_DIR = "/home/lxc/Target_Detect/img/true"

SCRIPTS = [
    "/home/lxc/go2_launch_sh/1_slam.sh",
    "/home/lxc/go2_launch_sh/2_path_plan.sh",
    "/home/lxc/go2_launch_sh/4_target_detect.sh",
    "/home/lxc/go2_launch_sh/3_path_run.sh",
]

script_status = ["idle"] * len(SCRIPTS)
status_lock = threading.Lock()

def run_script(idx):
    path = SCRIPTS[idx]
    os.chmod(path, 0o755)
    with status_lock:
        script_status[idx] = "running"

    def target():
        subprocess.call(["gnome-terminal", "--", "bash", "-c", f"{path}; read"])
        with status_lock:
            script_status[idx] = "idle"

    threading.Thread(target=target).start()

@app.route("/start/<int:idx>", methods=["POST"])
def start(idx):
    if 1 <= idx <= 4:
        with status_lock:
            if script_status[idx-1] == "running":
                return jsonify({"status":"error","msg":"脚本已在运行"}), 400
        run_script(idx-1)
        return jsonify({"status": "ok", "msg": f"脚本 {idx} 已启动"})
    else:
        return jsonify({"status": "error","msg":"无效脚本编号"}), 400

@app.route("/status")
def status():
    with status_lock:
        return jsonify(script_status)

# --- 修改此路由 ---
@app.route("/images")
def list_images():
    if not os.path.exists(IMAGE_DIR):
        return jsonify([])
    try:
        # 核心改动：使用 os.path.getmtime 作为排序的 key，并设置 reverse=True
        files = sorted(
            [f for f in os.listdir(IMAGE_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))],
            key=lambda f: os.path.getmtime(os.path.join(IMAGE_DIR, f)),
            reverse=True  # 降序排列，最新的在前
        )
        return jsonify(files)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
# --------------------

@app.route("/get_image/<path:filename>")
def get_image(filename):
    return send_from_directory(IMAGE_DIR, filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)