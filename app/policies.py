"""Read policies each request so edits invalidate old answers."""
import hashlib
import re
from pathlib import Path


def load_policies(path: Path) -> tuple[str, str, dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    sections = {}
    for title, body in re.findall(r"^## ([^\n]+)\n(.*?)(?=^## |\Z)", text, re.M | re.S):
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        sections[slug] = body.strip()
    if not sections:
        raise ValueError("policies.md must contain at least one ## policy heading")
    return text, hashlib.sha256(text.encode()).hexdigest(), sections
