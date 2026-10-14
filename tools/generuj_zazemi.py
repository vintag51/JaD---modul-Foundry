#!/usr/bin/env python3
"""
Generátor kompendia zázemí a odborností Jeskyní a draků (data/zazemi.yml → packs/_source/zazemi,
data/kompendium/zazemi.json).

Použití: python3 tools/generuj_zazemi.py
"""
import html, json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generuj import KOREN, MODUL, foundry_id, nacti_yaml, slug, stats  # noqa: E402
from generuj_rasy import adv_asi, adv_grant, adv_trait  # noqa: E402
from generuj_povolani import aktivita, efekt, pouziti  # noqa: E402

PACK = "zazemi"
LICENCE = "Licence JaD pro třetí strany"
SRD_ZAZEMI = "https://dnd5esrd.d20.cz/jeskyne-a-draci/2-tvorba-postavy.html"
SRD_ODB = "https://dnd5esrd.d20.cz/jeskyne-a-draci/4-povolani.html#odbornosti"
IKONA_ZAZEMI = "icons/sundries/documents/document-sealed-brown-red.webp"
IKONA_SCH = "icons/sundries/scrolls/scroll-bound-brown-tan.webp"
IKONA_ODB = "icons/sundries/books/book-worn-brown-grey.webp"


def uuid(iid):
    return f"Compendium.{MODUL}.{PACK}.Item.{iid}"


def feat(iid, nazev, d, druh, slozka, odkaz, ikona, p=None, akt=(), pas=None, postup=None, pozadavek=""):
    efekty = []
    if pas:
        e = efekt(f"{iid}-pas", nazev, pas, ikona, True, popis=f"{nazev} (pasivní)")
        e["origin"] = uuid(iid)
        efekty.append(e)
    aktivity = {}
    for i, a in enumerate(akt):
        x = aktivita(f"{iid}-akt-{i}", a, i, bool(p), [])
        aktivity[x["_id"]] = x
    popis = f"<p>{html.escape(d)}</p>"
    if pozadavek:
        popis = f"<p><strong>Předpoklad:</strong> {html.escape(pozadavek)}</p>" + popis
    popis += f"<p><em>Plné znění: <a href=\"{odkaz}\" target=\"_blank\">SRD Jeskyní a draků</a>.</em></p>"
    return {"_id": iid, "name": nazev, "type": "feat", "img": ikona, "folder": slozka, "sort": 0,
            "ownership": {"default": 0}, "effects": efekty,
            "system": {"description": {"value": popis, "chat": ""},
                       "source": {"custom": "", "book": "Jeskyně a draci", "page": "", "license": LICENCE, "rules": "2014"},
                       "uses": pouziti(p), "type": {"value": druh, "subtype": ""}, "requirements": pozadavek,
                       "properties": [], "activities": aktivity, "enchant": {}, "prerequisites": {"level": None},
                       "identifier": slug(nazev), "advancement": postup or {}},
            "flags": {MODUL: {druh: True}}, "_stats": stats(), "_key": f"!items!{iid}"}


