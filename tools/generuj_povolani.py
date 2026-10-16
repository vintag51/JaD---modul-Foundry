#!/usr/bin/env python3
"""
Generátor kompendia povolání Jeskyní a draků (data/povolani/*.yml → packs/_source/povolani,
data/kompendium/povolani.json).

Každé povolání = položka „class“ s postupem (Body výdrže, zdatnosti, škály, zvýšení vlastností, volba oboru,
schopnosti po úrovních), každý obor = položka „subclass“, každá schopnost = položka „feat“ (druh „class“).

Použití: python3 tools/generuj_povolani.py
"""
import glob, html, json, os, re, shutil, sys
import yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generuj import KOREN, MODUL, foundry_id, nacti_yaml, slug, stats  # noqa: E402
from generuj_rasy import adv_asi, adv_grant, adv_trait, spell_cfg  # noqa: E402

PACK = "povolani"
SRD = "https://dnd5esrd.d20.cz/jeskyne-a-draci/4-povolani.html"
LICENCE = "Licence JaD pro třetí strany"
SKILL = {k: k for k in ["acr", "ani", "arc", "ath", "dec", "his", "ins", "itm", "inv", "med", "nat", "prc", "prf",
                        "per", "rel", "slt", "ste", "sur"]}
IKONY = {"class": "icons/sundries/books/book-red-exclamation.webp", "subclass": "icons/sundries/books/book-symbol-triangle-silver-blue.webp",
         "feat": "icons/skills/melee/weapons-crossed-swords-white-blue.webp"}
OBNOVA = {"sr": "sr", "lr": "lr", "day": "day"}
VLASTNOSTI = {"str", "dex", "con", "int", "wis", "cha"}


def uuid(iid):
    return f"Compendium.{MODUL}.{PACK}.Item.{iid}"


def kouzla_podle_nazvu():
    """Mapa český název kouzla → UUID v kompendiu kouzel."""
    out = {}
    for f in glob.glob(os.path.join(KOREN, "packs/_source/kouzla/[!_]*.json")):
        d = json.load(open(f, encoding="utf-8"))
        out[d["name"].lower()] = f"Compendium.{MODUL}.kouzla.Item.{d['_id']}"
    return out


def pouziti(p):
    if not p:
        return {"max": "", "spent": 0, "recovery": []}
    mx, ob = str(p).rsplit("/", 1)
    return {"max": mx, "spent": 0, "recovery": [{"period": OBNOVA[ob], "type": "recoverAll"}]}


def cast_zasahu(formula, typ):
    return {"number": None, "denomination": None, "bonus": "", "types": ([typ] if typ else []) if isinstance(typ, str) else list(typ),
            "custom": {"enabled": True, "formula": str(formula)}, "scaling": {"mode": "", "number": None, "formula": ""}}


def zmena(z, transfer=True):
    klic, hodnota, typ = (list(z) + ["add"])[:3]
    return {"key": klic, "value": hodnota, "type": typ, "phase": "initial", "priority": None}


def efekt(seed, nazev, zmeny, ikona, transfer, statusy=(), kola=None, popis=""):
    return {"_id": foundry_id(seed), "name": nazev, "img": ikona, "type": "base", "transfer": transfer,
            "disabled": False, "statuses": list(statusy), "tint": "#ffffff", "showIcon": 1,
            "duration": {"value": kola * 6 if kola else None, "units": "seconds", "expiry": "turnStart" if kola else None,
                         "expired": False},
            "system": {"changes": [zmena(z) for z in zmeny]},
            "description": f"<p>{html.escape(popis or nazev)}</p>", "flags": {}}


