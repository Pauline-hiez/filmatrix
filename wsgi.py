"""Point d'entrée de l'application.

Le monkey patching de gevent doit précéder tout autre import : il remplace les
appels bloquants de la bibliothèque standard par des équivalents coopératifs, et
les modules déjà chargés garderaient les anciens.
"""

from gevent import monkey

monkey.patch_all()

from filmatrix import create_app  # noqa: E402  (voir le monkey patching ci-dessus)
from filmatrix.extensions import socketio  # noqa: E402

app = create_app()

if __name__ == "__main__":
    socketio.run(app, debug=True)
