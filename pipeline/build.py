#!/usr/bin/env python3
"""Build the site's data from banks/*.

    banks/<id>/meta.json + questions.json + exp/*.md + img/
        → site/data/banks.js, site/data/<id>.js   (what the website loads)
        → site/img/<id>/*                           (copied figures)
        → build/<id>.json, build/banks.json         (plain JSON for check.py and other tools)

Exits 1 when any ERR is found, so CI refuses to deploy a broken build.
"""
import datetime
import json
import os
import re
import shutil
import sys

from common import ROOT, load_banks, load_questions, load_taxonomy, parse_exp_dir, qid

TZ = datetime.timezone(datetime.timedelta(hours=8))  # Taiwan


def write_js(path, key, obj):
    """Data ships as a script that registers itself on window.BXD, so the site also works from file://."""
    payload = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")  # invalid in pre-ES2019 JS strings
    path.write_text(f"(window.BXD=window.BXD||{{}})[{json.dumps(key)}]={payload};\n", encoding="utf-8")


def main():
    tax = load_taxonomy()
    banks = load_banks()
    problems = 0
    data_dir, img_root, build_dir = ROOT / "site" / "data", ROOT / "site" / "img", ROOT / "build"
    for d in (data_dir, img_root, build_dir):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)

    out_banks, sub_order = [], []
    for b in banks:
        bid = b["id"]
        if b.get("taxonomy") not in tax:
            print(f"ERR {bid}: taxonomy '{b.get('taxonomy')}' not in taxonomy.json"); problems += 1
            continue
        subs = tax[b["taxonomy"]]
        sub_order += [s for s in subs if s not in sub_order]
        if b.get("sub_default") is not None and b["sub_default"] not in subs:
            print(f"ERR {bid}: sub_default '{b['sub_default']}' not in taxonomy '{b['taxonomy']}'"); problems += 1

        # figures
        src_img = b["_dir"] / "img"
        if src_img.is_dir():
            shutil.copytree(src_img, img_root / bid)

        exps, errs = parse_exp_dir(b)
        problems += errs
        fixes = b.get("fixes", {})
        used, qs, seen_no = set(), [], set()
        for r in load_questions(b):
            q_id = qid(b, r["no"])
            if r["no"] in seen_no:
                print(f"ERR {q_id}: duplicate question number in questions.json"); problems += 1
            seen_no.add(r["no"])
            stem, opts = r["stem"], list(r["options"])
            for old, new in fixes.get(q_id, []):
                stem = stem.replace(old, new)
                opts = [o.replace(old, new) for o in opts]
            answer = list(r["answer"])
            if not answer or any(L not in "ABCDE"[:len(opts)] for L in answer):
                print(f"ERR {q_id}: answer '{r['answer']}' does not fit {len(opts)} options"); problems += 1
            q = {"id": q_id, "no": r["no"], "type": b["type"], "stem": stem, "options": opts, "answer": answer,
                 "images": [f"img/{bid}/{f}" for f in r.get("images", [])]}
            for f in r.get("images", []):
                if not (src_img / f).is_file():
                    print(f"ERR {q_id}: image {f} missing in banks/{bid}/img"); problems += 1
            if r.get("ref"):
                q["ref"] = r["ref"]
            q["sub"] = b.get("sub_default")
            e = exps.get(q_id)
            if e:
                used.add(q_id)
                m = e["meta"]
                sub = m.get("sub") or b.get("sub_default")
                if sub not in subs:
                    print(f"ERR {q_id}: sub '{sub}' not in taxonomy '{b['taxonomy']}'"); problems += 1
                conf = m.get("conf")
                if conf not in ("高", "中", "低"):
                    print(f"ERR {q_id}: conf '{conf}' must be 高/中/低"); problems += 1
                if not e["body"]:
                    print(f"ERR {q_id}: empty body"); problems += 1
                for i in range(len(opts)):
                    L = "ABCDE"[i]
                    if not re.search(rf"\*\*{L}[｜|]", e["body"]):
                        print(f"ERR {q_id}: option {L} has no '**{L}｜…**' line"); problems += 1
                q.update({"sub": sub, "conf": conf, "exp": e["body"]})
                if m.get("flag"):
                    q["flag"] = m["flag"]
                if m.get("src"):
                    q["src"] = m["src"]
            qs.append(q)
        for q_id in exps:
            if q_id not in used:
                print(f"ERR explanation for unknown question {q_id} ({exps[q_id]['file']})"); problems += 1

        bank_obj = {"bank": bid, "questions": qs}
        (build_dir / f"{bid}.json").write_text(json.dumps(bank_obj, ensure_ascii=False, indent=1), encoding="utf-8")
        write_js(data_dir / f"{bid}.js", bid, bank_obj)
        n_exp = sum(1 for q in qs if q.get("exp"))
        print(f"{bid}: {len(qs)} questions, {n_exp} with explanations")
        out_banks.append({k: b[k] for k in ("id", "group", "title", "short", "type")} | {"file": f"{bid}.js", "count": len(qs)})

    meta = {"updated": datetime.datetime.now(TZ).strftime("%Y-%m-%d %H:%M"),
            "repo": os.environ.get("GITHUB_REPOSITORY", ""),  # set by GitHub Actions; enables 回報錯誤 links
            "subOrder": sub_order, "banks": out_banks}
    (build_dir / "banks.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    write_js(data_dir / "banks.js", "banks", meta)
    print("problems:", problems)
    return problems


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
