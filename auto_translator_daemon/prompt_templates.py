"""
Prompt templates module for Auto Translator Daemon.
Nơi quản lý tập trung toàn bộ mẫu câu lệnh prompt gửi cho AGY CLI.
"""
from pathlib import Path
from typing import List

# Mẫu prompt chuẩn cho AGY CLI sử dụng /goal và skill /dich_truyen_web
DEFAULT_GOAL_PROMPT_TEMPLATE = (
    '/goal Dịch tiếp truyện {story_id}: sử dụng /dich_truyen_web để dịch truyện "{story_dir}", '
    'các chương cần dịch: {chapters_to_translate}. '
    'Quy tắc phân bổ Subagent: Bắt buộc phân bổ Subagent dịch và QC theo từng batch = {batch_size} chương/session '
    '(đối với danh sách trên: gom thành các cụm {batch_size} chương tuần tự). '
    'BẮT BUỘC khi gọi define_subagent cho translator_subagent và qc_auditor_subagent phải đặt enable_write_tools: true '
    'để subagents có công cụ trực tiếp lưu và sửa file content_vi.txt. '
    'Mỗi batch hoàn thành ghi lần lượt từng file content_vi.txt tương ứng và QC nghiệm thu rồi mới chuyển sang batch tiếp theo theo đúng chuẩn AGENTS.md và skill dich_truyen_web. '
    '🔴 CHỈ THỊ THỰC THI HEADLESS CLI NON-INTERACTIVE (QUAN TRỌNG NHẤT): '
    '- CẤM TUYỆT ĐỐI xuất tin nhắn văn bản trung gian sau khi gọi invoke_subagent. Im lặng kết thúc lượt công cụ để CLI chờ nhận thông điệp phản hồi từ subagent. '
    '- Thực hiện liên tục không dừng qua toàn bộ các batch cho đến khi tạo đủ {num_chapters} file content_vi.txt. '
    'Tiêu chí nghiệm thu hoàn thành: '
    '(1) Đã tạo đầy đủ {num_chapters} file content_vi.txt trong các thư mục chương tương ứng tại "{story_dir}/chapters/", sạch 100% chữ Hán và thẻ HTML; '
    '(2) Dòng đầu tiên của mỗi file content_vi.txt bắt buộc theo định dạng "Chương X: [Tiêu đề]" (nếu truyện gốc thiếu tiêu đề thì tự động suy luận tiêu đề ngắn gọn 3-8 từ phù hợp theo nội dung chương phục vụ nạp CSDL); '
    '(3) Tuân thủ 4 nguyên lý dịch và quy chuẩn của skill dich_truyen_web; '
    '(4) Bản dịch các chương không bị cắt cụt, cắt gọt so với bản gốc; '
    '(5) Câu văn dịch mượt mà, tự nhiên, gãy gọn theo nghĩa tiếng Việt, ý nghĩa không bị lủng củng; '
    '(6) 🔴 Tự động loại bỏ 100% rác quảng cáo, dự thu văn truyện mới, lời tác giả xin phiếu/hoa/donate/bình chọn ở đầu hoặc cuối chương (nếu có); chỉ dịch trọn vẹn phần nội dung cốt truyện chính; '
    '(7) Chỉ xuất Báo Cáo Nghiệm Thu Tổng Kết kèm thẻ <!-- GOAL_COMPLETE --> ở cuối cùng khi 100% {num_chapters} file content_vi.txt đã tồn tại trên đĩa.'
)


