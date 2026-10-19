"""Parse the TSEM written exam PDF (single-answer, 4 options) into JSON.

Usage: python pipeline/parse_em.py <pdf> <out.json> <imgdir>   (normally called by ingest.py)

Layout facts (from inspection):
  - answer letter column: x0 < 70
  - question number "N. ": 70 <= x0 < 110, text like "12." / "12. "
  - stem/option text: x0 >= 110; options start with "（" at x0 ~112; option
    continuation lines are indented (x0 ~154)
  - images belong to the most recent question start (page, y order)
"""
import json, re, sys, os
import pymupdf

SRC, OUT, IMGDIR = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(IMGDIR, exist_ok=True)

SUB = str.maketrans("0123456789+-", "₀₁₂₃₄₅₆₇₈₉₊₋")
SUP = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")

doc = pymupdf.open(SRC)
events = []  # (page, y, kind, payload)

for page in doc:
    pn = page.number
    d = page.get_text("dict")
    for b in d["blocks"]:
        if b["type"] == 1:
            x0, y0, x1, y1 = b["bbox"]
            events.append((pn, y0, "image", {"bbox": (x0, y0, x1, y1)}))
            continue
        for line in b.get("lines", []):
            for s in line["spans"]:
                t = s["text"]
                if not t.strip():
                    continue
                x0, y0, x1, y1 = s["bbox"]
                if y0 < 60 or y0 > 800:  # header / footer
                    continue
                if t.strip() in ("答案", "題號", "題目"):
                    continue
                events.append((pn, y0, "span", {"x0": x0, "x1": x1, "y0": y0, "y1": y1,
                                                "size": s["size"], "text": t}))

# group spans into visual lines per page (y tolerance)
def group_lines(spans):
    spans = sorted(spans, key=lambda s: (s["y0"], s["x0"]))
    lines = []
    for s in spans:
        # baseline approx: use center y of full-size spans
        cy = (s["y0"] + s["y1"]) / 2
        placed = False
        for ln in lines:
            if abs(ln["cy"] - cy) <= 5:
                ln["spans"].append(s)
                placed = True
                break
        if not placed:
            lines.append({"cy": cy, "spans": [s]})
    for ln in lines:
        ln["spans"].sort(key=lambda s: s["x0"])
        ln["x0"] = ln["spans"][0]["x0"]
        ln["y0"] = min(s["y0"] for s in ln["spans"])
    return sorted(lines, key=lambda l: l["cy"])

def line_text(ln):
    big = max(s["size"] for s in ln["spans"])
    base_cy = None
    for s in ln["spans"]:
        if s["size"] == big:
            base_cy = (s["y0"] + s["y1"]) / 2
            break
    out = ""
    prev_x1 = None
    for s in ln["spans"]:
        t = s["text"]
        small = False
        if s["size"] < big - 2 and t.strip():
            cy = (s["y0"] + s["y1"]) / 2
            t2 = t.strip()
            if re.fullmatch(r"[0-9+\-]+", t2):
                t = t2.translate(SUB if cy > base_cy else SUP)
                small = True
        # a visible gap between spans means the source had a space there
        if (prev_x1 is not None and not small and s["x0"] - prev_x1 > 1.5
                and out and not out.endswith(" ") and not t.startswith(" ")):
            out += " "
        out += t
        prev_x1 = s["x1"]
    return out

pages = {}
for pn, y, kind, p in events:
    pages.setdefault(pn, {"spans": [], "images": []})
    if kind == "span":
        pages[pn]["spans"].append(p)
    else:
        pages[pn]["images"].append(p)

# Build an ordered stream of items: answer letters, question starts, text lines, images
stream = []
for pn in sorted(pages):
    spans = pages[pn]["spans"]
    ans = [s for s in spans if s["x0"] < 70]
    num = [s for s in spans if 70 <= s["x0"] < 110]
    body = [s for s in spans if s["x0"] >= 110]
    for s in ans:
        stream.append((pn, s["y0"], "ans", s["text"].strip()))
    for s in num:
        m = re.match(r"\s*(\d+)\.\s*(.*)$", s["text"])
        if m:
            stream.append((pn, s["y0"] - 4, "qstart", int(m.group(1))))
            rest = m.group(2)
            if rest.strip():
                body.append(dict(s, x0=110.5, text=rest))
        else:
            print("WARN unparsed number col", pn + 1, repr(s["text"]))
    for ln in group_lines(body):
        stream.append((pn, ln["y0"], "line", {"x0": ln["x0"], "text": line_text(ln)}))
    for im in pages[pn]["images"]:
        stream.append((pn, im["bbox"][1], "image", im["bbox"]))

