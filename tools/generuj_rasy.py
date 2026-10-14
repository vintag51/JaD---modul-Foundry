#!/usr/bin/env python3
"""
Generátor kompendia ras Jeskyní a draků (data/rasy.yml → packs/_source/rasy, data/kompendium/rasy.json).

Každý rod je samostatná položka typu „race“ (dnd5e podrasy neskládá), rasové schopnosti jsou položky typu
„feat“ (druh „race“) přidávané postupem (advancement) při přetažení rasy na postavu.

Použití: python3 tools/generuj_rasy.py
"""
import html, json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generuj import KOREN, MODUL, foundry_id, nacti_yaml, slug, stats  # noqa: E402

SRD_RASY = "https://dnd5esrd.d20.cz/jeskyne-a-draci/3-rasy.html"
SRD_TVORBA = "https://dnd5esrd.d20.cz/jeskyne-a-draci/2-tvorba-postavy.html"
PACK = "rasy"
VLASTNOSTI = ["str", "dex", "con", "int", "wis", "cha"]
OBNOVA = {"sr": "sr", "lr": "lr"}
IKONA_RASY = "icons/environment/people/group.webp"
IKONA_SCHOPNOSTI = "icons/sundries/books/book-embossed-bound-brown.webp"
IKONY_DECHU = {"fire": "icons/magic/fire/projectile-fireball-orange.webp", "cold": "icons/magic/water/projectile-ice-snowball.webp",
               "lightning": "icons/magic/lightning/bolt-strike-blue.webp", "acid": "icons/magic/acid/projectile-faceted-glob.webp",
               "poison": "icons/magic/death/skull-poison-green.webp", "thunder": "icons/magic/sonic/explosion-shock-wave-teal.webp",
               "radiant": "icons/magic/light/beam-rays-yellow.webp", "necrotic": "icons/magic/unholy/projectile-bolts-salvo-pink.webp",
               "psychic": "icons/magic/control/fear-fright-monster-purple-blue.webp", "force": "icons/magic/sonic/projectile-sound-rings-wave.webp"}


def uuid(pack, iid):
    return f"Compendium.{MODUL}.{pack}.Item.{iid}"


def kouzlo_uuid(ident):
    return f"Compendium.{MODUL}.kouzla.Item.{foundry_id(ident)}"


def pomocne(seed):
    """ID pro vnořené dokumenty (aktivity, efekty, postup)."""
    return foundry_id(seed)


# ---------------------------------------------------------------- postup (advancement)

def adv_trait(seed, titulek, zdatnosti=(), volby=(), rezim="default", uroven=0):
    aid = pomocne(seed)
    return aid, {"_id": aid, "type": "Trait", "level": uroven, "title": titulek, "hint": "", "flags": {},
                 "configuration": {"mode": rezim, "allowReplacements": False, "grants": list(zdatnosti),
                                   "choices": [{"count": v["pocet"], "pool": list(v["z"])} for v in volby]},
                 "value": {"chosen": []}}


def adv_asi(seed, fixni=None, body=0, omezeni=None, cap=2):
    aid = pomocne(seed)
    fixed = {k: (fixni or {}).get(k, 0) for k in VLASTNOSTI}
    locked = [k for k in VLASTNOSTI if omezeni and k not in omezeni]
    return aid, {"_id": aid, "type": "AbilityScoreImprovement", "level": 0, "title": "", "hint": "", "flags": {},
                 "configuration": {"points": body, "fixed": fixed, "cap": cap, "locked": locked, "recommendation": None},
                 "value": {}}


def spell_cfg(vlastnost=None, maximum="", obnova=""):
    vl = vlastnost if isinstance(vlastnost, list) else ([vlastnost] if vlastnost else [])
    return {"ability": vl, "uses": {"max": str(maximum or ""), "per": obnova or "", "requireSlot": False},
            "method": "innate", "prepared": 0}


def adv_grant(seed, polozky, titulek="", uroven=0, spell=None):
    aid = pomocne(seed)
    return aid, {"_id": aid, "type": "ItemGrant", "level": uroven, "title": titulek, "hint": "", "flags": {},
                 "configuration": {"items": [{"uuid": u, "optional": False} for u in polozky], "optional": False,
                                   "spell": spell or spell_cfg()},
                 "value": {}}


