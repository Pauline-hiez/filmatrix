"""Publication de contenu créé en local vers la base de production : questions,
scènes Cache-Ciné et cas Scène Mystère.

Le déploiement (git push -> Render) ne touche jamais au contenu, seulement au
code et au schéma de la base (scripts/prepare_db.py ne fait que les
migrations) : un contenu créé dans l'admin local y reste bloqué tant que
personne ne le recopie côté prod. Ce module fait cette recopie - jamais rien
n'est supprimé ni modifié côté prod, seul du contenu manquant y est ajouté."""

import os

import psycopg2
import psycopg2.extras

from filmatrix.models import CacheCineScene, MysteryCase, Question

# Seuls les modes dont la réponse porte un titre de film identifiable
# ("film" dans correct_answer) peuvent être comparés de façon fiable à la
# prod pour repérer les doublons. qcm, vrai_faux, chronologie, film_melange
# et emoji n'ont pas de clé équivalente et restent hors de cet outil - ils
# passent par data/questions/*.json comme avant.
PUBLISHABLE_MODES = ("citation", "devinette", "devinette_affiche", "casting", "blindtest", "dialogue")


def _film_title(question: Question) -> str | None:
    return (question.correct_answer or {}).get("film")


def is_local_environment() -> bool:
    """True si ce processus tourne en local, False s'il s'agit de l'instance
    déployée elle-même.

    DATABASE_URL n'est jamais définie en local (SQLite par défaut, voir
    resolve_database_uri dans filmatrix/__init__.py) - seul Render l'injecte
    au déploiement. Sert à cacher la section "Publier vers la prod" une fois
    en prod : elle n'y aurait aucun sens (publier la prod vers elle-même)."""
    return not os.environ.get("DATABASE_URL")


def prod_connection():
    """Ouvre une connexion à la base de production.

    Lève une erreur explicite plutôt qu'un traceback brut si la variable
    d'environnement manque, ou si l'app tourne déjà contre la prod (auquel
    cas il n'y a par définition rien à lui "publier" depuis elle-même)."""
    if not is_local_environment():
        raise RuntimeError("L'application est déjà connectée à la base de production.")

    prod_url = os.environ.get("PROD_DATABASE_URL")
    if not prod_url:
        raise RuntimeError("PROD_DATABASE_URL n'est pas définie dans .env.")

    return psycopg2.connect(prod_url)


def find_publishable_questions() -> list[Question]:
    """Questions locales, d'un mode comparable, absentes de la production."""
    candidates = [
        question
        for question in Question.query.filter(Question.mode.in_(PUBLISHABLE_MODES))
        .order_by(Question.mode, Question.id)
        .all()
        if _film_title(question)
    ]
    if not candidates:
        return []

    conn = prod_connection()
    try:
        cur = conn.cursor()
        existing = set()
        for mode in PUBLISHABLE_MODES:
            cur.execute("SELECT correct_answer->>'film' FROM questions WHERE mode = %s", (mode,))
            existing.update((mode, film) for (film,) in cur.fetchall())
        cur.close()
    finally:
        conn.close()

    return [
        question for question in candidates
        if (question.mode, _film_title(question)) not in existing
    ]


