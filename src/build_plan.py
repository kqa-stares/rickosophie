"""Build topic_plan.json: 730 Rickosophie topics (2 a day for one year), mixed across categories.

The 29 topics already written come first, in posting order (WRITTEN). The rest are spread evenly so the same
category rarely comes twice in a row, and dated topics (SEASONAL) are moved to their day. Titles are themes for
the writing task, not captions: the task finds Rick's angle on each one.
Run: python src/build_plan.py   (it refuses duplicates and any total other than 730)
"""
import json
import re
import sys
import unicodedata
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
START = date(2026, 11, 16)  # launch day, first video at 08:00
SLOTS = ["08:00", "20:00"]

# already written (topics.json), in posting order: id, title, category
WRITTEN = [
    ("telephone", "Le téléphone", "Écrans et réseaux"), ("amour", "L'amour", "Amour et famille"),
    ("travail", "Le travail", "Travail et argent"), ("normalite", "La normalité", "Grandes questions"),
    ("gourous", "Les gourous", "Bonheur et esprit"), ("bonheur", "Le bonheur", "Bonheur et esprit"),
    ("adultes", "Les adultes", "École et jeunesse"), ("reussite", "La réussite", "Travail et argent"),
    ("soldes", "Les soldes", "Consommation"), ("ecole", "L'école", "École et jeunesse"),
    ("argent", "L'argent", "Travail et argent"), ("influenceurs", "Les influenceurs", "Écrans et réseaux"),
    ("administration", "L'administration", "Pouvoir et société"), ("pouvoir", "Le pouvoir", "Pouvoir et société"),
    ("tradition", "La tradition", "Pouvoir et société"), ("merite", "Le mérite", "Travail et argent"),
    ("sommeil", "Le sommeil", "Corps et santé"), ("amitie", "L'amitié", "Vie quotidienne"),
    ("repas-de-famille", "Le repas de famille", "Amour et famille"), ("supermarche", "Le supermarché", "Consommation"),
    ("salle-de-sport", "La salle de sport", "Corps et santé"), ("dernier-episode", "Juste un dernier épisode", "Écrans et réseaux"),
    ("mort", "La mort", "Grandes questions"), ("sens-de-la-vie", "Le sens de la vie", "Grandes questions"),
    ("libre-arbitre", "Le libre arbitre", "Grandes questions"), ("quatre-mille-semaines", "Quatre mille semaines", "Temps et univers"),
    ("solitude", "La solitude", "Grandes questions"), ("hasard", "Le hasard", "Temps et univers"),
    ("aller-mal", "Aller mal", "Corps et santé"),
]

