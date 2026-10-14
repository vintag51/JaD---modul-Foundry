#!/usr/bin/env python3
"""
Generátor kompendia předmětů Jeskyní a draků (data/predmety.yml + data/kouzelne-predmety.yml
→ packs/_source/predmety, data/kompendium/predmety.json, scripts/registr-predmetu.mjs).

Mechaniku (útoky, zbroje, aktivity, efekty, kontejnery) přebírá z SRD předmětů systému dnd5e,
název, cenu, váhu a popis bere z JaD. Vzdálenosti převádí na sáhy, odkazy na SRD kouzla přesměruje
na kouzla modulu.

Použití: python3 tools/generuj_predmety.py --dnd5e ../dnd5e
"""
import argparse, copy, glob, html, json, os, re, shutil, sys
from collections import Counter
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generuj import KOREN, MODUL, ZASAHY, foundry_id, nacti_yaml, prevod, slug, stats  # noqa: E402

PACK = "predmety"
LICENCE = "Licence JaD pro třetí strany"
SRD_VYB = "https://dnd5esrd.d20.cz/jeskyne-a-draci/6-vybaveni.html"
SRD_MAG = "https://dnd5esrd.d20.cz/jeskyne-a-draci/11-kouzelne-predmety.html"
MENY = {"zl": "gp", "st": "sp", "md": "cp"}
VZACNOST = {"common": "Běžný", "uncommon": "Neobvyklý", "rare": "Vzácný", "veryRare": "Velmi vzácný",
            "legendary": "Legendární", "artifact": "Artefakt"}
DRUH_ZBRANE = {"simpleM": "Jednoduchá zbraň na blízko", "martialM": "Válečná zbraň na blízko",
               "simpleR": "Jednoduchá zbraň na dálku", "martialR": "Válečná zbraň na dálku"}
TYPY_ODOLNOSTI = ["acid", "cold", "fire", "force", "lightning", "necrotic", "poison", "psychic", "radiant", "thunder"]
OHNISKA = {"crystal": ("arcane", "crystal"), "orb": ("arcane", "orb"), "rod": ("arcane", "rod"), "staff": ("arcane", "staff"),
           "wand": ("arcane", "wand"), "sprig-of-mistletoe": ("druidic", "mistletoe"), "wooden-staff": ("druidic", "woodenstaff"),
           "yew-wand": ("druidic", "yewwand"), "amulet": ("holy", "amulet"), "emblem": ("holy", "emblem"), "reliquary": ("holy", "reliquary")}
PLUS_VZACNOST_ZBRANE = {1: "uncommon", 2: "rare", 3: "veryRare"}


def uuid(iid):
    return f"Compendium.{MODUL}.{PACK}.Item.{iid}"


def cena(text):
    m = re.match(r"^\s*([\d\s]+(?:[.,]\d+)?)\s*(zl|st|md)\s*$", str(text))
    if not m:
        raise ValueError(f"Neznámá cena: {text}")
    v = float(m.group(1).replace(" ", "").replace(",", "."))
    return {"value": int(v) if v == int(v) else v, "denomination": MENY[m.group(2)]}


# ---------------------------------------------------------------- SRD

class Srd:
    def __init__(self, koren):
        self.koren = os.path.join(koren, "packs/_source/items")
        self.spells = {}
        for f in glob.glob(os.path.join(koren, "packs/_source/spells/**/*.yml"), recursive=True):
            with open(f, encoding="utf-8") as fh:
                d = yaml.safe_load(fh)
            if d and d.get("type") == "spell":
                self.spells[d["_id"]] = d["system"]["identifier"]
        self.vsechny_id = set()
        for f in glob.glob(os.path.join(self.koren, "**/*.yml"), recursive=True):
            with open(f, encoding="utf-8") as fh:
                d = yaml.safe_load(fh)
            if d and "_id" in d:
                self.vsechny_id.add(d["_id"])

    def cesta(self, rel):
        for c in (f"{rel}.yml", f"{rel}/_container.yml"):
            p = os.path.join(self.koren, c)
            if os.path.exists(p):
                return p
        return None

    def nacti(self, rel):
        p = self.cesta(rel)
        if not p:
            return None
        with open(p, encoding="utf-8") as fh:
            return yaml.safe_load(fh)


# ---------------------------------------------------------------- úpravy dokumentu

