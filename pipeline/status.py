#!/usr/bin/env python3
"""Progress report straight from banks/* (no build needed).

    python pipeline/status.py            # all banks
    python pipeline/status.py <bank>     # one bank: missing questions, ⚠️, confidence, next batch
"""
import sys
from collections import Counter

from common import get_bank, load_banks, load_questions, parse_exp_dir, qid, ranges


def summary(b):
    qs = load_questions(b)
    exps, _ = parse_exp_dir(b)
    ids = {qid(b, q["no"]): q["no"] for q in qs}
    done = [n for i, n in ids.items() if i in exps]
    conf = Counter(exps[i]["meta"].get("conf") for i in ids if i in exps)
    flags = [n for i, n in ids.items() if i in exps and exps[i]["meta"].get("flag")]
    missing = [n for i, n in ids.items() if i not in exps]
    return qs, exps, done, conf, flags, missing


def overview():
    print(f"{'題庫':<10}{'題數':>5}{'已寫':>6}{'⚠️':>5}{'中':>5}{'低':>5}  標題")
    for b in load_banks():
        qs, _, done, conf, flags, _ = summary(b)
        print(f"{b['id']:<10}{len(qs):>5}{len(done):>6}{len(flags):>5}{conf.get('中', 0):>5}{conf.get('低', 0):>5}  {b['title']}")


def detail(bank_id, batch=10):
    b = get_bank(bank_id)
    qs, exps, done, conf, flags, missing = summary(b)
    print(f"{b['id']}｜{b['title']}｜{b['type']}｜{len(done)}/{len(qs)} 已寫")
    print(f"信心：高 {conf.get('高', 0)}、中 {conf.get('中', 0)}、低 {conf.get('低', 0)}")
    print(f"⚠️：{ranges(flags) or '無'}")
    low = sorted(int(i.rsplit('-', 1)[1]) for i in exps if exps[i]['meta'].get('conf') in ('中', '低'))
    print(f"信心中／低：{ranges(low) or '無'}")
    print(f"未寫：{ranges(missing) or '無'}")
    if missing:
        ms = sorted(missing)
        nxt = [ms[0]]  # first contiguous run of unwritten questions, at most `batch` long
        for n in ms[1:]:
            if n != nxt[-1] + 1 or len(nxt) >= batch:
                break
            nxt.append(n)
        print(f"下一批建議：Q{nxt[0]}–Q{nxt[-1]} → banks/{b['id']}/exp/{nxt[0]:03d}-{nxt[-1]:03d}.md"
              f"（看題目：python pipeline/show.py {b['id']} {nxt[0]} {nxt[-1]}）")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        detail(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 10)
    else:
        overview()
