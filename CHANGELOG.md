# Change Log

## [0.1.0] - 2025-03-08

### Added
- Initial release of VS Code Timelapse extension
- Screen recording functionality with configurable frame rate
- Pause/Resume capability for recording sessions
- Multi-monitor support
- Configurable capture area
- Status bar integration with recording controls
- Progress indication in status bar
- Extensive logging system for debugging
- Multiple video format support (MP4, AVI)
- Cross-platform compatibility (Windows, macOS, Linux)

### Fixed
- Process Control: Replaced signal-based stopping with file-based approach for better Windows compatibility
- Video Creation: Added multiple codec fallbacks to handle platform-specific availability issues
- Python Detection: Improved interpreter detection with multiple fallback methods
- Error Handling: Added extensive logging and user feedback
- Resource Management: Implemented proper cleanup through `atexit` handlers
- UTF-8 Encoding: Added proper environment variables for Python process
- Temporary Files: Added automatic cleanup of temporary files
- Process Termination: Extended wait time for video creation to prevent timeouts

### Technical Improvements
- Implemented hybrid TypeScript/Python architecture
- Added comprehensive error handling and logging
- Optimized screen capture using `mss` library
- Implemented file-based inter-process communication
- Added support for multiple video codecs
- Improved test infrastructure
- Added extensive documentation
- Optimized package.json scripts
- Updated TypeScript configuration for better compatibility
- Improved development tooling setup

### Configuration
- Added support for customizable:
  - Output directory
  - Frame rate
  - Video FPS
  - Image quality
  - Capture area
  - Multi-monitor settings