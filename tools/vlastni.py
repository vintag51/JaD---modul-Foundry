"""
Sestavení původních kouzel JaD (mimo SRD 5.1) z kompaktního zápisu v data/vlastni-kouzla.yml
do plné podoby položky "spell" systému dnd5e.

Název, Stupeň, škola, povolání a příznak rituálu se berou z data/jad-kouzla.yml (klíč = kotva).

Formát zápisu (klíč = kotva kouzla):

  hadi-ustknuti:
    shrnuti: Vlastní krátké shrnutí (NE text z knihy).
    slozky: [V, S, M]            # značky dnd5e: V verbální, S pohybová (JaD „P“), M surovinová (JaD „S“)
    material: zub jedovatého hada
    material_cena: 0             # v zlaťácích; material_spotreba: true = kouzlo surovinu spotřebuje
    sesilani: action             # action | bonus | reaction | minute | hour
    dosah: {hodnota: 6}          # v sázích; nebo {jednotky: self | touch | spec}
    trvani: {jednotky: inst}     # inst | round | minute | hour | day; hodnota: N
    soustredeni: false
    cil: {pocet: 1, typ: creature, sablona: {typ: cone, velikost: 2}}   # sablona: sphere|cone|line|cube|cylinder|radius
    efekty:
      - {id: hluchota, nazev: Ohlušený, stavy: [deafened], kola: 1, konec: turnEnd}
    aktivity:
      - typ: attack              # attack | save | damage | heal | utility
        utok: melee              # melee | ranged
        zachrana: con            # u typ save (lze seznam)
        pri_uspechu: half        # half | none
        zasah: [{kostky: 1d4, typ: piercing, skalovani: 1d4}, {kostky: 1d4, typ: poison, skalovani: 1d4}]
        leceni: {kostky: "", bonus: "1 + @prof", typ: healing}
        efekty: [hluchota]
"""
import re

IKONY = {"abj": "icons/magic/defensive/shield-barrier-blue.webp", "con": "icons/magic/symbols/runes-star-pentagon-blue.webp",
         "div": "icons/magic/perception/eye-ringed-glow-yellow.webp", "enc": "icons/magic/control/hypnosis-mesmerism-swirl.webp",
         "evo": "icons/magic/lightning/bolt-strike-blue.webp", "ill": "icons/magic/control/silhouette-hold-change-blue.webp",
         "nec": "icons/magic/unholy/strike-body-explode-disintegrate.webp", "trs": "icons/magic/earth/projectile-stone-boulder-orange.webp"}


def _cast(z, stupen):
    typy = z.get("typ") or []
    typy = typy if isinstance(typy, list) else [typy]
    m = re.match(r"^(\d+)d(\d+)$", str(z.get("kostky", "")))
    cast = {"number": int(m.group(1)) if m else None, "denomination": int(m.group(2)) if m else None,
            "bonus": str(z.get("bonus", "")), "types": typy,
            "custom": {"enabled": bool(z.get("kostky")) and not m, "formula": "" if m else str(z.get("kostky", ""))},
            "scaling": {"mode": "", "number": None, "formula": ""}}
    sk = z.get("skalovani")
    if sk:
        ms = re.match(r"^(\d+)d(\d+)$", str(sk))
        if ms and m and ms.group(2) == m.group(2):
            cast["scaling"] = {"mode": "whole", "number": int(ms.group(1)), "formula": ""}
        else:
            cast["scaling"] = {"mode": "whole", "number": None, "formula": str(sk)}
    return cast


def _aktivita(a, idx, fid, ident, stupen):
    typ = a.get("typ", "utility")
    akt = {
        "_id": fid(f"{ident}-aktivita-{idx}"), "type": typ, "img": "", "sort": idx * 100000,
        "name": a.get("nazev", "Seslat" if idx == 0 else f"Aktivita {idx + 1}"),
        "activation": {"type": a.get("sesilani", "action"), "value": None, "override": "sesilani" in a,
                       "condition": a.get("podminka", "")},
        "consumption": {"targets": [], "scaling": {"allowed": False, "max": ""},
                        "spellSlot": a.get("spotrebuje_pozici", idx == 0)},
        "description": {"chatFlavor": ""},
        "duration": {"units": "inst", "concentration": False, "override": False},
        "effects": [{"_id": fid(f"{ident}-efekt-{e}"), "level": {"min": None, "max": None}} for e in a.get("efekty", [])],
        "range": {"override": False},
        "target": {"prompt": True, "override": False, "template": {"contiguous": False, "units": "sah"}, "affects": {"choice": False}},
        "uses": {"spent": 0, "recovery": [], "max": ""},
        "visibility": {"level": {"min": None, "max": None}}
    }
    if a.get("dosah"):
        akt["range"] = {"override": True, "value": str(a["dosah"]), "units": "sah", "special": ""}
    if a.get("sablona"):
        s = a["sablona"]
        akt["target"] = {"prompt": True, "override": True, "affects": {"choice": False, "count": "", "type": "creature", "special": ""},
                         "template": {"contiguous": False, "units": "sah", "type": s["typ"], "size": str(s["velikost"]),
                                      "width": str(s.get("sirka", "")), "height": "", "count": ""}}
    for e in akt["effects"]:
        e["onSave"] = False
    casti = [_cast(z, stupen) for z in a.get("zasah", [])]
    if typ == "attack":
        akt["attack"] = {"ability": "", "bonus": "", "critical": {"threshold": None}, "flat": False,
                         "type": {"value": a.get("utok", "ranged"), "classification": "spell"}}
        akt["damage"] = {"critical": {"bonus": ""}, "includeBase": True, "parts": casti}
    elif typ == "save":
        z = a.get("zachrana", "dex")
        akt["save"] = {"ability": z if isinstance(z, list) else [z], "dc": {"calculation": "spellcasting", "formula": ""}}
        akt["damage"] = {"onSave": a.get("pri_uspechu", "half" if casti else "none"), "parts": casti}
    elif typ == "damage":
        akt["damage"] = {"critical": {"allow": False}, "parts": casti}
    elif typ == "heal":
        akt["healing"] = _cast(a["leceni"], stupen)
    return akt


