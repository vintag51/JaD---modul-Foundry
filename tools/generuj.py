#!/usr/bin/env python3
"""
Generátor kompendia kouzel Jeskyní a draků pro Foundry VTT (dnd5e).

Vstupy:
  - zdroje systému dnd5e (git clone https://github.com/foundryvtt/dnd5e) – SRD 5.1 kouzla s automatizací
  - data/jad-kouzla.yml        seznam kouzel JaD (název, stupeň, škola, povolání, párování na SRD)
  - data/shrnuti.yml           vlastní krátká shrnutí kouzel SRD
  - data/materialy.yml         vlastní překlad surovinových složek
  - data/preklady-aktivit.yml  názvy aktivit a efektů
  - data/podminky.yml          podmínky aktivace a další texty
  - data/midi-overtime.yml     volitelná vrstva Midi-QOL
  - data/vlastni-kouzla.yml    kouzla mimo SRD 5.1 (původní kouzla JaD)

Výstupy:
  - packs/_source/kouzla/*.json, packs/_source/seznamy-kouzel/*.json   zdroje pro Foundry CLI (LevelDB)
  - data/kompendium/*.json                                             záložní import přímo ve Foundry

Použití:
  python3 tools/generuj.py --dnd5e ../dnd5e [--jednotky sah|ft]
"""
import argparse, copy, glob, hashlib, html, json, os, re, shutil, sys, unicodedata
import yaml

MODUL = "jeskyne-a-draci"
KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRD_JAD = "https://dnd5esrd.d20.cz/jeskyne-a-draci/10-magie.html"
CORE_VERZE, SYS_VERZE = "14.367", "6.0.6"

VLASTNOSTI = {"str": "Sílu", "dex": "Obratnost", "con": "Odolnost", "int": "Inteligenci",
              "wis": "Moudrost", "cha": "Charisma"}
ZASAHY = {"acid": "Kyselinový", "bludgeoning": "Drtivý", "cold": "Chladný", "fire": "Ohnivý", "force": "Silový",
          "lightning": "Bleskový", "necrotic": "Nekrotický", "piercing": "Bodný", "poison": "Jedový",
          "psychic": "Psychický", "radiant": "Zářivý", "slashing": "Sečný", "thunder": "Hromový"}
POVOLANI = {"bard": "Bard", "cleric": "Klerik", "druid": "Druid", "paladin": "Paladin",
            "ranger": "Hraničář", "sorcerer": "Čaroděj", "warlock": "Černokněžník", "wizard": "Kouzelník"}
SLOZKY = ["Triky"] + [f"{i}. Stupeň" for i in range(1, 10)]
ATRIBUCE = ('<p><img src="modules/jeskyne-a-draci/assets/logo-jad-komunitni.jpg" alt="JaD – komunitní tvorba" width="140"></p>'
            '<p class="jad-atribuce">Jeskyně a draci pro Foundry VTT je nezávislá tvorba autora vintag51 a není spojena s autory ani '
            'vydavatelem hry Jeskyně a Draci (dostupné na imago.cz). Publikováno pod Licencí JaD pro třetí strany.</p>')
TYPY_AKTIVIT = {"utility": "Užitek", "save": "Záchrana", "attack": "Útok", "damage": "Zásah", "heal": "Léčení",
                "summon": "Přivolání", "check": "Ověření", "enchant": "Očarování", "transform": "Proměna",
                "teleport": "Přesun"}


def nacti_yaml(nazev):
    cesta = os.path.join(KOREN, "data", nazev)
    if not os.path.exists(cesta):
        return {}
    with open(cesta, encoding="utf-8") as f:
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


def stats():
    return {"coreVersion": CORE_VERZE, "systemId": "dnd5e", "systemVersion": SYS_VERZE, "createdTime": None,
            "modifiedTime": None, "lastModifiedBy": None, "compendiumSource": None, "duplicateSource": None,
            "exportSource": None}


# ---------------------------------------------------------------- jednotky (1 sáh = 5 stop = 1 pole)

