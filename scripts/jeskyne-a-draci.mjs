/**
 * Jeskyně a draci pro Foundry VTT (komunitní tvorba)
 * Modul pro Foundry VTT v14 a systém dnd5e.
 *
 * - registruje seznamy kouzel povolání JaD do registru dnd5e,
 * - pokud kompendium chybí nebo je prázdné (modul nainstalovaný bez sestavených LevelDB balíků),
 *   naimportuje kouzla a seznamy z přiložených JSON dat,
 * - ohlásí, zda je aktivní volitelná vrstva Midi-QOL.
 */

import { NASTROJE, ZAKLADNI } from "./registr-predmetu.mjs";
import { zapnoutNosnost, zajistitRezimNalozeni } from "./nosnost.mjs";
import { registrovatDenik } from "./denik.mjs";

const MODUL = "jeskyne-a-draci";
const DATA = `modules/${MODUL}/data/kompendium`;

/** Kompendia modulu a soubory se záložními daty pro import. */
const BALIKY = [
  { pack: "kouzla", soubor: "kouzla.json" },
  { pack: "seznamy-kouzel", soubor: "seznamy-kouzel.json" },
  { pack: "rasy", soubor: "rasy.json" },
  { pack: "povolani", soubor: "povolani.json" },
  { pack: "zazemi", soubor: "zazemi.json" },
  { pack: "predmety", soubor: "predmety.json" }
];

const t = (klic, data) => data ? game.i18n.format(`JAD.${klic}`, data) : game.i18n.localize(`JAD.${klic}`);

Hooks.once("init", () => {
  registrovatSahy();
  game.settings.register(MODUL, "registrovatSeznamy", {
    name: "JAD.Nastaveni.Seznamy.Nazev",
    hint: "JAD.Nastaveni.Seznamy.Napoveda",
    scope: "world", config: true, type: Boolean, default: true, requiresReload: true
  });
  game.settings.register(MODUL, "upozorneniJednotky", {
    name: "JAD.Nastaveni.Jednotky.Nazev",
    hint: "JAD.Nastaveni.Jednotky.Napoveda",
    scope: "world", config: true, type: Boolean, default: true
  });
  game.settings.register(MODUL, "jmenaMinci", {
    name: "JAD.Nastaveni.Mince.Nazev",
    hint: "JAD.Nastaveni.Mince.Napoveda",
    scope: "world", config: true, type: Boolean, default: true, requiresReload: true
  });
  game.settings.register(MODUL, "importovanaVerze", { scope: "world", config: false, type: String, default: "" });
  game.settings.register(MODUL, "ceskePredmety", {
    name: "JAD.Nastaveni.Predmety.Nazev",
    hint: "JAD.Nastaveni.Predmety.Napoveda",
    scope: "world", config: true, type: Boolean, default: true, requiresReload: true
  });
  game.settings.register(MODUL, "nosnostRadky", {
    name: "JAD.Nastaveni.Radky.Nazev",
    hint: "JAD.Nastaveni.Radky.Napoveda",
    scope: "world", config: true, type: Boolean, default: true, requiresReload: true
  });
  game.settings.register(MODUL, "nosnostZjednodusena", {
    name: "JAD.Nastaveni.Zjednodusena.Nazev",
    hint: "JAD.Nastaveni.Zjednodusena.Napoveda",
    scope: "world", config: true, type: Boolean, default: false, requiresReload: true
  });
  registrovatNastroje();
  if ( game.settings.get(MODUL, "jmenaMinci") ) prejmenovatMince();
  if ( game.settings.get(MODUL, "nosnostRadky") && zapnoutNosnost() ) {
    // Zpomalení Těžkou zbrojí bez potřebné Síly platí v JaD jen se zjednodušenou nosností.
    if ( !game.settings.get(MODUL, "nosnostZjednodusena") ) CONFIG.DND5E.armorSpeedReduction = 0;
  }
  registrovatDenik();
  vynutitRychlostRasy();
  if ( game.settings.get(MODUL, "ceskePredmety") ) nahraditZakladniPredmety();
});

