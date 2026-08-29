# Filmatrix

Plateforme de jeux cinématographiques développé en Python avec Flask, dans le but d'apprendre Python.

## Fonctionnalités

- **10 modes de jeu** : Quiz (QCM), Vrai/Faux, Citations, Emoji Quiz, Film mélangé, Chronologie, Devinette, Devinette affiche, Casting, Blind test
- Comptes utilisateurs (inscription/connexion), certaines questions réservées aux membres
- Système d'XP et de niveaux, avec paliers croissantss
- Classement général des joueurs
- Badges à débloquer (6 pour l'instant)
- Monnaie virtuelle et boutique de titres
- Filtrage des questions par type (films / séries) et par thème, univers, pays ou époque
- Chronomètres par question, adapté à chaque mode
- Interface responsive (mobile-first), thème néon noir/turquoise

## Stack technique

-**Backend** : Python 3.10, Flask
-**Base de données** : SQLite, SQLAlchemy (ORM), Flask-migrate (migrations)
-**Authentification** : Flask-Login
-**Frontend** : Tailwind CSS (build local via npm), JavaScript vanilla
-**APIs externes** : TMDB (affiches, casting), iTunens Search (extraits audio)
-**Tests** : pytest


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
| `python -m scripts.refresh_audio_urls` | Vérifie et régénère les URLs audio expirées du mode Blind Test |
| `flask db migrate -m "message"` | Génère une nouvelle migration après modification d'un modèle |
| `flask db upgrade` | Applique les migrations en attente |
| `python -m scripts.generate_image_question affiche "Titre" [film\|serie]` | Génère le JSON d'une question Devinette-affiche via TMDB |
| `python -m scripts.generate_image_question casting "Titre" [film\|serie]` | Génère le JSON d'une question Casting via TMDB |
| `python -m scripts.generate_blindtest_question "Titre" "terme de recherche" [film\|serie]` | Génère le JSON d'une question Blind Test via iTunes |

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
│   ├── multiplayer.py          #   duels en temps réel
│   ├── shop.py                 #   boutique de titres
│   ├── leaderboard.py          #   classement
│   ├── notifications.py        #   consultation des notifications
│   └── admin.py                #   administration
├── services/                   # règles du jeu, sans dépendance à Flask
│   ├── engine.py               #   vérification des réponses
│   ├── questions.py            #   sélection et tirage des questions
│   ├── score.py                #   suivi d'une partie solo
│   ├── levels.py               #   niveaux, chrono et récompenses
│   ├── multiplayer.py          #   parties à deux
│   ├── badges.py, shop.py, friends.py, notifications.py
│   └── matching.py, validation.py
├── integrations/               # services externes
│   ├── tmdb.py                 #   images de films et séries
│   └── itunes.py               #   extraits audio
└── realtime/
    └── events.py               # gestionnaires SocketIO

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
- **User** : compte joueur, XP, niveau (calculé), pièces, titre équipé
- **Attempt** : historique des réponses d'un joueur
- **UserBadge** / **UserTitle** : badges et titres obtenus par un joueur

## Notes

- Les questions sont éditées dans `data/questions/*.json` puis importées en base via `scripts/seed_db.py` - ce fichier JSON n'est jamais lu directement par le site.
- L'`id` d'une question est sa clé primaire et doit être unique **dans l'ensemble du dossier**, pas seulement dans son fichier : deux questions partageant un id s'écrasent silencieusement à l'import.
- L'import est un upsert : il ne supprime rien. Une question retirée d'un JSON reste jouable tant qu'elle n'est pas effacée de la base - `seed_db.py` les liste en fin d'import.
- Les URLs audio d'iTunes ont une durée de vie limitée : relancer `scripts/refresh_audio_urls.py` régulièrement pour éviter les extraits cassés.
- Le CSS compilé (`static/css/output.css`) doit être régénéré après toute modification de classe Tailwind dans les templates - voir la commande `--watch` ci-dessus.