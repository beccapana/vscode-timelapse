# Main timelapse recording script that captures screen and creates video
# Uses mss for fast screen capture and OpenCV for video creation

import sys
import os
import json
import time
import signal
import atexit
import platform
from datetime import datetime
import mss
import cv2
import numpy as np

# Add debug logging for MacOS
IS_MACOS = platform.system() == 'Darwin'
def debug_log(message):
    print(f"DEBUG:{message}")

class TimelapseRecorder:
    """
    Main class responsible for recording timelapses.
    Handles screen capture, frame saving, and video creation.
    Uses a file-based approach for control (stop/pause) to ensure reliability across platforms.
    """
    def __init__(self, output_dir, frame_rate, video_fps, quality, capture_area=None, multi_monitor=False):
        self.output_dir = output_dir
        self.frame_rate = frame_rate
        self.video_fps = video_fps
        self.quality = quality
        self.capture_area = capture_area
        self.multi_monitor = multi_monitor
        self.frame_count = 0
        self.should_stop = False
        self.is_paused = False
        
        # Create directory for temporary frame storage
        self.temp_dir = os.path.join(output_dir, 'temp')
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Register signal handlers for stop
        signal.signal(signal.SIGTERM, self.handle_stop)
        signal.signal(signal.SIGINT, self.handle_stop)
        
        # On Unix-like systems, try to use SIGUSR1 for pause
        if platform.system() != 'Windows':
            try:
                signal.signal(signal.SIGUSR1, self.handle_pause)
            except AttributeError:
                print("INFO:SIGUSR1 not available, using file-based pause control")
        
        # Register cleanup function
        atexit.register(self.cleanup)

    def handle_stop(self, signum, frame):
        """Signal handler for stop signals"""
        print("\nINFO:Received stop signal")
        self.should_stop = True

    def handle_pause(self, signum, frame):
        """Signal handler for pause signal"""
        self.is_paused = not self.is_paused
        state = "paused" if self.is_paused else "resumed"
        print(f"\nINFO:Recording {state}")

    def check_pause_file(self):
        """Check for pause file in temp directory"""
        pause_file = os.path.join(self.temp_dir, '.pause')
        return os.path.exists(pause_file)

    def cleanup(self):
        """
        Cleanup function that runs on process exit.
        Ensures video is created and temporary files are cleaned up.
        Critical for handling unexpected termination scenarios.
        """
        print("\nINFO:Running cleanup...")
        
        # Create final video if frames were captured
        if self.frame_count > 0:
            print("\nINFO:Creating final video...")
            create_video(self.temp_dir, self.output_dir, self.video_fps)

    def record(self):
        """
        Main recording loop that captures screen frames at specified intervals.
        Implements pause functionality through both signals and file-based control.
        Uses mss for efficient screen capture.
        """
        try:
            # Initialize screen capture
            with mss.mss() as sct:
                if IS_MACOS:
                    debug_log(f"Available monitors: {sct.monitors}")
                    debug_log(f"Primary monitor: {sct.monitors[0]}")
                    debug_log(f"Using multi_monitor: {self.multi_monitor}")
                    debug_log(f"Capture area: {self.capture_area}")

                monitor = sct.monitors[0] if not self.multi_monitor else None
                if self.capture_area:
                    monitor = self.capture_area

                if IS_MACOS:
                    debug_log(f"Selected monitor configuration: {monitor}")

                last_capture = 0
                capture_interval = 1.0 / self.frame_rate

                print(f"INFO:Starting capture with frame rate {self.frame_rate} fps")
                print(f"INFO:Saving frames to {self.temp_dir}")

                while not self.should_stop:
                    try:
                        # Check both signal-based and file-based pause states
                        if platform.system() == 'Windows':
                            self.is_paused = self.check_pause_file()
                        
                        if self.is_paused:
                            time.sleep(0.1)  # Small delay while paused to reduce CPU usage
                            continue

                        current_time = time.time()
                        if current_time - last_capture >= capture_interval:
                            # Capture and save frame
                            if IS_MACOS:
                                debug_log("Attempting to capture frame...")
                            
                            screenshot = sct.grab(monitor)
                            
                            if IS_MACOS:
                                debug_log(f"Frame captured. Size: {screenshot.width}x{screenshot.height}")
                            
                            # Convert to numpy array and handle color channels
                            frame = np.array(screenshot, dtype=np.uint8)
                            
                            if IS_MACOS:
                                debug_log(f"Frame shape before conversion: {frame.shape}")
                                debug_log(f"Frame data type: {frame.dtype}")
                            
                            # MSS captures in BGRA format, we need RGB for correct colors
                            if len(frame.shape) == 3:
                                if frame.shape[2] == 4:
                                    # Convert BGRA to RGB
                                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
                                elif frame.shape[2] == 3:
                                    # Convert BGR to RGB
                                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            
                            if IS_MACOS:
                                debug_log(f"Frame shape after conversion: {frame.shape}")
                            
                            # Save frame with quality setting
                            frame_path = os.path.join(self.temp_dir, f'frame_{self.frame_count:06d}.jpg')
                            cv2.imwrite(frame_path, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, self.quality])
                            
                            if IS_MACOS:
                                debug_log(f"Frame saved to {frame_path}")
                            
                            self.frame_count += 1
                            last_capture = current_time

                            # Progress logging
                            if self.frame_count % 10 == 0:
                                print(f"INFO:Captured {self.frame_count} frames")
                    except Exception as e:
                        if IS_MACOS:
                            debug_log(f"Error during frame capture: {str(e)}")
                        raise

            print("\nINFO:Recording stopped")

        except Exception as e:
            print(f"ERROR:{str(e)}")
            if IS_MACOS:
                debug_log(f"Stack trace: {sys.exc_info()}")
            sys.exit(1)

