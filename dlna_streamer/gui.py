import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.parse import quote

from .avtransport import DLNAController
from .device import fetch_description
from .format_detector import (
    build_optimization_command,
    get_streaming_recommendations,
    get_subtitle_info,
    suggest_optimization_command,
)
from .http_server import serve_directory
from .rendering_control import RenderingControl
from .ssdp import discover


def suppress_macos_warnings():
    """Suppress harmless macOS GUI framework warnings."""
    import warnings

    warnings.filterwarnings("ignore", message=".*NSOpenPanel.*")
    warnings.filterwarnings("ignore", message=".*NSWindow.*")


def _root_uuid(usn: str) -> str:
    return usn.split("::", 1)[0] if usn else usn


def _entry_rank(st: str) -> int:
    if "urn:schemas-upnp-org:service:AVTransport:1" in st:
        return 0
    if "urn:schemas-upnp-org:device:MediaRenderer:1" in st:
        return 1
    if st == "upnp:rootdevice":
        return 2
    return 3


def get_avtransport_candidates(timeout: float = 2.0):
    devices = discover(timeout=timeout)
    best_by_uuid = {}
    for dev in devices:
        desc = fetch_description(dev.location)
        if not desc.avtransport_control_url:
            continue
        uuid = _root_uuid(dev.usn)
        rank = _entry_rank(dev.st)
        current = best_by_uuid.get(uuid)
        if current is None or rank < current[2]:
            best_by_uuid[uuid] = (dev, desc, rank)
    return [(dev, desc) for (dev, desc, _) in best_by_uuid.values()]


def _get_local_ip() -> str:
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def _parse_tag(text: str, tag: str) -> str:
    # Very simple extraction of <tag>value</tag>
    start_tag = f"<{tag}>"
    end_tag = f"</{tag}>"
    start = text.find(start_tag)
    if start == -1:
        return ""
    start += len(start_tag)
    end = text.find(end_tag, start)
    if end == -1:
        return ""
    return text[start:end].strip()


def _hhmmss_to_seconds(hhmmss: str) -> int:
    """Convert HH:MM:SS to total seconds as integer."""
    if not hhmmss:
        return 0
    parts = hhmmss.split(":")
    if len(parts) != 3:
        return 0
    try:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + int(s)
    except (ValueError, TypeError):
        return 0


