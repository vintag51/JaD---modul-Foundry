// Sestaví LevelDB kompendia z JSON zdrojů v packs/_source pomocí oficiálního Foundry CLI.
import { compilePack } from "@foundryvtt/foundryvtt-cli";
import { rm } from "node:fs/promises";

for ( const pack of ["kouzla", "seznamy-kouzel", "rasy", "povolani", "zazemi", "predmety"] ) {
  await rm(`packs/${pack}`, { recursive: true, force: true });
  await compilePack(`packs/_source/${pack}`, `packs/${pack}`, { log: true, recursive: true });
  console.log(`Sestaveno: packs/${pack}`);
}