def prevod(hodnota, jednotky, cil):
    if cil != "sah" or jednotky != "ft" or hodnota in (None, ""):
        return hodnota, jednotky
    try:
        v = float(hodnota) / 5
    except (TypeError, ValueError):
        return hodnota, jednotky
    v = int(v) if v == int(v) else round(v, 2)
    return (str(v) if isinstance(hodnota, str) else v), "sah"


def preved_dosah(r, cil):
    if isinstance(r, dict) and r.get("units") == "ft":
        r["value"], r["units"] = prevod(r.get("value"), "ft", cil)


def preved_sablonu(t, cil):
    if not isinstance(t, dict):
        return
    if (t.get("units") or "ft") == "ft" and cil == "sah":
        for k in ("size", "width", "height"):
            if t.get(k) not in (None, ""):
                t[k], _ = prevod(t[k], "ft", cil)
        t["units"] = "sah"


# ---------------------------------------------------------------- texty mechaniky (terminologie JaD)

def vzorec(cast):
    if (cast.get("custom") or {}).get("enabled"):
        f = cast["custom"].get("formula") or ""
    else:
        n, d, b = cast.get("number"), cast.get("denomination"), cast.get("bonus") or ""
        f = f"{n}k{d}" if n and d else ""
        if b:
            f = f"{f} + {b}" if f else b
    f = f.replace("@mod", "Oprava sesílací vlastnosti").replace("@prof", "Zdatnostní bonus")
    f = f.replace("@item.level", "Stupeň Pozice")
    return re.sub(r"(\d+)d(\d+)", r"\1k\2", f).strip()


def popis_casti(cast):
    typy = cast.get("types") or []
    f = vzorec(cast)
    if not f:
        return ""
    if typy == ["healing"]:
        return f"{f} Bodů výdrže"
    if typy == ["temphp"]:
        return f"{f} Dočasných bodů výdrže"
    druhy = [ZASAHY[t] for t in typy if t in ZASAHY]
    if not druhy:
        return f"zásah za {f} Bodů výdrže"
    druh = druhy[0] if len(druhy) == 1 else "/".join(druhy) + " (dle volby)"
    return f"{druh} zásah za {f} Bodů výdrže"


def skalovani(cast, stupen):
    s = cast.get("scaling") or {}
    if not s.get("mode"):
        return ""
    if stupen == 0:
        return "roste na 5., 11. a 17. Úrovni"
    if s.get("formula") and "@" in s["formula"]:
        return "roste se Stupněm Pozice"
    if s.get("formula"):
        k = re.sub(r"(\d+)d(\d+)", r"\1k\2", s["formula"])
    elif s.get("number") and cast.get("denomination"):
        k = f"{s['number']}k{cast['denomination']}"
    else:
        return ""
    po = "každé dva Stupně" if s.get("mode") == "half" else "každý Stupeň"
    return f"+{k} za {po} nad {stupen}"


