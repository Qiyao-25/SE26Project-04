#!/usr/bin/env python3
"""H027/H028 自检（Arxiv/uml 扁平布局）。"""

from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = [
    "pipeline-activity.md",
    "pipeline-sequence.md",
    "DEPENDENCY.md",
    "README.md",
]


def main() -> int:
    print("H027/H028 UML check (Arxiv/uml V1.1)")
    ok = True
    for name in FILES:
        path = HERE / name
        if not path.exists():
            print(f"[MISS] {name}")
            ok = False
            continue
        text = path.read_text(encoding="utf-8")
        print(f"[OK] {name}: mermaid={len(re.findall(r'```mermaid', text))}, plantuml={len(re.findall(r'@startuml', text))}")
    activity = (HERE / "pipeline-activity.md").read_text(encoding="utf-8")
    sequence = (HERE / "pipeline-sequence.md").read_text(encoding="utf-8")
    for label, passed in [
        ("ParseTask", "ParseTask" in activity),
        ("page_no", "page_no" in activity),
        ("wiki_triple", "wiki_triple" in activity or "wiki_triple" in sequence),
        ("ApiResponse", "ApiResponse" in activity or "ApiResponse" in sequence),
    ]:
        print(f"{'PASS' if passed else 'FAIL'}: {label}")
        ok = ok and passed
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
