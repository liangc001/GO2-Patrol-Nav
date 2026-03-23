import cv2
import numpy as np
import os                      # ← 新增
import time                    # ← 新增

# ----------------  显示黑窗，保证窗口提前创建  ----------------
height, width = 720, 1280
img = np.zeros((height, width, 3), dtype=np.uint8)
cv2.imshow("Video", img)
cv2.waitKey(1)

import asyncio
import logging
import threading
from queue import Queue
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from aiortc import MediaStreamTrack

logging.basicConfig(level=logging.FATAL)

SAVE_DIR = r'/home/lxc/Target_Detect/img/pred'
os.makedirs(SAVE_DIR, exist_ok=True)
last_save_ts = 0

# ==========================================================
def main():
    frame_queue = Queue()

    conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip="192.168.123.161")

    async def recv_camera_stream(track: MediaStreamTrack):
        while True:
            frame = await track.recv()
            img = frame.to_ndarray(format="bgr24")
            frame_queue.put(img)

    def run_asyncio_loop(loop):
        asyncio.set_event_loop(loop)

        async def setup():
            await conn.connect()
            conn.video.switchVideoChannel(True)
            conn.video.add_track_callback(recv_camera_stream)

        loop.run_until_complete(setup())
        loop.run_forever()

    loop = asyncio.new_event_loop()
    asyncio_thread = threading.Thread(target=run_asyncio_loop, args=(loop,))
    asyncio_thread.start()

    # ----------------  主循环：显示 + 每秒保存  ----------------
    try:
        while True:
            if not frame_queue.empty():
                img = frame_queue.get()

                # 每秒保存一帧
                now = int(time.time())
                global last_save_ts
                if now != last_save_ts:
                    last_save_ts = now
                    cv2.imwrite(os.path.join(SAVE_DIR, f"{now}.jpg"), img)

                cv2.imshow("Video", img)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            else:
                time.sleep(0.01)
    finally:
        cv2.destroyAllWindows()
        loop.call_soon_threadsafe(loop.stop)
        asyncio_thread.join()

# ==========================================================
if __name__ == "__main__":
    main()