class Generator:
    def __init__(self, srd, preklady, nase_kouzla):
        self.srd = srd
        self.akt_sl = preklady.get("aktivity", {})
        self.ef_sl = preklady.get("efekty", {})
        self.nase_kouzla = nase_kouzla          # identifikátor SRD kouzla → id v kompendiu modulu
        self.polozky, self.chyby = [], []
        self.nepr_akt, self.nepr_ef = Counter(), Counter()
        self.slozky = {}
        self.pouzita_id = set()

    def slozka(self, nazev, rodic=None):
        klic = (rodic, nazev)
        if klic not in self.slozky:
            fid = foundry_id(f"predmety-slozka-{rodic}-{nazev}")
            nad = next((f["_id"] for (r, n), f in self.slozky.items() if n == rodic), None) if rodic else None
            self.slozky[klic] = {"_id": fid, "name": nazev, "type": "Item", "sorting": "a",
                                 "sort": (len(self.slozky) + 1) * 1000, "folder": nad,
                                 "color": None, "flags": {}, "_key": f"!folders!{fid}"}
        return self.slozky[klic]["_id"]

    def novy(self, seed, zdroj, nazev, slozka):
        """Kopie SRD dokumentu s novým ID, názvem a složkou; odkazy na SRD kouzla přesměruje na kouzla modulu."""
        iid = foundry_id(f"predmet:{seed}")
        if iid in self.pouzita_id:
            raise ValueError(f"Duplicitní předmět {seed}")
        self.pouzita_id.add(iid)
        txt = json.dumps(zdroj, ensure_ascii=False)
        txt = txt.replace(f"Item.{zdroj['_id']}", f"Item.{iid}")

        def kouzlo(m):
            ident = self.srd.spells.get(m.group(1))
            if ident and ident in self.nase_kouzla:
                return f"Compendium.{MODUL}.kouzla.Item.{self.nase_kouzla[ident]}"
            return m.group(0)
        txt = re.sub(r"Compendium\.dnd5e\.spells\.Item\.([A-Za-z0-9]{16})", kouzlo, txt)
        d = json.loads(txt)
        d.pop("_key", None)
        d.update({"_id": iid, "name": nazev, "folder": slozka, "sort": 0, "ownership": {"default": 0},
                  "_stats": stats()})
        d.setdefault("effects", [])
        d["flags"] = {}
        sy = d["system"]
        sy["source"] = {"custom": "", "book": "Jeskyně a draci", "page": "", "license": LICENCE, "rules": "2014"}
        sy["container"] = None
        if isinstance(sy.get("unidentified"), dict):
            sy["unidentified"]["description"] = ""
        self.preved(d, nazev, zdroj["name"])
        return d

    def preved(self, d, cz, en):
        sy = d["system"]
        r = sy.get("range")
        if isinstance(r, dict) and r.get("units") == "ft":
            for k in ("value", "long", "reach"):
                if r.get(k) not in (None, ""):
                    r[k], _ = prevod(r[k], "ft", "sah")
            r["units"] = "sah"
        for a in (sy.get("activities") or {}).values():
            rr = a.get("range") or {}
            if rr.get("units") == "ft":
                rr["value"], rr["units"] = prevod(rr.get("value"), "ft", "sah")
            t = (a.get("target") or {}).get("template")
            if isinstance(t, dict):
                if (t.get("units") or "ft") == "ft":
                    for k in ("size", "width", "height"):
                        if t.get(k) not in (None, ""):
                            t[k], _ = prevod(t[k], "ft", "sah")
                    t["units"] = "sah"
            if isinstance(a.get("description"), dict):
                a["description"]["chatFlavor"] = ""
                if a["description"].get("value"):
                    a["description"]["value"] = ""
            n = a.get("name") or ""
            if n:
                if n in self.akt_sl:
                    a["name"] = self.akt_sl[n]
                elif n == en:
                    a["name"] = cz
                else:
                    self.nepr_akt[n] += 1
        for e in d.get("effects", []):
            n = e.get("name", "")
            if n in self.ef_sl:
                e["name"] = self.ef_sl[n]
            elif n == en or not n:
                e["name"] = cz
            else:
                self.nepr_ef[n] += 1
            e["description"] = f"<p>Účinek předmětu <em>{html.escape(cz)}</em>.</p>"
            e["_stats"] = stats()
            if str(e.get("origin") or "").startswith("Compendium.dnd5e"):
                e["origin"] = uuid(d["_id"])

    def pridej(self, d):
        for e in d.get("effects", []):
            e["_key"] = f"!items.effects!{d['_id']}.{e['_id']}"
        d["_key"] = f"!items!{d['_id']}"
        self.polozky.append(d)
        return d


