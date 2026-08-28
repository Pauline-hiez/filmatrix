"""Contrôle des fichiers de data/questions/ avant import en base.

Le JSON n'est validé nulle part ailleurs : scripts/seed_db.py fait confiance à
ce qu'il lit. Or l'id d'une question est sa clé primaire pour tout le dossier,
et deux questions qui le partagent s'écrasent en silence à l'import. Ce script
vérifie donc, en plus du schéma attendu par filmatrix/services/engine.py :
l'unicité des id, l'absence de doublons de contenu, et le fait qu'un mode dont
l'écran n'affiche que `prompt` nomme bien l'œuvre concernée.

    python -m scripts.check_questions
"""
import json, collections, sys, unicodedata, re
from pathlib import Path

BASE = Path("data/questions")
REQUIRED = {"id", "mode", "prompt", "payload", "correct_answer", "requires_account"}
FORBIDDEN = {"category", "difficulty"}
CONTENT = {"film", "serie"}
TAG_TYPES = {"genre", "univers", "saga", "pays", "epoque", "annee",
             "realisateur", "acteur", "studio", "autre"}

# Forme du payload / correct_answer attendue par filmatrix/services/engine.py
SHAPE = {
    "qcm":               (["options"], ["index"]),
    "vrai_faux":         ([], ["value"]),
    "chronologie":       (["films"], ["order"]),
    "film_melange":      ([], ["title"]),
    "citation":          ([], ["film"]),
    "emoji":             ([], ["film"]),
    "devinette":         (["hints"], ["film"]),
    "devinette_affiche": (["poster_url"], ["film"]),
    "casting":           (["actor_photos"], ["film"]),
    "blindtest":         (["audio_url"], ["film"]),
}
# Modes dont l'énoncé doit à lui seul désigner l'œuvre (l'écran de jeu
# n'affiche que `prompt`, jamais les tags).
NEEDS_CONTEXT = {"qcm", "vrai_faux"}

def subjects(q):
    """Œuvre(s) sur lesquelles porte la question, pour mesurer la diversité."""
    if q["mode"] == "chronologie":
        return {t for t in q["correct_answer"]["order"]}
    a = q["correct_answer"]
    if a.get("film") or a.get("title"):
        return {a.get("film") or a.get("title")}
    univers = [t["name"] for t in q.get("tags", []) if t.get("type") == "univers"]
    return set(univers) or {"(sans univers)"}

errors, warnings = [], []
by_mode = collections.defaultdict(list)
ids = {}

def norm(text):
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()

