#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

npm install
npx tailwindcss -i ./static/css/input.css -o ./static/css/output.css --minify

python -m scripts.prepare_db
python -m scripts.seed_db