def popis(radky, d, odkaz, nazev_odkazu):
    out = "".join(f"<p>{r}</p>" for r in radky if r)
    if d:
        out += f"<p>{html.escape(d)}</p>"
    out += f"<p><em>Plné znění: <a href=\"{odkaz}\" target=\"_blank\">SRD Jeskyní a draků – {nazev_odkazu}</a>.</em></p>"
    return out


def nastav(d, polozka):
    sy = d["system"]
    if "cena" in polozka:
        c = cena(polozka["cena"])
        ks = polozka.get("ks")
        if ks:
            c["value"] = round(c["value"] / ks, 4)
            sy["quantity"] = ks
        sy["price"] = c
    if "lb" in polozka:
        lb = polozka["lb"]
        if polozka.get("ks"):
            lb = round(lb / polozka["ks"], 4)
        sy["weight"] = {"value": lb, "units": "lb"}


def hlavicka_magie(sy):
    vz = VZACNOST.get(sy.get("rarity") or "", "")
    sl = {"required": "vyžaduje Sladění", "optional": "Sladění volitelné"}.get(sy.get("attunement") or "", "")
    return f"<em>{', '.join(x for x in (vz, sl) if x)}</em>" if (vz or sl) else ""


# ---------------------------------------------------------------- hlavní běh

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dnd5e", required=True)
    args = ap.parse_args()

    srd = Srd(args.dnd5e)
    data = nacti_yaml("predmety.yml")
    magie = nacti_yaml("kouzelne-predmety.yml")
    preklady = nacti_yaml("preklady-predmetu.yml")

    nase_kouzla = {}
    p = os.path.join(KOREN, "data/kompendium/kouzla.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as fh:
            for k in json.load(fh)["items"]:
                nase_kouzla[k["system"]["identifier"]] = k["_id"]

    g = Generator(srd, preklady, nase_kouzla)
    zaklad_ids = {"weaponIds": {}, "armorIds": {}, "toolIds": {}, "focus": {}}
    zakladni = g.slozka("Vybavení")
    mag_root = g.slozka("Kouzelné předměty")
    s_zbr = g.slozka("Zbraně", "Vybavení")
    s_zbroje = g.slozka("Zbroje a štíty", "Vybavení")
    s_vyb = g.slozka("Výbava dobrodruhů", "Vybavení")
    s_bal = g.slozka("Balíčky vybavení", "Vybavení")
    s_pom = g.slozka("Pomůcky", "Vybavení")

    def srd_nebo_chyba(rel, kdo):
        z = srd.nacti(rel)
        if z is None:
            g.chyby.append(f"{kdo}: SRD předmět {rel} nenalezen")
        return z

    # ----- zbraně
    zbrane_srd = {}
    for z in data["zbrane"]:
        zdroj = srd_nebo_chyba(z["srd"], z["n"])
        if not zdroj:
            continue
        d = g.novy(z["srd"], zdroj, z["n"], s_zbr)
        nastav(d, z)
        druh = DRUH_ZBRANE.get(d["system"]["type"]["value"], "Zbraň")
        radky = [f"<strong>{druh}</strong>",
                 f"Zásah: {html.escape(z['t'])}" + (f" · Dostřel: {z['dostrel']} sáhů" if z.get("dostrel") else ""),
                 f"Vlastnosti: {html.escape(z['v'])}" if z.get("v") else ""]
        d["system"]["description"] = {"value": popis(radky, z.get("d"), f"{SRD_VYB}#tabulka-zbrani-na-blizko", "Vybavení"), "chat": ""}
        g.pridej(d)
        zbrane_srd[z["srd"]] = z["n"]
        zaklad_ids["weaponIds"][d["system"]["type"]["baseItem"]] = uuid(d["_id"])

    # ----- palné zbraně
    s_pal = g.slozka("Palné zbraně", "Vybavení")
    vzor = srd.nacti("weapon/light-crossbow")
    for z in data.get("palne", []):
        d = g.novy(f"palna/{z['k']}", vzor, z["n"], s_pal)
        sy = d["system"]
        nastav(d, z)
        sy["type"] = {"value": z["druh"], "baseItem": {"pistole": "pistol", "musketa": "musket"}.get(z["k"], "")}
        sy["identifier"] = z["k"]
        sy["properties"] = list(z["vl"])
        sy.pop("ammunition", None)
        sy["damage"]["base"].update({"number": z["kostka"][0], "denomination": z["kostka"][1], "types": [z["typ"]]})
        sy["range"] = {"value": z["dostrel"][0], "long": z["dostrel"][1], "units": "sah", "reach": None}
        for a in sy["activities"].values():
            a["range"] = {"value": str(z["dostrel"][0]), "units": "sah", "special": "", "override": False}
        if z.get("vybusna"):
            aid = foundry_id(f"predmet:palna/{z['k']}:vybuch")
            sy["activities"][aid] = {
                "_id": aid, "type": "save", "name": "Výbuch", "img": "", "sort": 200000, "flags": {},
                "activation": {"type": "special", "value": None, "condition": "", "override": False},
                "consumption": {"targets": [], "scaling": {"allowed": False, "max": ""}, "spellSlot": False},
                "description": {"chatFlavor": ""}, "duration": {"concentration": False, "value": "", "units": "inst", "special": "", "override": False},
                "effects": [], "range": {"units": "", "special": "", "override": False},
                "target": {"template": {"count": "", "contiguous": False, "type": "radius", "size": "1", "width": "", "height": "", "units": "sah"},
                           "affects": {"count": "", "type": "creature", "choice": False, "special": ""}, "prompt": True, "override": False},
                "save": {"ability": ["dex"], "dc": {"calculation": "", "formula": "8 + @abilities.dex.mod + @prof"}},
                "damage": {"onSave": "none", "parts": [{"number": 1, "denomination": 8, "bonus": "", "types": ["fire"],
                                                         "custom": {"enabled": False, "formula": ""}, "scaling": {"mode": "", "number": None, "formula": ""}}]},
                "uses": {"spent": 0, "recovery": [], "max": ""}, "visibility": {"level": {"min": None, "max": None}}}
        vl = {"lod": f"Nabíjecí ({z['nabiti']})", "lgt": "Lehká", "two": "Obouruční", "hvy": "Těžká", "fir": None}
        texty = [vl[v] for v in z["vl"] if vl.get(v)] + [f"Selhání {z['selhani']}"] + (["Výbušná"] if z.get("vybusna") else [])
        radky = [f"<strong>{DRUH_ZBRANE[z['druh']]} – palná</strong>",
                 f"Zásah: {z['kostka'][0]}k{z['kostka'][1]} {ZASAHY[z['typ']]} · Dostřel: {z['dostrel'][0] // 5} / {z['dostrel'][1] // 5} sáhů",
                 f"Vlastnosti: {', '.join(texty)}"]
        pravidla = ("Palné zbraně jsou volitelné pravidlo JaD. Po výstřelu je musíš nabít (počet Akcí v závorce), proti protivníkům v Těžké zbroji "
                    "máš Výhodu. Padne-li na kostce Útoku číslo do Hodnoty selhání, zbraň se zasekne – zprovozníš ji Kutilskými nástroji (SO 8 + Selhání); "
                    "bez Zdatnosti je Selhání o 1 vyšší." + (" Při dopadu vybuchne: vše do 1 sáhu musí uspět v Záchraně na Obratnost "
                    "(SO 8 + Oprava obratnosti + Zdatnostní bonus střelce), jinak utrpí 1k8 Ohnivého zásahu." if z.get("vybusna") else ""))
        sy["description"] = {"value": popis(radky, pravidla, f"{SRD_VYB}#palne-zbrane", "Palné zbraně"), "chat": ""}
        g.pridej(d)
        if sy["type"]["baseItem"]:
            zaklad_ids["weaponIds"][sy["type"]["baseItem"]] = uuid(d["_id"])

    # ----- zbroje
    zbroje_srd = {}
    for z in data["zbroje"]:
        zdroj = srd_nebo_chyba(z["srd"], z["n"])
        if not zdroj:
            continue
        d = g.novy(z["srd"], zdroj, z["n"], s_zbroje)
        nastav(d, z)
        sy = d["system"]
        druh = {"light": "Lehká zbroj", "medium": "Střední zbroj", "heavy": "Těžká zbroj", "shield": "Štít"}.get(sy["type"]["value"], "Zbroj")
        radky = [f"<strong>{druh}</strong>", f"Obranné číslo: {z['oc']}",
                 "Nevýhoda k Nenápadnosti" if "stealthDisadvantage" in sy.get("properties", []) else "",
                 f"Bez Síly {z['sila']} (zjednodušená nosnost) klesne Rychlost o 2 sáhy" if z.get("sila") else "",
                 f"Zabírá {z['radky']} {'Řádek' if z['radky'] == 1 else 'Řádky'} vybavení"]
        sy["description"] = {"value": popis(radky, z.get("d"), f"{SRD_VYB}#zbroje-a-stity", "Vybavení"), "chat": ""}
        g.pridej(d)
        zbroje_srd[z["srd"]] = z["n"]
        zaklad_ids["armorIds"][d["system"]["type"]["baseItem"]] = uuid(d["_id"])

    # ----- výbava a pomůcky
    jmena_stem = {}
    for sekce, slozka_def, kotva in (("vybava", s_vyb, "vybava-dobrodruhu"), ("pomucky", s_pom, "pomucky")):
        for z in data[sekce]:
            sl = g.slozka(z["s"], "Vybavení") if z.get("s") else slozka_def
            if z.get("srd"):
                zdroj = srd_nebo_chyba(z["srd"], z["n"])
                if not zdroj:
                    continue
                d = g.novy(z["srd"], zdroj, z["n"], sl)
                jmena_stem[z["srd"].split("/")[-1]] = z
            else:
                zdroj = srd_nebo_chyba(z["zaklad"], z["n"])
                if not zdroj:
                    continue
                d = g.novy(f"vlastni/{z['k']}", zdroj, z["n"], sl)
                sy = d["system"]
                sy["identifier"] = z["k"]
                if d["type"] == "tool":
                    sy["type"]["baseItem"] = z["k"]
                    sy["ability"] = z.get("vlastnost", sy.get("ability"))
                if z.get("typ") in ("trinket", "potion", "wondrous") and d["type"] == "consumable":
                    sy["type"] = {"value": z["typ"], "subtype": ""}
                if z["k"] != "voda-sfer":
                    sy["activities"] = {}
                    d["effects"] = []
                if z.get("akt"):
                    from generuj_povolani import aktivita
                    a = aktivita(f"predmet:vlastni/{z['k']}:akt", z["akt"], 0, False, [])
                    sy["activities"] = {a["_id"]: a}
                    if d["type"] == "consumable":
                        sy["uses"] = {"max": "1", "spent": 0, "recovery": [], "autoDestroy": True}
                        a["consumption"]["targets"] = [{"type": "itemUses", "value": "1", "target": "", "scaling": {}}]
            nastav(d, z)
            d["system"]["description"] = {"value": popis([], z.get("d"), f"{SRD_VYB}#{kotva}", "Vybavení"), "chat": ""}
            g.pridej(d)
            if d["type"] == "tool" and z.get("srd"):
                zaklad_ids["toolIds"][d["system"]["type"]["baseItem"]] = uuid(d["_id"])
            stem = (z.get("srd") or "").split("/")[-1]
            if stem in OHNISKA:
                typ, klic = OHNISKA[stem]
                zaklad_ids["focus"].setdefault(typ, {})[klic] = uuid(d["_id"])

    # ----- balíčky (kontejnery s obsahem)
    obsah_jmena = data.get("obsah", {})

    def kontejner(adresar, rel, nazev, cena_txt, nadrazeny, slozka, seed):
        with open(os.path.join(adresar, "_container.yml"), encoding="utf-8") as fh:
            zdroj = yaml.safe_load(fh)
        d = g.novy(seed, zdroj, nazev, slozka)
        if cena_txt:
            d["system"]["price"] = cena(cena_txt)
        d["system"]["container"] = nadrazeny
        g.pridej(d)
        for f in sorted(os.listdir(adresar)):
            cesta = os.path.join(adresar, f)
            stem = f[:-4] if f.endswith(".yml") else f
            if f == "_container.yml":
                continue
            z = jmena_stem.get(stem)
            jmeno = (z or {}).get("n") or obsah_jmena.get(stem)
            if not jmeno:
                g.chyby.append(f"{nazev}: chybí český název obsahu {stem}")
                jmeno = stem
            if os.path.isdir(cesta):
                kontejner(cesta, f"{rel}/{stem}", jmeno, None, d["_id"], slozka, f"{seed}/{stem}")
                continue
            with open(cesta, encoding="utf-8") as fh:
                pz = yaml.safe_load(fh)
            mnozstvi = pz["system"].get("quantity", 1)
            x = g.novy(f"{seed}/{stem}", pz, jmeno, slozka)
            if z:
                nastav(x, {k: v for k, v in z.items() if k in ("cena", "lb")})
            x["system"]["quantity"] = mnozstvi
            x["system"]["container"] = d["_id"]
            x["system"]["description"] = {"value": popis([], (z or {}).get("d"), f"{SRD_VYB}#balicky-vybaveni", "Vybavení"), "chat": ""}
            g.pridej(x)
        return d

    for b in data.get("balicky", []):
        adr = os.path.join(srd.koren, b["srd"])
        d = kontejner(adr, b["srd"], b["n"], b["cena"], None, s_bal, b["srd"])
        d["system"]["description"] = {"value": popis([], "Balíček výbavy za zvýhodněnou cenu; obsah najdeš uvnitř kontejneru.",
                                                       f"{SRD_VYB}#balicky-vybaveni", "Vybavení"), "chat": ""}

    # ----- kouzelné předměty
    for kategorie, seznam in magie.items():
        sl = g.slozka(kategorie, "Kouzelné předměty")
        for m in seznam:
            odkaz = f"{SRD_MAG}#{m['kotva']}"
            varianty = []
            if m.get("varianty"):
                varianty = [(v["srd"], v["n"]) for v in m["varianty"]]
            elif m.get("odolnost"):
                for typ in TYPY_ODOLNOSTI:
                    varianty.append((m["odolnost"].format(typ=typ), f"{m['n']} ({ZASAHY[typ]} zásah)"))
            elif m.get("plus") == "zbrane":
                for rel, cz in zbrane_srd.items():
                    for n in (1, 2, 3):
                        varianty.append((f"{rel}-{n}", f"{cz} +{n}"))
            elif m.get("plus") == "zbroje":
                for rel, cz in zbroje_srd.items():
                    if rel.endswith("/shield"):
                        continue
                    for n in (1, 2, 3):
                        varianty.append((f"{rel}-{n}", f"{cz} +{n}"))
            elif m.get("odolani_zbroje"):
                for rel, cz in zbroje_srd.items():
                    if rel.endswith("/shield"):
                        continue
                    varianty.append((f"{rel}-of-resistance".replace("armor-armor", "armor"), f"{m['n']} ({cz})"))
            elif m.get("srd"):
                varianty = [(m["srd"], m["n"])]

            vl_slozka = g.slozka(m["n"], kategorie) if len(varianty) > 3 else sl
            for rel, cz in varianty:
                if m.get("odolani_zbroje") and not srd.cesta(rel):
                    rel = rel.replace("-of-resistance", "-armor-of-resistance")
                zdroj = srd_nebo_chyba(rel, cz)
                if not zdroj:
                    continue
                d = g.novy(rel, zdroj, cz, vl_slozka)
                if m.get("odolani_zbroje"):
                    eid = foundry_id(f"predmet:{rel}:odolnost")
                    d["effects"] = [{"_id": eid, "name": "Odolnost (uprav typ zásahu)", "img": d["img"], "type": "base",
                                     "transfer": True, "disabled": False, "statuses": [], "tint": "#ffffff", "showIcon": 1,
                                     "duration": {"value": None, "units": "seconds", "expiry": None, "expired": False},
                                     "system": {"changes": [{"key": "system.traits.dr.value", "value": "fire", "type": "add",
                                                             "phase": "initial", "priority": None}]},
                                     "description": "<p>Výchozí typ je Ohnivý – změň podle konkrétní zbroje.</p>",
                                     "origin": uuid(d["_id"]), "flags": {}}]
                d["system"]["description"] = {"value": popis([hlavicka_magie(d["system"])], m.get("d"), odkaz, "Kouzelné předměty"), "chat": ""}
                d["flags"] = {MODUL: {"kotva": m["kotva"]}}
                g.pridej(d)

            if m.get("ohnisko"):
                zdroj = srd.nacti("spellcasting-focus/crystal")
                for n, vz in ((1, "uncommon"), (2, "rare"), (3, "veryRare")):
                    cz = f"{m['n'].replace('+X', '')}+{n}"
                    d = g.novy(f"vlastni/ohnisko-{n}", zdroj, cz, sl)
                    sy = d["system"]
                    sy.update({"rarity": vz, "attunement": "required", "identifier": f"ohniskovy-predmet-{n}"})
                    sy["properties"] = sorted(set(sy.get("properties", [])) | {"mgc"})
                    sy["price"] = {"value": {1: 500, 2: 5000, 3: 50000}[n], "denomination": "gp"}
                    eid = foundry_id(f"predmet:vlastni/ohnisko-{n}:efekt")
                    d["effects"] = [{"_id": eid, "name": cz, "img": d["img"], "type": "base", "transfer": True, "disabled": False,
                                     "statuses": [], "tint": "#ffffff", "showIcon": 1,
                                     "duration": {"value": None, "units": "seconds", "expiry": None, "expired": False},
                                     "system": {"changes": [{"key": k, "value": f"+{n}", "type": "add", "phase": "initial", "priority": None}
                                                            for k in ("system.bonuses.msak.attack", "system.bonuses.rsak.attack", "system.bonuses.spell.dc")]},
                                     "description": f"<p>Účinek předmětu <em>{cz}</em>.</p>", "origin": uuid(d["_id"]), "flags": {}}]
                    sy["description"] = {"value": popis([hlavicka_magie(sy)], m.get("d"), odkaz, "Kouzelné předměty"), "chat": ""}
                    d["flags"] = {MODUL: {"kotva": m["kotva"]}}
                    g.pridej(d)

            if m.get("k"):
                zdroj = srd_nebo_chyba(m["zaklad"], m["n"])
                if not zdroj:
                    continue
                d = g.novy(f"vlastni/{m['k']}", zdroj, m["n"], sl)
                sy = d["system"]
                sy["identifier"] = m["k"]
                if m.get("vz"):
                    sy["rarity"] = m["vz"]
                    sy["price"] = {"value": {"common": 50, "artifact": 0}.get(m["vz"], sy["price"]["value"]), "denomination": "gp"}
                if "sladeni" in m:
                    sy["attunement"] = m["sladeni"]
                sy["properties"] = sorted(set(sy.get("properties", [])) | {"mgc"} | set(m.get("vl_plus", [])))
                if d["type"] != "weapon":
                    sy["activities"] = {}
                d["effects"] = []
                if m.get("typ") and d["type"] == "consumable":
                    sy["type"] = {"value": m["typ"], "subtype": ""}
                if m.get("mnozstvi"):
                    sy["quantity"] = m["mnozstvi"]
                if m.get("magie"):
                    sy["magicalBonus"] = m["magie"]
                if m.get("kostka"):
                    sy["damage"]["base"].update({"number": m["kostka"][0], "denomination": m["kostka"][1]})
                if m.get("kostka2"):
                    sy["damage"]["versatile"].update({"number": m["kostka2"][0], "denomination": m["kostka2"][1]})
                if m.get("dostrel"):
                    sy["range"].update({"value": m["dostrel"][0] // 5, "long": m["dostrel"][1] // 5, "units": "sah"})
                for a in sy.get("activities", {}).values():
                    if a.get("type") == "attack":
                        if m.get("extra"):
                            n, k, t = m["extra"]
                            a["damage"]["parts"] = [{"number": n, "denomination": k, "bonus": "", "types": [t],
                                                     "custom": {"enabled": False, "formula": ""}, "scaling": {"mode": "", "number": None, "formula": ""}}]
                        if m.get("kriticky"):
                            a["attack"]["critical"]["threshold"] = m["kriticky"]
                if m.get("sila"):
                    eid = foundry_id(f"predmet:vlastni/{m['k']}:sila")
                    d["effects"].append({"_id": eid, "name": m["n"], "img": d["img"], "type": "base", "transfer": True, "disabled": False,
                                         "statuses": [], "tint": "#ffffff", "showIcon": 1,
                                         "duration": {"value": None, "units": "seconds", "expiry": None, "expired": False},
                                         "system": {"changes": [{"key": "system.abilities.str.value", "value": str(m["sila"]), "type": "upgrade",
                                                                 "phase": "initial", "priority": None}]},
                                         "description": f"<p>Účinek předmětu <em>{m['n']}</em>.</p>", "origin": uuid(d["_id"]), "flags": {}})
                if m.get("cast"):
                    sid = nase_kouzla.get(m["cast"])
                    if not sid:
                        g.chyby.append(f"{m['n']}: kouzlo {m['cast']} není v kompendiu kouzel")
                    else:
                        aid = foundry_id(f"predmet:vlastni/{m['k']}:cast")
                        sy["activities"] = {aid: {
                            "_id": aid, "type": "cast", "name": "Seslat", "img": "", "sort": 100000, "flags": {},
                            "spell": {"uuid": f"Compendium.{MODUL}.kouzla.Item.{sid}", "challenge": {"attack": None, "save": None, "override": False},
                                      "level": None, "properties": ["vocal", "somatic"], "ability": "", "spellbook": True},
                            "activation": {"type": "action", "value": 1, "override": False},
                            "consumption": {"targets": [], "scaling": {"allowed": False}, "spellSlot": False},
                            "description": {"chatFlavor": ""}, "duration": {"units": "inst", "concentration": False, "override": False},
                            "range": {"override": False}, "target": {"override": False, "prompt": True},
                            "uses": {"spent": 0, "recovery": [], "max": ""},
                            "visibility": {"requireAttunement": False, "requireIdentification": False, "requireMagic": False,
                                           "level": {"min": None, "max": None}}}}
                popisek = ("<em>Originální předmět JaD</em>" if m.get("jad") else "")
                sy["description"] = {"value": popis([hlavicka_magie(sy), popisek], m.get("d"), odkaz, "Kouzelné předměty"), "chat": ""}
                d["flags"] = {MODUL: {"kotva": m["kotva"]}}
                g.pridej(d)

    # ----- kontrola odkazů na SRD předměty a zápis
    for d in g.polozky:
        txt = json.dumps(d)
        for m in re.finditer(r"Compendium\.dnd5e\.items\.Item\.([A-Za-z0-9]{16})", txt):
            g.chyby.append(f"{d['name']}: odkaz na SRD předmět {m.group(1)} zůstal")

    cil = os.path.join(KOREN, "packs/_source", PACK)
    shutil.rmtree(cil, ignore_errors=True)
    os.makedirs(cil)
    for d in g.polozky:
        with open(os.path.join(cil, f"{slug(d['name'])}_{d['_id']}.json"), "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=2)
    folders = list(g.slozky.values())
    for f in folders:
        with open(os.path.join(cil, f"_slozka_{f['_id']}.json"), "w", encoding="utf-8") as fh:
            json.dump(f, fh, ensure_ascii=False, indent=2)
    bez = lambda o: {a: b for a, b in o.items() if a != "_key"}
    with open(os.path.join(KOREN, "data/kompendium/predmety.json"), "w", encoding="utf-8") as fh:
        json.dump({"folders": [bez(f) for f in folders],
                   "items": [{**bez(d), "effects": [bez(e) for e in d.get("effects", [])]} for d in g.polozky]}, fh, ensure_ascii=False)

    # registr vlastních nástrojů pro skript modulu (zdatnosti v Pomůckách)
    nastroje = {}
    for z in data["pomucky"]:
        if z.get("k"):
            nastroje[z["k"]] = {"ability": z.get("vlastnost", "int"), "id": uuid(foundry_id(f"predmet:vlastni/{z['k']}"))}
    with open(os.path.join(KOREN, "scripts/registr-predmetu.mjs"), "w", encoding="utf-8") as fh:
        fh.write("// Vygenerováno nástrojem tools/generuj_predmety.py – neupravovat ručně.\n")
        fh.write(f"export const NASTROJE = {json.dumps(nastroje, ensure_ascii=False, indent=2)};\n")
        fh.write("// Základní předměty dnd5e (volby zbraní, zbrojí, pomůcek a ohnisek) → české předměty JaD.\n")
        fh.write(f"export const ZAKLADNI = {json.dumps(zaklad_ids, ensure_ascii=False, indent=2)};\n")

    print(f"Předměty: {len(g.polozky)} ({dict(Counter(d['type'] for d in g.polozky))}), složek {len(folders)}")
    if g.nepr_akt:
        print("Nepřeložené aktivity:", dict(g.nepr_akt))
    if g.nepr_ef:
        print("Nepřeložené efekty:", dict(g.nepr_ef))
    for c in g.chyby:
        print("CHYBA:", c)
    return 1 if g.chyby else 0


if __name__ == "__main__":
    sys.exit(main())
