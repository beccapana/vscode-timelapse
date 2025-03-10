# Main timelapse recording script that captures screen and creates video
# Uses mss for fast screen capture and OpenCV for video creation

import sys
import os
import json
import time
import signal
import atexit
import platform
import argparse
from datetime import datetime
import mss
import cv2
import numpy as np

# Import window handling libraries based on platform
if platform.system() == 'Windows':
    import win32gui
    import win32con
    import win32api
elif platform.system() == 'Darwin':
    from AppKit import NSWorkspace
else:
    import Xlib.display
    import Xlib.X

# Add debug logging for MacOS
IS_MACOS = platform.system() == 'Darwin'
def debug_log(message):
    print(f"DEBUG:{message}")

def force_print(message):
    """Print message and flush stdout immediately"""
    print(message)
    sys.stdout.flush()

def get_ide_window():
    """Get the IDE window coordinates based on the platform"""
    if platform.system() == 'Windows':
        try:
            # Try to get the foreground window first
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            force_print(f"DEBUG:Active window: '{title}'")
            
            # If the active window is not VS Code, enumerate all windows
            if not any(ide_name in title for ide_name in ['Visual Studio Code', 'VS Code', 'Code']):
                def callback(hwnd, windows):
                    if win32gui.IsWindowVisible(hwnd):
                        title = win32gui.GetWindowText(hwnd)
                        if any(ide_name in title for ide_name in ['Visual Studio Code', 'VS Code', 'Code']):
                            windows.append(hwnd)
                    return True

                windows = []
                win32gui.EnumWindows(callback, windows)
                
                if not windows:
                    force_print("WARNING:No VS Code window found")
                    return None
                    
                force_print(f"DEBUG:Found {len(windows)} VS Code windows")
                hwnd = windows[0]
                title = win32gui.GetWindowText(hwnd)
            
            force_print(f"DEBUG:Using window: '{title}'")
            
            # Get window placement info
            placement = win32gui.GetWindowPlacement(hwnd)
            force_print(f"DEBUG:Window placement: {placement}")
            
            # Check if window is minimized
            if placement[1] == win32con.SW_SHOWMINIMIZED:
                force_print("INFO:Window is minimized, restoring...")
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.5)  # Give window time to restore
            
            # Get window coordinates
            rect = win32gui.GetWindowRect(hwnd)
            force_print(f"DEBUG:Window rect: {rect}")
            
            # Get window styles
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            
            # Check if window is maximized
            is_maximized = style & win32con.WS_MAXIMIZE
            force_print(f"DEBUG:Window is maximized: {bool(is_maximized)}")
            
            # Get DPI for the window
            try:
                import ctypes
                user32 = ctypes.windll.user32
                user32.SetProcessDPIAware()
                dpi = user32.GetDpiForWindow(hwnd) if hasattr(user32, 'GetDpiForWindow') else 96
                dpi_scale = dpi / 96.0
                force_print(f"DEBUG:Window DPI: {dpi} (scale: {dpi_scale})")
            except Exception as e:
                force_print(f"WARNING:Failed to get DPI, using default: {e}")
                dpi_scale = 1.0
            
            # Calculate borders based on window style
            border_width = 0
            title_height = 0
            
            if not is_maximized:
                if style & win32con.WS_BORDER:
                    border_width += int(1 * dpi_scale)
                if style & win32con.WS_THICKFRAME:
                    border_width += int(4 * dpi_scale)
                if style & win32con.WS_CAPTION:
                    title_height += int(24 * dpi_scale)
                if ex_style & win32con.WS_EX_WINDOWEDGE:
                    border_width += int(2 * dpi_scale)
            else:
                # For maximized windows, we need to account for the invisible borders
                border_width = int(8 * dpi_scale)  # Windows 10/11 invisible border
                title_height = int(8 * dpi_scale)  # Top invisible border
            
            force_print(f"DEBUG:Calculated borders - width: {border_width}, title height: {title_height}")
            
            # Calculate client area
            x = rect[0] + border_width
            y = rect[1] + title_height
            width = rect[2] - rect[0] - (border_width * 2)
            height = rect[3] - rect[1] - title_height - border_width
            
            # Ensure coordinates are within screen bounds
            screen_width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            screen_height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            force_print(f"DEBUG:Screen dimensions: {screen_width}x{screen_height}")
            
            # For maximized windows, adjust coordinates to screen bounds
            if is_maximized:
                x = 0
                y = 0
                width = screen_width
                height = screen_height - title_height  # Leave space for title bar
            else:
                x = max(0, min(x, screen_width - 1))
                y = max(0, min(y, screen_height - 1))
                width = max(1, min(width, screen_width - x))
                height = max(1, min(height, screen_height - y))
            
            window_info = {
                'x': x,
                'y': y,
                'width': width,
                'height': height
            }
            force_print(f"DEBUG:Final window info: {window_info}")
            return window_info
            
        except Exception as e:
            force_print(f"WARNING:Error getting window coordinates: {e}")
            import traceback
            force_print(f"DEBUG:Stack trace: {traceback.format_exc()}")
            return None

    elif platform.system() == 'Darwin':
        workspace = NSWorkspace.sharedWorkspace()
        for window in workspace.runningApplications():
            if 'Code' in window.localizedName():
                frame = window.frame()
                return {
                    'x': int(frame.origin.x),
                    'y': int(frame.origin.y),
                    'width': int(frame.size.width),
                    'height': int(frame.size.height)
                }
        return None

    else:  # Linux
        display = Xlib.display.Display()
        root = display.screen().root
        window_ids = root.get_full_property(
            display.intern_atom('_NET_CLIENT_LIST'),
            Xlib.X.AnyPropertyType
        ).value

        for window_id in window_ids:
            window = display.create_resource_object('window', window_id)
            name = window.get_wm_name()
            if name and 'Visual Studio Code' in name:
                geometry = window.get_geometry()
                return {
                    'x': geometry.x,
                    'y': geometry.y,
                    'width': geometry.width,
                    'height': geometry.height
                }
        return None

