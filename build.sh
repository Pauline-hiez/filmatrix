#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

npm install
npx tailwindcss -i ./static/css/input.css -o ./static/css/output.css --minify

python -c "from app import app; from src.database import db; app.app_context().push(); db.create_all()"
flask db stamp head
python seed_db.py