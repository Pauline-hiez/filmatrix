"""Tests des mini-missions quotidiennes et de la série de connexion."""

from datetime import date, timedelta

from filmatrix.extensions import db
from filmatrix.models import DailyChallenge, Question, Tag, User
from filmatrix.services.daily_challenges import (
    CHALLENGE_TYPES,
    MISSION_COIN_REWARD,
    MISSIONS_PER_DAY,
    MODE_COUNT_TARGET,
    SAGA_COUNT_TARGET,
    STREAK_BONUS_THRESHOLD,
    STREAK_COUNT_TARGET,
    TOTAL_COUNT_TARGET,
    challenge_play_url,
    describe_challenge,
    describe_daily_missions,
    get_or_create_daily_missions,
    update_missions_progress,
    update_streak_on_completion,
)


def create_test_user(username: str = "Defieur") -> User:
    """Crée un utilisateur de test en base"""
    user = User(username=username, email=f"{username.lower()}@filmatrix.fr")
    user.set_password("Azerty1!")
    db.session.add(user)
    db.session.commit()
    return user


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


TARGET_BY_TYPE = {
    "total_count": TOTAL_COUNT_TARGET,
    "mode_count": MODE_COUNT_TARGET,
    "saga_count": SAGA_COUNT_TARGET,
    "streak_count": STREAK_COUNT_TARGET,
}


def force_mission(user, challenge_type: str, slot: int = 0, **extra_fields) -> DailyChallenge:
    """Crée directement une mini-mission d'un type précis, à un slot donné,
    sans passer par le tirage aléatoire. Plusieurs missions du même joueur le
    même jour doivent avoir des slots différents (contrainte d'unicité)."""
    mission = DailyChallenge(
            user_id=user.id,
            challenge_date=date.today(),
            slot=slot,
            challenge_type=challenge_type,
            target_value=extra_fields.pop("target_value", TARGET_BY_TYPE[challenge_type]),
            progress=0,
            **extra_fields,
        )
    db.session.add(mission)
    db.session.commit()
    return mission


def force_daily_missions(user, overrides: dict[str, dict] | None = None) -> dict[str, DailyChallenge]:
    """Crée les 3 mini-missions du jour d'un joueur (total_count, mode_count,
    streak_count), sans passer par le tirage aléatoire.

    get_or_create_daily_missions attend toujours exactement 3 lignes pour un
    jour donné (les 3 sont créées ensemble en production) : un test qui
    n'utilise force_mission que pour une seule déclencherait une tentative de
    génération des 2 manquantes, en collision avec le slot déjà occupé.
    `overrides` personnalise les champs d'un type donné (ex. target_value)."""
    overrides = overrides or {}
    specs = [
        ("total_count", {}),
        ("mode_count", {"target_mode": "qcm"}),
        ("streak_count", {}),
    ]
    missions = {}
    for slot, (challenge_type, defaults) in enumerate(specs):
        fields = {**defaults, **overrides.get(challenge_type, {})}
        missions[challenge_type] = force_mission(user, challenge_type, slot=slot, **fields)
    return missions


# ---- Génération des missions du jour --------------------------------------

def test_get_or_create_daily_missions_creates_three(app):
    """Un joueur sans mission aujourd'hui doit s'en voir créer exactement 3."""
    with app.app_context():
        user = create_test_user()

        missions = get_or_create_daily_missions(user)

        assert len(missions) == MISSIONS_PER_DAY
        for mission in missions:
            assert mission.id is not None
            assert mission.challenge_type in CHALLENGE_TYPES
            assert mission.progress == 0


def test_daily_missions_have_distinct_types(app):
    """Les 3 missions d'un jour ne doivent jamais porter sur le même critère
    (ex. deux fois total_count), sous peine de doublon plutôt que de variété."""
    with app.app_context():
        user = create_test_user()

        missions = get_or_create_daily_missions(user)

        types = [mission.challenge_type for mission in missions]
        assert len(set(types)) == len(types)


def test_get_or_create_daily_missions_returns_existing_ones(app):
    """Appeler deux fois le même jour doit renvoyer les mêmes missions, pas en créer de nouvelles."""
    with app.app_context():
        user = create_test_user()

        first = get_or_create_daily_missions(user)
        second = get_or_create_daily_missions(user)

        assert [mission.id for mission in first] == [mission.id for mission in second]
        assert DailyChallenge.query.filter_by(user_id=user.id).count() == MISSIONS_PER_DAY


