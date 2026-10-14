# Jeskyně a draci pro Foundry VTT

Neoficiální komunitní modul, který do **Foundry VTT** se systémem **D&D 5e (dnd5e)** přidává obsah české hry **Jeskyně a draci** (JaD) – kouzla, rasy, povolání, zázemí, předměty a deník postavy podle karty JaD. Všechno česky, s terminologií JaD a vzdálenostmi v sázích.

![JaD – komunitní tvorba](assets/logo-jad-komunitni.jpg)

> Jeskyně a draci pro Foundry VTT je nezávislá tvorba autora vintag51 a není spojena s autory ani vydavatelem hry Jeskyně a Draci (dostupné na [imago.cz](https://imago.cz)). Publikováno pod Licencí JaD pro třetí strany.

> **Stav: testovací verze.** Modul se aktivně ladí ve hře. Pokud narazíš na chybu, [založ issue](https://github.com/vintag51/JaD---modul-Foundry/issues) – nejlépe se screenshotem a popisem, co jsi dělal.

## Co v modulu najdeš

- **Kouzla** – všech 342 kouzel ze seznamu JaD včetně 23 původních kouzel JaD. Útoky, záchrany, zásahy, léčení, šablony oblastí a efekty fungují automaticky. Seznamy kouzel povolání se objeví ve výběru kouzel při postupu na Úroveň.
- **Rasy** – 14 ras a rodů (lidské rody, elfové, trpaslíci, půlčík, půlork, gnóm, drakorozený, tiefling) s vlastnostmi, rychlostí a viděním ve tmě v sázích, jazyky a rasovými schopnostmi.
- **Povolání** – všech 11 povolání JaD včetně **Alchymisty** a **Lovce netvorů**, 41 oborů a postup až do 20. Úrovně se všemi schopnostmi.
- **Zázemí a odbornosti** – 16 zázemí a 10 odborností.
- **Předměty** – zbraně, zbroje, výbava, pomůcky, balíčky vybavení a přes 300 kouzelných předmětů. Ceny ve zlaťácích, stříbrňácích a měďácích.
- **Počáteční vybavení** – při tvorbě postavy si vybereš výbavu podle knihy, nebo si vezmeš zlaťáky.
- **Deník JaD** – volitelný deník postavy s rozložením podle karty postavy JaD: vlastnosti a dovednosti, záchrany, OČ, rychlost dle naložení, zbraně, kouzla a pozice, výbava v Řádcích, schopnosti, vzhled a vztahy.
- **Nosnost na Řádky** – naložení se počítá podle JaD (Lehké, Střední, Těžké, Batoh) a automaticky snižuje rychlost.

Kouzla a schopnosti mají krátké popisy vlastními slovy s odkazem na plné znění v [SRD Jeskyní a draků](https://dnd5esrd.d20.cz/jeskyne-a-draci/).

## Co potřebuješ

- **Foundry VTT** verze 14
- herní systém **D&D 5e (dnd5e)** verze 5.3 nebo novější
- doporučené (nepovinné): **Midi-QOL** a **DAE** pro plně automatické vyhodnocování

Modul hraje na pravidlech D&D 5e ve Foundry a přidává do nich obsah a terminologii JaD. Některá pravidla JaD, která Foundry neumí (třeba Mezidobí), zůstávají na hráčích a PH.

## Instalace

1. Ve Foundry otevři **Doplňkové moduly → Instalovat modul**.
2. Do pole **Adresa manifestu** vlož:
   ```
   https://github.com/vintag51/JaD---modul-Foundry/releases/latest/download/module.json
   ```
3. Klikni na **Instalovat**.
4. Ve světě se systémem dnd5e modul zapni (**Nastavení hry → Spravovat moduly**).

Ruční instalace: stáhni `jeskyne-a-draci.zip` z [Releases](https://github.com/vintag51/JaD---modul-Foundry/releases) a rozbal ho do složky `Data/modules/` tak, aby vznikla složka `Data/modules/jeskyne-a-draci`.

## První kroky

1. **Kompendia** najdeš na kartě Kompendia ve složce **Jeskyně a draci**: Kouzla, Rasy, Povolání a obory, Zázemí a odbornosti, Předměty a vybavení, Seznamy kouzel povolání.
2. **Tvorba postavy**: přetáhni na postavu rasu, povolání a zázemí z kompendií – volby (dovednosti, jazyky, vybavení…) se nabídnou samy.
3. **Deník JaD**: v okně postavy klikni v záhlaví na nastavení deníku a vyber **Deník JaD**. Pro všechny postavy ho nastavíš v **Nastavení hry → Výchozí deníky**.
4. **Mřížka scén**: scény mají mít **1 pole = 1 sáh** (jednotka „sáh“). Nové scény to dostanou samy, u starších modul převod nabídne. Pak měření pohybu tokenů po mapě i šablony kouzel odpovídají rychlosti postav v sázích.

## Nastavení modulu

| Nastavení | Co dělá |
|---|---|
| Nosnost na Řádky (JaD) | Naložení podle Řádků místo liber; Střední −1 sáh, Těžké −3 sáhy |
| Zjednodušená nosnost (JaD) | Bez stupňů naložení: unese 15 + Oprava síly Řádků, víc ne |
| Mince JaD | Zlaťáky, stříbrňáky a měďáky místo gp/sp/cp |
| České základní předměty | Volby „jakákoliv zbraň/zbroj/pomůcka“ nabízejí české předměty JaD |
| Registrovat seznamy kouzel | Seznamy kouzel povolání JaD ve výběru kouzel |
| Nové scény v sázích | Nové scény dostanou mřížku 1 pole = 1 sáh |
| Kontrolovat mřížku scény | Při otevření scény mimo sáhy nabídne PH převod na 1 sáh na pole |

## Deník JaD v kostce

- **Hody**: kliknutím na vlastnost, dovednost, záchranu, iniciativu nebo smrt se hází; kliknutím na zbraň, kouzlo nebo schopnost je použiješ.
- **Úpravy**: po odemknutí zámečku upravíš hodnoty vlastností; hvězdičky zdatností přepínáš kliknutím.
- **Výbava**: počet kusů i Řádky jde přepsat přímo v Deníku; Batoh se dá jedním kliknutím odložit (nepočítá se pak ani jeho obsah).
- **Kouzla**: záložka Kouzla má rozložení podle karty – sesilatelská povolání, pozice kouzel, připravení kouzel kroužkem P.
- Ostatní záložky (Inventář, Schopnosti, Efekty…) zůstávají ze systému dnd5e v barvách JaD.

## Automatizace

- **Bez dalších modulů** funguje vše, co umí dnd5e: útoky, záchrany, zásahy a léčení v chatu, škálování podle Stupně pozice a Úrovně, šablony oblastí, efekty, přivolání.
- **S Midi-QOL a DAE** navíc plně automatický průběh útoku a u vybraných kouzel opakované záchrany a zásahy na konci tahu.

## Časté otázky

**Neukazují se mi kompendia / jsou prázdná.** Při prvním spuštění je PH naplní automaticky z dat modulu. Ruční obnova: v konzoli (F12) `game.modules.get("jeskyne-a-draci").api.importovat()`.

**Proč jsou některé nápisy anglicky?** Části rozhraní pocházejí ze systému dnd5e a jeho českého překladu, ne z tohoto modulu.

**Jsou tu celé texty z knihy?** Ne. Licence JaD kopírování textů nedovoluje, proto jsou popisy krátká vlastní shrnutí s odkazem na SRD JaD. Knihu doporučujeme mít po ruce.

## Chyby a nápady

Hlas chyby a nápady přes [GitHub Issues](https://github.com/vintag51/JaD---modul-Foundry/issues). Pomůže verze modulu, Foundry a dnd5e, screenshot a případná chybová hláška z konzole (F12).

Chceš modul upravovat nebo rozšiřovat? Postup najdeš ve [VYVOJ.md](VYVOJ.md).

## Licence

Viz [LICENSE.md](LICENSE.md). Modul obsahuje materiál ze SRD 5.1 (CC-BY-4.0) a strukturovaná data systému dnd5e. Obsah Jeskyní a draků je použit podle Licence JaD pro třetí strany.
