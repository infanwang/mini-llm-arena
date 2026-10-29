import re


def extract_style(text: str) -> dict:
    tokens = len(re.findall(r"\S+", text))
    headers = len(re.findall(r"^#{1,6}\s+", text, re.M))
    bold = len(re.findall(r"\*\*[^*]+\*\*", text))
    lists = len(re.findall(r"^\s*[-*+]\s+", text, re.M))
    md_count = headers + bold + lists
    return {
        "token_length": tokens,
        "markdown_density": md_count / max(tokens, 1),
        "header_count": headers,
        "bold_count": bold,
        "list_count": lists,
    }
