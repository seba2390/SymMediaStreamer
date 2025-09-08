"""
UPnP device description parsing for DLNA MediaRenderer devices.

This module provides functionality for fetching and parsing UPnP device
description XML documents to extract control URLs and device information.

Key components:
- DeviceDescription: Container for parsed device information
- fetch_description(): Fetches and parses device description XML

Example usage:
    from dlna_streamer.device import fetch_description

    desc = fetch_description("http://192.168.1.100:8080/desc.xml")
    print(f"Device: {desc.friendly_name}")
    print(f"AVTransport: {desc.avtransport_control_url}")
"""

import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Optional


class DeviceDescription:
    """Container for parsed UPnP device description information.

    This class holds the essential information extracted from a UPnP device
    description XML document, focusing on playback-related services.

    Attributes:
        friendly_name (str): Human-readable device name
        avtransport_control_url (Optional[str]): URL for AVTransport service control
        rendering_control_url (Optional[str]): URL for RenderingControl service control

    Example:
        desc = DeviceDescription(
            friendly_name="Samsung TV",
            avtransport_control_url="http://192.168.1.100:8080/AVTransport/control",
            rendering_control_url="http://192.168.1.100:8080/RenderingControl/control"
        )
    """

    def __init__(
        self, friendly_name: str, avtransport_control_url: Optional[str], rendering_control_url: Optional[str]
    ):
        """Initialize DeviceDescription with parsed device information.

        Args:
            friendly_name: Human-readable device name from device description
            avtransport_control_url: Absolute URL for AVTransport service control
            rendering_control_url: Absolute URL for RenderingControl service control
        """
        self.friendly_name = friendly_name
        self.avtransport_control_url = avtransport_control_url
        self.rendering_control_url = rendering_control_url


def fetch_description(location_url: str) -> DeviceDescription:
    """Fetch and parse UPnP device description XML to extract control URLs.

    Downloads the device description XML from the specified location and
    extracts relevant service control URLs, resolving relative URLs against
    the URLBase or document URL as appropriate.

    Args:
        location_url: URL to the device description XML document

    Returns:
        DeviceDescription object with parsed device information

    Raises:
        urllib.error.URLError: If the device description cannot be fetched
        xml.etree.ElementTree.ParseError: If the XML cannot be parsed

    Example:
        desc = fetch_description("http://192.168.1.100:8080/desc.xml")
        if desc.avtransport_control_url:
            print(f"Device supports playback: {desc.friendly_name}")
    """
    with urllib.request.urlopen(location_url, timeout=5) as resp:
        xml_data = resp.read()
    root = ET.fromstring(xml_data)
    # UPnP does not always include XML namespaces uniformly; parse loosely
    friendly_name = root.findtext(".//{*}friendlyName") or "Unknown Device"

    # Resolve base URL
    base_url_text = root.findtext(".//{*}URLBase")
    if base_url_text:
        base_url = base_url_text
    else:
        base_url = location_url

    av_control_url = None
    rc_control_url = None
    for service in root.findall(".//{*}service"):
        service_type = service.findtext("{*}serviceType") or ""
        ctrl = service.findtext("{*}controlURL")
        if not ctrl:
            continue
        if ctrl.startswith("http://") or ctrl.startswith("https://"):
            abs_url = ctrl
        else:
            abs_url = urllib.parse.urljoin(base_url, ctrl)
        if "AVTransport" in service_type:
            av_control_url = abs_url
        elif "RenderingControl" in service_type:
            rc_control_url = abs_url

    return DeviceDescription(friendly_name, av_control_url, rc_control_url)