def build_goal_prompt(
    story_id: str,
    story_dir: Path,
    chapters: List[int],
    batch_size: int = 10,
    template: str = DEFAULT_GOAL_PROMPT_TEMPLATE
) -> str:
    """
    Tạo chuỗi prompt /goal hoàn chỉnh từ template và các tham số đầu vào.

    Args:
        story_id: Mã định danh truyện (ID)
        story_dir: Đường dẫn thư mục cục bộ của truyện
        chapters: Danh sách các số chương cần dịch
        batch_size: Kích thước batch cho mỗi Subagent session (mặc định 10; nếu < 10 chương tự động ép về 1)
        template: Mẫu prompt tùy biến (mặc định lấy DEFAULT_GOAL_PROMPT_TEMPLATE)
    """
    # Nếu tổng số chương cần dịch < 10, tự động phân bổ 1 Chapter = 1 Session theo chuẩn AGENTS.md
    effective_batch_size = 1 if len(chapters) < 10 else batch_size
    return template.format(
        story_id=story_id,
        story_dir=str(story_dir),
        chapters_to_translate=chapters,
        num_chapters=len(chapters),
        batch_size=effective_batch_size
    )


# Mẫu prompt tiếp tục dịch (Resume Prompt) khi phiên bị ngắt quãng giữa chừng
DEFAULT_RESUME_PROMPT_TEMPLATE = (
    'Tiếp tục dịch các chương còn thiếu của truyện {story_id}: '
    'Hiện tại các chương sau chưa có file content_vi.txt hoặc bị gián đoạn: {missing_chapters_str} (tổng cộng {num_missing} chương). '
    'Hãy kế thừa glossary.json và summary.txt hiện có tại "{story_dir}", tiếp tục phân bổ translator_subagent và qc_auditor_subagent '
    '(với enable_write_tools=True) theo batch {batch_size} chương để dịch và hoàn thành toàn bộ các chương còn thiếu này. '
    '🔴 CẤM xuất tin nhắn trung gian sau khi invoke_subagent. Mỗi chương bắt buộc lưu vào "{story_dir}/chapters/[Chương]/content_vi.txt" '
    '(dòng 1: Chương X: [Tiêu đề suy luận], sạch 100% chữ Hán và thẻ HTML). '
    'Chỉ xuất Báo Cáo Nghiệm Thu kèm thẻ <!-- GOAL_COMPLETE --> khi toàn bộ {num_missing} chương còn thiếu đã hoàn thành.'
)


def build_resume_prompt(
    story_id: str,
    story_dir: Path,
    missing_chapters: List[int],
    batch_size: int = 10,
    template: str = DEFAULT_RESUME_PROMPT_TEMPLATE
) -> str:
    """
    Tạo chuỗi prompt khôi phục phiên để dịch tiếp các chương còn thiếu.
    """
    from auto_translator_daemon.config import format_chapter_ranges
    missing_str = format_chapter_ranges(missing_chapters)
    effective_batch_size = 1 if len(missing_chapters) < 10 else batch_size

    return template.format(
        story_id=story_id,
        story_dir=str(story_dir),
        missing_chapters_str=missing_str,
        num_missing=len(missing_chapters),
        batch_size=effective_batch_size
    )


# Mẫu prompt chuẩn cho AGY CLI lượt 2 (Prompt Chaining) thực hiện tổng rà soát và tự động hiệu đính
DEFAULT_REVIEW_PROMPT_TEMPLATE = (
    'Rà soát lại 1 lần nữa xem các chương {chapters_str} đã đạt tiêu chuẩn QC của /dich_truyen_web chưa, có bị cắt gọt nội dung không, '
    'và mạch truyện có logic không, câu văn dịch có bị lủng củng không, '
    'đã cắt bỏ 100% các đoạn tác giả tự quảng cáo truyện mới, xin phiếu/hoa/donate ở đầu/cuối chương (nếu có) chưa? '
    'Nếu chưa đạt cần sửa lại'
)


def build_review_prompt(
    chapters: List[int],
    template: str = DEFAULT_REVIEW_PROMPT_TEMPLATE
) -> str:
    """
    Tạo chuỗi prompt rà soát cho lượt 2 (Prompt Chaining).

    Args:
        chapters: Danh sách các số chương vừa dịch
        template: Mẫu prompt tùy biến (mặc định lấy DEFAULT_REVIEW_PROMPT_TEMPLATE)
    """
    if len(chapters) == 1:
        chapters_str = f"{chapters[0]}"
    else:
        chapters_str = f"{chapters[0]} đến {chapters[-1]}"

    return template.format(
        chapters_str=chapters_str
    )


