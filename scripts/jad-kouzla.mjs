/**
 * Jeskyně a draci – Kouzla (komunitní tvorba)
 * Modul pro Foundry VTT v14 a systém dnd5e.
 *
 * - registruje seznamy kouzel povolání JaD do registru dnd5e,
 * - pokud kompendium chybí nebo je prázdné (modul nainstalovaný bez sestavených LevelDB balíků),
 *   naimportuje kouzla a seznamy z přiložených JSON dat,
 * - ohlásí, zda je aktivní volitelná vrstva Midi-QOL.
 */

const MODUL = "jad-kouzla";
const DATA = `modules/${MODUL}/data/kompendium`;
const SEZNAMY = "sC0HvqYsKpj7yC0a";
const STRANKY = {
  bard: "KKH9sqrVZ0IQYYTe", cleric: "8vVo9MFpiq6v425W", druid: "tEqiIu1FDMmKUThK", paladin: "HTgJrYjdwPclj1UH",
  ranger: "1C5FCHQ0u9ZKLKBy", sorcerer: "gnZwvoKGPSsf5ZbF", warlock: "nSt6F8YUimKJ7nDx", wizard: "erksSX0HbLIY3IJu"
};

const t = (klic, data) => data ? game.i18n.format(`JAD.${klic}`, data) : game.i18n.localize(`JAD.${klic}`);

Hooks.once("init", () => {
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
  game.settings.register(MODUL, "importovanaVerze", { scope: "world", config: false, type: String, default: "" });
});

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
    if ( game.modules.get("midi-qol")?.active ) ui.notifications.info(t("Midi.Aktivni"));
  }

  if ( game.settings.get(MODUL, "registrovatSeznamy") ) await registrovatSeznamy();
});

/** Zaregistruje stránky se seznamy kouzel povolání do registru dnd5e. */
async function registrovatSeznamy() {
  const registr = globalThis.dnd5e?.registry?.spellLists;
  if ( !registr?.register ) return console.warn(`${MODUL} | Registr seznamů kouzel dnd5e nenalezen.`);
  for ( const id of Object.values(STRANKY) ) {
    const uuid = `Compendium.${MODUL}.seznamy-kouzel.JournalEntry.${SEZNAMY}.JournalEntryPage.${id}`;
    try {
      await registr.register(uuid);
    } catch(err) {
      console.warn(`${MODUL} | Seznam ${uuid} nelze zaregistrovat`, err);
    }
  }
}

/**
 * Pokud jsou kompendia prázdná (nebo je vynuceno), naplní je z JSON dat modulu.
 * @param {boolean} vynutit  Smazat stávající obsah a importovat znovu.
 */
async function zajistitKompendia(vynutit) {
  const verze = game.modules.get(MODUL).version;
  const kouzla = game.packs.get(`${MODUL}.kouzla`);
  const seznamy = game.packs.get(`${MODUL}.seznamy-kouzel`);
  if ( !kouzla || !seznamy ) return;

  const prazdna = (await kouzla.getIndex()).size === 0;
  if ( !vynutit && !prazdna ) return;

  ui.notifications.info(t("Import.Zacatek"));
  const [dk, ds] = await Promise.all([
    fetch(`${DATA}/kouzla.json`).then(r => r.json()),
    fetch(`${DATA}/seznamy-kouzel.json`).then(r => r.json())
  ]);

  await naplnit(kouzla, async pack => {
    await Folder.implementation.createDocuments(dk.folders, { pack: pack.collection, keepId: true });
    await Item.implementation.createDocuments(dk.items, { pack: pack.collection, keepId: true });
  }, vynutit);
  await naplnit(seznamy, async pack => {
    await JournalEntry.implementation.createDocuments(ds.journal, { pack: pack.collection, keepId: true });
  }, vynutit);

  await game.settings.set(MODUL, "importovanaVerze", verze);
  ui.notifications.info(t("Import.Hotovo", { pocet: dk.items.length }));
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

/** Kouzla mají vzdálenosti v metrech (JaD: 1 pole = 1,5 m). Upozorní GM, pokud svět používá stopy. */
function upozornitNaJednotky() {
  if ( !game.settings.get(MODUL, "upozorneniJednotky") ) return;
  let metricke = false;
  try { metricke = game.settings.get("dnd5e", "metricLengthUnits"); } catch(err) { /* starší dnd5e */ }
  if ( !metricke ) ui.notifications.warn(t("Jednotky.Upozorneni"), { permanent: false });
}
