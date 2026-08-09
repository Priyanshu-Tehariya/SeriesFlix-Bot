import re

def normalize_query(text: str) -> str:
    if not text:
        return ""
    # Lowercase, strip surrounding whitespace, and normalize multiple spaces/punctuation
    text = text.lower().strip()
    # Replace punctuation with a space
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