# titles separated by ";"
CATEGORIES = {
    "Travail et argent": """Le lundi matin; Les réunions qui auraient pu être un mail; Le CV qui ment poliment;
        L'entretien d'embauche; Le stage non payé; L'open space; Le télétravail; La retraite qu'on attend toute sa vie;
        Le crédit immobilier; Le loyer qui mange tout; Les impôts; La fiche de paie; L'augmentation qu'on n'ose pas demander;
        Le patron sympa; Le team building; Les titres de poste ronflants; La startup qui va changer le monde;
        Le métier passion; Les métiers utiles mal payés; Les métiers inutiles bien payés; Le premier salaire;
        Les fins de mois; Le découvert; Les frais bancaires; Le paiement en plusieurs fois; Les rêves de fortune rapide;
        Le loto; Les jeux d'argent; L'héritage; Être riche; La pauvreté; Le chômage; La reconversion; La productivité;
        Les vacances où on lit ses mails; Les jours fériés; Les collègues; La machine à café du bureau; Le pot de départ;
        La démission; Le licenciement; Être son propre patron; Le travail le dimanche; Les heures supplémentaires;
        Rester tard pour être vu; Le mail de vingt-trois heures; Les objectifs annuels; L'entretien annuel;
        Le salaire qu'on cache; Parler d'argent en famille; Prêter de l'argent à un ami; Le pourboire;
        Les petites dépenses invisibles; L'inflation; Le budget; L'argent ne fait pas le bonheur; Les trajets domicile travail;
        Le premier jour dans un nouveau job; La semaine de quatre jours; Les machines qui prennent nos emplois;
        Le travail qui n'a pas de sens; Faire semblant d'être occupé; Les petits boulots; Les pauses déjeuner devant l'écran""",
    "Écrans et réseaux": """Les notifications; Le scroll infini; Les likes; Les stories; Le selfie; Les filtres beauté;
        La comparaison permanente; Les commentaires haineux; Les débats en ligne; Les fausses informations; Les algorithmes;
        Les cookies qu'on accepte sans lire; Les conditions d'utilisation; Les données personnelles; L'intelligence artificielle;
        Les textes écrits par des machines; Le vu sans réponse; Les messages vocaux; Le groupe de discussion familial;
        Le téléphone à table; La batterie à un pour cent; Le mot de passe oublié; La mise à jour obligatoire;
        L'obsolescence programmée; Le nouveau téléphone; Les jeux vidéo; Les écrans des enfants; Le temps d'écran;
        La déconnexion; Le mode avion; Les tendances qui durent une semaine; Les défis viraux; Les vidéos de dix secondes;
        La célébrité d'internet; Le buzz; Le harcèlement en ligne; L'anonymat; Les avis en ligne; Les photos de vacances;
        Les mondes virtuels; Les objets connectés; L'assistant vocal qui écoute; La maison intelligente; Les spoilers;
        La mémoire de poisson rouge; Les captures d'écran; Les mèmes; La nostalgie des débuts d'internet; Le streaming;
        Les mauvaises nouvelles en boucle; Les montres qui comptent tout; Les photos de nourriture; Les faux abonnés;
        La panne d'internet; Le premier téléphone; Les écouteurs toujours dans les oreilles; Les visioconférences;
        Le partage de sa vie en direct; Les jeux sur téléphone; Les applis qu'on n'ouvre jamais; Les mails non lus;
        Être joignable tout le temps; Les vidéos de chats""",
    "Consommation": """La publicité; Les marques; Le luxe; La mode rapide; Les vêtements qu'on ne porte jamais;
        Le placard plein et rien à se mettre; Les objets inutiles; Les gadgets de cuisine; La livraison en un jour;
        Le colis qu'on attend; Les achats compulsifs; Le shopping pour se consoler; Les emballages;
        Les étiquettes écolo; La voiture; La voiture neuve; Les abonnements qu'on oublie; Les cadeaux; Les cartes cadeaux;
        Le mariage qui coûte une fortune; Le café à emporter; La malbouffe; Les compléments alimentaires;
        Les produits miracles; Les cosmétiques; Le minimalisme; Le vide-grenier; La seconde main; Le grenier plein;
        La collection; Le jetable; Les chargeurs qui s'accumulent; L'électroménager qui tombe en panne; La garantie;
        Le prix barré; Les cartes de fidélité; Le petit plaisir qu'on s'offre; L'avion; Le tourisme de masse;
        Les souvenirs de vacances; Le parc d'attractions; Les fêtes commerciales; Halloween; Le sapin de Noël;
        Les fournitures de la rentrée; Les baskets à la mode; Les montres de luxe; Le dernier cri;
        La file d'attente devant un magasin; Le fast-food; L'eau en bouteille; Le paiement sans contact;
        Le crédit gratuit; La version premium; Le panier en ligne abandonné; Les offres d'essai gratuites;
        Les produits pour enfants; Le packaging; Les centres commerciaux; Le marché du dimanche;
        Les prix qui finissent en quatre-vingt-dix-neuf; Acheter pour impressionner; La réparation plutôt que le neuf""",
    "Pouvoir et société": """La politique; Les promesses politiques; Les débats télévisés; Les sondages; La démocratie;
        La loi; La justice; La prison; L'armée; La guerre; La paix; Les frontières; Le drapeau; Le patriotisme; L'État;
        Les services publics; La sécurité sociale; L'hôpital public; Les grèves; Les manifestations; Les experts à la télé;
        Les médias; Le journal de vingt heures; La peur comme outil; La propagande; La censure; La liberté d'expression;
        Les religions comme institutions; Le dogme; La morale; Les lois absurdes; Les règlements; La surveillance;
        Les caméras partout; La vie privée; L'obéissance; La rébellion; La révolution; L'utopie; Le progrès; Le complotisme;
        L'argent public; Les lobbys; La corruption; Les inégalités; La mondialisation; La croissance infinie; L'écologie;
        Le réchauffement climatique; La fin du monde; Les animaux qu'on mange; La science; Les pseudo-sciences;
        L'astrologie; Les superstitions; La médecine; Les héros nationaux; Les statues; Les commémorations;
        Le travail des enfants dans le monde; Les records du monde; Les classements de tout; La ville; La campagne;
        La foule""",
    "Vie quotidienne": """Le réveil qui sonne; La douche du matin; Le petit déjeuner; Les transports en commun; Les bouchons;
        Le métro à l'heure de pointe; Le vélo en ville; Le permis de conduire; Les voisins; Le bruit des voisins;
        La colocation; Le déménagement; Le ménage; La vaisselle; Le linge; Les courses du samedi; La cuisine;
        Les recettes ratées; Les restes; Le frigo vide; La météo; La pluie; La canicule; L'hiver; Le dimanche soir;
        Le week-end trop court; Le retour de vacances; La valise; Les files d'attente; Le rendez-vous chez le médecin; Le dentiste;
        Le coiffeur; Les clés perdues; Les chaussettes perdues; Les plantes qui meurent; Les animaux de compagnie; Le chat;
        Le chien; Les anniversaires; Les soirées; Le lendemain de soirée; L'apéro; Les excuses pour ne pas sortir;
        Le retard; La procrastination; Les listes de choses à faire; Les bonnes résolutions; L'agenda;
        Parler de la pluie et du beau temps; Les formules de politesse; Dire non; Les compliments; Les excuses;
        Le mensonge; Les rumeurs; Les disputes; Les mariages des autres; Le camping; La plage; Le bricolage;
        Les meubles en kit; Le jardin; La voiture qui tombe en panne; Les parkings; La salle d'attente""",
    "Amour et famille": """Le premier rendez-vous; Le coup de foudre; La rupture; L'ex; Le célibat; Le mariage; Le divorce;
        Être parent; Les parents; La mère; Le père; Les frères et sœurs; Les grands-parents; La belle-famille;
        Le premier amour; Le couple qui dure; La routine du couple; La séduction; Les applis de rencontre; Le désir;
        La fidélité; L'infidélité; L'amour à distance; Les déclarations d'amour; La Saint-Valentin; Les disputes de couple;
        Emménager ensemble; Les surnoms ridicules; Les enfants qui grandissent; Le nid vide; Les familles recomposées;
        L'éducation des enfants; Les punitions; Les secrets de famille; La généalogie; Le nom de famille; Les albums photo;
        Les parents qui vieillissent; Le deuil d'un proche; Noël en famille; Les vacances en famille; La maison d'enfance;
        La comparaison avec le cousin; Les attentes des parents; Décevoir ses parents; Quitter la maison;
        Revenir chez ses parents; Faire un enfant ou pas; Les prénoms; Les bébés; Les nuits blanches des jeunes parents;
        L'amour inconditionnel; Le chagrin d'amour; Les lettres d'amour; Les ex qui reviennent; Être amoureux;
        Regarder le téléphone de l'autre; Les couples parfaits sur internet; La demande en mariage; Présenter quelqu'un à ses parents;
        Les belles-mères; Les oncles et tantes; Les cousins; La famille qu'on choisit""",
    "Corps et santé": """Le corps qu'on n'aime pas; Le miroir; La beauté; Vieillir; Les cheveux blancs; La calvitie;
        Le poids; Les régimes; Manger équilibré; Le sucre; Le café; L'alcool; La cigarette; Les addictions; Le stress;
        L'anxiété; La thérapie; Aller voir un psy; Pleurer; Les émotions; La fatigue; La sieste; Le mal de dos; Marcher;
        Courir; La douleur; La maladie; L'hypocondrie; Chercher ses symptômes sur internet; Les médicaments;
        L'effet placebo; La respiration; La méditation; Le silence; Le bruit; Le soleil; La nature qui fait du bien;
        Le corps comme machine; Les hormones; Le cerveau; La mémoire; L'oubli; Les rêves; Les cauchemars;
        Les conseils santé contradictoires; La chirurgie esthétique; Les rides; La jeunesse éternelle; Les tatouages;
        Le maquillage; Les complexes; La timidité; Le rire; Le toucher; Les câlins; Le burn-out; La santé mentale des jeunes;
        Les crises d'angoisse; Prendre soin de soi; La flemme; Les allergies; Le rhume; Les vaccins de l'enfance""",
    "École et jeunesse": """Les devoirs; Les notes; Le bac; L'orientation; Choisir ses études à dix-sept ans; Les profs;
        Le prof qui a changé ta vie; La récré; La cantine; Le harcèlement à l'école; Les groupes au lycée; Être populaire;
        Le premier de la classe; Le cancre; Les maths; La philo au lycée; L'histoire; Les langues étrangères; Les examens;
        La triche; Les diplômes; Les études longues; La fac; Les grandes écoles; L'alternance; Le premier job d'été;
        Le baby-sitting; Avoir dix-huit ans; L'argent de poche; La crise d'ado; Les parents qui ne comprennent pas;
        La phrase les jeunes d'aujourd'hui; Grandir trop vite; L'enfance; Les jouets; Les dessins animés; Le père Noël;
        Les monstres sous le lit; Les pourquoi des enfants; L'imagination; Le jeu; L'ennui; Les vacances d'été;
        La colonie de vacances; Le sac trop lourd; La rentrée; Le redoublement; Les enfants surdoués; Lire des livres;
        La bibliothèque; Le savoir inutile; La culture générale; Apprendre à apprendre; L'erreur; L'échec scolaire;
        Les voyages scolaires; Le bal de fin d'année; Les copains d'enfance; Les cours de sport; Les réseaux à quatorze ans; Les cours qu'on n'écoute pas; Le conseil de classe; Le brevet""",
    "Grandes questions": """La liberté; La vérité; Les questions sans réponse; La conscience; L'âme; La réincarnation;
        L'au-delà; L'éternité; Le néant; Le destin; Le bien et le mal; L'éthique; Le courage; La lâcheté; La peur; L'espoir;
        Le doute; La certitude; La raison; L'instinct; L'intelligence; La bêtise; Le génie; La folie; L'identité;
        Qui suis-je; L'ego; Le regard des autres; L'empathie; L'égoïsme; L'altruisme; La gentillesse; La méchanceté;
        La vengeance; Le pardon; La gratitude; Le regret; La nostalgie; Le passé; Le futur; Le présent; L'attente;
        La patience; L'ambition; La paresse; L'humanité; Les extraterrestres; La vie ailleurs; Les univers parallèles;
        Le voyage dans le temps; L'immortalité; L'humain augmenté; La fin de l'humanité; Le vide; L'absurde; Le choix;
        Le bonheur des autres; Être quelqu'un de bien; Laisser une trace; Le sens du devoir; La dignité;
        Ce qu'on ne peut pas savoir; Les grandes idées qui ont tout changé; Le temps perdu; Les promesses""",
    "Temps et univers": """L'univers; Les étoiles; Le soleil qui finira par s'éteindre; La lune; La terre vue de l'espace;
        Le big bang; Les trous noirs; L'infini; Les atomes; L'évolution; Les dinosaures; Les fourmis; Les singes; L'ADN;
        Les probabilités; Les coïncidences; Le chaos; L'entropie; La gravité; La lumière; La vitesse; Le temps qui passe;
        Les horloges; Le changement d'heure; Le calendrier; Le nouvel an; Les civilisations disparues; Les pyramides;
        L'histoire qui se répète; Les inventions; Le feu; La roue; L'écriture; L'électricité; Internet;
        La conquête spatiale; Mars; Les robots; Les ordinateurs; La science-fiction; Les prédictions ratées;
        Le futur imaginé autrefois; Les catastrophes naturelles; Les volcans; Les océans; Les virus; Les bactéries;
        Les microbes dans ton ventre; Les arbres; Les champignons; Le ciel la nuit; L'échelle des choses;
        La petitesse humaine; Les météorites; Les saisons; Le jour et la nuit; Les âges de la vie; Les dernières minutes
        de l'année; L'âge de la terre; Les animaux plus vieux que nous; Les espèces disparues; Les marées; Les éclipses""",
    "Bonheur et esprit": """La motivation; La discipline; Les habitudes; La confiance en soi; L'estime de soi;
        Le perfectionnisme; La peur de l'échec; La peur du ridicule; La honte; La culpabilité; La jalousie; L'envie;
        La colère; La rancune; La tristesse; La joie; Les petits plaisirs; Le plaisir immédiat; Le lâcher-prise;
        La pensée positive forcée; Les citations inspirantes; L'optimisme; Le pessimisme; Le cynisme; L'humour;
        La curiosité; La créativité; L'inspiration; Le talent; Les rêves d'enfant; Les passions; Les loisirs;
        Le temps libre; Ne rien faire; La lenteur; L'urgence; La charge mentale; Les décisions; Trop de choix;
        Le changement; Sortir de sa zone de confort; Le risque; L'aventure; La sécurité; Les excuses qu'on se donne;
        Dire je t'aime; Dire merci; Demander de l'aide; L'orgueil; L'humilité; Avoir raison; Changer d'avis;
        Les préjugés; Les premières impressions; La sincérité; L'hypocrisie; La sérénité; Le mauvais caractère;
        Les gens qui râlent tout le temps; Se faire confiance; Se pardonner soi-même; La comparaison avec soi d'avant; Savoir s'arrêter"""
}

