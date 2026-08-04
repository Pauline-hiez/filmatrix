"""Point d'entrée : joue un quiz en terminal, question par question."""

from data.questions import QUESTIONS
from src.engine import check_answer
from src.models import Question


def poser_question_qcm(question: Question) -> None:
    """Affiche une question de type QCM avec ses options numérotées."""
    print(f"\n{question.prompt}")
    for i, option in enumerate(question.payload["options"]):
        print(f"  {i}. {option}")


def poser_question_vrai_faux(question: Question) -> None:
    """Affiche une question de type vrai/faux."""
    print(f"\n{question.prompt}")
    print("  1. Vrai")
    print("  0. Faux")


def demander_reponse(question: Question):
    """Demande la réponse au joueur et la convertit dans le bon type."""
    match question.mode:
        case "qcm":
            return int(input("Ta réponse (numéro) : "))
        case "vrai_faux":
            return input("Ta réponse (1=Vrai, 0=Faux) : ") == "1"
        case _:
            raise ValueError(f"Mode inconnu : {question.mode}")


def main() -> None:
    """Boucle principale : pose chaque question, vérifie la réponse, compte le score."""
    score = 0

    for question in QUESTIONS:
        if question.mode == "qcm":
            poser_question_qcm(question)
        elif question.mode == "vrai_faux":
            poser_question_vrai_faux(question)

        reponse_joueur = demander_reponse(question)
        est_correct = check_answer(question, reponse_joueur)

        if est_correct:
            print("Bonne réponse !")
            score += 1
        else:
            print("Mauvaise réponse.")

    print(f"\nScore final : {score}/{len(QUESTIONS)}")


if __name__ == "__main__":
    main()