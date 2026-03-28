import re
from collections import Counter
from typing import Iterable

STOPWORDS = {
    "的",
    "和",
    "或",
    "与",
    "及",
    "在",
    "对",
    "有",
    "为",
    "并",
    "能",
    "可",
    "将",
    "是",
    "负责",
    "要求",
    "以上",
    "至少",
    "我们",
    "你",
    "the",
    "and",
    "or",
    "with",
    "for",
    "to",
    "of",
    "in",
    "on",
    "a",
    "an",
    "is",
    "are",
    "be",
    "experience",
    "year",
    "years",
    "plus",
}

TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9+#._-]*|[\u4e00-\u9fff]{2,}")


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_PATTERN.findall(text)]


def extract_keywords(text: str, top_n: int = 15) -> list[str]:
    counter = Counter()
    for token in tokenize(text):
        if token in STOPWORDS:
            continue
        if len(token) < 2:
            continue
        counter[token] += 1
    return [k for k, _ in counter.most_common(top_n)]


def pick_lines(text: str, hints: Iterable[str], limit: int = 5) -> list[str]:
    rows = [line.strip(" -•\t") for line in text.splitlines() if line.strip()]
    selected: list[str] = []
    for row in rows:
        lower_row = row.lower()
        if any(h in lower_row for h in hints):
            selected.append(row)
        if len(selected) >= limit:
            break
    return selected


def compute_match_score(target_keywords: list[str], source_text: str) -> tuple[list[str], list[str], int]:
    source_tokens = set(tokenize(source_text))
    matched = [k for k in target_keywords if k.lower() in source_tokens]
    missing = [k for k in target_keywords if k.lower() not in source_tokens]
    score = int((len(matched) / max(len(target_keywords), 1)) * 100)
    return matched, missing, score