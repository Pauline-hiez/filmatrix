"""Tests de la logique des défis quotidiens."""

from filmatrix.extensions import db
from filmatrix.models import DailyChallenge, Question, Tag, User
from filmatrix.services.daily_challenges import CHALLENGE_TYPES, get_or_create_daily_challenge, update_challenge_progress, STREAK_BONUS_THRESHOLD, update_streak_on_completion

from datetime import date, timedelta


def create_test_user(username: str = "Defieur") -> User:
    """Crée un utilisateur de test en base"""
    user = User(username=username, email=f"{username.lower()}@filmatrix.fr")
    user.set_password("Azerty1!")
    db.session.add(user)
    db.session.commit()
    return user


def test_get_or_create_daily_challenge_creates_one_if_missing(app):
    """Un utilisateur sans défi aujourd'hui doit en voir un créé"""
    with app.app_context():
        user = create_test_user()

        challenge = get_or_create_daily_challenge(user)

        assert challenge.id is not None
        assert challenge.challenge_type in CHALLENGE_TYPES
        assert challenge.progress == 0


def test_get_or_create_daily_challenge_returns_existing_one(app):
    """Appeler deux fois le même jour doit renvoyer le même défi, et non en créer un nouveau"""
    with app.app_context():
        user = create_test_user()

        first_challenge = get_or_create_daily_challenge(user)
        second_challenge = get_or_create_daily_challenge(user)

        assert first_challenge.id == second_challenge.id
        assert DailyChallenge.query.filter_by(user_id=user.id).count() == 1


def test_mode_count_challenge_has_a_target_mode(app):
    """Un défi mode_count doit toujours préciser quel mode est ciblé"""
    with app.app_context():
        user = create_test_user()

        # On force le type pour un test déterministe plutôt que d'attendre
        # que le hasard tombe dessus.
        import filmatrix.services.daily_challenges as daily_challenges_module
        original_choice = daily_challenges_module.random.choice
        daily_challenges_module.random.choice = lambda options: (
            "mode_count" if options == CHALLENGE_TYPES else original_choice(options)
        )

        try:
            challenge = get_or_create_daily_challenge(user)
        finally:
            daily_challenges_module.random.choice = original_choice

        assert challenge.challenge_type == "mode_count"
        assert challenge.target_mode is not None

def create_test_question(mode: str = "qcm", tags: list[Tag] | None = None) -> Question:
    """Crée une question de test, éventuellement liée à des tags"""
    question = Question(
            mode=mode,
            prompt="Question de test",
            payload={},
            correct_answer={"film": "Test"},
            requires_account=False,
        )
    if tags:
        question.tags = tags
    db.session.add(question)
    db.session.commit()
    return question

def force_challenge_type(user, challenge_type: str, **extra_fields) -> DailyChallenge:
    """Crée directement un défi d'un type précis pour un joueur, sans passer par le tirage aléatoire"""
    target_values = {
            "total_count": 8,
            "mode_count": 5,
            "saga_count": 3,
            "streak_count": 3,
        }

    challenge = DailyChallenge(
            user_id=user.id,
            challenge_date=date.today(),
            challenge_type=challenge_type,
            target_value=target_values[challenge_type],
            progress=0,
            **extra_fields,
        )
    db.session.add(challenge)
    db.session.commit()
    return challenge

def test_wrong_answer_does_not_progress_challenge(app):
    """Une réponse incorrecte ne doit jamais faire progresser le défi"""
    with app.app_context():
        user = create_test_user()
        force_challenge_type(user, "total_count")
        question = create_test_question()

        update_challenge_progress(user, question, is_correct=False)

        challenge = DailyChallenge.query.filter_by(user_id=user.id).first()
        assert challenge.progress == 0

def test_total_count_challenge_progresses_on_any_correct_answer(app):
    """Un défi total_count doit progresser à chaque bonne réponse, quel que soit le mode"""
    with app.app_context():
        user = create_test_user()
        force_challenge_type(user, "total_count")
        question = create_test_question(mode="citation")

        update_challenge_progress(user, question, is_correct=True)

        challenge = DailyChallenge.query.filter_by(user_id=user.id).first()
        assert challenge.progress == 1

def test_mode_count_challenge_ignores_wrong_mode(app):
    """Un défi mode_count ne doit progresser que pour son mode cible spécifique"""
    with app.app_context():
        user = create_test_user()
        force_challenge_type(user, "mode_count", target_mode="qcm")
        wrong_mode_question = create_test_question(mode="citation")

        update_challenge_progress(user, wrong_mode_question, is_correct=True)

        challenge = DailyChallenge.query.filter_by(user_id=user.id).first()
        assert challenge.progress == 0

