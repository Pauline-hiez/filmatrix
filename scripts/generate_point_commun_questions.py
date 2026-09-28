"""Génère les questions du mode Point commun depuis les Work déjà en base.

Contrairement aux autres modes (question créée une par une dans l'admin), ce
mode s'appuie sur ce que TMDB fournit déjà via Work (genres, saga, casting) :
pas de saisie manuelle, juste un regroupement des œuvres qui partagent un
trait commun. Trois dimensions couvertes pour cette première version :

- saga (Work.saga, un champ unique par œuvre) : toutes les œuvres qui
  partagent la même collection TMDB.
- genre (Work.genres, une liste par œuvre) : toutes les œuvres qui
  partagent au moins un genre.
- acteur (Work.cast, une liste par œuvre, cf. Work.cast et le script de
  rattrapage scripts/backfill_work_cast.py pour les Work créées avant
  l'ajout de ce champ) : toutes les œuvres où un même acteur figure au
  casting.

Idempotent : chaque groupe (saga, genre ou acteur) ne produit jamais plus
d'une question - la sélection des 3 œuvres montrées est déterministe (triées
par id), donc un deuxième passage retombe sur le même trio et le détecte
déjà généré via _existing_work_id_trios(), sans jamais dupliquer.

    python -m scripts.generate_point_commun_questions
"""
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from filmatrix.extensions import db
from filmatrix.models import Question, Work

MIN_GROUP_SIZE = 3
WORKS_PER_QUESTION = 3
OPTIONS_PER_QUESTION = 4


def _clean_saga_name(saga: str) -> str:
    """Nettoie le suffixe TMDB "Collection", pour un affichage plus naturel
    ("Harry Potter" plutôt que "Harry Potter Collection")."""
    cleaned = saga.removesuffix(" Collection").strip()
    return cleaned or saga


def _saga_groups() -> dict[str, list[Work]]:
    """Œuvres groupées par saga (non nulle), groupes d'au moins MIN_GROUP_SIZE."""
    groups: dict[str, list[Work]] = defaultdict(list)
    for work in Work.query.filter(Work.saga.isnot(None)).all():
        groups[work.saga].append(work)
    return {saga: works for saga, works in groups.items() if len(works) >= MIN_GROUP_SIZE}


def _genre_groups() -> dict[str, list[Work]]:
    """Œuvres groupées par genre (une œuvre peut apparaître dans plusieurs
    groupes, contrairement à _saga_groups), groupes d'au moins MIN_GROUP_SIZE."""
    groups: dict[str, list[Work]] = defaultdict(list)
    for work in Work.query.all():
        for genre in (work.genres or []):
            groups[genre].append(work)
    return {genre: works for genre, works in groups.items() if len(works) >= MIN_GROUP_SIZE}


def _cast_groups() -> dict[str, list[Work]]:
    """Œuvres groupées par acteur (une œuvre peut apparaître dans plusieurs
    groupes, comme _genre_groups), groupes d'au moins MIN_GROUP_SIZE."""
    groups: dict[str, list[Work]] = defaultdict(list)
    for work in Work.query.all():
        for actor in (work.cast or []):
            groups[actor].append(work)
    return {actor: works for actor, works in groups.items() if len(works) >= MIN_GROUP_SIZE}


def _all_known_sagas() -> list[str]:
    return [row[0] for row in db.session.query(Work.saga).filter(Work.saga.isnot(None)).distinct().all()]


def _all_known_genres() -> list[str]:
    genres: set[str] = set()
    for row in db.session.query(Work.genres).all():
        genres.update(row[0] or [])
    return sorted(genres)


def _all_known_actors() -> list[str]:
    actors: set[str] = set()
    for row in db.session.query(Work.cast).all():
        actors.update(row[0] or [])
    return sorted(actors)


def _existing_work_id_trios() -> set[frozenset[int]]:
    """Trios de Work.id déjà utilisés par une question Point commun
    existante : garantit qu'on ne régénère jamais deux fois le même trio."""
    trios: set[frozenset[int]] = set()
    for question in Question.query.filter_by(mode="point_commun").all():
        work_ids = [entry["work_id"] for entry in question.payload.get("works", []) if "work_id" in entry]
        if len(work_ids) == WORKS_PER_QUESTION:
            trios.add(frozenset(work_ids))
    return trios


def _make_question(chosen: list[Work], correct_label: str, decoy_labels: list[str]) -> Question:
    options = decoy_labels + [correct_label]
    random.shuffle(options)
    correct_index = options.index(correct_label)

    content_types = [work.content_type for work in chosen]
    majority_content_type = max(set(content_types), key=content_types.count)

    return Question(
        mode="point_commun",
        prompt="Quel est le point commun entre ces trois œuvres ?",
        payload={
            "works": [
                {
                    "work_id": work.id,
                    "tmdb_id": work.tmdb_id,
                    "content_type": work.content_type,
                    "title": work.title,
                    "poster_url": work.poster_url,
                }
                for work in chosen
            ],
            "options": options,
        },
        correct_answer={"index": correct_index},
        content_type=majority_content_type,
        difficulty="moyen",
    )