/** Pomůcky JaD, které v dnd5e nejsou (Hornické nářadí…), přidá do seznamu nástrojů pro Zdatnosti. */
function registrovatNastroje() {
  const nastroje = CONFIG.DND5E?.tools;
  if ( !nastroje ) return;
  for ( const [klic, data] of Object.entries(NASTROJE) ) nastroje[klic] ??= data;
}

/**
 * Volby „jakákoliv Jednoduchá zbraň“, zbroje, pomůcky a ohniskové předměty (počáteční vybavení, zdatnosti)
 * budou nabízet české předměty z kompendia JaD – Předměty místo anglických předmětů dnd5e.
 */
function nahraditZakladniPredmety() {
  const cfg = CONFIG.DND5E;
  if ( !cfg ) return;
  for ( const klic of ["weaponIds", "armorIds"] ) {
    if ( cfg[klic] ) Object.assign(cfg[klic], ZAKLADNI[klic]);
  }
  for ( const [klic, id] of Object.entries(ZAKLADNI.toolIds) ) {
    const n = cfg.tools?.[klic];
    if ( n && (typeof n === "object") ) n.id = id;
  }
  for ( const [typ, polozky] of Object.entries(ZAKLADNI.focus) ) {
    const f = cfg.focusTypes?.[typ];
    if ( f?.itemIds ) Object.assign(f.itemIds, polozky);
  }
}

/**
 * Rasy JaD mají rychlost a vidění ve tmě v sázích. dnd5e je ale použije jen tam, kde postava nemá vlastní
 * hodnotu – nová postava má často výchozích 30 stop, a pak by se rychlost v sázích ztratila (30 „sáhů“).
 * U postav s rasou JaD proto hodnoty rasy (včetně jednotek) vždy přednostně použijeme.
 */
function vynutitRychlostRasy() {
  const AF = globalThis.dnd5e?.dataModels?.actor?.AttributesFields;
  if ( !AF?.prepareRace ) return;
  const puvodni = AF.prepareRace;
  AF.prepareRace = function(race, options = {}) {
    const jad = !!race?.flags?.[MODUL]?.rasa;
    return puvodni.call(this, race, jad ? { ...options, force: true } : options);
  };
}

/** Zlaťáky, stříbrňáky a měďáky místo gp/sp/cp (převodní poměry zůstávají). */
function prejmenovatMince() {
  const mince = CONFIG.DND5E?.currencies;
  if ( !mince ) return;
  for ( const [klic, jad] of [["gp", "Zl"], ["sp", "St"], ["cp", "Md"]] ) {
    if ( !mince[klic] ) continue;
    mince[klic].label = `JAD.Mince.${jad}.Nazev`;
    mince[klic].abbreviation = `JAD.Mince.${jad}.Zkratka`;
  }
}

Hooks.once("ready", async () => {
  const modul = game.modules.get(MODUL);
  modul.api = { importovat: (vynutit = true) => zajistitKompendia(vynutit) };

  if ( game.users.activeGM?.isSelf ) {
    try {
      await zajistitKompendia(false);
    } catch(err) {
      console.error(`${MODUL} | Import kompendií selhal`, err);
      ui.notifications.error(t("Import.Chyba"));
    }
    upozornitNaJednotky();
    if ( game.settings.get(MODUL, "nosnostRadky") ) await zajistitRezimNalozeni();
    if ( game.modules.get("midi-qol")?.active ) ui.notifications.info(t("Midi.Aktivni"));
  }

  if ( game.settings.get(MODUL, "registrovatSeznamy") ) await registrovatSeznamy();
});

/** Zaregistruje stránky se seznamy kouzel povolání do registru dnd5e. */
async function registrovatSeznamy() {
  const registr = globalThis.dnd5e?.registry?.spellLists;
  if ( !registr?.register ) return console.warn(`${MODUL} | Registr seznamů kouzel dnd5e nenalezen.`);
  let uuidy = [];
  try {
    uuidy = (await fetch(`${DATA}/registr.json`).then(r => r.json())).seznamyKouzel ?? [];
  } catch(err) {
    return console.warn(`${MODUL} | Soubor registr.json nelze načíst`, err);
  }
  for ( const uuid of uuidy ) {
    try {
      await registr.register(uuid);
    } catch(err) {
      console.warn(`${MODUL} | Seznam ${uuid} nelze zaregistrovat`, err);
    }
  }
}

