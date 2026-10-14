#!/usr/bin/env python3
"""
Generátor kompendia kouzel JaD pro Foundry VTT (dnd5e).

Vstupy:
  - zdroje systému dnd5e (git clone https://github.com/foundryvtt/dnd5e) – SRD 5.1 kouzla s automatizací
  - data/*.yml – české názvy, shrnutí, materiály, překlady aktivit a efektů
  - data/vlastni-kouzla/*.json – ručně vytvořená kouzla mimo SRD 5.1 (volitelné)

Výstupy:
  - packs/_source/kouzla/*.json            zdroj pro `fvtt package pack` (LevelDB)
  - packs/_source/seznamy-kouzel/*.json    seznamy kouzel povolání (JournalEntry + stránky typu "spells")
  - data/kompendium/*.json                 stejná data pro záložní import přímo ve Foundry

Použití:
  python3 tools/generuj.py --dnd5e ../dnd5e [--jednotky m|ft]
"""
import argparse, copy, glob, hashlib, html, json, os, re, shutil, sys, unicodedata
import yaml

MODUL = "jeskyne-a-draci"
KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRD_JAD = "https://dnd5esrd.d20.cz/grimoar/grimoar-jmen.html"
CORE_VERZE, SYS_VERZE = "14.367", "6.0.6"

SKOLY = {"abj": "Vymítání", "con": "Vyvolávání", "div": "Věštění", "enc": "Očarování",
         "evo": "Zaklínání", "ill": "Iluze", "nec": "Nekromancie", "trs": "Transmutace"}
VLASTNOSTI = {"str": "Sílu", "dex": "Obratnost", "con": "Odolnost", "int": "Inteligenci",
              "wis": "Moudrost", "cha": "Charisma"}
ZRANENI = {"acid": "kyselinové", "bludgeoning": "drtivé", "cold": "chladné", "fire": "ohnivé",
           "force": "silové", "lightning": "bleskové", "necrotic": "nekrotické", "piercing": "bodné",
           "poison": "jedové", "psychic": "psychické", "radiant": "zářivé", "slashing": "sečné",
           "thunder": "hromové", "healing": "léčení", "temphp": "dočasné životy", "midi-none": "bez zranění"}
POVOLANI = {"bard": "Bard", "cleric": "Klerik", "druid": "Druid", "paladin": "Paladin",
            "ranger": "Hraničář", "sorcerer": "Čaroděj", "warlock": "Černokněžník", "wizard": "Kouzelník"}
SLOZKY = ["Triky"] + [f"{i}. stupeň" for i in range(1, 10)]
ATRIBUCE = ('<p><img src="modules/jeskyne-a-draci/assets/logo-jad-komunitni.jpg" alt="JaD – komunitní tvorba" width="140"></p>'
            '<p class="jad-atribuce">Jeskyně a draci pro Foundry VTT je nezávislá tvorba autora vintag51 a není spojena s autory ani '
            'vydavatelem hry Jeskyně a Draci (dostupné na imago.cz). Publikováno pod Licencí JaD pro třetí strany.</p>')
