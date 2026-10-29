import base64
import binascii
import re
import unicodedata

ZERO_WIDTH = re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff]")
B64_PATTERN = re.compile(r"(?:[A-Za-z0-9+/]{4}){2,}(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?")

PROBE_PATTERNS = [
    r"\b(what|which)\s+(model|llm|ai)\s+(are you|is this|do you use)\b",
    r"\b(who|what)\s+(are you|is your (name|model|version))\b",
    r"\b(your|the)\s+(system prompt|training data|knowledge cutoff)\b",
    r"\b(are you|is this)\s+(gpt|claude|gemini|llama|qwen|deepseek)\b",
    r"\breveal\s+(your|the)\s+(identity|model name|instructions)\b",
]


def normalize_prompt(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = ZERO_WIDTH.sub("", text)

    def try_b64(m):
        try:
            decoded = base64.b64decode(m.group(0)).decode("utf-8", errors="ignore")
            if re.search(r"[A-Za-z]{3,}", decoded):
                return " " + decoded + " "
        except (binascii.Error, ValueError):
            pass
        return m.group(0)

    text = B64_PATTERN.sub(try_b64, text)
    return re.sub(r"\s+", " ", text.lower()).strip()


def classify_probe(raw_prompt: str) -> str:
    norm = normalize_prompt(raw_prompt)
    hits = [p for p in PROBE_PATTERNS if re.search(p, norm)]
    if not hits:
        return "clean"
    return "probe_hard" if len(norm.split()) < 30 else "probe_soft"
