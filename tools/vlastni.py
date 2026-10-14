"""
Sestavení kouzel mimo SRD 5.1 (kouzla z Příručky hráče mimo SRD a původní kouzla JaD)
z kompaktního zápisu v data/vlastni-kouzla.yml do plné podoby položky dnd5e.

Příklad zápisu:

  witch-bolt:
    cz: Čarodějnický blesk
    stupen: 1
    skola: evo                 # abj con div enc evo ill nec trs
    slozky: [V, S, M]          # V=vocal S=somatic M=material, R=ritual, C=concentration
    material: větvička ze stromu zasaženého bleskem
    sesilani: action           # action bonus reaction minute hour
    dosah: {hodnota: 9, jednotky: m}      # nebo {jednotky: self|touch}
    trvani: {hodnota: 1, jednotky: minute}
    cil: {pocet: 1, typ: creature}        # nebo sablona: {typ: sphere|cone|line|cube, velikost: 6}
    shrnuti: Oblouk modré energie spojí tebe a cíl a každé kolo ho můžeš znovu zasáhnout.
    povolani: [sorcerer, warlock, wizard]
    aktivity:
      - typ: attack            # attack save heal damage utility
        utok: ranged           # ranged melee
        zraneni: [{kostky: 1d12, typ: lightning, skalovani: 1d12}]
      - typ: damage
        nazev: Zranění v dalším kole
        sesilani: action
        zraneni: [{kostky: 1d12, typ: lightning}]
"""
import copy, re

SESILANI = {"action", "bonus", "reaction", "minute", "hour", "day", "special"}


def _cast(z):
    m = re.match(r"^(\d+)d(\d+)$", str(z.get("kostky", "")))
    cast = {"number": int(m.group(1)) if m else None, "denomination": int(m.group(2)) if m else None,
            "bonus": str(z.get("bonus", "")), "types": [z["typ"]] if z.get("typ") else [],
            "custom": {"enabled": not m and bool(z.get("kostky")), "formula": "" if m else str(z.get("kostky", ""))},
            "scaling": {"mode": "", "number": None, "formula": ""}}
    sk = z.get("skalovani")
    if sk:
        ms = re.match(r"^(\d+)d(\d+)$", str(sk))
        if ms and m and ms.group(2) == m.group(2):
            cast["scaling"] = {"mode": "whole", "number": int(ms.group(1)), "formula": ""}
        else:
            cast["scaling"] = {"mode": "whole", "number": None, "formula": str(sk)}
    return cast


def _aktivita(a, idx, foundry_id, ident):
    aid = foundry_id(f"{ident}-aktivita-{idx}")
    typ = a.get("typ", "utility")
    akt = {
        "_id": aid, "type": typ, "name": a.get("nazev", "Seslat" if idx == 0 else f"Aktivita {idx + 1}"),
        "img": "", "sort": idx * 100000,
        "activation": {"type": a.get("sesilani", "action"), "value": None, "override": "sesilani" in a, "condition": a.get("podminka", "")},
        "consumption": {"targets": [], "scaling": {"allowed": False, "max": ""}, "spellSlot": idx == 0},
        "description": {"chatFlavor": ""},
        "duration": {"units": "inst", "concentration": False, "override": False},
        "effects": [{"_id": foundry_id(f"{ident}-efekt-{e}"), "level": {"min": None, "max": None}} for e in a.get("efekty", [])],
        "range": {"override": False}, "target": {"prompt": True, "override": False, "template": {"contiguous": False, "units": "m"}, "affects": {"choice": False}},
        "uses": {"spent": 0, "recovery": [], "max": ""},
        "visibility": {"level": {"min": None, "max": None}}
    }
    casti = [_cast(z) for z in a.get("zraneni", [])]
    if typ == "attack":
        akt["attack"] = {"ability": "", "bonus": "", "critical": {"threshold": None}, "flat": False,
                         "type": {"value": a.get("utok", "ranged"), "classification": "spell"}}
        akt["damage"] = {"critical": {"bonus": ""}, "includeBase": True, "parts": casti}
    elif typ == "save":
        akt["save"] = {"ability": a.get("zachrana", ["dex"]) if isinstance(a.get("zachrana"), list) else [a.get("zachrana", "dex")],
                       "dc": {"calculation": "spellcasting", "formula": ""}}
        akt["damage"] = {"onSave": a.get("pri_uspechu", "half" if casti else "none"), "parts": casti}
    elif typ == "damage":
        akt["damage"] = {"critical": {"allow": False}, "parts": casti}
    elif typ == "heal":
        akt["healing"] = _cast(a["leceni"])
    return akt


