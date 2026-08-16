"""Deterministic markdown scanner (paper Alg. 1 line 1, Appendix B.2).

Parses front matter, headings, nested lists, code blocks, tables, and file
references into blocks with stable provenance IDs *before* any model is used.
Code fences and tables stay atomic (splitting them can destroy a template or
schema). Markdown nesting supplies an initial scope tree; numbered lists and
temporal markers are recorded as high-confidence workflow hints.

No model, no task access.
"""
from __future__ import annotations

import hashlib
import re
from typing import List, Tuple

from .contract import Block

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_BULLET = re.compile(r"^(\s*)(?:[-*+]|(\d+)[.)])\s+(.*)$")
_FENCE = re.compile(r"^\s*(```+|~~~+)")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_ORDINAL = re.compile(r"^\s*(\d+)[.)]\s")
_TEMPORAL = re.compile(r"\b(first|then|next|after|before|finally|step\s*\d+|"
                       r"once|when done)\b", re.I)


def _bid(norm_text: str, heading_path: List[str]) -> str:
    """Stable id = hash(normalized text + ancestor headings) (B.2). Line
    numbers are stored separately so unrelated insertions do not invalidate
    provenance."""
    key = "\u0001".join(heading_path) + "\u0002" + re.sub(r"\s+", " ", norm_text.lower()).strip()
    return "b" + hashlib.sha1(key.encode()).hexdigest()[:10]


def scan(text: str) -> List[Block]:
    lines = (text or "").splitlines()
    blocks: List[Block] = []
    heading_path: List[str] = []
    i = 0
    n = len(lines)

    # YAML front matter
    if i < n and lines[i].strip() == "---":
        j = i + 1
        while j < n and lines[j].strip() != "---":
            j += 1
        fm = "\n".join(lines[i:min(j + 1, n)])
        blocks.append(Block(_bid(fm, ["frontmatter"]), "frontmatter",
                            ["frontmatter"], fm, (i + 1, j + 1), 0))
        i = j + 1

    para: List[str] = []
    para_start = 0

    def flush_para():
        nonlocal para, para_start
        if not para:
            return
        chunk = "\n".join(para).strip()
        if chunk:
            blocks.append(Block(_bid(chunk, heading_path), "paragraph",
                                list(heading_path), chunk,
                                (para_start + 1, para_start + len(para)),
                                len(heading_path)))
        para = []

    while i < n:
        line = lines[i]

        m = _HEADING.match(line)
        if m:
            flush_para()
            level = len(m.group(1))
            title = m.group(2).strip()
            heading_path = heading_path[:level - 1] + [title]
            blocks.append(Block(_bid(title, heading_path), "heading",
                                list(heading_path), title, (i + 1, i + 1), level))
            i += 1
            continue

        f = _FENCE.match(line)
        if f:
            flush_para()
            fence = f.group(1)[0] * 3
            start = i
            body = [line]
            i += 1
            while i < n and not lines[i].strip().startswith(fence):
                body.append(lines[i])
                i += 1
            if i < n:
                body.append(lines[i])
                i += 1
            chunk = "\n".join(body)
            blocks.append(Block(_bid(chunk, heading_path), "code",
                                list(heading_path), chunk,
                                (start + 1, i), len(heading_path)))
            continue

        if _TABLE_ROW.match(line):
            flush_para()
            start = i
            body = []
            while i < n and _TABLE_ROW.match(lines[i]):
                body.append(lines[i])
                i += 1
            chunk = "\n".join(body)
            blocks.append(Block(_bid(chunk, heading_path), "table",
                                list(heading_path), chunk,
                                (start + 1, i), len(heading_path)))
            continue

        b = _BULLET.match(line)
        if b:
            flush_para()
            indent = len(b.group(1))
            ordinal = b.group(2)
            content = b.group(3).strip()
            # gather continuation lines (deeper indented, non-bullet)
            start = i
            i += 1
            cont: List[str] = []
            while i < n:
                nxt = lines[i]
                if not nxt.strip():
                    break
                if _BULLET.match(nxt) or _HEADING.match(nxt) or _FENCE.match(nxt):
                    break
                if len(nxt) - len(nxt.lstrip()) > indent:
                    cont.append(nxt.strip())
                    i += 1
                else:
                    break
            full = content + ((" " + " ".join(cont)) if cont else "")
            depth = len(heading_path) + (indent // 2) + 1
            blk = Block(_bid(full, heading_path + [full[:40]]), "list_item",
                        list(heading_path), full, (start + 1, i), depth)
            blocks.append(blk)
            continue

        if line.strip():
            if not para:
                para_start = i
            para.append(line)
            i += 1
        else:
            flush_para()
            i += 1

    flush_para()
    return blocks


def workflow_hint(block: Block) -> bool:
    """High-confidence workflow signal: ordered list item or temporal marker."""
    return bool(_ORDINAL.match(block.text) or _TEMPORAL.search(block.text))


def file_references(text: str) -> List[str]:
    """Referenced files a skill may point to (paper: 'files referenced by S')."""
    refs = re.findall(r"\[[^\]]*\]\(([^)]+)\)", text or "")
    refs += re.findall(r"\b([\w./-]+\.(?:md|json|ya?ml|py|txt|csv))\b", text or "")
    seen, out = set(), []
    for r in refs:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out
