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