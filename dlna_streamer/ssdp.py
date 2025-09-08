"""
SSDP (Simple Service Discovery Protocol) implementation for DLNA/UPnP device discovery.

This module provides functionality for discovering DLNA MediaRenderer devices
on the local network using SSDP multicast M-SEARCH requests.

Key components:
- SSDPDevice: Represents a discovered device with parsed headers
- discover(): Main discovery function with configurable timeouts
- ST_TARGETS: Common search targets for DLNA devices

Example usage:
    from dlna_streamer.ssdp import discover

    devices = discover(timeout=3.0)
    for device in devices:
        print(f"Found device: {device.location}")
"""

import socket
import time
from typing import List, Tuple

# SSDP multicast configuration
SSDP_MCAST_ADDR = "239.255.255.250"
SSDP_PORT = 1900

# Common ST targets for DLNA/UPnP MediaRenderers
ST_TARGETS = [
    "ssdp:all",
    "upnp:rootdevice",
    "urn:schemas-upnp-org:device:MediaRenderer:1",
    "urn:schemas-upnp-org:service:AVTransport:1",
]


class SSDPDevice:
    """Represents a discovered DLNA/UPnP device via SSDP.

    This class encapsulates the key information from an SSDP discovery response,
    providing access to device location, service type, and unique identifiers.

    Attributes:
        location (str): URL to the device description XML document
        st (str): Search Target value indicating the service/device type
        usn (str): Unique Service Name including root UUID and optional suffix
        server (str): Server header value if present in the response

    Example:
        device = SSDPDevice(
            location="http://192.168.1.100:8080/desc.xml",
            st="urn:schemas-upnp-org:device:MediaRenderer:1",
            usn="uuid:12345678-1234-1234-1234-123456789012::urn:schemas-upnp-org:device:MediaRenderer:1"
        )
    """

    def __init__(self, location: str, st: str, usn: str, server: str = ""):
        """Initialize SSDPDevice with discovery response data.

        Args:
            location: URL to device description XML
            st: Search Target value from SSDP response
            usn: Unique Service Name from SSDP response
            server: Server header value (optional)
        """
        self.location = location
        self.st = st
        self.usn = usn
        self.server = server

    def __repr__(self) -> str:
        """Return string representation of the device."""
        return f"SSDPDevice(st={self.st!r}, usn={self.usn!r}, location={self.location!r})"


def _parse_ssdp_response(data: bytes) -> dict:
    """Parse raw UDP response bytes into a lowercase-header dictionary.

    Args:
        data: Raw bytes from SSDP UDP response

    Returns:
        Dictionary with lowercase header names as keys and header values as values.
        Returns empty dict if parsing fails.
    """
    try:
        text = data.decode("utf-8", errors="ignore")
    except Exception:
        return {}

    lines = text.split("\r\n")
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return headers


def _get_local_ip() -> str:
    """Return the primary local IPv4 address for outbound connections.

    Uses a connection to a public DNS server to determine the local IP
    address that would be used for outbound connections.

    Returns:
        Local IPv4 address as string, or "0.0.0.0" if detection fails.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "0.0.0.0"
    finally:
        s.close()
    return ip


def discover(timeout: float = 2.0, mx: int = 1, st_list: List[str] = None) -> List[SSDPDevice]:
    """Discover UPnP/DLNA devices via SSDP multicast M-SEARCH.

    Sends M-SEARCH requests to the SSDP multicast address for each specified
    search target and collects responses within the timeout window.

    Args:
        timeout: Socket timeout and listen window per ST target in seconds
        mx: Maximum wait (MX) advertised in M-SEARCH requests in seconds
        st_list: List of ST (Search Target) values to query. If None, uses
                common DLNA targets from ST_TARGETS.

    Returns:
        List of SSDPDevice objects representing discovered devices.
        May contain duplicates - caller should deduplicate by location/USN.

    Example:
        # Basic discovery
        devices = discover()

        # Extended timeout for slow networks
        devices = discover(timeout=5.0)

        # Custom search targets
        devices = discover(st_list=["upnp:rootdevice"])
    """
    if st_list is None:
        st_list = ST_TARGETS

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # Bind to allow receiving unicast responses reliably
    try:
        sock.bind(("0.0.0.0", 0))
    except Exception:
        pass

    # Set outbound interface for multicast and a small TTL
    try:
        local_ip = _get_local_ip()
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(local_ip))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    except Exception:
        pass

    sock.settimeout(timeout)

    devices: List[SSDPDevice] = []
    seen: set[Tuple[str, str]] = set()

    for st in st_list:
        msg = (
            "M-SEARCH * HTTP/1.1\r\n"
            f"HOST: {SSDP_MCAST_ADDR}:{SSDP_PORT}\r\n"
            'MAN: "ssdp:discover"\r\n'
            f"MX: {mx}\r\n"
            f"ST: {st}\r\n\r\n"
        ).encode("utf-8")

        try:
            sock.sendto(msg, (SSDP_MCAST_ADDR, SSDP_PORT))
        except Exception:
            continue

        start = time.time()
        while time.time() - start < timeout:
            try:
                data, _ = sock.recvfrom(65535)
            except socket.timeout:
                break
            except Exception:
                break
            headers = _parse_ssdp_response(data)
            location = headers.get("location")
            st_hdr = headers.get("st", st)
            usn = headers.get("usn", "")
            server = headers.get("server", "")
            if not location:
                continue
            key = (location, usn)
            if key in seen:
                continue
            seen.add(key)
            devices.append(SSDPDevice(location=location, st=st_hdr, usn=usn, server=server))

    sock.close()
    return devices
