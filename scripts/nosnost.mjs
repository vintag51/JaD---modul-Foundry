/**
 * Nosnost podle Řádků (Jeskyně a draci, 6. kapitola).
 *
 * - Každý fyzický předmět zabírá Řádky: Drobný ⅓, Běžný 1, Velký 2–3 (lze ručně přepsat příznakem
 *   flags.jeskyne-a-draci.radky na předmětu).
 * - Lehké naložení do 5 + Oprava síly, Střední do 10 + Oprava síly, s Batohem Těžké do 15 + Oprava síly.
 * - Střední naložení: Rychlost −1 sáh, Těžké: −3 sáhy, nad maximum: Rychlost nejvýš 1 sáh.
 * - Velikost tvora násobí nosnost (Drobný ½, Velký ×2, Obrovský ×4, Gigantický ×8).
 *
 * Výpočet nahrazuje AttributesFields.prepareEncumbrance systému dnd5e, takže s ním pracuje
 * standardní deník i Deník JaD a dnd5e podle něj nastavuje stavy Naložení a snižuje rychlost.
 */

export const MODUL = "jeskyne-a-draci";
export const TRETINA = 1 / 3;

/** Násobitel nosnosti podle velikosti. */
const VELIKOST = { tiny: 0.5, sm: 1, med: 1, lg: 2, huge: 4, grg: 8 };

/** Identifikátory předmětů, které fungují jako Batoh (zvýší maximální nosnost o 5 Řádků). */
export const BATOHY = new Set([
  "backpack", "burglars-pack", "dungeoneers-pack", "entertainers-pack", "explorers-pack", "priests-pack", "scholars-pack"
]);

/** Je předmět Batoh (nebo balíček vybavení zabalený v batohu)? */
export function jeBatoh(item) {
  return (item.type === "container") && (BATOHY.has(item.system?.identifier) || !!item.flags?.[MODUL]?.batoh);
}

/**
 * Řádky jednoho kusu předmětu podle typu a váhy.
 * @param {Item} item
 * @returns {number}
 */
export function radkyZaKus(item) {
  const s = item.system;
  const vaha = Number(s.weight?.value ?? s.weight ?? 0) || 0;
  const podleVahy = w => (w < 0.5 ? 0.1 : w <= 1.5 ? TRETINA : w <= 12 ? 1 : w <= 30 ? 2 : w <= 60 ? 3 : Math.ceil(w / 20));
  switch ( item.type ) {
    case "weapon": {
      const vl = s.properties ?? new Set();
      if ( vaha <= 0.5 ) return TRETINA;
      if ( s.type?.baseItem === "longbow" || s.type?.baseItem === "shortbow" ) return 1;
      if ( vl.has?.("hvy") ) return 2;
      if ( vl.has?.("lgt") && (vaha <= 1) ) return TRETINA;
      return 1;
    }
    case "equipment": {
      const typ = s.type?.value;
      if ( typ === "light" || typ === "shield" ) return 1;
      if ( typ === "medium" ) return 2;
      if ( typ === "heavy" ) return 3;
      if ( typ === "clothing" && s.equipped ) return 0;
      return podleVahy(vaha);
    }
    case "consumable":
      return vaha < 0.5 ? 0.1 : TRETINA;
    case "tool":
      return vaha <= 1.5 ? TRETINA : podleVahy(vaha);
    case "container":
      if ( jeBatoh(item) ) return 0;
      return podleVahy(vaha);
    default:
      return podleVahy(vaha);
  }
}

/**
 * Řádky předmětu včetně množství (střely: 20 kusů = 1 Řádek).
 * @param {Item} item
 * @returns {number}
 */
export function radkyPredmetu(item) {
  const s = item.system;
  const pocet = Math.max(Number(s.quantity ?? 1) || 0, 0);
  const rucne = item.flags?.[MODUL]?.radky;
  if ( (rucne !== undefined) && (rucne !== null) && (rucne !== "") && Number.isFinite(Number(rucne)) ) {
    return Number(rucne) * pocet;
  }
  if ( (item.type === "consumable") && (s.type?.value === "ammo") ) return Math.ceil(pocet / 20 * 3) / 3;
  return radkyZaKus(item) * pocet;
}

/** Je předmět fyzický (má množství a váhu)? */
function fyzicky(item) {
  return ("quantity" in item.system) && ("weight" in item.system);
}

/** Je předmět odložený (Batoh shozený na zem apod.) – i s obsahem? */
export function odlozeny(item) {
  let i = item;
  for ( let hloubka = 0; i && (hloubka < 10); hloubka++ ) {
    if ( i.flags?.[MODUL]?.odlozeno ) return true;
    i = i.system?.container ? item.actor?.items.get(i.system.container) : null;
  }
  return false;
}

/** Obsah kontejneru, který nic neváží (Pytel beztíže, Šikovná brašna…), se nepočítá. */
function vBeztiznemKontejneru(item) {
  let c = item.system?.container ? item.actor?.items.get(item.system.container) : null;
  for ( let hloubka = 0; c && (hloubka < 10); hloubka++ ) {
    if ( c.system?.properties?.has?.("weightlessContents") ) return true;
    c = c.system?.container ? item.actor?.items.get(c.system.container) : null;
  }
  return false;
}

/**
 * Spočítá naložení postavy v Řádcích.
 * @param {Actor} actor
 * @returns {object}
 */
