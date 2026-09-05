import urllib.request
import json
import os
from typing import Tuple
from .config import TTS_API_URL, AUDIO_BASE_URL, HEADERS, DEFAULT_PAYLOAD_CONFIG

class TTSApiClient:
    """Client giao tiếp với dịch vụ TTS Audiobook."""

    def __init__(self, api_url: str = TTS_API_URL, headers: dict = None, payload_config: dict = None):
        self.api_url = api_url
        self.headers = headers or HEADERS
        self.payload_config = payload_config or DEFAULT_PAYLOAD_CONFIG

    def generate_audio(self, text: str) -> Tuple[str, float]:
        """
        Gửi văn bản đến API TTS và bắt stream SSE để nhận kết quả.
        
        Returns:
            Tuple[output_filename, duration_seconds]
        """
        payload = self.payload_config.copy()
        payload["text"] = text

        req = urllib.request.Request(
            self.api_url,
            data=json.dumps(payload).encode('utf-8'),
            headers=self.headers,
            method='POST'
        )

        output_filename = None
        duration_s = 0.0

        with urllib.request.urlopen(req, timeout=600) as resp:

            for line_bytes in resp:
                line = line_bytes.decode('utf-8').strip()
                if line.startswith("data:"):
                    json_str = line[5:].strip()
                    if not json_str:
                        continue
                    try:
                        event = json.loads(json_str)
                        evt_type = event.get("type")
                        if evt_type == "chapter":
                            duration_s = event.get("duration_s", 0.0)
                        elif evt_type == "done":
                            output_filename = event.get("output")
                        elif evt_type in ("chapter_error", "error"):
                            raise RuntimeError(f"Lỗi TTS Server: {event.get('error')}")
                    except json.JSONDecodeError:
                        pass

        if not output_filename:
            raise RuntimeError("Không nhận được file đầu ra từ TTS API Server!")

        return output_filename, duration_s

    def download_audio(self, output_filename: str, save_path: str) -> str:
        """Tải file MP3 đã render về đĩa cứng."""
        download_url = AUDIO_BASE_URL + output_filename
        urllib.request.urlretrieve(download_url, save_path)
        return save_path