def aktivita(seed, a, idx, ma_pouziti, efekty_id):
    typ = a.get("typ", "utility")
    akt = {"_id": foundry_id(seed), "type": typ, "name": a.get("n", "Použít"), "img": "", "sort": idx * 100000, "flags": {},
           "activation": {"type": a.get("t", "action"), "value": None, "condition": a.get("podminka", ""), "override": False},
           "consumption": {"targets": [{"type": "itemUses", "value": "1", "target": "", "scaling": {}}]
                           if ma_pouziti and not a.get("bezpouziti") else [],
                           "scaling": {"allowed": False, "max": ""}, "spellSlot": False},
           "description": {"chatFlavor": ""},
           "duration": {"concentration": False, "value": "", "units": "inst", "special": "", "override": False},
           "effects": [{"_id": efekty_id[i], "level": {"min": None, "max": None}} for i in a.get("ef", [])],
           "range": {"units": "sah" if a.get("dosah") else "", "value": str(a.get("dosah", "")), "special": "", "override": False},
           "target": {"template": {"count": "", "contiguous": False, "type": "", "size": "", "width": "", "height": "", "units": ""},
                      "affects": {"count": "", "type": "", "choice": False, "special": ""}, "prompt": True, "override": False},
           "uses": {"spent": 0, "recovery": [], "max": ""},
           "visibility": {"level": {"min": None, "max": None}}}
    if a.get("spotreba"):  # vlastní spotřeba, např. [[activityUses, 1], [itemUses, -1]]
        akt["consumption"]["targets"] = [{"type": t, "value": str(v), "target": "", "scaling": {}} for t, v in a["spotreba"]]
    if a.get("pouziti"):  # vlastní počet použití aktivity, např. "1/lr"
        mx, ob = str(a["pouziti"]).rsplit("/", 1)
        akt["uses"] = {"spent": 0, "recovery": [{"period": OBNOVA[ob], "type": "recoverAll"}], "max": mx}
    if a.get("sablona"):
        s = a["sablona"]
        akt["target"]["template"] = {"count": "", "contiguous": False, "type": s["typ"], "size": str(s["velikost"]),
                                     "width": str(s.get("sirka", "")), "height": "", "units": "sah"}
        akt["target"]["affects"]["type"] = "creature"
    if a.get("hod"):
        akt["roll"] = {"formula": str(a["hod"]), "name": a.get("n", ""), "prompt": False, "visible": True}
    parts = [cast_zasahu(*d) for d in ([a["dmg"]] if a.get("dmg") and isinstance(a["dmg"][0], str) else a.get("dmg", []))]
    if typ == "heal":
        akt["healing"] = cast_zasahu(a["heal"], a.get("htyp", "healing"))
    elif typ == "save":
        dc = str(a.get("dc", "spellcasting"))
        akt["save"] = {"ability": [a["save"]] if isinstance(a["save"], str) else list(a["save"]),
                       "dc": {"calculation": dc if (dc in VLASTNOSTI or dc == "spellcasting") else "",
                              "formula": "" if (dc in VLASTNOSTI or dc == "spellcasting") else dc}}
        akt["damage"] = {"onSave": a.get("onsave", "half" if parts else "none"), "parts": parts}
    elif typ == "attack":
        akt["attack"] = {"ability": a.get("vlastnost", ""), "bonus": "", "critical": {"threshold": None}, "flat": False,
                         "type": {"value": a.get("utok", "melee"), "classification": a.get("druh", "weapon")}}
        akt["damage"] = {"critical": {"bonus": ""}, "includeBase": not parts, "parts": parts}
    elif typ == "damage":
        akt["damage"] = {"critical": {"allow": False}, "parts": parts}
    return akt


def popis(d, urovne, kotva, extra=""):
    ur = ", ".join(f"{u}." for u in urovne)
    out = f"<p>{html.escape(d)}</p>" if d else ""
    if extra:
        out += extra
    if ur:
        out += f"<p><em>Úroveň: {ur}</em></p>"
    out += f"<p><em>Plné znění: <a href=\"{SRD}#{kotva}\" target=\"_blank\">SRD Jeskyní a draků – Povolání</a>.</em></p>"
    return out