/**
 * Pokud je některé kompendium prázdné (nebo je vynuceno), naplní ho z JSON dat modulu.
 * @param {boolean} vynutit  Smazat stávající obsah a importovat znovu.
 */
async function zajistitKompendia(vynutit) {
  let celkem = 0;
  let zacato = false;
  for ( const { pack: nazev, soubor } of BALIKY ) {
    const pack = game.packs.get(`${MODUL}.${nazev}`);
    if ( !pack ) continue;
    if ( !vynutit && (await pack.getIndex()).size > 0 ) continue;
    if ( !zacato ) {
      ui.notifications.info(t("Import.Zacatek"));
      zacato = true;
    }
    const data = await fetch(`${DATA}/${soubor}`).then(r => r.json());
    await naplnit(pack, async p => {
      if ( data.folders?.length ) await Folder.implementation.createDocuments(data.folders, { pack: p.collection, keepId: true });
      if ( data.items?.length ) await Item.implementation.createDocuments(data.items, { pack: p.collection, keepId: true });
      if ( data.journal?.length ) await JournalEntry.implementation.createDocuments(data.journal, { pack: p.collection, keepId: true });
    }, vynutit);
    celkem += (data.items?.length ?? 0) + (data.journal?.length ?? 0);
  }
  if ( zacato ) {
    await game.settings.set(MODUL, "importovanaVerze", game.modules.get(MODUL).version);
    ui.notifications.info(t("Import.Hotovo", { pocet: celkem }));
  }
}

async function naplnit(pack, vytvorit, vynutit) {
  const zamceno = pack.locked;
  if ( zamceno ) await pack.configure({ locked: false });
  try {
    if ( vynutit ) {
      const index = await pack.getIndex();
      const cls = pack.documentClass;
      if ( index.size ) await cls.deleteDocuments(Array.from(index.keys()), { pack: pack.collection });
      const slozky = pack.folders.map(f => f.id);
      if ( slozky.length ) await Folder.implementation.deleteDocuments(slozky, { pack: pack.collection });
    }
    await vytvorit(pack);
  } finally {
    if ( zamceno ) await pack.configure({ locked: true });
  }
}

/**
 * Jednotka délky JaD: 1 sáh = 5 stop = 1 pole. Přidá ji do konfigurace dnd5e, aby se dosahy a oblasti kouzel
 * zobrazovaly v sázích a šablony se správně přepočítaly na jednotky scény.
 */
function registrovatSahy() {
  const cfg = CONFIG.DND5E;
  if ( !cfg?.movementUnits || cfg.movementUnits.sah ) return;
  cfg.movementUnits.sah = {
    label: "JAD.Jednotky.Sah.Nazev",
    abbreviation: "JAD.Jednotky.Sah.Zkratka",
    template: "JAD.Jednotky.Sah.Sablona",
    counted: "JAD.Jednotky.Sah.Pocet",
    conversion: 5,
    type: "imperial",
    travelResolution: "round"
  };
  if ( cfg.distanceUnits && !Object.isFrozen(cfg.distanceUnits) ) cfg.distanceUnits.sah = "JAD.Jednotky.Sah.Nazev";
}

/** Upozorní GM, pokud aktuální scéna nemá mřížku 1 pole = 5 stop / 1 sáh (doporučené nastavení pro JaD). */
function upozornitNaJednotky() {
  if ( !game.settings.get(MODUL, "upozorneniJednotky") ) return;
  const grid = canvas?.scene?.grid;
  if ( !grid ) return;
  const ok = (grid.units === "sah" && grid.distance === 1) || (grid.units === "ft" && grid.distance === 5)
    || (grid.units === "m" && grid.distance === 1.5);
  if ( !ok ) ui.notifications.warn(t("Jednotky.Upozorneni"));
}
