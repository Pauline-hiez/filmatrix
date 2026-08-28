"""Instance centrale de SocketIO, importée par les autres modules.

Elle vit ici, et non dans app.py, pour la même raison que db vit dans
src/database.py : n'importe quel module doit pouvoir l'atteindre sans avoir à
importer l'application.

Ce n'est pas qu'une question de rangement. Lancer « python app.py » exécute ce
fichier sous le nom « __main__ » ; un module qui ferait « from app import
socketio » chargerait alors app.py une seconde fois, sous le nom « app », et
obtiendrait un SECOND objet SocketIO. Le serveur garderait les clients connectés
au premier, tandis que les émissions des routes partiraient du second — sans
jamais atteindre personne, et sans la moindre erreur.
"""

from flask_socketio import SocketIO

socketio = SocketIO()
