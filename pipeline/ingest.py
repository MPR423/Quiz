#!/usr/bin/env python3
"""Turn a question-bank PDF into a new bank folder: banks/<id>/{meta.json, questions.json, img/, exp/}.

    python pipeline/ingest.py --pdf sources/gs_multi.pdf --id gs-m \\
        --title "一般外科・複選題庫" --short "一外複選" --group 外科 \\
        --taxonomy surg --sub-default 一般外科 [--parser parse_surg] [--type auto] [--order 110]

Parsers (pipeline/<parser>.py <pdf> <out.json> <imgdir>):
  parse_surg  台灣外科醫學會 Excel 匯出格式（科別｜題目類別｜題號｜題目｜答案｜出題參考），單選或複選
  parse_em    急診醫學會筆試公告格式（答案欄＋題號＋題目，（ ）選項，含附圖）
A PDF with a different layout needs a new parser: copy the closest one and adjust the column rules.

The script refuses to overwrite an existing bank unless --force (explanations in exp/ are never touched).
After running it, CHECK the printed summary against the PDF before writing explanations:
question count, numbering gaps, answer distribution, and the two sample questions.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from common import BANKS_DIR, ROOT, load_banks, load_taxonomy


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--id", required=True, help="short id, lowercase letters/digits/-, e.g. gs-m; becomes the question id prefix")
    ap.add_argument("--title", required=True)
    ap.add_argument("--short", required=True)
    ap.add_argument("--group", required=True, help="首頁分組，例如 急診、外科")
    ap.add_argument("--taxonomy", required=True, help="key in taxonomy.json (em / surg / …)")
    ap.add_argument("--sub-default", default=None, help="次專科預設值（外科題庫通常就是該科）；不給則每題詳解都要寫 sub:")
    ap.add_argument("--parser", default="parse_surg")
    ap.add_argument("--type", default="auto", choices=["auto", "single", "multi"])
    ap.add_argument("--order", type=int, default=None, help="首頁排序；預設排在最後")
    ap.add_argument("--force", action="store_true", help="re-parse an existing bank (keeps exp/)")
    a = ap.parse_args()

    import re
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", a.id):
        sys.exit("ERR --id must be lowercase letters, digits and '-'")
    pdf = (ROOT / a.pdf).resolve() if not Path(a.pdf).is_absolute() else Path(a.pdf)
    if not pdf.is_file():
        sys.exit(f"ERR no such PDF: {a.pdf}")
    tax = load_taxonomy()
    if a.taxonomy not in tax:
        sys.exit(f"ERR taxonomy '{a.taxonomy}' not in taxonomy.json ({', '.join(tax)}); add it there first")
    if a.sub_default and a.sub_default not in tax[a.taxonomy]:
        sys.exit(f"ERR --sub-default '{a.sub_default}' not in taxonomy '{a.taxonomy}': {tax[a.taxonomy]}")
    bdir = BANKS_DIR / a.id
    if (bdir / "meta.json").exists() and not a.force:
        sys.exit(f"ERR bank '{a.id}' already exists; pass --force to re-parse it")

    parser = ROOT / "pipeline" / f"{a.parser}.py"
    if not parser.is_file():
        sys.exit(f"ERR no parser {parser.relative_to(ROOT)}")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "questions.json"
        imgdir = Path(tmp) / "img"
        r = subprocess.run([sys.executable, str(parser), str(pdf), str(out), str(imgdir)], text=True, capture_output=True)
        print(r.stdout.strip())
        if r.returncode != 0:
            print(r.stderr.strip()); sys.exit("ERR parser failed")
        qs = json.loads(out.read_text(encoding="utf-8"))
        if not qs:
            sys.exit("ERR parser returned no questions")
        bdir.mkdir(parents=True, exist_ok=True)
        (bdir / "exp").mkdir(exist_ok=True)
        keep = [{k: q[k] for k in ("no", "stem", "options", "answer", "images", "ref") if q.get(k)} for q in qs]
        for q in keep:
            q.setdefault("images", [])
        (bdir / "questions.json").write_text(json.dumps(keep, ensure_ascii=False, indent=1), encoding="utf-8")
        imgs = sorted(imgdir.glob("*")) if imgdir.is_dir() else []
        if imgs:
            (bdir / "img").mkdir(exist_ok=True)
            for f in imgs:
                (bdir / "img" / f.name).write_bytes(f.read_bytes())

    answers = [q["answer"] for q in keep]
    qtype = a.type if a.type != "auto" else ("multi" if any(len(x) > 1 for x in answers) else "single")
    others = [b for b in load_banks() if b["id"] != a.id]
    order = a.order if a.order is not None else max([b.get("order", 0) for b in others] + [0]) + 10
    meta = {"id": a.id, "order": order, "group": a.group, "title": a.title, "short": a.short, "type": qtype,
            "taxonomy": a.taxonomy, "sub_default": a.sub_default,
            "source": str(pdf.relative_to(ROOT)) if pdf.is_relative_to(ROOT) else a.pdf,
            "parser": a.parser, "fixes": {}}
    if (bdir / "meta.json").exists():  # --force: keep hand-added fixes
        meta["fixes"] = json.loads((bdir / "meta.json").read_text(encoding="utf-8")).get("fixes", {})
    (bdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    nos = sorted(q["no"] for q in keep)
    print(f"\n== {a.id}: {len(keep)} 題（Q{nos[0]}–Q{nos[-1]}），類型 {qtype}，圖片 {len(imgs)} 張")
    gaps = sorted(set(range(nos[0], nos[-1] + 1)) - set(nos))
    dups = sorted({n for n in nos if nos.count(n) > 1})
    print(f"缺號：{gaps or '無'}　重號：{dups or '無'}")
    print("選項數：", dict(Counter(len(q["options"]) for q in keep)))
    print("答案分布：", dict(sorted(Counter(answers).items())) if qtype == "single" else
          dict(sorted(Counter(len(x) for x in answers).items())), "（複選題顯示答案個數）" if qtype == "multi" else "")
    for q in (keep[0], keep[-1]):
        print(f"\n範例 Q{q['no']}［{q['answer']}］{q['stem'][:120]}")
        for L, o in zip("ABCDE", q["options"]):
            print(f"  {L}. {o[:80]}")
    print("\n下一步：對照 PDF 確認題數、答案與範例題無誤；有亂碼就在 meta.json 的 fixes 加替換規則；"
          "然後 python pipeline/build.py && python pipeline/check.py")


if __name__ == "__main__":
    main()
