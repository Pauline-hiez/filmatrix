"""Modèles de données du moteur de jeu Filmatrix"""

from filmatrix.extensions import db
from flask_login import UserMixin
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime


class Question(db.Model):
    """Représente une question générique, quel que soit son mode de jeu.

    Le champ `payload` contient les données propres au mode (ex: les 4
    options d'un QCM). Le champ `correct_answer` contient la bonne
    réponse, dans un format adapté au mode
    """

    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    mode = db.Column(db.String(50), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    payload = db.Column(db.JSON, nullable=False)
    correct_answer = db.Column(db.JSON, nullable=False)
    content_type = db.Column(db.String(10), nullable=False, default="film")
    difficulty = db.Column(db.String(20), nullable=False, default="moyen")
    work_id = db.Column(db.Integer, db.ForeignKey("works.id"), nullable=True)

    work = db.relationship("Work", backref="questions")

class User(db.Model, UserMixin):
    """Représente un compte joueur"""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    __table_args__ = (
        db.Index("uq_users_username_lower", func.lower(username), unique=True),
    )
    password_hash = db.Column(db.String(255), nullable=False)
    total_xp = db.Column(db.Integer, nullable=False, default=0)
    coins = db.Column(db.Integer, nullable=False, default=0)
    equipped_title = db.Column(db.String(50), nullable=True)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    avatar = db.Column(db.String(10), nullable=True)
    bio = db.Column(db.String(280), nullable=True)
    last_fragment_earned_at = db.Column(db.DateTime, nullable=True)
    current_streak = db.Column(db.Integer, nullable=False, default=0)
    last_streak_date = db.Column(db.Date, nullable=True)
    # Ressource des Jeux Spéciaux (catégorie à part des modes classiques,
    # voir filmatrix/special_games.py) : consommée au lancement d'une partie,
    # jamais achetable, gagnée au palier de série de connexion
    # (STREAK_BONUS_THRESHOLD, services/daily_challenges.py) et tous les
    # CORRECT_ANSWERS_PER_TICKET bonnes réponses (filmatrix/special_games.py).
    golden_tickets = db.Column(db.Integer, nullable=False, default=0)
    # Compteur cumulatif, tous modes et toutes questions confondus (y compris
    # les répétitions) : source du second chemin d'obtention d'un Ticket
    # d'Or, indépendant de la série de connexion — récompense le volume de
    # jeu plutôt que la régularité quotidienne.
    total_correct_answers = db.Column(db.Integer, nullable=False, default=0)

    def set_password(self, password: str) -> None:
        "Hash le mot de passe fourni et le stocke (jamais en clair)"
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password: str) -> bool:
        """Vérifie qu'un mot de passe correspond au hash stocké"""
        return check_password_hash(self.password_hash, password)

class Attempt(db.Model):
    """Représente une réponse donnée par un joueur à une question"""

    __tablename__ = "attempts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    answered_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # XP réellement crédité par cette tentative (0 pour une mauvaise réponse ou
    # une question déjà réussie avant). Sert au classement par période : le
    # total cumulé sur User ne dit pas quand ces points ont été gagnés.
    earned_xp = db.Column(db.Integer, nullable=False, default=0)
    question = db.relationship("Question")
    user = db.relationship("User", backref="attempts")

class UserBadge(db.Model):
    """Représente un badge obtenu par un joueur"""
    __tablename__ = "user_badges"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    badge_code = db.Column(db.String(50), nullable = False)
    earned_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", backref="badges")

class UserTitle(db.Model):
    """Représente un titre possédé par un utilisateur"""

    __tablename__ = "user_titles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title_code = db.Column(db.String(50), nullable=False)
    purchassed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", backref="titles")

class Report(db.Model):
    """Représente un signalement fait par un joueur sur une question"""

    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    reason = db.Column(db.String(50), nullable=False)
    is_resolved = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", backref="reports")
    question = db.relationship("Question", backref="reports")

submission_tags = db.Table(
    "submission_tags",
    db.Column("submission_id", db.Integer, db.ForeignKey("question_submissions.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id"), primary_key=True),
)

