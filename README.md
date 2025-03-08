# VS Code Timelapse

[Русская версия](README_RU.md)

Create beautiful timelapses of your coding sessions in Visual Studio Code. This extension captures your screen at regular intervals and combines the frames into a video, allowing you to showcase your development process or create educational content.

## Features

- 🎥 **Screen Recording**: Capture your entire screen or a specific area
- ⏯️ **Pause/Resume**: Temporarily pause recording when needed
- 🖥️ **Multi-Monitor Support**: Choose which monitor to record
- 🎨 **Quality Settings**: Adjust frame rate and video quality
- 🎬 **Multiple Video Formats**: Supports MP4, AVI with various codecs for maximum compatibility
- 🔄 **Platform Support**: Currently tested only on Windows. While the code includes support for macOS and Linux, it has not been thoroughly tested on these platforms.

## Important Note

This extension has been primarily developed and tested on Windows. While it includes code to support macOS and Linux, these platforms have not been thoroughly tested. Users on non-Windows platforms may encounter issues. I welcome feedback and contributions to improve cross-platform support.

## Requirements

- Python 3.6 or higher
- Required Python packages (automatically installed):
  - `mss` for efficient screen capture
  - `opencv-python` for video creation
  - `numpy` for image processing

For other platforms (macOS, Linux):
- Basic functionality should work, but extensive testing has not been performed
- You may encounter platform-specific issues
- Please report any issues you find to help improve cross-platform support

## Installation

1. Install the extension from VS Code Marketplace
2. Ensure Python is installed and available in your PATH
   - On Windows, both `py` and `python` commands are supported
   - On other platforms, `python3` and `python` commands will be attempted
3. The extension will automatically handle Python package dependencies

## Usage

### Starting a Recording

1. Click the camera icon in the status bar or use the command palette:
   - Command: `Start Timelapse Recording`
   - Default location: `timelapse` folder in your workspace

### During Recording

- **Pause/Resume**: Use the command palette or click the status bar icon
- **Stop Recording**: Use the command palette or click the status bar icon
- Progress is shown in the status bar and output channel

### Configuration

```json
{
    "timelapse.outputDirectory": "timelapse",
    "timelapse.frameRate": 2,
    "timelapse.videoFps": 10,
    "timelapse.quality": 95,
    "timelapse.captureArea": null,
    "timelapse.multiMonitor": false
}
```

- `outputDirectory`: Where to save videos (relative to workspace)
- `frameRate`: How many frames to capture per second (recommended: 1-4 for normal coding, 5-10 for fast-paced sessions)
- `videoFps`: Frame rate of the output video (recommended: 10-30)
- `quality`: JPEG quality for frames (1-100)
- `captureArea`: Specific screen area to capture (optional, format: {"x": 0, "y": 0, "width": 1920, "height": 1080})
- `multiMonitor`: Enable multi-monitor support (Note: thoroughly tested only on Windows)

## Technical Details

### Architecture

The extension uses a hybrid approach:
- TypeScript/Node.js for the VS Code integration
- Python for efficient screen capture and video processing
- File-based communication for reliable cross-platform operation

### Implementation Notes

- Uses `mss` for fast screen capture with minimal CPU usage
- OpenCV for video creation with multiple codec support
- File-based control system for reliable process management
- Extensive error handling and progress reporting
- Automatic cleanup of temporary files

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [mss](https://github.com/BoboTiG/python-mss) for efficient screen capture
- [OpenCV](https://opencv.org/) for video processing