def adv_choice(seed, titulek, pocet, pool=(), typ="feat", spell=None, seznam=None, uroven_kouzla=""):
    aid = pomocne(seed)
    return aid, {"_id": aid, "type": "ItemChoice", "level": 0, "title": titulek, "hint": "", "flags": {},
                 "configuration": {"choices": {"0": {"count": pocet, "replacement": False}}, "allowDrops": bool(seznam),
                                   "type": typ, "pool": [{"uuid": u} for u in pool], "spell": spell or spell_cfg(),
                                   "restriction": {"type": "race" if typ == "feat" else "", "subtype": "",
                                                   "level": str(uroven_kouzla), "list": [f"class:{seznam}"] if seznam else []}},
                 "value": {"added": {}, "replaced": {}}}


# ---------------------------------------------------------------- aktivity a efekty schopností

def aktivita(seed, a, ma_pouziti, idx):
    aid = pomocne(seed)
    typ = a.get("typ", "utility")
    akt = {"_id": aid, "type": typ, "name": a.get("nazev", "Použít"), "img": "", "sort": idx * 100000, "flags": {},
           "activation": {"type": a.get("sesilani", "action"), "value": None, "condition": a.get("podminka", ""), "override": False},
           "consumption": {"targets": [{"type": "itemUses", "value": "1", "target": "", "scaling": {}}] if ma_pouziti else [],
                           "scaling": {"allowed": False, "max": ""}, "spellSlot": False},
           "description": {"chatFlavor": ""},
           "duration": {"concentration": False, "value": "", "units": "inst", "special": "", "override": False},
           "effects": [],
           "range": {"units": "self" if (a.get("cil") or {}).get("typ") == "self" else "", "special": "", "override": False},
           "target": {"template": {"count": "", "contiguous": False, "type": "", "size": "", "width": "", "height": "", "units": ""},
                      "affects": {"count": str((a.get("cil") or {}).get("pocet", "")), "type": (a.get("cil") or {}).get("typ", ""),
                                  "choice": False, "special": ""},
                      "prompt": True, "override": False},
           "uses": {"spent": 0, "recovery": [], "max": ""},
           "visibility": {"level": {"min": None, "max": None}}}
    if typ == "heal":
        l = a["leceni"]
        akt["healing"] = {"number": None, "denomination": None, "bonus": "", "types": [l.get("typ", "healing")],
                          "custom": {"enabled": True, "formula": str(l.get("bonus", ""))}, "scaling": {"mode": "", "number": None, "formula": ""}}
    return aid, akt


def efekt(seed, e, nazev_polozky, ikona):
    eid = pomocne(seed)
    return {"_id": eid, "name": e.get("nazev", nazev_polozky), "img": ikona, "type": "base", "transfer": True,
            "disabled": False, "statuses": [], "tint": "#ffffff", "showIcon": 1, "flags": {},
            "duration": {"value": None, "units": "seconds", "expiry": None, "expired": False},
            "system": {"changes": [{"key": c["klic"], "value": c["hodnota"], "type": c.get("typ", "add"),
                                    "phase": "initial", "priority": None} for c in e.get("zmeny", [])]},
            "description": f"<p>{html.escape(nazev_polozky)} (pasivní rasová schopnost).</p>"}


def popis_schopnosti(text, kotva=None):
    odkaz = f"{SRD_TVORBA}#{kotva}" if kotva else SRD_TVORBA
    return (f"<p>{html.escape(text)}</p><p><em>Pravidla: <a href=\"{odkaz}\" target=\"_blank\">SRD Jeskyní a draků – "
            f"Tvorba postavy</a>.</em></p>")


