import http.client
import urllib.parse

RENDERING_SERVICE_TYPE = "urn:schemas-upnp-org:service:RenderingControl:1"
RENDERING_CONTROL_NS = "urn:schemas-upnp-org:service:RenderingControl:1"
SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"


class RenderingControl:
    """Minimal client for DLNA RenderingControl service for volume/mute."""

    def __init__(self, control_url: str):
        self.control_url = control_url
        parsed = urllib.parse.urlparse(control_url)
        self.host = parsed.hostname
        self.port = parsed.port or (443 if parsed.scheme == "https" else 80)
        self.path = parsed.path
        self.scheme = parsed.scheme

    def _post_soap(self, action: str, body_xml: str) -> str:
        soap_action = f'"{RENDERING_SERVICE_TYPE}#{action}"'
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
            raise RuntimeError(f"DLNA RC error {resp.status}: {data[:200]!r}")
        return data.decode("utf-8", errors="ignore")

    def set_volume(self, instance_id: int, channel: str, volume: int):
        body = f'''<u:SetVolume xmlns:u="{RENDERING_CONTROL_NS}">
            <InstanceID>{instance_id}</InstanceID>
            <Channel>{channel}</Channel>
            <DesiredVolume>{volume}</DesiredVolume>
        </u:SetVolume>'''
        return self._post_soap("SetVolume", body)

    def get_volume(self, instance_id: int, channel: str) -> str:
        body = f'''<u:GetVolume xmlns:u="{RENDERING_CONTROL_NS}">
            <InstanceID>{instance_id}</InstanceID>
            <Channel>{channel}</Channel>
        </u:GetVolume>'''
        return self._post_soap("GetVolume", body)

    def set_mute(self, instance_id: int, channel: str, desired_mute: bool):
        val = "1" if desired_mute else "0"
        body = f'''<u:SetMute xmlns:u="{RENDERING_CONTROL_NS}">
            <InstanceID>{instance_id}</InstanceID>
            <Channel>{channel}</Channel>
            <DesiredMute>{val}</DesiredMute>
        </u:SetMute>'''
        return self._post_soap("SetMute", body)

    def get_mute(self, instance_id: int, channel: str) -> str:
        body = f'''<u:GetMute xmlns:u="{RENDERING_CONTROL_NS}">
            <InstanceID>{instance_id}</InstanceID>
            <Channel>{channel}</Channel>
        </u:GetMute>'''
        return self._post_soap("GetMute", body)
