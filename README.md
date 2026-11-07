# WoW Traducteur (+ addon ChatFR)

Traduction en direct du tchat de **World of Warcraft: Forever** vers le français (ou une autre langue), avec réponse dans la langue de ton interlocuteur.

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
2. **Addon** : copie le dossier `ChatFR` dans `World of Warcraft\_forever_\Interface\AddOns`.
   Le chemin final doit être `...\AddOns\ChatFR\ChatFR.toc` (pas de dossier `ChatFR` en double).
   Au lancement de WoW, vérifie dans **AddOns** que ChatFR est coché.
3. **Affichage** : dans WoW, *Options → Graphismes → Mode d'affichage* → **Fenêtré** ou **Plein écran (fenêtré)**.
4. **Traducteur** : copie le dossier `Traducteur` dans un endroit stable (par ex. `Documents\WoW Traducteur`, pas dans `Program Files`).
   Clic droit sur `Lancer le traducteur.bat` → *Envoyer vers → Bureau (créer un raccourci)*.

## Utilisation

1. Lance WoW et entre en jeu : une bande de cases colorées apparaît près du coin haut-gauche. C'est normal, ne la recouvre pas.
2. Double-clique sur **Lancer le traducteur.bat**.
3. La barre de statut doit afficher **« Pont image : OK (N messages reçus) »**. Les messages arrivent traduits en 1 à 2 secondes, avec un badge de langue (`[EN]`, `[DE]`, `[RU]`…).
4. Pour répondre : tape en français dans **« Écrire (FR) → »**, appuie sur Entrée, puis **Ctrl+V** dans le tchat de WoW. La langue de réponse se règle seule sur le dernier message étranger reçu.

Un petit lexique de joueur traduit directement les messages courts (« who » → qui, « ty » → merci, « gg » → bien joué, « lfg » → cherche groupe…) et développe les abréviations anglaises avant Google (« where r u » → « where are you »). Tu peux ajouter tes mots dans `LEX_FULL` et `LEX_EXPAND`, au début de `translator.py`.

Le traducteur se ferme tout seul quelques secondes après la fermeture de WoW. La fenêtre se déplace par sa barre du haut et se redimensionne par le coin en bas à droite.

### `Lancer le traducteur.bat`

Il démarre `translator.py` sans fenêtre de console, avec `pyw` (le lanceur installé avec Python) ou, à défaut, `pythonw`. Si aucun des deux n'est trouvé, il affiche un message et attend une touche. Il ne modifie rien, ne télécharge rien et n'a pas besoin des droits administrateur. Il doit rester à côté de `translator.py`.

Pour voir les erreurs en cas de problème, lance plutôt `python translator.py` depuis un terminal ouvert dans le dossier `Traducteur`.

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

Fenêtre perdue hors de l'écran : ferme-la, supprime `translator_config.json`, relance.
Alt+Z (masquer l'interface) cache aussi la bande : le traducteur ne reçoit plus rien tant qu'elle est masquée.

## Limites

- Traductions de Google Traduction : correctes sur les phrases simples, approximatives sur l'argot et les abréviations.
- Un message reste 0,4 s dans la bande : lors d'une très grosse rafale, un message peut être perdu. Au-delà d'environ 280 octets, il est coupé.
- Le texte des messages à traduire et ce que tu écris dans « Écrire (FR) » est envoyé à Google Traduction. Rien d'autre ne quitte ton ordinateur.
- L'addon n'utilise que des fonctions normales de WoW, et le traducteur ne fait que lire une partie de ton propre écran ; il ne touche ni au clavier ni à la souris et n'envoie rien dans le tchat. Ce n'est toutefois pas une méthode prévue par Blizzard : utilisation sous ta responsabilité.

## Désinstallation

Supprime `_forever_\Interface\AddOns\ChatFR` et le dossier `Traducteur`.
