"""Génération contrôlée de lots de questions par genre."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "data" / "questions"

def tag(name, kind="genre"):
    return {"name": name, "type": kind}

def make(i, mode, content_type, prompt, payload, answer, genres, univers=None, saga=None, pays=None, epoque=None):
    tags = [tag(x) for x in genres]
    if univers: tags.append(tag(univers, "univers"))
    if saga: tags.append(tag(saga, "saga"))
    if pays: tags.append(tag(pays, "pays"))
    if epoque: tags.append(tag(epoque, "epoque"))
    return {"id": i, "mode": mode, "content_type": content_type, "prompt": prompt, "payload": payload, "correct_answer": answer, "requires_account": False, "tags": tags}

COMEDY = [
make(61000,"qcm","film","Dans Les Visiteurs, qui interprète Godefroy de Montmirail ?",{"options":["Jean Reno","Christian Clavier","Gérard Depardieu","Thierry Lhermitte"]},{"index":0},["comédie","fantasy"],saga="Les Visiteurs",pays="france",epoque="annees-1990"),
make(61001,"qcm","film","Dans Astérix et Obélix : Mission Cléopâtre, qui joue Numérobis ?",{"options":["Jamel Debbouze","José Garcia","Alain Chabat","Édouard Baer"]},{"index":0},["comédie","aventure"],univers="Astérix",pays="france",epoque="annees-2000"),
make(61002,"qcm","film","Dans Maman, j'ai raté l'avion !, comment s'appelle le jeune héros ?",{"options":["Kevin McCallister","Peter McCallister","Buzz McCallister","Harry Lime"]},{"index":0},["comédie","aventure","familial"],saga="Maman j'ai raté l'avion",pays="etats-unis",epoque="annees-1990"),
make(61003,"qcm","film","Dans La Cité de la peur, quel trio d'acteurs forme les membres des Nuls à l'écran ?",{"options":["Chabat, Farrugia et Lauby","Clavier, Reno et Lhermitte","Boon, Merad et Kad","Dujardin, Lamy et Elmaleh"]},{"index":0},["comédie"],univers="La Cité de la peur",pays="france",epoque="annees-1990"),
make(61004,"qcm","film","Dans The Mask, quel objet transforme Stanley Ipkiss ?",{"options":["Un masque magique","Une bague","Une montre","Un chapeau"]},{"index":0},["comédie","fantasy"],univers="The Mask",pays="etats-unis",epoque="annees-1990"),
make(61005,"qcm","film","Dans Un jour sans fin, quelle journée Phil revit-il sans cesse ?",{"options":["Le jour de la marmotte","Le réveillon","Le 14 juillet","Son anniversaire"]},{"index":0},["comédie","fantasy"],univers="Un jour sans fin",pays="etats-unis",epoque="annees-1990"),
make(61006,"qcm","film","Dans Le Dîner de cons, que fabrique François Pignon ?",{"options":["Des maquettes en allumettes","Des trains miniatures","Des poupées","Des meubles"]},{"index":0},["comédie"],univers="Le Dîner de cons",pays="france",epoque="annees-1990"),
make(61007,"qcm","film","Dans The Big Lebowski, quel surnom porte Jeffrey Lebowski ?",{"options":["The Dude","The Chief","The Man","The Player"]},{"index":0},["comédie","policier"],univers="The Big Lebowski",pays="etats-unis",epoque="annees-1990"),
make(61008,"qcm","serie","Dans Friends, quel métier exerce Ross ?",{"options":["Paléontologue","Avocat","Chef cuisinier","Médecin"]},{"index":0},["comédie"],univers="Friends",pays="etats-unis",epoque="annees-1990"),
make(61009,"qcm","serie","Dans The Office, dans quelle entreprise travaillent les personnages principaux ?",{"options":["Dunder Mifflin","Wernham Hogg","Waystar Royco","Sterling Cooper"]},{"index":0},["comédie"],univers="The Office",pays="etats-unis",epoque="annees-2000"),
make(61010,"vrai_faux","film","Dans Les Visiteurs, Godefroy et Jacquouille viennent du Moyen Âge.",{}, {"value":True},["comédie","fantasy"],saga="Les Visiteurs",pays="france",epoque="annees-1990"),
make(61011,"vrai_faux","film","Dans Maman, j'ai raté l'avion !, Kevin est oublié à Chicago.",{}, {"value":True},["comédie","aventure","familial"],saga="Maman j'ai raté l'avion",pays="etats-unis",epoque="annees-1990"),
make(61012,"vrai_faux","film","Alain Chabat réalise Astérix et Obélix : Mission Cléopâtre.",{}, {"value":True},["comédie","aventure"],univers="Astérix",pays="france",epoque="annees-2000"),
make(61013,"vrai_faux","film","Dans The Mask, Stanley Ipkiss est un super-héros avant de porter le masque.",{}, {"value":False},["comédie","fantasy"],univers="The Mask",pays="etats-unis",epoque="annees-1990"),
make(61014,"vrai_faux","film","Un jour sans fin se déroule principalement à Punxsutawney.",{}, {"value":True},["comédie","fantasy"],univers="Un jour sans fin",pays="etats-unis",epoque="annees-1990"),
make(61015,"vrai_faux","film","Dans Le Dîner de cons, Pierre Brochant organise un dîner avec François Pignon.",{}, {"value":True},["comédie"],univers="Le Dîner de cons",pays="france",epoque="annees-1990"),
make(61016,"vrai_faux","film","The Big Lebowski est réalisé par les frères Coen.",{}, {"value":True},["comédie","policier"],univers="The Big Lebowski",pays="etats-unis",epoque="annees-1990"),
make(61017,"vrai_faux","serie","Dans Friends, Chandler travaille dans la paléontologie.",{}, {"value":False},["comédie"],univers="Friends",pays="etats-unis",epoque="annees-1990"),
make(61018,"vrai_faux","serie","Dans The Office, Michael Scott dirige la succursale de Scranton.",{}, {"value":True},["comédie"],univers="The Office",pays="etats-unis",epoque="annees-2000"),
make(61019,"citation","film","« On ne met pas Bébé dans un coin. » — De quel film vient cette réplique ?",{}, {"film":"Dirty Dancing"},["comédie","romance","musique"],univers="Dirty Dancing",pays="etats-unis",epoque="annees-1980"),
make(61020,"citation","film","« Je suis ton père... » — De quel film vient cette réplique parodiée dans de nombreuses comédies ?",{}, {"film":"Star Wars"},["comédie","science-fiction"],univers="Star Wars",pays="etats-unis",epoque="annees-1980"),
make(61021,"devinette","film","Quel film se cache derrière ces indices de comédie française ?",{"hints":["Deux hommes venus du Moyen Âge arrivent à l'époque moderne.","Un serviteur porte un nom très reconnaissable.","Jean Reno et Christian Clavier sont en tête d'affiche."]},{"film":"Les Visiteurs"},["comédie","fantasy"],univers="Les Visiteurs",pays="france",epoque="annees-1990"),
make(61022,"devinette","film","Quel film se cache derrière ces indices de voyage temporel ?",{"hints":["Un homme revit sans cesse la même journée.","Une fête traditionnelle est au centre du récit.","Bill Murray joue le personnage principal."]},{"film":"Un jour sans fin"},["comédie","fantasy"],univers="Un jour sans fin",pays="etats-unis",epoque="annees-1990"),
make(61023,"devinette","film","Quel film se cache derrière ces indices de dîner ?",{"hints":["Un éditeur invite des personnes considérées comme originales.","Un invité fabrique des maquettes en allumettes.","Le personnage s'appelle François Pignon."]},{"film":"Le Dîner de cons"},["comédie"],univers="Le Dîner de cons",pays="france",epoque="annees-1990"),
make(61024,"devinette","film","Quel film se cache derrière ces indices de masque ?",{"hints":["Un employé de banque découvre un objet surnaturel.","L'objet transforme son comportement et son apparence.","Jim Carrey tient le rôle principal."]},{"film":"The Mask"},["comédie","fantasy"],univers="The Mask",pays="etats-unis",epoque="annees-1990"),
make(61025,"chronologie","film","Classez ces comédies françaises de la plus ancienne à la plus récente.",{"films":["Le Dîner de cons","Les Visiteurs","Astérix et Obélix : Mission Cléopâtre","Intouchables"]},{"order":["Le Dîner de cons","Les Visiteurs","Astérix et Obélix : Mission Cléopâtre","Intouchables"]},["comédie"],pays="france"),
make(61026,"chronologie","film","Classez ces films de Jim Carrey du plus ancien au plus récent.",{"films":["The Mask","Menteur, menteur","Bruce tout-puissant","Yes Man"]},{"order":["The Mask","Menteur, menteur","Bruce tout-puissant","Yes Man"]},["comédie","fantasy"],pays="etats-unis"),
make(61027,"casting","film","À quel film appartiennent ces membres du casting ?",{"actor_photos":["https://image.tmdb.org/t/p/w500/wo2hJpn04vbtmh0B9utCFdsQhxM.jpg","https://image.tmdb.org/t/p/w500/9WsvKjheeizXCcZrFjZCrCoItqO.jpg","https://image.tmdb.org/t/p/w500/aiqWSWbRJ6rrjxxVE6y2Xb3KdSp.jpg"]},{"film":"Astérix et Obélix : Mission Cléopâtre"},["comédie","aventure"],univers="Astérix",pays="france",epoque="annees-2000"),
make(61028,"film_melange","film","Quel film se cache derrière cette image ?",{"question_image_url":"https://image.tmdb.org/t/p/w500/tH7GoWIooWdKwF4GTUuIVc3pnnN.jpg"},{"title":"Les Visiteurs"},["comédie","fantasy"],univers="Les Visiteurs",pays="france",epoque="annees-1990"),
make(61029,"qcm","serie","Dans Kaamelott, quel est le nom du roi joué par Alexandre Astier ?",{"options":["Arthur","Perceval","Lancelot","Karadoc"]},{"index":0},["comédie","fantasy"],univers="Kaamelott",pays="france",epoque="annees-2000"),
]

THRILLER = [
make(62000,"qcm","film","Dans Seven, quels crimes servent de fil conducteur à l'enquête ?",{"options":["Les sept péchés capitaux","Les douze travaux","Les cinq éléments","Les quatre saisons"]},{"index":0},["thriller","policier","mystère"],univers="Seven",pays="etats-unis",epoque="annees-1990"),
make(62001,"qcm","film","Dans Le Silence des agneaux, quel agent interroge Hannibal Lecter ?",{"options":["Clarice Starling","Dana Scully","Ellen Ripley","Marge Gunderson"]},{"index":0},["thriller","policier","drame"],univers="Le Silence des agneaux",pays="etats-unis",epoque="annees-1990"),
make(62002,"qcm","film","Dans Memento, quel problème affecte Leonard Shelby ?",{"options":["Une perte de mémoire récente","La cécité","La surdité","Une amnésie de l'enfance"]},{"index":0},["thriller","mystère"],univers="Memento",pays="etats-unis",epoque="annees-2000"),
make(62003,"qcm","film","Quel réalisateur a signé Gone Girl ?",{"options":["David Fincher","Christopher Nolan","Denis Villeneuve","Martin Scorsese"]},{"index":0},["thriller","mystère","drame"],univers="Gone Girl",pays="etats-unis",epoque="annees-2010"),
make(62004,"qcm","film","Dans Us, quel élément est associé aux doubles des personnages ?",{"options":["Les Tethered","Les Inconnus","Les Ombres","Les Reflets"]},{"index":0},["thriller","horreur","mystère"],univers="Us",pays="etats-unis",epoque="annees-2010"),
make(62005,"qcm","film","Dans Shutter Island, où se déroule principalement l'intrigue ?",{"options":["Sur une île abritant un hôpital psychiatrique","Dans une station spatiale","Dans un hôtel","Dans un sous-marin"]},{"index":0},["thriller","mystère","drame"],univers="Shutter Island",pays="etats-unis",epoque="annees-2010"),
make(62006,"qcm","film","Dans Zodiac, quelle affaire est au centre de l'enquête ?",{"options":["Un tueur qui envoie des lettres codées","Un braquage de banque","Une disparition en mer","Un espionnage industriel"]},{"index":0},["thriller","policier","mystère"],univers="Zodiac",pays="etats-unis",epoque="annees-2000"),
make(62007,"qcm","film","Dans Inception, quel objet permet à Cobb de vérifier la réalité ?",{"options":["Une toupie","Une montre","Une pièce","Une bague"]},{"index":0},["thriller","science-fiction"],univers="Inception",pays="etats-unis",epoque="annees-2010"),
make(62008,"qcm","serie","Dans Breaking Bad, quelle activité devient le centre de l'ascension de Walter White ?",{"options":["La production de méthamphétamine","Le trafic d'armes","Le piratage informatique","Le jeu clandestin"]},{"index":0},["thriller","policier","drame"],univers="Breaking Bad",pays="etats-unis",epoque="annees-2000"),
make(62009,"qcm","serie","Dans Dexter, quel métier officiel exerce Dexter Morgan ?",{"options":["Expert médico-légal spécialisé dans le sang","Avocat","Médecin légiste","Journaliste"]},{"index":0},["thriller","policier","drame"],univers="Dexter",pays="etats-unis",epoque="annees-2000"),
make(62010,"vrai_faux","film","Seven a été réalisé par David Fincher.",{}, {"value":True},["thriller","policier","mystère"],univers="Seven",pays="etats-unis",epoque="annees-1990"),
make(62011,"vrai_faux","film","Clarice Starling est une agente du FBI dans Le Silence des agneaux.",{}, {"value":True},["thriller","policier","drame"],univers="Le Silence des agneaux",pays="etats-unis",epoque="annees-1990"),
make(62012,"vrai_faux","film","Memento raconte une histoire présentée dans un ordre chronologique classique.",{}, {"value":False},["thriller","mystère"],univers="Memento",pays="etats-unis",epoque="annees-2000"),
make(62013,"vrai_faux","film","Gone Girl est adapté d'un roman de Gillian Flynn.",{}, {"value":True},["thriller","mystère","drame"],univers="Gone Girl",pays="etats-unis",epoque="annees-2010"),
make(62014,"vrai_faux","film","Dans Inception, les rêves peuvent être partagés entre plusieurs personnes.",{}, {"value":True},["thriller","science-fiction"],univers="Inception",pays="etats-unis",epoque="annees-2010"),
make(62015,"vrai_faux","film","Shutter Island se déroule dans une petite ville française.",{}, {"value":False},["thriller","mystère","drame"],univers="Shutter Island",pays="etats-unis",epoque="annees-2010"),
make(62016,"vrai_faux","serie","Walter White est professeur de chimie au début de Breaking Bad.",{}, {"value":True},["thriller","policier","drame"],univers="Breaking Bad",pays="etats-unis",epoque="annees-2000"),
make(62017,"vrai_faux","serie","Dexter Morgan travaille comme expert en traces de sang.",{}, {"value":True},["thriller","policier","drame"],univers="Dexter",pays="etats-unis",epoque="annees-2000"),
make(62018,"citation","film","« Qu'y a-t-il dans la boîte ?! » — De quel film vient cette réplique ?",{}, {"film":"Seven"},["thriller","policier","mystère"],univers="Seven",pays="etats-unis",epoque="annees-1990"),
make(62019,"citation","film","« Je vois des personnes mortes. » — De quel film vient cette réplique ?",{}, {"film":"Sixième Sens"},["thriller","mystère","drame"],univers="Sixième Sens",pays="etats-unis",epoque="annees-1990"),
make(62020,"devinette","film","Quel thriller se cache derrière ces indices ?",{"hints":["Deux inspecteurs enquêtent sur une série de crimes.","Les crimes renvoient aux sept péchés capitaux.","David Fincher réalise le film."]},{"film":"Seven"},["thriller","policier","mystère"],univers="Seven",pays="etats-unis",epoque="annees-1990"),
make(62021,"devinette","film","Quel thriller se cache derrière ces indices de mémoire ?",{"hints":["Le héros enquête sur la mort de sa femme.","Il ne peut plus créer de nouveaux souvenirs.","Le récit joue avec l'ordre des événements."]},{"film":"Memento"},["thriller","mystère"],univers="Memento",pays="etats-unis",epoque="annees-2000"),
make(62022,"devinette","film","Quel thriller se cache derrière ces indices judiciaires ?",{"hints":["Une disparition bouleverse un couple.","La presse et l'opinion publique s'en mêlent.","David Fincher adapte un roman de Gillian Flynn."]},{"film":"Gone Girl"},["thriller","mystère","drame"],univers="Gone Girl",pays="etats-unis",epoque="annees-2010"),
make(62023,"devinette","film","Quel thriller se cache derrière ces indices insulaires ?",{"hints":["Un marshal arrive sur une île isolée.","Un établissement psychiatrique y accueille des criminels.","Leonardo DiCaprio tient le rôle principal."]},{"film":"Shutter Island"},["thriller","mystère","drame"],univers="Shutter Island",pays="etats-unis",epoque="annees-2010"),
make(62024,"chronologie","film","Classez ces thrillers de David Fincher du plus ancien au plus récent.",{"films":["Seven","Fight Club","Zodiac","Gone Girl"]},{"order":["Seven","Fight Club","Zodiac","Gone Girl"]},["thriller","mystère"],pays="etats-unis"),
make(62025,"chronologie","film","Classez ces films de Christopher Nolan du plus ancien au plus récent.",{"films":["Memento","The Dark Knight","Inception","Interstellar"]},{"order":["Memento","The Dark Knight","Inception","Interstellar"]},["thriller","science-fiction"],pays="etats-unis"),
make(62026,"casting","film","À quel thriller appartiennent ces membres du casting ?",{"actor_photos":["https://image.tmdb.org/t/p/w500/905k0RFzH0Kd6gx8oSxRdnr6FL.jpg","https://image.tmdb.org/t/p/w500/ajNaPmXVVMJFg9GWmu6MJzTaXdV.jpg","https://image.tmdb.org/t/p/w500/r4wbWWEEjmtRFZ0GU10XbLTgp47.jpg"]},{"film":"Seven"},["thriller","policier","mystère"],univers="Seven",pays="etats-unis",epoque="annees-1990"),
make(62027,"film_melange","film","Quel film se cache derrière cette image ?",{"question_image_url":"https://image.tmdb.org/t/p/w500/i5H7zusQGsysGQ8i6P361Vnr0n2.jpg"},{"title":"Seven"},["thriller","policier","mystère"],univers="Seven",pays="etats-unis",epoque="annees-1990"),
make(62028,"qcm","serie","Dans Sherlock, quelle ville est le principal décor de l'histoire ?",{"options":["Londres","Manchester","Dublin","Édimbourg"]},{"index":0},["thriller","policier","mystère"],univers="Sherlock",pays="royaume-uni",epoque="annees-2010"),
make(62029,"vrai_faux","serie","Dans Sherlock, John Watson est médecin militaire avant de rencontrer Sherlock Holmes.",{}, {"value":True},["thriller","policier","mystère"],univers="Sherlock",pays="royaume-uni",epoque="annees-2010"),
]

CATALOG = {"horreur": [], "comédie": COMEDY, "thriller": THRILLER}
MODE_FILES = {("film","qcm"):"qcm.json",("serie","qcm"):"qcm_serie.json",("film","vrai_faux"):"vrai_faux.json",("serie","vrai_faux"):"vrai_faux_serie.json",("film","citation"):"citation.json",("serie","citation"):"citation_serie.json",("film","devinette"):"devinette.json",("serie","devinette"):"devinette_serie.json",("film","chronologie"):"chronologie.json",("serie","chronologie"):"chronologie_serie.json",("film","casting"):"casting.json",("serie","casting"):"casting_serie.json",("film","film_melange"):"film_melange.json",("serie","film_melange"):"melange_serie.json"}

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--genres",nargs="+",required=True); parser.add_argument("--per-genre",type=int,default=30); parser.add_argument("--dry-run",action="store_true"); args=parser.parse_args()
    known_ids=set(); keys=set()
    for path in QUESTIONS.glob("*.json"):
        for row in json.loads(path.read_text(encoding="utf-8")):
            known_ids.add(row["id"]); keys.add((row["mode"],row["prompt"],json.dumps(row["correct_answer"],sort_keys=True,ensure_ascii=False)))
    selected=[]
    for genre in args.genres:
        rows=CATALOG.get(genre,[])
        if len(rows)<args.per_genre: raise SystemExit(f"{genre}: {len(rows)} question(s), {args.per_genre} requises")
        selected.extend(rows[:args.per_genre])
    ids=[x["id"] for x in selected]
    if len(ids)!=len(set(ids)) or any(x in known_ids for x in ids): raise SystemExit("IDs dupliqués ou déjà utilisés")
    for row in selected:
        key=(row["mode"],row["prompt"],json.dumps(row["correct_answer"],sort_keys=True,ensure_ascii=False))
        if key in keys: raise SystemExit(f"Doublon détecté : {row['prompt']}")
    if args.dry_run: print(f"Lot valide : {len(selected)} question(s)"); return
    grouped={}
    for row in selected: grouped.setdefault(QUESTIONS/MODE_FILES[(row["content_type"],row["mode"])],[]).append(row)
    for path, additions in grouped.items():
        rows=json.loads(path.read_text(encoding="utf-8")); rows.extend(additions); path.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(f"{path.name}: +{len(additions)}")

if __name__ == "__main__": main()