submission_reviewed_tags = db.Table(
    "submission_reviewed_tags",
    db.Column("submission_id", db.Integer, db.ForeignKey("question_submissions.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id"), primary_key=True),
)

class QuestionSubmission(db.Model):
    """Représente une question proposée par un joueur, en attente de revue admin.

    Séparée de Question (plutôt qu'un statut dessus) pour qu'il soit
    structurellement impossible qu'un contenu non approuvé fuite dans
    build_question_query / le tirage de parties, appelés depuis de
    nombreux endroits.
    """

    __tablename__ = "question_submissions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending | approved | rejected

    # Champs originaux soumis par le joueur - jamais modifiés après coup,
    # même si un admin corrige avant publication (voir reviewed_*).
    mode = db.Column(db.String(50), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    payload = db.Column(db.JSON, nullable=False)
    correct_answer = db.Column(db.JSON, nullable=False)
    content_type = db.Column(db.String(10), nullable=False, default="film")
    difficulty = db.Column(db.String(20), nullable=False, default="moyen")

    # Retouches admin avant publication (approbation avec modifications) :
    # champs distincts pour que l'historique du joueur montre toujours ce
    # qu'il a réellement soumis, jamais une version modifiée en silence.
    was_edited_by_admin = db.Column(db.Boolean, nullable=False, default=False)
    reviewed_prompt = db.Column(db.Text, nullable=True)
    reviewed_payload = db.Column(db.JSON, nullable=True)
    reviewed_correct_answer = db.Column(db.JSON, nullable=True)
    reviewed_content_type = db.Column(db.String(10), nullable=True)
    reviewed_difficulty = db.Column(db.String(20), nullable=True)

    rejection_reason = db.Column(db.String(200), nullable=True)

    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=True)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", foreign_keys=[user_id], backref="question_submissions")
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])
    question = db.relationship("Question")
    # backref indispensable : sans lui, Tag n'a aucune connaissance de ces
    # deux tables d'association, et supprimer un Tag via l'ORM (admin_tags_delete)
    # laisse des lignes orphelines ici sans jamais lever d'erreur (incident réel -
    # Question.tags et Album.tags ont ce même besoin, satisfait chez eux par un
    # backref déjà en place).
    tags = db.relationship("Tag", secondary=submission_tags, backref=db.backref("submissions", lazy="dynamic"))
    reviewed_tags = db.relationship(
        "Tag", secondary=submission_reviewed_tags, backref=db.backref("reviewed_by_submissions", lazy="dynamic")
    )

class Friendship(db.Model):
    """Représente une relation d'amitié entre deux utilisateurs"""

    __tablename__ = "friendships"

    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    requester = db.relationship("User", foreign_keys=[requester_id], backref="sent_friend_requests")
    receiver = db.relationship("User", foreign_keys=[receiver_id], backref="received_friend_requests")

class Notification(db.Model):
    """Représente une notification reçue par un utilisateur"""

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    link = db.Column(db.String(255), nullable=True)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", backref="notifications")

class ChatMessage(db.Model):
    """Représente un message échangé en direct entre deux amis.

    Pas de table Conversation séparée : une conversation 1-à-1 est
    entièrement identifiée par la paire (sender_id, recipient_id), comme
    Friendship l'est déjà pour la relation d'amitié elle-même.
    """

    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.String(1000), nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    sender = db.relationship("User", foreign_keys=[sender_id], backref="sent_chat_messages")
    recipient = db.relationship("User", foreign_keys=[recipient_id], backref="received_chat_messages")

class GameSession(db.Model):
    """Représente une partie multijoueur 1v1 en mode rapidité"""

    __tablename__ = "game_sessions"

    id = db.Column(db.Integer, primary_key=True)
    host_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    guest_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    mode = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="invited")
    host_score = db.Column(db.Integer, nullable=False, default=0)
    guest_score = db.Column(db.Integer, nullable=False, default=0)
    current_question_index = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)

    host = db.relationship("User", foreign_keys=[host_id])
    guest = db.relationship("User", foreign_keys=[guest_id])


