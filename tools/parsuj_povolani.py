#!/usr/bin/env python3
"""
Vytáhne z uložené stránky SRD JaD (kapitola 4 – Povolání, MHT/HTML převedené na text) strukturu povolání:
Kostky obnovy, zdatnosti, tabulky, schopnosti (úrovně, četnost) a obory.
Výstup slouží jako podklad pro data/povolani.yml; texty schopností se do modulu NEKOPÍRUJÍ (licence JaD).

Použití: python3 -I tools/parsuj_povolani.py <povolani.txt> <vystup.json>
"""
import json, re, sys


def tabulka(blok):
    radky = [r for r in blok.split("\n") if r.startswith("| ")]
    return [[c.strip() for c in r.strip("| ").split(" | ")] for r in radky]


def schopnosti(text):
    out = []
    for m in re.finditer(r"\n#### (.+?)\n(.*?)(?=\n#### |\n### |\Z)", text, re.S):
        hlava, telo = m.group(1).strip(), m.group(2).strip()
        mm = re.match(r"^([\d\.,\s]+?)\s*-\s*(.+)$", hlava)
        if not mm:
            out.append({"nazev": hlava, "urovne": [], "cetnost": "", "text": telo})
            continue
        urovne = [int(x) for x in re.findall(r"\d+", mm.group(1))]
        radky = telo.split("\n")
        out.append({"nazev": mm.group(2).strip(), "urovne": urovne, "cetnost": radky[0].strip() if radky else "",
                    "text": "\n".join(radky[1:]).strip()})
    return out


def main(vstup, vystup):
    t = open(vstup, encoding="utf-8").read()
    pov = {}
    for blok in re.split(r"\n(?=## )", t):
        nazev = blok.split("\n")[0].lstrip("# ").strip()
        if nazev in ("Zlepšování postavy", "Počáteční vybavení", "Kombinovaná povolání", "Odbornosti") or "tabindex" in nazev:
            continue
        sekce = re.split(r"\n(?=### )", blok)
        p = {"nazev": nazev, "oboru": [], "schopnosti": [], "tabulka": [], "zdatnosti": {}, "vydrz": {}}
        for s in sekce[1:]:
            hl = s.split("\n")[0].lstrip("# ").strip()
            if hl.startswith("Tvorba"):
                p["tabulka"] = tabulka(s)
                for k in ("Kostky obnovy", "Zbraně", "Zbroje", "Pomůcky", "Záchranné hody", "Dovednosti"):
                    m = re.search(rf"\n{k}: (.+)", s)
                    if m:
                        (p["vydrz"] if k == "Kostky obnovy" else p["zdatnosti"])[k] = m.group(1).strip()
            elif hl.startswith("Schopnosti"):
                p["schopnosti"] = schopnosti(s)
            else:
                p["oboru"].append({"nazev": hl, "uvod": s.split("\n", 2)[-1].split("\n#### ")[0].strip()[:600],
                                   "schopnosti": schopnosti(s)})
        pov[nazev] = p
    json.dump(pov, open(vystup, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for k, p in pov.items():
        print(k, "| schopností:", len(p["schopnosti"]), "| oborů:", len(p["oboru"]),
              "| schopností oborů:", sum(len(o["schopnosti"]) for o in p["oboru"]), "|", p["vydrz"])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
