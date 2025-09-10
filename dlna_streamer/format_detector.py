"""
Media format detection and optimization analysis for DLNA streaming.

This module provides functionality for analyzing media files to determine
their format, codec, bitrate, and subtitle tracks. It also provides
optimization recommendations for better DLNA streaming performance.

Key components:
- detect_format_info(): Analyze file format, codec, and bitrate
- get_streaming_recommendations(): Get optimization recommendations
- get_subtitle_info(): Detect embedded and external subtitle tracks
- suggest_optimization_command(): Generate ffmpeg optimization commands

Example usage:
    from dlna_streamer.format_detector import get_streaming_recommendations

    recommendations = get_streaming_recommendations("/path/to/video.mp4")
    if not recommendations["is_optimal"]:
        print("Optimization suggestions:", recommendations["suggestions"])
"""

import os
import subprocess
from typing import Optional, Tuple


def detect_format_info(file_path: str) -> Tuple[str, Optional[str], Optional[int]]:
    """Detect media file format, codec, and bitrate information.

    Analyzes a media file to extract format information that can be used
    for optimization recommendations. Uses ffprobe when available for
    detailed analysis, falls back to file extension analysis.

    Args:
        file_path: Path to the media file to analyze

    Returns:
        Tuple containing:
        - container_format (str): Container format (e.g., 'mp4', 'matroska')
        - codec_info (Optional[str]): Video codec name (e.g., 'h264', 'h265')
        - estimated_bitrate (Optional[int]): Estimated bitrate in kbps

    Example:
        format_info, codec, bitrate = detect_format_info("/path/to/video.mp4")
        print(f"Format: {format_info}, Codec: {codec}, Bitrate: {bitrate} kbps")
    """
    if not os.path.isfile(file_path):
        return "unknown", None, None

    # Try to use ffprobe if available for detailed analysis
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", file_path],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            import json

            data = json.loads(result.stdout)

            # Extract container format
            container = data.get("format", {}).get("format_name", "unknown")

            # Find video stream and extract codec
            codec_info = None
            bitrate = None

            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    codec_info = stream.get("codec_name", "unknown")
                    # Try to get bitrate from stream or format
                    bitrate = stream.get("bit_rate")
                    if not bitrate:
                        bitrate = data.get("format", {}).get("bit_rate")
                    if bitrate:
                        bitrate = int(bitrate) // 1000  # Convert to kbps
                    break

            return container, codec_info, bitrate

    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        pass
    except Exception:
        # Handle any other exceptions including JSON decode errors
        pass

    # Fallback to file extension analysis
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".mp4", ".m4v"]:
        return "mp4", "h264", None
    elif ext in [".mkv"]:
        return "matroska", "h264", None
    elif ext in [".avi"]:
        return "avi", "h264", None
    elif ext in [".mov"]:
        return "mov", "h264", None
    else:
        return "unknown", None, None


def get_streaming_recommendations(file_path: str) -> dict:
    """Get optimization recommendations for DLNA streaming.

    Analyzes a media file and provides recommendations for optimal DLNA
    streaming performance, including format compatibility and optimization
    suggestions.

    Args:
        file_path: Path to the media file to analyze

    Returns:
        Dictionary containing:
        - container_format (str): Detected container format
        - codec (Optional[str]): Detected video codec
        - estimated_bitrate_kbps (Optional[int]): Estimated bitrate in kbps
        - is_optimal (bool): Whether the file is optimized for DLNA streaming
        - suggestions (List[str]): List of optimization recommendations

    Example:
        rec = get_streaming_recommendations("/path/to/video.mkv")
        if not rec["is_optimal"]:
            print("Optimization needed:", rec["suggestions"])
    """
    container, codec, bitrate = detect_format_info(file_path)

    recommendations = {
        "container_format": container,
        "codec": codec,
        "estimated_bitrate_kbps": bitrate,
        "is_optimal": True,
        "suggestions": [],
    }

    # Check for potential issues
    if container == "matroska" and codec != "h264":
        recommendations["is_optimal"] = False
        recommendations["suggestions"].append("MKV with non-H.264 codec may cause compatibility issues")

    if container not in ["mp4", "matroska"]:
        recommendations["is_optimal"] = False
        recommendations["suggestions"].append(f"Container format '{container}' may not be well supported")

    if codec and codec not in ["h264", "h265", "hevc"]:
        recommendations["is_optimal"] = False
        recommendations["suggestions"].append(f"Codec '{codec}' may not be supported by your TV")

    if bitrate and bitrate > 15000:  # > 15 Mbps
        recommendations["suggestions"].append(f"High bitrate ({bitrate} kbps) may cause buffering on slower networks")

    if not recommendations["suggestions"]:
        recommendations["suggestions"].append("File appears optimized for DLNA streaming")

    return recommendations