RADY = {"1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5, "6th": 6, "7th": 7, "8th": 8, "9th": 9}


def nacti_yaml(nazev):
    with open(os.path.join(KOREN, "data", nazev), encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def foundry_id(seed):
    """Deterministické 16znakové ID (stejné při každém buildu → stabilní UUID)."""
    abc = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    h = int(hashlib.sha256(f"{MODUL}:{seed}".encode()).hexdigest(), 16)
    out = ""
    for _ in range(16):
        h, r = divmod(h, len(abc))
        out += abc[r]
    return out


def slug(text):
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


# ---------------------------------------------------------------- jednotky

def prevod_delky(hodnota, jednotky, cil):
    """JaD převod: 5 stop = 1,5 m (×0,3); 1 míle = 1,5 km."""
    if cil != "m" or hodnota in (None, ""):
        return hodnota, jednotky
    try:
        v = float(hodnota)
    except (TypeError, ValueError):
        return hodnota, jednotky
    if jednotky == "ft":
        v, jednotky = round(v * 0.3, 2), "m"
    elif jednotky == "mi":
        v, jednotky = round(v * 1.5, 2), "km"
    else:
        return hodnota, jednotky
    v = int(v) if v == int(v) else v
    return (str(v) if isinstance(hodnota, str) else v), jednotky


def preved_sablonu(t, cil):
    if not isinstance(t, dict):
        return
    jed = t.get("units") or "ft"
    zmena = False
    for k in ("size", "width", "height"):
        if t.get(k) not in (None, ""):
            t[k], nove = prevod_delky(t[k], jed, cil)
            zmena = zmena or nove != jed
    if zmena or jed == "ft":
        t["units"] = "m" if (cil == "m" and jed == "ft") else ("km" if cil == "m" and jed == "mi" else jed)


def preved_dosah(r, cil):
    if isinstance(r, dict) and r.get("units") in ("ft", "mi"):
        r["value"], r["units"] = prevod_delky(r.get("value"), r["units"], cil)


POHYB = re.compile(r"^system\.attributes\.(movement|senses)\.(walk|fly|swim|climb|burrow|darkvision|blindsight|tremorsense|truesight|range)")


def preved_efekty(efekty, cil):
    if cil != "m":
        return
    for e in efekty:
        zmeny = (e.get("system") or {}).get("changes") or e.get("changes") or []
        for c in zmeny:
            if POHYB.match(c.get("key", "")):
                try:
                    v = float(c["value"])
                    v = round(v * 0.3, 2)
                    c["value"] = str(int(v) if v == int(v) else v)
                except (TypeError, ValueError, KeyError):
                    pass


# ---------------------------------------------------------------- texty

def vzorec(cast):
    if (cast.get("custom") or {}).get("enabled"):
        f = cast["custom"].get("formula") or ""
    else:
        n, d, b = cast.get("number"), cast.get("denomination"), cast.get("bonus") or ""
        f = f"{n}k{d}" if n and d else ""
        if b:
            f = f"{f} + {b}" if f else b
    f = f.replace("@mod", "oprava sesílací vlastnosti").replace("@item.level", "stupeň")
    f = re.sub(r"(\d+)d(\d+)", r"\1k\2", f)
    return f.strip()


def popis_casti(cast):
    druhy = [ZRANENI.get(t, t) for t in cast.get("types") or []]
    f = vzorec(cast)
    if not f:
        return ""
    if druhy == ["léčení"]:
        return f"{f} životů"
    if druhy == ["dočasné životy"]:
        return f"{f} dočasných životů"
    return f"{f} {' nebo '.join(druhy)} zranění" if druhy else f


def skalovani(cast, stupen):
    s = cast.get("scaling") or {}
    if not s.get("mode"):
        return ""
    if stupen == 0:
        return "roste na 5., 11. a 17. úrovni postavy"
    if s.get("formula") and "@" in s["formula"]:
        return "roste se stupněm seslání"
    if s.get("formula"):
        k = re.sub(r"(\d+)d(\d+)", r"\1k\2", s["formula"])
    elif s.get("number") and cast.get("denomination"):
        k = f"{s['number']}k{cast['denomination']}"
    else:
        return ""
    po = "za každé dva stupně" if s.get("mode") == "half" else "za každý stupeň"
    return f"+{k} {po} nad {stupen}."


def mechanika(kouzlo):
    sy = kouzlo["system"]
    st = sy["level"]
    radky = []
    for a in sorted(sy["activities"].values(), key=lambda x: x.get("sort", 0)):
        typ = a["type"]
        nazev = a.get("name") or "Seslat"
        casti = []
        if typ == "attack":
            druh = (a.get("attack") or {}).get("type", {}).get("value")
            casti.append({"melee": "útok kouzlem na blízko", "ranged": "útok kouzlem na dálku"}.get(druh, "útok kouzlem"))
        if typ == "save":
            ab = (a.get("save") or {}).get("ability")
            ab = ab if isinstance(ab, list) else [ab] if ab else []
            if ab:
                casti.append("záchranný hod na " + " nebo ".join(VLASTNOSTI.get(x, x) for x in ab) + " proti SO kouzla")
        if typ == "check":
            casti.append("ověření vlastnosti")
        if typ == "summon":
            casti.append("přivolání tvora (karta tvora se vytvoří automaticky)")
        if typ == "enchant":
            casti.append("očaruje předmět")
        if typ == "transform":
            casti.append("proměna podoby")
        if typ == "teleport":
            casti.append("přesun")
        dmg = (a.get("damage") or {}).get("parts") or []
        for p in dmg:
            t = popis_casti(p)
            if t:
                sk = skalovani(p, st)
                casti.append(("zásah: " if typ == "attack" else "") + t + (f" ({sk.rstrip('.')})" if sk else ""))
        if typ == "save" and dmg:
            casti.append({"half": "při úspěchu polovina", "none": "při úspěchu nic", "full": "zranění i při úspěchu"}
                         .get((a.get("damage") or {}).get("onSave"), ""))
        if typ == "heal" and a.get("healing"):
            t = popis_casti(a["healing"])
            sk = skalovani(a["healing"], st)
            if t:
                casti.append("obnoví " + t + (f" ({sk.rstrip('.')})" if sk else ""))
        if a.get("effects"):
            jmena = [e["name"] for e in kouzlo.get("effects", []) if e["_id"] in {x["_id"] for x in a["effects"]}]
            jmena = list(dict.fromkeys(re.sub(r": \d\. stupeň$", " (podle stupně)", j) for j in jmena))
            if jmena:
                casti.append("efekt: " + ", ".join(jmena[:4]) + ("…" if len(jmena) > 4 else ""))
        casti = [c for c in casti if c]
        if casti:
            radky.append(f"<li><strong>{html.escape(nazev)}:</strong> {html.escape('; '.join(casti))}.</li>")
    return radky


def popis_kouzla(k, uvod, odkaz, overeno):
    cz = k["name"]
    popis = f"<p>{html.escape(uvod)}</p>" if uvod else ""
    mech = mechanika(k)
    if mech:
        popis += "<h3>Automatizace</h3><ul>" + "".join(mech) + "</ul>"
    popis += (f'<p><strong>Plné znění:</strong> <a href="{odkaz}" target="_blank">SRD Jeskyní a draků – {html.escape(cz)}</a>'
              f" (případně Kapitola 10 – Magie v knize Jeskyně a draci).</p>")
    if not overeno:
        popis += "<p><em>Pracovní název – čeká na ověření proti knize JaD.</em></p>"
    return popis


def nahrad_retezce(o, slovnik):
    """Nahradí řetězce, které přesně odpovídají klíči slovníku (rekurzivně)."""
    if isinstance(o, dict):
        return {k: nahrad_retezce(v, slovnik) for k, v in o.items()}
    if isinstance(o, list):
        return [nahrad_retezce(v, slovnik) for v in o]
    if isinstance(o, str) and o in slovnik:
        return slovnik[o]
    return o


def prelozit_nazev(nazev, slovnik, cz_kouzla, en_kouzla):
    if nazev in slovnik:
        return slovnik[nazev]
    m = re.match(r"^(.*?):?\s*(\d)(st|nd|rd|th) Level$", nazev)
    if m:
        zaklad = m.group(1).strip()
        return f"{cz_kouzla if zaklad == en_kouzla else slovnik.get(zaklad, cz_kouzla)}: {m.group(2)}. stupeň"
    if nazev == en_kouzla:
        return cz_kouzla
    return None


# ---------------------------------------------------------------- hlavní běh

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dnd5e", required=True, help="cesta ke zdrojům systému dnd5e")
    ap.add_argument("--jednotky", choices=["m", "ft"], default="m")
    args = ap.parse_args()

    nazvy = nacti_yaml("nazvy-kouzel.yml")
    shrnuti = nacti_yaml("shrnuti.yml")
    materialy = nacti_yaml("materialy.yml")
    pre = nacti_yaml("preklady-aktivit.yml")
    akt_sl, ef_sl = pre.get("aktivity", {}), pre.get("efekty", {})
    podminky = nacti_yaml("podminky.yml")
    overtime = nacti_yaml("midi-overtime.yml")

    srd = {}
    for f in glob.glob(os.path.join(args.dnd5e, "packs/_source/spells/**/*.yml"), recursive=True):
        with open(f, encoding="utf-8") as fh:
            d = yaml.safe_load(fh)
        if d and d.get("type") == "spell":
            srd[d["_id"]] = d

    nove_id = {sid: foundry_id(s["system"]["identifier"]) for sid, s in srd.items()}
    folder_id = {i: foundry_id(f"slozka-{i}") for i in range(10)}

    chyby, nepr_akt, nepr_ef = [], set(), set()
    kouzla = []
    for sid, puv in srd.items():
        ident = puv["system"]["identifier"]
        if ident not in nazvy:
            chyby.append(f"chybí český název: {ident}")
            continue
        k = copy.deepcopy(puv)
        k.pop("_key", None)
        cz = nazvy[ident]["cz"]
        en = puv["name"]
        nid = nove_id[sid]
        sy = k["system"]

        # přepsání odkazů na jiná SRD kouzla na kouzla tohoto modulu
        txt = json.dumps(k, ensure_ascii=False)
        for sid2, nid2 in nove_id.items():
            txt = txt.replace(f"Compendium.dnd5e.spells.Item.{sid2}", f"Compendium.{MODUL}.kouzla.Item.{nid2}")
        txt = txt.replace(f"Item.{sid}", f"Item.{nid}")
        k = json.loads(txt)
        sy = k["system"]

        k["_id"] = nid
        k["name"] = cz
        k["folder"] = folder_id[sy["level"]]
        k["sort"] = 0
        k["ownership"] = {"default": 0}

        # aktivity
        efekt_idy = {e["_id"] for e in k.get("effects", [])}
        typy = {"utility": "Užitek", "save": "Záchrana", "attack": "Útok", "damage": "Zranění", "heal": "Léčení",
                "summon": "Přivolání", "check": "Ověření", "enchant": "Očarování", "transform": "Proměna", "teleport": "Přesun"}
        for a in sy["activities"].values():
            a["effects"] = [e for e in a.get("effects", []) if e.get("_id") in efekt_idy]
            puvodni = a.get("name") or ""
            if not puvodni:
                a["name"] = "Seslat" if len(sy["activities"]) == 1 else typy.get(a["type"], "Seslat")
                puvodni = a["name"]
                akt_sl = {**akt_sl, puvodni: puvodni}
            n = prelozit_nazev(puvodni, akt_sl, cz, en)
            if n is None:
                nepr_akt.add(puvodni)
                n = puvodni
            a["name"] = n
            if isinstance(a.get("description"), dict):
                a["description"]["chatFlavor"] = ""
                if a["description"].get("value"):
                    a["description"]["value"] = ""
            preved_dosah(a.get("range"), args.jednotky)
            preved_sablonu((a.get("target") or {}).get("template"), args.jednotky)

        # efekty
        for e in k.get("effects", []):
            n = prelozit_nazev(e["name"], ef_sl, cz, en)
            if n is None:
                nepr_ef.add(e["name"])
                n = f"{cz} – {e['name']}"
            e["name"] = n
            e["description"] = f"<p>Účinek kouzla <em>{html.escape(cz)}</em>. Podrobnosti v popisu kouzla.</p>"
            e.setdefault("flags", {})
            for c in (e.get("system") or {}).get("changes", []):
                if c.get("key") == "system.description.value" and "<p>" in str(c.get("value")):
                    c["value"] = f"{{}} <p><strong>{html.escape(cz)}.</strong> {html.escape(shrnuti.get(ident, ''))}</p>"
        preved_efekty(k.get("effects", []), args.jednotky)

        # volitelná vrstva Midi-QOL (OverTime)
        if ident in overtime:
            spec = overtime[ident]
            for e in k.get("effects", []):
                if spec.get("status") and spec["status"] not in (e.get("statuses") or []):
                    continue
                m = re.search(r": (\d)\. stupeň$", e["name"])
                n = m.group(1) if m else str(max(sy["level"], 1))
                hodnota = spec["ot"].replace("{N}", n) + f",label={e['name']}"
                e.setdefault("system", {}).setdefault("changes", []).append(
                    {"key": "flags.midi-qol.OverTime", "value": hodnota, "type": "custom", "priority": 20})
                e["flags"].setdefault(MODUL, {})["midiOverTime"] = True

        k = nahrad_retezce(k, podminky)
        sy = k["system"]

        # délky
        preved_dosah(sy.get("range"), args.jednotky)
        preved_sablonu((sy.get("target") or {}).get("template"), args.jednotky)

        # materiály
        if sy["materials"].get("value"):
            if ident in materialy:
                sy["materials"]["value"] = materialy[ident]
            else:
                chyby.append(f"chybí překlad materiálu: {ident}")
                sy["materials"]["value"] = ""

        # popis
        odkaz = f"{SRD_JAD}#{slug(cz)}"
        uvod = shrnuti.get(ident)
        if not uvod:
            chyby.append(f"chybí shrnutí: {ident}")
        sy["description"] = {"value": popis_kouzla(k, uvod, odkaz, nazvy[ident].get("overeno")), "chat": ""}
        sy["source"] = {"custom": "", "book": "Jeskyně a draci", "page": "", "license": "CC-BY-4.0", "rules": "2014"}

        k["flags"] = {MODUL: {"srd": sid, "nazevEn": en, "overeno": bool(nazvy[ident].get("overeno")), "odkaz": odkaz}}
        k["_stats"] = {"coreVersion": CORE_VERZE, "systemId": "dnd5e", "systemVersion": SYS_VERZE,
                       "createdTime": None, "modifiedTime": None, "lastModifiedBy": None,
                       "compendiumSource": None, "duplicateSource": None, "exportSource": None}
        k["_key"] = f"!items!{nid}"
        kouzla.append(k)

    # vlastní kouzla mimo SRD (kompaktní zápis v data/vlastni-kouzla.yml)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import vlastni
    doplnky_seznamu = {}
    for ident, spec in (nacti_yaml("vlastni-kouzla.yml") or {}).items():
        if spec.get("vypnuto"):
            continue
        k = vlastni.sestav(ident, spec, foundry_id)
        odkaz = f"{SRD_JAD}#{slug(spec['cz'])}"
        k["system"]["description"]["value"] = popis_kouzla(k, spec.get("shrnuti"), odkaz, spec.get("overeno"))
        k["flags"]["jeskyne-a-draci"]["odkaz"] = odkaz
        k["folder"] = folder_id[k["system"]["level"]]
        k["_stats"] = {"coreVersion": CORE_VERZE, "systemId": "dnd5e", "systemVersion": SYS_VERZE,
                       "createdTime": None, "modifiedTime": None, "lastModifiedBy": None,
                       "compendiumSource": None, "duplicateSource": None, "exportSource": None}
        k["_key"] = f"!items!{k['_id']}"
        for pov in spec.get("povolani", []):
            doplnky_seznamu.setdefault(pov, []).append(ident)
        if any(x["name"] == k["name"] for x in kouzla):
            chyby.append(f"duplicitní název: {k['name']}")
        kouzla.append(k)

    # složky
    slozky = [{"_id": folder_id[i], "name": SLOZKY[i], "type": "Item", "sorting": "a", "sort": (i + 1) * 100000,
               "folder": None, "color": None, "flags": {}, "_key": f"!folders!{folder_id[i]}"} for i in range(10)]

    # seznamy kouzel povolání
    seznamy = []
    with open(os.path.join(args.dnd5e, "packs/_source/rules/chapter-10-spellcasting.yml"), encoding="utf-8") as fh:
        for doc in yaml.safe_load_all(fh):
            for p in (doc or {}).get("pages", []):
                if p.get("type") != "spells":
                    continue
                ident = p["system"]["identifier"]
                uuidy = []
                for u in p["system"].get("spells", []):
                    sid = u.split(".")[-1]
                    if sid in nove_id:
                        uuidy.append(f"Compendium.{MODUL}.kouzla.Item.{nove_id[sid]}")
                vlastni = doplnky_seznamu.get(ident, [])
                uuidy += [f"Compendium.{MODUL}.kouzla.Item.{foundry_id(x)}" for x in vlastni]
                seznamy.append({"ident": ident, "spells": sorted(set(uuidy))})
    jid = foundry_id("seznamy-kouzel")
    stranky = []
    for i, s in enumerate(sorted(seznamy, key=lambda x: POVOLANI.get(x["ident"], x["ident"]))):
        pid = foundry_id(f"seznam-{s['ident']}")
        stranky.append({"_id": pid, "name": f"Kouzla povolání {POVOLANI.get(s['ident'], s['ident'])}", "type": "spells",
                        "sort": (i + 1) * 100000, "title": {"show": True, "level": 1},
                        "system": {"type": "class", "identifier": s["ident"], "grouping": "level",
                                   "description": {"value": ATRIBUCE},
                                   "spells": s["spells"], "unlinkedSpells": []},
                        "ownership": {"default": -1}, "flags": {}, "_key": f"!journal.pages!{jid}.{pid}"})
    denik = {"_id": jid, "name": "Seznamy kouzel povolání (JaD)", "pages": stranky, "folder": None, "sort": 0,
             "ownership": {"default": 0}, "flags": {}, "_key": f"!journal!{jid}"}

    # zápis
    for cil in ("packs/_source/kouzla", "packs/_source/seznamy-kouzel", "data/kompendium"):
        shutil.rmtree(os.path.join(KOREN, cil), ignore_errors=True)
        os.makedirs(os.path.join(KOREN, cil))
    for k in kouzla:
        with open(os.path.join(KOREN, "packs/_source/kouzla", f"{slug(k['name'])}_{k['_id']}.json"), "w", encoding="utf-8") as fh:
            json.dump(k, fh, ensure_ascii=False, indent=2)
    for s in slozky:
        with open(os.path.join(KOREN, "packs/_source/kouzla", f"_slozka_{slug(s['name'])}.json"), "w", encoding="utf-8") as fh:
            json.dump(s, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(KOREN, "packs/_source/seznamy-kouzel/seznamy-kouzel.json"), "w", encoding="utf-8") as fh:
        json.dump(denik, fh, ensure_ascii=False, indent=2)
    bez_klicu = lambda o: {k: v for k, v in o.items() if k != "_key"}
    with open(os.path.join(KOREN, "data/kompendium/kouzla.json"), "w", encoding="utf-8") as fh:
        json.dump({"folders": [bez_klicu(s) for s in slozky], "items": [bez_klicu(k) for k in kouzla]}, fh, ensure_ascii=False)
    d2 = bez_klicu(denik)
    d2["pages"] = [bez_klicu(p) for p in d2["pages"]]
    with open(os.path.join(KOREN, "data/kompendium/seznamy-kouzel.json"), "w", encoding="utf-8") as fh:
        json.dump({"journal": [d2]}, fh, ensure_ascii=False)

    with open(os.path.join(KOREN, "data/kompendium/registr.json"), "w", encoding="utf-8") as fh:
        json.dump({"seznamyKouzel": [f"Compendium.{MODUL}.seznamy-kouzel.JournalEntry.{jid}.JournalEntryPage.{p['_id']}"
                                     for p in stranky]}, fh, ensure_ascii=False, indent=1)

    print(f"Kouzel: {len(kouzla)}, seznamů: {len(stranky)}, jednotky: {args.jednotky}")
    print("Ověřených názvů:", sum(1 for k in kouzla if k['flags'].get(MODUL, {}).get('overeno')))
    for c in chyby:
        print("  !", c)
    if nepr_akt:
        print("  ! nepřeložené aktivity:", sorted(nepr_akt))
    if nepr_ef:
        print("  ! nepřeložené efekty:", sorted(nepr_ef))
    return 1 if chyby else 0


if __name__ == "__main__":
    sys.exit(main())