# dated topics: id -> day (morning slot of that day, evening if taken)
SEASONAL = {
    "le-sapin-de-noel": "2026-12-12",
    "noel-en-famille": "2026-12-24",
    "les-dernieres-minutes-de-l-annee": "2026-12-31",
    "les-bonnes-resolutions": "2027-01-01",
    "la-saint-valentin": "2027-02-14",
    "le-changement-d-heure": "2027-03-28",
    "les-vacances-d-ete": "2027-07-03",
    "la-rentree": "2027-09-01",
    "halloween": "2027-10-31",
}


def split(text):
    return [re.sub(r"\s+", " ", t).strip() for t in text.split(";") if t.strip()]


def slug(title):
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")


def main():
    category_of, problems = {}, []
    for s, title, category in WRITTEN:
        category_of[s] = (category, title)
    for category, text in CATEGORIES.items():
        for title in split(text):
            s = slug(title)
            if s in category_of:
                problems.append(f"duplicate: {title} ({category} and {category_of[s][0]})")
            category_of[s] = (category, title)
    counts = {c: len(split(t)) for c, t in CATEGORIES.items()}
    if len(category_of) != 730:
        problems.append(f"{len(category_of)} topics in total, expected 730 ({counts})")
    problems += [f"dated topic not in a category: {s}" for s in SEASONAL if s not in category_of]
    if problems:
        sys.exit("\n".join(problems))

    first = [s for s, _, _ in WRITTEN]
    rest = []
    for category, text in CATEGORIES.items():
        items = [slug(t) for t in split(text) if slug(t) not in SEASONAL]
        rest += [((k + 0.5) / len(items), category, s) for k, s in enumerate(items)]
    order = first + [s for _, _, s in sorted(rest)]

    wanted = {}
    for s, day in SEASONAL.items():
        i = max((date.fromisoformat(day) - START).days * 2, len(first))
        while i in wanted:
            i += 1
        wanted[i] = s
    for i in sorted(wanted):
        order.insert(i, wanted[i])

    plan = [{"n": i + 1, "date": str(START + timedelta(days=i // 2)), "time": SLOTS[i % 2],
             "id": s, "category": category_of[s][0], "title": category_of[s][1]} for i, s in enumerate(order)]
    (ROOT / "topic_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(plan)} topics, {plan[0]['date']} -> {plan[-1]['date']}")
    print("per category: " + ", ".join(f"{c} {n}" for c, n in counts.items()))


if __name__ == "__main__":
    main()
