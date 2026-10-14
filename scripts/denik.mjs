/**
 * Deník JaD – deník postavy s rozložením podle karty postavy Jeskyní a draků.
 *
 * Rozšiřuje standardní deník postavy dnd5e: přidává záložky „Deník“ (vlastnosti, dovednosti,
 * OČ, záchrany, rychlost dle Naložení, zbraně, kouzla, výbava v Řádcích, schopnosti) a
 * „Vzhled a vztahy“. Ostatní záložky (Inventář, Schopnosti, Kouzla, Efekty…) zůstávají z dnd5e.
 */
import { MODUL, formatRadky, odlozeny, radkyPredmetu, spocitatNalozeni } from "./nosnost.mjs";

const SABLONY = `modules/${MODUL}/templates`;

/** Vlastnosti a dovednosti v pořadí karty JaD. */
const VLASTNOSTI = [
  ["str", "Síla", ["ath"]],
  ["dex", "Obratnost", ["acr", "slt", "ste"]],
  ["con", "Odolnost", []],
  ["int", "Inteligence", ["his", "arc", "rel", "inv", "nat"]],
  ["wis", "Moudrost", ["med", "ani", "sur", "ins", "prc"]],
  ["cha", "Charisma", ["dec", "per", "prf", "itm"]]
];
const DOVEDNOSTI = {
  acr: "Akrobacie", ani: "Ovládání zvířat", arc: "Mystika", ath: "Atletika", dec: "Klamání", his: "Historie",
  ins: "Vhled", itm: "Zastrašování", inv: "Pátrání", med: "Lékařství", nat: "Příroda", prc: "Vnímání",
  prf: "Vystupování", per: "Přesvědčování", rel: "Náboženství", slt: "Čachry", ste: "Nenápadnost", sur: "Přežití"
};
const PASIVNI = [["ath", "Atletika"], ["acr", "Akrobacie"], ["ste", "Nenápadnost"], ["ins", "Vhled"], ["prc", "Vnímání"]];
const ZDATNOST = { 0: "", 0.5: "polovicni", 1: "plna", 2: "dvojita" };
const STUPNE = { lehke: "Lehké", stredni: "Střední", tezke: "Těžké", pretizeni: "Přetížení" };

const TYPY_ZASAHU = {
  acid: "Kyselinový", bludgeoning: "Drtivý", cold: "Chladný", fire: "Ohnivý", force: "Silový", lightning: "Bleskový",
  necrotic: "Nekrotický", piercing: "Bodný", poison: "Jedový", psychic: "Psychický", radiant: "Zářivý",
  slashing: "Sečný", thunder: "Hromový", healing: "Léčení", temphp: "Dočasné BV"
};
const CYKLUS_ZDATNOSTI = [0, 1, 2, 0.5];

const sign = n => (Number(n) >= 0 ? `+${Number(n)}` : `${Number(n)}`);

/**
 * Vytvoří třídu Deníku JaD. Volá se v init, kdy už existují třídy systému dnd5e.
 * @returns {typeof ActorSheet|null}
 */
