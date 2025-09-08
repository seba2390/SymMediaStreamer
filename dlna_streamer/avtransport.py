import http.client
import mimetypes
import urllib.parse

AVTRANSPORT_SERVICE_TYPE = "urn:schemas-upnp-org:service:AVTransport:1"
AVTRANSPORT_CONTROL_NS = "urn:schemas-upnp-org:service:AVTransport:1"
SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"


def _escape_xml(text: str) -> str:
    """Escape XML special characters in a minimal, safe way."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _get_dlna_profile(mime_type: str) -> str:
    """Return appropriate DLNA profile based on MIME type for better TV compatibility."""
    if mime_type == "video/mp4":
        return (
            "DLNA.ORG_PN=AVC_MP4_HD_24_AC3;DLNA.ORG_OP=11;DLNA.ORG_CI=0;DLNA.ORG_FLAGS=01500000000000000000000000000000"
        )
    elif mime_type == "video/x-matroska":
        return (
            "DLNA.ORG_PN=AVC_MKV_HD_24_AC3;DLNA.ORG_OP=11;DLNA.ORG_CI=0;DLNA.ORG_FLAGS=01500000000000000000000000000000"
        )
    elif mime_type.startswith("video/"):
        return "DLNA.ORG_OP=11;DLNA.ORG_CI=0;DLNA.ORG_FLAGS=01500000000000000000000000000000"
    elif mime_type.startswith("audio/"):
        return "DLNA.ORG_PN=MP3;DLNA.ORG_OP=11;DLNA.ORG_CI=0;DLNA.ORG_FLAGS=01500000000000000000000000000000"
    else:
        return "DLNA.ORG_OP=11;DLNA.ORG_CI=0;DLNA.ORG_FLAGS=01500000000000000000000000000000"


def build_didl_lite_metadata(content_url: str, title: str, mime_type: str) -> str:
    """Return a minimal DIDL-Lite item metadata string for the media resource.

    Includes DLNA parameters in protocolInfo to indicate support for operations
    like pause/seek where possible, with format-specific profiles for better compatibility.
    """
    # Map common mime types to DLNA upnp:class
    if mime_type.startswith("video/"):
        upnp_class = "object.item.videoItem"
    elif mime_type.startswith("audio/"):
        upnp_class = "object.item.audioItem"
    else:
        upnp_class = "object.item"

    # Use format-specific DLNA profile for better TV compatibility
    dlna_params = _get_dlna_profile(mime_type)
    protocol_info = f"http-get:*:{mime_type}:{dlna_params}"

    esc_title = _escape_xml(title)
    esc_url = _escape_xml(content_url)

    didl = (
        '<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">'
        '<item id="0" parentID="0" restricted="1">'
        f"<dc:title>{esc_title}</dc:title>"
        f"<upnp:class>{upnp_class}</upnp:class>"
        f'<res protocolInfo="{protocol_info}">{esc_url}</res>'
        "</item>"
        "</DIDL-Lite>"
    )
    return didl


class DLNAController:
    """Minimal client for the DLNA AVTransport service."""

    def __init__(self, control_url: str):
        self.control_url = control_url
        parsed = urllib.parse.urlparse(control_url)
        self.host = parsed.hostname
        self.port = parsed.port or (443 if parsed.scheme == "https" else 80)
        self.path = parsed.path
        self.scheme = parsed.scheme

    def _post_soap(self, action: str, body_xml: str) -> str:
        """Send a SOAP action to the AVTransport control URL and return the response body."""
        soap_action = f'"{AVTRANSPORT_SERVICE_TYPE}#{action}"'
        envelope = f'''<?xml version="1.0" encoding="utf-8"?>
            <s:Envelope xmlns:s="{SOAP_ENV}" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
                <s:Body>
                    {body_xml}
                </s:Body>
            </s:Envelope>'''
        conn = (
            http.client.HTTPSConnection(self.host, self.port, timeout=5)
            if self.scheme == "https"
            else http.client.HTTPConnection(self.host, self.port, timeout=5)
        )
        headers = {
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPACTION": soap_action,
        }
        conn.request("POST", self.path, body=envelope.encode("utf-8"), headers=headers)
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        if resp.status >= 400:
            raise RuntimeError(f"DLNA error {resp.status}: {data[:200]!r}")
        return data.decode("utf-8", errors="ignore")

    def set_av_transport_uri(self, instance_id: int, current_uri: str, current_uri_metadata: str = ""):
        """Set the URI to play and optional DIDL-Lite metadata for the item."""
        body = f'''<u:SetAVTransportURI xmlns:u="{AVTRANSPORT_CONTROL_NS}">
            <InstanceID>{instance_id}</InstanceID>
            <CurrentURI>{_escape_xml(current_uri)}</CurrentURI>
            <CurrentURIMetaData>{_escape_xml(current_uri_metadata)}</CurrentURIMetaData>
        </u:SetAVTransportURI>'''
        return self._post_soap("SetAVTransportURI", body)

    def set_uri_with_metadata(self, instance_id: int, content_url: str, title: str) -> None:
        """Best-effort: try with minimal DIDL-Lite metadata first, fallback to bare URI."""
        guessed = mimetypes.guess_type(content_url)[0] or "video/mp4"
        didl = build_didl_lite_metadata(content_url, title, guessed)
        try:
            self.set_av_transport_uri(instance_id, content_url, didl)
        except RuntimeError:
            # Retry without metadata as fallback
            self.set_av_transport_uri(instance_id, content_url, "")

    def play(self, instance_id: int, speed: str = "1"):
        """Start playback at the given speed (usually '1')."""
        body = f'''<u:Play xmlns:u="{AVTRANSPORT_CONTROL_NS}">
            <InstanceID>{instance_id}</InstanceID>
            <Speed>{speed}</Speed>
        </u:Play>'''
        return self._post_soap("Play", body)

    def pause(self, instance_id: int):
        """Pause playback."""
        body = f'''<u:Pause xmlns:u="{AVTRANSPORT_CONTROL_NS}">
            <InstanceID>{instance_id}</InstanceID>
        </u:Pause>'''
        return self._post_soap("Pause", body)

    def stop(self, instance_id: int):
        """Stop playback."""
        body = f'''<u:Stop xmlns:u="{AVTRANSPORT_CONTROL_NS}">
            <InstanceID>{instance_id}</InstanceID>
        </u:Stop>'''
        return self._post_soap("Stop", body)

    def seek(self, instance_id: int, target: str):
        """Seek to REL_TIME target (format HH:MM:SS)."""
        body = f'''<u:Seek xmlns:u="{AVTRANSPORT_CONTROL_NS}">
            <InstanceID>{instance_id}</InstanceID>
            <Unit>REL_TIME</Unit>
            <Target>{target}</Target>
        </u:Seek>'''
        return self._post_soap("Seek", body)

    def get_position_info(self, instance_id: int) -> str:
        """Return the raw SOAP response for GetPositionInfo (contains RelTime, TrackDuration)."""
        body = f'''<u:GetPositionInfo xmlns:u="{AVTRANSPORT_CONTROL_NS}">
            <InstanceID>{instance_id}</InstanceID>
            <MediaBrowserID>0</MediaBrowserID>
        </u:GetPositionInfo>'''
        return self._post_soap("GetPositionInfo", body)

    def get_media_info(self, instance_id: int) -> str:
        """Return the raw SOAP response for GetMediaInfo (contains MediaDuration)."""
        body = f'''<u:GetMediaInfo xmlns:u="{AVTRANSPORT_CONTROL_NS}">
            <InstanceID>{instance_id}</InstanceID>
        </u:GetMediaInfo>'''
        return self._post_soap("GetMediaInfo", body)
