"""
TTS Package: Tự động hóa tạo giọng đọc AI từ văn bản dịch và căn phụ đề SRT.
"""

from .config import TTS_API_URL, AUDIO_BASE_URL
from .api_client import TTSApiClient
from .audio_processor import AudioProcessor
from .batch_runner import BatchRunner

__all__ = [
    'TTS_API_URL',
    'AUDIO_BASE_URL',
    'TTSApiClient',
    'AudioProcessor',
    'BatchRunner'
]
