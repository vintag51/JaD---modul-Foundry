# Jeskyně a draci pro Foundry VTT

Modul pro **Foundry VTT v14** a systém **dnd5e** (5.3+ / 6.x), který přidává kompendium automatizovaných kouzel kompatibilních s hrou **Jeskyně a draci** a seznamy kouzel jednotlivých povolání.

![JaD – komunitní tvorba](assets/logo-jad-komunitni.jpg)

> Jeskyně a draci pro Foundry VTT je nezávislá tvorba autora vintag51 a není spojena s autory ani vydavatelem hry Jeskyně a Draci (dostupné na [imago.cz](https://imago.cz)). Publikováno pod Licencí JaD pro třetí strany.

## Co modul obsahuje (verze 0.2.0)

| Část | Stav |
|---|---|
| **Všech 342 kouzel z kapitoly 10 – Magie** knihy Jeskyně a draci | hotovo |
| – 319 kouzel s automatizací převzatou ze SRD 5.1 v systému dnd5e (útoky, Záchranné hody, Zásahy, léčení, škálování dle Stupně Pozice i Úrovně, efekty, přivolání, šablony oblastí) | hotovo |
| – 23 původních kouzel JaD (Hexenšus, Hněv živlů, Řetězy upoutání, Slídivé oko…) s vlastní automatizací | hotovo |
| Názvy, Stupně, školy a seznamy kouzel 8 povolání přesně podle knihy JaD | hotovo, ověřeno |
| Terminologie JaD (Zásah, Body výdrže, Pozice, Stupeň, SO, Oprava sesílací vlastnosti) | hotovo |
| Vlastní krátká shrnutí + odkaz na plné znění v SRD JaD | hotovo |
| Vzdálenosti v **sázích** (1 sáh = 1 pole = 5 stop) – modul přidává jednotku „sáh“ do dnd5e | hotovo |
| Volitelná vrstva Midi-QOL + DAE (opakované Záchranné hody a zásahy na konci tahu) | 13 kouzel |
| **14 hratelných ras a rodů** (Člověk s lidskými rody a variantami, 4 elfí a 4 trpasličí rody, Půlčík, Půlork, Gnóm, Drakorozený s 10 dračími původy, Tiefling) s automatickým postupem: vlastnosti, velikost, rychlost a vidění ve tmě v sázích, jazyky, zdatnosti, odolnosti, vrozená kouzla a rasové schopnosti | hotovo |
| Povolání a obory (včetně Alchymisty a Lovce netvorů), předměty | další fáze, ve stejném modulu |

## Instalace

1. Do `assets/` vlož **logo komunitní tvorby JaD** jako `logo-jad-komunitni.jpg` (stáhni z <https://www.mytago.cz/blog/jad-komunitni-tvorba>; licence vyžaduje jeho viditelné použití v nezměněné podobě, barvu lze upravit).
2. Zkopíruj složku `jeskyne-a-draci` do `Data/modules/` (nebo instaluj přes manifest po zveřejnění na GitHubu).
3. Ve světě s dnd5e zapni modul. Při prvním spuštění GM modul sám naplní kompendia z `data/kompendium/*.json` (pokud nejsou předem sestavená).
4. Mřížku scén nastav na **1 sáh** (nebo 5 stop / 1,5 m) na pole – šablony kouzel se přepočítají automaticky.

Kompendia najdeš ve složce **Jeskyně a draci**: *JaD – Kouzla* a *JaD – Seznamy kouzel povolání*.

Ruční reimport (např. po aktualizaci dat): v konzoli `game.modules.get("jeskyne-a-draci").api.importovat()`.

## Automatizace

- **Bez dalších modulů**: vše, co umí dnd5e nativně – tlačítka útoku, záchrany, zranění a léčení v chatu, automatické škálování podle stupně slotu a úrovně postavy, šablony oblastí, aplikace efektů na cíle, přivolání tvorů, očarování zbraní.
- **S Midi-QOL + DAE**: navíc plně automatický průběh (zásah → záchrana → aplikace zranění) a u vybraných kouzel opakované záchrany / zranění na konci tahu (`flags.midi-qol.OverTime`, seznam v `data/midi-overtime.yml`). Bez Midi-QOL tyto příznaky nic nedělají.

## Vývoj – jak se data generují

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
python3 tools/generuj_rasy.py                     # rasy
python3 tools/kontrola.py                        # strukturní kontrola
npm install && npm run build                     # LevelDB kompendia (Foundry CLI)
```

GitHub Action `.github/workflows/release.yml` při vydání vše vygeneruje, sestaví a přiloží `module.json` + `jeskyne-a-draci.zip`.

### Přidání nebo úprava kouzla

- Seznam kouzel JaD je v `data/jad-kouzla.yml` (vznikl z uložené stránky kapitoly 10 – Magie pomocí `tools/parsuj_magii.py` a spárováním se SRD podle mechanik).
- Původní kouzla JaD mají mechaniku v `data/vlastni-kouzla.yml` (formát v `tools/vlastni.py`).
- Popisy piš vlastními slovy – licence JaD zakazuje kopírovat bloky textu z knihy.

## Licence

Viz [LICENSE.md](LICENSE.md). Obsahuje materiál ze SRD 5.1 (CC-BY-4.0) a strukturovaná data systému dnd5e.
