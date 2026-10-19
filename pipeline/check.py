#!/usr/bin/env python3
"""Content checks on build/*.json (run build.py first). Exits 1 on any problem.

1. ★ must mark exactly the official answer: every '**X｜…★…**' option label is starred, and the
   starred set must equal the answer key (disputed options are starred too; the ⚠️ flag explains).
2. Markdown sanity: no line with an odd number of '**'; every table keeps one column count.
3. flag / src fields: no odd '**'.
"""
import json
import re
import sys

from common import ROOT


def main():
    bad = 0
    files = sorted(p for p in (ROOT / "build").glob("*.json") if p.name != "banks.json")
    if not files:
        print("no build output — run pipeline/build.py first"); return 1
    for f in files:
        for q in json.loads(f.read_text(encoding="utf-8"))["questions"]:
            exp = q.get("exp")
            if not exp:
                continue
            starred = {m.group(1) for m in re.finditer(r"\*\*([A-E])[｜|]((?:(?!\*\*)[^\n])*)\*\*", exp) if "★" in m.group(2)}
            if starred != set(q["answer"]):
                print(f"{q['id']}: answer {''.join(sorted(q['answer']))} but ★ on {''.join(sorted(starred)) or '-'}"); bad += 1
            lines = exp.split("\n")
            for ln in lines:
                if ln.count("**") % 2:
                    print(f"{q['id']}: odd ** in line: {ln[:60]}"); bad += 1
            tbl = []
            for ln in lines + [""]:
                if ln.strip().startswith("|"):
                    tbl.append(ln)
                elif tbl:
                    cols = [len(r.strip().strip("|").split("|")) for r in tbl]
                    if len(set(cols)) > 1:
                        print(f"{q['id']}: table column counts differ {cols}"); bad += 1
                    tbl = []
            if "**解析**" not in exp:
                print(f"{q['id']}: missing **解析** section"); bad += 1
            for fld in ("flag", "src"):
                if q.get(fld, "").count("**") % 2:
                    print(f"{q['id']}: odd ** in {fld}"); bad += 1
    print("check problems:", bad)
    return bad


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
