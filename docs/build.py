"""Build docs/index.html: the Arabic translation aligned morpheme by morpheme with
the Coptic. Hovering over a piece on either side highlights its partner.

Input : docs/align.txt  (the alignment; see the comments at its top)
        thomas.txt     (the Arabic, which the alignment must reproduce exactly)
        coptic-reader  (Coptic SCRIPTORIUM morphemes, lemmas and parts of speech)
Output: docs/index.html (self-contained apart from web fonts)

Usage: python3 docs/build.py
       (set COPTIC_READER if coptic-reader is not next to this repository)
"""
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
READER = os.environ.get("COPTIC_READER", os.path.join(os.path.dirname(ROOT), "coptic-reader"))
TEXTS = os.path.join(READER, "data", "texts", "sah", "tho")
ABJAD = ["أ", "ب", "ج", "د", "هـ", "و", "ز", "ح", "ط", "ي"]
LABEL = re.compile(r"^(\d+)(%s)?$" % "|".join(ABJAD))


def key(s):
    """Coptic form without diacritics or the ⳿ divider, for matching."""
    s = "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))
    return s.replace("⳿", "")


def arabic_lines():
    out = {}
    with open(os.path.join(ROOT, "thomas.txt"), encoding="utf-8") as fh:
        for line in fh:
            m = re.match(r"^(\d+(?:%s)?)\. (.*)$" % "|".join(ABJAD), line.rstrip("\n"))
            if m and re.search("[ء-ي]", m.group(2)):
                out[m.group(1)] = m.group(2)
    return out


def coptic_verse(label):
    m = LABEL.match(label)
    logion = int(m.group(1))
    with open(os.path.join(TEXTS, "%d.json" % logion), encoding="utf-8") as fh:
        verses = json.load(fh)["verses"]
    n = ABJAD.index(m.group(2)) + 1 if m.group(2) else 1
    return next(v for v in verses if v["n"] == n)


def read_blocks():
    blocks, cur = [], None
    with open(os.path.join(HERE, "align.txt"), encoding="utf-8") as fh:
        for n, raw in enumerate(fh, 1):
            line = raw.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            if LABEL.match(line.strip()):
                cur = {"label": line.strip(), "segs": []}
                blocks.append(cur)
                continue
            ar, _, cop = line.partition("\t")
            cur["segs"].append((n, ar, cop.split()))
    return blocks


def build_block(block, arabic, errors):
    label = block["label"]
    verse = coptic_verse(label)
    groups, morphs = [], []
    for g in verse["groups"]:
        ids = []
        for m in g["m"]:
            morphs.append({"d": m.get("o", m["t"]), "k": key(m.get("o", m["t"])),
                           "l": m["l"], "p": m["p"], "seg": []})
            ids.append(len(morphs) - 1)
        groups.append(ids)
    used, segs, text = set(), [], ""
    for n, ar, cops in block["segs"]:
        join = ar.startswith("+")
        ar = ar[1:] if join else ar
        text += ar if join or not text else " " + ar
        links = []
        for c in cops:
            form, _, nth = c.partition("@")   # ⲉ@2 = the second ⲉ in the sub-verse
            same = [i for i, m in enumerate(morphs) if m["k"] == key(form)]
            if nth:
                hit = same[int(nth) - 1] if len(same) >= int(nth) and same[int(nth) - 1] not in used else None
            else:
                hit = next((i for i in same if i not in used), None)
            if hit is None:
                errors.append("align.txt:%d: %s: no unused Coptic morpheme %s" % (n, label, c))
                continue
            used.add(hit)
            links.append(hit)
            morphs[hit]["seg"].append(len(segs))
        segs.append({"a": ar, "j": join, "c": links})
    if text != arabic.get(label):
        errors.append("%s: the segments give\n  %s\nbut thomas.txt has\n  %s" % (label, text, arabic.get(label)))
    for m in morphs:
        del m["k"]
    return {"label": label, "groups": groups, "morphs": morphs, "segs": segs}


def main():
    arabic = arabic_lines()
    errors = []
    data = [build_block(b, arabic, errors) for b in read_blocks()]
    if errors:
        print("\n".join(errors))
        sys.exit(1)
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as fh:
        page = fh.read()
    page = page.replace("/*DATA*/null", json.dumps(data, ensure_ascii=False))
    with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(page)
    untranslated = sum(1 for v in data for m in v["morphs"] if not m["seg"] and m["p"] != "PUNCT")
    print("wrote docs/index.html: %d sub-verses, %d untranslated Coptic morphemes"
          % (len(data), untranslated))


if __name__ == "__main__":
    main()
