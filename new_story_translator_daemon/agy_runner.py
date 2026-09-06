"""
Module điều phối gọi AGY CLI ở chế độ headless non-interactive để thực thi skill /dich_truyen_web cho TRUYỆN MỚI.
Áp dụng kỹ thuật log thời gian thực và phân tích transcript trực quan của auto_translator_daemon,
đồng thời kẹp chặt mã định danh [story_id] ở từng dòng log để theo dõi chính xác khi chạy song song đa luồng.
"""
import os
import re
import sys
import json
import zipfile
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any

from new_story_translator_daemon.config import (
    BASE_DIR,
    LOGS_DIR,
    TIMEOUT_HOURS,
    get_agy_timeout_str,
    MAX_RETRIES,
    DEFAULT_BATCH_SIZE,
    AGY_BIN
)
from new_story_translator_daemon.prompt_templates import build_new_story_goal_prompt

class AGYRunner:
    """Điều phối và thực thi tiến trình AGY CLI cho từng bộ truyện mới."""

    def __init__(self, timeout_hours: float = TIMEOUT_HOURS, batch_size: int = DEFAULT_BATCH_SIZE):
        self.timeout_hours = timeout_hours
        self.batch_size = batch_size
        self.timeout_str = get_agy_timeout_str(timeout_hours)

    def prepare_local_workspace(self, story_dir: Path) -> str:
        """
        Chuẩn bị thư mục làm việc của truyện mới trước khi gọi AGY:
        - Giải nén chapters.zip vào thư mục chapters/
        - Đọc tên truyện từ info.json nếu có
        """
        chapters_dir = story_dir / "chapters"
        chapters_dir.mkdir(parents=True, exist_ok=True)

        chapters_zip = story_dir / "chapters.zip"
        if chapters_zip.exists():
            print(f"📦 [{story_dir.name}] Đang giải nén chapters.zip vào {chapters_dir}...", flush=True)
            try:
                with zipfile.ZipFile(chapters_zip, 'r') as zf:
                    zf.extractall(story_dir)
            except Exception as e:
                print(f"⚠️ [{story_dir.name}] Lỗi giải nén chapters.zip: {e}", flush=True)

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
        Thực thi AGY CLI dịch danh sách chương cho bộ truyện mới:
        - Phân tích luồng stream-json thời gian thực, in rõ ràng vai trò Subagent và tiến độ từng chương.
        - Mọi dòng log trên terminal đều được gắn thẻ [AGY:{story_id}] để phân biệt khi chạy song song.
        - Tự động phân tích transcript sau khi xong để tạo file log báo cáo chi tiết trực quan.
        """
        story_dir = story_dir.resolve()
        story_id = story_dir.name

        if not story_name:
            story_name = self.prepare_local_workspace(story_dir)
        else:
            self.prepare_local_workspace(story_dir)

        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOGS_DIR / f"{story_id}_{date_str}.log"
        internal_debug_log = LOGS_DIR / f"{story_id}_{date_str}_internal.log"

        prompt = build_new_story_goal_prompt(
            story_id=story_id,
            story_dir=story_dir,
            chapters=chapters_to_translate,
            batch_size=self.batch_size
        )

        project_name = f"Dịch mới {story_id} ({len(chapters_to_translate)} chaps)"

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

        print(f"\n🚀 [{story_id}] Bắt đầu chạy AGY CLI dịch mới:", flush=True)
        print(f"   - Tên truyện: {story_name}", flush=True)
        print(f"   - Số chương: {len(chapters_to_translate)} chương ({chapters_to_translate[0]} -> {chapters_to_translate[-1]})", flush=True)
        print(f"   - Kích thước batch: {self.batch_size} chương/session", flush=True)
        print(f"   - Project: {project_name}", flush=True)
        print(f"   - Log hội thoại: {log_file}", flush=True)

        subproc_timeout_sec = int(self.timeout_hours * 3600) + 600

        for attempt in range(1, MAX_RETRIES + 1):
            print(f"⏳ [{story_id}] Lần thực thi #{attempt}/{MAX_RETRIES}...", flush=True)
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

                active_subagent = None
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
                            cid = ev.get("conversation_id", "")[:8]
                            print(f"   🌱 [AGY:{story_id}] Khởi tạo phiên (Conversation ID: {cid}...)", flush=True)

                        elif ev_type == "step_update":
                            su = ev.get("step_update", {})
                            stype = su.get("step_type")
                            sstate = su.get("state")
                            tname = su.get("tool_name", "")
                            tinfo = su.get("tool_info", {})
                            sub_info = su.get("subagent_info", {})

                            # 1. Nhận diện Subagent được điều động
                            if (tname == "invoke_subagent" or stype == "subagent") and sstate == "ACTIVE":
                                subagents = sub_info.get("subagents") or tinfo.get("parameters", {}).get("Subagents", [])
                                if subagents:
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

                                    combined_context = f"{srole} {sprompt}"
                                    valid_chaps = set(chapters_to_translate)
                                    c_range = None

                                    # 1. Ưu tiên tìm mảng chương trong ngoặc vuông: [1, 2, 3, ...]
                                    m_list = re.search(r'\[\s*(\d+(?:[\s,]+\d+)*)\s*\]', combined_context)
                                    if m_list:
                                        nums = [int(x) for x in re.findall(r'\d+', m_list.group(1)) if int(x) in valid_chaps]
                                        if nums:
                                            c_range = (min(nums), max(nums), len(set(nums)))

                                    # 2. Tìm pattern khoảng chương: chương 1 đến 10, chap 1 -> 10, v.v.
                                    if not c_range:
                                        m_range = re.search(r'(?:chương|chap|c)\s*(\d+)\s*(?:đến|-|->|➔|đến chương)\s*(\d+)', combined_context, re.I)
                                        if m_range:
                                            c1, c2 = int(m_range.group(1)), int(m_range.group(2))
                                            if c1 in valid_chaps and c2 in valid_chaps:
                                                c_range = (min(c1, c2), max(c1, c2), abs(c2 - c1) + 1)

                                    # 3. Fallback: tìm cụm số liên tiếp dài nhất (loại bỏ số rời rạc như 100 trong '100 chương', 4 trong '4 nguyên lý')
                                    if not c_range:
                                        all_nums = sorted(list(set(int(n) for n in re.findall(r'\b\d+\b', combined_context) if int(n) in valid_chaps)))
                                        if all_nums:
                                            clusters = []
                                            current = [all_nums[0]]
                                            for n in all_nums[1:]:
                                                if n - current[-1] <= 2:
                                                    current.append(n)
                                                else:
                                                    clusters.append(current)
                                                    current = [n]
                                            clusters.append(current)
                                            longest = max(clusters, key=len)
                                            c_range = (min(longest), max(longest), len(longest))

                                    if c_range:
                                        min_c, max_c, cnt = c_range
                                        c_label = f"Chương {min_c}" if min_c == max_c else f"Chương {min_c} -> {max_c} ({cnt} chương)"
                                    else:
                                        m_single = re.search(r'(?:chương|chap|c)\s*(\d+)', combined_context, re.I)
                                        if m_single:
                                            c_label = f"Chương {m_single.group(1)}"
                                        else:
                                            c_label = f"Batch dịch ({len(chapters_to_translate)} chương)"

                                    active_subagent = f"{t_label} | {c_label}"
                                    print(f"   {icon} [AGY:{story_id}] Bắt đầu: {active_subagent}", flush=True)
                                else:
                                    active_subagent = "Subagent"
                                    print(f"   🚀 [AGY:{story_id}] Bắt đầu điều động Subagent...", flush=True)

                            # 2. Nhận diện Subagent hoàn tất báo cáo
                            elif active_subagent and (stype in ("system_message", "user_input") or (stype == "agent_response" and sstate == "ACTIVE")):
                                print(f"   📥 [AGY:{story_id}] Đã nhận báo cáo hoàn tất từ: {active_subagent}", flush=True)
                                active_subagent = None

                            # 3. Nhận diện thao tác ghi file
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
                                    print(f"   🔍 [AGY:{story_id}] Đang kiểm tra và nghiệm thu các file chương...", flush=True)

                        elif ev_type == "result":
                            print(f"   🏁 [AGY:{story_id}] Đã nhận báo cáo nghiệm thu hoàn thành!", flush=True)
                    except Exception:
                        pass

                process.wait(timeout=subproc_timeout_sec)
                stdout_full = "".join(stdout_lines)
                stderr_full = process.stderr.read() if process.stderr else ""

                # Format chi tiết log bao gồm Subagents, QC Auditor và Thao tác
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
                    print(f"✅ [{story_id}] AGY CLI hoàn thành thành công!", flush=True)
                    return True
                else:
                    print(f"❌ [{story_id}] AGY CLI thất bại (Exit code {process.returncode}):", flush=True)
                    if stderr_full:
                        print(f"   Stderr: {stderr_full[-500:]}", flush=True)

            except subprocess.TimeoutExpired:
                process.kill()
                print(f"⏰ [{story_id}] AGY CLI bị timeout sau {self.timeout_hours} giờ!", flush=True)
            except Exception as e:
                print(f"❌ [{story_id}] Ngoại lệ khi thực thi AGY CLI: {e}", flush=True)

            if attempt < MAX_RETRIES:
                print(f"🔄 [{story_id}] Đang thử lại lần #{attempt + 1} sau 10 giây...", flush=True)
                import time
                time.sleep(10)

        print(f"💥 [{story_id}] Đã hết số lần thử lại. Phiên dịch thất bại.", flush=True)
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
        Trích xuất thông tin tiến trình dưới dạng báo cáo trực quan:
        - Điều động Subagent & phạm vi chương thực hiện
        - Thông báo diễn tiến của Planner
        - Tiến độ dịch & biên tập từng chương
        - Cập nhật glossary & summary
        - Báo cáo nghiệm thu cuối cùng
        """
        conv_id = None
        final_response = None

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
            f"📖 BÁO CÁO PHIÊN DỊCH MỚI AGY CLI: {story_name} ({story_id})",
            f"📅 Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"📊 Số chương: {len(chapters)} chương ({chapters[0]} -> {chapters[-1]})",
            f"🎯 Exit Code: {returncode}",
            f"🆔 Conversation ID: {conv_id or 'Unknown'}",
            "=" * 75 + "\n"
        ]

        # Kiểm tra transcript trong các đường dẫn khả dĩ
        brain_dirs = [
            Path.home() / ".gemini" / "antigravity" / "brain",
            Path.home() / ".gemini" / "antigravity-cli" / "brain"
        ]
        transcript_path = None
        if conv_id:
            for bdir in brain_dirs:
                tpath = bdir / conv_id / ".system_generated" / "logs" / "transcript_full.jsonl"
                if tpath.exists():
                    transcript_path = tpath
                    break

        body_lines = []

        if transcript_path and transcript_path.exists():
            body_lines.append(f"📁 Source Transcript: {transcript_path}\n")
            try:
                with open(transcript_path, 'r', encoding='utf-8', errors='ignore') as f:
                    steps = [json.loads(l) for l in f if l.strip()]

                subagent_map = {}
                pending_subagents = []

                for step in steps:
                    stype = step.get('type')
                    content = step.get('content', '')
                    tc = step.get('tool_calls', [])

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
                                body_lines.append(f"📚 [CẬP NHẬT] Đã khởi tạo/cập nhật bảng thuật ngữ truyện (glossary.json)")
                            elif fname == 'summary.txt':
                                body_lines.append(f"📑 [CẬP NHẬT] Đã khởi tạo/cập nhật tóm tắt diễn biến truyện (summary.txt)")
                            elif fname and fname != 'content_vi.txt':
                                body_lines.append(f"📝 [THAO TÁC FILE] {fname} - {desc}")

                    if content and '"conversationId":' in content:
                        for m in re.finditer(r'"conversationId":\s*"([a-f0-9\-]+)"', content):
                            scid = m.group(1)
                            if pending_subagents:
                                subagent_map[scid] = pending_subagents.pop(0)

                    if stype == 'PLANNER_RESPONSE' and content and not tc:
                        if 'Báo Cáo Kết Quả Dịch' in content or 'BÁO CÁO NGHIỆM THU' in content:
                            final_response = content.strip()
                        else:
                            body_lines.append(f"\n💬 [THÔNG BÁO AGENT]\n{content.strip()}\n")

                    if stype == 'SYSTEM_MESSAGE' and '<SYSTEM_MESSAGE>' in content:
                        m = re.search(r'sender=([a-f0-9\-]+).*?content=(.*)', content, re.DOTALL)
                        if m:
                            sender_id = m.group(1)
                            raw_report = m.group(2).strip()
                            sa_info = subagent_map.get(sender_id, {})
                            sa_label = sa_info.get('role', f"Subagent {sender_id[:8]}")

                            body_lines.append(f"\n📥 [BÁO CÁO TỪ SUBAGENT] {sa_label} (ID: {sender_id[:8]})")

                            for bdir in brain_dirs:
                                sa_transcript = bdir / sender_id / ".system_generated" / "logs" / "transcript_full.jsonl"
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
                                    break

            except Exception as e:
                body_lines.append(f"⚠️ Không thể phân tích toàn bộ transcript: {e}\n")

        if not body_lines:
            body_lines.append("--- NỘI DUNG PHẢN HỒI (RAW OUTPUT) ---\n")
            if final_response:
                body_lines.append(final_response)
            else:
                body_lines.append(stdout_raw)

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