order = {"qstart": 0, "line": 1, "image": 1, "ans": 2}
stream.sort(key=lambda e: (e[0], e[1], order[e[2]]))

questions = []
cur = None
for pn, y, kind, p in stream:
    if kind == "qstart":
        cur = {"no": p, "lines": [], "ans": [], "images": [], "page": pn + 1}
        questions.append(cur)
    elif cur is None:
        print("WARN content before first question", kind, p)
    elif kind == "ans":
        cur["ans"].append(p)
    elif kind == "line":
        cur["lines"].append(p)
    elif kind == "image":
        cur["images"].append((pn, p))

def join(a, b):
    if not a:
        return b
    if a and b and re.match(r"[A-Za-z0-9,.)%]", a[-1]) and re.match(r"[A-Za-z0-9(]", b[0]):
        return a + " " + b
    return a + b

OPT_RE = re.compile(r"^（\s*[˽˾˿ˀ]?\s*）\s*")
result = []
for q in questions:
    stem, opts = "", []
    for ln in q["lines"]:
        t = ln["text"].strip()
        if ln["x0"] < 120 and OPT_RE.match(t):
            # option start: strip marker like （˽）
            t2 = OPT_RE.sub("", t)
            opts.append(t2)
        elif opts:
            opts[-1] = join(opts[-1], t)
        else:
            stem = join(stem, t)
    # clean trailing full stop on options ("。")
    opts = [re.sub(r"\s+", " ", o).strip() for o in opts]
    stem = re.sub(r"[ \t]+", " ", stem).strip()
    imgs = []
    for k, (pn, bbox) in enumerate(q["images"]):
        page = doc[pn]
        # extract embedded image at native resolution
        found = None
        for info in page.get_images(full=True):
            xref = info[0]
            for r in page.get_image_rects(xref):
                if abs(r.y0 - bbox[1]) < 2 and abs(r.x0 - bbox[0]) < 2:
                    found = xref
        if found:
            raw = doc.extract_image(found)  # original stream, no recompression
            ext = raw["ext"] if raw["ext"] in ("jpeg", "jpg", "png") else "png"
            ext = "jpg" if ext == "jpeg" else ext
            fname = f"q{q['no']:03d}_{k+1}.{ext}"
            path = os.path.join(IMGDIR, fname)
            if ext == raw["ext"] or (ext == "jpg" and raw["ext"] == "jpeg"):
                open(path, "wb").write(raw["image"])
            else:
                pix = pymupdf.Pixmap(doc, found)
                if pix.n - pix.alpha >= 4:
                    pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                pix.save(path)
        else:
            fname = f"q{q['no']:03d}_{k+1}.png"
            path = os.path.join(IMGDIR, fname)
            page.get_pixmap(clip=pymupdf.Rect(bbox), dpi=220).save(path)
        imgs.append(fname)
    result.append({
        "no": q["no"], "page": q["page"], "stem": stem, "options": opts,
        "answer": "".join(q["ans"]), "images": imgs,
    })

# sanity checks
nos = [r["no"] for r in result]
print("questions:", len(result), "range", min(nos), max(nos))
missing = sorted(set(range(1, max(nos) + 1)) - set(nos))
dups = sorted({n for n in nos if nos.count(n) > 1})
print("missing:", missing, "dups:", dups)
for r in result:
    if len(r["options"]) != 4 or r["answer"] not in ("A", "B", "C", "D"):
        print("CHECK", r["no"], "opts", len(r["options"]), "ans", repr(r["answer"]))
print("with images:", [(r["no"], len(r["images"])) for r in result if r["images"]])
json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