def _seconds_to_hhmmss(seconds: int) -> str:
    """Convert total seconds to HH:MM:SS string."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _fmt_time(hhmmss: str) -> str:
    return hhmmss or "00:00:00"


class PlaybackSession:
    """Holds HTTP server and DLNA controllers for a single playback."""

    def __init__(self):
        self.httpd = None
        self.http_thread = None
        self.controller = None
        self.render_ctrl = None
        self.active = False
        self.paused = False
        self.current_file = None
        self.subtitle_file = None
        self.subtitle_track = None

    def start(
        self,
        control_url: str,
        media_path: str,
        rendering_control_url: str | None,
        subtitle_file: str = None,
        subtitle_track: int = None,
        http_port: int = 0,
    ):
        if self.active:
            self.stop()
        serve_dir = os.path.dirname(media_path)
        file_name = os.path.basename(media_path)
        self.current_file = file_name
        self.subtitle_file = subtitle_file
        self.subtitle_track = subtitle_track
        # Use specified port (0 means ephemeral)
        self.httpd, port = serve_directory(serve_dir, port=http_port if http_port > 0 else 0)
        self.http_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.http_thread.start()
        local_ip = _get_local_ip()
        file_url = f"http://{local_ip}:{port}/{quote(file_name)}"
        self.controller = DLNAController(control_url)
        self.render_ctrl = RenderingControl(rendering_control_url) if rendering_control_url else None

        def run():
            try:
                print(f"🎬 Starting playback: {file_name}")
                print(f"📡 Streaming from: {local_ip}:{port}")
                if subtitle_file:
                    print(f"📝 External subtitle: {os.path.basename(subtitle_file)}")
                if subtitle_track is not None:
                    print(f"📝 Embedded subtitle track: {subtitle_track}")
                title = os.path.splitext(file_name)[0]
                # Pass local file path to enable codec-aware DLNA profiles
                self.controller.set_uri_with_metadata(
                    0, file_url, title, local_file_path=os.path.join(serve_dir, file_name)
                )
                self.controller.play(0)
                self.active = True
                self.paused = False
                print("✅ Playback started successfully")
            except Exception as e:
                print(f"❌ Playback failed: {e}")
                try:
                    self.httpd.shutdown()
                    self.httpd.server_close()
                except Exception:
                    pass
                self.httpd = None
                self.http_thread = None
                self.controller = None
                self.render_ctrl = None
                self.active = False
                self.paused = False

        threading.Thread(target=run, daemon=True).start()

    def stop(self):
        if self.controller:
            try:
                self.controller.stop(0)
                if self.current_file:
                    print(f"⏹️  Stopped playback: {self.current_file}")
            except Exception:
                pass
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
        self.httpd = None
        self.http_thread = None
        self.controller = None
        self.render_ctrl = None
        self.active = False
        self.paused = False
        self.current_file = None
        self.subtitle_file = None
        self.subtitle_track = None

    def pause(self):
        if self.controller and self.active and not self.paused:
            self.controller.pause(0)
            self.paused = True
            print("⏸️  Playback paused")

    def resume(self):
        if self.controller and self.active and self.paused:
            self.controller.play(0)
            self.paused = False
            print("▶️  Playback resumed")

    def seek(self, hhmmss: str):
        if self.controller and self.active:
            self.controller.seek(0, hhmmss)
            print(f"⏩  Seeking to: {hhmmss}")

    def get_volume(self) -> int:
        """Return current volume as integer 0-100, or 0 if not available."""
        if not self.render_ctrl or not self.active:
            return 0
        try:
            xml = self.render_ctrl.get_volume(0, "Master")
            vol_str = _parse_tag(xml, "CurrentVolume")
            return int(float(vol_str)) if vol_str else 0
        except Exception:
            return 0

    def get_mute(self) -> bool:
        """Return current mute state, or False if not available."""
        if not self.render_ctrl or not self.active:
            return False
        try:
            xml = self.render_ctrl.get_mute(0, "Master")
            mute_str = _parse_tag(xml, "CurrentMute")
            return mute_str == "1"
        except Exception:
            return False


class DLNAGUI(tk.Tk):
    """Minimal GUI for discovering devices and starting/stopping playback."""

    def __init__(self):
        super().__init__()
        self.title("DLNA Streamer")

        # Get screen dimensions and set window to full height
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        # Set window to full height with reasonable width
        window_width = min(640, screen_width)
        self.geometry(f"{window_width}x{screen_height}")

        # Center the window horizontally
        x_position = (screen_width - window_width) // 2
        self.geometry(f"{window_width}x{screen_height}+{x_position}+0")

        self.devices = []  # list of (dev, desc)
        self.files = []  # list of file paths
        self.session = PlaybackSession()
        self.selected_device_idx = None
        self.selected_device_uuid = None
        self.selected_file_idx = None
        self.subtitle_info = {}  # subtitle info for current file
        self.selected_subtitle_file = None
        self.selected_subtitle_track = None

        # Device list and refresh
        frm_devices = tk.LabelFrame(self, text="Devices")
        frm_devices.pack(fill=tk.BOTH, expand=False, padx=8, pady=8)
        self.lst_devices = tk.Listbox(frm_devices, height=6, exportselection=False, selectmode=tk.BROWSE)
        self.lst_devices.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 4), pady=8)
        self.lst_devices.bind("<Double-Button-1>", self.on_device_double_click)
        # Right-side vertical controls (progress, refresh, advanced)
        right_controls = tk.Frame(frm_devices)
        right_controls.pack(side=tk.RIGHT, padx=8, pady=8, fill=tk.Y)
        self.btn_refresh = tk.Button(right_controls, text="Refresh", command=self.refresh_devices)
        # Indeterminate progress bar for discovery (shown/hidden dynamically)
        self.pb_refresh = ttk.Progressbar(right_controls, mode="indeterminate", length=120)
        self.pb_refresh.stop()
        self.pb_refresh.pack_forget()

        # Advanced settings defaults
        self.discovery_timeout = tk.DoubleVar(value=2.0)
        self.http_port = tk.IntVar(value=0)  # 0 = auto
        # Optimization settings
        self.optimize_mode = tk.StringVar(value="ask")  # off|ask|auto
        self.optimize_target_mbps = tk.DoubleVar(value=18.0)
        self.optimize_strategy = tk.StringVar(value="smart")  # smart|remux|transcode

        # Advanced settings button
        self.btn_advanced = tk.Button(right_controls, text="Advanced…", command=self.open_advanced_settings)

        # Pack in vertical order: progress (when visible), Refresh, Advanced
        self.btn_refresh.pack(side=tk.TOP, anchor="e", pady=(0, 6))
        self.btn_advanced.pack(side=tk.TOP, anchor="e")
        # Note: progress bar is packed dynamically in refresh_devices into right_controls
        self.lbl_device = tk.Label(self, text="Selected device: None")
        self.lbl_device.pack(anchor="w", padx=12)

        # File list and add
        frm_files = tk.LabelFrame(self, text="Files")
        frm_files.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.lst_files = tk.Listbox(frm_files, height=8, exportselection=False, selectmode=tk.BROWSE)
        self.lst_files.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 4), pady=8)
        self.lst_files.bind("<Double-Button-1>", self.on_file_double_click)
        btn_add = tk.Button(frm_files, text="Add File", command=self.add_file)
        btn_add.pack(side=tk.RIGHT, padx=8, pady=8)
        self.lbl_file = tk.Label(self, text="Selected file: None")
        self.lbl_file.pack(anchor="w", padx=12)

        # Controls
        frm_controls = tk.LabelFrame(self, text="Controls")
        frm_controls.pack(fill=tk.X, padx=8, pady=8)
        self.btn_play = tk.Button(frm_controls, text="Play", command=self.play_selected)
        self.btn_play.pack(side=tk.LEFT, padx=4)
        self.btn_stop = tk.Button(frm_controls, text="Stop", command=self.stop_playback)
        self.btn_stop.pack(side=tk.LEFT, padx=4)
        self.btn_pause = tk.Button(frm_controls, text="Pause", command=self.pause_playback)
        self.btn_pause.pack(side=tk.LEFT, padx=4)
        self.btn_resume = tk.Button(frm_controls, text="Resume", command=self.resume_playback)
        self.btn_resume.pack(side=tk.LEFT, padx=4)

        # Optimize dropdown
        self.mb_optimize = tk.Menubutton(frm_controls, text="Optimize…", relief=tk.RAISED, direction="below")
        self.opt_menu = tk.Menu(self.mb_optimize, tearoff=0)
        self.opt_menu.add_command(label="Analyze & Suggest", command=self.optimize_selected_file)
        self.opt_menu.add_command(label="Remux to MP4 (fast)", command=self.optimize_selected_remux)
        self.opt_menu.add_command(label="Transcode to MP4 (H.264/AAC)", command=self.optimize_selected_transcode)
        self.mb_optimize.config(menu=self.opt_menu)
        self.mb_optimize.pack(side=tk.LEFT, padx=12)

        # Seek controls
        frm_seek = tk.Frame(frm_controls)
        frm_seek.pack(side=tk.RIGHT, padx=8)
        tk.Label(frm_seek, text="Seek HH:MM:SS").pack(side=tk.LEFT)
        self.entry_seek = tk.Entry(frm_seek, width=9)
        self.entry_seek.insert(0, "00:05:00")
        self.entry_seek.pack(side=tk.LEFT, padx=4)
        self.btn_seek = tk.Button(frm_seek, text="Go", command=self.seek_to)
        self.btn_seek.pack(side=tk.LEFT)

        # Status and volume
        frm_status = tk.LabelFrame(self, text="Status")
        frm_status.pack(fill=tk.X, padx=8, pady=8)
        self.lbl_progress = tk.Label(frm_status, text="00:00:00 / 00:00:00")
        self.lbl_progress.pack(side=tk.LEFT, padx=8)
        self.mute_var = tk.IntVar(value=0)
        self.chk_mute = tk.Checkbutton(frm_status, text="Mute", variable=self.mute_var, command=self.on_toggle_mute)
        self.chk_mute.pack(side=tk.RIGHT, padx=8)
        self.vol_scale = tk.Scale(
            frm_status, from_=0, to=100, orient=tk.HORIZONTAL, length=200, label="Volume", command=self.on_volume_change
        )
        self.vol_scale.pack(side=tk.RIGHT, padx=12)

        # Subtitle controls (compact)
        frm_subtitles = tk.LabelFrame(self, text="Subtitles")
        frm_subtitles.pack(fill=tk.X, padx=8, pady=4)

        # Single row with both subtitle options
        frm_subtitle_row = tk.Frame(frm_subtitles)
        frm_subtitle_row.pack(fill=tk.X, padx=4, pady=2)

        # External subtitle file (left side)
        tk.Label(frm_subtitle_row, text="External:").pack(side=tk.LEFT)
        self.lbl_subtitle_file = tk.Label(frm_subtitle_row, text="None", fg="gray", width=15, anchor="w")
        self.lbl_subtitle_file.pack(side=tk.LEFT, padx=2)
        btn_add_subtitle = tk.Button(frm_subtitle_row, text="Add", command=self.add_subtitle_file, width=6)
        btn_add_subtitle.pack(side=tk.LEFT, padx=2)

        # Separator
        tk.Label(frm_subtitle_row, text="|").pack(side=tk.LEFT, padx=4)

        # Embedded subtitle tracks (right side)
        tk.Label(frm_subtitle_row, text="Embedded:").pack(side=tk.LEFT)
        self.subtitle_track_var = tk.StringVar(value="None")
        self.subtitle_track_combo = ttk.Combobox(
            frm_subtitle_row, textvariable=self.subtitle_track_var, state="readonly", width=25
        )
        self.subtitle_track_combo.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)

        # Compact subtitle info (single line)
        self.lbl_subtitle_info = tk.Label(frm_subtitles, text="No subtitles found", fg="gray", wraplength=600, height=1)
        self.lbl_subtitle_info.pack(anchor="w", padx=4, pady=1)

        # Optimization info
        frm_optimization = tk.LabelFrame(self, text="Streaming Optimization")
        frm_optimization.pack(fill=tk.X, padx=8, pady=8)
        self.lbl_optimization = tk.Label(frm_optimization, text="No file selected", wraplength=600)
        self.lbl_optimization.pack(anchor="w", padx=8, pady=4)

        self.refresh_devices()
        self._update_buttons()
        self._poll_status()

    def _update_buttons(self):
        playing = self.session.active and not self.session.paused
        self.btn_play.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.NORMAL if self.session.active else tk.DISABLED)
        self.btn_pause.config(state=tk.NORMAL if playing else tk.DISABLED)
        self.btn_resume.config(state=tk.NORMAL if self.session.active and self.session.paused else tk.DISABLED)
        self.btn_seek.config(state=tk.NORMAL if self.session.active else tk.DISABLED)
        self.after(500, self._update_buttons)

    def _poll_status(self):
        # Update window title with device count/names
        names = [desc.friendly_name for _, desc in self.devices]
        self.title(f"DLNA Streamer - Devices: {len(names)} - {', '.join(names[:3])}{'...' if len(names) > 3 else ''}")
        # Update position if active
        if self.session.active and self.session.controller:
            try:
                xml = self.session.controller.get_position_info(0)
                rel = _parse_tag(xml, "RelTime")
                dur = _parse_tag(xml, "TrackDuration") or _parse_tag(xml, "Duration")
                self.lbl_progress.config(text=f"{_fmt_time(rel)} / {_fmt_time(dur)}")
            except Exception:
                pass
        else:
            self.lbl_progress.config(text="00:00:00 / 00:00:00")
        self.after(1000, self._poll_status)

    def _update_optimization_info(self, file_path: str):
        """Update optimization info display for selected file."""
        try:
            recommendations = get_streaming_recommendations(file_path)

            info_parts = []
            if recommendations["container_format"] != "unknown":
                info_parts.append(f"Format: {recommendations['container_format']}")
            if recommendations["codec"]:
                info_parts.append(f"Codec: {recommendations['codec']}")
            if recommendations["estimated_bitrate_kbps"]:
                info_parts.append(f"Bitrate: {recommendations['estimated_bitrate_kbps']} kbps")

            status_color = "green" if recommendations["is_optimal"] else "orange"
            status_text = "✓ Optimized" if recommendations["is_optimal"] else "⚠ May need optimization"

            info_text = f"{status_text} | {' | '.join(info_parts)}"
            if recommendations["suggestions"]:
                info_text += f"\nSuggestions: {'; '.join(recommendations['suggestions'])}"

            self.lbl_optimization.config(text=info_text, fg=status_color)

        except Exception as e:
            self.lbl_optimization.config(text=f"Could not analyze file: {str(e)}", fg="red")

    def _update_subtitle_info(self, file_path: str):
        """Update subtitle information display for selected file."""
        try:
            self.subtitle_info = get_subtitle_info(file_path)

            # Update external subtitle files
            external_files = self.subtitle_info.get("external_files", [])
            if external_files:
                self.lbl_subtitle_file.config(text=f"{len(external_files)} file(s) found", fg="green")
            else:
                self.lbl_subtitle_file.config(text="None", fg="gray")

            # Update embedded subtitle tracks
            embedded_tracks = self.subtitle_info.get("embedded_tracks", [])
            track_options = ["None"]
            for i, track in enumerate(embedded_tracks):
                lang = track.get("language", "unknown")
                codec = track.get("codec", "unknown")
                title = track.get("title", "")
                forced = " (forced)" if track.get("forced", False) else ""
                default = " (default)" if track.get("default", False) else ""
                track_name = f"Track {i + 1}: {lang} ({codec}){title}{forced}{default}"
                track_options.append(track_name)

            self.subtitle_track_combo["values"] = track_options
            if not embedded_tracks:
                self.subtitle_track_var.set("None")
                self.subtitle_track_combo.config(state="disabled")
            else:
                self.subtitle_track_combo.config(state="readonly")
                # Auto-select default track if available
                default_track = None
                for i, track in enumerate(embedded_tracks):
                    if track.get("default", False):
                        default_track = i + 1
                        break
                if default_track:
                    self.subtitle_track_var.set(track_options[default_track])
                else:
                    self.subtitle_track_var.set("None")

            # Update subtitle info display (compact)
            total_tracks = len(embedded_tracks) + len(external_files)
            if total_tracks > 0:
                info_text = f"✓ {len(embedded_tracks)} embedded, {len(external_files)} external"
                self.lbl_subtitle_info.config(text=info_text, fg="green")
            else:
                self.lbl_subtitle_info.config(text="No subtitles found", fg="gray")

        except Exception as e:
            self.lbl_subtitle_info.config(text=f"Could not analyze subtitles: {str(e)}", fg="red")
            self.lbl_subtitle_file.config(text="Error", fg="red")
            self.subtitle_track_combo.config(state="disabled")

    def add_subtitle_file(self):
        """Add an external subtitle file."""
        file_path = filedialog.askopenfilename(
            title="Select subtitle file",
            filetypes=[
                ("Subtitle files", "*.srt *.sub *.vtt *.ass *.ssa"),
                ("SRT files", "*.srt"),
                ("VTT files", "*.vtt"),
                ("All files", "*.*"),
            ],
        )
        if file_path:
            self.selected_subtitle_file = file_path
            self.selected_subtitle_track = None  # Clear embedded track selection
            self.subtitle_track_var.set("None")
            self.lbl_subtitle_file.config(text=os.path.basename(file_path), fg="green")
            print(f"📝 Selected subtitle file: {os.path.basename(file_path)}")

    def _get_selected_subtitle_track(self):
        """Get the selected embedded subtitle track index."""
        selected = self.subtitle_track_var.get()
        if selected == "None":
            return None

        # Extract track number from selection (e.g., "Track 1: en (subrip)" -> 0)
        try:
            track_num = int(selected.split(":")[0].split()[-1]) - 1
            return track_num
        except (ValueError, IndexError):
            return None

    def refresh_devices(self):
        # Disable button and show progress bar
        self.btn_refresh.config(state=tk.DISABLED)
        try:
            # Show spinner just above the Refresh button inside right_controls
            self.pb_refresh.pack_forget()
            self.pb_refresh.pack(side=tk.TOP, anchor="e", pady=(0, 6))
            self.pb_refresh.start(80)
        except Exception:
            pass

        prev_uuid = self.selected_device_uuid

        def do_discover():
            try:
                found = get_avtransport_candidates(timeout=float(self.discovery_timeout.get()))
            except Exception:
                found = []

            def on_done():
                # Update UI with results
                self.lst_devices.delete(0, tk.END)
                self.devices = found
                self.selected_device_idx = None
                self.selected_device_uuid = None
                if not self.devices:
                    self.lst_devices.insert(tk.END, "No devices found")
                    self.lbl_device.config(text="Selected device: None")
                else:
                    for i, (dev, desc) in enumerate(self.devices):
                        self.lst_devices.insert(tk.END, desc.friendly_name)
                        if prev_uuid and _root_uuid(dev.usn) == prev_uuid:
                            self.lst_devices.selection_set(i)
                            self.lst_devices.activate(i)
                            self.selected_device_idx = i
                            self.selected_device_uuid = prev_uuid
                    if self.selected_device_idx is None:
                        self.lbl_device.config(text="Selected device: None")
                    else:
                        _, desc = self.devices[self.selected_device_idx]
                        self.lbl_device.config(text=f"Selected device: {desc.friendly_name}")

                # Hide progress bar and re-enable button
                try:
                    self.pb_refresh.stop()
                    self.pb_refresh.pack_forget()
                except Exception:
                    pass
                self.btn_refresh.config(state=tk.NORMAL)

            self.after(0, on_done)

        threading.Thread(target=do_discover, daemon=True).start()

    def on_device_double_click(self, event):
        sel = self.lst_devices.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(self.devices):
            return
        dev, desc = self.devices[idx]
        self.selected_device_idx = idx
        self.selected_device_uuid = _root_uuid(dev.usn)
        self.lbl_device.config(text=f"Selected device: {desc.friendly_name}")
        self.lst_devices.selection_clear(0, tk.END)
        self.lst_devices.selection_set(idx)
        self.lst_devices.activate(idx)

    def add_file(self):
        path = filedialog.askopenfilename(title="Select video file")
        if not path:
            return
        self.files.append(path)
        self.lst_files.insert(tk.END, path)
        self.selected_file_idx = len(self.files) - 1
        self.lbl_file.config(text=f"Selected file: {os.path.basename(path)}")
        self.lst_files.selection_clear(0, tk.END)
        self.lst_files.selection_set(self.selected_file_idx)
        self.lst_files.activate(self.selected_file_idx)
        # Update optimization and subtitle info for the new file
        self._update_optimization_info(path)
        self._update_subtitle_info(path)
        # Clear subtitle selections
        self.selected_subtitle_file = None
        self.selected_subtitle_track = None

    def on_file_double_click(self, event):
        sel = self.lst_files.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(self.files):
            return
        self.selected_file_idx = idx
        self.lbl_file.config(text=f"Selected file: {os.path.basename(self.files[idx])}")
        self.lst_files.selection_clear(0, tk.END)
        self.lst_files.selection_set(idx)
        self.lst_files.activate(idx)
        # Update optimization and subtitle info for the selected file
        self._update_optimization_info(self.files[idx])
        self._update_subtitle_info(self.files[idx])
        # Clear subtitle selections
        self.selected_subtitle_file = None
        self.selected_subtitle_track = None

    def play_selected(self):
        if not self.devices:
            messagebox.showerror("No devices", "No devices available. Click Refresh.")
            return
        idx_dev = self.selected_device_idx
        if idx_dev is None:
            sel = self.lst_devices.curselection()
            if sel:
                idx_dev = sel[0]
        if idx_dev is None:
            messagebox.showerror("No device selected", "Double-click a device to select it.")
            return
        if not self.files:
            messagebox.showerror("No file", "Please add at least one file.")
            return
        idx_file = self.selected_file_idx
        if idx_file is None:
            sel_f = self.lst_files.curselection()
            if sel_f:
                idx_file = sel_f[0]
        if idx_file is None:
            messagebox.showerror("No file selected", "Double-click a file to select it.")
            return

        _, desc = self.devices[idx_dev]
        media_path = self.files[idx_file]

        # Check for optimization recommendations
        try:
            recommendations = get_streaming_recommendations(media_path)
            if not recommendations["is_optimal"] and recommendations["suggestions"]:
                opt_cmd = suggest_optimization_command(media_path)
                if opt_cmd:
                    msg = f"File may not stream optimally:\n\n{chr(10).join(recommendations['suggestions'])}\n\nOptimization command:\n{opt_cmd}\n\nContinue anyway?"
                    if not messagebox.askyesno("Streaming Optimization", msg):
                        return
        except Exception:
            pass  # Continue if analysis fails

        try:
            # Optional pre-play optimization
            media_to_play = media_path
            if self.optimize_mode.get() != "off":
                cmd, mode = self._maybe_build_optimize_cmd(media_path)
                if cmd and mode:
                    if self.optimize_mode.get() == "ask":
                        if messagebox.askyesno(
                            "Optimize file", f"Optimize before streaming?\nMode: {mode}\n\nThis may take time."
                        ):
                            optimized = self._run_ffmpeg(cmd)
                            if optimized:
                                media_to_play = optimized
                                # Replace selected file in list with optimized one
                                self._replace_selected_file(idx_file, optimized)
                    elif self.optimize_mode.get() == "auto":
                        optimized = self._run_ffmpeg(cmd)
                        if optimized:
                            media_to_play = optimized
                            self._replace_selected_file(idx_file, optimized)

            # Get selected subtitle options
            subtitle_file = self.selected_subtitle_file
            subtitle_track = self._get_selected_subtitle_track()

            self.session.start(
                desc.avtransport_control_url,
                media_to_play,
                desc.rendering_control_url,
                subtitle_file,
                subtitle_track,
                http_port=int(self.http_port.get()),
            )
            # Sync volume slider to TV's current setting after a short delay
            self.after(1000, self._sync_volume)
        except Exception as e:
            messagebox.showerror("Playback error", str(e))

    def _maybe_build_optimize_cmd(self, file_path: str):
        strategy = self.optimize_strategy.get()
        remux_only = strategy == "remux"
        force_mp4 = strategy in {"remux", "transcode"}
        if strategy == "smart":
            # Prefer remux if already H.264, else transcode
            remux_only = True
            force_mp4 = False
        try:
            cmd, mode = build_optimization_command(
                file_path,
                target_bitrate_mbps=float(self.optimize_target_mbps.get()),
                force_mp4=force_mp4,
                remux_only=remux_only,
            )
            return cmd, mode
        except Exception:
            return None, None

    def _run_ffmpeg(self, command) -> str | None:
        import shutil
        import subprocess

        # Normalize to list form
        if isinstance(command, str):
            cmd_list = command.split()
        else:
            cmd_list = list(command)
        # Extract output path (last token)
        output_path = cmd_list[-1] if cmd_list else None

        # Check ffmpeg availability
        if not shutil.which("ffmpeg"):
            messagebox.showerror("ffmpeg not found", "Please install ffmpeg and ensure it is on your PATH.")
            return None
        win = tk.Toplevel(self)
        win.title("Optimizing…")
        win.transient(self)
        win.grab_set()
        ttk.Label(win, text="Running ffmpeg optimization. This may take a while.").pack(padx=12, pady=8)
        pb = ttk.Progressbar(win, mode="indeterminate", length=300)
        pb.pack(padx=12, pady=(0, 8))
        pb.start(100)
        cancelled = {"value": False}

        def on_cancel():
            cancelled["value"] = True
            try:
                proc.terminate()
            except Exception:
                pass

        btn = ttk.Button(win, text="Cancel", command=on_cancel)
        btn.pack(pady=(0, 8))

        def runner():
            try:
                proc = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out, err = proc.communicate()
                code = proc.returncode
            except Exception:
                code = -1

            def finish():
                try:
                    pb.stop()
                    win.destroy()
                except Exception:
                    pass
                if code == 0 and output_path and os.path.isfile(output_path) and not cancelled["value"]:
                    messagebox.showinfo("Optimization complete", f"Created: {os.path.basename(output_path)}")
                elif cancelled["value"]:
                    messagebox.showwarning("Optimization cancelled", "Operation was cancelled.")
                else:
                    try:
                        err_text = (
                            err.decode("utf-8", errors="ignore") if isinstance(err, (bytes, bytearray)) else str(err)
                        )
                    except Exception:
                        err_text = ""
                    messagebox.showerror("Optimization failed", f"ffmpeg failed.\n\n{err_text[-800:]}")

            self.after(0, finish)

        threading.Thread(target=runner, daemon=True).start()
        self.wait_window(win)
        return output_path if output_path and os.path.isfile(output_path) else None

    def optimize_selected_file(self):
        if not self.files:
            messagebox.showerror("No file", "Please add at least one file.")
            return
        idx = self.selected_file_idx or 0
        file_path = self.files[idx]
        cmd, mode = self._maybe_build_optimize_cmd(file_path)
        if not cmd or not mode:
            messagebox.showinfo("Optimize file", "File already appears optimal for DLNA streaming.")
            return
        if messagebox.askyesno("Optimize file", f"Proceed with {mode} optimization?\nThis may take time."):
            out = self._run_ffmpeg(cmd)
            if out:
                self._replace_selected_file(idx, out)

    def optimize_selected_remux(self):
        if not self.files:
            messagebox.showerror("No file", "Please add at least one file.")
            return
        idx = self.selected_file_idx or 0
        file_path = self.files[idx]
        # Force remux
        try:
            cmd, mode = build_optimization_command(
                file_path,
                target_bitrate_mbps=float(self.optimize_target_mbps.get()),
                force_mp4=True,
                remux_only=True,
            )
        except Exception:
            cmd, mode = None, None
        if not cmd or not mode:
            messagebox.showinfo("Remux", "File already appears suitable for fast remux or not applicable.")
            return
        if messagebox.askyesno("Remux to MP4", "Proceed with fast remux to MP4? This is usually quick."):
            out = self._run_ffmpeg(cmd)
            if out:
                self._replace_selected_file(idx, out)

    def optimize_selected_transcode(self):
        if not self.files:
            messagebox.showerror("No file", "Please add at least one file.")
            return
        idx = self.selected_file_idx or 0
        file_path = self.files[idx]
        # Force transcode
        try:
            cmd, mode = build_optimization_command(
                file_path,
                target_bitrate_mbps=float(self.optimize_target_mbps.get()),
                force_mp4=True,
                remux_only=False,
            )
        except Exception:
            cmd, mode = None, None
        if not cmd:
            messagebox.showinfo("Transcode", "No transcode needed based on current settings.")
            return
        if messagebox.askyesno(
            "Transcode to MP4", "Proceed with H.264/AAC transcode with bitrate cap? This may take time."
        ):
            out = self._run_ffmpeg(cmd)
            if out:
                self._replace_selected_file(idx, out)

    def _replace_selected_file(self, idx: int, new_path: str):
        """Replace the file at idx with new_path and refresh UI selections/info."""
        try:
            self.files[idx] = new_path
            # Update listbox entry
            self.lst_files.delete(idx)
            self.lst_files.insert(idx, new_path)
            # Keep selection on the new item
            self.lst_files.selection_clear(0, tk.END)
            self.lst_files.selection_set(idx)
            self.lst_files.activate(idx)
            self.selected_file_idx = idx
            self.lbl_file.config(text=f"Selected file: {os.path.basename(new_path)}")
            # Refresh optimization and subtitle info for new file
            self._update_optimization_info(new_path)
            self._update_subtitle_info(new_path)
        except Exception:
            pass

    def _sync_volume(self):
        """Sync volume slider and mute checkbox to TV's current state."""
        if not self.session.active:
            return
        vol = self.session.get_volume()
        self.vol_scale.set(vol)
        mute = self.session.get_mute()
        self.mute_var.set(1 if mute else 0)

    def stop_playback(self):
        self.session.stop()

    def pause_playback(self):
        try:
            self.session.pause()
        except Exception as e:
            messagebox.showerror("Pause error", str(e))

    def resume_playback(self):
        try:
            self.session.resume()
        except Exception as e:
            messagebox.showerror("Resume error", str(e))

    def seek_to(self):
        hhmmss = self.entry_seek.get().strip()
        try:
            self.session.seek(hhmmss)
        except Exception as e:
            messagebox.showerror("Seek error", str(e))

    def on_volume_change(self, val_str):
        if self.session.render_ctrl and self.session.active:
            try:
                vol = int(float(val_str))
                self.session.render_ctrl.set_volume(0, "Master", vol)
            except Exception:
                pass

    def on_toggle_mute(self):
        if self.session.render_ctrl and self.session.active:
            try:
                desired = bool(self.mute_var.get())
                self.session.render_ctrl.set_mute(0, "Master", desired)
            except Exception:
                pass

    def open_advanced_settings(self):
        """Open a simple dialog for advanced settings."""
        win = tk.Toplevel(self)
        win.title("Advanced Settings")
        win.transient(self)
        win.grab_set()
        win.resizable(False, False)

        pad = {"padx": 10, "pady": 6}

        # Discovery timeout
        ttk.Label(win, text="Discovery timeout (seconds):").grid(row=0, column=0, sticky="w", **pad)
        sp_timeout = ttk.Spinbox(win, from_=1.0, to=15.0, increment=0.5, textvariable=self.discovery_timeout, width=6)
        sp_timeout.grid(row=0, column=1, sticky="w", **pad)

        # HTTP port
        ttk.Label(win, text="HTTP server port (0 = auto):").grid(row=1, column=0, sticky="w", **pad)
        sp_port = ttk.Spinbox(win, from_=0, to=65535, increment=1, textvariable=self.http_port, width=8)
        sp_port.grid(row=1, column=1, sticky="w", **pad)

        # Optimization mode
        ttk.Label(win, text="Optimize before play:").grid(row=2, column=0, sticky="w", **pad)
        cb_mode = ttk.Combobox(
            win, state="readonly", values=["off", "ask", "auto"], textvariable=self.optimize_mode, width=8
        )
        cb_mode.grid(row=2, column=1, sticky="w", **pad)

        # Target bitrate
        ttk.Label(win, text="Target video bitrate (Mbps):").grid(row=3, column=0, sticky="w", **pad)
        sp_br = ttk.Spinbox(win, from_=5.0, to=50.0, increment=1.0, textvariable=self.optimize_target_mbps, width=8)
        sp_br.grid(row=3, column=1, sticky="w", **pad)

        # Strategy
        ttk.Label(win, text="Optimization strategy:").grid(row=4, column=0, sticky="w", **pad)
        cb_strat = ttk.Combobox(
            win, state="readonly", values=["smart", "remux", "transcode"], textvariable=self.optimize_strategy, width=12
        )
        cb_strat.grid(row=4, column=1, sticky="w", **pad)

        # Buttons
        btns = tk.Frame(win)
        btns.grid(row=5, column=0, columnspan=2, sticky="e", **pad)

        def on_close():
            try:
                # Clamp values
                self.discovery_timeout.set(max(1.0, min(15.0, float(self.discovery_timeout.get()))))
                port = int(self.http_port.get())
                if port < 0 or port > 65535:
                    self.http_port.set(0)
                self.optimize_target_mbps.set(max(5.0, min(50.0, float(self.optimize_target_mbps.get()))))
            except Exception:
                self.discovery_timeout.set(2.0)
                self.http_port.set(0)
                self.optimize_target_mbps.set(18.0)
            win.destroy()

        ttk.Button(btns, text="OK", command=on_close).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side=tk.RIGHT)


def launch():
    # Suppress macOS GUI warnings
    suppress_macos_warnings()

    print("🚀 Starting DLNA Streamer GUI...")
    print("💡 Tip: Check the 'Streaming Optimization' panel for file analysis")
    app = DLNAGUI()
    app.mainloop()
