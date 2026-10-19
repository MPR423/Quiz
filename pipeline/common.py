"""Shared helpers: repo paths, bank discovery, explanation-file parsing."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANKS_DIR = ROOT / "banks"
HEADER_KEYS = ("sub", "conf", "flag", "src")


def load_taxonomy():
    return json.loads((ROOT / "taxonomy.json").read_text(encoding="utf-8"))


def load_banks():
    """All banks, ordered by meta.order then id. Each meta gets a private '_dir' Path."""
    banks = []
    for meta_path in sorted(BANKS_DIR.glob("*/meta.json")):
        m = json.loads(meta_path.read_text(encoding="utf-8"))
        m["_dir"] = meta_path.parent
        if m.get("id") != meta_path.parent.name:
            raise SystemExit(f"ERR {meta_path}: id '{m.get('id')}' must equal folder name '{meta_path.parent.name}'")
        banks.append(m)
    return sorted(banks, key=lambda m: (m.get("order", 999), m["id"]))


def get_bank(bank_id):
    for b in load_banks():
        if b["id"] == bank_id:
            return b
    raise SystemExit(f"no bank '{bank_id}' (have: {', '.join(b['id'] for b in load_banks())})")


def load_questions(bank):
    return json.loads((bank["_dir"] / "questions.json").read_text(encoding="utf-8"))


def qid(bank, no):
    return f"{bank['id']}-{int(no):03d}"


def parse_exp_dir(bank):
    """Parse banks/<id>/exp/*.md. Returns (blocks, errors) where blocks[qid] = {meta, body, file}.

    Block format:
        @@ <bank>-<NNN>
        sub: ...        (optional when the bank has sub_default)
        conf: 高|中|低
        flag: ...       (optional)
        src: ...        (optional)
        ---
        markdown body
    """
    blocks, errors = {}, 0
    for path in sorted((bank["_dir"] / "exp").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT)
        for chunk in re.split(r"(?m)^@@\s+", text)[1:]:
            head, sep, body = chunk.partition("\n---\n")
            lines = head.strip().split("\n")
            q = lines[0].strip()
            if not sep:
                print(f"ERR {q}: no '---' line between header and body in {rel}"); errors += 1
            if not q.startswith(bank["id"] + "-"):
                print(f"ERR {q}: block id does not belong to bank '{bank['id']}' ({rel})"); errors += 1
            meta = {}
            for ln in lines[1:]:
                if not ln.strip():
                    continue
                m = re.match(r"^(%s):\s*(.*)$" % "|".join(HEADER_KEYS), ln)
                if not m:
                    print(f"ERR {q}: bad header line in {rel}: {ln[:50]!r}"); errors += 1
                    continue
                meta[m.group(1)] = m.group(2).strip()
            if q in blocks:
                print(f"ERR duplicate explanation {q} ({blocks[q]['file']} and {rel})"); errors += 1
            blocks[q] = {"meta": meta, "body": body.strip(), "file": str(rel)}
    return blocks, errors


def ranges(nums):
    """[1,2,3,7,9,10] -> '1–3, 7, 9–10'"""
    nums = sorted(nums)
    out, start, prev = [], None, None
    for n in nums + [None]:
        if start is None:
            start = prev = n
        elif n is not None and n == prev + 1:
            prev = n
        else:
            out.append(f"{start}" if start == prev else f"{start}–{prev}")
            start = prev = n
    return ", ".join(out)
