import sys

# Cấu hình encoding console trên Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Cấu hình API Endpoint
TTS_API_URL = 'https://voice.vibetext.info/audiobook'
AUDIO_BASE_URL = 'https://voice.vibetext.info/audio/'

# Request Headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:154.0) Gecko/20100101 Firefox/154.0',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Content-Type': 'application/json',
    'Origin': 'https://voice.vibetext.info',
    'Referer': 'https://voice.vibetext.info/'
}

# Cấu hình mặc định cho Payload TTS
DEFAULT_PAYLOAD_CONFIG = {
    "default_voice": "9b54a977",
    "format": "mp3",
    "loudness": "podcast",
    "cover_path": None,
    "metadata": None,
    "lexicon": {
        "1994": "một nghìn chín trăm chín mươi tư",
        "1999": "một nghìn chín trăm chín mươi chín"
    },
    "voice_map": None,
    "language": "Vietnamese",
    "num_step": 35
}

# Cấu hình Nén Âm Thanh FFmpeg (AAC/M4A 56kbps Mono)
AUDIO_CODEC = 'aac'
AUDIO_BITRATE = '56k'
AUDIO_CHANNELS = '1'
AUDIO_SAMPLERATE = '44100'

# Cấu hình Dò Khoảng Lặng FFmpeg cho SRT
SILENCE_NOISE_DB = '-28dB'
SILENCE_MIN_DURATION = '0.15'
PAUSE_TITLE_TAG = '[pause 1000ms]'
