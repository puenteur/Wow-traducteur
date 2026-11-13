# WoW Traducteur (+ addon ChatFR)

Traduction en direct du tchat de **World of Warcraft: Forever** vers le français (ou une autre langue), avec réponse dans la langue de ton interlocuteur.

## En bref

1. Installe Python (en cochant « Add python.exe to PATH »).
2. Copie l'addon `ChatFR` dans le dossier `AddOns` de WoW Forever.
3. Mets le jeu en mode **Fenêtré** ou **Plein écran (fenêtré)**.
4. Lance WoW, puis double-clique sur `Lancer le traducteur.bat`.
5. Attends « Pont image : OK » dans la barre de statut : les messages arrivent traduits.

Le détail de chaque étape est plus bas.

> **English:** WoW Traducteur and ChatFR are also available in English. At first launch, the translator asks *Français* or *English*: in English, the whole app is in English and the chat is translated **into English** (from French, German, Russian…). ChatFR follows your game language. Install steps are the same as above: Python, the `ChatFR` addon in `AddOns`, windowed mode, then `Lancer le traducteur.bat`. Video tutorial (in French): https://youtu.be/TS2QQybs0JI

## Ce que ça fait

**Traduction du tchat**
- Traduit en direct les messages de toutes les langues (anglais, espagnol, allemand, russe…) vers le français, ou vers la langue de ton choix.
- Tous les canaux : dire, crier, groupe, raid, guilde, chuchotements (en jeu et Battle.net), Général, Commerce, Recherche de groupe…
- Lexique de joueur : abréviations (gg, ty, lfm, pst, wts, any1…), jargon gardé tel quel (tank, heal, DPS, gank), donjons et zones en français (SFK → Donjon d'Ombrecroc), prix en pièces jamais traduits.
- Messages longs reçus en entier, liens d'objets et de quêtes colorés comme dans le jeu (liens Questie simplifiés), marqueurs de raid affichés en symboles.
- **Fiche d'objet au survol** : passe la souris sur un objet ou une quête en lien pour voir son infobulle (stats, niveau, prix), lue directement dans le jeu, comme dans WoW.
- Les messages déjà en français ne passent pas par Google.

**Répondre**
- Écris en français dans « Écrire (FR) », clique sur « Traduire + copier » : la traduction est copiée, tu la colles dans WoW (Entrée, Ctrl+V, Entrée).
- La langue de réponse se règle seule sur ton interlocuteur.
- Clique sur un **pseudo** : ta réponse est copiée avec `/w Pseudo` devant, pour lui chuchoter directement.
- Le traducteur n'envoie jamais rien au jeu lui-même : c'est toujours toi qui colles.

**Remplacer le tchat du jeu (options)**
- Avec les options de l'addon, tu vois aussi les PNJ, les messages système, la réputation (en bleu), l'expérience, le butin, les ventes au marchand (en vert) et tes dépenses (en rouge), ainsi que tes propres chuchotements envoyés.

**Fenêtre**
- 13 thèmes (Sombre, Alliance, Horde, Parchemin, Givre, Arcane…), appliqués tout de suite.
- Cadenas pour verrouiller la position et la taille.
- Se cache quand WoW n'est pas la fenêtre active (touche Windows, Alt+Tab, WoW réduit) et revient avec lui.
- Se ferme toute seule quand WoW se ferme, prévient quand une nouvelle version est disponible.
- Alertes sur ton pseudo ou des mots choisis, filtre de canaux, opacité, taille du texte.

**Addon ChatFR en jeu**
- Fenêtre de traduction hors ligne dans le jeu (dictionnaire de plus de 6 000 mots), facultative.
- Bande de cases colorées en haut à gauche, lue par le traducteur.
- Annonce en jeu des nouvelles versions du traducteur.

## Téléchargement

Va sur la page [Releases](https://github.com/puenteur/Wow-traducteur/releases/latest) et télécharge **les deux fichiers** :

- `ChatFR-<version>.zip` (ex. `ChatFR-1.7.zip`) : l'addon, à décompresser
- `WoW-Traducteur-<version>.zip` (ex. `WoW-Traducteur-1.7.zip`) : le traducteur, à décompresser (il contient le dossier `Traducteur`)

Évite le bouton vert « Code → Download ZIP » : il mélange tout dans un seul dossier et ne contient pas de dossier `Traducteur`. Si tu l'utilises quand même, garde `translator.py` et `Lancer le traducteur.bat` **ensemble dans le même dossier**.

## Les deux morceaux

Deux morceaux, **tous les deux obligatoires** :

| Morceau | Où | Rôle |
| --- | --- | --- |
| Addon **ChatFR** | dans le jeu | récupère chaque message du tchat et l'affiche dans une petite bande de cases colorées en haut à gauche de l'écran |
| **WoW Traducteur** (`translator.py`) | sur Windows | lit cette bande par capture d'écran, traduit avec Google Traduction et affiche le résultat dans sa fenêtre |

Pourquoi une bande de couleurs ? Un addon WoW n'a pas accès à Internet, et le client n'écrit le fichier de log du tchat qu'à la fermeture du jeu. La bande est le seul moyen de faire sortir le texte du jeu en direct. **Sans l'addon, le traducteur ne reçoit rien.**

## Prérequis

- Windows 10 ou 11
- WoW Forever en mode d'affichage **Fenêtré** ou **Plein écran (fenêtré)** — le plein écran exclusif donne une capture noire
- Python 3.9 ou plus récent depuis [python.org](https://www.python.org/downloads/windows/), avec « Add python.exe to PATH » coché (tcl/tk est inclus par défaut)
- Une connexion Internet

## Installation

1. **Python** : installe-le depuis python.org en cochant **« Add python.exe to PATH »**.
   Pour vérifier : ouvre une invite de commandes (touche Windows, tape `cmd`, Entrée) et tape `python --version`. Un numéro de version doit s'afficher. Si Windows ouvre le Microsoft Store à la place, Python n'est pas installé : installe-le depuis python.org, pas depuis le Store.
2. **Addon** : copie le dossier `ChatFR` dans `World of Warcraft\_forever_\Interface\AddOns`.
   Le chemin exact de WoW dépend de ton installation : c'est le dossier d'installation du jeu, puis `_forever_\Interface\AddOns`. Le chemin final doit être `...\AddOns\ChatFR\ChatFR.toc` (pas de dossier `ChatFR` en double).
   Au lancement de WoW, vérifie dans **AddOns** que ChatFR est coché.
3. **Affichage** : dans WoW, *Options → Graphismes → Mode d'affichage* → **Fenêtré** ou **Plein écran (fenêtré)**.
4. **Traducteur** : copie le dossier `Traducteur` dans un endroit stable (par ex. `Documents\WoW Traducteur`, pas dans `Program Files`).
   Clic droit sur `Lancer le traducteur.bat` → *Envoyer vers → Bureau (créer un raccourci)*.

## Utilisation

1. Lance WoW et entre en jeu : une bande de cases colorées apparaît près du coin haut-gauche. C'est normal, ne la recouvre pas.
2. Double-clique sur **Lancer le traducteur.bat**.
3. La barre de statut doit afficher **« Pont image : OK (N messages reçus) »**. Les messages arrivent traduits en 1 à 2 secondes, avec un badge de langue (`[EN]`, `[DE]`, `[RU]`…).
4. Pour répondre : tape en français dans **« Écrire (FR) → »**, appuie sur Entrée, puis **Ctrl+V** dans le tchat de WoW. La langue de réponse se règle seule sur le dernier message étranger reçu.

Un petit lexique de joueur traduit directement les messages courts (« who » → qui, « ty » → merci, « gg » → bien joué, « lfg » → cherche groupe…) et développe les abréviations anglaises avant Google (« where r u » → « where are you »). Les abréviations de donjons, raids, zones et villes sont remplacées par leur nom français (« SFK » → Donjon d'Ombrecroc, « STV » → Vallée de Strangleronce, « UC » → Fossoyeuse…). Le jargon « tank », « heal », « healer » et « DPS » reste tel quel. Tu peux ajouter tes mots dans `LEX_FULL` et `LEX_EXPAND`, et les noms de monstres ou de lieux que Google traduit à tort (« Hogger » → « porc ») dans `LEX_NAMES`, et tes abréviations de lieux dans `LEX_PLACES`, dans `translator.py`. Les prix en pièces (« 100 po », « 2 pa 50 pc ») ne sont jamais traduits.

Les liens du tchat sont colorés comme dans le jeu : quêtes en jaune, objets selon leur qualité (gris, blanc, vert, bleu, violet, orange), sorts en bleu clair, enchantements en jaune-orangé. Dans la traduction, le nom du lien est traduit par Google : cherche le nom anglais d'origine (ligne du dessus) si tu veux retrouver l'objet ou la quête.

Les marqueurs de raid du tchat (`{rt1}`…`{rt8}`) sont remplacés par des symboles : ★ étoile, ● rond, ◆ losange, ▲ triangle, ☾ lune, ■ carré, ✖ croix, ☠ crâne.

Le traducteur se ferme tout seul quelques secondes après la fermeture de WoW. La fenêtre se déplace par sa barre du haut et se redimensionne par le coin en bas à droite.

### Windows affiche « Windows a protégé votre ordinateur » ?

C'est normal pour un fichier `.bat` téléchargé. Clique sur **Informations complémentaires**, puis **Exécuter quand même**. Le fichier ne fait que lancer `translator.py`, le code est lisible dans ce dépôt. Certains antivirus peuvent aussi se méfier d'un programme qui capture l'écran : le traducteur ne lit que la petite bande de cases colorées, tu peux l'ajouter aux exceptions si besoin.

### `Lancer le traducteur.bat`

Il démarre `translator.py` sans fenêtre de console, avec `pyw` (le lanceur installé avec Python) ou, à défaut, `pythonw`. Si aucun des deux n'est trouvé, il affiche un message et attend une touche. Il ne modifie rien, ne télécharge rien et n'a pas besoin des droits administrateur. Il doit rester à côté de `translator.py`.

Pour voir les erreurs en cas de problème, lance plutôt `python translator.py` depuis un terminal ouvert dans le dossier `Traducteur`.

### Réglages

Le bouton **Réglages** de la fenêtre permet de :

- **Filtrer les canaux** : dans « Canaux masqués », écris des mots du nom des canaux à cacher, séparés par des virgules (ex. `trade,commerce,recherche`). Aucun canal n'est masqué par défaut.
- **Être alerté** : renseigne « Ton pseudo » et des « Mots surveillés » (séparés par des virgules) ; la ligne est surlignée et un son est joué quand l'un d'eux apparaît.
- **Ne voir que les messages étrangers** : décoche « Afficher aussi les messages déjà en français ».
- Régler l'opacité et la taille du texte, garder la fenêtre au premier plan, couper le son, désactiver la fermeture automatique avec WoW.
- Choisir un thème pour la fenêtre : Sombre, Alliance, Horde, Parchemin, Ombre, Forge, Druide, Arcane, Sables, Marais, Clair de lune, Aube dorée (clair) ou Givre (appliqué tout de suite).
- **Se cacher quand WoW n'est pas la fenêtre active** (activé par défaut) : la fenêtre disparaît quand tu passes sur une autre application et revient quand tu retournes dans WoW.

Dans la barre du haut, le **cadenas** verrouille la fenêtre : un clic et elle ne peut plus être déplacée ni redimensionnée, un autre clic la libère.

Pour **chuchoter une réponse**, clique sur le pseudo d'un joueur dans la fenêtre : « Écrire (FR) » devient « À Pseudo (FR) », et « Traduire + copier » copie `/w Pseudo ta réponse`. La croix à côté du pseudo revient à une réponse normale. Pour un ami Battle.net, la touche **R** de WoW reste plus fiable.

### Options de l'addon pour le traducteur

Dans les réglages de ChatFR en jeu (clic sur l'icône ChatFR de la minicarte), trois cases décochées par défaut ajoutent d'autres messages dans WoW Traducteur, affichés tels quels sans traduction (ils sont déjà en français) :

- **Traducteur : PNJ** : ce que disent, crient et font les PNJ et les boss.
- **Traducteur : messages système** : absent, invitations, réputation (en bleu), expérience, émotes…
- **Traducteur : butin et argent** : butin ramassé, pièces gagnées, ventes au marchand (en vert) et dépenses (en rouge).

Tes chuchotements envoyés (« À Pseudo : … ») s'affichent toujours, sans option.

Avec toutes ces cases cochées, tu peux placer WoW Traducteur par-dessus le tchat du jeu. En combat ou en ville, beaucoup de messages arrivent en même temps et peuvent avoir un léger retard.

### Commandes utiles de l'addon

| Commande | Effet |
| --- | --- |
| `/cfr pont` | affiche / masque la bande (à laisser affichée pour le traducteur) |
| `/cfr hide` · `/cfr show` | cache / affiche la fenêtre ChatFR en jeu (facultative) |
| `/cfr` | liste toutes les commandes |

## Dépannage

| Barre de statut | Solution |
| --- | --- |
| Pont image : fenêtre WoW introuvable | lance WoW et laisse sa fenêtre ouverte |
| Pont image : signal absent, capture 0 % non noire | passe le jeu en **Fenêtré** ou **Plein écran (fenêtré)** |
| Pont image : signal absent, capture non noire | vérifie que l'addon est activé, tape `/cfr pont` si la bande a disparu, retire ce qui la recouvre ; voir `debug_pont.bmp` à côté de `translator.py` |
| Erreur traduction : … | vérifie Internet ; après une rafale de messages, attends une minute |

Les liens apparaissent sans couleur ou avec de petits carrés bizarres : l'addon et le traducteur ne sont pas de la même version. Mets à jour les deux ensemble (addon `ChatFR` et dossier `Traducteur`).

Fenêtre perdue hors de l'écran : ferme-la, supprime `translator_config.json`, relance.
Alt+Z (masquer l'interface) cache aussi la bande : le traducteur ne reçoit plus rien tant qu'elle est masquée.

## Limites

- Traductions de Google Traduction : correctes sur les phrases simples, approximatives sur l'argot et les abréviations.
- Un message reste 0,4 s dans la bande : lors d'une très grosse rafale, un message peut être perdu. Au-delà d'environ 280 octets, il est coupé.
- Le texte des messages à traduire et ce que tu écris dans « Écrire (FR) » est envoyé à Google Traduction. Rien d'autre ne quitte ton ordinateur.
- L'addon n'utilise que des fonctions normales de WoW, et le traducteur ne fait que lire une partie de ton propre écran ; il ne touche ni au clavier ni à la souris et n'envoie rien dans le tchat. Ce n'est toutefois pas une méthode prévue par Blizzard : utilisation sous ta responsabilité.

## Désinstallation

Supprime `_forever_\Interface\AddOns\ChatFR` et le dossier `Traducteur`.

## Soutenir le projet

WoW Traducteur et ChatFR sont et resteront gratuits, sans fonction réservée aux donateurs. Si ces outils te rendent service et que tu veux me soutenir : [ko-fi.com/puenteur](https://ko-fi.com/puenteur)