def schopnost(klic, s, slozka, pozadavky=""):
    iid = foundry_id(f"rasa-schopnost-{klic}")
    ikona = s.get("ikona", IKONA_SCHOPNOSTI)
    pouziti = s.get("pouziti")
    aktivity = {}
    for i, a in enumerate(s.get("aktivity", [])):
        aid, akt = aktivita(f"{klic}-akt-{i}", a, bool(pouziti), i)
        aktivity[aid] = akt
    postup = {}
    for i, p in enumerate(s.get("postup", [])):
        if p["typ"] == "trait":
            aid, adv = adv_trait(f"{klic}-postup-{i}", s["nazev"], p.get("zdatnosti", []), p.get("volby", []), p.get("rezim", "default"))
        elif p["typ"] == "asi":
            aid, adv = adv_asi(f"{klic}-postup-{i}", p.get("fixni"), p.get("body", 0), cap=1)
        else:
            continue
        postup[aid] = adv
    efekty = [efekt(f"{klic}-efekt-{i}", e, s["nazev"], ikona) for i, e in enumerate(s.get("efekty", []))]
    for e in efekty:
        e["origin"] = uuid(PACK, iid)
    return {
        "_id": iid, "name": s["nazev"], "type": "feat", "img": ikona, "folder": slozka, "sort": 0,
        "ownership": {"default": 0}, "effects": efekty,
        "system": {
            "description": {"value": popis_schopnosti(s["popis"], s.get("kotva")), "chat": ""},
            "source": {"custom": "", "book": "Jeskyně a draci", "page": "", "license": "Licence JaD pro třetí strany", "rules": "2014"},
            "uses": {"max": str(pouziti["max"]) if pouziti else "", "spent": 0,
                     "recovery": [{"period": OBNOVA[pouziti["obnova"]], "type": "recoverAll"}] if pouziti else []},
            "type": {"value": "race", "subtype": ""}, "requirements": pozadavky, "properties": ["trait"],
            "activities": aktivity, "enchant": {}, "prerequisites": {"level": None}, "identifier": slug(klic),
            "advancement": postup},
        "flags": {MODUL: {"rasa": True}}, "_stats": stats(), "_key": f"!items!{iid}"}


def dech(klic, d, slozka):
    nazev, typ, tvar, zachrana = d
    iid = foundry_id(f"rasa-dech-{klic}")
    aid = pomocne(f"dech-{klic}-akt")
    sablona = {"count": "", "contiguous": False, "type": "cone", "size": "3", "width": "", "height": "", "units": "sah"} \
        if tvar == "cone" else {"count": "", "contiguous": False, "type": "line", "size": "6", "width": "1", "height": "", "units": "sah"}
    akt = {"_id": aid, "type": "save", "name": "Dračí dech", "img": "", "sort": 0, "flags": {},
           "activation": {"type": "action", "value": 1, "condition": "", "override": False},
           "consumption": {"targets": [{"type": "itemUses", "value": "1", "target": "", "scaling": {}}],
                           "scaling": {"allowed": False, "max": ""}, "spellSlot": False},
           "description": {"chatFlavor": ""},
           "duration": {"concentration": False, "value": "", "units": "inst", "special": "", "override": False},
           "effects": [], "range": {"units": "self", "special": "", "override": False},
           "target": {"template": sablona, "affects": {"count": "", "type": "creature", "choice": False, "special": ""},
                      "prompt": True, "override": False},
           "damage": {"onSave": "half", "parts": [{"number": None, "denomination": None, "bonus": "", "types": [typ],
                                                   "custom": {"enabled": True, "formula": "@scale.drakorozeny.dech"},
                                                   "scaling": {"mode": "", "number": None, "formula": ""}}]},
           "save": {"ability": [zachrana], "dc": {"calculation": "con", "formula": ""}},
           "uses": {"spent": 0, "recovery": [], "max": ""}, "visibility": {"level": {"min": None, "max": None}}}
    ikona = IKONY_DECHU.get(typ, IKONA_SCHOPNOSTI)
    ef = efekt(f"dech-{klic}-odolnost", {"nazev": f"Odolání zásahům ({nazev})",
                                          "zmeny": [{"klic": "system.traits.dr.value", "hodnota": typ, "typ": "add"}]}, nazev, ikona)
    ef["origin"] = uuid(PACK, iid)
    tvar_txt = "kužel 3 sáhy" if tvar == "cone" else "dráha 1 × 6 sáhů"
    popis = (f"Dračí původ: {nazev}. Jednou mezi Odpočinky vydechneš akcí ničivou energii ({tvar_txt}); tvorové v oblasti "
             f"si hází Záchranný hod (SO 8 + Zdatnostní bonus + Oprava odolnosti), při neúspěchu utrpí zásah 2k6 "
             f"(3k6 na 6., 4k6 na 11. a 5k6 na 16. Úrovni), při úspěchu polovinu. Máš Odolnost vůči tomuto typu zásahu.")
    return {
        "_id": iid, "name": f"Dračí původ – {nazev}", "type": "feat", "img": ikona, "folder": slozka, "sort": 0,
        "ownership": {"default": 0}, "effects": [ef],
        "system": {"description": {"value": popis_schopnosti(popis, "drakorozeny"), "chat": ""},
                   "source": {"custom": "", "book": "Jeskyně a draci", "page": "", "license": "Licence JaD pro třetí strany", "rules": "2014"},
                   "uses": {"max": "1", "spent": 0, "recovery": [{"period": "sr", "type": "recoverAll"}]},
                   "type": {"value": "race", "subtype": ""}, "requirements": "Drakorozený", "properties": ["trait"],
                   "activities": {aid: akt}, "enchant": {}, "prerequisites": {"level": None},
                   "identifier": f"dech-{klic}", "advancement": {}},
        "flags": {MODUL: {"rasa": True}}, "_stats": stats(), "_key": f"!items!{iid}"}


