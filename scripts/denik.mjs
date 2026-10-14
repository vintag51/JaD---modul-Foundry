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
        jadOtevrit: DenikJaD.#otevrit
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
      ...ostatni
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
      if ( partId === "denik" ) context.jad = this.#pripravitDenik(context);
      if ( partId === "vzhled" ) context.jad = this.#pripravitVzhled(context);
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
      const snizeni = { lehke: 0, stredni: 1, tezke: 3 }[nalozeni?.stupen] ?? 0;
      const zakladni = nalozeni?.stupen === "pretizeni" ? null : aktualni + (snizeni * krok);
      const jednotkaText = jednotky === "sah" ? "sáh." : (CONFIG.DND5E.movementUnits?.[jednotky]?.abbreviation ?? jednotky);
      const rychlost = {
        jednotky: jednotkaText,
        aktualni,
        stupne: zakladni === null ? null : [
          { nazev: "Lehké", hodnota: zakladni, aktivni: nalozeni?.stupen === "lehke" },
          { nazev: "Střední (−1)", hodnota: Math.max(zakladni - krok, 0), aktivni: nalozeni?.stupen === "stredni" },
          { nazev: "Těžké (−3)", hodnota: Math.max(zakladni - (3 * krok), 0), aktivni: nalozeni?.stupen === "tezke" }
        ]
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
      let zbraneSeznam = actor.itemTypes.weapon ?? [];
      if ( zbraneSeznam.some(z => z.system.equipped) ) zbraneSeznam = zbraneSeznam.filter(z => z.system.equipped);
      const zbraneData = zbraneSeznam.map(item => {
        const utok = item.system.activities?.find?.(a => a.type === "attack");
        const zasahy = utok?.labels?.damages ?? [];
        return {
          id: item.id, nazev: item.name, img: item.img,
          bonus: utok?.labels?.toHit ?? "",
          zasah: zasahy.map(d => d.formula).filter(_ => _).join(" + "),
          typ: zasahy.map(d => (d.label ?? "").replace(d.formula ?? "", "").trim()).filter(_ => _).join(", "),
          dosah: item.labels?.range ?? utok?.labels?.range ?? ""
        };
      });

      // Výbava v Řádcích
      const vybava = actor.items.filter(i => ("quantity" in i.system) && ("weight" in i.system))
        .sort((a, b) => (a.sort ?? 0) - (b.sort ?? 0))
        .map(item => {
          const rucne = item.flags?.[MODUL]?.radky;
          const kontejner = item.system.container ? actor.items.get(item.system.container) : null;
          return {
            id: item.id, nazev: item.name, img: item.img, pocet: item.system.quantity ?? 1,
            radky: formatRadky(radkyPredmetu(item)), rucne: (rucne ?? "") === "" ? "" : rucne,
            vKontejneru: kontejner?.name ?? "", jeKontejner: item.type === "container",
            odlozeno: odlozeny(item), vlastniOdlozeni: !!item.flags?.[MODUL]?.odlozeno
          };
        });

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
        hp: { value: hp.value ?? 0, max: hp.max ?? 0, temp: hp.temp ?? "" },
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

    static async #pouzit(event, target) {
      const item = this.actor.items.get(target.closest("[data-item-id]")?.dataset.itemId);
      return item?.use({ event });
    }

    static async #otevrit(event, target) {
      const item = this.actor.items.get(target.closest("[data-item-id]")?.dataset.itemId);
      return item?.sheet.render(true);
    }

    static async #odlozit(event, target) {
      const item = this.actor.items.get(target.closest("[data-item-id]")?.dataset.itemId);
      if ( !item ) return;
      if ( item.flags?.[MODUL]?.odlozeno ) return item.unsetFlag(MODUL, "odlozeno");
      return item.setFlag(MODUL, "odlozeno", true);
    }
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
