/**
 * Měření pohybu tokenů nezávislé na jednotkách.
 *
 * dnd5e obarvuje trasu tokenu podle rychlosti postavy, ale rychlost bere jako číslo v jednotkách mřížky
 * scény. Postava JaD se 6 sáhy by tak na scéně ve stopách měla „6 stop“ a nestvůra ze systému dnd5e
 * se 30 stopami by na scéně v sázích měla „30 sáhů“. Tady se rychlost nejdřív převede na jednotky scény.
 */
const MODUL = "jeskyne-a-draci";

/** Běžné zápisy jednotek v mřížce scény → klíč v CONFIG.DND5E.movementUnits. */
const ALIASY = {
  ft: "ft", feet: "ft", foot: "ft", stopa: "ft", stopy: "ft", stop: "ft",
  m: "m", metr: "m", metry: "m", metrů: "m", meters: "m",
  sah: "sah", "sáh": "sah", "sáhy": "sah", "sáhů": "sah", sahy: "sah", sahu: "sah",
  mi: "mi", mile: "mi", miles: "mi", km: "km"
};

function klicJednotky(u) {
  const s = String(u ?? "").trim().toLowerCase();
  if ( CONFIG.DND5E?.movementUnits?.[s] ) return s;
  return ALIASY[s] ?? null;
}

/**
 * Převede délku mezi jednotkami podle převodních poměrů dnd5e (vše vztaženo ke stopám).
 * Neznámé jednotky vrátí hodnotu beze změny.
 */
export function prevestDelku(hodnota, z, na) {
  const jednotky = CONFIG.DND5E?.movementUnits ?? {};
  const a = jednotky[klicJednotky(z)]?.conversion;
  const b = jednotky[klicJednotky(na)]?.conversion;
  if ( !a || !b || (klicJednotky(z) === klicJednotky(na)) ) return hodnota;
  return hodnota * a / b;
}

/** Zaregistruje pravítko tokenů, které převádí rychlost na jednotky scény. */
export function registrovatMeritko() {
  const Zaklad = CONFIG.Token?.rulerClass;
  if ( !Zaklad ) return;

  class PravitkoJaD extends Zaklad {
    /** Barva trasy podle rychlosti převedené na jednotky mřížky scény. */
    #barva(waypoint, style) {
      if ( !(game.user.id in (this.token._plannedMovement ?? {}))
        || CONFIG.Token.movement.actions[waypoint.action]?.teleport ) return style;
      const pohyb = this.token.actor?.system.attributes?.movement;
      const rychlosti = pohyb?.speeds;
      if ( !rychlosti || !this.token.actor?.system.isCreature ) return style;
      let rychlost = Number(rychlosti[waypoint.action] ?? 0);
      if ( CONFIG.DND5E.movementTypes[waypoint.action]?.walkFallback || !CONFIG.DND5E.movementTypes[waypoint.action] ) {
        rychlost = Math.max(rychlost, Number(rychlosti.walk ?? 0));
      }
      rychlost = prevestDelku(rychlost, pohyb.units || "ft", canvas.scene?.grid?.units);
      if ( !(rychlost > 0) ) return style;
      const { normal, double, triple } = CONFIG.DND5E.tokenRulerColors ?? {};
      const nasobek = (waypoint.measurement.cost - 0.1) / rychlost;
      if ( nasobek <= 1 ) style.color = normal ?? style.color;
      else if ( nasobek <= 2 ) style.color = double ?? style.color;
      else style.color = triple ?? style.color;
      return style;
    }

    _getWaypointStyle(waypoint) {
      const style = super._getWaypointStyle(waypoint);
      return (style?.radius === 0) ? style : this.#barva(waypoint, style);
    }

    _getSegmentStyle(waypoint) {
      return this.#barva(waypoint, super._getSegmentStyle(waypoint));
    }

    _getGridHighlightStyle(waypoint, offset) {
      return this.#barva(waypoint, super._getGridHighlightStyle(waypoint, offset));
    }
  }

  CONFIG.Token.rulerClass = PravitkoJaD;
  console.log(`${MODUL} | Měření pohybu tokenů převádí rychlost na jednotky scény.`);
}
