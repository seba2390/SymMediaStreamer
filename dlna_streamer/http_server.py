import http.server
import mimetypes
import os
import socket
import socketserver
from typing import Tuple

# Ensure MKV and common types are known
mimetypes.add_type("video/x-matroska", ".mkv")

# Optimized buffer size for streaming
STREAM_BUFFER_SIZE = 64 * 1024  # 64KB chunks


class RangeRequestHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress HTTP server logs for cleaner output
        pass

    def do_GET(self):
        try:
            super().do_GET()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def copyfile(self, source, outputfile):
        """Override copyfile to use optimized buffer size for streaming."""
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
                self.send_response(206)
                self.send_header("Content-Type", ctype)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Content-Length", str(end - start + 1))
                for hk, hv in extra_headers.items():
                    self.send_header(hk, hv)
                self.end_headers()
                f.seek(start)
                try:
                    self.copyfile(f, self.wfile)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                f.close()
                return None
            except Exception:
                # Fallback to full content on invalid Range header
                pass

        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(file_size))
        self.send_header("Accept-Ranges", "bytes")
        for hk, hv in extra_headers.items():
            self.send_header(hk, hv)
        self.end_headers()
        return f


class OptimizedTCPServer(socketserver.TCPServer):
    """TCP server with optimizations for streaming performance."""

    allow_reuse_address = True

    def server_bind(self):
        """Override to set socket options for better streaming performance."""
        super().server_bind()
        # Set socket options for better performance
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Enable TCP_NODELAY to reduce latency
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        # Increase socket buffer sizes
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 256 * 1024)  # 256KB send buffer
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 256 * 1024)  # 256KB receive buffer

    def handle_error(self, request, client_address):
        """Override to suppress connection reset errors during streaming."""
        # Suppress ConnectionResetError and BrokenPipeError during streaming
        # These are normal when the TV closes connections abruptly
        pass


def serve_directory(directory: str, port: int = 8000) -> Tuple[socketserver.TCPServer, int]:
    """Serve directory with optimized settings for DLNA streaming."""
    handler_class = RangeRequestHandler
    os.chdir(directory)

    httpd = OptimizedTCPServer(("0.0.0.0", port), handler_class)
    actual_port = httpd.socket.getsockname()[1]
    return httpd, actual_port