def create_video(frames_dir, output_path, fps):
    """Creates video from captured frames using OpenCV"""
    try:
        # Get list of frame files
        frame_files = sorted([f for f in os.listdir(frames_dir) if f.startswith('frame_') and f.endswith('.jpg')])
        if not frame_files:
            print("ERROR:No frames found for video creation")
            return False

        # Get frame dimensions from first frame
        first_frame = cv2.imread(os.path.join(frames_dir, frame_files[0]))
        if first_frame is None:
            print("ERROR:Failed to read first frame")
            return False

        height, width = first_frame.shape[:2]

        # Get preferred codec from arguments, with fallbacks
        preferred_codec = os.environ.get('TIMELAPSE_CODEC', 'H264')
        
        # Try different codecs in order of preference
        codecs = []
        
        # Start with preferred codec
        if preferred_codec in ['H265', 'AV1', 'H264', 'mp4v', 'XVID', 'MJPG']:
            # Special handling for H265 and AV1
            if preferred_codec == 'H265':
                codec_options = [
                    ('hevc', '.mp4'),  # HEVC codec
                    ('hvc1', '.mp4'),  # Alternative HEVC FourCC
                    ('x265', '.mp4')   # x265 implementation
                ]
            elif preferred_codec == 'AV1':
                codec_options = [
                    ('av01', '.mp4'),  # AV1 codec
                    ('aom0', '.mp4')   # Alternative AV1 FourCC
                ]
            else:
                ext = '.mp4' if preferred_codec in ['H264', 'mp4v'] else '.avi'
                codec_options = [(preferred_codec, ext)]
            
            codecs.extend(codec_options)
        
        # Add fallback codecs (excluding the preferred one)
        fallback_codecs = [
            ('H264', '.mp4'),
            ('mp4v', '.mp4'),
            ('XVID', '.avi'),
            ('MJPG', '.avi')
        ]
        
        for codec, ext in fallback_codecs:
            if codec != preferred_codec:
                codecs.append((codec, ext))

        out = None
        final_path = None

        for codec, ext in codecs:
            try:
                fourcc = cv2.VideoWriter_fourcc(*codec)
                test_path = output_path.replace('.mp4', ext)
                
                # Special parameters for modern codecs
                if codec in ['hevc', 'hvc1', 'x265', 'av01', 'aom0']:
                    # Try to use higher quality settings for modern codecs
                    test_writer = cv2.VideoWriter(test_path, fourcc, fps, (width, height), 
                                                params=[
                                                    cv2.VIDEOWRITER_PROP_QUALITY, 100,  # Highest quality
                                                    cv2.VIDEOWRITER_PROP_BITRATE, 8000000  # 8 Mbps
                                                ])
                else:
                    test_writer = cv2.VideoWriter(test_path, fourcc, fps, (width, height))
                
                if test_writer.isOpened():
                    out = test_writer
                    final_path = test_path
                    print(f"INFO:Successfully initialized video writer with codec {codec}")
                    break
                else:
                    test_writer.release()
            except Exception as e:
                print(f"INFO:Codec {codec} failed: {str(e)}")
                continue

        if out is None:
            print("ERROR:Failed to create video writer with any codec")
            return False

        # Write frames to video directly without color space conversion
        total_frames = len(frame_files)
        for i, frame_file in enumerate(frame_files, 1):
            frame = cv2.imread(os.path.join(frames_dir, frame_file))
            if frame is not None:
                # Write frame directly without color conversion
                out.write(frame)
                progress = int((i / total_frames) * 100)
                print(f"PROGRESS:{progress}")

        out.release()
        
        # Verify the video was created
        if os.path.exists(final_path) and os.path.getsize(final_path) > 0:
            print(f"INFO:Video created successfully at {final_path}")
            return True
        else:
            print("ERROR:Video file was not created or is empty")
            return False
            
    except Exception as e:
        print(f"ERROR:Failed to create video: {str(e)}")
        return False

def main():
    """Main function handling command line arguments and program flow"""
    if len(sys.argv) > 1 and sys.argv[1] == '--create-video':
        if len(sys.argv) < 5:
            print("ERROR:Not enough arguments for video creation")
            print("Usage: timelapse.py --create-video <frames_dir> <output_path> <fps>")
            sys.exit(1)
        
        frames_dir = sys.argv[2]
        output_path = sys.argv[3]
        fps = int(sys.argv[4])
        
        success = create_video(frames_dir, output_path, fps)
        sys.exit(0 if success else 1)

    if len(sys.argv) < 5:
        print("ERROR:Not enough arguments")
        print("Usage: timelapse.py <output_dir> <frame_rate> <video_fps> <quality> [--codec CODEC] [capture_area_json] [--multi-monitor]")
        sys.exit(1)

    output_dir = sys.argv[1]
    frame_rate = float(sys.argv[2])
    video_fps = int(sys.argv[3])
    quality = int(sys.argv[4])

    # Initialize variables with default values
    capture_area = None
    multi_monitor = False

    # Parse additional arguments
    i = 5
    while i < len(sys.argv):
        if sys.argv[i] == '--codec' and i + 1 < len(sys.argv):
            os.environ['TIMELAPSE_CODEC'] = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--multi-monitor':
            multi_monitor = True
            i += 1
        else:
            try:
                capture_area = json.loads(sys.argv[i])
                i += 1
            except json.JSONDecodeError:
                print("ERROR:Invalid capture area JSON")
                sys.exit(1)

    recorder = TimelapseRecorder(output_dir, frame_rate, video_fps, quality, capture_area, multi_monitor)
    recorder.record()

if __name__ == '__main__':
    main()
