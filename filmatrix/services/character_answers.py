"""Réponses personnages pour les citations dont l'auteur est suffisamment connu.

Les JSON historiques stockent la réponse d'une citation sous la clé ``film``
(même pour une série). Ce catalogue permet d'ajouter la seconde réponse sans
casser les imports existants ni le fonctionnement normal du mode Citation.
"""


# Les identifiants correspondent aux questions de data/questions/*.json.
# Les citations ambiguës ou prononcées par plusieurs personnages ne sont pas
# listées : elles restent des questions « titre de l'œuvre ».
CHARACTER_ANSWERS = {
    # Séries : Friends, Breaking Bad, Game of Thrones, Kaamelott
    3500: "Joey Tribbiani",
    3501: "Ross Geller",
    3502: "Chandler Bing",
    3503: "Ross Geller",
    3505: "Walter White",
    3506: "Walter White",
    3507: "Jesse Pinkman",
    3508: "Walter White",
    3509: "Mike Ehrmantraut",
    3511: "Ygritte",
    3512: "Daenerys Targaryen",
    3515: "Perceval",
    3516: "Perceval",
    3517: "Karadoc",
    # Séries : Stranger Things et séries cultes
    3518: "Eleven",
    3519: "Mike Wheeler",
    3520: "Jim Hopper",
    3521: "Dustin Henderson",
    3522: "Eddie Munson",
    3523: "Michael Scott",
    3524: "Omar Little",
    3526: "Les Daleks",
    3527: "Spock",
    3528: "Bart Simpson",
    3530: "Gregory House",
    3531: "Sherlock Holmes",
    3532: "Barney Stinson",
    3533: "Sheldon Cooper",
    3534: "Fox Mulder",
    3535: "Dale Cooper",
    3536: "Jack Shephard",
    3537: "Dexter Morgan",
    3538: "Rust Cohle",
    3539: "Din Djarin",
    3540: "Pablo Escobar",
    3541: "Valery Legasov",
    3542: "Columbo",
    3543: "Hannibal Smith",
    3544: "Rick Sanchez",
    3547: "Jake Peralta",
    3549: "The Soup Nazi",
    3550: "Meredith Grey",
    3551: "Carrie Bradshaw",
    22501: "Homer Simpson",
    22503: "Sheldon Cooper",
    22504: "Barney Stinson",
    22505: "Lucifer Morningstar",
    22506: "Thomas Shelby",
    # Films : citations suffisamment identifiables
    3005: "Gollum",
    3008: "Ian Malcolm",
    3009: "Rhett Butler",
    3010: "Jack Torrance",
    3011: "Johnny Castle",
    3012: "Dory",
    3013: "Colonel Kilgore",
    3014: "Godefroy de Montmirail",
    3016: "William Wallace",
    3017: "Le Joker",
    22000: "Tyler Durden",
    22002: "Gandalf",
    22003: "Darth Vader",
    22004: "Leia Organa",
    22005: "Rubeus Hagrid",
    22006: "Le Garçon à la cuillère",
    22007: "Pennywise",
    22008: "Hubert Bonisseur de La Bath",
    22009: "Martin Brody",
    22010: "James Bond",
    22011: "Indiana Jones",
    22012: "Hannibal Lecter",
    22013: "Le T-800",
    22014: "Léon",
    22015: "Jules Winnfield",
    22016: "David Mills",
    22017: "Maximus",
    22018: "Roy Batty",
    22019: "John McClane",
    22020: "Chucky",
    22022: "Ellen Ripley",
    22023: "Doc Brown",
    22024: "Doc Brown",
    22025: "John Hammond",
    22026: "Dutch",
    22027: "Obélix",
    22028: "Le Joker",
    22029: "Kevin McCallister",
    22030: "Effie Trinket",
}


def character_answer(question) -> str | None:
    """Retourne la réponse personnage explicite ou cataloguée, si disponible."""
    explicit_answer = (question.correct_answer or {}).get("character")
    if explicit_answer:
        return explicit_answer
    return CHARACTER_ANSWERS.get(question.id)