def mechanika(kouzlo):
    sy = kouzlo["system"]
    st = sy["level"]
    efekty = {e["_id"]: e["name"] for e in kouzlo.get("effects", [])}
    radky = []
    for a in sorted(sy["activities"].values(), key=lambda x: x.get("sort", 0)):
        typ = a["type"]
        casti = []
        if typ == "attack":
            druh = (a.get("attack") or {}).get("type", {}).get("value")
            casti.append({"melee": "Útok na blízko kouzlem", "ranged": "Útok na dálku kouzlem"}.get(druh, "Útok kouzlem"))
        if typ == "save":
            ab = (a.get("save") or {}).get("ability")
            ab = ab if isinstance(ab, list) else [ab] if ab else []
            if ab:
                casti.append("Záchranný hod na " + " nebo ".join(VLASTNOSTI.get(x, x) for x in ab) + " proti SO kouzla")
        casti += {"check": ["Ověření vlastnosti"], "summon": ["přivolání tvora (karta tvora se vytvoří automaticky)"],
                  "enchant": ["očarování předmětu"], "transform": ["proměna podoby"], "teleport": ["přesun"]}.get(typ, [])
        dmg = (a.get("damage") or {}).get("parts") or []
        for p in dmg:
            t = popis_casti(p)
            if t:
                sk = skalovani(p, st)
                casti.append(("při Zásahu " if typ == "attack" else "") + t + (f" ({sk})" if sk else ""))
        if typ == "save" and dmg:
            casti.append({"half": "při úspěchu poloviční Zásah", "none": "při úspěchu bez účinku",
                          "full": "plný Zásah i při úspěchu"}.get((a.get("damage") or {}).get("onSave"), ""))
        if typ == "heal" and a.get("healing"):
            t = popis_casti(a["healing"])
            sk = skalovani(a["healing"], st)
            if t:
                casti.append("obnoví " + t + (f" ({sk})" if sk else ""))
        jmena = [efekty[e["_id"]] for e in a.get("effects", []) if e.get("_id") in efekty]
        jmena = list(dict.fromkeys(re.sub(r": \d\. Stupeň$", " (podle Stupně)", j) for j in jmena))
        if jmena:
            casti.append("efekt: " + ", ".join(jmena[:4]) + ("…" if len(jmena) > 4 else ""))
        casti = [c for c in casti if c]
        if casti:
            radky.append(f"<li><strong>{html.escape(a.get('name') or 'Seslat')}:</strong> {html.escape('; '.join(casti))}.</li>")
    return radky


def popis_kouzla(k, uvod, odkaz):
    popis = f"<p>{html.escape(uvod)}</p>" if uvod else ""
    mech = mechanika(k)
    if mech:
        popis += "<h3>Automatizace</h3><ul>" + "".join(mech) + "</ul>"
    popis += (f'<p><strong>Plné znění:</strong> <a href="{odkaz}" target="_blank">SRD Jeskyní a draků – '
              f'{html.escape(k["name"])}</a> (Kapitola 10 – Magie).</p>')
    return popis


def nahrad_retezce(o, slovnik):
    if isinstance(o, dict):
        return {k: nahrad_retezce(v, slovnik) for k, v in o.items()}
    if isinstance(o, list):
        return [nahrad_retezce(v, slovnik) for v in o]
    if isinstance(o, str) and o in slovnik:
        return slovnik[o]
    return o


def prelozit_nazev(nazev, slovnik, cz, en):
    if nazev in slovnik:
        return slovnik[nazev]
    m = re.match(r"^(.*?):?\s*(\d)(st|nd|rd|th) Level$", nazev)
    if m:
        zaklad = m.group(1).strip()
        return f"{cz if zaklad == en else slovnik.get(zaklad, cz)}: {m.group(2)}. Stupeň"
    if nazev == en:
        return cz
    return None


