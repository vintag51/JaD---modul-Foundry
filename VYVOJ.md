# Jeskyně a draci pro Foundry VTT – vývoj

Tento dokument je pro ty, kdo chtějí modul upravovat nebo rozšiřovat. Hráči a PH ho nepotřebují – vše pro ně je v [README](README.md).

## Jak se data generují

```
dnd5e (SRD 5.1, automatizace)  ─┐
data/jad-kouzla.yml             │  (seznam kouzel JaD, párování na SRD)
data/shrnuti.yml                ├─► tools/generuj.py ─► packs/_source/*  ─► tools/build.mjs ─► packs/* (LevelDB)
data/materialy.yml              │                    └► data/kompendium/* (záložní import)
data/preklady-aktivit.yml       │
data/podminky.yml               │
data/midi-overtime.yml          │
data/vlastni-kouzla.yml        ─┘
```

```bash
git clone https://github.com/foundryvtt/dnd5e ../dnd5e
pip install pyyaml
python3 tools/generuj.py --dnd5e ../dnd5e        # --jednotky ft pro stopy místo sáhů
python3 tools/generuj_predmety.py --dnd5e ../dnd5e # předměty, vybavení a kouzelné předměty
python3 tools/generuj_rasy.py                     # rasy
python3 tools/generuj_povolani.py                 # povolání a obory
python3 tools/generuj_zazemi.py                   # zázemí a odbornosti
python3 tools/kontrola.py                        # strukturní kontrola
npm install && npm run build                     # LevelDB kompendia (Foundry CLI)
```

GitHub Action `.github/workflows/release.yml` při vydání vše vygeneruje, sestaví a přiloží `module.json` + `jeskyne-a-draci.zip`.

### Přidání nebo úprava kouzla

- Seznam kouzel JaD je v `data/jad-kouzla.yml` (vznikl z uložené stránky kapitoly 10 – Magie pomocí `tools/parsuj_magii.py` a spárováním se SRD podle mechanik).
- Původní kouzla JaD mají mechaniku v `data/vlastni-kouzla.yml` (formát v `tools/vlastni.py`).
- Popisy piš vlastními slovy – licence JaD zakazuje kopírovat bloky textu z knihy.

### Rasy, povolání, zázemí a předměty

| Data | Generátor | Kompendium |
|---|---|---|
| `data/rasy.yml` | `tools/generuj_rasy.py` | JaD – Rasy |
| `data/povolani/*.yml` | `tools/generuj_povolani.py` | JaD – Povolání a obory |
| `data/zazemi.yml`, `data/vybaveni-startovni.yml` | `tools/generuj_zazemi.py` | JaD – Zázemí a odbornosti |
| `data/predmety.yml`, `data/kouzelne-predmety.yml`, `data/preklady-predmetu.yml` | `tools/generuj_predmety.py` | JaD – Předměty a vybavení |

Pořadí spouštění: kouzla → předměty → rasy → povolání → zázemí (povolání a zázemí odkazují na předměty).

### Deník JaD a nosnost

- `scripts/denik.mjs` – Deník JaD (podtřída deníku postavy dnd5e), šablony v `templates/`, vzhled v `styles/jeskyne-a-draci.css`.
- `scripts/nosnost.mjs` – nosnost na Řádky (nahrazuje výpočet naložení v dnd5e).
- `scripts/meritko.mjs` – pravítko tokenů, které převádí rychlost postavy na jednotky mřížky scény.
- `tools/kontrola-sablon.mjs` – v GitHub Action vykreslí šablony a otestuje výpočet Řádků.

### Pravidla pro texty

Licence JaD pro třetí strany zakazuje kopírovat bloky textu a ilustrace z oficiálních produktů. Všechny popisy piš vlastními slovy a odkazuj na plné znění v [SRD JaD](https://dnd5esrd.d20.cz/jeskyne-a-draci/).
