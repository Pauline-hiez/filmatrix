"""OBSOLÈTE - NE PAS RELANCER TEL QUEL.

Ce script a produit le premier lot de questions de séries. Le relancer
écraserait le contenu actuel de data/questions/ avec :
  - des ids qui se recouvrent d'un fichier à l'autre (1000 + serie*100 + index),
    alors que l'id est la clé primaire commune à tout le dossier ;
  - les champs `category` et `difficulty`, retirés du schéma ;
  - un fichier « var_faux_serie.json » (faute de frappe pour vrai_faux) ;
  - des énoncés de QCM sans le nom de l'œuvre, et 5 titres répétés en mélange.

Il est conservé à titre d'historique. Pour ajouter des questions, éditer
directement les fichiers de data/questions/.

Génère le lot pilote de questions de séries.

Les contenus sont volontairement limités aux informations et répliques
largement connues. Les modes nécessitant une URL externe sont exclus ici.
"""
import json
from pathlib import Path

BASE = Path("data/questions")

SERIES = {
    "Friends": {
        "slug": "friends", "genre": "comédie", "country": "etats-unis", "era": "annees-1990",
        "qcm": [
            ("personnage", "Qui est le paléontologue du groupe ?", ["Ross Geller", "Joey Tribbiani", "Chandler Bing", "Mike Hannigan"], 0),
            ("personnage", "Quel est le métier de Monica au début de la série ?", ["Chef cuisinière", "Avocate", "Journaliste", "Médecin"], 0),
            ("personnage", "Comment s'appelle le singe de Ross ?", ["Marcel", "Maurice", "Milo", "Max"], 0),
            ("personnage", "Quel est le nom de famille de Rachel ?", ["Green", "Brown", "White", "Stone"], 0),
            ("personnage", "Qui devient la femme de Chandler ?", ["Monica", "Phoebe", "Rachel", "Emily"], 0),
            ("personnage", "Quel instrument Phoebe joue-t-elle souvent ?", ["Guitare", "Piano", "Violon", "Batterie"], 0),
            ("personnage", "Quel personnage est acteur dans la série ?", ["Joey", "Ross", "Chandler", "Gunther"], 0),
            ("personnage", "Dans quelle ville vivent principalement les six amis ?", ["New York", "Chicago", "Boston", "Seattle"], 0),
            ("personnage", "Quel est le prénom de la sœur jumelle de Phoebe ?", ["Ursula", "Emily", "Susan", "Carol"], 0),
            ("personnage", "Quel est le nom du café où le groupe se retrouve souvent ?", ["Central Perk", "Coffee House", "Manhattan Café", "The Perk"], 0),
        ],
        "vf": [
            ("Friends compte dix saisons.", True), ("Ross et Monica sont frère et sœur.", True), ("Joey joue le rôle du docteur Drake Ramoray.", True), ("Phoebe est avocate.", False), ("Central Perk est un café fréquenté par le groupe.", True), ("Chandler épouse Rachel.", False), ("Rachel a une fille avec Ross.", True), ("Gunther travaille au Central Perk.", True), ("Monica est la sœur de Joey.", False), ("La série se déroule principalement à New York.", True),
        ],
        "riddles": [
            ("Cette série suit six amis à New York.", "Un café appelé Central Perk est leur lieu de rendez-vous.", "Le titre anglais signifie « amis ».", "Friends"),
            ("Cette série met en scène un paléontologue.", "Il a une sœur très organisée et une ex-femme nommée Carol.", "Son prénom est Ross.", "Friends"),
            ("Cette série suit une jeune femme qui quitte son mariage.", "Elle devient amie avec Monica et vit un temps avec elle.", "Elle s'appelle Rachel Green.", "Friends"),
            ("Cette série comprend un personnage musicien excentrique.", "Elle chante des chansons décalées au café.", "Son prénom est Phoebe.", "Friends"),
            ("Cette série raconte une histoire d'amour avec des ruptures célèbres.", "Le couple se dispute notamment autour d'une pause.", "Il s'agit de Ross et Rachel.", "Friends"),
            ("Cette série comprend un acteur souvent maladroit avec les femmes.", "Il joue dans un feuilleton médical.", "Il s'appelle Joey Tribbiani.", "Friends"),
            ("Cette série comprend un couple qui se marie après une relation amicale.", "L'homme est sarcastique et la femme très organisée.", "Il s'agit de Chandler et Monica.", "Friends"),
            ("Cette série commence avec une mariée qui arrive dans un café.", "Elle fuit Barry et sa cérémonie de mariage.", "Elle s'appelle Rachel.", "Friends"),
            ("Cette série montre un homme qui travaille dans un café.", "Il est secrètement amoureux de Rachel.", "Il s'appelle Gunther.", "Friends"),
            ("Cette série est une sitcom américaine très connue.", "Son générique parle d'être là pour ses amis.", "Son titre est Friends.", "Friends"),
        ],
        "quotes": [("« How you doin'? » — De quelle série cette phrase est-elle emblématique ?", "Friends"), ("« We were on a break! » — De quelle série vient cette réplique ?", "Friends"), ("« Could I BE any more… ? » — De quelle série vient cette manière de parler ?", "Friends"), ("« Pivot! » — De quelle série vient ce cri pendant le déplacement d'un canapé ?", "Friends"), ("« I'll be there for you » — De quelle série vient cette phrase du générique ?", "Friends")],
        "emoji": [("☕🛋️👫", "Friends"), ("🦖🧪🧑‍🔬", "Friends"), ("🎸🐱☕", "Friends"), ("💍🏃‍♀️☕", "Friends"), ("🛋️↩️↪️", "Friends")],
        "titles": ["Friends"] * 5,
    },
    "Breaking Bad": {
        "slug": "breaking-bad", "genre": "drame", "country": "etats-unis", "era": "annees-2000",
        "qcm": [
            ("personnage", "Quel est le métier de Walter White au début de la série ?", ["Professeur de chimie", "Avocat", "Médecin", "Policier"], 0), ("personnage", "Quel pseudonyme Walter utilise-t-il ?", ["Heisenberg", "Gus", "Capone", "El Profesor"], 0), ("personnage", "Quel est le prénom du partenaire de Walter ?", ["Jesse", "Hank", "Saul", "Mike"], 0), ("personnage", "Dans quelle ville la série se déroule-t-elle principalement ?", ["Albuquerque", "Chicago", "Miami", "Denver"], 0), ("personnage", "Quel est le métier de Hank Schrader ?", ["Agent de la DEA", "Avocat", "Professeur", "Journaliste"], 0), ("personnage", "Comment s'appelle la femme de Walter ?", ["Skyler", "Marie", "Jane", "Andrea"], 0), ("personnage", "Quel produit Walter et Jesse fabriquent-ils ?", ["Méthamphétamine", "Cocaïne", "Héroïne", "Opium"], 0), ("personnage", "Quel avocat aide Walter et Jesse ?", ["Saul Goodman", "Harvey Specter", "Matt Murdock", "Mike Ross"], 0), ("personnage", "Quel personnage dirige Los Pollos Hermanos ?", ["Gus Fring", "Tuco Salamanca", "Hector Salamanca", "Mike Ehrmantraut"], 0), ("personnage", "Quel est le prénom du fils de Walter ?", ["Walter Jr.", "Thomas", "Henry", "Jack"], 0),
        ],
        "vf": [("Walter White est professeur de chimie.", True), ("Jesse Pinkman était l'élève de Walter.", True), ("La série se déroule principalement à Albuquerque.", True), ("Gus Fring dirige un restaurant de pizzas.", False), ("Hank travaille pour la DEA.", True), ("Saul Goodman est le nom professionnel de Jimmy McGill.", True), ("Walter utilise le pseudonyme Heisenberg.", True), ("Jesse est le frère de Walter.", False), ("La série compte cinq saisons.", True), ("Los Pollos Hermanos est associé à Gus Fring.", True)],
        "riddles": [("Cette série suit un professeur de chimie confronté à un cancer.", "Il commence à fabriquer de la drogue avec un ancien élève.", "Son pseudonyme devient Heisenberg.", "Breaking Bad"), ("Cette série suit un jeune homme impliqué dans le trafic de drogue.", "Il travaille avec son ancien professeur de chimie.", "Il s'appelle Jesse Pinkman.", "Breaking Bad"), ("Cette série présente un restaurant très connu.", "Son propriétaire est un homme d'affaires criminel.", "Le restaurant s'appelle Los Pollos Hermanos.", "Breaking Bad"), ("Cette série se déroule dans le désert du Nouveau-Mexique.", "Son héros est professeur avant de devenir criminel.", "Il s'agit de Breaking Bad.", "Breaking Bad"), ("Cette série met en scène un avocat très inventif.", "Il utilise le nom Saul Goodman.", "Son vrai nom est Jimmy McGill.", "Breaking Bad"), ("Cette série met en scène un agent de la DEA.", "Il est le beau-frère de Walter.", "Il s'appelle Hank Schrader.", "Breaking Bad"), ("Cette série suit un homme qui veut assurer l'avenir de sa famille.", "Il devient producteur de méthamphétamine.", "Son nom est Walter White.", "Breaking Bad"), ("Cette série présente un homme calme et méthodique.", "Il travaille comme homme de main et enquêteur.", "Il s'appelle Mike Ehrmantraut.", "Breaking Bad"), ("Cette série montre un personnage portant un chapeau noir.", "Il cache son identité derrière un nom inspiré d'un physicien.", "Ce personnage est Heisenberg.", "Breaking Bad"), ("Cette série est un drame criminel créé par Vince Gilligan.", "Son titre évoque une transformation morale.", "Son titre est Breaking Bad.", "Breaking Bad")],
        "quotes": [("« I am the one who knocks! » — De quelle série vient cette réplique ?", "Breaking Bad"), ("« Say my name. » — De quelle série vient cette réplique ?", "Breaking Bad"), ("« Yeah, science! » — À quelle série cette phrase est-elle associée ?", "Breaking Bad"), ("« I am the danger. » — De quelle série vient cette réplique ?", "Breaking Bad"), ("« Tread lightly. » — De quelle série vient cette menace ?", "Breaking Bad")],
        "emoji": [("🧪🔵👨‍🏫", "Breaking Bad"), ("🎩⚗️💰", "Breaking Bad"), ("🍗🌮🕴️", "Breaking Bad"), ("🚐🏜️🧪", "Breaking Bad"), ("👨‍👦‍👦💊🚔", "Breaking Bad")],
        "titles": ["Breaking Bad"] * 5,
    },
    "Game of Thrones": {
        "slug": "game-of-thrones", "genre": "fantasy", "country": "etats-unis", "era": "annees-2010",
        "qcm": [("univers", "Quel est le nom du continent principal de la série ?", ["Westeros", "Essos", "Narnia", "Middle-earth"], 0), ("personnage", "Quelle famille a le loup pour emblème ?", ["Stark", "Lannister", "Targaryen", "Baratheon"], 0), ("personnage", "Quel animal accompagne Daenerys ?", ["Des dragons", "Des loups", "Des corbeaux", "Des chevaux ailés"], 0), ("personnage", "Qui est surnommé le Roi du Nord ?", ["Jon Snow", "Tyrion Lannister", "Jaime Lannister", "Samwell Tarly"], 0), ("personnage", "Quel est le nom de l'épée de Jon Snow ?", ["Longclaw", "Ice", "Oathkeeper", "Needle"], 0), ("personnage", "Quelle famille règne depuis Port-Réal au début de la série ?", ["Baratheon", "Stark", "Greyjoy", "Tyrell"], 0), ("personnage", "Qui est surnommé The Hound ?", ["Sandor Clegane", "Gregor Clegane", "Bronn", "Jorah Mormont"], 0), ("personnage", "Arya et Sansa sont-elles de la même famille ?", ["Oui, elles sont sœurs", "Non", "Ce sont des cousines", "Ce sont des amies"], 0), ("univers", "Que protège principalement la Garde de Nuit ?", ["Le Mur", "Le Trône de Fer", "Port-Réal", "Peyredragon"], 0), ("personnage", "Quel titre de Daenerys est lié à ses dragons ?", ["Mère des Dragons", "Reine du Nord", "Main du Roi", "Dame de Winterfell"], 0)],
        "vf": [("Game of Thrones est adaptée des romans de George R. R. Martin.", True), ("Jon Snow est un Lannister.", False), ("Daenerys possède des dragons.", True), ("Winterfell est le fief des Stark.", True), ("Tyrion est le frère de Cersei.", True), ("Le Mur sépare Westeros des territoires du nord.", True), ("Arya est la sœur de Sansa.", True), ("Bran est un dragon.", False), ("Le Trône de Fer se trouve à Port-Réal.", True), ("La série se déroule dans un univers contemporain.", False)],
        "riddles": [("Cette série met en scène plusieurs familles nobles.", "Elles se disputent le pouvoir sur un trône.", "Son titre contient le mot « Thrones ».", "Game of Thrones"), ("Cette série suit une jeune femme liée à trois dragons.", "Elle veut reprendre le pouvoir de sa famille.", "Elle s'appelle Daenerys Targaryen.", "Game of Thrones"), ("Cette série commence dans un château du Nord.", "Ce château est le fief des Stark.", "Il s'appelle Winterfell.", "Game of Thrones"), ("Cette série comprend une immense construction glacée.", "La Garde de Nuit la protège.", "Il s'agit du Mur.", "Game of Thrones"), ("Cette série met en scène un personnage petit mais très intelligent.", "Il appartient à la famille Lannister.", "Il s'appelle Tyrion.", "Game of Thrones"), ("Cette série suit un jeune homme élevé à Winterfell.", "Il rejoint la Garde de Nuit.", "Il s'appelle Jon Snow.", "Game of Thrones"), ("Cette série comporte une lutte autour d'un siège en métal.", "Ce siège symbolise le pouvoir royal.", "C'est le Trône de Fer.", "Game of Thrones"), ("Cette série montre une famille dont l'emblème est le loup.", "Ses enfants comprennent Robb, Sansa, Arya et Bran.", "Il s'agit de la famille Stark.", "Game of Thrones"), ("Cette série comprend une menace venue du nord.", "Ses créatures sont appelées les Marcheurs Blancs.", "Elle s'appelle Game of Thrones.", "Game of Thrones"), ("Cette série est adaptée de A Song of Ice and Fire.", "Elle commence par une phrase devenue célèbre sur l'hiver.", "Son titre est Game of Thrones.", "Game of Thrones")],
        "quotes": [("« Winter is coming. » — De quelle série vient cette devise culte ?", "Game of Thrones"), ("« You know nothing, Jon Snow. » — De quelle série vient cette phrase ?", "Game of Thrones"), ("« Dracarys! » — De quelle série cette injonction est-elle emblématique ?", "Game of Thrones"), ("« Hold the door! » — De quelle série vient cette scène devenue culte ?", "Game of Thrones"), ("« A Lannister always pays his debts. » — De quelle série vient cette devise ?", "Game of Thrones")],
        "emoji": [("👑🐉⚔️", "Game of Thrones"), ("❄️🧱🗡️", "Game of Thrones"), ("🐺🏰👨‍👩‍👧‍👦", "Game of Thrones"), ("🪑⚔️👑", "Game of Thrones"), ("🐉🔥👸", "Game of Thrones")],
        "titles": ["Game of Thrones"] * 5,
    },
    "Kaamelott": {
        "slug": "kaamelott", "genre": "comédie", "country": "france", "era": "annees-2000",
        "qcm": [("personnage", "Qui interprète le roi Arthur ?", ["Alexandre Astier", "Franck Pitiot", "Lionnel Astier", "Jean-Christophe Hembert"], 0), ("univers", "Quel est le nom du royaume dirigé par Arthur ?", ["Kaamelott", "Camelot", "Logres", "Tintagel"], 0), ("personnage", "Quel personnage est connu pour ses erreurs de langage ?", ["Perceval", "Lancelot", "Merlin", "Venec"], 0), ("personnage", "Quel personnage est passionné par la nourriture ?", ["Karadoc", "Gauvain", "Bohort", "Calogrenant"], 0), ("personnage", "Qui est la femme d'Arthur au début de la série ?", ["Guenièvre", "Mevanwi", "Séli", "Dame du Lac"], 0), ("personnage", "Quel enchanteur accompagne Arthur ?", ["Merlin", "Méléagant", "Le Répurgateur", "Venec"], 0), ("personnage", "Qui est le rival d'Arthur amoureux de Guenièvre ?", ["Lancelot", "Gauvain", "Yvain", "Bohort"], 0), ("personnage", "Quel est le prénom de la reine de Carmélide ?", ["Séli", "Guenièvre", "Mevanwi", "Anna"], 0), ("personnage", "Quel est le prénom du roi de Bretagne ?", ["Arthur", "Léodagan", "Bohort", "Perceval"], 0), ("univers", "Que les chevaliers cherchent-ils principalement ?", ["Le Graal", "Le Trône de Fer", "Une épée magique", "Un trésor romain"], 0)],
        "vf": [("Kaamelott est une série française.", True), ("Arthur est roi de Bretagne.", True), ("Perceval est présenté comme un grand stratège dès le début.", False), ("Karadoc est passionné par la nourriture.", True), ("Merlin est un enchanteur.", True), ("Guenièvre est la sœur de Séli.", False), ("Léodagan est le père de Guenièvre.", True), ("La série reprend la légende arthurienne.", True), ("Lancelot est toujours un allié fidèle d'Arthur.", False), ("Alexandre Astier joue Arthur.", True)],
        "riddles": [("Cette série revisite une légende médiévale.", "Son héros cherche le Graal avec ses chevaliers.", "Son titre est Kaamelott.", "Kaamelott"), ("Cette série suit un roi souvent exaspéré par son entourage.", "Il règne sur la Bretagne et cherche le Graal.", "Il s'appelle Arthur.", "Kaamelott"), ("Cette série comprend un chevalier très attachant.", "Il parle souvent de manière approximative et vient de Gaunes.", "Il s'appelle Perceval.", "Kaamelott"), ("Cette série met en scène un chevalier obsédé par la nourriture.", "Il est souvent accompagné de Perceval.", "Il s'appelle Karadoc.", "Kaamelott"), ("Cette série présente un enchanteur peu efficace.", "Il est censé maîtriser la magie.", "Il s'appelle Merlin.", "Kaamelott"), ("Cette série comprend une reine mariée à Arthur.", "Elle vient de Carmélide et supporte difficilement la cour.", "Elle s'appelle Guenièvre.", "Kaamelott"), ("Cette série montre un seigneur très autoritaire.", "Il est le père de Guenièvre et le beau-père d'Arthur.", "Il s'appelle Léodagan.", "Kaamelott"), ("Cette série met en scène un ancien allié qui devient rival.", "Il aime Guenièvre et rejette la politique d'Arthur.", "Il s'appelle Lancelot.", "Kaamelott"), ("Cette série contient des épisodes courts et humoristiques.", "Elle adapte librement les récits du roi Arthur.", "Elle s'appelle Kaamelott.", "Kaamelott"), ("Cette série est écrite et interprétée notamment par Alexandre Astier.", "Elle mélange humour moderne et légende arthurienne.", "Son titre est Kaamelott.", "Kaamelott")],
        "quotes": [("« C'est pas faux. » — De quelle série cette réplique est-elle emblématique ?", "Kaamelott"), ("« On en a gros ! » — De quelle série vient cette phrase culte ?", "Kaamelott"), ("« Le gras, c'est la vie. » — De quelle série vient cette réplique ?", "Kaamelott"), ("« La stratégie, c'est deux lignes dans un livre. » — De quelle série vient cette réplique ?", "Kaamelott"), ("« Perceval, écoutez-moi bien… » — À quelle série cette adresse est-elle associée ?", "Kaamelott")],
        "emoji": [("👑⚔️🏰", "Kaamelott"), ("🍖🍗😂", "Kaamelott"), ("🧙‍♂️✨📜", "Kaamelott"), ("⚔️🏆❓", "Kaamelott"), ("🛡️🐴🗣️", "Kaamelott")],
        "titles": ["Kaamelott"] * 5,
    },
    "Stranger Things": {
        "slug": "stranger-things", "genre": "science-fiction", "country": "etats-unis", "era": "annees-1980",
        "qcm": [("univers", "Dans quelle ville se déroule principalement la série ?", ["Hawkins", "Sunnydale", "Riverdale", "Mystic Falls"], 0), ("personnage", "Quel est le prénom de la jeune fille aux pouvoirs psychiques ?", ["Eleven", "Max", "Nancy", "Robin"], 0), ("univers", "Comment s'appelle le monde parallèle ?", ["Le Monde à l'envers", "Le Néant", "La Zone", "Le Sous-Monde"], 0), ("personnage", "Quel personnage est le shérif de Hawkins ?", ["Jim Hopper", "Bob Newby", "Steve Harrington", "Murray Bauman"], 0), ("personnage", "Quel jeu les enfants pratiquent-ils souvent ?", ["Donjons et Dragons", "Monopoly", "Cluedo", "Risk"], 0), ("personnage", "Comment s'appelle le monstre de la première saison ?", ["Demogorgon", "Mind Flayer", "Vecna", "Bête de l'Ombre"], 0), ("personnage", "Quel est le frère de Will Byers ?", ["Jonathan", "Billy", "Dustin", "Lucas"], 0), ("personnage", "Quel personnage aime les inventions et les sciences ?", ["Dustin", "Steve", "Eddie", "Hopper"], 0), ("univers", "Quelle décennie inspire fortement l'esthétique de la série ?", ["Les années 1980", "Les années 1960", "Les années 1990", "Les années 2000"], 0), ("personnage", "Quel personnage devient proche d'Eleven ?", ["Mike", "Murray", "Ted", "Dmitri"], 0)],
        "vf": [("Stranger Things se déroule principalement dans les années 1980.", True), ("Hawkins est une ville réelle de Californie.", False), ("Eleven possède des pouvoirs psychiques.", True), ("Will Byers disparaît au début de la série.", True), ("Jim Hopper est shérif.", True), ("Le Monde à l'envers est un monde parallèle.", True), ("Dustin est le frère de Nancy.", False), ("Mike fait partie du groupe d'amis principal.", True), ("Le Demogorgon est un personnage comique.", False), ("La série mélange science-fiction et horreur.", True)],
        "riddles": [("Cette série commence par la disparition d'un garçon.", "Ses amis découvrent un monde parallèle.", "Le garçon s'appelle Will Byers.", "Stranger Things"), ("Cette série met en scène une jeune fille aux pouvoirs.", "Elle porte souvent un prénom qui est aussi un nombre.", "Elle s'appelle Eleven.", "Stranger Things"), ("Cette série se déroule dans une petite ville américaine.", "La ville est liée à des expériences secrètes.", "Elle s'appelle Hawkins.", "Stranger Things"), ("Cette série présente un univers sombre parallèle.", "Il ressemble à Hawkins mais est envahi par des créatures.", "C'est le Monde à l'envers.", "Stranger Things"), ("Cette série suit un groupe d'enfants passionnés par un jeu de rôle.", "Ils affrontent ensuite des menaces bien réelles.", "Le jeu est Donjons et Dragons.", "Stranger Things"), ("Cette série met en scène un shérif protecteur.", "Il enquête sur les phénomènes étranges de Hawkins.", "Il s'appelle Jim Hopper.", "Stranger Things"), ("Cette série est fortement marquée par la culture des années 1980.", "Elle comprend des vélos et des salles d'arcade.", "Son titre est Stranger Things.", "Stranger Things"), ("Cette série présente une créature sans visage humain.", "Elle vient du Monde à l'envers et menace Hawkins.", "C'est le Demogorgon.", "Stranger Things"), ("Cette série suit un groupe d'amis dont Mike fait partie.", "Ils recherchent leur ami disparu et protègent Eleven.", "Il s'agit de Stranger Things.", "Stranger Things"), ("Cette série a été créée par les frères Duffer.", "Elle mélange aventure, horreur et science-fiction.", "Son titre est Stranger Things.", "Stranger Things")],
        "quotes": [("« Friends don't lie. » — De quelle série cette phrase est-elle emblématique ?", "Stranger Things"), ("« She's our friend and she's crazy! » — De quelle série vient cette phrase ?", "Stranger Things"), ("« Mornings are for coffee and contemplation. » — De quelle série vient cette réplique ?", "Stranger Things"), ("« Why are you keeping this curiosity door locked? » — De quelle série vient cette phrase ?", "Stranger Things"), ("« Chrissy, wake up! » — De quelle série cette phrase est-elle devenue virale ?", "Stranger Things")],
        "emoji": [("🚲👦🌲", "Stranger Things"), ("🔢👧🩸", "Stranger Things"), ("🎲🐉🕳️", "Stranger Things"), ("☕🚔🧔", "Stranger Things"), ("🌌👹⚡", "Stranger Things")],
        "titles": ["Stranger Things"] * 5,
    },
}

