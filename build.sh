#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

npm install
npx tailwindcss -i ./static/css/input.css -o ./static/css/output.css --minify

python -m scripts.prepare_db
# scripts.seed_db désactivé : importait data/questions/*.json (jeu de questions
# périmé, remplacé par la curation via l'admin) sur CHAQUE déploiement, sans
# jamais renseigner la difficulté - polluait la prod avec des doublons tous à
# "moyen" par défaut. Voir scripts/seed_db.py pour le détail de l'incident.
