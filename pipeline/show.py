#!/usr/bin/env python3
"""Print questions (stem, options, official answer, reference, figures) for writing explanations.

    python pipeline/show.py <bank> <from> [<to>]     # by question number
    python pipeline/show.py <bank> --next [N]        # next batch: first run of ≤N consecutive unwritten questions
"""
import sys

from common import get_bank, load_questions, parse_exp_dir, qid


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 1
    b = get_bank(argv[1])
    qs = sorted(load_questions(b), key=lambda q: q["no"])
    fixes = b.get("fixes", {})
    if len(argv) > 2 and argv[2] == "--next":
        n = int(argv[3]) if len(argv) > 3 else 10
        exps, _ = parse_exp_dir(b)
        todo = [q for q in qs if qid(b, q["no"]) not in exps]
        pick = todo[:1]  # first contiguous run of unwritten questions (same as status.py's suggestion)
        for q in todo[1:]:
            if q["no"] != pick[-1]["no"] + 1 or len(pick) >= n:
                break
            pick.append(q)
    else:
        lo = int(argv[2]) if len(argv) > 2 else qs[0]["no"]
        hi = int(argv[3]) if len(argv) > 3 else lo
        pick = [q for q in qs if lo <= q["no"] <= hi]
    for q in pick:
        i = qid(b, q["no"])
        stem, opts = q["stem"], list(q["options"])
        for old, new in fixes.get(i, []):
            stem = stem.replace(old, new)
            opts = [o.replace(old, new) for o in opts]
        print(f"## {i}  [官方答案 {q['answer']}]" + (f"  出題參考：{q['ref']}" if q.get("ref") else ""))
        print(stem)
        for L, o in zip("ABCDE", opts):
            print(f"{L}. {o}")
        if q.get("images"):
            print("圖：" + "、".join(f"banks/{b['id']}/img/{f}" for f in q["images"]) + "（用 Read 開圖）")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
