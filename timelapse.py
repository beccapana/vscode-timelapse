import cv2
import pyautogui
import time
import os
import sys
import numpy as np
from PIL import Image
import json
import signal
import atexit
import subprocess

def print_info(message):
    """Вывод информационного сообщения в stdout"""
    print(f"INFO:{message}")
    sys.stdout.flush()

def print_error(message):
    """Вывод сообщения об ошибке в stderr"""
    print(f"ERROR:{message}", file=sys.stderr)
    sys.stderr.flush()

# Глобальные переменные для хранения параметров
output_dir = None
video_fps = None
should_stop = False
frame_count = 0

def check_stop_flag():
    """Проверяем наличие файла-флага для остановки"""
    stop_flag_file = os.path.join(output_dir, '.stop')
    if os.path.exists(stop_flag_file):
        try:
            os.remove(stop_flag_file)
        except:
            pass
        return True
    return False

def signal_handler(signum, frame):
    """Обработчик сигнала для корректного завершения"""
    global should_stop
    print_info(f"Received signal {signum}")
    # Создаем файл-флаг для остановки
    try:
        with open(os.path.join(output_dir, '.stop'), 'w') as f:
            f.write('stop')
    except:
        pass
    should_stop = True

def cleanup():
    """Функция очистки, которая будет вызвана при завершении программы"""
    global frame_count
    print_info("Cleanup function called")
    if output_dir and os.path.exists(output_dir) and frame_count > 0:
        create_final_video()