class TimelapseRecorder:
    """
    Main class responsible for recording timelapses.
    Handles screen capture, frame saving, and video creation.
    Uses a file-based approach for control (stop/pause) to ensure reliability across platforms.
    """
    def __init__(self, output_dir, frame_rate, video_fps, quality, capture_area=None, multi_monitor=False, capture_ide_only=False):
        self.output_dir = output_dir
        self.frame_rate = frame_rate
        self.video_fps = video_fps
        self.quality = quality
        self.capture_area = capture_area
        self.multi_monitor = multi_monitor
        self.capture_ide_only = capture_ide_only
        self.frame_count = 0
        self.should_stop = False
        self.is_paused = False
        self.last_window_update = 0
        self.window_update_interval = 0.5  # Update window position every 0.5 seconds
        
        # If capture_ide_only is True and no specific capture area is set, try to get IDE window
        if self.capture_ide_only and not self.capture_area:
            print("INFO:Attempting to locate VS Code window...")
            self.capture_area = get_ide_window()
            if self.capture_area:
                print(f"INFO:Found VS Code window at {self.capture_area}")
            else:
                print("WARNING:Could not find VS Code window, falling back to full screen capture")
        
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

    def update_window_position(self):
        """Update the window position and size if we're recording only the IDE"""
        if not self.capture_ide_only:
            return
            
        current_time = time.time()
        if current_time - self.last_window_update < self.window_update_interval:
            return
            
        new_area = get_ide_window()
        if new_area:
            if new_area != self.capture_area:
                force_print(f"DEBUG:Window position/size changed: {new_area}")
                self.capture_area = new_area
        else:
            force_print("WARNING:Lost track of VS Code window")
        
        self.last_window_update = current_time

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
        print(f"INFO:Captured {self.frame_count} frames")

    def record(self):
        """
        Main recording loop that captures screen frames at specified intervals.
        Implements pause functionality through both signals and file-based control.
        Uses mss for efficient screen capture.
        """
        try:
            force_print("\nINFO:Starting recording process")
            force_print(f"DEBUG:Initial capture area: {self.capture_area}")
            force_print(f"DEBUG:Multi-monitor mode: {self.multi_monitor}")
            force_print(f"DEBUG:Record only IDE: {self.capture_ide_only}")
            
            # Initialize screen capture
            with mss.mss() as sct:
                force_print("\nDEBUG:MSS Configuration:")
                force_print(f"DEBUG:Available monitors: {json.dumps(sct.monitors, indent=2)}")
                force_print(f"DEBUG:Primary monitor: {json.dumps(sct.monitors[1], indent=2)}")  # monitors[1] is primary
                
                # Get primary monitor bounds
                primary_monitor = sct.monitors[1]
                force_print(f"DEBUG:Primary monitor bounds: {json.dumps(primary_monitor, indent=2)}")
                
                last_capture = 0
                capture_interval = 1.0 / self.frame_rate

                force_print(f"\nINFO:Starting capture with frame rate {self.frame_rate} fps")
                force_print(f"INFO:Saving frames to {self.temp_dir}")

                while not self.should_stop:
                    try:
                        if platform.system() == 'Windows':
                            self.is_paused = self.check_pause_file()
                        
                        if self.is_paused:
                            time.sleep(0.1)
                            continue

                        # Update window position if needed
                        self.update_window_position()
                        
                        current_time = time.time()
                        if current_time - last_capture >= capture_interval:
                            # Set up monitor configuration
                            monitor = primary_monitor if not self.multi_monitor else sct.monitors[0]
                            if self.capture_area:
                                # Convert our coordinates to mss format
                                monitor = {
                                    'left': int(self.capture_area['x']),
                                    'top': int(self.capture_area['y']),
                                    'width': int(self.capture_area['width']),
                                    'height': int(self.capture_area['height']),
                                    'mon': 1,  # Use primary monitor as reference
                                }
                                
                                # Validate capture area
                                if monitor['width'] <= 0 or monitor['height'] <= 0:
                                    force_print(f"WARNING:Invalid capture area dimensions: {monitor}")
                                    continue
                                if monitor['left'] < 0 or monitor['top'] < 0:
                                    force_print(f"WARNING:Invalid capture area position: {monitor}")
                                    continue
                                
                                # Check if the capture area is within the primary monitor bounds
                                if (monitor['left'] + monitor['width'] > primary_monitor['width'] or
                                    monitor['top'] + monitor['height'] > primary_monitor['height']):
                                    force_print("WARNING:Capture area extends beyond primary monitor bounds, adjusting...")
                                    monitor['width'] = min(monitor['width'], primary_monitor['width'] - monitor['left'])
                                    monitor['height'] = min(monitor['height'], primary_monitor['height'] - monitor['top'])

                            try:
                                screenshot = sct.grab(monitor)
                                if self.frame_count == 0:  # Log only for first frame
                                    force_print(f"\nDEBUG:First frame capture:")
                                    force_print(f"DEBUG:Captured frame size: {screenshot.width}x{screenshot.height}")
                                    force_print(f"DEBUG:Monitor used: {json.dumps(monitor, indent=2)}")
                                    force_print(f"DEBUG:Screenshot bounds: left={screenshot.left}, top={screenshot.top}, width={screenshot.width}, height={screenshot.height}")
                            except Exception as e:
                                force_print(f"ERROR:Failed to capture frame: {str(e)}")
                                force_print(f"DEBUG:Monitor config used: {json.dumps(monitor, indent=2)}")
                                continue  # Skip this frame and try again
                            
                            frame = np.array(screenshot, dtype=np.uint8)
                            if self.frame_count == 0:  # Log only for first frame
                                force_print(f"DEBUG:Frame array shape: {frame.shape}")
                            
                            if len(frame.shape) == 3:
                                if frame.shape[2] == 4:
                                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
                                elif frame.shape[2] == 3:
                                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            
                            frame_path = os.path.join(self.temp_dir, f'frame_{self.frame_count:06d}.jpg')
                            cv2.imwrite(frame_path, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, self.quality])
                            
                            self.frame_count += 1
                            last_capture = current_time

                            if self.frame_count % 10 == 0:
                                force_print(f"INFO:Captured {self.frame_count} frames")
                    except Exception as e:
                        force_print(f"ERROR:Frame capture error: {str(e)}")
                        import traceback
                        force_print(f"DEBUG:Stack trace: {traceback.format_exc()}")
                        continue  # Skip this frame and try again

                force_print("\nINFO:Recording stopped")

        except Exception as e:
            force_print(f"ERROR:{str(e)}")
            import traceback
            force_print(f"DEBUG:Stack trace: {traceback.format_exc()}")
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
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(description='VS Code Timelapse Recording Script')
    
    # Add subparsers for different modes
    subparsers = parser.add_subparsers(dest='mode', help='Operation mode')
    
    # Record mode parser
    record_parser = subparsers.add_parser('record', help='Record timelapse')
    record_parser.add_argument('--output-dir', required=True, help='Directory for final video output')
    record_parser.add_argument('--temp-dir', required=True, help='Directory for temporary frame storage')
    record_parser.add_argument('--frame-interval', type=float, default=0.2, help='Interval between frames in seconds')
    record_parser.add_argument('--video-fps', type=int, default=10, help='FPS for output video')
    record_parser.add_argument('--quality', type=int, default=95, help='JPEG quality for frames (1-100)')
    record_parser.add_argument('--capture-area', type=str, help='JSON string defining capture area')
    record_parser.add_argument('--multi-monitor', action='store_true', help='Capture all monitors')
    record_parser.add_argument('--record-only-ide', action='store_true', default=False, help='Record only VS Code window')
    
    # Create video mode parser
    video_parser = subparsers.add_parser('create-video', help='Create video from frames')
    video_parser.add_argument('--frames-dir', required=True, help='Directory containing frame images')
    video_parser.add_argument('--output-path', required=True, help='Path for output video file')
    video_parser.add_argument('--fps', type=int, required=True, help='Frames per second for output video')

    try:
        args = parser.parse_args()
        
        if args.mode == 'record':
            # Parse capture area if provided
            capture_area = None
            if args.capture_area:
                try:
                    capture_area = json.loads(args.capture_area)
                except json.JSONDecodeError:
                    print("ERROR:Invalid capture area format")
                    sys.exit(1)

            recorder = TimelapseRecorder(
                output_dir=args.output_dir,
                frame_rate=1.0 / args.frame_interval,  # Convert interval to rate
                video_fps=args.video_fps,
                quality=args.quality,
                capture_area=capture_area,
                multi_monitor=args.multi_monitor,
                capture_ide_only=args.record_only_ide
            )
            recorder.record()
        elif args.mode == 'create-video':
            success = create_video(args.frames_dir, args.output_path, args.fps)
            sys.exit(0 if success else 1)
        else:
            parser.print_help()
            sys.exit(1)

    except Exception as e:
        print(f"ERROR:{str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
