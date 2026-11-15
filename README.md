# RickOsophie

Chaîne automatique de vidéos courtes en français : Rick (voix française recréée) commente la société, sur des plans de la série.

Chaque jour, GitHub fabrique les vidéos (`.github/workflows/daily.yml`) et les envoie à Zernio, qui les publie sur TikTok et Instagram.

- `topics.json` : les scripts à venir (texte en six blocs, descriptions des images, légende, hashtags)
- `src/` : le travail quotidien (choix du sujet, publication, alertes Telegram)
- `tools/` : la fabrication d'une vidéo (voix, sous-titres, choix des plans, montage)
- les plans de la série et le modèle de voix sont dans un dépôt privé, téléchargés avec le secret `ASSETS_TOKEN`
- musiques : six morceaux Pixabay (licence Pixabay), téléchargés au moment du montage, jamais stockés ici
- police : Open Sans (SIL Open Font License, `assets/fonts/OFL.txt`)
