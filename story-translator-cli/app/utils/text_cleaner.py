import re

# Regex matching Chinese character ranges
CHINESE_CHAR_REGEX = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\U00020000-\U0002a6df]')
HTML_TAG_REGEX = re.compile(r'<[^>]+>')

# Regex matching non-standard Kaomojis / ascii emoji symbols that break JSON escaping
KAOMOJI_REGEX = re.compile(
    r'\([^\)]*[\u2500-\u257f\u2200-\u22ff\u2600-\u26ff\u2700-\u27bf\u3000-\u303f\u0250-\u02af\u0370-\u03ff\u1d00-\u1d7f\u2000-\u206f\u2100-\u214f\uA900-\uA97F\u0E00-\u0E7F][^\)]*\)'
)

def contains_chinese(text: str) -> bool:
    """Returns True if text contains Chinese Hanzi characters."""
    return bool(CHINESE_CHAR_REGEX.search(text))

def clean_kaomojis(text: str) -> str:
    """Removes complex webnovel kaomojis like (ꐦÒ‸Ó), ＼(`Δ’)／ to prevent LLM JSON escaping issues."""
    if not text:
        return ""
    return KAOMOJI_REGEX.sub('', text)

def remove_html_tags(text: str) -> str:
    """Strips all HTML tags such as <p>, </p>, <br> leaving pure plain text."""
    if not text:
        return ""
    cleaned = HTML_TAG_REGEX.sub('', text)
    lines = [line.strip() for line in cleaned.splitlines()]
    return '\n\n'.join(line for line in lines if line)

def clean_plain_text(text: str) -> str:
    """Completely sanitizes text to plain text format."""
    text = clean_kaomojis(text)
    text = remove_html_tags(text)
    lines = text.splitlines()
    cleaned_lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in lines]
    return '\n'.join(line for line in cleaned_lines if line)

def extract_and_strip_chinese(text: str) -> tuple[str, list[str]]:
    """Strips all Chinese characters using Regex and returns (cleaned_text, list_of_removed_chars)."""
    if not text:
        return "", []
    found_chars = CHINESE_CHAR_REGEX.findall(text)
    cleaned_text = CHINESE_CHAR_REGEX.sub('', text)
    # Clean any residual double spaces left behind by stripped characters
    lines = cleaned_text.splitlines()
    cleaned_lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in lines]
    final_text = '\n'.join(line for line in cleaned_lines if line)
    return final_text, list(set(found_chars))

