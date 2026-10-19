"""Parse a Taiwan Surgical Association question-bank PDF (Excel export).

Usage: python pipeline/parse_surg.py <pdf> <out.json> [<imgdir>]   (normally called by ingest.py)

Columns (landscape A4): 科別 | 題目類別 | 題號 | 題目(含選項) | 答案 | 出題參考
Column x-ranges are detected from the header row on each page.
"""
import json, re, sys
import pymupdf

SRC, OUT = sys.argv[1], sys.argv[2]
IMGDIR = sys.argv[3] if len(sys.argv) > 3 else None  # interface parity with parse_em; figures not extracted yet
doc = pymupdf.open(SRC)
img_pages = [p.number + 1 for p in doc if p.get_images()]
if img_pages:
    print("WARN this PDF has embedded images on pages", img_pages,
          "- parse_surg does not extract figures; check whether questions need them (see parse_em.py for how)")

SUB = str.maketrans("0123456789+-", "₀₁₂₃₄₅₆₇₈₉₊₋")
SUP = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")

def spans_of(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                if s["text"].strip():
                    x0, y0, x1, y1 = s["bbox"]
                    out.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1,
                                "size": s["size"], "text": s["text"]})
    return out

def group_lines(spans, tol=5):
    spans = sorted(spans, key=lambda s: (s["y0"], s["x0"]))
    lines = []
    for s in spans:
        cy = (s["y0"] + s["y1"]) / 2
        for ln in lines:
            if abs(ln["cy"] - cy) <= tol:
                ln["spans"].append(s)
                break
        else:
            lines.append({"cy": cy, "spans": [s]})
    for ln in lines:
        ln["spans"].sort(key=lambda s: s["x0"])
        ln["y0"] = min(s["y0"] for s in ln["spans"])
    return sorted(lines, key=lambda l: l["cy"])

def line_text(ln):
    big = max(s["size"] for s in ln["spans"])
    base = next(s for s in ln["spans"] if s["size"] == big)
    base_cy = (base["y0"] + base["y1"]) / 2
    out, prev_x1 = "", None
    for s in ln["spans"]:
        t, small = s["text"], False
        if s["size"] < big - 2 and re.fullmatch(r"[0-9+\-]+", t.strip()):
            cy = (s["y0"] + s["y1"]) / 2
            t, small = t.strip().translate(SUB if cy > base_cy else SUP), True
        if (prev_x1 is not None and not small and s["x0"] - prev_x1 > 1.5
                and out and not out.endswith(" ") and not t.startswith(" ")):
            out += " "
        out += t
        prev_x1 = s["x1"]
    return out

def join(a, b):
    if not a:
        return b
    if re.search(r"[A-Za-z0-9,.)%:;]$", a) and re.match(r"[A-Za-z0-9(]", b):
        return a + " " + b
    return a + b

questions = []
for page in doc:
    sp = spans_of(page)
    hdr = {s["text"].strip(): s for s in sp if s["y0"] < 60}
    if "題號" not in hdr:
        continue
    x_no = hdr["題號"]["x0"] - 12
    x_q = hdr["題號"]["x1"] + 4
    x_ans = hdr["答案"]["x0"] - 12
    x_ref = hdr["出題參考"]["x0"] - 65
    body = [s for s in sp if 60 < s["y0"] < page.rect.height - 50]
    starts = sorted([(s["y0"], int(s["text"].strip())) for s in body
                     if x_no <= s["x0"] < x_q and re.fullmatch(r"\s*\d+\s*", s["text"])])
    cats = [s for s in body if s["x0"] < x_no]
    for i, (y, no) in enumerate(starts):
        y_top = y - 4
        y_bot = starts[i + 1][0] - 4 if i + 1 < len(starts) else 10_000
        inrow = [s for s in body if y_top <= s["y0"] < y_bot]
        qsp = [s for s in inrow if x_q <= s["x0"] < x_ans]
        asp = [s for s in inrow if x_ans <= s["x0"] < x_ref]
        rsp = [s for s in inrow if s["x0"] >= x_ref]
        csp = [s for s in inrow if s["x0"] < x_no]
        stem, opts = "", []
        for ln in group_lines(qsp):
            t = line_text(ln).strip()
            m = re.match(r"^([A-E])[\.．、]\s*(.*)$", t)
            if m and m.group(1) == "ABCDE"[len(opts)]:
                opts.append(m.group(2).strip())
            elif opts:
                opts[-1] = join(opts[-1], t)
            else:
                stem = join(stem, t)
        ref = ""
        for ln in group_lines(rsp):
            ref = join(ref, line_text(ln).strip())
        ans = "".join(s["text"].strip() for s in sorted(asp, key=lambda s: (s["y0"], s["x0"])))
        cat = " ".join(line_text(ln).strip() for ln in group_lines(csp))
        questions.append({"no": no, "page": page.number + 1, "cat": cat,
                          "stem": re.sub(r"[ \t]+", " ", stem).strip(),
                          "options": [re.sub(r"[ \t]+", " ", o) for o in opts],
                          "answer": ans, "ref": ref})

nos = [q["no"] for q in questions]
print("questions:", len(questions), "range", min(nos), max(nos))
print("missing:", sorted(set(range(1, max(nos) + 1)) - set(nos)),
      "dups:", sorted({n for n in nos if nos.count(n) > 1}))
for q in questions:
    if len(q["options"]) not in (4, 5) or not re.fullmatch(r"[A-E]+", q["answer"]):
        print("CHECK", q["no"], len(q["options"]), repr(q["answer"]))
json.dump(questions, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