def try_ffmpeg():
    """Проверяем наличие ffmpeg"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True)
        return True
    except:
        return False

def create_video_with_ffmpeg(frames_dir, output_file, fps):
    """Создаем видео с помощью ffmpeg"""
    try:
        input_pattern = os.path.join(frames_dir, '%04d.png')
        output_file = os.path.splitext(output_file)[0] + '.mp4'
        
        command = [
            'ffmpeg', '-y',
            '-framerate', str(fps),
            '-i', input_pattern,
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-preset', 'medium',
            '-crf', '23',
            output_file
        ]
        
        print_info(f"Running ffmpeg command: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode == 0:
            print_info("ffmpeg successfully created video")
            return True
        else:
            print_error(f"ffmpeg error: {result.stderr}")
            return False
    except Exception as e:
        print_error(f"Error running ffmpeg: {str(e)}")
        return False

def create_video_with_opencv(frames_dir, output_file, fps):
    """Создаем видео с помощью OpenCV"""
    frames = sorted([f for f in os.listdir(frames_dir) if f.endswith('.png')])
    if not frames:
        print_error("No frames found to create video")
        return False

    print_info(f"Found {len(frames)} frames")
    
    try:
        # Читаем первый кадр для определения размера
        first_frame = cv2.imread(os.path.join(frames_dir, frames[0]))
        if first_frame is None:
            print_error("Failed to read first frame")
            return False
            
        height, width = first_frame.shape[:2]
        print_info(f"Video dimensions: {width}x{height}")

        # Пробуем разные кодеки
        codecs = [
            ('H264', '.mp4'),
            ('mp4v', '.mp4'),
            ('XVID', '.avi'),
            ('MJPG', '.avi'),
            ('WMV1', '.wmv')
        ]

        success = False
        for codec, ext in codecs:
            try:
                print_info(f"Trying codec: {codec}")
                current_output = os.path.splitext(output_file)[0] + ext
                fourcc = cv2.VideoWriter_fourcc(*codec)
                out = cv2.VideoWriter(current_output, fourcc, fps, (width, height))
                
                if not out.isOpened():
                    print_error(f"Failed to create VideoWriter with codec {codec}")
                    continue

                total_frames = len(frames)
                for i, frame_file in enumerate(frames):
                    frame_path = os.path.join(frames_dir, frame_file)
                    frame = cv2.imread(frame_path)
                    if frame is not None:
                        out.write(frame)
                        progress = int((i + 1) / total_frames * 100)
                        print(f"PROGRESS:{progress}")
                    else:
                        print_error(f"Failed to read frame: {frame_path}")
                        break

                out.release()
                
                if os.path.exists(current_output) and os.path.getsize(current_output) > 0:
                    print_info(f"Successfully created video with codec {codec}")
                    output_file = current_output
                    success = True
                    break
                else:
                    print_error(f"Failed to create video with codec {codec}")
                    
            except Exception as e:
                print_error(f"Error with codec {codec}: {str(e)}")
                continue

        return success
            
    except Exception as e:
        print_error(f"Error in create_video: {str(e)}")
        return False

def create_final_video():
    """Создание финального видео"""
    video_file = os.path.join(output_dir, "timelapse.mp4")
    print_info(f"Creating final video at {video_file}")
    
    try:
        # Сначала пробуем ffmpeg
        if try_ffmpeg():
            print_info("Using ffmpeg to create video")
            if create_video_with_ffmpeg(output_dir, video_file, video_fps):
                print_info(f"Video created successfully with ffmpeg: {video_file}")
                cleanup_png_files()
                return
            else:
                print_info("ffmpeg failed, trying OpenCV")
        
        # Если ffmpeg не доступен или не сработал, используем OpenCV
        if create_video_with_opencv(output_dir, video_file, video_fps):
            print_info(f"Video created successfully with OpenCV: {video_file}")
            cleanup_png_files()
        else:
            print_error("Failed to create video with both ffmpeg and OpenCV")
            sys.exit(1)
    except Exception as e:
        print_error(f"Error creating video: {str(e)}")
        sys.exit(1)

def cleanup_png_files():
    """Удаление PNG файлов после создания видео"""
    try:
        for file in os.listdir(output_dir):
            if file.endswith('.png'):
                try:
                    os.remove(os.path.join(output_dir, file))
                except Exception as e:
                    print_error(f"Failed to remove {file}: {str(e)}")
        print_info("Cleaned up PNG files")
    except Exception as e:
        print_error(f"Error cleaning up PNG files: {str(e)}")

def get_screen_size():
    """Получаем размер экрана"""
    return pyautogui.size()

def capture_screen(quality):
    """Захватываем экран с указанным качеством"""
    screenshot = pyautogui.screenshot()
    frame = np.array(screenshot)
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    return frame

def main():
    global output_dir, video_fps, frame_count, should_stop

    if len(sys.argv) < 4:
        print_error("Usage: python timelapse.py <output_dir> <frame_rate> <video_fps> [quality]")
        sys.exit(1)

    # Регистрируем обработчики сигналов
    try:
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        atexit.register(cleanup)
    except Exception as e:
        print_error(f"Failed to register signal handlers: {str(e)}")

    output_dir = sys.argv[1]
    frame_rate = float(sys.argv[2])
    video_fps = int(sys.argv[3])
    quality = int(sys.argv[4]) if len(sys.argv) > 4 else 95

    # Создаем папку для кадров
    os.makedirs(output_dir, exist_ok=True)

    print_info(f"Starting timelapse recording")
    print_info(f"Output directory: {output_dir}")
    print_info(f"Frame rate: {frame_rate} FPS")
    print_info(f"Video FPS: {video_fps}")
    print_info(f"Quality: {quality}%")

    start_time = time.time()

    try:
        while not should_stop and not check_stop_flag():
            # Захватываем кадр
            frame = capture_screen(quality)
            
            # Сохраняем кадр
            frame_path = os.path.join(output_dir, f"{frame_count:04d}.png")
            cv2.imwrite(frame_path, frame)
            
            # Выводим прогресс
            elapsed_time = time.time() - start_time
            print_info(f"Captured frame {frame_count} at {elapsed_time:.1f}s")
            
            frame_count += 1
            time.sleep(1 / frame_rate)

    except KeyboardInterrupt:
        print_info("Received KeyboardInterrupt")
    except Exception as e:
        print_error(f"Error during recording: {str(e)}")
    finally:
        print_info("Entering finally block")
        if frame_count > 0:
            create_final_video()
        else:
            print_error("No frames were captured")

if __name__ == "__main__":
    main()
