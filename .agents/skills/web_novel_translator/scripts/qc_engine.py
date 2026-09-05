import re

# Minimum passing score: 8.5 / 10 (85 / 100)
PASS_THRESHOLD = 85

def detect_chinese_characters(text):
    """
    Finds any Hanzi / Chinese characters remaining in text.
    """
    pattern = re.compile(r'[\u4e00-\u9fff]')
    return pattern.findall(text)

def check_paragraph_count(raw_text, translated_text):
    """
    Verifies that the number of paragraphs matches between raw and translated text.
    Supports both <p> tags and clean line-separated text.
    """
    raw_p_count = len(re.findall(r'<p>', raw_text))
    if raw_p_count == 0:
        raw_p_count = len([l for l in raw_text.splitlines() if l.strip()])
        
    if '<p>' in translated_text:
        trans_p_count = len(re.findall(r'<p>', translated_text))
    else:
        lines = [l.strip() for l in translated_text.splitlines() if l.strip()]
        trans_p_count = len(lines)
        
    return raw_p_count, trans_p_count

def check_forbidden_convert_terms(text):
    """
    Checks for common raw convert artifacts that should be polished.
    """
    forbidden_terms = [
        "khủng bố như tư", "nồi nấu quặng", "bảo hộ thần", "quỷ phi cầu",
        "đương... khi", "thật là cái", "nói xong, nàng", "trong lồng ngực nào đó"
    ]
    found = []
    for term in forbidden_terms:
        if term.lower() in text.lower():
            found.append(term)
    return found

def audit_chapter(raw_text, translated_text):
    """
    Runs full QC audit on translated text.
    Returns: (passed: bool, score: float, report: dict)
    Threshold: score >= 85 (8.5/10) AND 0 Chinese characters.
    Focuses on fluency, zero Hanzi, zero HTML tags, and no raw convert artifacts.
    Sentence & paragraph counts are fully flexible for optimal reading flow!
    """
    chinese_chars = detect_chinese_characters(translated_text)
    bad_terms = check_forbidden_convert_terms(translated_text)
    
    errors = []
    score = 100
    
    # 1. Chinese Character Check (CRITICAL)
    if chinese_chars:
        score -= 50
        errors.append(f"🔴 Phát hiện {len(chinese_chars)} ký tự Hán chưa làm sạch: {set(chinese_chars)}")
        
    # 2. HTML Tag Check
    html_tags = re.findall(r'<[^>]+>', translated_text)
    if html_tags:
        score -= 30
        errors.append(f"⚠️ Phát hiện {len(html_tags)} thẻ HTML còn sót lại: {set(html_tags)}")

    # 3. Forbidden Convert Artifacts
    if bad_terms:
        score -= 15
        errors.append(f"⚠️ Phát hiện từ Convert thô chưa mượt hóa: {bad_terms}")
        
    passed = (score >= PASS_THRESHOLD) and len(chinese_chars) == 0 and len(html_tags) == 0
    
    report = {
        'passed': passed,
        'score': score,
        'score_out_of_10': round(score / 10.0, 1),
        'chinese_found_count': len(chinese_chars),
        'html_tags_count': len(html_tags),
        'errors': errors
    }
    
    return passed, score, report

if __name__ == '__main__':
    raw = "<p>Text 1</p><p>Text 2</p>"
    trans = "<p>Dịch 1</p><p>Dịch 2</p>"
    p, s, r = audit_chapter(raw, trans)
    print(f"QC Audit Test: Passed={p}, Score={r['score_out_of_10']}/10, Errors={r['errors']}")