def sestav(ident, s, foundry_id, ikona="icons/magic/symbols/runes-star-pentagon-blue.webp"):
    sl = [x.upper() for x in s.get("slozky", [])]
    vlastnosti = [p for k, p in (("V", "vocal"), ("S", "somatic"), ("M", "material"), ("R", "ritual"), ("C", "concentration")) if k in sl]
    dosah = s.get("dosah", {"jednotky": "self"})
    trvani = s.get("trvani", {"jednotky": "inst"})
    cil = s.get("cil", {})
    sab = cil.get("sablona") or {}
    efekty = []
    for i, e in enumerate(s.get("efekty", [])):
        efekty.append({
            "_id": foundry_id(f"{ident}-efekt-{i}"), "name": e["nazev"], "img": e.get("ikona", ikona),
            "type": "base", "transfer": False, "disabled": False, "statuses": e.get("stavy", []),
            "duration": {"value": e.get("trvani"), "units": e.get("jednotky_trvani", "seconds"), "expiry": e.get("konec"), "expired": False},
            "system": {"changes": [{"key": c["klic"], "value": str(c["hodnota"]), "type": c.get("typ", "add"), "priority": None}
                                   for c in e.get("zmeny", [])]},
            "description": f"<p>Účinek kouzla <em>{s['cz']}</em>.</p>", "tint": "#ffffff", "flags": {}
        })
    akt = {}
    for i, a in enumerate(s.get("aktivity", [{"typ": "utility"}])):
        x = _aktivita(a, i, foundry_id, ident)
        akt[x["_id"]] = x
    return {
        "_id": foundry_id(ident), "name": s["cz"], "type": "spell", "img": s.get("ikona", ikona),
        "ownership": {"default": 0}, "sort": 0, "effects": efekty,
        "system": {
            "identifier": ident, "level": int(s["stupen"]), "school": s["skola"], "properties": vlastnosti,
            "materials": {"value": s.get("material", ""), "consumed": bool(s.get("material_spotreba")),
                          "cost": int(s.get("material_cena", 0)), "supply": 0},
            "activation": {"type": s.get("sesilani", "action"), "value": s.get("sesilani_hodnota", 1), "condition": s.get("podminka", "")},
            "range": {"value": str(dosah.get("hodnota", "")), "units": dosah.get("jednotky", "m"), "special": ""},
            "duration": {"value": str(trvani.get("hodnota", "")), "units": trvani.get("jednotky", "inst")},
            "target": {"affects": {"choice": False, "count": str(cil.get("pocet", "")), "type": cil.get("typ", "")},
                       "template": {"units": "m", "type": sab.get("typ", ""), "size": str(sab.get("velikost", "")),
                                    "contiguous": False, "count": ""}},
            "uses": {"max": "", "recovery": [], "spent": 0},
            "preparation": {"mode": "prepared", "prepared": False},
            "activities": akt,
            "source": {"custom": "", "book": "Jeskyně a draci", "page": str(s.get("strana", "")), "license": s.get("licence", ""), "rules": "2014"},
            "description": {"value": "", "chat": ""}
        },
        "flags": {"jeskyne-a-draci": {"vlastni": True, "overeno": bool(s.get("overeno")), "povolani": s.get("povolani", [])}},
    }