def rasa(klic, r, schopnosti_id, puvody_id, slozka):
    iid = foundry_id(f"rasa-{klic}")
    adv = {}

    def pridej(par):
        adv[par[0]] = par[1]

    a = r.get("asi", {})
    pridej(adv_asi(f"{klic}-asi", a.get("fixni"), a.get("body", 0), a.get("omezeni"), cap=1 if a.get("body") and not a.get("fixni") else 2))
    sid = pomocne(f"{klic}-velikost")
    adv[sid] = {"_id": sid, "type": "Size", "level": 1, "title": "", "hint": "", "flags": {},
                "configuration": {"sizes": [r["velikost"]]}, "value": {"size": ""}}
    pridej(adv_trait(f"{klic}-jazyky", "Jazyky", r.get("jazyky", []), [v for v in r.get("volby_zdatnosti", []) if v["z"][0].startswith("languages")]))
    ostatni_volby = [v for v in r.get("volby_zdatnosti", []) if not v["z"][0].startswith("languages")]
    if r.get("zdatnosti") or ostatni_volby:
        pridej(adv_trait(f"{klic}-zdatnosti", "Zdatnosti a odolnosti", r.get("zdatnosti", []), ostatni_volby))
    if r.get("schopnosti"):
        pridej(adv_grant(f"{klic}-schopnosti", [uuid(PACK, schopnosti_id[s]) for s in r["schopnosti"]], "Rasové schopnosti"))
    for i, v in enumerate(r.get("volby", [])):
        pridej(adv_choice(f"{klic}-volba-{i}", v["nazev"], v["pocet"], [uuid(PACK, schopnosti_id[s]) for s in v["z"]]))
    for i, k in enumerate(r.get("kouzla", [])):
        pridej(adv_grant(f"{klic}-kouzlo-{i}", [kouzlo_uuid(k["kouzlo"])], "Vrozená magie", k.get("uroven", 0),
                         spell_cfg(k.get("vlastnost"), k.get("max", ""), k.get("obnova", ""))))
    vk = r.get("volba_kouzla")
    if vk:
        pridej(adv_choice(f"{klic}-volba-kouzla", vk["nazev"], 1, [kouzlo_uuid(x) for x in vk.get("z", [])], typ="spell",
                          spell=spell_cfg(vk.get("vlastnost")), seznam=vk.get("seznam"), uroven_kouzla="0"))
    if r.get("drakorozeny"):
        scid = pomocne(f"{klic}-skala")
        adv[scid] = {"_id": scid, "type": "ScaleValue", "level": 0, "title": "Dračí dech", "hint": "", "flags": {},
                     "configuration": {"identifier": "dech", "type": "dice", "distance": {"units": ""},
                                       "scale": {str(u): {"number": n, "faces": 6, "modifiers": []} for u, n in ((0, 2), (6, 3), (11, 4), (16, 5))}},
                     "value": {}}
        pridej(adv_choice(f"{klic}-puvod", "Dračí původ", 1, [uuid(PACK, x) for x in puvody_id.values()]))

    nazvy = [x for x in r.get("schopnosti", [])]
    popis = f"<p>{html.escape(r['popis'])}</p>"
    popis += "<ul>"
    popis += f"<li><strong>Rychlost:</strong> {r['rychlost']['walk']} sáhů" + (
        f", šplhání {r['rychlost']['climb']} sáhů" if r["rychlost"].get("climb") else "") + "</li>"
    if r.get("videni"):
        popis += f"<li><strong>Vidění ve tmě:</strong> {r['videni']} sáhů</li>"
    popis += "</ul>"
    popis += (f"<p><em>Více o rase: <a href=\"{SRD_RASY}#{r['kotva']}\" target=\"_blank\">SRD Jeskyní a draků – Rasy</a>; "
              f"pravidla: <a href=\"{SRD_TVORBA}#schopnosti-ras\" target=\"_blank\">Tvorba postavy</a>.</em></p>")
    return {
        "_id": iid, "name": r["nazev"], "type": "race", "img": r.get("ikona", IKONA_RASY), "folder": slozka, "sort": 0,
        "ownership": {"default": 0}, "effects": [],
        "system": {
            "description": {"value": popis, "chat": ""},
            "source": {"custom": "", "book": "Jeskyně a draci", "page": "", "license": "Licence JaD pro třetí strany", "rules": "2014"},
            "identifier": slug(klic), "advancement": adv,
            "movement": {"walk": r["rychlost"]["walk"], "climb": r["rychlost"].get("climb"), "burrow": None, "fly": None,
                         "swim": None, "units": "sah", "hover": False},
            "senses": {"darkvision": r.get("videni"), "blindsight": None, "tremorsense": None, "truesight": None,
                       "units": "sah", "special": ""},
            "type": {"value": "humanoid", "subtype": r.get("podtyp", r["nazev"]), "custom": ""}},
        "flags": {MODUL: {"rasa": klic}}, "_stats": stats(), "_key": f"!items!{iid}"}