def test_mode_count_mission_has_a_target_mode(app, monkeypatch):
    """Une mission mode_count doit toujours préciser quel mode est ciblé"""
    with app.app_context():
        user = create_test_user()

        # Le tirage passe par une instance random.Random dédiée
        # (_daily_random), pas par le module random global.
        import filmatrix.services.daily_challenges as daily_challenges_module

        class FixedRandom:
            def sample(self, population, count):
                return list(population)[:count]

            def choice(self, options):
                return options[0]

        monkeypatch.setattr(daily_challenges_module, "_daily_random", lambda today: FixedRandom())

        missions = get_or_create_daily_missions(user)

        mode_count_missions = [m for m in missions if m.challenge_type == "mode_count"]
        assert len(mode_count_missions) == 1
        assert mode_count_missions[0].target_mode is not None


def test_same_day_missions_are_identical_for_every_player(app):
    """Les mini-missions du jour doivent avoir les mêmes paramètres pour tous
    les joueurs : seule la progression leur est propre, pas le tirage."""
    with app.app_context():
        first_user = create_test_user("Premier")
        second_user = create_test_user("Second")

        first_missions = get_or_create_daily_missions(first_user)
        second_missions = get_or_create_daily_missions(second_user)

        for first, second in zip(first_missions, second_missions):
            assert first.challenge_type == second.challenge_type
            assert first.target_value == second.target_value
            assert first.target_mode == second.target_mode
            assert first.target_tag_id == second.target_tag_id


# ---- Progression --------------------------------------------------------

def test_wrong_answer_does_not_progress_missions(app):
    """Une réponse incorrecte ne doit jamais faire progresser une mission"""
    with app.app_context():
        user = create_test_user()
        force_mission(user, "total_count", slot=0)
        question = create_test_question()

        update_missions_progress(user, question, is_correct=False)

        mission = DailyChallenge.query.filter_by(user_id=user.id).first()
        assert mission.progress == 0


def test_total_count_mission_progresses_on_any_correct_answer(app):
    """Une mission total_count doit progresser à chaque bonne réponse, quel que soit le mode"""
    with app.app_context():
        user = create_test_user()
        missions = force_daily_missions(user)
        question = create_test_question(mode="citation")

        update_missions_progress(user, question, is_correct=True)

        db.session.refresh(missions["total_count"])
        assert missions["total_count"].progress == 1


def test_mode_count_mission_ignores_wrong_mode(app):
    """Une mission mode_count ne doit progresser que pour son mode cible"""
    with app.app_context():
        user = create_test_user()
        missions = force_daily_missions(user)
        wrong_mode_question = create_test_question(mode="citation")

        update_missions_progress(user, wrong_mode_question, is_correct=True)

        db.session.refresh(missions["mode_count"])
        assert missions["mode_count"].progress == 0


def test_mode_count_mission_progresses_on_matching_mode(app):
    """Une mission mode_count doit progresser lorsque le mode correspond"""
    with app.app_context():
        user = create_test_user()
        missions = force_daily_missions(user)
        matching_question = create_test_question(mode="qcm")

        update_missions_progress(user, matching_question, is_correct=True)

        db.session.refresh(missions["mode_count"])
        assert missions["mode_count"].progress == 1


def test_streak_count_mission_reflects_run_streak(app):
    """La progression d'une mission streak_count doit refléter la série
    d'exécutions transmise, et non s'accumuler"""
    with app.app_context():
        user = create_test_user()
        missions = force_daily_missions(user)
        question = create_test_question(mode="devinette")

        update_missions_progress(user, question, is_correct=True, current_run_streak=2)

        db.session.refresh(missions["streak_count"])
        assert missions["streak_count"].progress == 2


def test_mission_completes_when_target_reached(app):
    """L'atteinte de la valeur cible doit marquer la mission comme terminée
    et la renvoyer parmi les missions nouvellement complétées"""
    with app.app_context():
        user = create_test_user()
        missions = force_daily_missions(user)
        total_mission = missions["total_count"]
        total_mission.progress = total_mission.target_value - 1
        db.session.commit()
        question = create_test_question(mode="devinette")

        newly_completed, day_completed = update_missions_progress(user, question, is_correct=True)

        assert len(newly_completed) == 1
        assert newly_completed[0].challenge_type == "total_count"
        assert newly_completed[0].completed_at is not None
        # Une seule mission sur trois : la journée n'est pas encore complète.
        assert day_completed is False