for path in sorted(BASE.glob("*.json")):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{path.name} : JSON invalide — {exc}")
        continue
    if not isinstance(data, list):
        errors.append(f"{path.name} : la racine doit être une liste")
        continue
    for q in data:
        tag = f"{path.name}#{q.get('id')}"
        missing = REQUIRED - set(q)
        if missing:
            errors.append(f"{tag} : champs manquants {sorted(missing)}")
            continue
        if q["id"] in ids:
            errors.append(f"{tag} : id déjà utilisé par {ids[q['id']]}")
        ids[q["id"]] = tag
        for k in FORBIDDEN & set(q):
            errors.append(f"{tag} : champ « {k} » retiré du schéma")
        ct = q.get("content_type", "film")
        if ct not in CONTENT:
            errors.append(f"{tag} : content_type « {ct} » inconnu")
        if "content_type" not in q:
            warnings.append(f"{tag} : content_type implicite")
        if not isinstance(q["requires_account"], bool):
            errors.append(f"{tag} : requires_account n'est pas un booléen")
        if q["mode"] not in SHAPE:
            errors.append(f"{tag} : mode « {q['mode']} » inconnu du moteur")
            continue
        pk, ak = SHAPE[q["mode"]]
        for k in pk:
            if k not in q["payload"]:
                errors.append(f"{tag} : payload.{k} manquant")
        for k in ak:
            if k not in q["correct_answer"]:
                errors.append(f"{tag} : correct_answer.{k} manquant")
        for t in q.get("tags", []):
            if not isinstance(t, dict) or "name" not in t:
                errors.append(f"{tag} : tag mal formé {t!r}")
            elif t.get("type") not in TAG_TYPES:
                warnings.append(f"{tag} : type de tag inhabituel « {t.get('type')} »")

        # Contrôles propres à chaque mode
        m = q["mode"]
        if m == "qcm":
            opts = q["payload"]["options"]
            if len(opts) != 4:
                errors.append(f"{tag} : {len(opts)} propositions au lieu de 4")
            if len(set(opts)) != len(opts):
                errors.append(f"{tag} : propositions en double")
            if not 0 <= q["correct_answer"]["index"] < len(opts):
                errors.append(f"{tag} : index de bonne réponse hors bornes")
        if m == "vrai_faux" and not isinstance(q["correct_answer"]["value"], bool):
            errors.append(f"{tag} : correct_answer.value n'est pas un booléen")
        if m == "chronologie":
            films, order = q["payload"]["films"], q["correct_answer"]["order"]
            if sorted(films) != sorted(order):
                errors.append(f"{tag} : payload.films et correct_answer.order diffèrent")
            if films == order:
                warnings.append(f"{tag} : les titres sont déjà affichés dans l'ordre")
            if len(set(order)) != len(order):
                errors.append(f"{tag} : un titre apparaît deux fois")
        if m == "devinette":
            hints = q["payload"]["hints"]
            if len(hints) < 2:
                errors.append(f"{tag} : {len(hints)} indice(s), il en faut plusieurs")
            answer = norm(q["correct_answer"]["film"])
            for h in hints:
                if answer and answer in norm(h):
                    errors.append(f"{tag} : un indice donne la réponse — « {h} »")
        if m in ("devinette_affiche", "casting", "blindtest"):
            urls = q["payload"].get("actor_photos") or [
                q["payload"].get("poster_url") or q["payload"].get("audio_url")]
            for u in urls:
                if not (u or "").startswith("https://"):
                    errors.append(f"{tag} : URL absente ou non sécurisée")
            if m == "casting" and len(q["payload"]["actor_photos"]) != 3:
                errors.append(f"{tag} : {len(q['payload']['actor_photos'])} photos au lieu de 3")
        if m in NEEDS_CONTEXT and ct == "serie" and not q["prompt"].strip():
            errors.append(f"{tag} : énoncé vide alors que le mode l'affiche seul")

        q["_file"] = path.name
        q["_ct"] = ct
        by_mode[q["mode"]].append(q)

# --- Doublons -------------------------------------------------------------
for mode, rows in by_mode.items():
    seen = {}
    for q in rows:
        if mode == "emoji":
            # Les emoji disparaissent avec la normalisation alphanumérique :
            # on compare l'énoncé tel quel.
            key = q["prompt"].strip()
        elif mode in ("qcm", "vrai_faux", "citation"):
            key = norm(q["prompt"])
        elif mode == "film_melange":
            key = norm(q["correct_answer"]["title"])
        elif mode == "chronologie":
            key = "|".join(sorted(norm(t) for t in q["correct_answer"]["order"]))
        elif mode == "devinette":
            key = norm(" ".join(q["payload"]["hints"]))
        else:
            key = norm(json.dumps(q["payload"], sort_keys=True))
        if key in seen:
            errors.append(f"{mode} : doublon {q['_file']}#{q['id']} == {seen[key]}")
        seen[key] = f"{q['_file']}#{q['id']}"

# --- Tableau de bord ------------------------------------------------------
print(f"{'Mode':<20}{'Total':>6}{'Films':>7}{'Séries':>8}{'Œuvres':>8}")
total = 0
for mode in sorted(by_mode):
    rows = by_mode[mode]
    films = sum(1 for q in rows if q["_ct"] == "film")
    series = len(rows) - films
    works = set()
    for q in rows:
        works |= subjects(q)
    total += len(rows)
    print(f"{mode:<20}{len(rows):>6}{films:>7}{series:>8}{len(works):>8}")
    if len(rows) < 50:
        warnings.append(f"{mode} : {len(rows)} questions, objectif 50")
print(f"{'TOTAL':<20}{total:>6}")

# --- Concentration par franchise ------------------------------------------
print("\nŒuvres/univers les plus représentés :")
univ = collections.Counter()
for rows in by_mode.values():
    for q in rows:
        for s_ in subjects(q):
            univ[s_] += 1
for name, n in univ.most_common(8):
    print(f"   {name:<28}{n:>4}  ({n / total:.1%})")

print("\n--- Erreurs ---")
for e in errors:
    print("  ✗", e)
print("  aucune" if not errors else f"  {len(errors)} erreur(s)")
print("--- Avertissements ---")
for w in warnings:
    print("  ~", w)
print("  aucun" if not warnings else f"  {len(warnings)} avertissement(s)")
sys.exit(1 if errors else 0)