def schopnost(s, pozadavek, kotva, slozka, ikona=IKONY["feat"]):
    iid = foundry_id(f"povolani-schopnost-{pozadavek}-{s['k']}")
    ef_def = s.get("ef", [])
    efekty_id = [foundry_id(f"{iid}-ef-{i}") for i in range(len(ef_def))]
    efekty = [efekt(f"{iid}-ef-{i}", e["n"], e.get("z", []), ikona, False, e.get("st", []), e.get("kola"), s["n"])
              for i, e in enumerate(ef_def)]
    if s.get("pas"):
        efekty.append(efekt(f"{iid}-pas", s["n"], s["pas"], ikona, True, popis=f"{s['n']} (pasivní schopnost)"))
    for e in efekty:
        e["origin"] = uuid(iid)
    akt = {}
    for i, a in enumerate(s.get("akt", [])):
        x = aktivita(f"{iid}-akt-{i}", a, i, bool(s.get("p")), efekty_id)
        akt[x["_id"]] = x
    uses = pouziti(s.get("p"))
    for o in s.get("obnova", []):  # další způsoby obnovy, např. {period: sr, formula: "..."}
        uses["recovery"].append({"period": o["period"], "type": "formula", "formula": str(o["formula"])})
    postup = {}
    if s.get("trait"):
        aid, adv = adv_trait(f"{iid}-trait", s["n"], s["trait"].get("zdatnosti", []), s["trait"].get("volby", []),
                             s["trait"].get("rezim", "default"))
        postup[aid] = adv
    extra = ""
    if s.get("seznam"):
        extra = "<ul>" + "".join(f"<li>{html.escape(x)}</li>" for x in s["seznam"]) + "</ul>"
    return {
        "_id": iid, "name": s["n"], "type": "feat", "img": s.get("ikona", ikona), "folder": slozka, "sort": min(s.get("u") or [0]) * 1000,
        "ownership": {"default": 0}, "effects": efekty,
        "system": {"description": {"value": popis(s.get("d", ""), s.get("u", []), kotva, extra), "chat": ""},
                   "source": {"custom": "", "book": "Jeskyně a draci", "page": "", "license": LICENCE, "rules": "2014"},
                   "uses": uses, "type": {"value": "class", "subtype": ""},
                   "requirements": f"{pozadavek} {min(s['u'])}" if s.get("u") else pozadavek, "properties": [],
                   "activities": akt, "enchant": {}, "prerequisites": {"level": None}, "identifier": slug(s["k"]),
                   "advancement": postup},
        "flags": {MODUL: {"povolani": True}}, "_stats": stats(), "_key": f"!items!{iid}"}


def granty_po_urovnich(seed, schopnosti, ids):
    adv = {}
    po = {}
    for s in schopnosti:
        if s.get("u"):
            po.setdefault(min(s["u"]), []).append(ids[s["k"]])
    for lvl, polozky in sorted(po.items()):
        aid, a = adv_grant(f"{seed}-uroven-{lvl}", [uuid(i) for i in polozky], "Schopnosti", lvl)
        adv[aid] = a
    return adv


def skala(seed, ident, s):
    aid = foundry_id(seed)
    typ = s.get("typ", "number")
    sc = {}
    for lvl, v in s["hodnoty"].items():
        if typ == "dice":
            n, f = str(v).split("d")
            sc[str(lvl)] = {"number": int(n) if n else 1, "faces": int(f), "modifiers": []}
        elif typ == "distance":
            sc[str(lvl)] = {"value": v}
        else:
            sc[str(lvl)] = {"value": v}
    return aid, {"_id": aid, "type": "ScaleValue", "level": 0, "title": s["nazev"], "hint": "", "flags": {},
                 "configuration": {"identifier": ident, "type": typ, "distance": {"units": "sah" if typ == "distance" else ""}, "scale": sc},
                 "value": {}}


def volby(seed, seznam, ids, kouzla, chyby):
    """ItemChoice: výběr schopností (feat) nebo kouzel (spell) na daných úrovních."""
    adv = {}
    for i, v in enumerate(seznam):
        aid = foundry_id(f"{seed}-{i}")
        typ = v.get("typ", "feat")
        pool = []
        for k in v.get("z", []):
            if typ == "feat" and k in ids:
                pool.append(uuid(ids[k]))
            elif typ == "spell" and kouzla.get(k.lower()):
                pool.append(kouzla[k.lower()])
            else:
                chyby.append(f"volba {v['nazev']}: „{k}“ nenalezeno")
        cfg = spell_cfg(v.get("vlastnost"), v.get("max", ""), v.get("obnova", ""))
        restr = {"type": "", "subtype": "", "level": str(v.get("stupen", "")),
                 "list": [f"class:{v['seznam']}"] if v.get("seznam") else []}
        adv[aid] = {"_id": aid, "type": "ItemChoice", "level": 0, "title": v["nazev"], "hint": "", "flags": {},
                    "configuration": {"choices": {str(l): {"count": c, "replacement": bool(v.get("vymena"))}
                                                  for l, c in v["pocty"].items()},
                                      "allowDrops": True, "type": typ, "pool": [{"uuid": u} for u in pool],
                                      "spell": cfg, "restriction": restr},
                    "value": {"added": {}, "replaced": {}}}
    return adv