def test_mission_does_not_complete_twice(app):
    """Une mission déjà relevée ne doit pas redéclencher une complétion"""
    with app.app_context():
        user = create_test_user()
        missions = force_daily_missions(user)
        total_mission = missions["total_count"]
        total_mission.progress = total_mission.target_value
        total_mission.completed_at = db.func.now()
        db.session.commit()
        question = create_test_question(mode="devinette")

        newly_completed, day_completed = update_missions_progress(user, question, is_correct=True)

        assert newly_completed == []
        assert day_completed is False


def test_single_answer_can_complete_several_missions_at_once(app):
    """Une réponse qui satisfait plusieurs critères en même temps doit
    compléter toutes les missions concernées en un seul appel."""
    with app.app_context():
        user = create_test_user()
        tag = Tag(name="Men In Black", tag_type="univers")
        db.session.add(tag)
        db.session.commit()

        force_mission(user, "total_count", slot=0, target_value=1)
        force_mission(user, "mode_count", slot=1, target_mode="qcm", target_value=1)
        force_mission(user, "saga_count", slot=2, target_tag_id=tag.id, target_value=1)

        question = create_test_question(mode="qcm", tags=[tag])

        newly_completed, day_completed = update_missions_progress(user, question, is_correct=True)

        assert len(newly_completed) == 3
        assert day_completed is True


# ---- Journée complète (fragment garanti + série) -------------------------

def test_day_not_completed_until_all_missions_done(app):
    """La journée n'est marquée complète que si les 3 missions le sont"""
    with app.app_context():
        user = create_test_user()
        force_mission(user, "total_count", slot=0, target_value=1)
        force_mission(user, "mode_count", slot=1, target_mode="citation", target_value=1)
        force_mission(user, "streak_count", slot=2, target_value=5)

        question = create_test_question(mode="qcm")

        _, day_completed = update_missions_progress(user, question, is_correct=True)

        assert day_completed is False


def test_day_completed_exactly_once(app):
    """Une fois les 3 missions complétées, une réponse supplémentaire ne doit
    plus redéclencher day_completed (déjà passé à True une première fois)."""
    with app.app_context():
        user = create_test_user()
        for slot in range(3):
            mission = force_mission(user, "total_count", slot=slot, target_value=1)
            mission.completed_at = db.func.now()
            db.session.commit()

        question = create_test_question(mode="qcm")
        _, day_completed_again = update_missions_progress(user, question, is_correct=True)

        assert day_completed_again is False


# ---- Série de connexion (avance seulement quand la journée est complète) --

def test_streak_starts_at_one_for_first_completion(app):
    """La toute première journée réussie par un joueur doit porter sa série à 1"""
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
    """Une série inférieure au seuil ne doit pas déclencher le bonus"""
    with app.app_context():
        user = create_test_user()
        user.current_streak = STREAK_BONUS_THRESHOLD - 3
        user.last_streak_date = date.today() - timedelta(days=1)
        db.session.commit()

        reached_bonus = update_streak_on_completion(user)

        assert reached_bonus is False


# ---- Description pour l'affichage -----------------------------------------

def test_describe_challenge_includes_coin_reward(app):
    """La description d'une mission doit indiquer la récompense en pièces,
    pour l'afficher et l'annoncer côté client."""
    with app.test_request_context():
        user = create_test_user()
        mission = force_mission(user, "total_count", slot=0)

        info = describe_challenge(mission)

        assert info["coin_reward"] == MISSION_COIN_REWARD


def test_describe_daily_missions_reports_progress_summary(app):
    """La vue d'ensemble doit compter les missions complétées et signaler
    quand toutes le sont."""
    with app.test_request_context():
        user = create_test_user()
        force_mission(user, "total_count", slot=0, target_value=1).completed_at = db.func.now()
        force_mission(user, "mode_count", slot=1, target_mode="qcm")
        force_mission(user, "streak_count", slot=2)
        db.session.commit()

        summary = describe_daily_missions(user)

        assert summary["total_count"] == 3
        assert summary["completed_count"] == 1
        assert summary["all_completed"] is False
        assert len(summary["missions"]) == 3


