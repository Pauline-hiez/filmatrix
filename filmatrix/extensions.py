"""Instances des extensions Flask, partagées par tout le projet.

Elles vivent ici, et non dans le module qui construit l'application, pour que
n'importe quel module puisse les atteindre sans importer l'application.

Ce n'est pas qu'une question de rangement. Un module qui ferait
« from filmatrix import socketio » alors que le serveur a été lancé en exécutant
ce même fichier obtiendrait un SECOND objet SocketIO : le serveur garderait les
clients connectés au premier, tandis que les émissions partiraient du second,
sans jamais atteindre personne et sans la moindre erreur.
"""

from flask_login import LoginManager
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
socketio = SocketIO()
login_manager = LoginManager()
