import cv2
import os

OUTPUT_DIR = "timelapse"
VIDEO_FILE = "timelapse.avi"
VIDEO_FPS = 10  # FPS итогового видео

images = sorted([img for img in os.listdir(OUTPUT_DIR) if img.endswith(".png")])
if not images:
    print("No images found!")
    exit()

frame = cv2.imread(os.path.join(OUTPUT_DIR, images[0]))
height, width, layers = frame.shape
video = cv2.VideoWriter(VIDEO_FILE, cv2.VideoWriter_fourcc(*"XVID"), VIDEO_FPS, (width, height))

for image in images:
    img_path = os.path.join(OUTPUT_DIR, image)
    video.write(cv2.imread(img_path))

video.release()
print(f"Video saved as {VIDEO_FILE}")