export function vytvoritDenik() {
  const Zaklad = globalThis.dnd5e?.applications?.actor?.CharacterActorSheet;
  if ( !Zaklad ) {
    console.warn(`${MODUL} | CharacterActorSheet systému dnd5e nenalezen – Deník JaD není k dispozici.`);
    return null;
  }

  const { header, sidebar, ...ostatni } = Zaklad.PARTS;

  return class DenikJaD extends Zaklad {
    static DEFAULT_OPTIONS = {
      classes: ["jad-denik"],
      position: { width: 960, height: 900 },
      actions: {
        jadPouzit: DenikJaD.#pouzit,
        jadOdlozit: DenikJaD.#odlozit,
        jadOtevrit: DenikJaD.#otevrit,
        jadZdatnost: DenikJaD.#zdatnost,
        jadVybavit: DenikJaD.#vybavit,
        jadPripravit: DenikJaD.#pripravit,
        jadPozice: DenikJaD.#pozice,
        jadSmazat: DenikJaD.#smazat
      }
    };

    static PARTS = {
      header,
      sidebar,
      denik: {
        container: { classes: ["tab-body"], id: "tabs" },
        template: `${SABLONY}/denik.hbs`,
        scrollable: [""]
      },
      vzhled: {
        container: { classes: ["tab-body"], id: "tabs" },
        template: `${SABLONY}/vzhled.hbs`,
        scrollable: [""]
      },
      ...ostatni,
      spells: {
        container: { classes: ["tab-body"], id: "tabs" },
        template: `${SABLONY}/kouzla.hbs`,
        scrollable: [""]
      }
    };

    static TABS = [
      { tab: "denik", label: "JAD.Denik.Zalozka", icon: "fas fa-scroll" },
      ...Zaklad.TABS.filter(t => t.tab !== "details"),
      { tab: "vzhled", label: "JAD.Denik.ZalozkaVzhled", icon: "fas fa-user-pen" },
      ...Zaklad.TABS.filter(t => t.tab === "details")
    ];

    tabGroups = { primary: "denik" };

    /** @inheritDoc */
    async _preparePartContext(partId, context, options) {
      context = await super._preparePartContext(partId, context, options);
      if ( partId === "denik" ) {
        try {
          context.jad = this.#pripravitDenik(context);
        } catch(err) {
          console.error(`${MODUL} | Deník JaD nelze připravit`, err);
          context.jad = { chyba: `${err.name}: ${err.message}` };
        }
      }
      if ( partId === "vzhled" ) context.jad = this.#pripravitVzhled(context);
      if ( partId === "spells" ) {
        try {
          context.jad = pripravitKouzla(this.actor, this.isEditable);
        } catch(err) {
          console.error(`${MODUL} | Kouzla Deníku JaD nelze připravit`, err);
          context.jad = { chyba: `${err.name}: ${err.message}` };
        }
      }
      return context;
    }

    /** Data pro záložku Deník. */
    #pripravitDenik(context) {
      const actor = this.actor;
      const sys = actor.system;
      const nosnostZapnuta = game.settings.get(MODUL, "nosnostRadky");

      const vlastnosti = VLASTNOSTI.map(([k, nazev]) => {
        const a = sys.abilities[k] ?? {};
        return {
          key: k, nazev, hodnota: a.value ?? 10, oprava: sign(a.mod ?? 0),
          zachrana: sign(a.save?.value ?? a.save ?? a.mod ?? 0), zachranaZdatnost: !!a.proficient
        };
      });

      // Dovednosti podle skutečně přiřazené vlastnosti (lze změnit v nastavení dovednosti)
      const skupiny = Object.fromEntries(VLASTNOSTI.map(([k, nazev]) => [k, { key: k, nazev, dovednosti: [] }]));
      for ( const [klic, s] of Object.entries(sys.skills ?? {}) ) {
        const cil = skupiny[s.ability] ?? skupiny.str;
        cil.dovednosti.push({
          key: klic, nazev: DOVEDNOSTI[klic] ?? CONFIG.DND5E.skills[klic]?.label ?? klic,
          celkem: sign(s.total ?? s.mod ?? 0), zdatnost: ZDATNOST[s.value ?? 0] ?? "", pasivni: s.passive
        });
      }
      const poradi = Object.values(VLASTNOSTI).flatMap(v => v[2]);
      for ( const g of Object.values(skupiny) ) {
        g.dovednosti.sort((a, b) => {
          const ia = poradi.indexOf(a.key), ib = poradi.indexOf(b.key);
          return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
        });
      }

      const pomucky = Object.entries(sys.tools ?? {}).map(([k, t]) => ({
        key: k, nazev: this.#nazevPomucky(k), celkem: sign(t.total ?? t.mod ?? 0), zdatnost: ZDATNOST[t.value ?? 0] ?? ""
      }));

      const zbroj = sys.traits?.armorProf?.value ?? new Set();
      const zbrane = sys.traits?.weaponProf?.value ?? new Set();

      // Rychlost dle Naložení
      const pohyb = sys.attributes.movement ?? {};
      const jednotky = pohyb.units || "ft";
      const krok = jednotky === "sah" ? 1 : (jednotky === "m" ? 1.5 : 5);
      const nalozeni = sys.attributes.encumbrance?.jad ?? (nosnostZapnuta ? spocitatNalozeni(actor) : null);
      const aktualni = Number(pohyb.speed ?? pohyb.speeds?.walk ?? pohyb.walk ?? 0);
      const stupen = nalozeni?.stupen ?? "lehke";
      const snizeni = { lehke: 0, stredni: 1, tezke: 3 }[stupen];
      const zdroj = actor._source?.system?.attributes?.movement ?? {};
      const zakladni = (snizeni !== undefined) ? aktualni + (snizeni * krok)
        : Number(pohyb.fromSpecies?.walk || zdroj.speeds?.walk || zdroj.walk || aktualni);
      const jednotkaText = jednotky === "sah" ? "sáhů" : (CONFIG.DND5E.movementUnits?.[jednotky]?.abbreviation ?? jednotky);
      const stupne = [
        { nazev: "Lehké", hodnota: zakladni, aktivni: stupen === "lehke" },
        { nazev: "Střední (−1)", hodnota: Math.max(zakladni - krok, 0), aktivni: stupen === "stredni" },
        { nazev: "Těžké (−3)", hodnota: Math.max(zakladni - (3 * krok), 0), aktivni: stupen === "tezke" }
      ];
      if ( stupen === "pretizeni" ) stupne.push({ nazev: "Přetížení", hodnota: aktualni, aktivni: true });
      const rychlost = {
        stupne, pretizeni: stupen === "pretizeni",
        text: stupen === "pretizeni"
          ? `Přetížení: neseš víc, než uneseš – můžeš se pohybovat nejvýš ${aktualni} ${jednotkaText} za kolo (věci jen táhneš). Odlož část výbavy.`
          : `Aktuální rychlost: ${aktualni} ${jednotkaText} za kolo.`
      };

      // Kouzla
      const spell = sys.attributes.spell ?? {};
      const pozice = [];
      for ( let i = 1; i <= 9; i++ ) {
        const p = sys.spells?.[`spell${i}`];
        if ( p?.max ) pozice.push({ stupen: i, value: p.value ?? 0, max: p.max, cesta: `system.spells.spell${i}.value` });
      }
      const pakt = sys.spells?.pact?.max ? { value: sys.spells.pact.value ?? 0, max: sys.spells.pact.max, stupen: sys.spells.pact.level } : null;
      const truhla = actor.items.find(i => i.type === "feat" && /alchymistick[áa] truhla/i.test(i.name) && i.system.uses?.max);
      const kouzla = {
        vlastnost: CONFIG.DND5E.abilities[sys.attributes.spellcasting]?.label ?? "—",
        utok: sys.attributes.spellcasting ? sign(spell.attack ?? 0) : "—",
        so: sys.attributes.spellcasting ? (spell.dc ?? "—") : "—",
        pozice, pakt,
        truhla: truhla ? { id: truhla.id, value: truhla.system.uses.value ?? 0, max: truhla.system.uses.max } : null,
        zobrazit: !!(sys.attributes.spellcasting || pozice.length || pakt || truhla)
      };

      // Zbraně (vybavené, jinak všechny)
      const zbraneSeznam = [...(actor.itemTypes.weapon ?? [])]
        .sort((a, b) => (Number(!!b.system.equipped) - Number(!!a.system.equipped)) || ((a.sort ?? 0) - (b.sort ?? 0)));
      const zbraneData = zbraneSeznam.map(item => {
        const utok = item.system.activities?.find?.(a => a.type === "attack");
        const zasahy = utok?.labels?.damages ?? [];
        return {
          id: item.id, nazev: item.name, img: item.img, vybaveno: !!item.system.equipped,
          bonus: utok?.labels?.toHit ?? "",
          zasah: zasahy.map(d => d.formula).filter(_ => _).join(" + "),
          typ: [...new Set(zasahy.flatMap(d => [d.damageType ?? d.damageTypes ?? []].flat())
            .map(t => TYPY_ZASAHU[t] ?? CONFIG.DND5E.damageTypes?.[t]?.label ?? t))].join(", ")
            || zasahy.map(d => (d.label ?? "").replace(d.formula ?? "", "").trim()).filter(_ => _).join(", "),
          dosah: item.labels?.range ?? utok?.labels?.range ?? ""
        };
      });

      // Výbava v Řádcích: předměty mimo kontejnery, obsah kontejneru odsazeně pod ním
      const fyzicke = actor.items.filter(i => ("quantity" in i.system) && ("weight" in i.system));
      const PORADI_TYPU = { weapon: 0, equipment: 1, consumable: 2, tool: 3, loot: 4, container: 5 };
      const serad = (a, b) => ((PORADI_TYPU[a.type] ?? 9) - (PORADI_TYPU[b.type] ?? 9)) || ((a.sort ?? 0) - (b.sort ?? 0));
      const vybava = [];
      const pridat = (item, hloubka) => {
        const rucne = item.flags?.[MODUL]?.radky;
        vybava.push({
          id: item.id, nazev: item.name, img: item.img, pocet: item.system.quantity ?? 1, hloubka,
          odsazeni: hloubka * 18, radky: formatRadky(radkyPredmetu(item)), rucne: (rucne ?? "") === "" ? "" : rucne,
          jeKontejner: item.type === "container", vybavitelne: "equipped" in item.system,
          vybaveno: !!item.system.equipped, odlozeno: odlozeny(item), vlastniOdlozeni: !!item.flags?.[MODUL]?.odlozeno
        });
        if ( (item.type === "container") && (hloubka < 5) ) {
          fyzicke.filter(i => i.system.container === item.id).sort(serad).forEach(i => pridat(i, hloubka + 1));
        }
      };
      fyzicke.filter(i => !i.system.container || !actor.items.get(i.system.container)).sort(serad).forEach(i => pridat(i, 0));

      const schopnosti = (actor.itemTypes.feat ?? []).map(item => ({
        id: item.id, nazev: item.name, img: item.img,
        pouziti: item.system.uses?.max ? `${item.system.uses.value ?? 0}/${item.system.uses.max}` : ""
      }));

      const jazyky = sys.traits?.languages?.labels;
      const hp = sys.attributes.hp ?? {};
      const hd = sys.attributes.hd ?? {};
      const smrt = sys.attributes.death ?? {};

      return {
        prof: sign(sys.attributes.prof ?? 0),
        inspirace: !!sys.attributes.inspiration,
        iniciativa: sign(sys.attributes.init?.total ?? sys.attributes.init?.mod ?? 0),
        vlastnosti, skupiny: Object.values(skupiny), pomucky,
        oc: sys.attributes.ac?.value ?? 10,
        zbroj: { lehke: zbroj.has?.("lgt"), stredni: zbroj.has?.("med"), tezke: zbroj.has?.("hvy"), stity: zbroj.has?.("shl") },
        zbraneZdatnost: { jednoduche: zbrane.has?.("sim"), valecne: zbrane.has?.("mar") },
        pasivni: PASIVNI.map(([k, nazev]) => ({ nazev, hodnota: sys.skills?.[k]?.passive ?? "" })),
        rychlost, kouzla, zbrane: zbraneData, vybava, schopnosti,
        nalozeni: nalozeni ? {
          radky: nalozeni.radky, maximum: nalozeni.maximum, lehke: nalozeni.lehke, stredni: nalozeni.stredni,
          tezke: nalozeni.tezke, batoh: nalozeni.batoh, stupen: STUPNE[nalozeni.stupen], tridaStupne: nalozeni.stupen,
          zjednodusena: nalozeni.zjednodusena
        } : null,
        mince: ["gp", "sp", "cp"].map(k => ({
          key: k, cesta: `system.currency.${k}`, hodnota: sys.currency?.[k] ?? 0,
          nazev: game.i18n.localize(CONFIG.DND5E.currencies[k]?.abbreviation ?? k)
        })),
        jazyky: Array.isArray(jazyky?.languages) ? jazyky.languages.join(", ") : "",
        hp: { value: hp.value ?? 0, max: hp.max ?? 0, temp: hp.temp || "",
          maxRucne: actor._source?.system?.attributes?.hp?.max ?? "" },
        hd: { value: hd.value ?? "", max: hd.max ?? "" },
        smrt: {
          uspechy: [1, 2, 3].map(n => n <= (smrt.success ?? 0)),
          neuspechy: [1, 2, 3].map(n => n <= (smrt.failure ?? 0))
        },
        poznamky: actor.flags?.[MODUL]?.poznamkyHrani ?? "",
        editovatelne: this.isEditable
      };
    }

    /** Data pro záložku Vzhled a vztahy. */
    #pripravitVzhled(context) {
      const actor = this.actor;
      const d = actor.system.details ?? {};
      const f = actor.flags?.[MODUL] ?? {};
      const vztahy = [];
      for ( let i = 0; i < 14; i++ ) vztahy.push({ i, kdo: f.vztahy?.[i]?.kdo ?? "", vztah: f.vztahy?.[i]?.vztah ?? "" });
      return {
        vek: d.age ?? "", plet: d.skin ?? "", vyska: d.height ?? "", vlasy: d.hair ?? "", vaha: d.weight ?? "", oci: d.eyes ?? "",
        postava: f.postava ?? "", obleceni: f.obleceni ?? "", dojem: f.dojem ?? "", tituly: f.tituly ?? "",
        poznamky: f.poznamky ?? "", vztahy, editovatelne: this.isEditable
      };
    }

    #nazevPomucky(klic) {
      try {
        return globalThis.dnd5e.documents.Trait.keyLabel(`tool:${klic}`) || klic;
      } catch(err) {
        return klic;
      }
    }

    /** @inheritDoc */
    async _onRender(context, options) {
      await super._onRender(context, options);
      // Světlý (pergamenový) motiv dnd5e pro všechny záložky Deníku JaD
      this.element.classList.remove("theme-dark");
      this.element.classList.add("themed", "theme-light");
      for ( const input of this.element.querySelectorAll("input.jad-pocet") ) {
        input.addEventListener("change", event => {
          event.stopPropagation();
          const item = this.actor.items.get(input.dataset.itemId);
          const n = Math.max(Math.floor(Number(input.value)), 0);
          if ( item && Number.isFinite(n) ) item.update({ "system.quantity": n });
        });
      }
      for ( const pole of this.element.querySelectorAll(".jad-pole") ) {
        pole.addEventListener("change", event => {
          event.stopPropagation();
          this.#ulozitPole(pole);
        });
      }
      for ( const input of this.element.querySelectorAll("input.jad-radky") ) {
        input.addEventListener("change", async event => {
          event.stopPropagation();
          const item = this.actor.items.get(input.dataset.itemId);
          if ( !item ) return;
          const v = input.value.trim().replace(",", ".");
          if ( v === "" ) await item.unsetFlag(MODUL, "radky");
          else if ( Number.isFinite(Number(v)) ) await item.setFlag(MODUL, "radky", Number(v));
        });
      }
    }

    /** Uloží pole Deníku JaD (pole nemají „name“, aby se nebila se stejnými poli jiných záložek). */
    async #ulozitPole(pole) {
      const cesta = pole.dataset.cesta;
      let hodnota;
      switch ( pole.dataset.typ ) {
        case "bool": hodnota = pole.checked; break;
        case "cislo": hodnota = Number(pole.value) || 0; break;
        case "cislo-null": hodnota = pole.value.trim() === "" ? null : Number(pole.value); break;
        default: hodnota = pole.value;
      }
      if ( (typeof hodnota === "number") && !Number.isFinite(hodnota) ) return;
      await this.actor.update({ [cesta]: hodnota });
    }

    /** Ruční přepnutí zdatnosti (dovednost, pomůcka, záchrana, zbroje a zbraně). */
    static async #zdatnost(event, target) {
      if ( !this.isEditable ) return;
      const { cesta, druh, klic } = target.dataset;
      const aktualni = foundry.utils.getProperty(this.actor._source, cesta);
      let hodnota;
      if ( druh === "sada" ) {
        const sada = new Set(aktualni ?? []);
        if ( sada.has(klic) ) sada.delete(klic);
        else sada.add(klic);
        hodnota = Array.from(sada);
      } else if ( druh === "prepinac" ) {
        hodnota = aktualni ? 0 : 1;
      } else {
        const i = CYKLUS_ZDATNOSTI.indexOf(Number(aktualni ?? 0));
        hodnota = CYKLUS_ZDATNOSTI[(i + (event.shiftKey || event.button === 2 ? CYKLUS_ZDATNOSTI.length - 1 : 1)) % CYKLUS_ZDATNOSTI.length];
      }
      return this.actor.update({ [cesta]: hodnota });
    }

    /** Ve sloupci Hmotnost inventáře ukazuje Řádky. */
    async _prepareItemPhysical(item, ctx) {
      await super._prepareItemPhysical(item, ctx);
      if ( game.settings.get(MODUL, "nosnostRadky") && ("quantity" in item.system) ) {
        ctx.totalWeight = formatRadky(radkyPredmetu(item)) || "0";
      }
    }

    /** Sloupec Hmotnost přejmenovaný na Řádky. */
    async _configureInventorySections(sections) {
      await super._configureInventorySections(sections);
      if ( !game.settings.get(MODUL, "nosnostRadky") ) return;
      for ( const s of sections ) {
        if ( !Array.isArray(s.columns) ) continue;
        s.columns = s.columns.map(c => {
          const id = typeof c === "string" ? c : c?.id;
          if ( id !== "weight" ) return c;
          return { ...(typeof c === "object" ? c : {}), id: "weight", label: "JAD.Nosnost.Sloupec" };
        });
      }
    }

    static async #pouzit(event, target) {
      const item = this.actor.items.get(target.closest("[data-item-id]")?.dataset.itemId);
      return item?.use({ event });
    }

    static async #otevrit(event, target) {
      const item = this.actor.items.get(target.closest("[data-item-id]")?.dataset.itemId);
      return item?.sheet.render(true);
    }

    /** Připravit / odložit kouzlo (kroužek P). */
    static async #pripravit(event, target) {
      const item = this.actor.items.get(target.closest("[data-item-id]")?.dataset.itemId);
      if ( !item || (item.type !== "spell") || !item.system.canPrepare || (item.system.prepared === 2) ) return;
      return item.update({ "system.prepared": item.system.prepared ? 0 : 1 });
    }

    /** Kliknutí na kroužek pozice kouzla: nastaví počet zbývajících pozic. */
    static async #pozice(event, target) {
      const { cesta, index } = target.dataset;
      const aktualni = Number(foundry.utils.getProperty(this.actor, cesta) ?? 0);
      const n = Number(index) + 1;
      return this.actor.update({ [cesta]: aktualni === n ? n - 1 : n });
    }

    static async #smazat(event, target) {
      const item = this.actor.items.get(target.closest("[data-item-id]")?.dataset.itemId);
      return item?.deleteDialog?.() ?? item?.delete();
    }

    static async #vybavit(event, target) {
      const item = this.actor.items.get(target.closest("[data-item-id]")?.dataset.itemId);
      if ( !item || !("equipped" in item.system) ) return;
      return item.update({ "system.equipped": !item.system.equipped });
    }

    static async #odlozit(event, target) {
      const item = this.actor.items.get(target.closest("[data-item-id]")?.dataset.itemId);
      if ( !item ) return;
      if ( item.flags?.[MODUL]?.odlozeno ) return item.unsetFlag(MODUL, "odlozeno");
      return item.setFlag(MODUL, "odlozeno", true);
    }
  };
}

