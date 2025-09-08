"""
DLNA Streamer - A professional Python DLNA/UPnP media streaming application.

This package provides functionality for discovering DLNA MediaRenderer devices,
streaming local media files with optimized HTTP Range support, and controlling
playback via AVTransport and RenderingControl services.

Key modules:
- ssdp: SSDP-based device discovery
- device: UPnP device description parsing
- avtransport: DLNA AVTransport service client
- rendering_control: DLNA RenderingControl service client
- http_server: Optimized HTTP server with Range request support
- format_detector: Media format analysis and optimization recommendations
- gui: Tkinter-based graphical user interface

Example usage:
    from dlna_streamer.ssdp import discover
    from dlna_streamer.device import fetch_description

    devices = discover(timeout=3.0)
    for device in devices:
        desc = fetch_description(device.location)
        print(f"Found: {desc.friendly_name}")
"""

__version__ = "1.0.0"
__author__ = "Sebastian Yde Madsen"
__license__ = "MIT"

# Core functionality exports
from .avtransport import DLNAController
from .device import DeviceDescription, fetch_description
from .format_detector import get_streaming_recommendations, get_subtitle_info
from .http_server import serve_directory
from .rendering_control import RenderingControl
from .ssdp import SSDPDevice, discover

__all__ = [
    "discover",
    "SSDPDevice",
    "fetch_description",
    "DeviceDescription",
    "DLNAController",
    "RenderingControl",
    "serve_directory",
    "get_streaming_recommendations",
    "get_subtitle_info",
]