# ---- URL de lancement direct -----------------------------------------------

def test_play_url_targets_the_mode_directly_for_mode_count(app):
    """Une mission mode_count doit lancer directement une partie dans ce
    mode, sans repasser par l'écran de préparation."""
    with app.test_request_context():
        user = create_test_user("Mode")
        mission = force_mission(user, "mode_count", slot=0, target_mode="blindtest")

        url = challenge_play_url(mission)

        assert url == "/quiz/blindtest/1"


def test_play_url_targets_mixed_mode_filtered_on_the_saga_for_saga_count(app):
    """Une mission saga_count doit lancer le mode mixte filtré sur cette
    saga : le tirage entier s'y limite, garantissant assez de questions (la
    saga a déjà été vérifiée éligible à la génération de la mission)."""
    with app.app_context():
        tag = Tag(name="Men In Black", tag_type="univers")
        db.session.add(tag)
        db.session.commit()
        tag_id = tag.id

    with app.test_request_context():
        user = create_test_user("Saga")
        mission = force_mission(user, "saga_count", slot=0, target_tag_id=tag_id)

        url = challenge_play_url(mission)

        assert url == f"/quiz/mixte/1?tag_id={tag_id}"


def test_play_url_targets_mixed_mode_without_filter_for_total_and_streak(app):
    """total_count et streak_count acceptent n'importe quelle question :
    aucun filtre à appliquer, juste lancer le mode mixte."""
    with app.test_request_context():
        user = create_test_user("Generique")
        mission = force_mission(user, "total_count", slot=0)

        assert challenge_play_url(mission) == "/quiz/mixte/1"


# ---- Intégration bout en bout (route /quiz) -------------------------------

def login(client, email: str, password: str = "Azerty1!") -> None:
    client.post("/connexion", data={"email": email, "password": password})


def create_playable_qcm() -> Question:
    """Crée une vraie question QCM jouable via la route (options + index),
    contrairement à create_test_question qui sert aux appels directs au
    service et n'a pas la forme attendue par check_answer pour ce mode."""
    question = Question(
        mode="qcm",
        prompt="Question test",
        payload={"options": ["Bonne", "Mauvaise"]},
        correct_answer={"index": 0},
        requires_account=False,
    )
    db.session.add(question)
    db.session.commit()
    return question


def start_run_session(client, question_id: int, mode: str = "qcm") -> None:
    with client.session_transaction() as session:
        session["run"] = {
            "mode": mode,
            "correct": 0,
            "answered": [],
            "xp": 0,
            "coins": 0,
            "questions": [question_id],
            "filters": {},
        }


def test_completing_a_mission_is_announced_in_the_answer_response(client, app):
    """La réponse JSON qui complète une mini-mission doit la lister dans
    completed_missions, pour la notification affichée pendant la partie."""
    with app.app_context():
        user = create_test_user("Complet")
        force_mission(user, "total_count", slot=0, target_value=1)
        force_mission(user, "mode_count", slot=1, target_mode="citation", target_value=1)
        force_mission(user, "streak_count", slot=2, target_value=5)
        question = create_playable_qcm()
        question_id = question.id

    login(client, "complet@filmatrix.fr")
    start_run_session(client, question_id)

    result = client.post("/quiz/qcm/1", data={"answer": "0"}).get_json()

    assert len(result["completed_missions"]) == 1
    assert result["completed_missions"][0]["is_completed"] is True
    assert result["day_completed"] is False


def test_incomplete_mission_progress_is_not_announced(client, app):
    """Une réponse qui fait progresser une mission sans la terminer ne doit rien annoncer."""
    with app.app_context():
        user = create_test_user("Incomplet")
        force_mission(user, "total_count", slot=0, target_value=5)
        force_mission(user, "mode_count", slot=1, target_mode="citation")
        force_mission(user, "streak_count", slot=2)
        question = create_playable_qcm()
        question_id = question.id

    login(client, "incomplet@filmatrix.fr")
    start_run_session(client, question_id)

    result = client.post("/quiz/qcm/1", data={"answer": "0"}).get_json()

    assert result["completed_missions"] == []
    assert result["day_completed"] is False
    assert result["streak_bonus"] is None