def main():
    d = nacti_yaml("zazemi.yml")
    slozky = {n: foundry_id(f"zazemi-slozka-{n}") for n in ("Zázemí", "Schopnosti zázemí", "Odbornosti")}
    folders = [{"_id": fid, "name": n, "type": "Item", "sorting": "a", "sort": (i + 1) * 100000, "folder": None,
                "color": None, "flags": {}, "_key": f"!folders!{fid}"} for i, (n, fid) in enumerate(slozky.items())]
    polozky, chyby = [], []
    from vybava import startovni
    vyb = (nacti_yaml("vybaveni-startovni.yml") or {}).get("zazemi", {})

    for k, z in d["zazemi"].items():
        s = z["schopnost"]
        sid = foundry_id(f"zazemi-schopnost-{s['k']}")
        odkaz = f"{SRD_ZAZEMI}#{z['kotva']}"
        polozky.append(feat(sid, s["n"], s["d"], "background", slozky["Schopnosti zázemí"], odkaz, IKONA_SCH,
                            p=s.get("p"), akt=[{"n": s["n"], "t": "special"}] if s.get("p") else (), pozadavek=z["nazev"]))
        bid = foundry_id(f"zazemi-{k}")
        adv = {}
        ostatni = [v for v in z.get("volby", []) if not str(v["z"][0]).startswith("languages")]
        jazyky = [v for v in z.get("volby", []) if str(v["z"][0]).startswith("languages")]
        aid, a = adv_trait(f"{k}-zdatnosti", "Zdatnosti", z.get("zdatnosti", []), ostatni)
        adv[aid] = a
        if jazyky:
            aid, a = adv_trait(f"{k}-jazyky", "Jazyky", [], jazyky)
            adv[aid] = a
        aid, a = adv_grant(f"{k}-schopnost", [uuid(sid)], "Schopnost zázemí")
        adv[aid] = a
        popis = (f"<p>{html.escape(z['popis'])}</p><p><strong>Schopnost:</strong> {html.escape(s['n'])}</p>"
                 f"<p><strong>Vybavení:</strong> {html.escape(z['vybaveni'])}</p>"
                 f"<p><em>Plné znění: <a href=\"{odkaz}\" target=\"_blank\">SRD Jeskyní a draků – Tvorba postavy</a>.</em></p>")
        polozky.append({"_id": bid, "name": z["nazev"], "type": "background", "img": IKONA_ZAZEMI, "folder": slozky["Zázemí"],
                        "sort": 0, "ownership": {"default": 0}, "effects": [],
                        "system": {"description": {"value": popis, "chat": ""},
                                   "source": {"custom": "", "book": "Jeskyně a draci", "page": "", "license": LICENCE, "rules": "2014"},
                                   "advancement": adv, "startingEquipment": startovni(f"zazemi-{k}", vyb.get(k), chyby),
                                   "identifier": slug(k)},
                        "flags": {MODUL: {"zazemi": k}}, "_stats": stats(), "_key": f"!items!{bid}"})

    for k, o in d["odbornosti"].items():
        oid = foundry_id(f"odbornost-{k}")
        postup = {}
        for t in ("trait", "trait2"):
            if o.get(t):
                aid, a = adv_trait(f"{k}-{t}", o["nazev"], o[t].get("zdatnosti", []), o[t].get("volby", []),
                                   o[t].get("rezim", "default"))
                postup[aid] = a
        if o.get("asi"):
            aid, a = adv_asi(f"{k}-asi", None, o["asi"], cap=1)
            postup[aid] = a
        polozky.append(feat(oid, o["nazev"], o["d"], "feat", slozky["Odbornosti"], SRD_ODB, IKONA_ODB, p=o.get("p"),
                            akt=o.get("akt", ()), pas=o.get("pas"), postup=postup, pozadavek=o.get("pozadavek", "")))

    for p in polozky:
        for e in p.get("effects", []):
            e["_key"] = f"!items.effects!{p['_id']}.{e['_id']}"
    cil = os.path.join(KOREN, "packs/_source", PACK)
    shutil.rmtree(cil, ignore_errors=True)
    os.makedirs(cil)
    for p in polozky:
        with open(os.path.join(cil, f"{slug(p['name'])}_{p['_id']}.json"), "w", encoding="utf-8") as fh:
            json.dump(p, fh, ensure_ascii=False, indent=2)
    for f in folders:
        with open(os.path.join(cil, f"_slozka_{slug(f['name'])}.json"), "w", encoding="utf-8") as fh:
            json.dump(f, fh, ensure_ascii=False, indent=2)
    bez = lambda o: {a: b for a, b in o.items() if a != "_key"}
    with open(os.path.join(KOREN, "data/kompendium/zazemi.json"), "w", encoding="utf-8") as fh:
        json.dump({"folders": [bez(f) for f in folders],
                   "items": [{**bez(p), "effects": [bez(e) for e in p.get("effects", [])]} for p in polozky]}, fh, ensure_ascii=False)
    from collections import Counter
    print("Zázemí a odbornosti:", dict(Counter(p["system"]["type"]["value"] if p["type"] == "feat" else p["type"] for p in polozky)))
    for c in chyby:
        print("CHYBA:", c)
    return 1 if chyby else 0


if __name__ == "__main__":
    sys.exit(main())
