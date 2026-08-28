"""Décorateur et utilitaires pour les routes réservées aux admins"""

from functools import wraps

from flask import abort
from flask_login import current_user


def admin_required(view_function):
    """Décorateur qui bloque l'accès à une route si l'utilisateur n'est pas admin"""

    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return view_function(*args, **kwargs)

    return wrapped_view