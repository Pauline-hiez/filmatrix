"""Publication de questions créées en local vers la base de production.

Le déploiement (git push -> Render) ne touche jamais au contenu, seulement au
code et au schéma de la base (scripts/prepare_db.py ne fait que les
migrations) : une question créée dans l'admin local y reste bloquée tant que
personne ne la recopie côté prod. Ce module fait cette recopie - jamais rien
n'est supprimé ni modifié côté prod, seules des questions manquantes y sont
ajoutées."""

import os

import psycopg2
import psycopg2.extras

from filmatrix.models import Question

# Seuls les modes dont la réponse porte un titre de film identifiable
# ("film" dans correct_answer) peuvent être comparés de façon fiable à la
# prod pour repérer les doublons. qcm, vrai_faux, chronologie, film_melange
# et emoji n'ont pas de clé équivalente et restent hors de cet outil - ils
# passent par data/questions/*.json comme avant.
PUBLISHABLE_MODES = ("citation", "devinette", "devinette_affiche", "casting", "blindtest", "dialogue")


def _film_title(question: Question) -> str | None:
    return (question.correct_answer or {}).get("film")


def prod_connection():
    """Ouvre une connexion à la base de production.

    Lève une erreur explicite plutôt qu'un traceback brut si la variable
    d'environnement manque, ou si l'app tourne déjà contre la prod (auquel
    cas il n'y a par définition rien à lui "publier" depuis elle-même)."""
    prod_url = os.environ.get("PROD_DATABASE_URL")
    if not prod_url:
        raise RuntimeError("PROD_DATABASE_URL n'est pas définie dans .env.")

    if os.environ.get("DATABASE_URL") == prod_url:
        raise RuntimeError("L'application est déjà connectée à la base de production.")

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
                   (mode, prompt, payload, correct_answer, requires_account, content_type, difficulty)
                   VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (
                    question.mode,
                    question.prompt,
                    psycopg2.extras.Json(question.payload),
                    psycopg2.extras.Json(question.correct_answer),
                    question.requires_account,
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