# Počty známých triků a kouzel (tabulky povolání; shodné s 5E SRD, Theurg dle SRD JaD).
_TRETINOVY = {"triky": {3: 2, 10: 3},
              "kouzla": {3: 3, 4: 4, 7: 5, 8: 6, 10: 7, 11: 8, 13: 9, 14: 10, 16: 11, 19: 12, 20: 13}}
ZNAMA_KOUZLA = {
    "bard": {"triky": {1: 2, 4: 3, 10: 4},
             "kouzla": {1: 4, 2: 5, 3: 6, 4: 7, 5: 8, 6: 9, 7: 10, 8: 11, 9: 12, 10: 14, 11: 15, 13: 16, 14: 18,
                        15: 19, 17: 20, 18: 22}},
    "sorcerer": {"triky": {1: 4, 4: 5, 10: 6},
                 "kouzla": {1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 8, 8: 9, 9: 10, 10: 11, 11: 12, 13: 13, 15: 14, 17: 15}},
    "warlock": {"triky": {1: 2, 4: 3, 10: 4},
                "kouzla": {1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 8, 8: 9, 9: 10, 11: 11, 13: 12, 15: 13, 17: 14, 19: 15}},
    "wizard": {"triky": {1: 3, 4: 4, 10: 5}, "kniha": {1: 6, **{u: 2 for u in range(2, 21)}}},
    "cleric": {"triky": {1: 3, 4: 4, 10: 5}},
    "druid": {"triky": {1: 2, 4: 3, 10: 4}},
    "theurg": _TRETINOVY, "chodec": _TRETINOVY, "chramovy-rytir": _TRETINOVY, "svatokupec": _TRETINOVY,
    "rad-zaprodancu": _TRETINOVY,
}


def prirustky(tabulka):
    """{úroveň: celkem} → {úroveň: přírůstek}."""
    out, predchozi = {}, 0
    for u in sorted(tabulka):
        if tabulka[u] > predchozi:
            out[u] = tabulka[u] - predchozi
        predchozi = tabulka[u]
    return out


def volby_kouzel(seed, klic, seznam, vlastnost):
    """ItemChoice pro výběr triků a kouzel při postupu na Úroveň (filtr podle seznamu kouzel povolání)."""
    t = ZNAMA_KOUZLA.get(klic)
    if not t or not vlastnost:
        return {}
    adv = {}

    def pridej(nazev, pocty, stupen, vymena, pripraveno):
        aid = foundry_id(f"{seed}-{nazev}")
        adv[aid] = {"_id": aid, "type": "ItemChoice", "level": 0, "title": nazev, "hint": "", "flags": {},
                    "configuration": {"choices": {str(u): {"count": c, "replacement": bool(vymena and u > min(pocty))}
                                                  for u, c in pocty.items()},
                                      "allowDrops": True, "type": "spell", "pool": [],
                                      "spell": {"ability": [vlastnost], "uses": {"max": "", "per": "", "requireSlot": False},
                                                "method": "spell", "prepared": pripraveno},
                                      "restriction": {"type": "", "subtype": "", "level": stupen, "list": [seznam]}},
                    "value": {"added": {}, "replaced": {}}}

    if t.get("triky"):
        pridej("Triky", prirustky(t["triky"]), "0", False, 1)
    if t.get("kouzla"):
        pridej("Známá kouzla", prirustky(t["kouzla"]), "availableNoCantrips", True, 1)
    if t.get("kniha"):
        pridej("Kouzla do knihy kouzel", t["kniha"], "availableNoCantrips", False, 0)
    return adv


def kouzleni(k):
    if not k:
        return {"progression": "none", "ability": "", "preparation": {}}
    return {"progression": k["progrese"], "ability": k["vlastnost"], "preparation": {"formula": k.get("priprava", "")}}


