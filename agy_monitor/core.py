"""
Core monitoring & inspection logic for Antigravity (AGY).
100% Python Standard Library, tương thích hoàn toàn trên cả Linux và Windows.
"""
import os
import sys
import json
import time
import signal
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from agy_monitor.config import BRAIN_DIR, TEMP_DIR, LOGS_DIR, AGY_BIN

# Bộ nhớ đệm cache cho quota (giảm tải gọi agy CLI liên tục)
_quota_cache: Dict[str, Any] = {"timestamp": 0, "data": None}
QUOTA_CACHE_TTL_SEC = 60


def check_liveness() -> Dict[str, Any]:
    """
    Kiểm tra tình trạng sống của tiến trình agy trên hệ điều hành (Cross-Platform).
    - Windows: tasklist /FI "IMAGENAME eq agy.exe"
    - Linux: pgrep -l agy hoặc kiểm tra /proc
    """
    processes = []
    is_windows = sys.platform == "win32"

    if is_windows:
        try:
            res = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq agy.exe", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                errors="ignore",
                timeout=5
            )
            for line in res.stdout.splitlines():
                line = line.strip()
                if not line or line.startswith("INFO:"):
                    continue
                parts = [p.strip('"') for p in line.split('","')]
                if len(parts) >= 5:
                    pname = parts[0]
                    pid = int(parts[1])
                    mem_str = parts[4].replace(",", "").replace(" K", "").replace(" ", "")
                    mem_mb = round(int(mem_str) / 1024, 1) if mem_str.isdigit() else 0.0
                    processes.append({
                        "pid": pid,
                        "name": pname,
                        "memory_mb": mem_mb,
                        "platform": "windows"
                    })
        except Exception:
            pass
    else:
        # Linux / macOS
        try:
            res = subprocess.run(
                ["pgrep", "-l", "agy"],
                capture_output=True,
                text=True,
                errors="ignore",
                timeout=5
            )
            for line in res.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split(maxsplit=1)
                if parts and parts[0].isdigit():
                    pid = int(parts[0])
                    pname = parts[1] if len(parts) > 1 else "agy"
                    # Lấy dung lượng RAM từ /proc/{pid}/status nếu có
                    mem_mb = 0.0
                    status_file = Path(f"/proc/{pid}/status")
                    if status_file.exists():
                        try:
                            for sline in status_file.read_text(errors="ignore").splitlines():
                                if sline.startswith("VmRSS:"):
                                    kb = sline.split()[1]
                                    mem_mb = round(int(kb) / 1024, 1)
                                    break
                        except Exception:
                            pass
                    processes.append({
                        "pid": pid,
                        "name": pname,
                        "memory_mb": mem_mb,
                        "platform": "linux"
                    })
        except Exception:
            pass

    return {
        "is_alive": len(processes) > 0,
        "count": len(processes),
        "processes": processes,
        "os": "Windows" if is_windows else "Linux"
    }


def render_ascii_bar(fraction: float, width: int = 15) -> str:
    """Tạo thanh tiến trình ASCII trực quan."""
    fraction = max(0.0, min(1.0, fraction))
    filled_len = int(round(width * fraction))
    empty_len = width - filled_len
    return f"[{'█' * filled_len}{'░' * empty_len}] {fraction * 100:.1f}%"