def _efekt(e, ident, fid, cz, ikona):
    kola = e.get("kola")
    trvani = {"value": kola * 6 if kola else e.get("sekundy"), "units": "seconds", "expiry": e.get("konec", "turnStart"),
              "expired": False}
    return {
        "_id": fid(f"{ident}-efekt-{e['id']}"), "name": e["nazev"], "img": e.get("ikona", ikona), "type": "base",
        "transfer": False, "disabled": False, "statuses": e.get("stavy", []), "duration": trvani, "tint": "#ffffff",
        "system": {"changes": [{"key": c["klic"], "value": c["hodnota"], "type": c.get("typ", "add"), "phase": "initial",
                                "priority": None} for c in e.get("zmeny", [])]},
        "description": f"<p>Účinek kouzla <em>{cz}</em>. Podrobnosti v popisu kouzla.</p>",
        "flags": {"dnd5e": {"riders": {"statuses": []}}}
    }


def sestav(ident, s, fid, jednotky="sah"):
    stupen = int(s["stupen"])
    ikona = s.get("ikona", IKONY.get(s["skola"], IKONY["con"]))
    sl = [x.upper() for x in s.get("slozky", [])]
    vlastnosti = [p for k, p in (("V", "vocal"), ("S", "somatic"), ("M", "material"), ("R", "ritual")) if k in sl]
    if s.get("soustredeni"):
        vlastnosti.append("concentration")
    dosah = s.get("dosah", {"jednotky": "self"})
    dj = dosah.get("jednotky", "sah")
    hodnota = dosah.get("hodnota", "")
    if dj == "sah" and jednotky == "ft" and hodnota != "":
        hodnota, dj = hodnota * 5, "ft"
    trvani = s.get("trvani", {"jednotky": "inst"})
    cil = s.get("cil", {})
    sab = cil.get("sablona") or {}
    sab_j = "ft" if jednotky == "ft" else "sah"
    nasob = 5 if jednotky == "ft" else 1
    akt = {}
    for i, a in enumerate(s.get("aktivity", [{"typ": "utility"}])):
        x = _aktivita(a, i, fid, ident, stupen)
        if jednotky == "ft":
            x["target"]["template"]["units"] = "ft"
        akt[x["_id"]] = x
    return {
        "_id": fid(ident), "name": s["cz"], "type": "spell", "img": ikona, "ownership": {"default": 0}, "sort": 0,
        "effects": [_efekt(e, ident, fid, s["cz"], ikona) for e in s.get("efekty", [])],
        "system": {
            "identifier": ident, "level": stupen, "school": s["skola"], "properties": vlastnosti,
            "materials": {"value": s.get("material", ""), "consumed": bool(s.get("material_spotreba")),
                          "cost": int(s.get("material_cena", 0)), "supply": 0},
            "activation": {"type": s.get("sesilani", "action"), "value": s.get("sesilani_hodnota", 1), "condition": ""},
            "range": {"value": str(hodnota), "units": dj, "special": ""},
            "duration": {"value": str(trvani.get("hodnota", "")), "units": trvani.get("jednotky", "inst")},
            "target": {"affects": {"choice": False, "count": str(cil.get("pocet", "")), "type": cil.get("typ", ""),
                                   "special": ""},
                       "template": {"units": sab_j, "type": sab.get("typ", ""),
                                    "size": str(sab["velikost"] * nasob) if sab.get("velikost") else "",
                                    "width": str(sab["sirka"] * nasob) if sab.get("sirka") else "",
                                    "contiguous": False, "count": ""}},
            "uses": {"max": "", "recovery": [], "spent": 0},
            "preparation": {"mode": "prepared", "prepared": False},
            "activities": akt,
            "source": {"custom": "", "book": "Jeskyně a draci", "page": "", "license": "Licence JaD pro třetí strany", "rules": "2014"},
            "description": {"value": "", "chat": ""}
        },
        "flags": {"jeskyne-a-draci": {"vlastni": True}},
    }
