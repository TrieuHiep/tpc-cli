"""
Module điều phối gọi AGY CLI ở chế độ headless non-interactive để thực thi skill /dich_truyen_web.
"""
import os
import sys
import json
import zipfile
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any

from auto_translator_daemon.config import (
    BASE_DIR,
    LOGS_DIR,
    TIMEOUT_HOURS,
    get_agy_timeout_str,
    MAX_RETRIES,
    DEFAULT_BATCH_SIZE,
    AGY_BIN,
    ENABLE_FINAL_REVIEW,
    REVIEW_TIMEOUT_HOURS,
    get_agy_review_timeout_str
)
from auto_translator_daemon.prompt_templates import build_goal_prompt, build_review_prompt

class AGYRunner:
    """Điều phối và thực thi tiến trình AGY CLI cho từng bộ truyện."""

    def __init__(
        self,
        timeout_hours: float = TIMEOUT_HOURS,
        batch_size: int = DEFAULT_BATCH_SIZE,
        enable_final_review: bool = ENABLE_FINAL_REVIEW,
        review_timeout_hours: float = REVIEW_TIMEOUT_HOURS
    ):
        self.timeout_hours = timeout_hours
        self.batch_size = batch_size
        self.timeout_str = get_agy_timeout_str(timeout_hours)
        self.enable_final_review = enable_final_review
        self.review_timeout_hours = review_timeout_hours
        self.review_timeout_str = get_agy_review_timeout_str(review_timeout_hours)

    def prepare_local_workspace(self, story_dir: Path) -> str:
        """
        Chuẩn bị thư mục làm việc của truyện trước khi gọi AGY:
        - Giải nén chapters.zip vào thư mục chapters/ (nếu chưa giải nén hoặc thiếu)
        - Đọc tên truyện từ info.json nếu có
        """
        chapters_dir = story_dir / "chapters"
        chapters_dir.mkdir(parents=True, exist_ok=True)

        chapters_zip = story_dir / "chapters.zip"
        if chapters_zip.exists():
            print(f"📦 [{story_dir.name}] Đang giải nén chapters.zip vào {chapters_dir}...")
            try:
                with zipfile.ZipFile(chapters_zip, 'r') as zf:
                    zf.extractall(story_dir)
            except Exception as e:
                print(f"⚠️ Lỗi giải nén chapters.zip: {e}")

        # Đồng thời giải nén translated_chapters.zip để kế thừa các chương cũ nếu cần
        trans_zip = story_dir / "translated_chapters.zip"
        if trans_zip.exists():
            print(f"📦 [{story_dir.name}] Đang giải nén translated_chapters.zip vào {chapters_dir}...")
            try:
                with zipfile.ZipFile(trans_zip, 'r') as zf:
                    zf.extractall(story_dir)
            except Exception as e:
                print(f"⚠️ Lỗi giải nén translated_chapters.zip: {e}")

        # Lấy tên truyện từ info.json
        story_name = story_dir.name
        info_json = story_dir / "info.json"
        if info_json.exists():
            try:
                data = json.loads(info_json.read_text(encoding='utf-8', errors='ignore'))
                story_name = data.get('title') or data.get('name') or story_name
            except Exception:
                pass

        return story_name

    def run_translation(
        self,
        story_dir: Path,
        chapters_to_translate: List[int],
        story_name: Optional[str] = None
    ) -> bool:
        """
        Thực thi AGY CLI dịch danh sách chương cho một bộ truyện:
        - Tạo log file riêng theo ngày và story_id.
        - Gọi agy với cờ non-interactive: -p, --project, --log-file, --dangerously-skip-permissions.
        - Hỗ trợ cơ chế Retry tự động nếu gặp sự cố.
        """
        story_dir = story_dir.resolve()
        story_id = story_dir.name

        if not story_name:
            story_name = self.prepare_local_workspace(story_dir)
        else:
            self.prepare_local_workspace(story_dir)

        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOGS_DIR / f"{story_id}_{date_str}.log"

        # Chuẩn hóa prompt từ template tách riêng tại prompt_templates.py
        try:
            prompt = build_goal_prompt(
                story_id=story_id,
                story_dir=story_dir,
                chapters=chapters_to_translate,
                batch_size=self.batch_size
            )
        except TypeError:
            prompt = build_goal_prompt(
                story_id=story_id,
                story_dir=story_dir,
                chapters=chapters_to_translate
            )

        project_name = f"Dịch tiếp {story_id}"

        internal_debug_log = LOGS_DIR / f"{story_id}_{date_str}_internal.log"

        # Xây dựng danh sách arguments cho subprocess
        # Sử dụng --output-format stream-json để ghi nhận toàn bộ vòng đời subagents và công cụ
        cmd = [
            AGY_BIN,
            "-p", prompt,
            "--project", project_name,
            "--output-format", "stream-json",
            "--add-dir", str(story_dir),
            "--log-file", str(internal_debug_log),
            "--dangerously-skip-permissions",
            "--print-timeout", self.timeout_str
        ]

        print(f"\n🚀 [{story_id}] Bắt đầu chạy AGY CLI:", flush=True)
        print(f"   - Tên truyện: {story_name}", flush=True)
        print(f"   - Số chương cần dịch: {len(chapters_to_translate)} chương ({chapters_to_translate[0]} -> {chapters_to_translate[-1]})", flush=True)
        print(f"   - Kích thước batch: {self.batch_size} chương/session", flush=True)
        print(f"   - Project: {project_name}", flush=True)
        print(f"   - Log hội thoại: {log_file}", flush=True)
        print(f"   - Timeout: {self.timeout_hours} giờ ({self.timeout_str})", flush=True)

        # Timeout tính bằng giây cho subprocess.run (+10 phút buffer)
        subproc_timeout_sec = int(self.timeout_hours * 3600) + 600

        for attempt in range(1, MAX_RETRIES + 1):
            print(f"⏳ [{story_id}] Lần thực thi #{attempt}/{MAX_RETRIES}...", flush=True)
            try:
                # Chạy tiến trình agy với Popen để đọc stream trực tiếp ra màn hình
                process = subprocess.Popen(
                    cmd,
                    cwd=str(BASE_DIR), # Đứng từ gốc repository để nhận diện rules/skills
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='ignore'
                )

                stderr_chunks = []
                def _drain_stderr(pipe, storage):
                    try:
                        for err_line in iter(pipe.readline, ''):
                            storage.append(err_line)
                    except Exception:
                        pass
                    finally:
                        try:
                            pipe.close()
                        except Exception:
                            pass

                stderr_thread = threading.Thread(target=_drain_stderr, args=(process.stderr, stderr_chunks), daemon=True)
                stderr_thread.start()

                active_subagent = None
                conversation_id = None
                stdout_lines = []
                for line in process.stdout:
                    stdout_lines.append(line)
                    line_str = line.strip()
                    if not line_str:
                        continue
                    try:
                        ev = json.loads(line_str)
                        ev_type = ev.get("event")
                        if ev_type == "init":
                            conversation_id = ev.get("conversation_id")
                            cid = (conversation_id or "")[:8]
                            print(f"   🌱 [AGY:{story_id}] Khởi tạo phiên (Conversation ID: {cid}...)", flush=True)
                        elif ev_type == "step_update":
                            su = ev.get("step_update", {})
                            stype = su.get("step_type")
                            sstate = su.get("state")
                            tname = su.get("tool_name", "")
                            tinfo = su.get("tool_info", {})
                            sub_info = su.get("subagent_info", {})

                            if (tname == "invoke_subagent" or stype == "subagent") and sstate == "ACTIVE":
                                subagents = sub_info.get("subagents") or tinfo.get("parameters", {}).get("Subagents", [])
                                if subagents:
                                    import re
                                    sa = subagents[0]
                                    stype_name = sa.get("type_name") or sa.get("TypeName", "subagent")
                                    srole = sa.get("role") or sa.get("Role", stype_name)
                                    sprompt = sa.get("initial_prompt") or sa.get("Prompt", "")

                                    if "qc" in stype_name.lower() or "qc" in srole.lower():
                                        t_label = "Thẩm định QC"
                                        icon = "🔍"
                                    elif "trans" in stype_name.lower() or "dịch" in srole.lower():
                                        t_label = "Dịch thuật"
                                        icon = "🚀"
                                    else:
                                        t_label = srole
                                        icon = "🤖"

                                    # Trích xuất chính xác số chương thuộc danh sách chapters_to_translate
                                    combined_context = f"{srole} {sprompt}"
                                    nums_in_sub = [int(n) for n in re.findall(r'\b\d+\b', combined_context) if int(n) in set(chapters_to_translate)]

                                    if nums_in_sub:
                                        min_c, max_c = min(nums_in_sub), max(nums_in_sub)
                                        cnt = len(set(nums_in_sub))
                                        if min_c == max_c:
                                            c_label = f"Chương {min_c}"
                                        else:
                                            c_label = f"Chương {min_c} -> {max_c} ({cnt} chương)"
                                    else:
                                        m_single = re.search(r'(?:chương|chap|c)\s*(\d+)', combined_context, re.I)
                                        if m_single:
                                            c_label = f"Chương {m_single.group(1)}"
                                        else:
                                            c_label = f"{len(chapters_to_translate)} chương ({chapters_to_translate[0]} -> {chapters_to_translate[-1]})"

                                    active_subagent = f"{t_label} | {c_label}"
                                    print(f"   {icon} [AGY:{story_id}] Bắt đầu: {active_subagent}", flush=True)
                                else:
                                    active_subagent = "Subagent"
                                    print(f"   🚀 [AGY:{story_id}] Bắt đầu điều động Subagent...", flush=True)

                            elif active_subagent and (stype in ("system_message", "user_input") or (stype == "agent_response" and sstate == "ACTIVE")):
                                print(f"   📥 [AGY:{story_id}] Đã nhận báo cáo hoàn tất từ: {active_subagent}", flush=True)
                                active_subagent = None

                            elif tname in ("write_to_file", "replace_file_content") and sstate == "DONE":
                                target = tinfo.get("parameters", {}).get("TargetFile", "")
                                if target:
                                    p_target = Path(target)
                                    fname = p_target.name
                                    if fname == "content_vi.txt":
                                        chap_dir = p_target.parent.name
                                        print(f"   📝 [AGY:{story_id}] Đã hoàn thành bản dịch: Chương {chap_dir} ({fname})", flush=True)
                                    elif fname == "glossary.json":
                                        print(f"   📚 [AGY:{story_id}] Đã cập nhật bảng thuật ngữ truyện (glossary.json)", flush=True)
                                    elif fname == "summary.txt":
                                        print(f"   📑 [AGY:{story_id}] Đã cập nhật tóm tắt cốt truyện (summary.txt)", flush=True)
                                    else:
                                        print(f"   📝 [AGY:{story_id}] Đang cập nhật file: {fname}", flush=True)

                            elif tname == "run_command" and sstate == "DONE":
                                cmd_text = tinfo.get("parameters", {}).get("CommandLine", "")
                                if "glossary" in cmd_text.lower():
                                    print(f"   📚 [AGY:{story_id}] Đã cập nhật bảng thuật ngữ (glossary.json)", flush=True)
                                elif "summary" in cmd_text.lower():
                                    print(f"   📑 [AGY:{story_id}] Đã cập nhật tóm tắt cốt truyện (summary.txt)", flush=True)
                                elif "chapters" in cmd_text.lower() or "content_vi" in cmd_text.lower():
                                    print(f"   🔍 [AGY:{story_id}] Đang nghiệm thu và kiểm tra toàn bộ các file chương...", flush=True)

                        elif ev_type == "result":
                            res_obj = ev.get("result", {})
                            conversation_id = conversation_id or res_obj.get("conversation_id")
                            print(f"   🏁 [AGY:{story_id}] Đã nhận báo cáo nghiệm thu hoàn thành!", flush=True)
                    except Exception:
                        pass

                process.wait(timeout=subproc_timeout_sec)
                stderr_thread.join(timeout=5)
                stdout_full = "".join(stdout_lines)
                stderr_full = "".join(stderr_chunks)

                # Format chi tiết tiến trình bao gồm Subagents, QC Auditor và Thao tác
                formatted_log = self._format_execution_log(
                    story_name=story_name,
                    story_id=story_id,
                    chapters=chapters_to_translate,
                    returncode=process.returncode,
                    stdout_raw=stdout_full,
                    stderr_raw=stderr_full
                )

                with open(log_file, "w", encoding="utf-8") as f:
                    f.write(formatted_log)

                if process.returncode == 0:
                    print(f"✅ [{story_id}] AGY CLI hoàn thành thành công Lượt 1 (Dịch & QC batch)!", flush=True)

                    # Kích hoạt Lượt 2: Prompt Chaining tổng rà soát nếu được cấu hình
                    if self.enable_final_review and conversation_id:
                        print(f"\n🔗 [{story_id}] Kích hoạt Lượt 2: Prompt Chaining tổng rà soát toàn diện...", flush=True)
                        review_ok = self.run_final_review(
                            story_dir=story_dir,
                            chapters_to_translate=chapters_to_translate,
                            conversation_id=conversation_id,
                            log_file=log_file,
                            story_name=story_name
                        )
                        if not review_ok:
                            print(f"❌ [{story_id}] Lượt 2 (Tổng rà soát) thất bại!", flush=True)
                            return False

                    return True
                else:
                    print(f"❌ [{story_id}] AGY CLI thất bại (Exit code {process.returncode}):", flush=True)
                    if stderr_full:
                        print(f"   Stderr: {stderr_full[-500:]}", flush=True)
            except subprocess.TimeoutExpired:
                process.kill()
                print(f"⏰ [{story_id}] AGY CLI bị timeout sau {self.timeout_hours} giờ!", flush=True)
            except Exception as e:
                print(f"❌ [{story_id}] Lỗi ngoại lệ khi gọi AGY CLI: {e}")

            if attempt < MAX_RETRIES:
                print(f"🔄 Đang thử lại sau 10 giây...")
                import time
                time.sleep(10)

        print(f"💥 [{story_id}] Đã hết số lần thử lại. Phiên dịch thất bại.")
        return False

    def run_final_review(
        self,
        story_dir: Path,
        chapters_to_translate: List[int],
        conversation_id: str,
        log_file: Path,
        story_name: Optional[str] = None
    ) -> bool:
        """
        Thực thi Lượt 2 (Prompt Chaining qua --conversation):
        Gửi prompt rà soát toàn diện vào chính phiên hội thoại trước đó để Agent kiểm tra
        và tự động sửa trực tiếp trên file content_vi.txt.
        """
        story_id = story_dir.name
        review_prompt = build_review_prompt(chapters=chapters_to_translate)
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        review_internal_log = LOGS_DIR / f"{story_id}_{date_str}_review_internal.log"

        cmd = [
            AGY_BIN,
            "--conversation", conversation_id,
            "-p", review_prompt,
            "--project", f"Rà soát {story_id}",
            "--output-format", "stream-json",
            "--add-dir", str(story_dir),
            "--log-file", str(review_internal_log),
            "--dangerously-skip-permissions",
            "--print-timeout", self.review_timeout_str
        ]

        print(f"\n🔍 [{story_id}] Bắt đầu chạy AGY CLI rà soát (Turn 2):", flush=True)
        print(f"   - Conversation ID: {conversation_id[:8]}...", flush=True)
        print(f"   - Prompt: {review_prompt}", flush=True)
        print(f"   - Timeout rà soát: {self.review_timeout_hours} giờ ({self.review_timeout_str})", flush=True)

        review_timeout_sec = int(self.review_timeout_hours * 3600) + 300

        try:
            process = subprocess.Popen(
                cmd,
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )

            stderr_chunks = []
            def _drain_review_stderr(pipe, storage):
                try:
                    for err_line in iter(pipe.readline, ''):
                        storage.append(err_line)
                except Exception:
                    pass
                finally:
                    try:
                        pipe.close()
                    except Exception:
                        pass

            stderr_thread = threading.Thread(target=_drain_review_stderr, args=(process.stderr, stderr_chunks), daemon=True)
            stderr_thread.start()

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
                        sstate = su.get("state")
                        tinfo = su.get("tool_info", {})

                        if tname in ("replace_file_content", "write_to_file") and sstate == "DONE":
                            target = tinfo.get("parameters", {}).get("TargetFile", "")
                            p_t = Path(target)
                            if p_t.name == "content_vi.txt":
                                print(f"   🛠️ [AGY:{story_id}] Đã tự động hiệu đính: Chương {p_t.parent.name}", flush=True)
                    elif ev_type == "result":
                        print(f"   🏁 [AGY:{story_id}] Hoàn tất tổng rà soát!", flush=True)
                except Exception:
                    pass

            process.wait(timeout=review_timeout_sec)
            stderr_thread.join(timeout=5)
            stdout_full = "".join(stdout_lines)
            stderr_full = "".join(stderr_chunks)

            # Nối tiếp log của lượt rà soát vào log file chính của truyện
            review_header = (
                f"\n\n{'=' * 75}\n"
                f"🔍 BÁO CÁO LƯỢT 2 (PROMPT CHAINING RÀ SOÁT): {story_name or story_id}\n"
                f"📅 Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"🎯 Exit Code: {process.returncode}\n"
                f"{'=' * 75}\n"
            )

            with open(log_file, "a", encoding="utf-8") as f:
                f.write(review_header + "\n" + (stdout_full if stdout_full else stderr_full))

            if process.returncode == 0:
                print(f"✅ [{story_id}] Lượt 2 (Tổng rà soát) hoàn tất thành công!", flush=True)
                return True
            else:
                print(f"❌ [{story_id}] Lượt 2 (Tổng rà soát) thất bại (Exit code {process.returncode})", flush=True)
                if stderr_full:
                    print(f"   Stderr: {stderr_full[-500:]}", flush=True)
                return False

        except subprocess.TimeoutExpired:
            process.kill()
            print(f"⏰ [{story_id}] Lượt 2 (Tổng rà soát) bị timeout!", flush=True)
            return False
        except Exception as e:
            print(f"❌ [{story_id}] Lỗi ngoại lệ khi gọi Lượt 2 rà soát: {e}", flush=True)
            return False

    def _format_execution_log(
        self,
        story_name: str,
        story_id: str,
        chapters: List[int],
        returncode: int,
        stdout_raw: str,
        stderr_raw: str
    ) -> str:
        """
        Trích xuất thông tin tiến trình dưới dạng chuỗi thông báo trực quan như trên giao diện UI:
        - Điều động Subagent & phạm vi chương thực hiện
        - Thông báo diễn tiến của Agent (Planner Messages)
        - Tiến độ dịch & biên tập từng chương của Subagent
        - Các thao tác hiệu đính của QC Auditor
        - Cập nhật glossary & summary
        - Báo cáo nghiệm thu cuối cùng của Planner
        """
        import re

        conv_id = None
        final_response = None

        # Trích xuất conversation_id từ dòng NDJSON stream
        for line in stdout_raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                if event.get("event") == "init":
                    conv_id = event.get("conversation_id")
                elif event.get("event") == "result":
                    res = event.get("result", {})
                    conv_id = conv_id or res.get("conversation_id")
                    final_response = res.get("response")
            except Exception:
                pass

        header = [
            "=" * 75,
            f"📖 BÁO CÁO PHIÊN DỊCH AGY CLI: {story_name} ({story_id})",
            f"📅 Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"📊 Số chương: {len(chapters)} chương ({chapters[0]} -> {chapters[-1]})",
            f"🎯 Exit Code: {returncode}",
            f"🆔 Conversation ID: {conv_id or 'Unknown'}",
            "=" * 75 + "\n"
        ]

        # Kiểm tra transcript_full.jsonl trong brain của antigravity-cli
        base_brain_dir = Path.home() / ".gemini" / "antigravity-cli" / "brain"
        transcript_path = None
        if conv_id:
            transcript_path = base_brain_dir / conv_id / ".system_generated" / "logs" / "transcript_full.jsonl"

        body_lines = []

        if transcript_path and transcript_path.exists():
            body_lines.append(f"📁 Source Transcript: {transcript_path}\n")
            try:
                with open(transcript_path, 'r', encoding='utf-8', errors='ignore') as f:
                    steps = [json.loads(l) for l in f if l.strip()]

                subagent_map = {}
                pending_subagents = []

                for step in steps:
                    idx = step.get('step_index')
                    stype = step.get('type')
                    content = step.get('content', '')
                    tc = step.get('tool_calls', [])

                    # 1. Quét Tool Calls của Agent chính
                    for t in tc:
                        name = t.get('name')
                        args = t.get('args', {})

                        if name == 'invoke_subagent':
                            subagents = args.get('Subagents', [])
                            for sa in subagents:
                                role = sa.get('Role', 'Subagent')
                                tname = sa.get('TypeName', 'subagent')
                                prompt = sa.get('Prompt', '')

                                m_list = re.search(r'\[\s*\d+(?:[\s,]+\d+)*\s*\]', prompt)
                                m_single = re.search(r'(?:chương|chap|c)\s*(\d+(?:\s*(?:-|->)\s*\d+)?)', prompt, re.I)
                                scope = m_list.group(0) if m_list else (m_single.group(0) if m_single else f"{len(chapters)} chương")

                                body_lines.append(f"\n🚀 [ĐIỀU ĐỘNG SUBAGENT] {tname} ({role})")
                                body_lines.append(f"   🎯 Phạm vi thực hiện: {scope}")
                                pending_subagents.append({'role': role, 'type': tname, 'scope': scope})

                        elif name in ('write_to_file', 'replace_file_content'):
                            target = args.get('TargetFile', '')
                            fname = Path(target).name if target else ''
                            desc = args.get('Description') or ''
                            if fname == 'glossary.json':
                                body_lines.append(f"📚 [CẬP NHẬT] Đã cập nhật bảng thuật ngữ truyện (glossary.json)")
                            elif fname == 'summary.txt':
                                body_lines.append(f"📑 [CẬP NHẬT] Đã cập nhật tóm tắt diễn biến truyện (summary.txt)")
                            elif fname and fname != 'content_vi.txt':
                                body_lines.append(f"📝 [THAO TÁC FILE] {fname} - {desc}")

                        elif name == 'run_command':
                            cmd = args.get('CommandLine', '')
                            if 'glossary' in cmd.lower() and '$glossary' in cmd:
                                body_lines.append(f"📚 [CẬP NHẬT] Đã đồng bộ thuật ngữ mới vào glossary.json")
                            elif 'summary' in cmd.lower() and '$summary' in cmd:
                                body_lines.append(f"📑 [CẬP NHẬT] Đã lưu tóm tắt diễn biến vào summary.txt")

                    # 2. Bắt conversationId trả về từ lệnh gọi invoke_subagent
                    if content and '"conversationId":' in content:
                        for m in re.finditer(r'"conversationId":\s*"([a-f0-9\-]+)"', content):
                            scid = m.group(1)
                            if pending_subagents:
                                subagent_map[scid] = pending_subagents.pop(0)

                    # 3. Quét thông báo diễn tiến của Agent (Planner Messages gửi ra UI)
                    if stype == 'PLANNER_RESPONSE' and content and not tc:
                        if 'Báo Cáo Kết Quả Dịch' in content or 'BÁO CÁO NGHIỆM THU' in content:
                            final_response = content.strip()
                        else:
                            body_lines.append(f"\n💬 [THÔNG BÁO AGENT]\n{content.strip()}\n")

                    # 4. Quét Báo cáo từ Subagent gửi về
                    if stype == 'SYSTEM_MESSAGE' and '<SYSTEM_MESSAGE>' in content:
                        m = re.search(r'sender=([a-f0-9\-]+).*?content=(.*)', content, re.DOTALL)
                        if m:
                            sender_id = m.group(1)
                            raw_report = m.group(2).strip()
                            sa_info = subagent_map.get(sender_id, {})
                            sa_label = sa_info.get('role', f"Subagent {sender_id[:8]}")

                            body_lines.append(f"\n📥 [BÁO CÁO TỪ SUBAGENT] {sa_label} (ID: {sender_id[:8]})")

                            # Trích xuất tiến độ từng chương từ transcript riêng của Subagent
                            sa_transcript = base_brain_dir / sender_id / ".system_generated" / "logs" / "transcript_full.jsonl"
                            if sa_transcript.exists():
                                try:
                                    with open(sa_transcript, 'r', encoding='utf-8', errors='ignore') as sf:
                                        sa_steps = [json.loads(l) for l in sf if l.strip()]
                                    trans_actions = []
                                    qc_actions = []
                                    for ss in sa_steps:
                                        for stc in ss.get('tool_calls', []):
                                            stname = stc.get('name')
                                            sargs = stc.get('args', {})
                                            sdesc = sargs.get('Description') or ''
                                            starget = sargs.get('TargetFile', '')
                                            if stname == 'write_to_file' and 'content_vi.txt' in starget:
                                                p_t = Path(starget)
                                                c_num = p_t.parent.name
                                                trans_actions.append(f"Chương {c_num}: Hoàn thành dịch mượt ({sdesc or 'content_vi.txt'})")
                                            elif stname == 'replace_file_content' and 'content_vi.txt' in starget:
                                                p_t = Path(starget)
                                                c_num = p_t.parent.name
                                                qc_actions.append(f"Chương {c_num}: {sdesc or 'Hiệu đính văn phong'}")

                                    if trans_actions:
                                        body_lines.append("   📝 Tiến độ bản dịch:")
                                        # Loại trừ trùng lặp
                                        seen_acts = set()
                                        for act in trans_actions:
                                            if act not in seen_acts:
                                                seen_acts.add(act)
                                                body_lines.append(f"      - {act}")
                                    if qc_actions:
                                        body_lines.append("   🔍 Hiệu đính QC:")
                                        seen_qc = set()
                                        for act in qc_actions:
                                            if act not in seen_qc:
                                                seen_qc.add(act)
                                                body_lines.append(f"      - {act}")
                                except Exception:
                                    pass

                            # Trích xuất phần tóm tắt diễn biến ngắn gọn trong báo cáo
                            m_sum = re.search(r'(###\s*\d*\.?\s*TÓM TẮT DIỄN BIẾN.*?)(?=###|\Z)', raw_report, re.DOTALL | re.I)
                            if m_sum:
                                sum_text = m_sum.group(1).replace('</SYSTEM_MESSAGE>', '').strip()
                                body_lines.append("\n   " + sum_text.replace('\n', '\n   '))

            except Exception as e:
                body_lines.append(f"⚠️ Không thể phân tích toàn bộ transcript: {e}\n")

        # Nếu không đọc được từ transcript, fallback phân tích stdout NDJSON hoặc thô
        if not body_lines:
            body_lines.append("--- NỘI DUNG PHẢN HỒI (RAW OUTPUT) ---\n")
            if final_response:
                body_lines.append(final_response)
            else:
                body_lines.append(stdout_raw)

        # Phần nghiệm thu cuối cùng
        if final_response:
            body_lines.append("\n" + "=" * 75)
            body_lines.append("🏁 [BÁO CÁO NGHIỆM THU HOÀN THÀNH TỪ PLANNER]")
            body_lines.append("=" * 75 + "\n")
            body_lines.append(final_response)

        if stderr_raw:
            body_lines.append("\n\n" + "!" * 75)
            body_lines.append("⚠️ [STDERR / CẢNH BÁO HỆ THỐNG]")
            body_lines.append("!" * 75 + "\n")
            body_lines.append(stderr_raw)

        return "\n".join(header) + "\n" + "\n".join(body_lines)
