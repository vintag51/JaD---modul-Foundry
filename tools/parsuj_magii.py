#!/usr/bin/env python3
"""
Vytáhne z uložené stránky SRD JaD (kapitola 10 – Magie) strukturovaná data kouzel.
Výstup (data/jad-kouzla-zdroj.json) obsahuje jen mechaniky a pomocný text pro párování;
text kouzel se do modulu NEKOPÍRUJE (licence JaD).

Použití: python3 -I tools/parsuj_magii.py <10-magie.html> <vystup.json>
"""
import html, json, re, sys

SKOLY = {"vymít": "abj", "vyvol": "con", "věšt": "div", "očar": "enc", "zaklí": "evo", "iluz": "ill",
         "nekro": "nec", "trans": "trs"}


def cisty(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def main(vstup, vystup):
    t = open(vstup, encoding="utf-8").read()
    start = t.index('id="popisy-kouzel"')
    t = t[start:]
    bloky = re.split(r'(?=<h4 id=")', t)[1:]
    kouzla = []
    for b in bloky:
        m = re.match(r'<h4 id="([^"]+)"[^>]*>(.*?)</h4>', b, re.S)
        kotva, nazev = m.group(1), cisty(m.group(2))
        b = re.split(r"<h[23] ", b)[0]
        odstavce = [cisty(p) for p in re.findall(r"<p>(.*?)</p>", b, re.S)]
        k = {"kotva": kotva, "cz": nazev, "radky": {}, "text": []}
        for p in odstavce:
            mm = re.match(r"^(Vyvolání|Dosah|Složky|Trvání|Povolání):\s*(.*)$", p, re.S)
            if mm:
                k["radky"][mm.group(1)] = mm.group(2).strip()
            elif "typ" not in k:
                k["typ"] = p
            else:
                k["text"].append(p)
        typ = k.get("typ", "").lower()
        if "trik" in typ:
            k["stupen"] = 0
        else:
            ms = re.search(r"(\d)\.\s*stup", typ)
            k["stupen"] = int(ms.group(1)) if ms else None
        k["skola"] = next((v for kk, v in SKOLY.items() if typ.startswith(kk)), None)
        k["ritual"] = "rituál" in typ
        k["povolani"] = [x.strip() for x in re.split(r",", k["radky"].get("Povolání", "")) if x.strip()]
        kouzla.append(k)
    json.dump(kouzla, open(vystup, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(kouzla), "kouzel")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
