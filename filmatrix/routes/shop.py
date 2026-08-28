"""Boutique de titres : achat et équipement."""

from flask import Blueprint, flash, redirect, render_template, session, url_for
from flask_login import current_user, login_required

from filmatrix.extensions import db
from filmatrix.services.shop import TITLES, owns_title, purchase_title


bp = Blueprint("shop", __name__)


@bp.route("/boutique")
@login_required
def shop() -> str:
    """Affiche la boutique de titres avec le statut d'achat pour chacun"""
    shop_titles = []
    for code, info in TITLES.items():
        shop_titles.append(
            {
                "code": code,
                "name": info["name"],
                "price": info["price"],
                "owned": owns_title(current_user, code),
                "affordable": current_user.coins >= info["price"],
            }
        )

    return render_template("shop/boutique.html", shop_titles=shop_titles)

@bp.route("/boutique/acheter/<title_code>", methods=["POST"])
@login_required
def buy_title(title_code: str) -> str:
    """Traite l'achat d'un titre par un utilisateur connecté"""
    success = purchase_title(current_user, title_code)
    db.session.commit()

    if success:
        flash("Titre acheté avec succès.")
    else:
        flash("Achat impossible.")

    return redirect(url_for("shop.shop"))

@bp.route("/boutique/equiper/<title_code>", methods=["POST"])
@login_required
def equip_title(title_code: str) -> str:
    """Equipe un titre possédé par l'utilisateur connecté"""
    if owns_title(current_user, title_code):
        current_user.equipped_title = title_code
        db.session.commit()
        flash("Titre équipé.")
    else:
        flash("Tu ne possède pas ce titre.")

    return redirect(url_for("shop.shop"))