FILES = {"qcm_serie.json": ("qcm", "qcm"), "var_faux_serie.json": ("vrai_faux", "vf"), "devinette_serie.json": ("devinette", "riddles"), "citation_serie.json": ("citation", "quotes"), "emoji_serie.json": ("emoji", "emoji"), "melange_serie.json": ("film_melange", "titles")}

for filename, (mode, key) in FILES.items():
    records = []
    for series_index, (series_name, info) in enumerate(SERIES.items()):
        tags = [{"name": info["slug"], "type": "univers"}, {"name": info["genre"], "type": "genre"}, {"name": info["country"], "type": "pays"}, {"name": info["era"], "type": "epoque"}]
        for item_index, item in enumerate(info[key]):
            question_id = 1000 + series_index * 100 + item_index
            if mode == "qcm":
                category, prompt, options, correct = item
                payload, answer = {"options": options}, {"index": correct}
            elif mode == "vrai_faux":
                prompt, value = item
                category, payload, answer = "anecdote", {}, {"value": value}
            elif mode == "devinette":
                hint1, hint2, hint3, answer_text = item
                category, prompt, payload, answer = "anecdote", "", {"hints": [hint1, hint2, hint3]}, {"film": answer_text}
            elif mode in ("citation", "emoji"):
                prompt, answer_text = item
                category, payload, answer = "anecdote", {}, {"film": answer_text}
            else:
                category, prompt, payload, answer = "anecdote", "", {}, {"title": item}
            records.append({"id": question_id, "mode": mode, "category": category, "content_type": "serie", "difficulty": "facile" if item_index < 5 else "moyen", "prompt": prompt, "payload": payload, "correct_answer": answer, "requires_account": False, "tags": tags})
    (BASE / filename).write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(filename, len(records))
