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
    '- Mỗi batch: translator_subagent dịch và ghi toàn bộ file content_vi.txt, sau đó qc_auditor_subagent thẩm định QC '
    'đạt chuẩn mới được chuyển sang batch kế tiếp. '
    '- Kế thừa và cập nhật liên tục glossary.json và summary.txt sau mỗi batch. '
    'Tiêu chí nghiệm thu hoàn thành: '
    '(1) Đã tạo đầy đủ {num_chapters} file content_vi.txt trong các thư mục chương tương ứng tại "{story_dir}/chapters/", '
    'sạch 100% chữ Hán và không chứa bất kỳ thẻ HTML nào (<p>, </p>, <br>); '
    '(2) Dòng đầu tiên của mỗi file content_vi.txt bắt buộc theo định dạng "Chương X: [Tiêu đề]" (nếu raw gốc thiếu tiêu đề '
    'thì tự suy luận tiêu đề ngắn gọn 3-8 từ phù hợp theo nội dung chương phục vụ nạp CSDL); '
    '(3) Tuân thủ 4 nguyên lý dịch mượt mà, khử triệt để từ ngữ convert, Hán-Việt lỗi thời và tiếng lóng mạng Trung Quốc; '
    '(4) Bản dịch không bị cắt cụt, cắt gọt hay tóm tắt so với bản gốc (tỷ lệ ký tự đạt chuẩn); '
    '(5) Khởi tạo hoàn chỉnh file glossary.json và summary.txt trong thư mục truyện phục vụ cho các phiên dịch tiếp theo; '
    '(6) 🔴 Tự động loại bỏ 100% rác quảng cáo, dự thu văn truyện mới, lời tác giả xin phiếu/hoa/donate/bình chọn ở đầu hoặc cuối chương (nếu có); chỉ dịch trọn vẹn phần nội dung cốt truyện chính.'
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