class GameSessionQuestion(db.Model):
    """Représente une question précise dans une partie multijoueur, avec son ordre"""

    __tablename__ = "game_session_questions"

    id = db.Column(db.Integer, primary_key=True)
    game_session_id = db.Column(db.Integer, db.ForeignKey("game_sessions.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    order_index = db.Column(db.Integer, nullable=False)

    game_session = db.relationship("GameSession", backref="session_questions")
    question = db.relationship("Question")

class GameAnswer(db.Model):
    """Représente la réponse d'un joueur à une question dans une partie multijoueur"""

    __tablename__ = "game_answers"

    id = db.Column(db.Integer, primary_key=True)
    game_session_id = db.Column(db.Integer, db.ForeignKey("game_sessions.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    question_index = db.Column(db.Integer, nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    answered_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    game_session = db.relationship("GameSession", backref="answers")
    user = db.relationship("User")

question_tags = db.Table(
    "question_tags",
    db.Column("question_id", db.Integer, db.ForeignKey("questions.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id"), primary_key=True),
)

class Tag(db.Model):
    """Représente un tag de thème (genre) ou d'univers, applicable à des questions.

    Le nom est unique PAR TYPE, pas globalement : "Halloween" peut exister à
    la fois comme univers (la franchise de films) et comme thème (la période/
    l'ambiance), ce sont deux tags distincts qui portent volontairement le
    même nom."""

    __tablename__ = "tags"
    __table_args__ = (db.UniqueConstraint("name", "tag_type", name="uq_tags_name_tag_type"),)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    tag_type = db.Column(db.String(20), nullable=False)

    questions = db.relationship("Question", secondary=question_tags, backref="tags")


class Work(db.Model):
    """Représente une œuvre (film ou série) identifiée par son id TMDB.

    Centralise le classement saga/genre une seule fois par œuvre, plutôt que
    de le dupliquer sur chaque question qui en parle (cf. Tag, taggé question
    par question). Genres et saga sont toujours renseignés depuis TMDB, jamais
    à la main."""

    __tablename__ = "works"
    __table_args__ = (db.UniqueConstraint("tmdb_id", "content_type", name="uq_work_tmdb"),)

    id = db.Column(db.Integer, primary_key=True)
    tmdb_id = db.Column(db.Integer, nullable=False)
    content_type = db.Column(db.String(10), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    poster_url = db.Column(db.String(255), nullable=True)
    genres = db.Column(db.JSON, nullable=False, default=list)
    saga = db.Column(db.String(255), nullable=True)


class Character(db.Model):
    """Représente un personnage collectionnable, lié à une franchise (tag univers)."""

    __tablename__ = "characters"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    tag_id = db.Column(db.Integer, db.ForeignKey("tags.id"), nullable=False)
    rarity = db.Column(db.String(20), nullable=False, default="commun")
    image_url = db.Column(db.String(255), nullable=True)
    fragments_required = db.Column(db.Integer, nullable=False, default=5)
    image_x = db.Column(db.Float, nullable=False, default=0)
    image_y = db.Column(db.Float, nullable=False, default=0)
    image_scale = db.Column(db.Float, nullable=False, default=100)
    frame_x = db.Column(db.Float, nullable=False, default=0)
    frame_y = db.Column(db.Float, nullable=False, default=0)
    frame_scale = db.Column(db.Float, nullable=False, default=100)

    tag = db.relationship("Tag")


class UserCharacter(db.Model):
    """Représente la progression d'un joueur sur un personnage précis."""

    __tablename__ = "user_characters"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    character_id = db.Column(db.Integer, db.ForeignKey("characters.id"), nullable=False)
    fragments = db.Column(db.Integer, nullable=False, default=0)
    unlocked_at = db.Column(db.DateTime, nullable=True)
    last_fragment_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", backref="character_progress")
    character = db.relationship("Character")


# Un album est une collection thématique de personnages (ex. « Horreur »),
# liée à un ou plusieurs tags (genre, univers, pays...). Un personnage
# peut appartenir à plusieurs albums.
album_tags = db.Table(
    "album_tags",
    db.Column("album_id", db.Integer, db.ForeignKey("albums.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id"), primary_key=True),
)

album_characters = db.Table(
    "album_characters",
    db.Column("album_id", db.Integer, db.ForeignKey("albums.id"), primary_key=True),
    db.Column("character_id", db.Integer, db.ForeignKey("characters.id"), primary_key=True),
)


class Album(db.Model):
    """Représente un album de collection : un thème regroupant des personnages.

    L'album est relié à des tags (genre, univers...) : c'est par eux que
    le jeu sait quel album alimenter quand le joueur répond à une question.
    """

    __tablename__ = "albums"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(280), nullable=True)
    image_url = db.Column(db.String(255), nullable=True)
    image_x = db.Column(db.Float, nullable=False, default=0)
    image_y = db.Column(db.Float, nullable=False, default=0)
    image_scale = db.Column(db.Float, nullable=False, default=100)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_published = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    tags = db.relationship(
        "Tag",
        secondary=album_tags,
        backref=db.backref("albums", lazy="dynamic"),
    )
    characters = db.relationship(
        "Character",
        secondary=album_characters,
        backref=db.backref("albums", lazy="dynamic"),
    )


class DailyChallenge(db.Model):
    """Représente une mini-mission quotidienne assignée à un joueur pour une
    date donnée. Un joueur en a plusieurs par jour (voir slot) : chacune sa
    propre ligne, pour garder une progression indépendante par mission."""

    __tablename__ = "daily_challenges"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    challenge_date = db.Column(db.Date, nullable=False)
    # Position de cette mission parmi celles du jour (0, 1, 2...) : distingue
    # les lignes d'un même joueur à une même date, une fois qu'il y en a
    # plusieurs par jour plutôt qu'une seule.
    slot = db.Column(db.Integer, nullable=False, default=0)
    challenge_type = db.Column(db.String(50), nullable=False)
    target_value = db.Column(db.Integer, nullable=False)
    target_mode = db.Column(db.String(50), nullable=True)
    target_tag_id = db.Column(db.Integer, db.ForeignKey("tags.id"), nullable=True)
    progress = db.Column(db.Integer, nullable=False, default=0)
    completed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", backref="daily_challenges")
    target_tag = db.relationship("Tag")

    __table_args__ = (
        db.UniqueConstraint("user_id", "challenge_date", "slot", name="uq_user_challenge_date_slot"),
    )


class CacheCineScene(db.Model):
    """Représente un décor du jeu spécial Cache-Ciné : une illustration dans
    laquelle plusieurs références cinématographiques (CacheCineReference)
    sont cachées. Contenu créé par un admin, pas par un joueur."""

    __tablename__ = "cache_cine_scenes"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    image_url = db.Column(db.String(255), nullable=True)
    difficulty = db.Column(db.String(20), nullable=False, default="moyen")
    time_limit_seconds = db.Column(db.Integer, nullable=False, default=120)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class CacheCineReference(db.Model):
    """Représente une référence cachée dans une scène Cache-Ciné : une zone
    rectangulaire cliquable (position et taille en % de l'image, pour rester
    responsive) associée au titre de l'œuvre à retrouver."""

    __tablename__ = "cache_cine_references"

    id = db.Column(db.Integer, primary_key=True)
    scene_id = db.Column(db.Integer, db.ForeignKey("cache_cine_scenes.id"), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    pos_x = db.Column(db.Float, nullable=False, default=0)
    pos_y = db.Column(db.Float, nullable=False, default=0)
    width = db.Column(db.Float, nullable=False, default=10)
    height = db.Column(db.Float, nullable=False, default=10)
    order_index = db.Column(db.Integer, nullable=False, default=0)

    scene = db.relationship("CacheCineScene", backref="references")


class CacheCineProgress(db.Model):
    """Représente le meilleur résultat d'un joueur sur une scène Cache-Ciné
    précise : affiché sur l'écran de sélection des scènes
    (templates/special_games/cache_cine_choisir.html) pour marquer les
    scènes déjà jouées. Une ligne par couple joueur/scène, mise à jour
    seulement quand une nouvelle partie fait mieux que le record existant —
    le jeu reste librement rejouable, cette ligne ne fait que se souvenir du
    meilleur score."""

    __tablename__ = "cache_cine_progress"
    __table_args__ = (db.UniqueConstraint("user_id", "scene_id", name="uq_cache_cine_progress_user_scene"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    scene_id = db.Column(db.Integer, db.ForeignKey("cache_cine_scenes.id"), nullable=False)
    best_found_count = db.Column(db.Integer, nullable=False, default=0)
    best_total = db.Column(db.Integer, nullable=False, default=0)
    best_tier = db.Column(db.String(20), nullable=False, default="echec")
    times_played = db.Column(db.Integer, nullable=False, default=0)
    last_played_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", backref="cache_cine_progress")
    scene = db.relationship("CacheCineScene", backref="progress")


class MysteryCase(db.Model):
    """Représente un cas du jeu spécial Scène Mystère : une image de décor
    truffée d'une dizaine de références. Chaque référence (MysteryZone) pose
    sa propre question ; le joueur les résout une par une jusqu'à épuiser
    l'image. Contenu créé par un admin."""

    __tablename__ = "mystery_cases"

    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(255), nullable=True)
    difficulty = db.Column(db.String(20), nullable=False, default="moyen")
    time_limit_seconds = db.Column(db.Integer, nullable=False, default=240)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class MysteryZone(db.Model):
    """Représente une référence cachée sur l'image d'un cas Scène Mystère :
    une zone cliquable (position en % de l'image, comme CacheCineReference).
    Contrairement à Cache-Ciné, le joueur n'a pas de liste de titres à
    chercher : il clique sur ce qu'il repère lui-même dans l'image, puis tape
    le nom de l'œuvre (MysteryAnswer) sans aucun indice fourni. Il n'y a pas
    de "décoy" au niveau du cas, chaque zone est une cible légitime dans son
    propre tour de jeu."""

    __tablename__ = "mystery_zones"

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("mystery_cases.id"), nullable=False)
    pos_x = db.Column(db.Float, nullable=False, default=0)
    pos_y = db.Column(db.Float, nullable=False, default=0)
    width = db.Column(db.Float, nullable=False, default=10)
    height = db.Column(db.Float, nullable=False, default=10)
    order_index = db.Column(db.Integer, nullable=False, default=0)

    case = db.relationship("MysteryCase", backref="zones")


class MysteryAnswer(db.Model):
    """Représente un texte de réponse accepté pour une zone Scène Mystère
    précise : le joueur tape le nom de l'œuvre à la main, la comparaison
    (services/special_games.py) tolère casse, accents et petites fautes de
    frappe. Plusieurs lignes par zone permettent d'accepter des alias (titre
    original, abréviation courante...)."""

    __tablename__ = "mystery_answers"

    id = db.Column(db.Integer, primary_key=True)
    zone_id = db.Column(db.Integer, db.ForeignKey("mystery_zones.id"), nullable=False)
    text = db.Column(db.String(100), nullable=False)
    order_index = db.Column(db.Integer, nullable=False, default=0)

    zone = db.relationship("MysteryZone", backref="answers")


class MysteryProgress(db.Model):
    """Représente le meilleur résultat d'un joueur sur un cas Scène Mystère
    précis : équivalent de CacheCineProgress, affiché sur l'écran de
    sélection des cas (templates/special_games/scene_mystere_choisir.html)."""

    __tablename__ = "mystery_progress"
    __table_args__ = (db.UniqueConstraint("user_id", "case_id", name="uq_mystery_progress_user_case"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    case_id = db.Column(db.Integer, db.ForeignKey("mystery_cases.id"), nullable=False)
    best_found_count = db.Column(db.Integer, nullable=False, default=0)
    best_total = db.Column(db.Integer, nullable=False, default=0)
    best_tier = db.Column(db.String(20), nullable=False, default="echec")
    times_played = db.Column(db.Integer, nullable=False, default=0)
    last_played_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", backref="mystery_progress")
    case = db.relationship("MysteryCase", backref="progress")