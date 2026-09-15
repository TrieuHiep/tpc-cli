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
    '(đối với danh sách trên: gom thành các cụm {batch_size} chương tuần tự), mỗi batch hoàn thành ghi toàn bộ '
    'các file content_vi.txt tương ứng và QC nghiệm thu rồi mới chuyển sang batch tiếp theo theo đúng chuẩn AGENTS.md và skill dich_truyen_web. '
    'Tiêu chí nghiệm thu hoàn thành: '
    '(1) Đã tạo đầy đủ {num_chapters} file content_vi.txt trong các thư mục chương tương ứng tại "{story_dir}/chapters/", sạch 100% chữ Hán và thẻ HTML; '
    '(2) Dòng đầu tiên của mỗi file content_vi.txt bắt buộc theo định dạng "Chương X: [Tiêu đề]" (nếu truyện gốc thiếu tiêu đề thì tự động suy luận tiêu đề ngắn gọn 3-8 từ phù hợp theo nội dung chương phục vụ nạp CSDL); '
    '(3) Tuân thủ 4 nguyên lý dịch và quy chuẩn của skill dich_truyen_web; '
    '(4) Bản dịch các chương không bị cắt cụt, cắt gọt so với bản gốc; '
    '(5) Câu văn dịch mượt mà, tự nhiên, gãy gọn theo nghĩa tiếng Việt, ý nghĩa không bị lủng củng; '
    '(6) 🔴 Tự động loại bỏ 100% rác quảng cáo, dự thu văn truyện mới, lời tác giả xin phiếu/hoa/donate/bình chọn ở đầu hoặc cuối chương (nếu có); chỉ dịch trọn vẹn phần nội dung cốt truyện chính.'
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


# Mẫu prompt chuẩn cho AGY CLI lượt 2 (Prompt Chaining) thực hiện tổng rà soát và tự động hiệu đính
DEFAULT_REVIEW_PROMPT_TEMPLATE = (
    '/goal Rà soát lại 1 lần nữa xem các chương {chapters_str}  đã đạt tiêu chuẩn QC của /dich_truyen_web chưa, có bị cắt gọt nội dung không, '
    'và mạch truyện có logic không, câu văn dịch có bị lủng củng không, '
    'đã cắt bỏ 100% các đoạn tác giả tự quảng cáo truyện mới, xin phiếu/hoa/donate ở đầu/cuối chương (nếu có) chưa? '
    'từ chapter đầu đến chapter cuối. Nếu chưa đạt cần sửa lại'
)


def build_review_prompt(
    chapters: List[int],
    template: str = DEFAULT_REVIEW_PROMPT_TEMPLATE
) -> str:
    """
    Tạo chuỗi prompt /goal rà soát cho lượt 2 (Prompt Chaining).

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


