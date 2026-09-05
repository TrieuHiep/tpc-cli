import subprocess
import re
import os
from typing import List
from .config import (
    AUDIO_CODEC, AUDIO_BITRATE, AUDIO_CHANNELS, AUDIO_SAMPLERATE,
    SILENCE_NOISE_DB, SILENCE_MIN_DURATION
)

class AudioProcessor:
    """Xử lý nén âm thanh bằng FFmpeg và tự động căn mốc phụ đề SRT."""

    @staticmethod
    def format_srt_time(seconds: float) -> str:
        """Chuyển đổi giây dạng float sang định dạng timestamp SRT (HH:MM:SS,mmm)."""
        millis = int(round((seconds - int(seconds)) * 1000))
        if millis >= 1000:
            seconds += 1
            millis = 0
        mins, secs = divmod(int(seconds), 60)
        hrs, mins = divmod(mins, 60)
        return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

    @classmethod
    def compress_to_m4a(cls, input_mp3_path: str, output_m4a_path: str) -> str:
        """Nén file MP3 sang định dạng M4A / AAC-LC Mono bằng FFmpeg."""
        cmd = [
            'ffmpeg', '-y', '-i', input_mp3_path,
            '-c:a', AUDIO_CODEC, '-b:a', AUDIO_BITRATE,
            '-ac', AUDIO_CHANNELS, '-ar', AUDIO_SAMPLERATE,
            output_m4a_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return output_m4a_path

    @classmethod
    def generate_srt(cls, audio_path: str, sentences: List[str], duration_s: float, output_srt_path: str) -> str:
        """
        Thuật toán Forced Alignment thuần túy (Dynamic Programming / Viterbi):
        Khớp trực tiếp văn bản gốc content_vi.txt với dạng sóng âm thanh 
        dựa trên tỉ lệ độ dài ký tự và mốc ngắt nghỉ thực tế mà KHÔNG cần dùng AI ASR.
        """
        if not sentences:
            return output_srt_path

        # 1. Quét mốc khoảng lặng qua FFmpeg
        cmd = [
            'ffmpeg', '-i', audio_path,
            '-af', f'silencedetect=noise={SILENCE_NOISE_DB}:d={SILENCE_MIN_DURATION}',
            '-f', 'null', '-'
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')

        starts, ends = [], []
        for line in res.stderr.split('\n'):
            if 'silence_start:' in line:
                m = re.search(r'silence_start:\s*([\d\.]+)', line)
                if m: starts.append(float(m.group(1)))
            elif 'silence_end:' in line:
                m = re.search(r'silence_end:\s*([\d\.]+)', line)
                if m: ends.append(float(m.group(1)))

        silence_intervals = list(zip(starts, ends))

        # Phân đoạn phát âm (Speech intervals)
        speech_intervals = []
        prev_e = 0.0
        for s, e in silence_intervals:
            if s > prev_e + 0.05:
                speech_intervals.append((prev_e, s))
            prev_e = e
        if prev_e < duration_s - 0.05:
            speech_intervals.append((prev_e, duration_s))

        if not speech_intervals:
            speech_intervals = [(0.0, duration_s)]

        # 2. Tính thời lượng kỳ vọng từng câu theo độ dài ký tự
        sentence_lens = [max(1, len(s)) for s in sentences]
        total_chars = sum(sentence_lens)

        title_extra_pause = 1.0  # Thẻ [pause 1000ms] ở tiêu đề
        char_time_ratio = (duration_s - title_extra_pause) / max(1, total_chars)

        expected_durations = [len(s) * char_time_ratio for s in sentences]
        expected_durations[0] += title_extra_pause

        N = len(sentences)
        M = len(speech_intervals)

        # 3. Thuật toán Dynamic Programming (DP) Forced Alignment
        dp = [[float('inf')] * (M + 1) for _ in range(N + 1)]
        parent = [[-1] * (M + 1) for _ in range(N + 1)]
        dp[0][0] = 0.0

        for i in range(1, N + 1):
            exp_dur = expected_durations[i - 1]
            for j in range(i, M + 1):
                for k in range(i - 1, j):
                    if dp[i - 1][k] == float('inf'):
                        continue
                    seg_start = speech_intervals[k][0]
                    seg_end = speech_intervals[j - 1][1]
                    act_dur = seg_end - seg_start
                    
                    cost = (act_dur - exp_dur) ** 2
                    if j < M:
                        gap = speech_intervals[j][0] - seg_end
                        cost += max(0, 0.5 - gap) * 10.0

                    total_cost = dp[i - 1][k] + cost
                    if total_cost < dp[i][j]:
                        dp[i][j] = total_cost
                        parent[i][j] = k

        # Truy vết (Backtracking)
        partition = []
        curr = M
        for i in range(N, 0, -1):
            prev = parent[i][curr]
            if prev == -1:
                prev = max(0, curr - 1)
            partition.append((prev, curr))
            curr = prev

        partition.reverse()

        # 4. Xuất file SRT
        srt_blocks = []
        for idx, (k_start, k_end) in enumerate(partition, start=1):
            t_start = speech_intervals[k_start][0]
            t_end = speech_intervals[min(k_end - 1, M - 1)][1]
            start_str = cls.format_srt_time(t_start)
            end_str = cls.format_srt_time(t_end)
            srt_blocks.append(f"{idx}\n{start_str} --> {end_str}\n{sentences[idx-1]}\n")

        with open(output_srt_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(srt_blocks))

        return output_srt_path