def publish_questions(question_ids: list[int]) -> dict:
    """Publie les questions demandées vers la prod, avec leurs tags.

    Tout ou rien : une seule transaction, annulée entièrement en cas
    d'erreur plutôt que de laisser une publication à moitié faite."""
    questions = Question.query.filter(Question.id.in_(question_ids)).all()

    conn = prod_connection()
    conn.autocommit = False
    cur = conn.cursor()
    inserted = []
    tags_created = 0
    try:
        cur.execute("SELECT id, tag_type, name FROM tags")
        tag_cache = {(tag_type, name): tag_id for tag_id, tag_type, name in cur.fetchall()}

        for question in questions:
            cur.execute(
                """INSERT INTO questions
                   (mode, prompt, payload, correct_answer, content_type, difficulty)
                   VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                (
                    question.mode,
                    question.prompt,
                    psycopg2.extras.Json(question.payload),
                    psycopg2.extras.Json(question.correct_answer),
                    question.content_type,
                    question.difficulty,
                ),
            )
            new_id = cur.fetchone()[0]

            for tag in question.tags:
                key = (tag.tag_type, tag.name)
                if key not in tag_cache:
                    cur.execute(
                        "INSERT INTO tags (name, tag_type) VALUES (%s, %s) RETURNING id",
                        (tag.name, tag.tag_type),
                    )
                    tag_cache[key] = cur.fetchone()[0]
                    tags_created += 1
                cur.execute(
                    "INSERT INTO question_tags (question_id, tag_id) VALUES (%s, %s)",
                    (new_id, tag_cache[key]),
                )

            inserted.append({
                "local_id": question.id,
                "prod_id": new_id,
                "film": _film_title(question),
                "mode": question.mode,
            })

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    return {"inserted": inserted, "tags_created": tags_created}


def find_publishable_cache_cine_scenes() -> list[CacheCineScene]:
    """Scènes Cache-Ciné locales absentes de la production.

    Comparées par image_url plutôt que par titre : chaque image est envoyée
    sous un nom généré (uuid4, voir _save_special_game_image), donc unique
    par construction - contrairement au titre, jamais garanti sans doublon."""
    candidates = [scene for scene in CacheCineScene.query.order_by(CacheCineScene.id).all() if scene.image_url]
    if not candidates:
        return []

    conn = prod_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT image_url FROM cache_cine_scenes")
        existing = {row[0] for row in cur.fetchall()}
        cur.close()
    finally:
        conn.close()

    return [scene for scene in candidates if scene.image_url not in existing]


def find_publishable_mystery_cases() -> list[MysteryCase]:
    """Cas Scène Mystère locaux absents de la production (même logique que
    find_publishable_cache_cine_scenes, comparaison par image_url)."""
    candidates = [case for case in MysteryCase.query.order_by(MysteryCase.id).all() if case.image_url]
    if not candidates:
        return []

    conn = prod_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT image_url FROM mystery_cases")
        existing = {row[0] for row in cur.fetchall()}
        cur.close()
    finally:
        conn.close()

    return [case for case in candidates if case.image_url not in existing]


def publish_cache_cine_scenes(scene_ids: list[int]) -> dict:
    """Publie les scènes Cache-Ciné demandées, avec leurs références cachées.

    L'image elle-même n'a rien à faire migrer : local et prod pointent vers
    le même bucket R2 (mêmes identifiants dans .env), seule la ligne de base
    manque côté prod."""
    scenes = CacheCineScene.query.filter(CacheCineScene.id.in_(scene_ids)).all()

    conn = prod_connection()
    conn.autocommit = False
    cur = conn.cursor()
    inserted = []
    try:
        for scene in scenes:
            cur.execute(
                """INSERT INTO cache_cine_scenes
                   (title, image_url, difficulty, time_limit_seconds, is_active, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                (
                    scene.title,
                    scene.image_url,
                    scene.difficulty,
                    scene.time_limit_seconds,
                    scene.is_active,
                    scene.created_at,
                ),
            )
            new_scene_id = cur.fetchone()[0]

            for ref in sorted(scene.references, key=lambda r: r.order_index):
                cur.execute(
                    """INSERT INTO cache_cine_references
                       (scene_id, title, pos_x, pos_y, width, height, order_index)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (new_scene_id, ref.title, ref.pos_x, ref.pos_y, ref.width, ref.height, ref.order_index),
                )

            inserted.append({"local_id": scene.id, "prod_id": new_scene_id, "title": scene.title})

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    return {"inserted": inserted}


def publish_mystery_cases(case_ids: list[int]) -> dict:
    """Publie les cas Scène Mystère demandés, avec leurs zones et options."""
    cases = MysteryCase.query.filter(MysteryCase.id.in_(case_ids)).all()

    conn = prod_connection()
    conn.autocommit = False
    cur = conn.cursor()
    inserted = []
    try:
        for case in cases:
            cur.execute(
                """INSERT INTO mystery_cases
                   (image_url, difficulty, time_limit_seconds, is_active, created_at)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                (case.image_url, case.difficulty, case.time_limit_seconds, case.is_active, case.created_at),
            )
            new_case_id = cur.fetchone()[0]

            for zone in sorted(case.zones, key=lambda z: z.order_index):
                cur.execute(
                    """INSERT INTO mystery_zones
                       (case_id, pos_x, pos_y, width, height, clue_text, order_index)
                       VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                    (new_case_id, zone.pos_x, zone.pos_y, zone.width, zone.height, zone.clue_text, zone.order_index),
                )
                new_zone_id = cur.fetchone()[0]

                for option in sorted(zone.options, key=lambda o: o.order_index):
                    cur.execute(
                        """INSERT INTO mystery_options (zone_id, label, is_correct, order_index)
                           VALUES (%s, %s, %s, %s)""",
                        (new_zone_id, option.label, option.is_correct, option.order_index),
                    )

            inserted.append({"local_id": case.id, "prod_id": new_case_id})

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    return {"inserted": inserted}
