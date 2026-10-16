/**
 * Určení základních Hodnot vlastností při tvorbě postavy:
 * standardní sada, nákup bodů (27) nebo hod 4k6 (nejnižší se škrtá).
 * Zapisuje do system.abilities.*.value (rasové a jiné bonusy se přičítají zvlášť přes postup).
 */
const KLICE = ["str", "dex", "con", "int", "wis", "cha"];
const NAZVY = { str: "Síla", dex: "Obratnost", con: "Odolnost", int: "Inteligence", wis: "Moudrost", cha: "Charisma" };
const SADA = [15, 14, 13, 12, 10, 8];
const CENA = { 8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9 };
const BODY = 27;

/** Hodí 4k6 a sečte tři nejvyšší; vrátí hodnotu a text hodu. */
async function hod4k6() {
  const roll = await new Roll("4d6kh3").evaluate();
  const kostky = roll.dice[0]?.results?.map(r => r.result) ?? [];
  return { hodnota: roll.total, text: kostky.join(", ") };
}

function vyberHodnot(hodnoty, prefix) {
  const moznosti = hodnoty.map((h, i) => `<option value="${i}">${h}</option>`).join("");
  return KLICE.map((k, i) => `
    <label class="jad-urceni-radek"><span>${NAZVY[k]}</span>
      <select name="${prefix}-${k}"><option value="">—</option>${moznosti}</select>
    </label>`).join("");
}

/**
 * Otevře dialog a zapíše zvolené hodnoty postavě.
 * @param {Actor} actor
 */
export async function urcitVlastnosti(actor) {
  const { DialogV2 } = foundry.applications.api;
  const hody = [];
  for ( let i = 0; i < 6; i++ ) hody.push(await hod4k6());

  const content = `
  <div class="jad-urceni">
    <p>Zvol způsob určení základních Hodnot vlastností. Rasové bonusy se přičtou samy při přidání rasy.</p>
    <nav class="jad-urceni-zalozky">
      <label><input type="radio" name="zpusob" value="sada" checked> Standardní sada</label>
      <label><input type="radio" name="zpusob" value="nakup"> Nákup bodů</label>
      <label><input type="radio" name="zpusob" value="hod"> Hod 4k6</label>
    </nav>
    <section data-zpusob="sada">
      <p class="jad-poznamka">Každé hodnotě 15, 14, 13, 12, 10, 8 přiřaď jednu Vlastnost.</p>
      ${vyberHodnot(SADA, "sada")}
    </section>
    <section data-zpusob="nakup" hidden>
      <p class="jad-poznamka">Máš ${BODY} bodů; každá Vlastnost začíná na 8, maximum je 15.
        Zbývá: <strong class="jad-zbyva">${BODY}</strong></p>
      ${KLICE.map(k => `
        <label class="jad-urceni-radek"><span>${NAZVY[k]}</span>
          <input type="number" name="nakup-${k}" value="8" min="8" max="15" step="1">
        </label>`).join("")}
    </section>
    <section data-zpusob="hod" hidden>
      <p class="jad-poznamka">Hozeno 4k6 (nejnižší kostka se škrtá):
        ${hody.map(h => `<strong>${h.hodnota}</strong> <small>(${h.text})</small>`).join(" · ")}</p>
      ${vyberHodnot(hody.map(h => h.hodnota), "hod")}
    </section>
    <p class="jad-urceni-chyba" hidden></p>
  </div>`;

  const precist = form => {
    const zpusob = form.querySelector("[name=zpusob]:checked")?.value;
    const vysledek = {};
    if ( zpusob === "nakup" ) {
      let utraceno = 0;
      for ( const k of KLICE ) {
        const v = Math.clamp(Number(form.querySelector(`[name=nakup-${k}]`).value) || 8, 8, 15);
        vysledek[k] = v;
        utraceno += CENA[v];
      }
      if ( utraceno > BODY ) return { chyba: `Utratil jsi ${utraceno} bodů z ${BODY}.` };
      return { vysledek };
    }
    const zdroj = zpusob === "hod" ? hody.map(h => h.hodnota) : SADA;
    const pouzite = new Set();
    for ( const k of KLICE ) {
      const v = form.querySelector(`[name=${zpusob}-${k}]`).value;
      if ( v === "" ) return { chyba: "Přiřaď hodnotu všem Vlastnostem." };
      if ( pouzite.has(v) ) return { chyba: "Každou hodnotu lze použít jen jednou." };
      pouzite.add(v);
      vysledek[k] = zdroj[Number(v)];
    }
    return { vysledek };
  };

  const vysledek = await DialogV2.wait({
    window: { title: `Hodnoty vlastností – ${actor.name}`, icon: "fas fa-dice-d20" },
    classes: ["jad-urceni-okno"],
    content,
    position: { width: 440 },
    buttons: [
      { action: "ok", label: "Zapsat", icon: "fas fa-check", default: true,
        callback: (event, button) => {
          const r = precist(button.form);
          if ( r.chyba ) { ui.notifications.warn(r.chyba); return null; }
          r.vysledek.zpusob = button.form.querySelector("[name=zpusob]:checked")?.value;
          return r.vysledek;
        } },
      { action: "zrusit", label: "Zrušit", icon: "fas fa-xmark", callback: () => null }
    ],
    render: (event, dialog) => {
      const el = dialog.element;
      const prepnout = () => {
        const z = el.querySelector("[name=zpusob]:checked")?.value;
        for ( const s of el.querySelectorAll("section[data-zpusob]") ) s.hidden = s.dataset.zpusob !== z;
      };
      const prepocitat = () => {
        let utraceno = 0;
        for ( const k of KLICE ) utraceno += CENA[Math.clamp(Number(el.querySelector(`[name=nakup-${k}]`).value) || 8, 8, 15)] ?? 0;
        const zb = el.querySelector(".jad-zbyva");
        zb.textContent = BODY - utraceno;
        zb.style.color = utraceno > BODY ? "#a01818" : "";
      };
      el.querySelectorAll("[name=zpusob]").forEach(r => r.addEventListener("change", prepnout));
      el.querySelectorAll("[name^=nakup-]").forEach(i => i.addEventListener("input", prepocitat));
    },
    rejectClose: false
  });
  if ( !vysledek ) return;
  const zmeny = Object.fromEntries(KLICE.map(k => [`system.abilities.${k}.value`, vysledek[k]]));
  await actor.update(zmeny);
  if ( vysledek.zpusob === "hod" ) {
    await ChatMessage.create({
      speaker: ChatMessage.getSpeaker({ actor }),
      content: `<p><strong>Hod na Hodnoty vlastností (4k6, nejnižší se škrtá):</strong> ${hody.map(h => `${h.hodnota} (${h.text})`).join(", ")}</p>`
    });
  }
  ui.notifications.info(`Hodnoty vlastností zapsány: ${KLICE.map(k => `${NAZVY[k]} ${vysledek[k]}`).join(", ")}.`);
}
