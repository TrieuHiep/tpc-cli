"""
Prompt templates module for New Story Translator Daemon.
Chuyên quản lý mẫu câu lệnh prompt gửi cho AGY CLI phục vụ DỊCH MỚI truyện từ chương 1 đến 100.
Khởi tạo bảng glossary.json và summary.txt từ đầu.
"""
from pathlib import Path
from typing import List

# Mẫu prompt chuẩn cho AGY CLI sử dụng /goal và skill /dich_truyen_web dành riêng cho truyện mới
NEW_STORY_GOAL_PROMPT_TEMPLATE = (
    '/goal Dịch mới truyện {story_id}: sử dụng skill /dich_truyen_web để dịch truyện tại "{story_dir}". '
    'Các chương cần dịch: từ chương 1 đến chương {num_chapters} (danh sách: {chapters_to_translate}). '
    'Nhiệm vụ khởi tạo bộ truyện mới: '
    '(1) Đọc metadata từ "{story_dir}/info.json" để nắm rõ bối cảnh, thể loại, văn phong phù hợp; '
    '(2) Khởi tạo bảng thuật ngữ chuẩn ban đầu tại "{story_dir}/glossary.json" (xác định danh xưng nhân vật chính, '
    'xưng hô tôn ti, địa danh, thuật ngữ thể loại) và nhật ký cốt truyện "{story_dir}/summary.txt". '
    'Quy tắc phân bổ Subagent & Chống tràn Context (AGENTS.md): '
    '- Bắt buộc chia danh sách {num_chapters} chương thành các batch tuần tự (mỗi batch = {batch_size} chương/session: '
    '[1..10], [11..20], ..., [{start_last_batch}..{num_chapters}]). '
    '- BẮT BUỘC khi gọi define_subagent cho translator_subagent và qc_auditor_subagent phải đặt enable_write_tools: true '
    'để subagents có đủ quyền tạo và sửa file content_vi.txt. '
    '- Mỗi batch: translator_subagent dịch và ghi lần lượt từng file content_vi.txt, sau đó qc_auditor_subagent thẩm định QC '
    'đạt chuẩn mới được chuyển sang batch kế tiếp. Kế thừa và cập nhật liên tục glossary.json và summary.txt sau mỗi batch. '
    '🔴 ANTI-ABRIDGMENT & FULL NARRATIVE MANDATE (LỆNH CẤM TÓM TẮT TUYỆT ĐỐI): '
    '- Bản dịch là dịch văn học toàn văn 100% bám sát nội dung gốc (Full Verbatim Narrative Translation). '
    '- CẤM TUYỆT ĐỐI tóm tắt, cấm lược dịch, cấm gộp đoạn, cấm cắt xén bất kỳ lời thoại, tình tiết, suy nghĩ nhân vật hay miêu tả bối cảnh nào. '
    '- Ràng buộc định lượng: Bản dịch tiếng Việt phải tương ứng đầy đủ 1-1 với raw Trung; '
    'dung lượng ký tự Vi/Zh bắt buộc >= 0.9 (sàn an toàn sau khi đã loại bỏ 100% rác tác giả/donate/xin hoa) '
    'và số từ tiếng Việt phải đạt từ 1.500 đến 3.500 từ/chương (tương đương số chữ Hán raw). '
    'Bất kỳ chương nào dưới 800 từ hoặc Vi/Zh < 0.9 đều bị coi là LỖI PHẾ PHẨM NGHIÊM TRỌNG và phải dịch lại toàn văn ngay lập tức. '
    '🔴 IN-FLIGHT BATCH QC GATE (CHỐT CHẶN NGHIỆM THU TỪNG BATCH): '
    '- Trong mỗi batch: Sau khi translator_subagent tạo file, qc_auditor_subagent BẮT BUỘC phải kiểm tra độ dài từng file content_vi.txt. '
    'Nếu phát hiện bất kỳ chương nào bị cắt gọt / tóm tắt (Vi/Zh < 0.9 hoặc < 800 từ) hoặc còn sót chữ Hán / thẻ HTML, '
    'BẮT BUỘC từ chối nghiệm thu và yêu cầu translator_subagent dịch lại toàn văn ngay trong batch đó trước khi được phép sang batch kế tiếp. '
    '🔴 CHỈ THỊ THỰC THI HEADLESS CLI NON-INTERACTIVE (QUAN TRỌNG NHẤT): '
    '- CẤM TUYỆT ĐỐI xuất bất kỳ tin nhắn văn bản thông báo trung gian (intermediate chat text) nào sau khi gọi invoke_subagent. '
    'Hãy im lặng kết thúc lượt công cụ để CLI tự động chờ nhận phản hồi từ subagent khi hoàn thành. '
    '- Thực hiện liên tục không dừng qua toàn bộ các batch cho đến khi hoàn thành đủ {num_chapters} chương. '
    'Tiêu chí nghiệm thu hoàn thành: '
    '(1) Đã tạo đầy đủ {num_chapters} file content_vi.txt trong các thư mục chương tương ứng tại "{story_dir}/chapters/", '
    'sạch 100% chữ Hán và không chứa bất kỳ thẻ HTML nào (<p>, </p>, <br>); '
    '(2) Dòng đầu tiên của mỗi file content_vi.txt bắt buộc theo định dạng "Chương X: [Tiêu đề]" (nếu raw gốc thiếu tiêu đề '
    'thì tự suy luận tiêu đề ngắn gọn 3-8 từ phù hợp theo nội dung chương phục vụ nạp CSDL); '
    '(3) Tuân thủ 4 nguyên lý dịch mượt mà, khử triệt để từ ngữ convert, Hán-Việt lỗi thời và tiếng lóng mạng Trung Quốc; '
    '(4) Bản dịch các chương bảo toàn 100% dung lượng và chi tiết, không bị tóm tắt, cắt cụt, cắt gọt so với bản gốc (tỷ lệ ký tự Vi/Zh >= 0.9 và số từ >= 800 từ/chương); '
    '(5) Khởi tạo hoàn chỉnh file glossary.json và summary.txt trong thư mục truyện phục vụ cho các phiên dịch tiếp theo; '
    '(6) 🔴 Tự động loại bỏ 100% rác quảng cáo, dự thu văn truyện mới, lời tác giả xin phiếu/hoa/donate/bình chọn ở đầu hoặc cuối chương (nếu có); chỉ dịch trọn vẹn phần nội dung cốt truyện chính; '
    '(7) Chỉ xuất Báo Cáo Nghiệm Thu Tổng Kết kèm thẻ <!-- GOAL_COMPLETE --> ở cuối cùng khi 100% {num_chapters} file content_vi.txt đã tồn tại trên đĩa.'
)