def main():
    soubory = sorted(glob.glob(os.path.join(KOREN, "data/povolani/*.yml")))
    kouzla = kouzla_podle_nazvu()
    slozky = {}
    folders = []

    def slozka(nazev, rodic=None):
        if nazev not in slozky:
            fid = foundry_id(f"povolani-slozka-{nazev}")
            slozky[nazev] = fid
            folders.append({"_id": fid, "name": nazev, "type": "Item", "sorting": "a", "sort": len(folders) * 100000,
                            "folder": rodic, "color": None, "flags": {}, "_key": f"!folders!{fid}"})
        return slozky[nazev]

    f_pov = slozka("Povolání")
    polozky, chyby = [], []
    from vybava import startovni
    vyb = (yaml.safe_load(open(os.path.join(KOREN, "data/vybaveni-startovni.yml"), encoding="utf-8")) or {}).get("povolani", {})
    for f in soubory:
        p = yaml.safe_load(open(f, encoding="utf-8"))
        cid = p["identifikator"]
        sv = vyb.get(os.path.basename(f)[:-4], {})
        f_sch = slozka(f"Schopnosti – {p['nazev']}")
        ids = {}
        for s in p.get("schopnosti", []):
            it = schopnost(s, p["nazev"], p.get("kotva", ""), f_sch)
            ids[s["k"]] = it["_id"]
            polozky.append(it)

        # postup povolání
        adv = {}
        hp = foundry_id(f"{cid}-hp")
        adv[hp] = {"_id": hp, "type": "HitPoints", "level": 0, "title": "Body výdrže", "hint": "", "flags": {},
                   "configuration": {}, "value": {}}
        for nazev, zd in (("Zbroje", p.get("zbroje", [])), ("Zbraně", p.get("zbrane", [])), ("Pomůcky", p.get("pomucky", []))):
            if zd:
                aid, a = adv_trait(f"{cid}-{nazev}", nazev, zd)
                a["level"] = 1
                adv[aid] = a
        if p.get("volby_pomucek"):
            aid, a = adv_trait(f"{cid}-volby-pomucek", "Pomůcky dle volby", [], p["volby_pomucek"])
            a["level"] = 1
            adv[aid] = a
        aid, a = adv_trait(f"{cid}-zachrany", "Záchranné hody", [f"saves:{x}" for x in p["zachrany"]])
        a["level"] = 1
        a["classRestriction"] = "primary"
        adv[aid] = a
        dv = p["dovednosti"]
        z = [f"skills:{SKILL[x]}" for x in dv["z"]] if dv.get("z") else ["skills:*"]
        aid, a = adv_trait(f"{cid}-dovednosti", "Dovednosti", [], [{"pocet": dv["pocet"], "z": z}])
        a["level"] = 1
        a["classRestriction"] = "primary"
        adv[aid] = a
        for sid, s in (p.get("skaly") or {}).items():
            aid, a = skala(f"{cid}-skala-{sid}", sid, s)
            adv[aid] = a
        for lvl in p.get("asi", []):
            aid, a = adv_asi(f"{cid}-asi-{lvl}", None, 2, cap=2)
            a["level"] = lvl
            a["title"] = "Zvýšení Hodnot vlastností"
            adv[aid] = a
        sub = foundry_id(f"{cid}-obor")
        adv[sub] = {"_id": sub, "type": "Subclass", "level": p["obor"]["uroven"], "title": p["obor"]["nazev"], "hint": "",
                    "flags": {}, "configuration": {}, "value": {}}
        adv.update(granty_po_urovnich(f"{cid}-granty", p.get("schopnosti", []), ids))
        adv.update(volby(f"{cid}-volba", p.get("volby", []), ids, kouzla, chyby))
        adv.update(volby_kouzel(f"{cid}-znama", cid, f"class:{cid}", (p.get("kouzleni") or {}).get("vlastnost")))

        cls_id = foundry_id(f"povolani-{cid}")
        tab = ""
        polozky.append({
            "_id": cls_id, "name": p["nazev"], "type": "class", "img": p.get("ikona", IKONY["class"]), "folder": f_pov, "sort": 0,
            "ownership": {"default": 0}, "effects": [],
            "system": {"description": {"value": popis(p["popis"], [], p.get("kotva", "")) + tab, "chat": ""},
                       "source": {"custom": "", "book": "Jeskyně a draci", "page": "", "license": LICENCE, "rules": "2014"},
                       "identifier": cid, "levels": 1, "hd": {"denomination": p["kostka"], "spent": 0, "additional": ""},
                       "hitDice": p["kostka"], "hitDiceUsed": 0, "advancement": adv,
                       "spellcasting": kouzleni(p.get("kouzleni")), "startingEquipment": startovni(f"povolani-{cid}", sv.get("vybaveni"), chyby),
                       "wealth": sv.get("bohatstvi") or p.get("bohatstvi", ""),
                       "primaryAbility": {"value": p.get("hlavni", []), "all": True}},
            "flags": {MODUL: {"povolani": cid}}, "_stats": stats(), "_key": f"!items!{cls_id}"})

        # obory
        f_ob = slozka(f"Obory – {p['nazev']}")
        for oid, o in (p.get("obory") or {}).items():
            oids = {}
            for s in o.get("schopnosti", []):
                it = schopnost(s, o["nazev"], o.get("kotva", ""), f_ob)
                oids[s["k"]] = it["_id"]
                polozky.append(it)
            oadv = granty_po_urovnich(f"{oid}-granty", o.get("schopnosti", []), oids)
            for i, blok in enumerate(o.get("kouzla", [])):
                uu = []
                for n in blok["kouzla"]:
                    u = kouzla.get(n.lower())
                    if u:
                        uu.append(u)
                    else:
                        chyby.append(f"{o['nazev']}: kouzlo „{n}“ nenalezeno")
                if uu:
                    aid, a = adv_grant(f"{oid}-kouzla-{i}", uu, o.get("kouzla_nazev", "Kouzla oboru"), blok["uroven"],
                                       {"ability": [], "uses": {"max": "", "per": "", "requireSlot": False},
                                        "method": "spell", "prepared": 2})
                    oadv[aid] = a
            oadv.update(volby(f"{oid}-volba", o.get("volby", []), oids, kouzla, chyby))
            oadv.update(volby_kouzel(f"{oid}-znama", slug(oid), f"subclass:{slug(oid)}",
                                     (o.get("kouzleni") or {}).get("vlastnost")))
            for sid, s in (o.get("skaly") or {}).items():
                aid, a = skala(f"{oid}-skala-{sid}", sid, s)
                oadv[aid] = a
            sub_id = foundry_id(f"povolani-obor-{oid}")
            polozky.append({
                "_id": sub_id, "name": o["nazev"], "type": "subclass", "img": o.get("ikona", IKONY["subclass"]), "folder": f_ob,
                "sort": 0, "ownership": {"default": 0}, "effects": [],
                "system": {"description": {"value": popis(o["popis"], [], o.get("kotva", "")), "chat": ""},
                           "source": {"custom": "", "book": "Jeskyně a draci", "page": "", "license": LICENCE, "rules": "2014"},
                           "identifier": slug(oid), "classIdentifier": cid, "advancement": oadv,
                           "spellcasting": kouzleni(o.get("kouzleni"))},
                "flags": {MODUL: {"obor": oid}}, "_stats": stats(), "_key": f"!items!{sub_id}"})

    for p in polozky:
        for e in p.get("effects", []):
            e["_key"] = f"!items.effects!{p['_id']}.{e['_id']}"
    nazvy = {}
    for p in polozky:
        nazvy.setdefault((p["type"], p["name"], p["folder"]), []).append(p["_id"])
    idy = [p["_id"] for p in polozky]
    if len(set(idy)) != len(idy):
        chyby.append("duplicitní ID položek")

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
    os.makedirs(os.path.join(KOREN, "data/kompendium"), exist_ok=True)
    with open(os.path.join(KOREN, "data/kompendium/povolani.json"), "w", encoding="utf-8") as fh:
        json.dump({"folders": [bez(f) for f in folders],
                   "items": [{**bez(p), "effects": [bez(e) for e in p.get("effects", [])]} for p in polozky]}, fh, ensure_ascii=False)
    from collections import Counter
    print("Povolání:", dict(Counter(p["type"] for p in polozky)))
    for c in chyby:
        print("  !", c)
    return 1 if chyby else 0


if __name__ == "__main__":
    sys.exit(main())