def test_completing_a_mission_awards_coins_immediately(client, app):
    """Compléter une mini-mission doit créditer les pièces tout de suite,
    sans attendre la fin de la journée — en plus des pièces gagnées pour la
    bonne réponse elle-même, qui restent indépendantes de la mission."""
    with app.app_context():
        user = create_test_user("Pieces")
        starting_coins = user.coins
        force_mission(user, "total_count", slot=0, target_value=1)
        force_mission(user, "mode_count", slot=1, target_mode="citation", target_value=1)
        force_mission(user, "streak_count", slot=2, target_value=5)
        question = create_playable_qcm()
        question_id = question.id

    login(client, "pieces@filmatrix.fr")
    start_run_session(client, question_id)

    client.post("/quiz/qcm/1", data={"answer": "0"})

    with app.app_context():
        refreshed = User.query.filter_by(username="Pieces").first()
        gained = refreshed.coins - starting_coins
        # Au moins la récompense de la mission, en plus de la récompense de
        # la bonne réponse (dont le montant exact dépend du niveau par défaut,
        # non testé ici) : la mission ne doit jamais se substituer à elle.
        assert gained >= MISSION_COIN_REWARD
        assert gained > MISSION_COIN_REWARD  # la bonne réponse rapporte aussi ses propres pièces


def test_day_completed_and_streak_bonus_announced_together(client, app):
    """Une réponse qui termine les 3 missions du jour d'un coup doit annoncer
    day_completed et, si le palier est atteint, le bonus de série."""
    with app.app_context():
        user = create_test_user("Serie")
        user.current_streak = STREAK_BONUS_THRESHOLD - 1
        user.last_streak_date = date.today() - timedelta(days=1)
        tag = Tag(name="Men In Black", tag_type="univers")
        db.session.add(tag)
        db.session.commit()

        force_mission(user, "total_count", slot=0, target_value=1)
        force_mission(user, "mode_count", slot=1, target_mode="qcm", target_value=1)
        force_mission(user, "saga_count", slot=2, target_tag_id=tag.id, target_value=1)

        question = Question(
            mode="qcm",
            prompt="Question test",
            payload={"options": ["Bonne", "Mauvaise"]},
            correct_answer={"index": 0},
            requires_account=False,
        )
        question.tags = [tag]
        db.session.add(question)
        db.session.commit()
        question_id = question.id

    login(client, "serie@filmatrix.fr")
    start_run_session(client, question_id)

    result = client.post("/quiz/qcm/1", data={"answer": "0"}).get_json()

    assert len(result["completed_missions"]) == 3
    assert result["day_completed"] is True
    assert result["streak_bonus"] == {"streak": STREAK_BONUS_THRESHOLD}


def test_profile_page_shows_daily_missions(client, app):
    """La page de profil doit afficher les mini-missions du jour, leur
    progression et la série de connexion."""
    with app.app_context():
        user = create_test_user("Visible")
        user.current_streak = 3
        db.session.add(user)
        db.session.commit()
        mission = force_mission(user, "total_count", slot=0, target_value=1)
        mission.progress = 1
        mission.completed_at = db.func.now()
        force_mission(user, "mode_count", slot=1, target_mode="qcm")
        force_mission(user, "streak_count", slot=2)
        db.session.commit()

    login(client, "visible@filmatrix.fr")

    page = client.get("/profil").get_data(as_text=True)

    assert "Mini-missions" in page
    assert "1/3" in page
    assert "🔥 3" in page


def test_home_page_shows_daily_missions_for_logged_in_players(client, app):
    """Les mini-missions doivent aussi apparaître sur l'accueil."""
    with app.app_context():
        user = create_test_user("Accueil")
        db.session.add(user)
        db.session.commit()
        force_mission(user, "mode_count", slot=0, target_mode="blindtest")
        force_mission(user, "total_count", slot=1)
        force_mission(user, "streak_count", slot=2)

    login(client, "accueil@filmatrix.fr")

    page = client.get("/").get_data(as_text=True)

    assert "Mini-missions" in page
    assert "data-challenge-countdown" in page
    assert "js/challenge_countdown.js" in page


def test_home_page_hides_daily_missions_for_visitors(client):
    """Un visiteur non connecté n'a pas de mission : la carte ne doit pas apparaître."""
    page = client.get("/").get_data(as_text=True)

    assert "Mini-missions" not in page
