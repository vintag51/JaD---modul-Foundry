# Jeskyně a draci – Kouzla (Foundry VTT)

Modul pro **Foundry VTT v14** a systém **dnd5e** (5.3+ / 6.x), který přidává kompendium automatizovaných kouzel kompatibilních s hrou **Jeskyně a draci** a seznamy kouzel jednotlivých povolání.

![JaD – komunitní tvorba](assets/logo-jad-komunitni.jpg)

> Jeskyně a draci – Kouzla je nezávislá tvorba autora vintag51 a není spojena s autory ani vydavatelem hry Jeskyně a Draci (dostupné na [imago.cz](https://imago.cz)). Publikováno pod Licencí JaD pro třetí strany.

## Co modul obsahuje (verze 0.1.0)

| Část | Stav |
|---|---|
| 319 kouzel SRD 5.1 s automatizací dnd5e (útoky, záchrany, zranění, léčení, škálování dle stupně i úrovně, efekty, přivolání, šablony oblastí) | hotovo |
| České názvy, stupně, materiály, názvy aktivit a efektů, podmínky | hotovo – 38 názvů ověřeno proti SRD JaD, ostatní pracovní |
| Vlastní krátká shrnutí + odkaz na plné znění v SRD JaD | hotovo |
| Vzdálenosti v metrech podle JaD (5 stop = 1,5 m) | hotovo (lze přepnout na stopy) |
| Seznamy kouzel 8 povolání zaregistrované do dnd5e (výběr kouzel při postupu) | hotovo pro kouzla SRD |
| Volitelná vrstva Midi-QOL + DAE (opakované záchrany a zranění na konci tahu – OverTime) | hotovo pro 12 kouzel |
| Kouzla z knihy JaD mimo SRD 5.1 a původní kouzla JaD | připravený formát, čeká na data z PDF |
| Rasy, povolání, předměty | další fáze |

## Instalace

1. Do `assets/` vlož **logo komunitní tvorby JaD** jako `logo-jad-komunitni.jpg` (stáhni z <https://www.mytago.cz/blog/jad-komunitni-tvorba>; licence vyžaduje jeho viditelné použití v nezměněné podobě, barvu lze upravit).
2. Zkopíruj složku `jad-kouzla` do `Data/modules/` (nebo instaluj přes manifest po zveřejnění na GitHubu).
3. Ve světě s dnd5e zapni modul. Při prvním spuštění GM modul sám naplní kompendia z `data/kompendium/*.json` (pokud nejsou předem sestavená).
4. Doporučeno: v nastavení dnd5e zapni **metrické jednotky délky** a scény nastav na **1,5 m na pole**.

Kompendia najdeš ve složce **Jeskyně a draci**: *JaD – Kouzla* a *JaD – Seznamy kouzel povolání*.

Ruční reimport (např. po aktualizaci dat): v konzoli `game.modules.get("jad-kouzla").api.importovat()`.

## Automatizace

- **Bez dalších modulů**: vše, co umí dnd5e nativně – tlačítka útoku, záchrany, zranění a léčení v chatu, automatické škálování podle stupně slotu a úrovně postavy, šablony oblastí, aplikace efektů na cíle, přivolání tvorů, očarování zbraní.
- **S Midi-QOL + DAE**: navíc plně automatický průběh (zásah → záchrana → aplikace zranění) a u vybraných kouzel opakované záchrany / zranění na konci tahu (`flags.midi-qol.OverTime`, seznam v `data/midi-overtime.yml`). Bez Midi-QOL tyto příznaky nic nedělají.

## Vývoj – jak se data generují

```
dnd5e (SRD 5.1, automatizace)  ─┐
data/nazvy-kouzel.yml           │
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
python3 tools/generuj.py --dnd5e ../dnd5e        # --jednotky ft pro stopy
python3 tools/kontrola.py                        # strukturní kontrola
npm install && npm run build                     # LevelDB kompendia (Foundry CLI)
```

GitHub Action `.github/workflows/release.yml` při vydání vše vygeneruje, sestaví a přiloží `module.json` + `jad-kouzla.zip`.

### Přidání kouzla mimo SRD

Zápis do `data/vlastni-kouzla.yml` (formát v `tools/vlastni.py`), pak znovu `generuj.py`. Popis piš vlastními slovy – licence JaD zakazuje kopírovat bloky textu z knihy.

### Ověření názvů

V `data/nazvy-kouzel.yml` má každé kouzlo `overeno: true/false`. Neověřené mají v popisu poznámku „Pracovní název“. Po porovnání s knihou stačí název opravit a přepnout na `true`.

## Licence

Viz [LICENSE.md](LICENSE.md). Obsahuje materiál ze SRD 5.1 (CC-BY-4.0) a strukturovaná data systému dnd5e.
