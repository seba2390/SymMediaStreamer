# Changelog

All notable changes to DLNA Streamer will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive test suite
- CI/CD pipeline with GitHub Actions
- Advanced error handling and logging
- Configuration file support
- Plugin system architecture

### Changed
- Improved error messages and user feedback
- Enhanced documentation and examples

### Fixed
- Various bug fixes and stability improvements

## [1.0.0] - 2025-01-08

### Added
- Initial release with CLI and GUI interfaces
- DLNA/UPnP device discovery via SSDP
- Media streaming with HTTP Range request support
- AVTransport service integration for playback control
- RenderingControl service integration for volume/mute
- Subtitle support (external files and embedded tracks)
- Format detection and optimization recommendations
- Performance optimizations (64KB buffers, TCP_NODELAY)
- Professional documentation and examples
- Package installation support (setup.py, pyproject.toml)

### Features
- **Device Discovery**: Intelligent SSDP-based discovery with deduplication
- **Media Streaming**: Optimized HTTP streaming with Range request support
- **Playback Control**: Full AVTransport integration (play, pause, seek, stop)
- **Volume Control**: RenderingControl service integration
- **Subtitle Support**: External subtitle files (SRT, VTT, ASS, SSA) and embedded tracks
- **Format Analysis**: Automatic codec detection and optimization recommendations
- **Performance Optimization**: 64KB buffers, TCP_NODELAY, and DLNA-specific headers
- **Dual Interface**: Both command-line and graphical user interfaces

### Technical Highlights
- **Zero Dependencies**: Uses only Python standard library
- **Network Optimized**: 256KB socket buffers and HTTP keep-alive
- **DLNA Compliant**: Format-specific profiles and protocol optimizations
- **Error Resilient**: Graceful handling of network interruptions

### Supported Formats
- **Video**: MP4, MKV, AVI, MOV (H.264/H.265 recommended)
- **Audio**: AAC, MP3, AC3 (embedded in video containers)
- **Subtitles**: SRT, VTT, SUB, ASS, SSA (external and embedded)

### Documentation
- Comprehensive README with installation and usage instructions
- Professional API documentation with examples
- Troubleshooting guide with common issues and solutions
- Contributing guidelines and code of conduct
- MIT License for open source distribution

[Unreleased]: https://github.com/yourusername/dlna-streamer/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/yourusername/dlna-streamer/releases/tag/v1.0.0