def main():
    d = nacti_yaml("rasy.yml")
    slozky = {n: foundry_id(f"rasy-slozka-{n}") for n in ("rasy", "schopnosti", "puvody")}
    nazvy_slozek = {"rasy": "Rasy a rody", "schopnosti": "Rasové schopnosti", "puvody": "Dračí původy"}
    folders = [{"_id": fid, "name": nazvy_slozek[n], "type": "Item", "sorting": "a", "sort": (i + 1) * 100000,
                "folder": None, "color": None, "flags": {}, "_key": f"!folders!{fid}"} for i, (n, fid) in enumerate(slozky.items())]

    schopnosti_id = {k: foundry_id(f"rasa-schopnost-{k}") for k in d["schopnosti"]}
    puvody_id = {k: foundry_id(f"rasa-dech-{k}") for k in d["drakorozeny_puvody"]}

    # požadavky (která rasa schopnost používá)
    pozadavky = {}
    for r in d["rasy"].values():
        for s in r.get("schopnosti", []) + [x for v in r.get("volby", []) for x in v["z"]]:
            pozadavky.setdefault(s, []).append(r["nazev"].split(" – ")[0])

    polozky = []
    chyby = []
    for k, s in d["schopnosti"].items():
        polozky.append(schopnost(k, s, slozky["schopnosti"], ", ".join(sorted(set(pozadavky.get(k, []))))))
    for k, p in d["drakorozeny_puvody"].items():
        polozky.append(dech(k, p, slozky["puvody"]))
    for k, r in d["rasy"].items():
        for s in r.get("schopnosti", []) + [x for v in r.get("volby", []) for x in v["z"]]:
            if s not in schopnosti_id:
                chyby.append(f"{k}: neznámá schopnost {s}")
        if not chyby:
            polozky.append(rasa(k, r, schopnosti_id, puvody_id, slozky["rasy"]))

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
    os.makedirs(os.path.join(KOREN, "data/kompendium"), exist_ok=True)
    with open(os.path.join(KOREN, "data/kompendium/rasy.json"), "w", encoding="utf-8") as fh:
        json.dump({"folders": [bez(f) for f in folders],
                   "items": [{**bez(p), "effects": [bez(e) for e in p.get("effects", [])]} for p in polozky]}, fh, ensure_ascii=False)

    print(f"Ras: {sum(1 for p in polozky if p['type'] == 'race')}, schopností: {sum(1 for p in polozky if p['type'] == 'feat')}")
    for c in chyby:
        print("  !", c)
    return 1 if chyby else 0


if __name__ == "__main__":
    sys.exit(main())
