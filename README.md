# Filmatrix

Plateforme de jeux cinématographiques développé en Python avec Flask, dans le but d'apprendre Python.

## Fonctionnalités

- **10 modes de jeu** : Quiz (QCM), Vrai/Faux, Citations, Emoji Quiz, Film mélangé, Chronologie, Devinette, Devinette affiche, Casting, Blind test
- Comptes utilisateurs (inscription/connexion), certaines questions réservées aux membres
- Système d'XP et de niveaux, avec paliers croissantss
- Classement général des joueurs
- Badges à débloquer (6 pour l'instant)
- Monnaie virtuelle et boutique de titres
- Filtrage des questions par catégories
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
 
# Importer les questions depuis data/questions/
python seed_db.py
```

## Lancer le projet en développement

Deux terminaux sont nécessaires : 

**Terminal 1 - Le serveur Flask :**
```bash
python app.py
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
| `python seed_db.py` | Réimporte les questions depuis `data/questions/*.json` vers la base |
| `python refresh_audio_urls.py` | Vérifie et régénère les URLs audio expirées du mode Blind Test |
| `flask db migrate -m "message"` | Génère une nouvelle migration après modification d'un modèle |
| `flask db upgrade` | Applique les migrations en attente |
| `python generate_image_question.py affiche "Titre" difficulte categorie` | Génère le JSON d'une question Devinette-affiche via TMDB |
| `python generate_image_question.py casting "Titre" difficulte categorie` | Génère le JSON d'une question Casting via TMDB |
| `python generate_blindtest_question.py "Titre" difficulte categorie "terme de recherche"` | Génère le JSON d'une question Blind Test via iTunes |

## Structure du projet

```
filmatrix/
├── app.py                    # Application Flask (routes, application factory)
├── seed_db.py                 # Import des questions JSON vers la base
├── refresh_audio_urls.py       # Régénération des URLs audio expirées
├── generate_image_question.py  # Génération de questions avec images (TMDB)
├── generate_blindtest_question.py  # Génération de questions Blind Test (iTunes)
├── src/
│   ├── database.py            # Instance SQLAlchemy centrale
│   ├── models.py               # Modèles de données (Question, User, Attempt, ...)
│   ├── engine.py                # Moteur de vérification des réponses
│   ├── validation.py            # Validation du mot de passe
│   ├── badges.py                 # Définition et logique des badges
│   ├── shop.py                    # Définition et logique de la boutique
│   ├── tmdb.py                     # Accès à l'API TMDB
│   └── itunes.py                    # Accès à l'API iTunes Search
├── data/questions/             # Contenu des questions, un fichier JSON par mode
├── templates/                  # Templates Jinja2
├── static/
│   ├── css/                    # Tailwind (input.css source, output.css généré)
│   └── js/                     # JavaScript (quiz.js, modes.js, navbar.js)
├── migrations/                 # Historique des migrations Alembic
└── tests/                      # Tests pytest
```

## Modèle de données (aperçu)

- **Question** : mode, catégorie, difficulté, contenu (`payload`), bonne réponse (`correct_answer`), accès restreint ou non
- **User** : compte joueur, XP, niveau (calculé), pièces, titre équipé
- **Attempt** : historique des réponses d'un joueur
- **UserBadge** / **UserTitle** : badges et titres obtenus par un joueur

## Notes

- Les questions sont éditées dans `data/questions/*.json` puis importées en base via `seed_db.py` - ce fichier JSON n'est jamais lu directement par le site.
- Les URLs audio d'iTunes ont une durée de vie limitée : relancer `refresh_audio_urls.py` régulièrement pour éviter les extraits cassés.
- Le CSS compilé (`static/css/output.css`) doit être régénéré après toute modification de classe Tailwind dans les templates - voir la commande `--watch` ci-dessus.