def get_model_quota() -> Dict[str, Any]:
    """
    Lấy thông tin Quota Token chính thức của Antigravity thông qua:
    agy -p "/quota" --output-format json
    Tiêu tốn: 0 token.
    Có cơ chế cache 60s để tránh spam CLI.
    """
    global _quota_cache
    now = time.time()

    if _quota_cache["data"] and (now - _quota_cache["timestamp"] < QUOTA_CACHE_TTL_SEC):
        return {"success": True, "cached": True, "data": _quota_cache["data"]}

    try:
        cmd = [AGY_BIN, "-p", "/quota", "--output-format", "json"]
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=15
        )
        if res.returncode == 0 and res.stdout.strip():
            raw = json.loads(res.stdout.strip())
            cmd_data = raw.get("command", {}).get("data", {})
            groups = cmd_data.get("groups", [])
            parsed_groups = []

            for g in groups:
                g_name = g.get("name", "")
                buckets = []
                for b in g.get("buckets", []):
                    b_name = b.get("name", "")
                    fraction = float(b.get("remaining_fraction", 1.0))
                    reset_time = b.get("reset_time", "")
                    desc = b.get("description", "")
                    buckets.append({
                        "name": b_name,
                        "fraction": fraction,
                        "bar": render_ascii_bar(fraction),
                        "reset_time": reset_time,
                        "description": desc
                    })
                parsed_groups.append({
                    "name": g_name,
                    "description": g.get("description", ""),
                    "buckets": buckets
                })

            result_data = {
                "groups": parsed_groups,
                "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            _quota_cache = {"timestamp": now, "data": result_data}
            return {"success": True, "cached": False, "data": result_data}

        return {"success": False, "error": f"Exit code {res.returncode}: {res.stderr.strip()}"}
    except FileNotFoundError:
        return {
            "success": False,
            "error": f"Không tìm thấy lệnh '{AGY_BIN}' trên hệ thống. Vui lòng kiểm tra đã cài đặt Antigravity CLI và thiết lập AGY_BIN_PATH trong file .env."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_active_tasks() -> Dict[str, Any]:
    """
    Quét trực tiếp Antigravity CLI Brain (~/.gemini/antigravity-cli/brain/)
    để phát hiện các phiên làm việc và Subagents đang chạy.
    """
    if not BRAIN_DIR.exists():
        return {"active": False, "message": "Thư mục brain không tồn tại hoặc chưa khởi tạo."}

    now = time.time()
    recent_sessions = []

    try:
        conv_dirs = [d for d in BRAIN_DIR.iterdir() if d.is_dir()]
        conv_dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    except Exception as e:
        return {"active": False, "error": str(e)}

    # Quét tối đa 5 session gần nhất được chỉnh sửa trong vòng 30 phút qua
    for cdir in conv_dirs[:10]:
        mtime = cdir.stat().st_mtime
        diff_sec = now - mtime
        if diff_sec > 1800: # Quá 30 phút thì bỏ qua
            continue

        transcript_file = cdir / ".system_generated" / "logs" / "transcript.jsonl"
        if not transcript_file.exists():
            transcript_file = cdir / ".system_generated" / "logs" / "transcript_full.jsonl"

        if transcript_file.exists():
            try:
                # Đọc 25 dòng cuối để phát hiện hành động mới nhất
                with open(transcript_file, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                last_lines = lines[-25:] if len(lines) > 25 else lines

                subagents = []
                current_action = "Đang xử lý..."
                story_hint = None

                for l in last_lines:
                    l = l.strip()
                    if not l:
                        continue
                    try:
                        step = json.loads(l)
                        for tc in step.get("tool_calls", []):
                            tname = tc.get("name")
                            args = tc.get("args", {})
                            if tname == "invoke_subagent":
                                for sa in args.get("Subagents", []):
                                    srole = sa.get("Role", "Subagent")
                                    stype = sa.get("TypeName", "subagent")
                                    sprompt = sa.get("Prompt", "")
                                    subagents.append(f"{stype} ({srole})")
                                    if not story_hint and ("chương" in sprompt.lower() or "chapters" in sprompt.lower()):
                                        story_hint = sprompt[:150]
                            elif tname in ("write_to_file", "replace_file_content"):
                                target = args.get("TargetFile", "")
                                if target:
                                    current_action = f"Ghi file: {Path(target).name}"
                            elif tname == "run_command":
                                current_action = f"Chạy lệnh: {args.get('CommandLine', '')[:50]}"
                    except Exception:
                        pass

                elapsed_min = round(diff_sec / 60, 1)
                recent_sessions.append({
                    "conversation_id": cdir.name,
                    "elapsed_min": elapsed_min,
                    "last_updated_sec_ago": int(diff_sec),
                    "subagents": list(set(subagents)),
                    "current_action": current_action,
                    "story_hint": story_hint
                })
            except Exception:
                pass

    return {
        "active": len(recent_sessions) > 0,
        "sessions": recent_sessions
    }


def kill_agy() -> Dict[str, Any]:
    """
    Dừng cưỡng bức toàn bộ tiến trình agy đang chạy trên máy chủ (Cross-Platform)
    và dọn dẹp thư mục tạm.
    """
    is_windows = sys.platform == "win32"
    killed_count = 0
    errors = []

    if is_windows:
        try:
            res = subprocess.run(
                ["taskkill", "/F", "/IM", "agy.exe", "/T"],
                capture_output=True,
                text=True,
                errors="ignore"
            )
            if "SUCCESS" in res.stdout or "thành công" in res.stdout.lower():
                killed_count += 1
        except Exception as e:
            errors.append(str(e))
    else:
        try:
            res = subprocess.run(
                ["pkill", "-9", "-f", "agy"],
                capture_output=True,
                text=True,
                errors="ignore"
            )
            if res.returncode == 0:
                killed_count += 1
        except Exception as e:
            errors.append(str(e))

    # Dọn dẹp thư mục tạm nếu có
    temp_cleaned = False
    if TEMP_DIR.exists():
        try:
            import shutil
            for item in TEMP_DIR.iterdir():
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
            temp_cleaned = True
        except Exception:
            pass

    return {
        "success": killed_count > 0 or not errors,
        "killed_any": killed_count > 0,
        "temp_cleaned": temp_cleaned,
        "errors": errors
    }


def smart_split_message(text: str, max_chars: int = 4000) -> List[str]:
    """
    Chia nhỏ văn bản thành các đoạn <= max_chars (giới hạn Telegram là 4096).
    Ưu tiên ngắt tại dấu xuống dòng đôi \\n\\n, xuống dòng đơn \\n, hoặc dấu chấm câu.
    Đảm bảo không bao giờ bị cắt cụt ngang từ.
    """
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks = []
    remaining = text

    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break

        candidate = remaining[:max_chars]

        # 1. Tìm \n\n
        split_idx = candidate.rfind("\n\n")
        if split_idx != -1 and split_idx > max_chars // 2:
            chunks.append(remaining[:split_idx].strip())
            remaining = remaining[split_idx + 2:].strip()
            continue

        # 2. Tìm \n
        split_idx = candidate.rfind("\n")
        if split_idx != -1 and split_idx > max_chars // 2:
            chunks.append(remaining[:split_idx].strip())
            remaining = remaining[split_idx + 1:].strip()
            continue

        # 3. Tìm dấu chấm câu (. ! ?)
        m_idx = -1
        for punct in (". ", "! ", "? ", "。\n", ".\n"):
            p_idx = candidate.rfind(punct)
            if p_idx > m_idx:
                m_idx = p_idx + len(punct) - 1

        if m_idx > max_chars // 2:
            chunks.append(remaining[:m_idx].strip())
            remaining = remaining[m_idx:].strip()
            continue

        # 4. Tìm khoảng trắng
        split_idx = candidate.rfind(" ")
        if split_idx != -1 and split_idx > max_chars // 2:
            chunks.append(remaining[:split_idx].strip())
            remaining = remaining[split_idx + 1:].strip()
            continue

        # 5. Cắt cứng nếu không tìm được điểm ngắt
        chunks.append(remaining[:max_chars])
        remaining = remaining[max_chars:]

    return [c for c in chunks if c]


def send_chat_to_agy(
    prompt: str,
    conversation_id: Optional[str] = None,
    timeout_sec: int = 180
) -> Dict[str, Any]:
    """
    Gửi câu hỏi / yêu cầu chat tới AGY CLI và nhận câu trả lời.
    - Hỗ trợ Multi-turn context thông qua cờ --conversation <id>
    - Output format: json
    """
    cmd = [AGY_BIN, "-p", prompt, "--output-format", "json"]
    if conversation_id:
        cmd.extend(["--conversation", conversation_id])

    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=timeout_sec
        )
        if res.returncode == 0 and res.stdout.strip():
            raw = json.loads(res.stdout.strip())
            response_text = raw.get("response", "").strip()
            new_conv_id = raw.get("conversation_id") or conversation_id
            return {
                "success": True,
                "response": response_text,
                "conversation_id": new_conv_id,
                "duration_seconds": raw.get("duration_seconds", 0)
            }
        else:
            err = res.stderr.strip() or f"Exit code {res.returncode}"
            return {
                "success": False,
                "error": err,
                "conversation_id": conversation_id
            }
    except FileNotFoundError:
        return {
            "success": False,
            "error": f"Không tìm thấy lệnh '{AGY_BIN}' trên hệ thống. Vui lòng kiểm tra đã cài đặt Antigravity CLI và thiết lập AGY_BIN_PATH trong file .env.",
            "conversation_id": conversation_id
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Hết thời gian chờ phản hồi ({timeout_sec}s).",
            "conversation_id": conversation_id
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "conversation_id": conversation_id
        }

