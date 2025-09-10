# DLNA Streamer

A professional Python DLNA/UPnP media streaming application for macOS. Stream local video files to DLNA-compatible devices (Samsung TVs, etc.) with advanced features including subtitle support, format optimization, and real-time playback controls.

## Features

### Core Functionality
- **Device Discovery**: Intelligent SSDP-based discovery with deduplication
- **Media Streaming**: HTTP Range request support with optimized buffering
- **Playback Control**: Full AVTransport integration (play, pause, seek, stop)
- **Volume Control**: RenderingControl service integration for audio management

### Advanced Features
- **Subtitle Support**: External subtitle files (SRT, VTT, ASS, SSA) and embedded tracks
- **Format Analysis**: Automatic codec detection and optimization recommendations
- **Performance Optimization**: 64KB buffers, TCP_NODELAY, and DLNA-specific headers
- **Dual Interface**: Both command-line and graphical user interfaces

### Technical Highlights
- **Zero Dependencies**: Uses only Python standard library
- **Network Optimized**: 256KB socket buffers and HTTP keep-alive
- **DLNA Compliant**: Format-specific profiles and protocol optimizations
- **Error Resilient**: Graceful handling of network interruptions

## Installation

### Prerequisites
- Python 3.8 or higher
- macOS (tested on macOS 10.15+)
- DLNA-compatible device on the same network

### Setup
1. Clone or download the repository
2. Make the launcher scripts executable:
   ```bash
   chmod +x bin/dlna_stream
   chmod +x bin/dlna_gui
   ```
3. Optionally add the repository directory to your PATH

## Quick Start

### Command Line Interface

**Discover available devices:**
```bash
bin/dlna_stream discover --timeout 3
```

**Stream a video file:**
```bash
bin/dlna_stream play "/path/to/video.mp4" --timeout 3
```

### Graphical Interface

**Launch the GUI:**
```bash
bin/dlna_gui
```

The GUI provides:
- Device discovery and selection
- File management with drag-and-drop support
- Real-time playback controls
- Subtitle management
- Volume and mute controls
- Streaming optimization analysis

## Advanced Settings

The GUI exposes an Advanced… dialog (Devices panel) to tune discovery and streaming behavior. These map to the CLI flags shown below.

- Discovery timeout (seconds) [CLI: `--timeout`]
  - Start with 2–3 seconds on stable home networks.
  - Increase to 5–8 seconds if some TVs don’t appear on first refresh or on busy/mesh Wi‑Fi.
  - Decrease to 1–2 seconds if you want faster refreshes and your device list is consistent.

- HTTP server port (0 = auto) [CLI: `--port`]
  - Use `0` (auto/ephemeral) by default to avoid conflicts.
  - Pick a fixed high port (e.g., 8080, 8888, 18080) if your TV caches URLs or reconnects often; fixed ports can improve stability on some renderers.
  - Avoid ports already used by other apps. If a fixed port fails, switch back to auto or choose another high port.

- Optimize before play [Modes: off | ask | auto]
  - off: never optimize; stream the selected file as-is.
  - ask: if the file exceeds the target bitrate or is not MP4/H.264/AAC, you’ll be prompted to optimize.
  - auto: automatically optimize before streaming when recommended.

- Target video bitrate (Mbps)
  - Recommended: 15–20 Mbps for typical Wi‑Fi. Use higher for Ethernet.
  - Used as `-maxrate` (and `-bufsize` = 2×) for ffmpeg when transcoding.

- Optimization strategy
  - smart: prefer fast remux to MP4 when video is already H.264; otherwise transcode to H.264/AAC.
  - remux: copy video stream to MP4 and convert audio to AAC with `+faststart` (no re-encode of video).
  - transcode: re-encode video to H.264 with the target bitrate cap and audio to AAC.

### Optimize file (manual)

The Controls panel includes an “Optimize file…” button. It will propose an ffmpeg command (remux or transcode) based on your settings and run it with a progress indicator, producing a new `<name>_optimized.mp4` file.

Requirements: `ffmpeg` must be installed and available on your PATH.

## Command Reference

### `discover` Command
Discover and list DLNA MediaRenderer devices.

**Options:**
- `--timeout <seconds>`: SSDP discovery timeout (default: 2.0)
- `--verbose`: Display detailed device information

**Example:**
```bash
bin/dlna_stream discover --timeout 5 --verbose
```

