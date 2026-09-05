from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class TranslationOutput(BaseModel):
    chapter_title_vi: str = Field(description="Tiêu đề chương dịch mượt sang Tiếng Việt")
    translated_content: str = Field(description="Nội dung toàn bộ chương đã mượt hóa Tiếng Việt (Plain Text)")
    extracted_new_terms: Dict[str, str] = Field(default_factory=dict, description="Các thuật ngữ/tên riêng mới xuất hiện")
    chapter_summary: str = Field(default="", description="Tóm tắt 2-3 câu ngắn gọn về diễn biến chính của chương")

class QCIssueItem(BaseModel):
    original_sentence: str = Field(description="Trích dẫn câu lỗi hoặc thô trong bản dịch")
    issue_type: str = Field(description="Loại lỗi: HTML, Chinese, Convert, Structure, DynamicPronoun")
    corrected_sentence: str = Field(description="Câu đã được sửa lại mượt mà")

class QCOutput(BaseModel):
    qc_score: float = Field(description="Điểm QC chất lượng bản dịch từ 0.0 đến 10.0")
    status: str = Field(description="Trạng thái: PASSED hoặc REJECTED")
    has_chinese_characters: bool = Field(description="Còn rác chữ Hán hay không")
    has_html_tags: bool = Field(description="Còn dính thẻ HTML (<p>, </p>, <br>) hay không")
    issues: List[QCIssueItem] = Field(default_factory=list, description="Danh sách các lỗi được phát hiện và trích dẫn sửa lại")

class ChineseCleanupOutput(BaseModel):
    cleaned_title: str = Field(description="Tiêu đề đã được dọn sạch chữ Hán")
    cleaned_content: str = Field(description="Nội dung đã được dọn sạch chữ Hán (Plain Text)")

class ChapterCheckpoint(BaseModel):
    chapter_num: int
    step: str = Field(description="Trạng thái mốc: INGESTED -> GLOSSARY_SLOTTED -> TRANSLATED -> QC_AUDITED -> COMMITTED")
    chapter_title: str = ""
    updated_at: str = ""
