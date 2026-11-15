# Weekly routine: "Rickosophie - write next topics"

Created with RemoteTrigger (claude.ai/code/routines) once github.com/apps/claude has access to this repository:
cron `0 9 * * 1` (Monday 09:00 UTC; the other channels run at 07:00, 07:30, 08:00 and 08:30), source this repository,
tools `Bash, Read, Write, Edit, Glob, Grep, WebSearch, WebFetch`, no MCP connections. Run it once right after creating it.

## Prompt

Tu écris les scripts de RickOsophie, une chaîne automatique de vidéos courtes en français (TikTok et Instagram,
public français). Dans chaque vidéo, Rick Sanchez (voix française recréée) livre pendant une minute un monologue
cynique et drôle sur la société, sur des plans de la série. Ce dépôt (rickosophie) est lu chaque nuit par GitHub, qui
transforme topics.json en vidéos publiées en PUBLIC deux fois par jour. Un fait faux ou un dérapage abîme le compte.

ÉTAPE 1 - Faut-il écrire ?
Avec python3 : écrits = ids de topics.json ; utilisés = state.json["fr"] (fichier ou clé absents = liste vide) ;
restants = écrits non utilisés. Si restants >= 30, réponds « Assez de scripts : N restants, rien à faire » et
ARRÊTE (pas de commit).

ÉTAPE 2 - Lis d'abord, entièrement : docs/personnage-rick.md (la fiche du personnage : sa façon de penser, de parler,
ce qu'il ne fait jamais, la structure d'un script, les garde-fous, les exemples, la liste de vérification), le texte
d'aide de src/add_content.py (le format exact), puis cinq scripts de topics.json pour le ton.

ÉTAPE 3 - Choisis 20 sujets nouveaux.
Des sujets de société et de vie quotidienne qui parlent à un public français de 16 à 35 ans : travail, école, argent,
amour, famille, réseaux sociaux, consommation, réussite, bonheur, santé mentale vue sans moquerie, politique en général
(jamais un parti, un élu ou une élection), religion en tant qu'institution (jamais les croyants), mort, temps qui
passe, amitié, liberté, routine, technologie, etc. Aucun sujet déjà traité : compare avec les titres de topics.json
et ne reprends pas le même angle sous un autre mot. Varie : un tiers de sujets « société », un tiers « vie
quotidienne », un tiers « grandes questions » (sens de la vie, mort, liberté, bonheur).

ÉTAPE 4 - Écris content/batchNN.json (NN = numéro suivant les fichiers existants), une liste de 20 sujets au format
de src/add_content.py :
- 6 blocs, 30 à 50 mots chacun, 225 à 255 mots en tout (environ une minute de voix).
- Structure de la fiche : accroche sans introduction, démontage avec des exemples concrets du quotidien français,
  montée avec un changement d'échelle (univers, chimie, probabilités), une fêlure ou une autodérision de Rick avant
  la fin, et une question directe au spectateur dans le dernier bloc.
- Écrit pour une voix : nombres en lettres, aucun chiffre, aucun guillemet ni parenthèse, pas de sigles.
- Jamais « Morty », jamais une réplique ou une phrase culte de la série. Deux gros mots au maximum.
- Garde-fous : on vise des idées et des systèmes, jamais un groupe de personnes, aucune personne réelle nommée,
  aucune marque dénigrée. Tout chiffre ou fait doit être vrai : vérifie-le avec WebSearch, sinon enlève-le.
- images : pour chaque bloc, 3 courtes descriptions EN ANGLAIS de ce que Rick fait à l'image, séparées par « | »,
  toujours sur Rick lui-même (« Rick Sanchez with a raised finger | Rick Sanchez laughing | Rick Sanchez in his
  garage »), car toutes les images sont des plans de Rick de face.
- caption : une phrase en français, l'accroche ou sa meilleure punchline. hashtags : 4 hashtags en minuscules, sans
  #rickosophie (ajouté tout seul).
Avant d'enregistrer, relis chaque script avec la liste de vérification de la fiche (section 9). Si un script sonne
comme un coach énervé plutôt que comme Rick, réécris-le.

ÉTAPE 5 - Contrôle et enregistrement.
Lance `python3 src/add_content.py content/batchNN.json`. S'il refuse des sujets, corrige-les et relance jusqu'à ce
qu'il les accepte tous. Puis commit et push sur main (« Scripts batch NN »), en réessayant avec git pull --rebase si
le push est refusé (le robot quotidien enregistre aussi state.json). Termine par un résumé en français : les 20
titres, et les faits vérifiés avec leur source.
