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
                            
                            # Convert to numpy array with explicit bytes order
                            frame = np.array(screenshot, dtype=np.uint8)
                            
                            if IS_MACOS:
                                debug_log(f"Frame shape before conversion: {frame.shape}")
                                debug_log(f"Frame data type: {frame.dtype}")
                            
                            # Ensure we have the correct number of channels
                            if len(frame.shape) == 3 and frame.shape[2] == 4:
                                # Extract BGR channels (ignore alpha)
                                frame = frame[:, :, :3]
                                
                                if IS_MACOS:
                                    debug_log(f"Frame shape after channel extraction: {frame.shape}")
                            
                            # Save frame with quality setting
                            frame_path = os.path.join(self.temp_dir, f'frame_{self.frame_count:06d}.jpg')
                            cv2.imwrite(frame_path, frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
                            
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

def create_video(temp_dir, output_dir, fps):
    """
    Creates video from captured frames.
    Implements multiple codec fallbacks for maximum compatibility.
    Added extensive error handling and progress reporting.
    Bug fix: Added multiple codec attempts to handle codec availability issues across platforms.
    Bug fix: Fixed color space handling to prevent green tint in videos.
    """
    try:
        print("INFO:Starting video creation process...")
        frames = sorted([f for f in os.listdir(temp_dir) if f.startswith('frame_')])
        if not frames:
            print("ERROR:No frames found")
            return

        print(f"INFO:Found {len(frames)} frames")

        # Read first frame to get dimensions
        first_frame_path = os.path.join(temp_dir, frames[0])
        print(f"INFO:Reading first frame from {first_frame_path}")
        first_frame = cv2.imread(first_frame_path)
        
        if first_frame is None:
            print(f"ERROR:Failed to read first frame from {first_frame_path}")
            return
            
        height, width = first_frame.shape[:2]
        print(f"INFO:Video dimensions will be {width}x{height}")

        # Create video file
        output_path = os.path.join(output_dir, 'timelapse.mp4')
        print(f"INFO:Creating video at {output_path}")
        
        # Try different codecs for compatibility
        codecs = [
            ('H264', '.mp4'),  # Try H264 first as it's most reliable
            ('avc1', '.mp4'),  # AVC1 is also good for MP4
            ('XVID', '.avi'),  # XVID is very reliable but creates larger files
            ('MJPG', '.avi'),  # Motion JPEG as fallback
            ('mp4v', '.mp4')   # MP4V as last resort
        ]
        
        out = None
        for codec, ext in codecs:
            try:
                print(f"INFO:Trying codec {codec}")
                current_output = os.path.join(output_dir, f'timelapse{ext}')
                fourcc = cv2.VideoWriter_fourcc(*codec)
                
                # For H264, try to set higher bitrate
                if codec == 'H264':
                    test_out = cv2.VideoWriter(current_output, fourcc, fps, (width, height), True)
                    # Try to set bitrate if possible (not all OpenCV builds support this)
                    try:
                        test_out.set(cv2.VIDEOWRITER_PROP_QUALITY, 100)
                    except:
                        pass
                else:
                    test_out = cv2.VideoWriter(current_output, fourcc, fps, (width, height))
                
                if test_out.isOpened():
                    out = test_out
                    output_path = current_output
                    print(f"INFO:Successfully created video writer with codec {codec}")
                    break
                else:
                    print(f"INFO:Codec {codec} failed")
                    test_out.release()
            except Exception as e:
                print(f"INFO:Error with codec {codec}: {str(e)}")
                continue

        if out is None:
            print("ERROR:Failed to create video with any codec")
            return

        total_frames = len(frames)
        print(f"INFO:Starting to write {total_frames} frames to video")
        
        for i, frame_name in enumerate(frames):
            frame_path = os.path.join(temp_dir, frame_name)
            
            # Read frame
            frame = cv2.imread(frame_path, cv2.IMREAD_UNCHANGED)
            
            if frame is None:
                print(f"ERROR:Failed to read frame {frame_path}")
                continue
            
            if IS_MACOS:
                debug_log(f"Frame shape during video creation: {frame.shape}")
            
            # For certain codecs, ensure proper color handling
            if codec == 'mp4v':
                # MP4V sometimes needs explicit BGR->RGB->BGR conversion
                frame = cv2.cvtColor(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), cv2.COLOR_RGB2BGR)
            
            # Write frame
            out.write(frame)
            
            # Output progress
            progress = int((i + 1) / total_frames * 100)
            print(f"PROGRESS:{progress}")

        out.release()
        print(f"INFO:Video saved to {output_path}")

        # Verify video was created
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            print(f"INFO:Video file created successfully, size: {os.path.getsize(output_path)} bytes")
        else:
            print("ERROR:Video file was not created or is empty")
            return

        print("INFO:Cleaning up temporary files...")
        # Remove temporary files
        for frame in frames:
            try:
                os.remove(os.path.join(temp_dir, frame))
            except Exception as e:
                print(f"WARNING:Failed to remove frame {frame}: {str(e)}")
                
        try:
            os.rmdir(temp_dir)
            print("INFO:Temporary directory removed")
        except Exception as e:
            print(f"WARNING:Failed to remove temp directory: {str(e)}")

    except Exception as e:
        print(f"ERROR:Failed to create video: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--create-video':
        if len(sys.argv) < 5:
            print("ERROR:Missing arguments for video creation")
            print("Usage: python timelapse.py --create-video <frames_dir> <output_path> <fps>")
            sys.exit(1)
        
        frames_dir = sys.argv[2]
        output_path = sys.argv[3]
        fps = float(sys.argv[4])
        
        output_dir = os.path.dirname(output_path)
        create_video(frames_dir, output_dir, fps)
        sys.exit(0)
    
    if len(sys.argv) < 5:
        print("ERROR:Missing required arguments")
        print("Usage: python timelapse.py <output_dir> <frame_rate> <video_fps> <quality> [capture_area] [multi_monitor]")
        sys.exit(1)

    output_dir = sys.argv[1]
    frame_rate = float(sys.argv[2])
    video_fps = float(sys.argv[3])
    quality = int(sys.argv[4])
    
    capture_area = None
    if len(sys.argv) > 5:
        try:
            capture_area = json.loads(sys.argv[5])
        except:
            pass
            
    multi_monitor = False
    if len(sys.argv) > 6:
        multi_monitor = sys.argv[6] == '--multi-monitor'
    
    recorder = TimelapseRecorder(output_dir, frame_rate, video_fps, quality, capture_area, multi_monitor)
    recorder.record()
