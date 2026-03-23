import os
import shutil
import time
import torch
import cv2
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

WATCH_DIR    = Path("./img/pred").expanduser()
DETECTED_DIR = Path("./img/true").absolute()
EMPTY_DIR    = Path("./img/false").absolute()
WEIGHTS      = Path("./model/best.pt")
IMG_SIZE     = 640
CONF_THRES   = 0.35
IOU_THRES    = 0.45
DEVICE       = ''

DETECTED_DIR.mkdir(exist_ok=True, parents=True)
EMPTY_DIR.mkdir(exist_ok=True, parents=True)
print("DIR EXIST.")

try:
    model = torch.hub.load('./yolov5', 'custom',
                           source='local', path=WEIGHTS, device=DEVICE)
    model.eval()
    print("YOLOv5 模型加载完成")
except Exception as e:
    print("模型加载失败：", e)
    raise


def process_image(image_path: Path):
    img = cv2.imread(str(image_path))
    if img is None:
        print(f"[WARN] 无法读取图像 {image_path}")
        return

    results = model(img, size=IMG_SIZE)
    df = results.pandas().xyxy[0]  # 检测框 DataFrame
    detected = False

    # 画框：只要检测出目标就画，但仅 package 且置信度足够才算“检测到”
    for _, row in df.iterrows():
        x1, y1, x2, y2, conf, cls = int(row.xmin), int(row.ymin), int(row.xmax), int(row.ymax), row.confidence, row['name']
        label = f"{cls} {conf:.2f}"
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(img, label, (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        if cls == "package" and conf >= CONF_THRES:
            detected = True

    # 根据是否检测到 package 决定保存目录
    if detected:
        out_path = DETECTED_DIR / image_path.name
        print(f"[DETECT] 保存到 {out_path}")
    else:
        out_path = EMPTY_DIR / image_path.name
        print(f"[EMPTY] 保存到 {out_path}")

    cv2.imwrite(str(out_path), img)
    image_path.unlink(missing_ok=True)


# 处理遗留图片
existing_jpgs = list(WATCH_DIR.glob("*.jpg"))
if existing_jpgs:
    print(f"发现 {len(existing_jpgs)} 张遗留图片，直接删除 …")
    for jpg in existing_jpgs:
        jpg.unlink(missing_ok=True)
    print("遗留图片清理完毕，开始实时监控 …")


class ImageHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.jpg'):
            self.handle(event.src_path)

    def on_moved(self, event):
        if not event.is_directory and event.dest_path.endswith('.jpg'):
            self.handle(event.dest_path)

    def handle(self, path: str):
        path = Path(path)
        time.sleep(0.1)
        if path.exists():
            process_image(path)


if __name__ == "__main__":
    handler = ImageHandler()
    observer = Observer()
    observer.schedule(handler, str(WATCH_DIR), recursive=False)
    observer.start()
    print(f"开始监控 {WATCH_DIR} ...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