def _build_saga_question(saga: str, works: list[Work], all_sagas: list[str]) -> Question | None:
    # Sélection déterministe (triée par id) : condition de l'idempotence, un
    # second passage doit retomber exactement sur le même trio.
    chosen = sorted(works, key=lambda work: work.id)[:WORKS_PER_QUESTION]

    decoy_pool = [candidate for candidate in all_sagas if candidate != saga]
    if len(decoy_pool) < OPTIONS_PER_QUESTION - 1:
        return None
    decoys = random.sample(decoy_pool, OPTIONS_PER_QUESTION - 1)

    correct_label = f"Ils appartiennent tous à la saga {_clean_saga_name(saga)}"
    decoy_labels = [f"Ils appartiennent tous à la saga {_clean_saga_name(d)}" for d in decoys]
    return _make_question(chosen, correct_label, decoy_labels)


def _build_genre_question(genre: str, works: list[Work], all_genres: list[str]) -> Question | None:
    chosen = sorted(works, key=lambda work: work.id)[:WORKS_PER_QUESTION]

    # Anti-ambiguïté : un leurre n'est valide que si AU MOINS UNE des trois
    # œuvres montrées n'a pas ce genre - sinon ce serait, en plus de la bonne
    # réponse, une deuxième réponse tout aussi correcte (contrairement à la
    # saga, une œuvre a plusieurs genres à la fois).
    safe_decoys = [
        candidate
        for candidate in all_genres
        if candidate != genre and any(candidate not in (work.genres or []) for work in chosen)
    ]
    if len(safe_decoys) < OPTIONS_PER_QUESTION - 1:
        return None
    decoys = random.sample(safe_decoys, OPTIONS_PER_QUESTION - 1)

    correct_label = f"Ils ont tous le genre {genre} en commun"
    decoy_labels = [f"Ils ont tous le genre {d} en commun" for d in decoys]
    return _make_question(chosen, correct_label, decoy_labels)


def _build_cast_question(actor: str, works: list[Work], all_actors: list[str]) -> Question | None:
    chosen = sorted(works, key=lambda work: work.id)[:WORKS_PER_QUESTION]

    # Anti-ambiguïté : même principe que le genre - un leurre n'est valide
    # que si au moins une des trois œuvres montrées n'a PAS cet acteur au
    # casting (une œuvre a plusieurs acteurs, comme plusieurs genres).
    safe_decoys = [
        candidate
        for candidate in all_actors
        if candidate != actor and any(candidate not in (work.cast or []) for work in chosen)
    ]
    if len(safe_decoys) < OPTIONS_PER_QUESTION - 1:
        return None
    decoys = random.sample(safe_decoys, OPTIONS_PER_QUESTION - 1)

    correct_label = f"Ils ont tous {actor} au casting"
    decoy_labels = [f"Ils ont tous {d} au casting" for d in decoys]
    return _make_question(chosen, correct_label, decoy_labels)


def generate_point_commun_questions() -> None:
    existing_trios = _existing_work_id_trios()
    all_sagas = _all_known_sagas()
    all_genres = _all_known_genres()
    all_actors = _all_known_actors()

    created_saga = 0
    created_genre = 0
    created_cast = 0
    skipped = 0

    for saga, works in _saga_groups().items():
        question = _build_saga_question(saga, works, all_sagas)
        if question is None:
            skipped += 1
            continue
        work_ids = frozenset(entry["work_id"] for entry in question.payload["works"])
        if work_ids in existing_trios:
            continue
        db.session.add(question)
        db.session.commit()
        existing_trios.add(work_ids)
        created_saga += 1
        print(f"  saga {saga!r} -> question #{question.id}")

    for genre, works in _genre_groups().items():
        question = _build_genre_question(genre, works, all_genres)
        if question is None:
            skipped += 1
            continue
        work_ids = frozenset(entry["work_id"] for entry in question.payload["works"])
        if work_ids in existing_trios:
            continue
        db.session.add(question)
        db.session.commit()
        existing_trios.add(work_ids)
        created_genre += 1
        print(f"  genre {genre!r} -> question #{question.id}")

    for actor, works in _cast_groups().items():
        question = _build_cast_question(actor, works, all_actors)
        if question is None:
            skipped += 1
            continue
        work_ids = frozenset(entry["work_id"] for entry in question.payload["works"])
        if work_ids in existing_trios:
            continue
        db.session.add(question)
        db.session.commit()
        existing_trios.add(work_ids)
        created_cast += 1
        print(f"  acteur {actor!r} -> question #{question.id}")

    print(
        f"\n{created_saga} question(s) saga, {created_genre} question(s) genre, "
        f"{created_cast} question(s) acteur, "
        f"{skipped} groupe(s) ignoré(s) (pas assez de leurres disponibles)."
    )


def main() -> None:
    # Importé ici plutôt qu'en tête de module : le monkey patching gevent de
    # wsgi.py ne doit s'exécuter qu'en lancement direct du script, jamais
    # comme effet de bord d'un import par les tests (même raison que
    # scripts/migrate_questions_to_works.py).
    from wsgi import app

    with app.app_context():
        generate_point_commun_questions()


if __name__ == "__main__":
    main()