export function spocitatNalozeni(actor) {
  const sys = actor.system;
  let celkem = 0;
  let batoh = false;
  const polozky = [];
  for ( const item of actor.items ) {
    if ( !fyzicky(item) ) continue;
    if ( odlozeny(item) ) continue;
    if ( vBeztiznemKontejneru(item) ) continue;
    if ( jeBatoh(item) ) batoh = true;
    const r = radkyPredmetu(item);
    celkem += r;
    polozky.push({ item, radky: r });
  }
  // Mince: 100 mincí = Drobný předmět
  const mince = Object.values(sys.currency ?? {}).reduce((a, b) => a + Math.max(Number(b) || 0, 0), 0);
  celkem += Math.ceil(mince / 100) * TRETINA;

  const oprava = sys.abilities?.str?.mod ?? 0;
  const klice = CONFIG.DND5E.actorSizes ? Object.keys(CONFIG.DND5E.actorSizes) : [];
  let velikost = sys.traits?.size ?? "med";
  if ( actor.flags?.dnd5e?.powerfulBuild && klice.length ) {
    const i = klice.indexOf(velikost);
    velikost = klice[Math.min(i + 1, klice.length - 1)] ?? velikost;
  }
  const nasobek = VELIKOST[velikost] ?? 1;
  const meze = z => Math.max(Math.floor((z + oprava) * nasobek), 0);
  const zjednodusena = game.settings.get(MODUL, "nosnostZjednodusena");
  const lehke = zjednodusena ? meze(15) : meze(5);
  const stredni = zjednodusena ? meze(15) : meze(10);
  const tezke = meze(15);
  const maximum = (batoh || zjednodusena) ? tezke : stredni;
  const radky = Math.ceil(celkem - 1e-6);
  let stupen = "lehke";
  if ( radky > maximum ) stupen = "pretizeni";
  else if ( radky > stredni ) stupen = "tezke";
  else if ( radky > lehke ) stupen = "stredni";
  return { radky, presne: celkem, lehke, stredni, tezke, maximum, batoh, stupen, polozky, zjednodusena };
}

/** Zapne výpočet nosnosti podle Řádků (volá se v init). */
export function zapnoutNosnost() {
  const AF = globalThis.dnd5e?.dataModels?.actor?.AttributesFields;
  if ( !AF?.prepareEncumbrance ) {
    console.warn(`${MODUL} | AttributesFields.prepareEncumbrance nenalezeno – nosnost na Řádky není aktivní.`);
    return false;
  }
  const puvodni = AF.prepareEncumbrance;
  AF.prepareEncumbrance = function(rollData, options) {
    if ( !["character", "npc"].includes(this.parent?.type) ) return puvodni.call(this, rollData, options);
    let n;
    try {
      n = spocitatNalozeni(this.parent);
    } catch(err) {
      console.error(`${MODUL} | Výpočet Řádků selhal`, err);
      return puvodni.call(this, rollData, options);
    }
    const e = this.attributes.encumbrance ??= {};
    e.value = n.radky;
    e.thresholds = { encumbered: n.lehke, heavilyEncumbered: n.stredni, maximum: n.maximum };
    e.max = n.maximum;
    e.mod = 1;
    e.stops = {
      encumbered: n.maximum ? Math.clamp(n.lehke * 100 / n.maximum, 0, 100) : 0,
      heavilyEncumbered: n.maximum ? Math.clamp(n.stredni * 100 / n.maximum, 0, 100) : 0
    };
    e.pct = n.maximum ? Math.clamp(n.radky * 100 / n.maximum, 0, 100) : 100;
    e.encumbered = n.radky > n.stredni;
    e.units = "Řádky";
    e.jad = n;
  };

  // Snížení rychlosti v sázích (a ekvivalent ve stopách a metrech)
  const r = CONFIG.DND5E.encumbrance.speedReduction;
  r.encumbered = { ...r.encumbered, sah: 1, ft: 5, m: 1.5 };
  r.heavilyEncumbered = { ...r.heavilyEncumbered, sah: 3, ft: 15, m: 4.5 };
  r.exceedingCarryingCapacity = { ...r.exceedingCarryingCapacity, sah: 1, ft: 5, m: 1.5 };
  return true;
}

/** dnd5e uplatňuje stavy Naložení jen v režimu „variant“ – GM ho při zapnutých Řádcích nastaví. */
export async function zajistitRezimNalozeni() {
  if ( !game.user.isGM ) return;
  const cil = game.settings.get(MODUL, "nosnostZjednodusena") ? "normal" : "variant";
  let rezim;
  try {
    rezim = game.settings.get("dnd5e", "encumbrance");
  } catch(err) {
    return;
  }
  if ( (rezim === cil) || ((cil === "normal") && (rezim === "variant")) ) return;
  await game.settings.set("dnd5e", "encumbrance", cil);
  ui.notifications.info(game.i18n.localize("JAD.Nosnost.RezimNastaven"));
}

/** Zobrazení Řádků (např. 2⅓). */
export function formatRadky(x) {
  const cele = Math.floor(x + 1e-6);
  const zbytek = Math.round((x - cele) * 3);
  const zlomek = ["", "⅓", "⅔"][zbytek] ?? "";
  if ( zbytek === 3 ) return String(cele + 1);
  return (cele || !zlomek) ? `${cele}${zlomek}` : zlomek;
}