def build_new_story_goal_prompt(
    story_id: str,
    story_dir: Path,
    chapters: List[int],
    batch_size: int = 10,
    template: str = NEW_STORY_GOAL_PROMPT_TEMPLATE
) -> str:
    """
    Tạo chuỗi prompt /goal hoàn chỉnh cho truyện mới từ template và các tham số đầu vào.

    Args:
        story_id: Mã định danh truyện (ID)
        story_dir: Đường dẫn thư mục cục bộ của truyện
        chapters: Danh sách các số chương cần dịch (ví dụ: 1 đến 100)
        batch_size: Kích thước batch cho mỗi Subagent session (mặc định 10)
        template: Mẫu prompt tùy biến
    """
    num_chapters = len(chapters)
    effective_batch_size = 1 if num_chapters < 10 else batch_size

    # Tính mốc bắt đầu của batch cuối cùng
    start_last_batch = ((num_chapters - 1) // effective_batch_size) * effective_batch_size + 1

    return template.format(
        story_id=story_id,
        story_dir=str(story_dir),
        chapters_to_translate=chapters,
        num_chapters=num_chapters,
        batch_size=effective_batch_size,
        start_last_batch=start_last_batch
    )


# Mẫu prompt tiếp tục dịch (Resume Prompt) khi phiên bị ngắt quãng giữa chừng
NEW_STORY_RESUME_PROMPT_TEMPLATE = (
    'Tiếp tục dịch các chương còn thiếu của truyện {story_id}: '
    'Hiện tại các chương sau chưa có file content_vi.txt hoặc bị gián đoạn: {missing_chapters_str} (tổng cộng {num_missing} chương). '
    'Hãy kế thừa glossary.json và summary.txt hiện có tại "{story_dir}", tiếp tục phân bổ translator_subagent và qc_auditor_subagent '
    '(với enable_write_tools=True) theo batch {batch_size} chương để dịch và hoàn thành toàn bộ các chương còn thiếu này. '
    '🔴 ANTI-ABRIDGMENT MANDATE: Dịch toàn văn 100% chi tiết bám sát raw, CẤM TUYỆT ĐỐI tóm tắt/lược dịch, tỷ lệ Vi/Zh bắt buộc >= 0.9 và số từ >= 800 từ/chương. '
    '🔴 IN-FLIGHT QC: qc_auditor_subagent kiểm tra nghiêm ngặt độ dài từng chương trước khi cho phép chuyển batch. '
    '🔴 CẤM xuất tin nhắn trung gian sau khi invoke_subagent. Mỗi chương bắt buộc lưu vào "{story_dir}/chapters/[Chương]/content_vi.txt" '
    '(dòng 1: Chương X: [Tiêu đề suy luận], sạch 100% chữ Hán và thẻ HTML). '
    'Chỉ xuất Báo Cáo Nghiệm Thu kèm thẻ <!-- GOAL_COMPLETE --> khi toàn bộ {num_missing} chương còn thiếu đã hoàn thành và đạt 100% QC.'
)


def build_new_story_resume_prompt(
    story_id: str,
    story_dir: Path,
    missing_chapters: List[int],
    batch_size: int = 10,
    template: str = NEW_STORY_RESUME_PROMPT_TEMPLATE
) -> str:
    """
    Tạo chuỗi prompt khôi phục phiên để dịch tiếp các chương còn thiếu.
    """
    from new_story_translator_daemon.config import format_chapter_ranges
    missing_str = format_chapter_ranges(missing_chapters)
    effective_batch_size = 1 if len(missing_chapters) < 10 else batch_size

    return template.format(
        story_id=story_id,
        story_dir=str(story_dir),
        missing_chapters_str=missing_str,
        num_missing=len(missing_chapters),
        batch_size=effective_batch_size
    )


# Mẫu prompt chuẩn cho AGY CLI lượt 2 (Prompt Chaining) thực hiện tổng rà soát cho truyện mới
NEW_STORY_REVIEW_PROMPT_TEMPLATE = (
    'Rà soát lại 1 lần nữa xem các chương {chapters_str} đã đạt tiêu chuẩn QC của /dich_truyen_web chưa, có bị cắt gọt nội dung không, '
    'và mạch truyện có logic không, câu văn dịch có bị lủng củng không, '
    'đã cắt bỏ 100% các đoạn tác giả tự quảng cáo truyện mới, xin phiếu/hoa/donate ở đầu/cuối chương (nếu có) chưa? '
    'Nếu chưa đạt cần sửa lại'
)


def build_new_story_review_prompt(
    chapters: List[int],
    template: str = NEW_STORY_REVIEW_PROMPT_TEMPLATE
) -> str:
    """
    Tạo chuỗi prompt rà soát cho truyện mới ở lượt 2 (Prompt Chaining).

    Args:
        chapters: Danh sách các số chương vừa dịch
        template: Mẫu prompt tùy biến (mặc định lấy NEW_STORY_REVIEW_PROMPT_TEMPLATE)
    """
    if len(chapters) == 1:
        chapters_str = f"{chapters[0]}"
    else:
        chapters_str = f"{chapters[0]} đến {chapters[-1]}"

    return template.format(
        chapters_str=chapters_str
    )


# Mẫu prompt chuẩn cho AGY CLI tiền thẩm định ngữ nghĩa truyện mới (Pre-Translate Sanity Check)
DEFAULT_NEW_STORY_PRE_TRANSLATE_PROMPT_TEMPLATE = (
    "Bạn là Chuyên gia Thẩm định Ngữ nghĩa Dữ liệu Truyện Tiếng Trung & Tiếng Việt.\n"
    "Thư mục làm việc của bộ truyện: `{story_dir}`.\n\n"
    "THÔNG TIN ĐỢT KHỞI TẠO BỘ TRUYỆN MỚI:\n"
    "- Mã truyện: `{story_id}`\n"
    "- Dải chương dự kiến dịch: Từ Chương {start_chap} đến Chương {end_chap} (Tổng {num_chapters} chương: {chapters_range})\n"
    "- Danh sách các chương lấy mẫu thẩm định: {sample_chapters_str}\n\n"
    "NHIỆM VỤ CỦA BẠN:\n"
    "Hãy đọc skill /dich_truyen_web, sử dụng công cụ view_file để tự mở và đọc các file cần thiết trong thư mục:\n"
    "1. Đọc file `info.json` (nếu có) để nắm Tên truyện, Tác giả, Thể loại (genres/tags/category), và Văn án/Tóm tắt (description/intro).\n"
    "2. Đọc mở đầu các chương khởi động: `chapters/1/content.txt`, `chapters/2/content.txt`, `chapters/3/content.txt` (hoặc thư mục dạng chap_X).\n"
    "3. Đọc lướt chương chốt giữa: `chapters/{mid_chap}/content.txt` để kiểm tra tính nhất quán (chống crawler ghép nhầm truyện ở giữa).\n"
    "4. Đọc chương cán mốc: `chapters/{end_chap}/content.txt` để kiểm tra tính nguyên vẹn và phát hiện dấu hiệu Đại kết cục sớm.\n\n"
    "HÃY ĐÁNH GIÁ THEO NGUYÊN TẮC 'TƯƠNG THÍCH TIỀN ĐỀ & KHÔNG MÂU THUẪN TRIỆT TIÊU':\n"
    "- LƯU Ý QUAN TRỌNG: Chương 1-3 chỉ là phần mở đầu/khởi động của câu chuyện. Văn án thường chứa các diễn biến cao trào về sau. "
    "Bạn KHÔNG ĐƯỢC đòi hỏi Chương 1-3 phải chứa toàn bộ sự kiện trong văn án. Yêu cầu cốt lõi là: Đúng nhân vật chính, đúng tiền đề xuất phát điểm, "
    "và TUYỆT ĐỐI KHÔNG CÓ MÂU THUẪN TRIỆT TIÊU (ví dụ văn án cổ đại mà truyện hiện đại, văn án nam chính A mà truyện nam chính B không liên quan).\n\n"
    "🔴 QUY TẮC CẤP PHÉP DỊCH NGHIÊM NGẶT (CHỈ DUYỆT 2 TRƯỜNG HỢP SAU):\n"
    "1. Case 1 (Happy Case): `info.json` có khai báo thể loại (genre), đồng thời Thể loại + Nhân vật chính + Tiền đề cốt truyện trong `info.json` "
    "khớp và tương thích logic với nội dung raw Chương 1-3; raw sạch không paywall hay lặp chương -> Đặt `allowed_to_translate: true`, `validation_case: 'HAPPY_CASE'`.\n"
    "2. Case 2 (Khuyết Genre): `info.json` không có trường thể loại (genre rỗng/null/thiếu), nhưng Nhân vật chính và bối cảnh mở đầu tương thích với văn án; "
    "raw sạch -> Đặt `allowed_to_translate: true`, `validation_case: 'MISSING_GENRE_AUTO_DETECTED'`, tự động trích xuất `detected_genre` từ raw.\n\n"
    "🔴 TẤT CẢ CÁC TRƯỜNG HỢP CÒN LẠI BẮT BUỘC ĐẶT `allowed_to_translate: false`:\n"
    "- Xung đột Thể loại (`GENRE_MISMATCH`): `info.json` ghi một đằng (ví dụ 'Đô thị'), nhưng raw thực tế lại là một nẻo (ví dụ tu chân tiên hiệp cổ đại hoặc ngược lại).\n"
    "- Lệch Nhân vật / Cào nhầm truyện (`STORY_MISMATCH`): Nhân vật mở đầu hoàn toàn khác lạ, không liên quan đến văn án.\n"
    "- Lỗi Raw (`RAW_CORRUPT`): Chương 1-3 dính Paywall VIP ('chương chưa mở khóa', 'vui lòng nạp tiền'), thông báo tác giả xin nghỉ, "
    "file rỗng, hoặc các chương đầu bị cào trùng lặp y hệt nội dung của nhau.\n\n"
    "QUY ĐỊNH BẮT BUỘC VỀ 'report_brief':\n"
    "- Viết bằng tiếng Việt, dung lượng vừa phải (từ 2 đến 4 câu).\n"
    "- Nêu rõ bằng chứng cụ thể: Tên nhân vật chính phát hiện được, thể loại nhận diện, tình trạng raw để Editor có thể FORWARD cho ĐỘI CRAWLER sửa nguồn nếu lỗi.\n\n"
    "KẾT QUẢ ĐẦU RA:\n"
    "BẮT BUỘC tạo hoặc ghi đè file `{result_file}` với nội dung DUY NHẤT là một khối JSON hợp lệ theo đúng cấu trúc sau:\n"
    "```json\n"
    "{{\n"
    '  "allowed_to_translate": true,\n'
    '  "validation_case": "HAPPY_CASE",\n'
    '  "declared_genre": "Thể loại lấy từ info.json (hoặc Không khai báo)",\n'
    '  "detected_genre": "Thể loại thực tế suy luận từ raw",\n'
    '  "suggested_pronouns": "Ví dụ: Hắn - Ta / Anh - Em / Sư tôn - Đồ nhi",\n'
    '  "is_complete": false,\n'
    '  "is_short_story": false,\n'
    '  "report_brief": "Mô tả chi tiết và cụ thể tình trạng truyện theo hướng dẫn ở trên..."\n'
    "}}\n"
    "```\n\n"
    "Sau khi ghi file `{result_filename}`, bạn hãy kết thúc lượt làm việc ngay."
)


def build_new_story_pre_translate_prompt(
    story_dir: Path,
    chapters: List[int],
    story_info: dict,
    template: str = DEFAULT_NEW_STORY_PRE_TRANSLATE_PROMPT_TEMPLATE
) -> str:
    """
    Tạo chuỗi prompt tiền thẩm định ngữ nghĩa cho truyện mới (New Story Pre-Translate Sanity Check).
    Tự động tính toán các mốc lấy mẫu: Chương 1, 2, 3, Chốt giữa (N/2), Cán mốc (N).
    """
    from new_story_translator_daemon.config import format_chapter_ranges
    story_id = story_dir.name
    start_chap = chapters[0]
    end_chap = chapters[-1]
    num_chapters = len(chapters)

    # Tính toán danh sách chương lấy mẫu chiến lược (1, 2, 3, mid, end)
    sample_chaps = []
    for c in [start_chap, start_chap + 1, start_chap + 2]:
        if c in chapters and c not in sample_chaps:
            sample_chaps.append(c)

    mid_chap = chapters[num_chapters // 2]
    if mid_chap not in sample_chaps:
        sample_chaps.append(mid_chap)

    if end_chap not in sample_chaps:
        sample_chaps.append(end_chap)

    sample_chaps.sort()
    sample_chapters_str = ", ".join(f"Chương {c}" for c in sample_chaps)
    chapters_range_str = format_chapter_ranges(chapters, arrow="➔")
    result_file = str((story_dir / "pre_check_result.json").resolve())

    return template.format(
        story_id=story_id,
        story_dir=str(story_dir),
        start_chap=start_chap,
        end_chap=end_chap,
        num_chapters=num_chapters,
        chapters_range=chapters_range_str,
        sample_chapters_str=sample_chapters_str,
        mid_chap=mid_chap,
        result_file=result_file,
        result_filename="pre_check_result.json"
    )


