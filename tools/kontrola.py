#!/usr/bin/env python3
"""Strukturní kontrola vygenerovaných dat (bez spuštění Foundry)."""
import glob, json, os, re, sys

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ID = re.compile(r"^[A-Za-z0-9]{16}$")
chyby = []

polozky, slozky = [], set()
for f in glob.glob(os.path.join(KOREN, "packs/_source/kouzla/*.json")):
    d = json.load(open(f, encoding="utf-8"))
    if d["_key"].startswith("!folders!"):
        slozky.add(d["_id"])
    else:
        polozky.append(d)

idy = {p["_id"] for p in polozky}
if len(idy) != len(polozky):
    chyby.append("duplicitní _id položek")
nazvy = [p["name"] for p in polozky]
if len(set(nazvy)) != len(nazvy):
    chyby.append("duplicitní názvy: " + str({n for n in nazvy if nazvy.count(n) > 1}))

for p in polozky:
    n = p["name"]
    if not ID.match(p["_id"]) or p["_key"] != f"!items!{p['_id']}":
        chyby.append(f"{n}: špatné _id/_key")
    if p.get("folder") not in slozky:
        chyby.append(f"{n}: neexistující složka")
    sy = p["system"]
    if not (0 <= sy["level"] <= 9):
        chyby.append(f"{n}: stupeň")
    if sy["school"] not in {"abj", "con", "div", "enc", "evo", "ill", "nec", "trs"}:
        chyby.append(f"{n}: škola {sy['school']}")
    efekty = {e["_id"] for e in p.get("effects", [])}
    for e in p.get("effects", []):
        if not ID.match(e["_id"]):
            chyby.append(f"{n}: id efektu {e['_id']}")
    if not sy["activities"]:
        chyby.append(f"{n}: žádná aktivita")
    for aid, a in sy["activities"].items():
        if a["_id"] != aid:
            chyby.append(f"{n}: nesoulad id aktivity")
        for e in a.get("effects", []):
            if e["_id"] not in efekty:
                chyby.append(f"{n}/{a['name']}: odkaz na chybějící efekt {e['_id']}")
        if not a.get("name"):
            chyby.append(f"{n}: aktivita bez názvu")
    for u in re.findall(r"Compendium\.jeskyne-a-draci\.kouzla\.Item\.([A-Za-z0-9]{16})", json.dumps(p)):
        if u not in idy:
            chyby.append(f"{n}: odkaz na neexistující kouzlo {u}")

j = json.load(open(os.path.join(KOREN, "packs/_source/seznamy-kouzel/seznamy-kouzel.json"), encoding="utf-8"))
for s in j["pages"]:
    for u in s["system"]["spells"]:
        if u.split(".")[-1] not in idy:
            chyby.append(f"seznam {s['name']}: chybí {u}")

reg = json.load(open(os.path.join(KOREN, "data/kompendium/registr.json"), encoding="utf-8"))
if len(reg["seznamyKouzel"]) != len(j["pages"]) or any(s["_id"] not in " ".join(reg["seznamyKouzel"]) for s in j["pages"]):
    chyby.append("registr.json neodpovídá seznamům kouzel")

print(f"Kouzel: {len(polozky)}, složek: {len(slozky)}, seznamů: {len(j['pages'])}")
for c in chyby:
    print("  !", c)
print("OK" if not chyby else f"{len(chyby)} chyb")
sys.exit(1 if chyby else 0)
