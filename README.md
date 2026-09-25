# Filmatrix

Plateforme de jeux cinématographiques développé en Python avec Flask, dans le but d'apprendre Python.

## Fonctionnalités

- **11 modes de jeu solo**, plus un mode Mix qui les mélange dans une même partie : Quiz (QCM), Vrai/Faux, Citations, Emoji Quiz, Film mélangé, Chronologie, Devinette, Devinette affiche, Casting, Blind test, Dialogue
- **Duels en temps réel** entre amis (Socket.IO), sur n'importe quel mode solo
- **Jeux spéciaux** débloqués par Tickets d'Or : Cache-Ciné et Scène Mystère
- **Missions quotidiennes** (3 mini-missions par jour) et série de connexion
- **Collection de personnages** à débloquer et albums, avec animation de puzzle à l'obtention d'un fragment
- **Suggestions de questions par les joueurs**, validées ou modifiées côté admin avant publication
- Comptes utilisateurs (inscription/connexion), certaines questions réservées aux membres
- Amis, messagerie instantanée et notifications
- Système d'XP et de niveaux, avec paliers croissants
- Classement général des joueurs
- Badges à débloquer (8 pour l'instant)
- Monnaie virtuelle et boutique de titres
- Filtrage des questions par type (films / séries) et par thème, univers, pays ou époque
- Chronomètres par question, adapté à chaque mode
- Interface responsive (mobile-first), thème néon noir/turquoise
- Panneau d'administration complet : création/édition de questions (recherche TMDB, iTunes et YouTube intégrée), gestion des personnages, jeux spéciaux, signalements et suggestions

## Stack technique

- **Backend** : Python 3.10, Flask, Flask-SocketIO (gevent) pour le temps réel (duels, chat)
- **Base de données** : SQLite en local, PostgreSQL en production, SQLAlchemy (ORM), Flask-Migrate (migrations)
- **Authentification** : Flask-Login
- **Frontend** : Tailwind CSS + FlyonUI (build local via npm), JavaScript vanilla
- **APIs externes** : TMDB (affiches, casting), iTunes Search (extraits audio du Blind Test) et YouTube Data API (extraits vidéo en repli pour le Blind Test, seule source pour le mode Dialogue), Cloudflare R2 (stockage des images de personnages)
- **Déploiement** : Render, via Gunicorn + worker gevent-websocket (voir `Procfile`)
- **Tests** : pytest


## Installation

### Prérequis

- Python 3.10+
- Node.js et npm
- Clé API [TMDB](https://www.themoviedb.org/documentation/api)

### Étapes

```bash
# Cloner le dépôt
git clone <url-du-repo>
cd filmatrix
 
# Créer et activer l'environnement virtuel Python
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows PowerShell
 
# Installer les dépendances Python
pip install -r requirements.txt
 
# Installer les dépendances npm (Tailwind)
npm install
 
# Créer le fichier .env à la racine, avec :
# SECRET_KEY=une_cle_secrete_aleatoire
# TMDB_API_KEY=ta_cle_api_tmdb
# YOUTUBE_API_KEY=ta_cle_api_youtube_data_v3
# R2_ACCOUNT_ID=ton_account_id_cloudflare
# R2_ACCESS_KEY_ID=ta_cle_d_acces_r2
# R2_SECRET_ACCESS_KEY=ta_cle_secrete_r2
# R2_BUCKET_NAME=nom_du_bucket
# R2_PUBLIC_URL=https://xxxxx.r2.dev  (ou ton domaine personnalisé)
#
# Sans DATABASE_URL, l'app utilise SQLite en local. En production (Render),
# DATABASE_URL est fourni par l'hébergeur - inutile de la définir soi-même.
 
# Appliquer les migrations de base de données
flask db upgrade
 
# Importer les questions et synchroniser les tags depuis data/questions/
python -m scripts.seed_db

# Télécharger une fois le catalogue complet OpenMoji pour l'administration
python -m scripts.download_openmoji_catalog
```

## Lancer le projet en développement

Deux terminaux sont nécessaires : 

**Terminal 1 - Le serveur Flask :**
```bash
python wsgi.py
```
Le site est alors accessible sur http://127.0.0.1:5000

**Terminal 2 - La compilation Tailwind :**
```bash
npx tailwindcss -i ./static/css/input.css -o ./static/css/output.css --watch
```
Recompile automatiquement le CSS à chaque modification d'un template.

## Commandes utiles

| Commande | Description |
|---|---|
| `python -m pytest -v` | Lance tous les tests automatisés |
| `python -m scripts.seed_db` | Réimporte les questions depuis `data/questions/*.json` vers la base |
| `python -m scripts.check_questions` | Vérifie les fichiers de questions (schéma, unicité des id, doublons) avant import |
| `python -m scripts.refresh_audio_urls` | Vérifie et régénère les URLs iTunes expirées du Blind Test (ne couvre pas les extraits sourcés YouTube) |
| `python -m scripts.delete_orphan_questions` | Supprime les questions en base absentes des JSON (et leurs tentatives associées) |
| `python -m scripts.promote_admin [email]` | Donne les droits admin à un compte déjà inscrit |
| `flask db migrate -m "message"` | Génère une nouvelle migration après modification d'un modèle |
| `flask db upgrade` | Applique les migrations en attente |
| `python -m scripts.generate_image_question affiche "Titre" [film\|serie]` | Génère le JSON d'une question Devinette-affiche via TMDB |
| `python -m scripts.generate_image_question casting "Titre" [film\|serie]` | Génère le JSON d'une question Casting via TMDB |
| `python -m scripts.generate_blindtest_question "Titre" "terme de recherche" [film\|serie]` | Génère le JSON d'une question Blind Test via iTunes |

D'autres scripts ponctuels (retag, harmonisation de tags, génération en masse...) vivent dans `scripts/` - chacun documente son usage en tête de fichier.

## Structure du projet

```
filmatrix/                      # le paquet applicatif
├── __init__.py                 # create_app() : assemble extensions et blueprints
├── extensions.py               # db, socketio, login_manager, migrate
├── models.py                   # modèles de données
├── game_modes.py               # catalogue des modes de jeu
├── catalog.py                  # avatars, motifs de signalement
├── permissions.py              # décorateur admin_required
├── routes/                     # un blueprint par domaine
│   ├── main.py                 #   accueil, catalogue des modes
│   ├── auth.py                 #   inscription, connexion, déconnexion
│   ├── profile.py              #   profil personnel et fiches publiques
│   ├── quiz.py                 #   parties solo
│   ├── friends.py              #   amis et demandes
│   ├── chat.py                 #   historique de la messagerie entre amis
│   ├── multiplayer.py          #   duels en temps réel
│   ├── special_games.py        #   Cache-Ciné et Scène Mystère (Tickets d'Or)
│   ├── admin_special_games.py  #   administration des jeux spéciaux
│   ├── collection.py           #   galerie de personnages à débloquer
│   ├── suggestions.py          #   questions proposées par les joueurs
│   ├── shop.py                 #   boutique de titres
│   ├── leaderboard.py          #   classement
│   ├── notifications.py        #   consultation des notifications
│   └── admin.py                #   administration des questions, utilisateurs, signalements
├── services/                   # règles du jeu, sans dépendance à Flask
│   ├── engine.py               #   vérification des réponses
│   ├── questions.py            #   sélection et tirage des questions
│   ├── score.py                #   suivi d'une partie solo
│   ├── levels.py               #   niveaux, chrono et récompenses
│   ├── multiplayer.py          #   parties à deux
│   ├── daily_challenges.py     #   mini-missions quotidiennes et série de connexion
│   ├── collection.py, puzzle.py, character_answers.py
│   ├── special_games.py, run_rewards.py
│   ├── suggestions.py, tags.py
│   ├── badges.py, shop.py, friends.py, chat.py, notifications.py
│   └── matching.py, validation.py
├── integrations/               # services externes
│   ├── tmdb.py                 #   images de films, séries et casting
│   ├── itunes.py               #   extraits audio du Blind Test
│   ├── youtube.py              #   extraits vidéo (repli Blind Test, seule source du mode Dialogue)
│   └── storage.py              #   upload vers Cloudflare R2 (images de personnages)
└── realtime/
    └── events.py               # gestionnaires SocketIO (duels, chat)

wsgi.py                         # point d'entrée (dev et production)
scripts/                        # amorçage de la base, génération de questions
data/questions/                 # contenu des questions, un fichier JSON par mode
templates/                      # gabarits Jinja2, un dossier par blueprint
static/
├── css/                        # Tailwind (input.css source, output.css généré)
└── js/                         # JavaScript, dont vendor/socket.io.min.js
migrations/                     # historique des migrations Alembic
tests/                          # tests pytest
```

## Modèle de données (aperçu)

- **Question** : mode, type de contenu (`content_type` : `film` ou `serie`), contenu (`payload`), bonne réponse (`correct_answer`), accès restreint ou non. La difficulté n'est pas portée par la question : c'est un niveau choisi par le joueur avant la partie, qui fixe le chrono et les récompenses (voir `services/levels.py`).
- **User** : compte joueur, XP, niveau (calculé), pièces, Tickets d'Or, titre équipé
- **Attempt** : historique des réponses d'un joueur
- **UserBadge** / **UserTitle** : badges et titres obtenus par un joueur
- **QuestionSubmission** : question proposée par un joueur, en attente (ou non) de revue admin
- **Friendship** / **ChatMessage** / **Notification** : amis, messagerie et notifications
- **GameSession** / **GameSessionQuestion** / **GameAnswer** : un duel en temps réel et son déroulé
- **Character** / **UserCharacter** / **Album** : la collection de personnages à débloquer
- **DailyChallenge** : mini-missions quotidiennes et série de connexion d'un joueur
- **CacheCineScene** / **CacheCineReference**, **MysteryCase** / **MysteryZone** / **MysteryAnswer** : contenu des deux jeux spéciaux

## Notes

- Deux façons de créer une question : en JSON dans `data/questions/` puis import via `scripts/seed_db.py` (contenu initial, en masse), ou directement depuis le panneau admin (`/admin/questions/nouvelle`), qui écrit en base sans jamais passer par un fichier. Le mode Dialogue n'existe qu'en base pour l'instant, aucune question de ce mode n'est versionnée en JSON.
- L'`id` d'une question JSON est sa clé primaire et doit être unique **dans l'ensemble du dossier**, pas seulement dans son fichier : deux questions partageant un id s'écrasent silencieusement à l'import.
- L'import est un upsert : il ne supprime rien. Une question retirée d'un JSON reste jouable tant qu'elle n'est pas effacée de la base - `seed_db.py` les liste en fin d'import.
- Les URLs audio d'iTunes ont une durée de vie limitée : relancer `scripts/refresh_audio_urls.py` régulièrement pour éviter les extraits cassés. Les extraits sourcés YouTube (Blind Test en repli, ou Dialogue) n'ont pas cette limite de durée, mais une vidéo peut être supprimée ou rendue privée - rien d'automatisé ne surveille ce cas pour l'instant.
- Le CSS compilé (`static/css/output.css`) doit être régénéré après toute modification de classe Tailwind dans les templates - voir la commande `--watch` ci-dessus.
- La base de production (PostgreSQL, Render) est distincte de la base locale : `DATABASE_URL` n'est jamais définie en local (SQLite par défaut), et un accès direct à la prod depuis un script local nécessite ses identifiants séparément - jamais commités.