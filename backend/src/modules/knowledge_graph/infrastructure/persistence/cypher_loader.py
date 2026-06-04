"""Load .cypher files at runtime (LEGAL_KG_PIPELINE.md rule 10).

Two layouts are supported:
  * statement files (e.g. schema.cypher) — split on ';'.
  * named-section files — each section starts with a `// @name` marker line.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

_CYPHER_DIR = Path(__file__).resolve().parent / "cypher"
_SECTION_RE = re.compile(r"^//\s*@(\w+)\s*$")


def _read(filename: str) -> str:
    path = _CYPHER_DIR / filename
    return path.read_text(encoding="utf-8")


@lru_cache(maxsize=None)
def load_statements(filename: str) -> tuple[str, ...]:
    """Return individual statements (split on ';'), comments/blank stripped."""
    raw = _read(filename)
    stmts: list[str] = []
    for chunk in raw.split(";"):
        lines = [
            ln for ln in chunk.splitlines() if ln.strip() and not ln.strip().startswith("//")
        ]
        stmt = "\n".join(lines).strip()
        if stmt:
            stmts.append(stmt)
    return tuple(stmts)


@lru_cache(maxsize=None)
def load_sections(filename: str) -> dict[str, str]:
    """Return {section_name: cypher} for a `// @name`-delimited file.

    A trailing ';' on the last statement of a section is stripped.
    """
    raw = _read(filename)
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in raw.splitlines():
        m = _SECTION_RE.match(line.strip())
        if m:
            current = m.group(1)
            sections[current] = []
            continue
        if current is None:
            continue
        if line.strip().startswith("//"):
            continue
        sections[current].append(line)
    return {
        name: "\n".join(body).strip().rstrip(";").strip()
        for name, body in sections.items()
        if "\n".join(body).strip()
    }
