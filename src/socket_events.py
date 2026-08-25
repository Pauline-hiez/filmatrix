"""Gestionnaire d'évènements SocketIO"""

from flask_login import current_user
from flask_socketio import join_room 

def register_socket_events(socketio):
    """Enregistre les gestionnaires d'évènements SocketIO"""
    @socketio.on("connect")
    def handle_connect():
        """Fait rejoindre à l'utilisateur son salon personnel dès la connexion"""
        if current_user.is_authenticated:
            join_room(f"user_{current_user.id}")