def get_subtitle_info(file_path: str) -> dict:
    """Get subtitle information for a video file.

    Analyzes a video file to detect both embedded subtitle tracks and
    external subtitle files with matching names.

    Args:
        file_path: Path to the video file to analyze

    Returns:
        Dictionary containing:
        - embedded_tracks (List[dict]): List of embedded subtitle track info
        - external_files (List[dict]): List of external subtitle file info

        Each embedded track dict contains:
        - index (int): Stream index
        - codec (str): Subtitle codec name
        - language (str): Language code
        - title (str): Track title
        - forced (bool): Whether track is forced
        - default (bool): Whether track is default

        Each external file dict contains:
        - path (str): Full path to subtitle file
        - name (str): Filename
        - extension (str): File extension

    Example:
        info = get_subtitle_info("/path/to/video.mp4")
        print(f"Found {len(info['embedded_tracks'])} embedded tracks")
        print(f"Found {len(info['external_files'])} external files")
    """
    if not os.path.isfile(file_path):
        return {"embedded_tracks": [], "external_files": []}

    result = {"embedded_tracks": [], "external_files": []}

    # Try to use ffprobe to detect embedded subtitle tracks
    try:
        probe_result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", file_path],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if probe_result.returncode == 0:
            import json

            data = json.loads(probe_result.stdout)

            for stream in data.get("streams", []):
                if stream.get("codec_type") == "subtitle":
                    track_info = {
                        "index": stream.get("index", 0),
                        "codec": stream.get("codec_name", "unknown"),
                        "language": stream.get("tags", {}).get("language", "unknown"),
                        "title": stream.get("tags", {}).get("title", ""),
                        "forced": stream.get("disposition", {}).get("forced", 0) == 1,
                        "default": stream.get("disposition", {}).get("default", 0) == 1,
                    }
                    result["embedded_tracks"].append(track_info)

    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        pass
    except Exception:
        pass

    # Look for external subtitle files
    base_path = os.path.splitext(file_path)[0]
    subtitle_extensions = [".srt", ".vtt", ".sub", ".ass", ".ssa"]

    for ext in subtitle_extensions:
        subtitle_file = base_path + ext
        if os.path.isfile(subtitle_file):
            result["external_files"].append({
                "path": subtitle_file,
                "name": os.path.basename(subtitle_file),
                "extension": ext,
            })

    return result


def suggest_optimization_command(file_path: str) -> Optional[str]:
    """Suggest ffmpeg command to optimize file for DLNA streaming.

    Analyzes a media file and generates an ffmpeg command that would
    optimize it for DLNA streaming if optimization is needed.

    Args:
        file_path: Path to the media file to analyze

    Returns:
        Complete ffmpeg command string if optimization is recommended,
        None if the file is already optimized for DLNA streaming

    Example:
        cmd = suggest_optimization_command("/path/to/video.mkv")
        if cmd:
            print("Run this command to optimize:", cmd)
        else:
            print("File is already optimized")
    """
    container, codec, bitrate = detect_format_info(file_path)

    # Only suggest optimization for problematic files
    if container == "mp4" and codec == "h264":
        return None  # Already optimal

    # Build ffmpeg command for optimization
    output_path = os.path.splitext(file_path)[0] + "_optimized.mp4"

    cmd_parts = [
        "ffmpeg",
        "-i",
        file_path,
        "-c:v",
        "libx264",  # H.264 codec
        "-preset",
        "fast",  # Fast encoding
        "-crf",
        "23",  # Good quality/size balance
        "-c:a",
        "aac",  # AAC audio
        "-b:a",
        "128k",  # 128kbps audio
        "-movflags",
        "+faststart",  # Optimize for streaming
        "-y",  # Overwrite output
        output_path,
    ]

    return " ".join(cmd_parts)


def build_optimization_command(
    file_path: str,
    *,
    target_bitrate_mbps: float = 18.0,
    force_mp4: bool = False,
    remux_only: bool = False,
) -> Tuple[Optional[list], Optional[str]]:
    """Build an ffmpeg command to optimize a file for DLNA.

    Returns a tuple of (command, mode), where mode is one of:
    - "remux": stream copy to MP4 with faststart (video copy, audio -> AAC)
    - "transcode": re-encode to H.264 + AAC with bitrate cap
    - (None, None) if no optimization recommended

    This does not execute the command.
    """
    container, codec, bitrate = detect_format_info(file_path)

    # If already optimal MP4/H.264 and within bitrate cap, skip
    if not force_mp4 and container == "mp4" and (codec in {"h264", "avc1"} or codec is None):
        if bitrate is None or bitrate <= int(target_bitrate_mbps * 1000):
            return None, None

    output_path = os.path.splitext(file_path)[0] + "_optimized.mp4"

    if remux_only and (codec in {"h264", "avc1", None}):
        # Fast remux (copy video), convert audio to AAC for compatibility
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            file_path,
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            output_path,
        ]
        return cmd, "remux"

    # Full transcode to H.264 + AAC with bitrate cap
    maxrate_k = int(target_bitrate_mbps * 1000)
    bufsize_k = maxrate_k * 2
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        file_path,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-maxrate",
        f"{maxrate_k}k",
        "-bufsize",
        f"{bufsize_k}k",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        output_path,
    ]
    return cmd, "transcode"
