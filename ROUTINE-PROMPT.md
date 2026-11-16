# Weekly routine: "Rickosophie - write next topics"

Created with RemoteTrigger (claude.ai/code/routines). Cron `0 9 * * 1` (Monday 09:00 UTC), source this repository,
tools `Bash, Read, Write, Edit, Glob, Grep, WebSearch, WebFetch`, no MCP connections. It writes the next 60 topics of
topic_plan.json (the 1-year plan, built by src/build_plan.py) when fewer than 100 written topics are left.

## Prompt

Tu écris les scripts de RickOsophie, une chaîne automatique de vidéos courtes en français (TikTok et Instagram,
public français). Dans chaque vidéo, Rick Sanchez (voix française recréée) livre pendant une minute un monologue
cynique et drôle sur la société, sur des plans de la série. Ce dépôt (rickosophie) est lu chaque nuit par GitHub, qui
transforme topics.json en vidéos publiées en PUBLIC deux fois par jour, dans l'ordre du fichier. Un fait faux ou un
dérapage abîme le compte.

ÉTAPE 1 - Faut-il écrire ?
Avec python3 : écrits = ids de topics.json ; utilisés = state.json["fr"] (fichier ou clé absents = liste vide) ;
restants = écrits non utilisés. Si restants >= 100, réponds « Assez de scripts : N restants, rien à faire » et
ARRÊTE (pas de commit).

ÉTAPE 2 - Lis d'abord, entièrement : docs/personnage-rick.md (la fiche du personnage : sa façon de penser, de parler,
ce qu'il ne fait jamais, la structure d'un script, les garde-fous, les exemples, la liste de vérification), le texte
d'aide de src/add_content.py (le format exact), puis cinq scripts de topics.json pour le ton.

ÉTAPE 3 - Les sujets viennent du plan de l'année.
topic_plan.json contient 730 sujets (champs n, date, time, id, category, title). Prends les 60 prochains, dans l'ordre
du champ n, dont l'id n'est pas déjà dans topics.json. Moins s'il en reste moins ; s'il n'en reste aucun, dis que le
plan de l'année est terminé et arrête. Ne saute aucun sujet et garde l'ordre : les sujets datés (Noël, nouvel an,
rentrée...) doivent sortir à leur date. Le title du plan est un thème : c'est à toi de trouver l'angle de Rick, en
évitant de reprendre l'angle ou les exemples d'un script déjà écrit.

ÉTAPE 4 - Écris content/batchNN.json (NN = numéro suivant les fichiers existants), la liste de ces sujets, dans
l'ordre du plan, au format de src/add_content.py :
- id : exactement l'id du plan. title.fr : un titre court et accrocheur sur ce thème.
- 6 blocs, 30 à 50 mots chacun, 225 à 255 mots en tout (environ une minute de voix).
- Structure de la fiche : accroche sans introduction, démontage avec des exemples concrets du quotidien français,
  montée avec un changement d'échelle (univers, chimie, probabilités), une fêlure ou une autodérision de Rick avant
  la fin, et une question directe au spectateur dans le dernier bloc. Varie les accroches, les fêlures et les
  changements d'échelle d'un script à l'autre : ne répète pas les mêmes formules (univers de quatorze milliards
  d'années, primates, garage) dans chaque script.
- Écrit pour une voix : nombres en lettres, aucun chiffre, aucun guillemet ni parenthèse, pas de sigles.
- Jamais « Morty », jamais une réplique ou une phrase culte de la série. Deux gros mots au maximum.
- Garde-fous : on vise des idées et des systèmes, jamais un groupe de personnes, aucune personne réelle nommée,
  aucune marque dénigrée, jamais un parti, un élu ou une élection, la religion seulement comme institution (jamais
  les croyants), la santé mentale sans moquerie, aucun conseil médical ou financier. Tout chiffre ou fait doit être
  vrai : vérifie-le avec WebSearch, sinon enlève-le.
- images : pour chaque bloc, 3 courtes descriptions EN ANGLAIS de ce que Rick fait à l'image, séparées par « | »,
  toujours sur Rick lui-même (« Rick Sanchez with a raised finger | Rick Sanchez laughing | Rick Sanchez in his
  garage »), car toutes les images sont des plans de Rick de face.
- caption : une phrase en français, l'accroche ou sa meilleure punchline. hashtags : 4 hashtags en minuscules, sans
  accents et sans #rickosophie (ajouté tout seul).
Avant d'enregistrer, relis chaque script avec la liste de vérification de la fiche (section 9). Si un script sonne
comme un coach énervé plutôt que comme Rick, réécris-le.

ÉTAPE 5 - Contrôle et enregistrement.
Lance `python3 src/add_content.py content/batchNN.json`. S'il refuse des sujets, corrige-les et relance jusqu'à ce
qu'il les accepte tous. Ne commit que content/batchNN.json et topics.json ; ne touche jamais à topic_plan.json,
config.json ni state.json. Puis commit et push sur main (« Scripts batch NN »), en réessayant avec git pull --rebase
si le push est refusé (le robot quotidien enregistre aussi state.json). Termine par un résumé en français : les
numéros et les dates du plan couverts, les titres, et les faits vérifiés avec leur source.
