/**
 * Kontrola Deníku JaD bez Foundry: přeloží šablony Handlebars a vykreslí je se vzorovými daty
 * a otestuje výpočet Řádků (nosnost) na zkušební postavě. Spouští se v GitHub Action.
 */
import fs from "node:fs";
const Handlebars = (await import("handlebars").catch(() => null))?.default;

let chyby = 0;
const chyba = (...m) => { chyby++; console.error("CHYBA:", ...m); };

// ----------------------------------------------------------------- šablony
const vzor = {
  rollableClass: "rollable",
  tab: { cssClass: "active", id: "denik", group: "primary" },
  jad: {
    prof: "+2", inspirace: false, iniciativa: "+3", oc: 15, editovatelne: true,
    vlastnosti: [{ key: "str", nazev: "Síla", hodnota: 14, oprava: "+2", zachrana: "+4", zachranaZdatnost: true }],
    skupiny: [{ key: "str", nazev: "Síla", dovednosti: [{ key: "ath", nazev: "Atletika", celkem: "+4", zdatnost: "plna" }] }],
    pomucky: [], zbroj: { lehke: true }, zbraneZdatnost: { jednoduche: true },
    pasivni: [{ nazev: "Vnímání", hodnota: 12 }],
    rychlost: { jednotky: "sáh.", aktualni: 6, stupne: [{ nazev: "Lehké", hodnota: 6, aktivni: true }] },
    kouzla: { zobrazit: true, vlastnost: "Inteligence", utok: "+5", so: 13,
      pozice: [{ stupen: 1, value: 2, max: 2, cesta: "system.spells.spell1.value" }],
      pakt: { value: 1, max: 1, stupen: 1 }, truhla: { id: "x", value: 1, max: 2 } },
    zbrane: [{ id: "a", nazev: "Dýka", img: "x.webp", bonus: "+4", zasah: "1d4 + 2", typ: "Bodný", dosah: "4/12 sáhů" }],
    vybava: [{ id: "b", nazev: "Batoh", img: "x.webp", pocet: 1, radky: "0", rucne: "", vKontejneru: "", jeKontejner: true, odlozeno: false, vlastniOdlozeni: false }],
    schopnosti: [{ id: "c", nazev: "Druhý dech", img: "x.webp", pouziti: "1/1" }],
    nalozeni: { radky: 7, maximum: 17, lehke: 7, stredni: 12, tezke: 17, batoh: true, stupen: "Lehké", tridaStupne: "lehke", zjednodusena: false },
    mince: [{ key: "gp", cesta: "system.currency.gp", hodnota: 10, nazev: "zl" }],
    jazyky: "obecná řeč", hp: { value: 10, max: 12, temp: "" }, hd: { value: 1, max: 1 },
    smrt: { uspechy: [true, false, false], neuspechy: [false, false, false] }, poznamky: "",
    // vzhled
    vek: "30", plet: "", vyska: "", vlasy: "", vaha: "", oci: "", postava: "", obleceni: "", dojem: "", tituly: "",
    vztahy: [{ i: 0, kdo: "Bran", vztah: "přítel" }]
  }
};
if ( !Handlebars ) {
  if ( process.env.CI ) chyba("balíček handlebars chybí");
  else console.warn("Handlebars není nainstalovaný – šablony přeskočeny.");
}
for ( const soubor of Handlebars ? fs.readdirSync("templates").filter(f => f.endsWith(".hbs")) : [] ) {
  try {
    const html = Handlebars.compile(fs.readFileSync(`templates/${soubor}`, "utf8"), { strict: false })(vzor);
    if ( !html.includes("jad-tab") ) chyba(soubor, "výstup neobsahuje záložku");
    if ( /\{\{|\}\}/.test(html) ) chyba(soubor, "nevykreslené značky Handlebars");
    if ( html.includes("flags..") ) chyba(soubor, "prázdná cesta k příznaku");
    console.log(`Šablona ${soubor}: OK (${html.length} znaků)`);
  } catch(err) {
    chyba(soubor, err.message);
  }
}

// ----------------------------------------------------------------- nosnost
globalThis.Math.clamp ??= (v, a, b) => Math.min(Math.max(v, a), b);
globalThis.CONFIG = { DND5E: { actorSizes: { tiny: {}, sm: {}, med: {}, lg: {}, huge: {}, grg: {} } } };
const nastaveni = { nosnostZjednodusena: false };
globalThis.game = { settings: { get: (m, k) => nastaveni[k] } };
const { spocitatNalozeni, formatRadky } = await import("../scripts/nosnost.mjs");

const predmet = (id, type, system, flags = {}) => ({ id, type, system: { quantity: 1, weight: { value: 0 }, properties: new Set(), ...system }, flags });
const items = [
  predmet("batoh", "container", { identifier: "backpack", weight: { value: 5 } }),
  predmet("mec", "weapon", { weight: { value: 3 }, type: { value: "martialM", baseItem: "longsword" } }),
  predmet("dyka", "weapon", { quantity: 2, weight: { value: 1 }, properties: new Set(["lgt", "fin", "thr"]) }, { "jeskyne-a-draci": { radky: 0.3333 } }),
  predmet("kruz", "equipment", { weight: { value: 55 }, type: { value: "heavy" } }),
  predmet("sipy", "consumable", { quantity: 20, weight: { value: 0.05 }, type: { value: "ammo" }, container: "batoh" }),
  predmet("stan", "loot", { weight: { value: 20 } }, { "jeskyne-a-draci": { radky: 3 } }),
  predmet("lano", "loot", { weight: { value: 10 }, container: "batoh" })
];
const actor = { items: { get: id => items.find(i => i.id === id), [Symbol.iterator]: () => items[Symbol.iterator]() },
  flags: {}, system: { abilities: { str: { mod: 2 } }, traits: { size: "med" }, currency: { gp: 50 } } };
for ( const i of items ) i.actor = actor;

const n = spocitatNalozeni(actor);
// meč 1 + dýky ⅔ + Těžká zbroj 3 + šípy 1 + stan 3 + lano 1 + mince ⅓ = 10 → zaokrouhleno 10
const ocekavane = { radky: 10, lehke: 7, stredni: 12, tezke: 17, maximum: 17, stupen: "stredni", batoh: true };
for ( const [k, v] of Object.entries(ocekavane) ) if ( n[k] !== v ) chyba(`nosnost.${k} = ${n[k]}, čekáno ${v}`);
items[0].flags = { "jeskyne-a-draci": { odlozeno: true } };
const bez = spocitatNalozeni(actor);
if ( bez.maximum !== 12 || bez.radky !== 8 ) chyba(`odložený Batoh: ${bez.radky}/${bez.maximum}, čekáno 8/12`);
if ( formatRadky(2 + 1 / 3) !== "2⅓" || formatRadky(2 / 3) !== "⅔" ) chyba("formatRadky");
console.log(`Nosnost: ${n.radky}/${n.maximum} (${n.stupen}), bez Batohu ${bez.radky}/${bez.maximum}`);

if ( chyby ) process.exit(1);
console.log("Kontrola Deníku JaD: OK");
