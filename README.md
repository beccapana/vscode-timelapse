# VS Code Timelapse

[Русская версия](README_RU.md)

Create beautiful timelapses of your coding sessions in Visual Studio Code. This extension captures your screen at regular intervals and combines the frames into a video, allowing you to showcase your development process or create educational content.

## Features

- 🎥 **Screen Recording**: Capture your entire screen or a specific area
- ⏯️ **Pause/Resume**: Temporarily pause recording when needed
- 🖥️ **Multi-Monitor Support**: Choose which monitor to record
- 🎨 **Quality Settings**: Adjust frame rate and video quality
- 🎬 **Multiple Video Formats**: Supports MP4, AVI with various codecs for maximum compatibility
- 🔄 **Cross-Platform**: Works on Windows, macOS, and Linux

## Requirements

- Python 3.6 or higher
- Required Python packages (automatically installed):
  - `mss` for efficient screen capture
  - `opencv-python` for video creation
  - `numpy` for image processing

## Installation

1. Install the extension from VS Code Marketplace
2. Ensure Python is installed and available in your PATH
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
- `frameRate`: How many frames to capture per second
- `videoFps`: Frame rate of the output video
- `quality`: JPEG quality for frames (1-100)
- `captureArea`: Specific screen area to capture (optional)
- `multiMonitor`: Enable multi-monitor support

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

### Bug Fixes and Improvements

1. **Process Control**: Replaced signal-based stopping with file-based approach for better Windows compatibility
2. **Video Creation**: Added multiple codec fallbacks to handle platform-specific availability
3. **Python Detection**: Improved interpreter detection with multiple fallback methods
4. **Error Handling**: Added extensive logging and user feedback
5. **Resource Management**: Implemented proper cleanup through `atexit` handlers

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