# ---------------------------------------------------------------- hlavní běh

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dnd5e", required=True, help="cesta ke zdrojům systému dnd5e")
    ap.add_argument("--jednotky", choices=["sah", "ft"], default="sah")
    args = ap.parse_args()

    jad = nacti_yaml("jad-kouzla.yml")
    shrnuti = nacti_yaml("shrnuti.yml")
    materialy = nacti_yaml("materialy.yml")
    pre = nacti_yaml("preklady-aktivit.yml")
    akt_sl, ef_sl = pre.get("aktivity", {}), pre.get("efekty", {})
    podminky = nacti_yaml("podminky.yml")
    overtime = nacti_yaml("midi-overtime.yml")
    vlastni_spec = nacti_yaml("vlastni-kouzla.yml")

    srd = {}
    for f in glob.glob(os.path.join(args.dnd5e, "packs/_source/spells/**/*.yml"), recursive=True):
        with open(f, encoding="utf-8") as fh:
            d = yaml.safe_load(fh)
        if d and d.get("type") == "spell":
            srd[d["system"]["identifier"]] = d

    # kotva JaD ↔ identifikátor
    kotva_srd = {k: v["srd"] for k, v in jad.items() if v.get("srd")}
    nove_id = {ident: foundry_id(ident) for ident in srd}
    folder_id = {i: foundry_id(f"slozka-{i}") for i in range(10)}

    chyby, nepr_akt, nepr_ef = [], set(), set()
    kouzla, povolani_kouzla = [], {}

    for kotva, j in jad.items():
        ident = j.get("srd")
        if not ident:
            continue
        if ident not in srd:
            chyby.append(f"{kotva}: SRD kouzlo {ident} v dnd5e nenalezeno")
            continue
        puv = srd[ident]
        sid, en, cz = puv["_id"], puv["name"], j["cz"]
        nid = nove_id[ident]

        txt = json.dumps(puv, ensure_ascii=False)
        for i2, s2 in srd.items():
            txt = txt.replace(f"Compendium.dnd5e.spells.Item.{s2['_id']}", f"Compendium.{MODUL}.kouzla.Item.{nove_id[i2]}")
        txt = txt.replace(f"Item.{sid}", f"Item.{nid}")
        k = json.loads(txt)
        k.pop("_key", None)
        sy = k["system"]

        k.update({"_id": nid, "name": cz, "folder": folder_id[sy["level"]], "sort": 0, "ownership": {"default": 0}})
        if j.get("stupen") is not None and j["stupen"] != sy["level"]:
            chyby.append(f"{cz}: stupeň JaD {j['stupen']} ≠ SRD {sy['level']}")
        if j.get("skola"):
            sy["school"] = j["skola"]

        # aktivity
        efekt_idy = {e["_id"] for e in k.get("effects", [])}
        for a in sy["activities"].values():
            a["effects"] = [e for e in a.get("effects", []) if e.get("_id") in efekt_idy]
            puvodni = a.get("name") or ""
            if not puvodni:
                n = "Seslat" if len(sy["activities"]) == 1 else TYPY_AKTIVIT.get(a["type"], "Seslat")
            else:
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

        k = nahrad_retezce(k, podminky)
        sy = k["system"]
        preved_dosah(sy.get("range"), args.jednotky)
        preved_sablonu((sy.get("target") or {}).get("template"), args.jednotky)

        # Midi-QOL OverTime
        if ident in overtime:
            spec = overtime[ident]
            for e in k.get("effects", []):
                if spec.get("status") and spec["status"] not in (e.get("statuses") or []):
                    continue
                m = re.search(r": (\d)\. Stupeň$", e["name"])
                n = m.group(1) if m else str(max(sy["level"], 1))
                e.setdefault("system", {}).setdefault("changes", []).append(
                    {"key": "flags.midi-qol.OverTime", "value": spec["ot"].replace("{N}", n) + f",label={e['name']}",
                     "type": "custom", "phase": "initial", "priority": 20})
                e["flags"].setdefault(MODUL, {})["midiOverTime"] = True

        # materiály
        if sy["materials"].get("value"):
            if ident in materialy:
                sy["materials"]["value"] = materialy[ident]
            else:
                chyby.append(f"chybí překlad materiálu: {ident}")
                sy["materials"]["value"] = ""

        odkaz = f"{SRD_JAD}#{kotva}"
        if not shrnuti.get(ident):
            chyby.append(f"chybí shrnutí: {ident}")
        sy["description"] = {"value": popis_kouzla(k, shrnuti.get(ident), odkaz), "chat": ""}
        sy["source"] = {"custom": "", "book": "Jeskyně a draci", "page": "", "license": "CC-BY-4.0", "rules": "2014"}
        k["flags"] = {MODUL: {"kotva": kotva, "srd": sid, "nazevEn": en, "odkaz": odkaz}}
        k["_stats"] = stats()
        k["_key"] = f"!items!{nid}"
        kouzla.append(k)
        for p in j.get("povolani", []):
            povolani_kouzla.setdefault(p, []).append(nid)

    # původní kouzla JaD (mimo SRD 5.1)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import vlastni
    for kotva, j in jad.items():
        if j.get("srd"):
            continue
        spec = vlastni_spec.get(kotva)
        if not spec:
            chyby.append(f"chybí data původního kouzla JaD: {kotva} ({j['cz']})")
            continue
        spec = {**spec, "cz": j["cz"], "stupen": j["stupen"], "skola": j["skola"], "povolani": j.get("povolani", [])}
        if j.get("ritual") and "R" not in [s.upper() for s in spec.get("slozky", [])]:
            spec["slozky"] = list(spec.get("slozky", [])) + ["R"]
        k = vlastni.sestav(kotva, spec, foundry_id, args.jednotky)
        odkaz = f"{SRD_JAD}#{kotva}"
        k["system"]["description"]["value"] = popis_kouzla(k, spec.get("shrnuti"), odkaz)
        k["flags"][MODUL]["kotva"] = kotva
        k["flags"][MODUL]["odkaz"] = odkaz
        k["folder"] = folder_id[k["system"]["level"]]
        k["_stats"] = stats()
        k["_key"] = f"!items!{k['_id']}"
        kouzla.append(k)
        for p in j.get("povolani", []):
            povolani_kouzla.setdefault(p, []).append(k["_id"])

    nazvy = [k["name"] for k in kouzla]
    for n in {n for n in nazvy if nazvy.count(n) > 1}:
        chyby.append(f"duplicitní název: {n}")

    # složky
    slozky = [{"_id": folder_id[i], "name": SLOZKY[i], "type": "Item", "sorting": "a", "sort": (i + 1) * 100000,
               "folder": None, "color": None, "flags": {}, "_key": f"!folders!{folder_id[i]}"} for i in range(10)]

    # seznamy kouzel povolání (podle JaD)
    jid = foundry_id("seznamy-kouzel")
    stranky = []
    for i, ident in enumerate(sorted(povolani_kouzla, key=lambda x: POVOLANI[x])):
        pid = foundry_id(f"seznam-{ident}")
        stranky.append({"_id": pid, "name": f"Kouzla povolání {POVOLANI[ident]}", "type": "spells",
                        "sort": (i + 1) * 100000, "title": {"show": True, "level": 1},
                        "system": {"type": "class", "identifier": ident, "grouping": "level",
                                   "description": {"value": ATRIBUCE},
                                   "spells": sorted(f"Compendium.{MODUL}.kouzla.Item.{x}" for x in set(povolani_kouzla[ident])),
                                   "unlinkedSpells": []},
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
    bez = lambda o: {a: b for a, b in o.items() if a != "_key"}
    with open(os.path.join(KOREN, "data/kompendium/kouzla.json"), "w", encoding="utf-8") as fh:
        json.dump({"folders": [bez(s) for s in slozky], "items": [bez(k) for k in kouzla]}, fh, ensure_ascii=False)
    d2 = bez(denik)
    d2["pages"] = [bez(p) for p in d2["pages"]]
    with open(os.path.join(KOREN, "data/kompendium/seznamy-kouzel.json"), "w", encoding="utf-8") as fh:
        json.dump({"journal": [d2]}, fh, ensure_ascii=False)
    with open(os.path.join(KOREN, "data/kompendium/registr.json"), "w", encoding="utf-8") as fh:
        json.dump({"seznamyKouzel": [f"Compendium.{MODUL}.seznamy-kouzel.JournalEntry.{jid}.JournalEntryPage.{p['_id']}"
                                     for p in stranky]}, fh, ensure_ascii=False, indent=1)

    print(f"Kouzel: {len(kouzla)} (SRD {len(kouzla) - sum(1 for k in kouzla if k['flags'][MODUL].get('vlastni'))}, "
          f"původní JaD {sum(1 for k in kouzla if k['flags'][MODUL].get('vlastni'))}), jednotky: {args.jednotky}")
    print("Seznamy:", {POVOLANI[p["system"]["identifier"]]: len(p["system"]["spells"]) for p in stranky})
    for c in chyby:
        print("  !", c)
    if nepr_akt:
        print("  ! nepřeložené aktivity:", sorted(nepr_akt))
    if nepr_ef:
        print("  ! nepřeložené efekty:", sorted(nepr_ef))
    return 1 if chyby else 0


if __name__ == "__main__":
    sys.exit(main())
