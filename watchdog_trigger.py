from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess
import time
import os

WATCH_FOLDER = r"C:\Users\sendt\Downloads\n8nv2\trigger"
TRIGGER_FILE = "start.txt"
PIPELINE_SCRIPT = r"D:\newprojekt\automationtool\run_pipeline.py"

class TriggerHandler(FileSystemEventHandler):
    def on_created(self, event):
        if os.path.basename(event.src_path) == TRIGGER_FILE:
            print(f"[+] Trigger file detected: {event.src_path}")
            try:
                subprocess.run(["python", PIPELINE_SCRIPT], check=True)
                print("[✓] Script executed successfully")
            except subprocess.CalledProcessError as e:
                print(f"[!] Error: {e}")
            os.remove(event.src_path)
            print("[✓] Trigger file deleted")

if __name__ == "__main__":
    print(f"👀 Watching folder: {WATCH_FOLDER}")
    observer = Observer()
    event_handler = TriggerHandler()
    observer.schedule(event_handler, path=WATCH_FOLDER, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n[✋] Stopped by user.")

    observer.join()
