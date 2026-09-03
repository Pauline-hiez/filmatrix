"""Fusionne les tags de type "saga" dans "univers" et déduplique les graphies.

Les tags saga/univers se recoupent presque partout dans le code (filtrage des
questions, attribution des fragments d'album) sauf à deux endroits traités
différemment par oubli. Ce script fusionne les deux types en un seul
("univers") et normalise les variantes d'un même nom (slug vs humanisé, casse,
accents) vers une graphie canonique unique, directement dans les fichiers
sources data/questions/*.json.

Autonome : ne dépend pas du package filmatrix (qui initialiserait Flask/DB à
l'import), donc key()/is_slug()/humanize_tag_name() sont dupliées ici depuis
scripts/harmonize_franchise_tags.py et filmatrix/catalog_rarities.py plutôt
qu'importées.

Par défaut n'écrit rien (--dry-run implicite) : affiche le rapport de fusion
pour revue. Ajouter --apply pour committer les fichiers sur disque.

    python -m scripts.merge_saga_into_univers
    python -m scripts.merge_saga_into_univers --apply
"""
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

FRANCHISE_TYPES = ("saga", "univers")


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


BASE = project_root() / "data" / "questions"


def key(name: str) -> str:
    """Clé de normalisation : minuscules sans accents ni ponctuation."""
    decomposed = unicodedata.normalize("NFKD", name.lower())
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", without_accents)


def is_slug(name: str) -> bool:
    """Un nom est un slug s'il est en minuscules sans espace ni majuscule."""
    return " " not in name and not any(char.isupper() for char in name)


def humanize_tag_name(name: str) -> str:
    """Transforme un nom de slug en vrai nom : indiana-jones -> Indiana Jones."""
    if " " in name or any(char.isupper() for char in name):
        return name
    return name.replace("-", " ").title()


def collect_variants(files: list[tuple[Path, list[dict]]]) -> dict[str, Counter]:
    """Regroupe toutes les graphies de tags saga/univers par clé normalisée."""
    variants: dict[str, Counter] = {}
    for _path, data in files:
        for question in data:
            for t in question.get("tags", []):
                if t.get("type") in FRANCHISE_TYPES:
                    variants.setdefault(key(t["name"]), Counter())[t["name"]] += 1
    return variants


def pick_canonical(counter: Counter) -> str:
    """Choisit la graphie canonique d'un groupe : non-slug > fréquence > alpha."""
    non_slug = {name: n for name, n in counter.items() if not is_slug(name)}
    pool = non_slug or counter
    name = sorted(pool.items(), key=lambda item: (-item[1], item[0]))[0][0]
    return humanize_tag_name(name) if is_slug(name) else name


def rewrite_tags(tags: list[dict], canonical_map: dict[str, str]) -> list[dict]:
    """Reconstruit le tableau tags : saga->univers, graphie canonique, dédup."""
    new_tags: list[dict] = []
    seen: set[str] = set()
    for t in tags:
        if t.get("type") in FRANCHISE_TYPES:
            k = key(t["name"])
            if k in seen:
                continue
            seen.add(k)
            new_tags.append({"name": canonical_map[k], "type": "univers"})
        else:
            new_tags.append(t)
    return new_tags


def main() -> None:
    apply_changes = "--apply" in sys.argv

    files = []
    for json_file in sorted(BASE.glob("*.json")):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        files.append((json_file, data))

    variants = collect_variants(files)
    canonical_map = {k: pick_canonical(counter) for k, counter in variants.items()}

    fusions = {k: c for k, c in variants.items() if len(c) > 1}
    simple_retypes = len(variants) - len(fusions)

    print(f"{len(fusions)} fusion(s) de graphies, {simple_retypes} retypage(s) simple(s) saga->univers :\n")
    for k, counter in sorted(fusions.items(), key=lambda item: -sum(item[1].values())):
        parts = " + ".join(f"{name} ({n}x)" for name, n in counter.most_common())
        print(f"  {parts} -> {canonical_map[k]}")

    files_changed = 0
    for json_file, data in files:
        file_changed = False
        for question in data:
            old_tags = question.get("tags", [])
            new_tags = rewrite_tags(old_tags, canonical_map)
            if new_tags != old_tags:
                question["tags"] = new_tags
                file_changed = True

        if file_changed:
            files_changed += 1
            if apply_changes:
                json_file.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
            print(f"  {'écrit' if apply_changes else 'à écrire'} : {json_file.name}")

    print(f"\n{files_changed} fichier(s) {'modifié(s)' if apply_changes else 'seraient modifié(s)'}.")
    if not apply_changes:
        print("Dry-run : relancer avec --apply pour écrire les fichiers.")


if __name__ == "__main__":
    main()