// ------------------------------------------------------------------ Kouzla (3. strana karty JaD)

const ZKRATKY = { str: "SIL", dex: "OBR", con: "ODL", int: "INT", wis: "MDR", cha: "CHA" };
const VLASTNOST_NAZEV = { str: "Síla", dex: "Obratnost", con: "Odolnost", int: "Inteligence", wis: "Moudrost", cha: "Charisma" };
const AKTIVACE = {
  action: "Akce", bonus: "Bon. akce", reaction: "Reakce", minute: "min.", hour: "hod.", day: "den",
  special: "Zvláštní", legendary: "Leg. akce", none: "—"
};
const TRVANI = { inst: "Okamžité", turn: "tah", round: "kolo", minute: "min.", hour: "hod.", day: "den", month: "měsíc",
  year: "rok", perm: "Trvalé", disp: "Do rozptýlení", spec: "Zvláštní", ureq: "Do spuštění" };
const POVOLANI_NAZEV = { wizard: "Kouzelník", sorcerer: "Čaroděj", warlock: "Černokněžník", druid: "Druid", cleric: "Klerik",
  bard: "Bard", alchymista: "Alchymista", fighter: "Bojovník", rogue: "Tulák", "lovec-netvoru": "Lovec netvorů" };

function cislovka(n, jedna, dve, pet) {
  return n === 1 ? jedna : (n >= 2 && n <= 4) ? dve : pet;
}