### `play` Command
Stream a media file to a selected DLNA device.

**Arguments:**
- `file`: Path to the media file (absolute or relative)

**Options:**
- `--device-index <n>`: Select device by index (skips interactive selection)
- `--timeout <seconds>`: SSDP discovery timeout (default: 2.0)
- `--port <n>`: HTTP server port (default: ephemeral)
- `--verbose`: Enable debug output

**Examples:**
```bash
# Interactive device selection
bin/dlna_stream play "/Users/username/Movies/movie.mp4"

# Direct device selection
bin/dlna_stream play "/Users/username/Movies/movie.mp4" --device-index 0

# Custom port
bin/dlna_stream play "/Users/username/Movies/movie.mp4" --port 8080
```

## Performance Optimizations

### Network Layer
- **64KB streaming buffers** (vs standard 8KB)
- **TCP_NODELAY** for reduced latency
- **256KB socket buffers** for improved throughput
- **HTTP/1.1 keep-alive** connections
- **Threaded HTTP server** to handle concurrent range requests
- **Bounded Range responses** strictly honoring `Content-Range`
- **Zero-copy sendfile** path on supported platforms (macOS/Linux)

### DLNA Protocol
- **Format-specific profiles** for optimal TV compatibility
- **Enhanced contentFeatures.dlna.org** headers
- **Trick mode support** (pause/seek) via protocol flags
- **Range request optimization** for large files

### Media Analysis
- **Automatic format detection** using ffprobe (when available)
- **Codec-aware DLNA profiles** in metadata (uses detected container/codec)
- **Codec compatibility analysis** with optimization suggestions
- **Bitrate recommendations** for network conditions
- **Subtitle track detection** and metadata extraction

## Subtitle Support

### External Subtitle Files
Supported formats: SRT, VTT, SUB, ASS, SSA

**Auto-detection**: Files with matching names (e.g., `movie.mp4` + `movie.srt`)
**Manual selection**: Use "Add Subtitle File" button in GUI

### Embedded Subtitle Tracks
- **Automatic detection** of embedded subtitle streams
- **Language identification** and codec information
- **Default track selection** with manual override
- **Forced subtitle support** for accessibility

## Troubleshooting

### Common Issues

**No devices found:**
- Ensure TV and Mac are on the same subnet
- Disable client isolation on your router
- Allow multicast/UPnP traffic
- Try increasing `--timeout` value

**Playback issues:**
- Check network connectivity (prefer Ethernet or 5GHz Wi-Fi)
- Verify file format compatibility (MP4/H.264 recommended)
- Review optimization recommendations in GUI
- Ensure sufficient network bandwidth

**Port conflicts:**
- The application uses ephemeral ports by default
- If using fixed ports, try different port numbers
- Check for other applications using the same port

**Performance problems:**
- Use the optimization panel in GUI for file analysis
- Consider transcoding problematic files with suggested ffmpeg commands
- Ensure stable network connection
- Close other bandwidth-intensive applications

### Error Messages

**"NSOpenPanel" warning**: Harmless macOS GUI framework message, can be ignored.

**Connection reset errors**: Normal during streaming, handled gracefully by the application.

**DLNA error 500**: Usually indicates unsupported file format or codec. Check optimization recommendations.

## Technical Details

### Architecture
- **SSDP Discovery**: Multicast-based device discovery
- **HTTP Server**: Custom implementation with Range request support
- **SOAP Client**: DLNA service control via AVTransport and RenderingControl
- **GUI Framework**: Tkinter with ttk components for modern appearance

### Supported Formats
- **Video**: MP4, MKV, AVI, MOV (H.264/H.265 recommended)
- **Audio**: AAC, MP3, AC3 (embedded in video containers)
- **Subtitles**: SRT, VTT, SUB, ASS, SSA (external and embedded)

### Network Requirements
- **Multicast support** for device discovery
- **HTTP Range requests** for media streaming
- **UPnP/DLNA protocol** compatibility
- **Stable network connection** (recommended: 10+ Mbps)

## License

This project is provided as-is for educational and personal use. Please ensure compliance with local copyright laws when streaming media content.

## Contributing

Contributions are welcome! Please ensure:
- Code follows Python PEP 8 style guidelines
- New features include appropriate error handling
- Documentation is updated for new functionality
- Tests are added for new features (when test framework is implemented)

## Version History

- **v1.0.0**: Initial release with CLI and GUI interfaces
