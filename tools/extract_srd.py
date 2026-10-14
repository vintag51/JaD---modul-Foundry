"""Načte SRD 5.1 kouzla a seznamy povolání ze zdrojů systému dnd5e."""
import yaml, json, glob, os, sys
src = sys.argv[1]; out = sys.argv[2]
spells = {}
for f in glob.glob(os.path.join(src, "packs/_source/spells/**/*.yml"), recursive=True):
    d = yaml.safe_load(open(f, encoding="utf-8"))
    if d.get("type") != "spell": continue
    d.pop("_key", None)
    spells[d["_id"]] = d
lists = {}
for doc in yaml.safe_load_all(open(os.path.join(src, "packs/_source/rules/chapter-10-spellcasting.yml"), encoding="utf-8")):
    for p in doc.get("pages", []):
        if p.get("type") == "spells":
            lists[p["system"]["identifier"]] = {"name": p["name"], "type": p["system"]["type"],
              "spells": [u.split(".")[-1] for u in p["system"].get("spells", [])]}
json.dump({"spells": spells, "lists": lists}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(spells), "kouzel;", {k: len(v["spells"]) for k, v in lists.items()})