function textDosahu(r) {
  if ( !r ) return "";
  const u = r.units;
  if ( u === "self" ) return "Sesilatel";
  if ( u === "touch" ) return "Dotyk";
  if ( u === "spec" ) return "Zvláštní";
  if ( u === "any" ) return "Neomezený";
  if ( u === "sah" ) {
    const v = Number(r.value);
    return `${r.value} ${cislovka(v, "sáh", "sáhy", "sáhů")}`;
  }
  if ( u === "ft" && r.value ) {
    const v = Number(r.value) / 5;
    return `${v} ${cislovka(v, "sáh", "sáhy", "sáhů")}`;
  }
  if ( u === "mi" ) return `${r.value} mil`;
  return [r.value, u].filter(_ => _).join(" ");
}

function textTrvani(d, soustredeni) {
  if ( !d ) return "";
  let t = TRVANI[d.units] ?? d.units ?? "";
  if ( d.value && !["inst", "perm", "spec", "disp", "ureq"].includes(d.units) ) t = `${d.value} ${t}`;
  return soustredeni ? `S, ${t}` : t;
}

/**
 * Data pro záložku Kouzla v rozložení karty JaD.
 * @param {Actor} actor
 * @param {boolean} editovatelne
 */
export function pripravitKouzla(actor, editovatelne) {
  const sys = actor.system;
  const prof = sys.attributes?.prof ?? 0;

  // Sesilatelská povolání
  const povolani = Object.entries(actor.spellcastingClasses ?? {}).map(([klic, cls]) => {
    const vl = cls.spellcasting?.ability || sys.attributes.spellcasting;
    const mod = sys.abilities?.[vl]?.mod ?? 0;
    return {
      nazev: cls.name ?? POVOLANI_NAZEV[klic] ?? klic, klic, uroven: cls.system?.levels ?? "",
      vlastnost: VLASTNOST_NAZEV[vl] ?? "—",
      so: vl ? 8 + prof + mod + (Number(sys.bonuses?.spell?.dc) || 0) : "—",
      utok: vl ? sign(prof + mod) : "—"
    };
  });

  // Pozice kouzel
  const pozice = [];
  let maxStupen = 0;
  for ( let i = 1; i <= 9; i++ ) {
    const p = sys.spells?.[`spell${i}`];
    const max = p?.max ?? 0;
    if ( max ) maxStupen = i;
    pozice.push({
      stupen: i, max, value: p?.value ?? 0, cesta: `system.spells.spell${i}.value`,
      kruhy: Array.from({ length: max }, (_, k) => ({ index: k, plny: k < (p?.value ?? 0) }))
    });
  }
  const pk = sys.spells?.pact;
  const pakt = pk?.max ? {
    stupen: pk.level, max: pk.max, value: pk.value ?? 0, cesta: "system.spells.pact.value",
    kruhy: Array.from({ length: pk.max }, (_, k) => ({ index: k, plny: k < (pk.value ?? 0) }))
  } : null;
  if ( pakt ) maxStupen = Math.max(maxStupen, pk.level ?? 0);
  for ( const p of povolani ) p.maxStupen = maxStupen || "—";

  // Kouzla podle Stupně
  const skupiny = new Map();
  const kouzla = [...(actor.itemTypes.spell ?? [])].sort((a, b) => (a.system.level - b.system.level) || a.name.localeCompare(b.name, "cs"));
  for ( const item of kouzla ) {
    const s = item.system;
    const vl = s.properties ?? new Set();
    const aktivity = [...(s.activities ?? [])];
    const utok = aktivity.find(a => a.type === "attack");
    const zachrana = aktivity.find(a => a.type === "save");
    let utokSo = "";
    if ( utok ) utokSo = utok.labels?.toHit ?? "útok";
    else if ( zachrana ) {
      const abl = [...(zachrana.save?.ability ?? [])].map(k => ZKRATKY[k] ?? k).join("/");
      utokSo = `${abl} ${zachrana.save?.dc?.value ?? ""}`.trim();
    }
    const slozky = [vl.has?.("vocal") && "V", vl.has?.("somatic") && "P", vl.has?.("material") && "S"].filter(_ => _).join(", ");
    const akt = s.activation ?? {};
    let doba = AKTIVACE[akt.type] ?? akt.type ?? "";
    if ( ["minute", "hour", "day"].includes(akt.type) ) doba = `${akt.value ?? 1} ${doba}`;
    if ( vl.has?.("ritual") ) doba += " (R)";
    const pripravitelne = !!s.canPrepare;
    const stav = pripravitelne ? (s.prepared === 2 ? "vzdy" : (s.prepared ? "pripraveno" : "")) : "vzdy";
    const pouziti = s.uses?.max ? `${s.uses.value ?? 0}/${s.uses.max}` : "";
    const radek = {
      id: item.id, nazev: item.name, img: item.img, stupen: s.level || "T", stav,
      klikaci: pripravitelne && (s.prepared !== 2), utokSo, doba, slozky,
      dosah: textDosahu(s.range), trvani: textTrvani(s.duration, vl.has?.("concentration")),
      poznamka: [s.materials?.value, pouziti && `Použití ${pouziti}`].filter(_ => _).join(" · ")
    };
    const klic = s.level;
    if ( !skupiny.has(klic) ) skupiny.set(klic, { nazev: klic ? `${klic}. Stupeň` : "Triky", kouzla: [] });
    skupiny.get(klic).kouzla.push(radek);
  }

  const prvni = povolani[0]?.klic ?? "";
  return {
    povolani, pozice: pozice.filter(p => p.max), pakt, skupiny: [...skupiny.values()],
    zadna: !kouzla.length, editovatelne, tridaPovolani: prvni
  };
}

/** Zaregistruje Deník JaD jako volitelný deník postav. */
export function registrovatDenik() {
  const Denik = vytvoritDenik();
  if ( !Denik ) return;
  const Config = foundry.applications?.apps?.DocumentSheetConfig;
  const moznosti = { types: ["character"], makeDefault: false, label: "JAD.Denik.Nazev" };
  if ( Config?.registerSheet ) Config.registerSheet(Actor, MODUL, Denik, moznosti);
  else Actors.registerSheet(MODUL, Denik, moznosti);
}
