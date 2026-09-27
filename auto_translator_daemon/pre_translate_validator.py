"""
Module thẩm định ngữ nghĩa dữ liệu truyện trước khi dịch (Pre-Translate Sanity Validator):
Sử dụng AGY CLI để đọc và kiểm tra nhanh:
1. Các chương sắp dịch có đúng nhân vật, bối cảnh thuộc về bộ truyện này không (chống cào nhầm truyện khác).
2. Mạch truyện có nối tiếp hợp lý với chương vừa dịch trước đó không (chống đứt gãy tình tiết).
3. Các chương sắp dịch có bị cào lặp lại nội dung của nhau hoặc lặp với chương cũ không.
4. Chương cuối trong dải sắp dịch có phải là Đại Kết Cục (hoàn thành bộ truyện) không.

Kết quả trả về JSON:
{
  "allowed_to_translate": bool,
  "is_complete": bool,
  "report_brief": str
}
"""
import os
import re
import sys
import json
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

from auto_translator_daemon.config import (
    BASE_DIR,
    AGY_BIN,
    AGY_MODEL,
    AGY_EFFORT,
    LOGS_DIR,
    format_chapter_ranges
)
from auto_translator_daemon.prompt_templates import (
    DEFAULT_PRE_TRANSLATE_PROMPT_TEMPLATE,
    build_pre_translate_prompt
)

class PreTranslateValidator:
    """Thẩm định ngữ nghĩa dữ liệu truyện bằng AGY CLI trước khi cấp phép dịch."""

    def __init__(self, timeout_minutes: int = 5):
        self.timeout_minutes = timeout_minutes
        self.timeout_str = f"{timeout_minutes}m"

    def build_prompt(
        self,
        story_dir: Path,
        chapters: List[int],
        story_info: Dict[str, Any],
        template: str = DEFAULT_PRE_TRANSLATE_PROMPT_TEMPLATE
    ) -> str:
        """Xây dựng prompt chỉ dẫn AGY CLI tự đọc file và thẩm định ngữ nghĩa."""
        return build_pre_translate_prompt(
            story_dir=story_dir,
            chapters=chapters,
            story_info=story_info,
            template=template
        )

    def validate_story(
        self,
        story_dir: Path,
        chapters: List[int],
        story_info: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Thực thi AGY CLI thẩm định truyện trước khi dịch.
        Trả về: (success: bool, check_data: dict)
        """
        story_id = story_dir.name
        result_file = story_dir / "pre_check_result.json"
        if result_file.exists():
            result_file.unlink()

        prompt = self.build_prompt(story_dir, chapters, story_info)
        log_file = LOGS_DIR / f"pre_check_{story_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        cmd = [
            AGY_BIN,
            "-p", prompt,
            "--output-format", "stream-json",
            "--add-dir", str(story_dir),
            "--dangerously-skip-permissions",
            "--print-timeout", self.timeout_str
        ]
        if AGY_MODEL:
            cmd.extend(["--model", AGY_MODEL])
        if AGY_EFFORT:
            cmd.extend(["--effort", AGY_EFFORT])

        print(f"🔍 [{story_id}] Khởi động AGY CLI thẩm định dữ liệu (Timeout: {self.timeout_str})...", flush=True)

        try:
            process = subprocess.Popen(
                cmd,
                cwd=str(BASE_DIR),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )

            stdout_lines = []
            for line in process.stdout:
                stdout_lines.append(line)
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    ev = json.loads(line_str)
                    ev_type = ev.get("event")
                    if ev_type == "step_update":
                        su = ev.get("step_update", {})
                        tname = su.get("tool_name", "")
                        if tname:
                            print(f"   🔎 [AGY Pre-Check] Đang kiểm tra: {tname}...", flush=True)
                except Exception:
                    pass

            timeout_sec = self.timeout_minutes * 60 + 60
            process.wait(timeout=timeout_sec)

            # Đọc và kiểm tra trực tiếp file pre_check_result.json
            if result_file.exists():
                try:
                    content = result_file.read_text(encoding='utf-8').strip()
                    # Khử bọc markdown ```json ... ``` nếu có
                    if content.startswith("```"):
                        lines = content.splitlines()
                        if lines and lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].startswith("```"):
                            lines = lines[:-1]
                        content = "\n".join(lines).strip()

                    data = json.loads(content)
                    if isinstance(data, dict) and "allowed_to_translate" in data and "report_brief" in data:
                        allowed = bool(data["allowed_to_translate"])
                        is_comp = bool(data.get("is_complete", False))
                        report = str(data["report_brief"]).strip() or ("Đạt yêu cầu thẩm định dữ liệu." if allowed else "Dữ liệu không đạt yêu cầu.")
                        return True, {
                            "allowed_to_translate": allowed,
                            "is_complete": is_comp,
                            "report_brief": report
                        }
                    else:
                        print(f"⚠️ [{story_id}] File pre_check_result.json không đúng cấu trúc dict/keys yêu cầu!", flush=True)
                except Exception as e:
                    print(f"⚠️ [{story_id}] Không thể parse JSON từ pre_check_result.json ({e})!", flush=True)

            # Nếu không tồn tại file hoặc không parse được JSON hợp lệ -> Trả về kết quả an toàn mặc định ngay lập tức
            print(f"❌ [{story_id}] Bước Pre-Translate không trả ra JSON hợp lệ. Kích hoạt kết quả an toàn mặc định (Từ chối dịch)!", flush=True)
            return False, {
                "allowed_to_translate": False,
                "is_complete": False,
                "report_brief": (
                    f"LỖI HỆ THỐNG: AGY CLI kết thúc với mã {process.returncode} nhưng không tạo ra file pre_check_result.json hợp lệ "
                    f"theo đúng cấu trúc JSON yêu cầu. Hệ thống tự động từ chối dịch để đảm bảo an toàn."
                )
            }

        except subprocess.TimeoutExpired:
            print(f"⏰ [{story_id}] AGY CLI thẩm định dữ liệu bị timeout sau {self.timeout_minutes} phút!", flush=True)
            try:
                process.kill()
            except Exception:
                pass
            return False, {
                "allowed_to_translate": False,
                "is_complete": False,
                "report_brief": f"LỖI TIMEOUT: Tiến trình thẩm định AGY CLI bị quá thời gian ({self.timeout_minutes} phút)."
            }
        except Exception as e:
            print(f"❌ [{story_id}] Lỗi ngoại lệ khi chạy AGY Pre-check: {e}", flush=True)
            return False, {
                "allowed_to_translate": False,
                "is_complete": False,
                "report_brief": f"LỖI NGOẠI LỆ HỆ THỐNG: {e}"
            }