def test_mode_count_challenge_progresses_on_matching_mode(app):
    """Un défi mode_count doit progresser lorsque le mode correspond"""
    with app.app_context():
        user = create_test_user()
        force_challenge_type(user, "mode_count", target_mode="qcm")
        matching_question = create_test_question(mode="qcm")

        update_challenge_progress(user, matching_question, is_correct=True)

        challenge = DailyChallenge.query.filter_by(user_id=user.id).first()
        assert challenge.progress == 1


def test_challenge_completes_when_target_reached(app):
    """L'atteinte de la valeur cible doit marquer le défi comme terminé et le renvoyer"""
    with app.app_context():
        user = create_test_user()
        challenge = force_challenge_type(user, "total_count")
        challenge.progress = challenge.target_value - 1
        db.session.commit()
        question = create_test_question()

        result = update_challenge_progress(user, question, is_correct=True)

        assert result is not None
        assert result.completed_at is not None


def test_challenge_does_not_complete_twice(app):
    """Un défi déjà relevé ne doit pas déclencher une nouvelle tentative"""
    with app.app_context():
        user = create_test_user()
        challenge = force_challenge_type(user, "total_count")
        challenge.progress = challenge.target_value
        challenge.completed_at = db.func.now()
        db.session.commit()
        question = create_test_question()

        result = update_challenge_progress(user, question, is_correct=True)

        assert result is None


def test_streak_count_challenge_reflects_run_streak(app):
    """La progression d'un défi streak_count doit refléter la série d'exécutions transmise, et non s'accumuler"""
    with app.app_context():
        user = create_test_user()
        force_challenge_type(user, "streak_count")
        question = create_test_question()

        update_challenge_progress(user, question, is_correct=True, current_run_streak=2)

        challenge = DailyChallenge.query.filter_by(user_id=user.id).first()
        assert challenge.progress == 2

def test_streak_starts_at_one_for_first_completion(app):
    """Le tout premier défi réussi par un joueur doit porter sa série à 1"""
    with app.app_context():
        user = create_test_user()

        update_streak_on_completion(user)

        assert user.current_streak == 1
        assert user.last_streak_date == date.today()


def test_streak_increments_on_consecutive_day(app):
    """Terminer le lendemain du dernier doit prolonger la série"""
    with app.app_context():
        user = create_test_user()
        user.current_streak = 4
        user.last_streak_date = date.today() - timedelta(days=1)
        db.session.commit()

        update_streak_on_completion(user)

        assert user.current_streak == 5


def test_streak_resets_after_a_missed_day(app):
    """Terminer une session après un intervalle de plus d'un jour doit réinitialiser la série à 1"""
    with app.app_context():
        user = create_test_user()
        user.current_streak = 6
        user.last_streak_date = date.today() - timedelta(days=3)
        db.session.commit()

        update_streak_on_completion(user)

        assert user.current_streak == 1


def test_streak_does_not_double_increment_on_same_day(app):
    """Appeler la fonction deux fois le même jour ne doit pas incrémenter la série deux fois"""
    with app.app_context():
        user = create_test_user()
        user.current_streak = 2
        user.last_streak_date = date.today() - timedelta(days=1)
        db.session.commit()

        update_streak_on_completion(user)
        first_streak = user.current_streak

        update_streak_on_completion(user)
        second_streak = user.current_streak

        assert first_streak == second_streak


def test_streak_bonus_triggers_at_threshold(app):
    """Atteindre exactement le seuil doit déclencher le bonus"""
    with app.app_context():
        user = create_test_user()
        user.current_streak = STREAK_BONUS_THRESHOLD - 1
        user.last_streak_date = date.today() - timedelta(days=1)
        db.session.commit()

        reached_bonus = update_streak_on_completion(user)

        assert reached_bonus is True


def test_streak_bonus_does_not_trigger_below_threshold(app):
    """Une série de victoires inférieure au seuil ne doit pas déclencher le bonus"""
    with app.app_context():
        user = create_test_user()
        user.current_streak = STREAK_BONUS_THRESHOLD - 3
        user.last_streak_date = date.today() - timedelta(days=1)
        db.session.commit()

        reached_bonus = update_streak_on_completion(user)

        assert reached_bonus is False