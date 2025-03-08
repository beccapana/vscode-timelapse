# Main timelapse recording script that captures screen and creates video
# Uses mss for fast screen capture and OpenCV for video creation

import sys
import os
import json
import time
import atexit
from datetime import datetime
import mss
import cv2
import numpy as np

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
        
        # Create directory for temporary frame storage
        self.temp_dir = os.path.join(output_dir, 'temp')
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # File used to control pause functionality
        # Bug fix: Previously used signals which were unreliable on Windows
        self.pause_file = os.path.join(self.temp_dir, '.pause')
        if os.path.exists(self.pause_file):
            os.remove(self.pause_file)

        # File used to signal recording stop
        # Bug fix: Replaced signal-based stopping with file-based approach
        self.stop_file = os.path.join(self.temp_dir, '.stop')
        if os.path.exists(self.stop_file):
            os.remove(self.stop_file)

        # Register cleanup function to ensure proper resource handling
        # Bug fix: Added to ensure video creation even if process terminates unexpectedly
        atexit.register(self.cleanup)

    def cleanup(self):
        """
        Cleanup function that runs on process exit.
        Ensures video is created and temporary files are cleaned up.
        Critical for handling unexpected termination scenarios.
        """
        print("\nINFO:Running cleanup...")
        
        # Remove control files
        if os.path.exists(self.pause_file):
            try:
                os.remove(self.pause_file)
            except:
                pass

        if os.path.exists(self.stop_file):
            try:
                os.remove(self.stop_file)
            except:
                pass
        
        # Create final video if frames were captured
        if self.frame_count > 0:
            print("\nINFO:Creating final video...")
            create_video(self.temp_dir, self.output_dir, self.video_fps)

    def check_stop(self):
        """
        Checks for presence of stop file.
        Part of the file-based control system that replaced signal handling.
        Returns True if recording should stop.
        """
        if os.path.exists(self.stop_file):
            print("\nINFO:Stop file detected")
            return True
        return False

    def record(self):
        """
        Main recording loop that captures screen frames at specified intervals.
        Implements pause functionality through file checking.
        Uses mss for efficient screen capture.
        """
        try:
            # Initialize screen capture
            with mss.mss() as sct:
                monitor = sct.monitors[0] if not self.multi_monitor else None
                if self.capture_area:
                    monitor = self.capture_area

                last_capture = 0
                capture_interval = 1.0 / self.frame_rate

                print(f"INFO:Starting capture with frame rate {self.frame_rate} fps")
                print(f"INFO:Saving frames to {self.temp_dir}")

                while not self.check_stop():
                    # Check for pause state
                    is_paused = os.path.exists(self.pause_file)
                    if is_paused:
                        time.sleep(0.1)  # Small delay while paused to reduce CPU usage
                        continue

                    current_time = time.time()
                    if current_time - last_capture >= capture_interval:
                        # Capture and save frame
                        screenshot = sct.grab(monitor)
                        
                        # Convert to OpenCV format
                        frame = np.array(screenshot)
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                        
                        # Save frame with quality setting
                        frame_path = os.path.join(self.temp_dir, f'frame_{self.frame_count:06d}.jpg')
                        cv2.imwrite(frame_path, frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
                        
                        self.frame_count += 1
                        last_capture = current_time

                        # Progress logging
                        if self.frame_count % 10 == 0:
                            print(f"INFO:Captured {self.frame_count} frames")

            print("\nINFO:Recording stopped")

        except Exception as e:
            print(f"ERROR:{str(e)}")
            sys.exit(1)

def create_video(temp_dir, output_dir, fps):
    """
    Creates video from captured frames.
    Implements multiple codec fallbacks for maximum compatibility.
    Added extensive error handling and progress reporting.
    Bug fix: Added multiple codec attempts to handle codec availability issues across platforms.
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
            ('mp4v', '.mp4'),
            ('avc1', '.mp4'),
            ('H264', '.mp4'),
            ('XVID', '.avi')
        ]
        
        out = None
        for codec, ext in codecs:
            try:
                print(f"INFO:Trying codec {codec}")
                current_output = os.path.join(output_dir, f'timelapse{ext}')
                fourcc = cv2.VideoWriter_fourcc(*codec)
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
            frame = cv2.imread(frame_path)
            
            if frame is None:
                print(f"ERROR:Failed to read frame {frame_path}")
                continue
                
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
    if len(sys.argv) < 5:
        print("ERROR:Missing required arguments")
        print("Usage: python timelapse.py output_dir frame_rate video_fps quality [capture_area] [--multi-monitor]")
        sys.exit(1)

    output_dir = sys.argv[1]
    frame_rate = float(sys.argv[2])
    video_fps = float(sys.argv[3])
    quality = int(sys.argv[4])

    capture_area = None
    multi_monitor = False

    if len(sys.argv) > 5:
        if sys.argv[5] == '--multi-monitor':
            multi_monitor = True
        else:
            try:
                capture_area = json.loads(sys.argv[5])
            except json.JSONDecodeError:
                print("ERROR:Invalid capture area format")
                sys.exit(1)

    if len(sys.argv) > 6 and sys.argv[6] == '--multi-monitor':
        multi_monitor = True

    recorder = TimelapseRecorder(output_dir, frame_rate, video_fps, quality, capture_area, multi_monitor)
    recorder.record()
