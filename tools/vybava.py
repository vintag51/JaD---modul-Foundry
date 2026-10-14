"""Převod počátečního vybavení z data/vybaveni-startovni.yml na system.startingEquipment dnd5e."""
import json, os, re

from generuj import KOREN, MODUL, foundry_id

_PREDMETY = None


def predmety():
    """Název → id předmětu v kompendiu JaD – Předměty (jen předměty mimo kontejnery)."""
    global _PREDMETY
    if _PREDMETY is None:
        _PREDMETY = {}
        p = os.path.join(KOREN, "data/kompendium/predmety.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                for i in json.load(fh)["items"]:
                    if not i["system"].get("container"):
                        _PREDMETY.setdefault(i["name"], i["_id"])
    return _PREDMETY


KATEGORIE = {"zbran": "weapon", "zbroj": "armor", "ohnisko": "focus", "nastroj": "tool"}


def startovni(seed, seznam, chyby):
    """Vrátí seznam EquipmentEntryData. Prvky nejvyšší úrovně jsou zabalené do skupiny AND."""
    if not seznam:
        return []
    if not predmety():
        chyby.append(f"{seed}: chybí data/kompendium/predmety.json – spusť nejdřív generuj_predmety.py")
        return []
    vystup, citac = [], [0]

    def nove(typ, skupina, **kw):
        citac[0] += 1
        e = {"_id": foundry_id(f"vybava:{seed}:{citac[0]}"), "group": skupina, "sort": citac[0] * 100000,
             "type": typ, "requiresProficiency": False}
        e.update(kw)
        vystup.append(e)
        return e

    def prvek(x, skupina):
        if isinstance(x, list):
            op = str(x[0]).upper()
            if op not in ("OR", "AND"):
                chyby.append(f"{seed}: neznámý operátor {x[0]}")
                return
            g = nove(op, skupina)
            for y in x[1:]:
                prvek(y, g["_id"])
        elif isinstance(x, dict):
            (k, v), = x.items()
            if k == "mince":
                nove("currency", skupina, key="gp", count=int(v))
            elif k in KATEGORIE:
                nove(KATEGORIE[k], skupina, key=str(v), count=None)
            else:
                chyby.append(f"{seed}: neznámý prvek {x}")
        else:
            m = re.match(r"^(\d+)x\s+(.+)$", str(x))
            pocet, nazev = (int(m.group(1)), m.group(2)) if m else (None, str(x))
            iid = predmety().get(nazev)
            if not iid:
                chyby.append(f"{seed}: předmět „{nazev}“ v kompendiu není")
                return
            nove("linked", skupina, key=f"Compendium.{MODUL}.predmety.Item.{iid}", count=pocet)

    koren = nove("AND", "")
    for x in seznam:
        prvek(x, koren["_id"])
    return vystup
