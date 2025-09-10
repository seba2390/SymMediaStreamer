import http.server
import mimetypes
import os
import socket
import socketserver
from typing import Optional, Tuple

# Ensure MKV and common types are known
mimetypes.add_type("video/x-matroska", ".mkv")

# Optimized buffer size for streaming
STREAM_BUFFER_SIZE = 64 * 1024  # 64KB chunks


class RangeRequestHandler(http.server.SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # Track current range bounds for bounded copy
    _range_start: Optional[int] = None
    _range_end: Optional[int] = None

    def log_message(self, format, *args):
        # Suppress HTTP server logs for cleaner output
        pass

    def do_HEAD(self):
        head = self.send_head()
        if head:
            head.close()

    def do_GET(self):
        try:
            super().do_GET()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _sendfile(self, in_fd: int, out_fd: int, count: int, offset: int) -> None:
        """Attempt zero-copy sendfile, fallback to buffered copy if unavailable."""
        try:
            import os as _os

            sent = 0
            while sent < count:
                n = _os.sendfile(out_fd, in_fd, offset + sent, count - sent)
                if n == 0:
                    break
                sent += n
            return
        except Exception:
            # Fallback to manual copy bounded by count
            os.lseek(in_fd, offset, os.SEEK_SET)
            remaining = count
            try:
                while remaining > 0:
                    chunk = os.read(in_fd, min(STREAM_BUFFER_SIZE, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def copyfile(self, source, outputfile):
        """Override copyfile to use optimized buffer size and enforce ranges."""
        # If a range is active, enforce end position
        if self._range_start is not None and self._range_end is not None:
            length = self._range_end - self._range_start + 1
            try:
                in_fd = source.fileno()
                out_fd = outputfile.fileno()
                self._sendfile(in_fd, out_fd, length, self._range_start)
            except Exception:
                # Final fallback: bounded buffered copy
                try:
                    source.seek(self._range_start)
                    remaining = length
                    while remaining > 0:
                        buf = source.read(min(STREAM_BUFFER_SIZE, remaining))
                        if not buf:
                            break
                        outputfile.write(buf)
                        remaining -= len(buf)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            finally:
                # Clear range tracking
                self._range_start = None
                self._range_end = None
            return

        # No range requested: stream entire file
        try:
            while True:
                buf = source.read(STREAM_BUFFER_SIZE)
                if not buf:
                    break
                outputfile.write(buf)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return self.list_directory(path)
        ctype = self.guess_type(path)
        try:
            file_stat = os.stat(path)
            file_size = file_stat.st_size
            f = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None

        range_header = self.headers.get("Range")
        # Enhanced DLNA-friendly headers for better streaming performance
        extra_headers = {
            "transferMode.dlna.org": "Streaming",
            # More specific DLNA profile flags for better TV compatibility
            "contentFeatures.dlna.org": "DLNA.ORG_OP=11;DLNA.ORG_CI=0;DLNA.ORG_FLAGS=01500000000000000000000000000000",
            # HTTP optimizations
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Accept-Ranges": "bytes",
            "Last-Modified": self.date_time_string(file_stat.st_mtime),
        }

        if range_header:
            try:
                units, range_spec = range_header.strip().split("=")
                if units != "bytes":
                    raise ValueError
                start_str, end_str = range_spec.split("-")
                start = int(start_str) if start_str else 0
                end = int(end_str) if end_str else file_size - 1
                if start >= file_size:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{file_size}")
                    for hk, hv in extra_headers.items():
                        self.send_header(hk, hv)
                    self.end_headers()
                    f.close()
                    return None
                # Clamp end and compute length
                end = min(end, file_size - 1)
                length = end - start + 1

                # Track requested range for bounded copy in copyfile
                self._range_start = start
                self._range_end = end

                self.send_response(206)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Content-Length", str(length))
                for hk, hv in extra_headers.items():
                    self.send_header(hk, hv)
                self.end_headers()
                return f
            except Exception:
                # Fallback to full content on invalid Range header
                pass

        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(file_size))
        for hk, hv in extra_headers.items():
            self.send_header(hk, hv)
        self.end_headers()
        return f


class OptimizedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """Threaded TCP server with optimizations for streaming performance."""

    allow_reuse_address = True
    daemon_threads = True

    def server_bind(self):
        """Override to set socket options for better streaming performance."""
        super().server_bind()
        s = self.socket
        # Set socket options for better performance
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Enable TCP_NODELAY to reduce latency
        try:
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass
        # Increase socket buffer sizes
        s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 256 * 1024)  # 256KB send buffer
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 256 * 1024)  # 256KB receive buffer
        # Keepalive hints (best-effort)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        except Exception:
            pass
        try:
            # macOS uses TCP_KEEPALIVE for idle time
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPALIVE, 60)
        except Exception:
            pass

    def handle_error(self, request, client_address):
        """Suppress normal connection reset errors during streaming."""
        pass


def serve_directory(directory: str, port: int = 8000) -> Tuple[socketserver.TCPServer, int]:
    """Serve directory with optimized settings for DLNA streaming."""
    handler_class = RangeRequestHandler
    os.chdir(directory)

    httpd = OptimizedTCPServer(("0.0.0.0", port), handler_class)
    actual_port = httpd.socket.getsockname()[1]
    return httpd, actual_port
