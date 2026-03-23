import os
import shutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

source_dir = os.path.expanduser("./launch")
target_dir = os.path.expanduser("./img/pred")

os.makedirs(source_dir, exist_ok=True)
os.makedirs(target_dir, exist_ok=True)

class MyHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith('.jpg'):
            self.move_file(event.src_path)

    def on_moved(self, event):
        if event.is_directory:
            return
        if event.dest_path.endswith('.jpg'):
            self.move_file(event.dest_path)

    def move_file(self, src_path):
        filename = os.path.basename(src_path)
        target_path = os.path.join(target_dir, filename)
        try:
            shutil.move(src_path, target_path)
            print(f'Moved: {src_path} -> {target_path}')
        except Exception as e:
            print(f'Failed to move {src_path}: {e}')

def scan_existing_files():
    for filename in os.listdir(source_dir):
        if filename.endswith('.jpg'):
            full_path = os.path.join(source_dir, filename)
            if os.path.isfile(full_path):
                handler.move_file(full_path)

if __name__ == '__main__':
    handler = MyHandler()
    scan_existing_files()

    observer = Observer()
    observer.schedule(handler, path=source_dir, recursive=False)
    observer.start()
    print(f'Starting to monitor {source_dir} for .jpg files...')

    try:
        while True:
            pass
    except KeyboardInterrupt:
        observer.stop()
    observer.join()