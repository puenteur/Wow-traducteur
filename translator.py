# -*- coding: utf-8 -*-
"""
Traducteur de tchat WoW  (v2)

- Lit WoWChatLog.txt (cree par /chatlog) et traduit chaque message vers le francais
  (langue d'origine detectee automatiquement : [DE], [EN], [PL]...).
- Couleurs par canal, canaux masquables (aucun masque par defaut).
- Alertes (son + surlignage) quand ton pseudo ou un mot surveille apparait.
- Zone du bas : tu ecris en francais, ca traduit dans la langue voulue et ca COPIE
  le resultat : il ne reste qu'a faire Ctrl+V dans WoW.
Aucune installation supplementaire : Python seul suffit.
"""
import base64
import binascii
import difflib
import ctypes
import json
import io
import shutil
import zipfile
import math
import os
import queue
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
import struct
import webbrowser
from ctypes import wintypes
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont

try:
    import winsound
except ImportError:  # pas sous Windows
    winsound = None

VERSION = "1.9.8"
# Verification de mise a jour : le fichier version.txt du depot contient le numero de la derniere version.
VERSION_URL = "https://raw.githubusercontent.com/puenteur/Wow-traducteur/main/version.txt"
KOFI_URL = "https://ko-fi.com/puenteur"
# Fiche d'un objet / d'une quete cliques dans la fenetre (recherche par nom, en francais).
WOWHEAD_SEARCH = "https://www.wowhead.com/classic/fr/search?q="
RELEASE_URL = "https://github.com/puenteur/Wow-traducteur/releases/latest"

HERE = os.path.dirname(os.path.abspath(__file__))

# Liens de metier ("[Alchimie]" = liste de recettes d'un joueur) : le jeu n'en donne pas de fiche.
PROFESSIONS = set("""alchimie forge couture enchantement ingénierie ingenierie cuisine secourisme pêche peche
minage herboristerie dépeçage depecage joaillerie calligraphie alchemy blacksmithing tailoring
enchanting engineering cooking fishing mining herbalism skinning jewelcrafting inscription""".split()) | {
    "travail du cuir", "premiers soins", "leatherworking", "first aid"}

# Nouveautes affichees une fois dans la fenetre apres une mise a jour (pas au premier lancement).
NEWS = {
    "fr": ["WoW Traducteur %s" % VERSION,
           "- Nouveau en %s : bouton \u2713 ABC pour corriger ton orthographe avant d'envoyer (en b\u00eata) ; barre d'\u00e9criture sur une ligne, fen\u00eatre et boutons aux coins arrondis, R\u00e9glages relook\u00e9s ; 7 th\u00e8mes retravaill\u00e9s et nouveaux embl\u00e8mes Alliance et Horde, le th\u00e8me change d\u00e8s qu'on le choisit ; option pour cacher la bande de cases color\u00e9es (R\u00e9glages, essai) ; quand Google bloque, Bing prend le relais et Google se repose plus longtemps ; moins de demandes \u00e0 Google ; \u00ab slt \u00bb, \u00ab lu \u00bb, \u00ab tlm \u00bb... bien traduits dans tes r\u00e9ponses ; la touche Entr\u00e9e ne traduit plus par accident ; meilleures traductions (La Prison, LFW, Arme flamboyante, Crois\u00e9, +2 Endurance, in IF = Forgefer). Mets aussi ChatFR \u00e0 jour." % VERSION,
           "- 1.9.7 : si Google tombe en panne, les traducteurs de secours prennent maintenant toujours le relais ; prix des fiches d'objets avec les pi\u00e8ces, comme dans le jeu ; pings \u00ab Menace \u00bb et \u00ab Par ici \u00bb avec leur losange ; un fichier services.txt (dossier des r\u00e9glages) note quel service a traduit les messages et les pannes, sans jamais le texte des messages.",
           "- 1.9.6 : correction importante, le traducteur ne s'arr\u00eate plus d'afficher les messages apr\u00e8s une annonce de qu\u00eate de Questie ; s'il plante sur un message, il continue avec les suivants et note l'erreur dans erreurs.txt ; noms des joueurs \u00e0 la couleur de leur classe, comme dans le jeu (ton pseudo en gras) ; \u00e9motes en orange, exp\u00e9rience en bleu, changements de r\u00f4le en groupe ; la fen\u00eatre se cache quand la carte est ouverte en grand ; avertissement si ChatFR et le traducteur n'ont pas la m\u00eame version ; liens de qu\u00eate Questie nettoy\u00e9s ; \u00ab salty \u00bb traduit par \u00ab vex\u00e9 \u00bb.",
           "- 1.9.5 : le traducteur se met \u00e0 jour tout seul au lancement (avec un compte \u00e0 rebours) ; s'il manque Python, \u00ab Lancer le traducteur.bat \u00bb propose de l'installer ; symboles des pings Menace et Par ici ; marques de raid reconnues dans toutes les langues du jeu ; annonces de Questie non traduites ; la fen\u00eatre ne redescend plus quand tu lis plus haut ; case \u00ab \u00c9crire \u00bb corrig\u00e9e dans une petite fen\u00eatre ; meilleures traductions (La Prison, \u00c9olide, Comt\u00e9-du-Nord, chevalet de tannage, BS / LW + niveau, q = qu\u00eate, yo, dr, dobro do\u0161li). Mets aussi ChatFR \u00e0 jour.",
           "- 1.9.4 : mise \u00e0 jour en un clic (bouton \u00ab Mettre \u00e0 jour \u00bb) ; tes r\u00e9glages sont maintenant rang\u00e9s \u00e0 part (%APPDATA%\\WoW-Traducteur) et ne se perdent plus ; la fen\u00eatre se place sur le tchat de WoW (premier lancement, ou bouton dans les R\u00e9glages) et se cache quand un menu du jeu s'ouvre ; \u00ab \u2014 \u00bb replie la fen\u00eatre sur sa barre ; messages de l'h\u00f4tel des ventes ; meilleures traductions (WTB/WTS, prix, COD, unstuck).",
           "- La grande nouveaut\u00e9 : tout le traducteur existe en anglais. Au premier lancement, on choisit Fran\u00e7ais ou English ; en anglais, le tchat est traduit vers l'anglais. Pratique pour tes amis anglophones ! (changeable dans les R\u00e9glages)",
           "- 1.9.3 : le nom du canal devant les messages (Groupe, Guilde, Raid, Officier) ; tes messages reconnus tout seuls ; r\u00e9ponse \u00e0 un joueur fran\u00e7ais copi\u00e9e telle quelle ; phrase \u00e9crite dans une autre langue que le fran\u00e7ais bien traduite ; marques de raid ; liens de qu\u00eate Questie en texte simple (mets aussi ChatFR \u00e0 jour) ; fonctionne aussi avec une r\u00e9solution personnalis\u00e9e ou une \u00e9chelle de rendu r\u00e9duite ; le lanceur trouve mieux Python ; abr\u00e9viations mieux traduites (ty, lfr, slt, tlm...) ; ic\u00f4nes des pings (\u26a0 \u2691 \u2b07 \u2694).",
           "- 1.9.1 : cliquer sur la fen\u00eatre ne prend plus le clavier \u00e0 WoW (tu continues \u00e0 bouger et \u00e0 parler aux PNJ). Seule la zone \u00ab \u00c9crire \u00bb le prend, quand tu cliques dedans. Tes messages de groupe en bleu, comme dans le jeu. Liens de qu\u00eate Questie des autres joueurs : bonne couleur et nom dans ta langue.",
           "- Pi\u00e8ces d'or, d'argent et de cuivre en ic\u00f4nes bien visibles, m\u00eame quand le jeu \u00e9crit \u00ab 25 Cuivre \u00bb.",
           "- Langue de r\u00e9ponse : une liste qui s'ouvre vers le haut (EN, DE, ES, puis Autre langue\u2026).",
           "- Fen\u00eatre des nouveaut\u00e9s apr\u00e8s chaque mise \u00e0 jour (celle-ci !).",
           "- Meilleures traductions : lfg/lfm, wts/wtb, Deadmines, jargon russe (\u041b\u0424\u0413), mots coll\u00e9s aux liens, petits messages en espagnol ou en letton, moins d'appels inutiles \u00e0 Google."],
    "en": ["WoW Traducteur %s" % VERSION,
           "- New in %s: \u2713 ABC button to fix your French spelling before sending (beta); write bar on one line, rounded window and buttons, restyled Settings; 7 reworked themes and new Alliance and Horde emblems, the theme changes as soon as you pick it; option to hide the strip of colored squares (Settings, test); when Google blocks, Bing takes over and Google rests longer; fewer requests to Google; Enter no longer translates by accident; better translations (The Stockade, LFW, Fiery Weapon, Crusader, +2 Stamina, in IF = Ironforge). Update ChatFR too." % VERSION,
           "- 1.9.7: if Google goes down, the backup translators now always take over; item tooltip prices shown with coins, like in the game; \"Threat\" and \"Look here\" pings with their diamond icon; a services.txt file (settings folder) records which service translated the messages and any outages, never the message text.",
           "- 1.9.6: important fix, the translator no longer stops showing messages after a Questie quest announcement; if it fails on a message, it carries on with the next ones and writes the error to erreurs.txt; player names in their class color, like in the game (your name in bold); emotes in orange, experience in blue, group role changes; the window hides when the world map is open full size; warning if ChatFR and the translator are not the same version; cleaner Questie quest links; \"salty\" handled in French translations.",
           "- 1.9.5: the translator now updates itself at launch (with a countdown); if Python is missing, \"Lancer le traducteur.bat\" offers to install it; Threat and Look ping symbols; raid marks recognized in every game language; Questie announcements no longer translated; the window no longer jumps down while you read older messages; \"Write\" box fixed in a small window; better translations (BS / LW + skill, q = quest, Skyborne, Northshire, Tanning Rack). Update ChatFR too.",
           "- 1.9.4: one-click update (\"Update\" button); your settings are now stored separately (%APPDATA%\\WoW-Traducteur) and are no longer lost; the window places itself over the WoW chat (first launch, or button in Settings) and hides when a game menu opens; \"\u2014\" rolls the window up to its bar; auction house messages; better translations (WTB/WTS, prices, COD, unstuck).",
           "- The big one: the whole translator is now available in English. Choose Fran\u00e7ais or English at first launch; in English, the chat is translated into English (can be changed in Settings).",
           "- 1.9.3: channel name in front of messages (Party, Guild, Raid, Officer); your own messages recognized automatically; replies in your own language copied as is; text written in another language than English translated correctly; raid marks; Questie quest links in plain text (update ChatFR too); also works with a custom resolution or a lower render scale; the launcher finds Python more reliably; better abbreviations (ty, lfr, slt, tlm...); ping icons (\u26a0 \u2691 \u2b07 \u2694).",
           "- 1.9.1: clicking the window no longer takes the keyboard away from WoW (keep moving and talking to NPCs). Only the \"Write\" box takes it, when you click in it. Your party messages in blue, like in the game. Questie quest links from other players: right color and name in your language.",
           "- Gold, silver and copper coins shown as clear icons, even when the game writes \"25 Copper\".",
           "- Reply language: a list that opens upwards (FR, DE, ES, then Other language\u2026).",
           "- A window like this one after each update.",
           "- Better translations: French gamer slang (pex, slt, tlm, \"du monde ?\"), Russian jargon, lfg/lfm, words stuck to links, and fewer useless calls to Google."],
}


def _data_dir():
    """Reglages hors du dossier du programme (%APPDATA%\\WoW-Traducteur) : on peut remplacer ou
    supprimer le dossier Traducteur a chaque mise a jour sans rien perdre."""
    base = os.environ.get("APPDATA")
    if os.name == "nt" and base:
        d = os.path.join(base, "WoW-Traducteur")
        try:
            os.makedirs(d, exist_ok=True)
            return d
        except OSError:
            pass
    return HERE


DATA_DIR = _data_dir()
ERROR_LOG = os.path.join(DATA_DIR, "erreurs.txt")


def log_error(where, item=None, tb=True):
    """Note une erreur dans erreurs.txt (dossier des reglages) : a envoyer pour qu'on corrige la cause."""
    try:
        import traceback
        if os.path.exists(ERROR_LOG) and os.path.getsize(ERROR_LOG) > 300000:
            os.replace(ERROR_LOG, ERROR_LOG + ".ancien")   # pas de fichier qui grossit sans fin
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write("=== %s  WoW Traducteur %s  (%s)\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), VERSION, where))
            if item is not None:
                f.write("Message : %r\n" % (item,))
            if tb:
                f.write(traceback.format_exc())
            f.write("\n")
    except Exception:  # noqa
        pass
for _name in ("translator_config.json", "infobulles.json"):   # 1.9.3 et avant : reglages dans le dossier
    _old, _new = os.path.join(HERE, _name), os.path.join(DATA_DIR, _name)
    if DATA_DIR != HERE and os.path.exists(_old) and not os.path.exists(_new):
        try:
            shutil.copy2(_old, _new)          # copie (l'ancien reste, au cas ou on revient en arriere)
        except OSError:
            pass
CONFIG_PATH = os.path.join(DATA_DIR, "translator_config.json")
# Mise a jour en un clic : le zip joint a la release (compte dans les telechargements de GitHub, comme un
# telechargement a la main). Secours : les memes fichiers dans le depot, au tag de la version.
UPDATE_ZIP = "https://github.com/puenteur/Wow-traducteur/releases/download/v%s/WoW-Traducteur-%s.zip"
UPDATE_RAW = "https://raw.githubusercontent.com/puenteur/Wow-traducteur/v%s/"
UPDATE_FILES = ("translator.py", "Lancer le traducteur.bat")


def _http_get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "WoW-Traducteur"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def download_update(latest):
    """-> {nom: contenu} pour UPDATE_FILES. D'abord le zip de la release, sinon le depot."""
    try:
        z = zipfile.ZipFile(io.BytesIO(_http_get(UPDATE_ZIP % (latest, latest))))
        got = {}
        for name in UPDATE_FILES:
            member = next((m for m in z.namelist() if m.replace("\\", "/").endswith("/Traducteur/" + name)), None)
            if member:
                got[name] = z.read(member)
        if "translator.py" in got:
            return got
    except Exception:  # noqa  (zip absent ou illisible : on essaie le depot)
        pass
    got = {}
    for name in UPDATE_FILES:
        try:
            got[name] = _http_get(UPDATE_RAW % latest + urllib.parse.quote(name), timeout=20)
        except Exception:  # noqa
            if name == "translator.py":
                raise
    return got
# Taille minimale de la fenetre (pixels) : assez petite pour tenir sur un petit tchat de WoW,
# assez grande pour garder la ligne "Ecrire" entiere (380 x 300 avant : trop grand)
MIN_W, MIN_H = 320, 180
TIPS_PATH = os.path.join(DATA_DIR, "infobulles.json")     # infobulles d'objets gardees entre deux lancements

DEFAULTS = {
    "source": "pont",               # "pont" (capture de la bande de l'addon) ou "log"
    "log_path": r"D:\World of Warcraft\_forever_\Logs\WoWChatLog.txt",
    "target": "fr",                 # langue d'affichage
    "out_lang": "en",               # langue pour ce que tu ecris
    "my_name": "",                  # ton pseudo (alertes)
    "keywords": "",                 # mots surveilles, separes par des virgules
    "hidden": "",
    "sound": True,
    "topmost": True,
    "alpha": 0.92,
    "font_size": 11,
    "show_french": True,            # afficher aussi les messages deja en francais
    "autoclose": True,              # se fermer quand WoW se ferme
    "follow_wow": True,             # se cacher quand WoW n'est pas la fenetre active (reduit, Alt+Tab...)
    # langue de reponse = langue du dernier message etranger. Desactivee par defaut depuis 1.9.3 (nouveau
    # nom de reglage : l'ancien "auto_reply_lang", active pour tout le monde, est ignore)
    "reply_lang_auto": False,
    "hide_on_menu": True,           # se cacher quand un menu du jeu s'ouvre (menu du tchat, clic droit...)
    "auto_update": True,            # au lancement, installer tout seul une nouvelle version (sinon : bouton)
    "theme": "Sombre",              # theme de la fenetre (voir THEMES)
    "locked": False,                # cadenas : fenetre verrouillee (ni deplacement ni redimensionnement)
    "help_seen": False,             # fenetre d'aide deja montree une fois (premier lancement)
    "ui_lang": "",                  # langue de l'interface : "fr" ou "en" (choisie au premier lancement)
    "cover_band": False,            # rectangle par-dessus la bande de cases (invisible pour la capture)
}

BG = "#101418"
FG = "#e6e6e6"
COLORS = {
    "say": "#ffffff", "yell": "#ff5555", "party": "#7fb2ff", "raid": "#ff9a3c",
    "guild": "#5fe05f", "officer": "#40c040", "whisper": "#ff8bd8",
    "channel": "#c8c8c8", "lfg": "#ffe066", "other": "#c8c8c8",
    "npc": "#fffb9f", "system": "#ffff00", "loot": "#00c000",     # options de ChatFR (sans traduction)
    "spent": "#ff5050",                                           # argent depense chez un marchand
    "whisper_out": "#ff8bd8",                                     # tes chuchotements envoyes
    "faction": "#8080ff",                                         # reputation (bleu, comme dans WoW)
    "ping": "#7fb2ff",                                            # pings du groupe (couleur du groupe)
    "emote": "#ff8040", "temote": "#ff8040",                      # emotes (/e, /genou...) : orange, comme dans WoW
}
# Nom du canal affiche devant le pseudo, comme dans WoW : (Groupe) Nom: ...
KIND_LABEL = {"party": ("Groupe", "Party"), "raid": ("Raid", "Raid"),
              "guild": ("Guilde", "Guild"), "officer": ("Officier", "Officer")}
NO_TRANSLATE = ("npc", "system", "temote", "loot", "spent", "whisper_out", "faction", "ping")   # ping : texte du jeu
# Pieces dans les messages du jeu ("11 pa 32 pc") : petite icone ronde a la place de po / pa / pc.
# Seulement pour les messages du jeu : dans le tchat des joueurs, "2pc" veut souvent dire "2 pieces".
COIN_KINDS = ("loot", "spent", "system")
COIN_RE = re.compile(r"(?<=\d)(\s?)(po|pa|pc)(?![A-Za-z\u00c0-\u024f])")
# Le jeu ecrit parfois le nom de la piece ("Votre part du butin est de 25 Cuivre.") : -> "25 pc"
COIN_WORDS_RE = re.compile(r"(?<=\d)\s?(?:pi\u00e8ces?\s+(?:d'|de\s+))?(or|argent|cuivre|gold|silver|copper)s?(?![A-Za-z\u00c0-\u024f])", re.I)
COIN_WORDS = {"or": "po", "gold": "po", "argent": "pa", "silver": "pa", "cuivre": "pc", "copper": "pc"}
COIN_COLORS = {"po": ("#f2c94c", "#9c7412"), "pa": ("#d6dae2", "#7f8590"), "pc": ("#d0874e", "#7d4520")}
# ---------------------------------------------------------------------------
# Langue de l'interface (francais / anglais). Les textes sont ecrits en francais dans le code ;
# _("...") renvoie la version anglaise quand l'interface est en anglais.
UI = "fr"

EN = {
    "Demarrage...": "Starting...",
    "Bienvenue dans WoW Traducteur %s !": "Welcome to WoW Traducteur %s!",
    "Le traducteur est gratuit. Pour me soutenir : ": "The translator is free. To support me: ",
    "Bouton \u2713 ABC (correcteur d'orthographe, b\u00eata)": "\u2713 ABC button (spell checker, beta)",
    "ABC (b\u00eata) : corrige et copie en fran\u00e7ais, SANS traduire. Correcteur en d\u00e9veloppement : relis avant d'envoyer.":
        "ABC (beta): corrects and copies in French, WITHOUT translating. Checker still in development: read it before sending.",
    "Cacher la bande de cases color\u00e9es (essai)": "Hide the strip of colored squares (test)",
    "Cache-bande d\u00e9sactiv\u00e9 : Windows ne permet pas de le cacher \u00e0 la capture (Windows trop ancien ?).":
        "Strip cover turned off: Windows can't hide it from the capture (Windows too old?).",
    "\u2713 Corriger": "\u2713 Correct",
    "ABC : corrige et copie en fran\u00e7ais, SANS traduire.":
        "ABC: corrects and copies in English, WITHOUT translating.",
    "\u2713 %d correction(s). Copi\u00e9 en fran\u00e7ais, sans traduction (Ctrl+V dans WoW)":
        "\u2713 %d correction(s). Copied in English, not translated (Ctrl+V in WoW)",
    "\u2713 Aucune faute. Copi\u00e9 en fran\u00e7ais, sans traduction (Ctrl+V dans WoW)":
        "\u2713 No mistakes. Copied in English, not translated (Ctrl+V in WoW)",
    "\u2713 %d correction(s) de base (correcteur en ligne indisponible). Copi\u00e9 en fran\u00e7ais, sans traduction":
        "\u2713 %d basic correction(s) (online checker unavailable). Copied in English, not translated",
    "\u26a0 ChatFR est en %s, le traducteur en %s : mets ChatFR \u00e0 jour (CurseForge), puis relance le jeu.":
        "\u26a0 ChatFR is %s, the translator is %s: update ChatFR (CurseForge), then restart the game.",
    "\u26a0 ChatFR est en %s, le traducteur en %s : mets le traducteur \u00e0 jour (bouton dans les R\u00e9glages).":
        "\u26a0 ChatFR is %s, the translator is %s: update the translator (button in Settings).",
    "⚙ Réglages": "⚙ Settings",
    "Effacer": "Clear",
    "Clique sur un message pour repondre dans sa langue.": "Click a message to reply in its language.",
    "Autre langue…": "Other language…",
    "À %s (%s) →": "To %s (%s) →",
    "Ecrire (%s) →": "Write (%s) →",
    "\u00c9cris ici en fran\u00e7ais\u2026": "Type here in English\u2026",
    "\u2715 : efface ta phrase (touche \u00c9chap aussi).": "\u2715: clears your sentence (Esc key too).",
    "Langue dans laquelle ta phrase sera traduite (clique pour la changer).": "Language your sentence will be translated into (click to change it).",
    "Traduit ta phrase dans la langue choisie et copie la traduction.": "Translates your sentence into the chosen language and copies it.",
    "Chuchotement à %s : ta reponse sera copiee avec /w %s": "Whisper to %s: your reply will be copied with /w %s",
    "Reponse normale (sans /w).": "Normal reply (no /w).",
    "(haut fait : le détail est sur Wowhead)": "(achievement: details are on Wowhead)",
    "(lien de métier : clique dessus dans WoW pour voir ses recettes)":
        "(profession link: click it in WoW to see the recipes)",
    "(le jeu ne donne pas la fiche de cette quête, souvent tant qu'elle n'est pas dans ton journal : vois-la sur Wowhead)":
        "(the game doesn't send this quest's details, usually until it is in your quest log: see it on Wowhead)",
    "(fiche pas encore reçue du jeu : elle arrivera au prochain lien de cet objet)":
        "(details not received from the game yet: they will come with the next link of this item)",
    "Langue de reponse : %s": "Reply language: %s",
    "WoW Traducteur %s - ce qu'il sait faire": "WoW Traducteur %s - what it can do",
    "Fermer": "Close",
    "Reglages": "Settings",
    "Source (pont ou log)": "Source (pont or log)",
    "Fichier de log (si source=log)": "Log file (if source=log)",
    "Traduire vers (fr, en...)": "Translate into (en, fr...)",
    "Ton pseudo (alerte)": "Your character name (alert)",
    "Mots surveilles (virgules)": "Watched words (commas)",
    "Son pour les alertes": "Sound for alerts",
    "Toujours au premier plan": "Always on top",
    "Afficher aussi les messages deja dans ta langue": "Also show messages already in your language",
    "Se fermer quand WoW se ferme": "Close when WoW closes",
    "Se cacher quand WoW n'est pas la fenetre active": "Hide when WoW is not the active window",
    "Langue de reponse automatique (dernier message etranger)": "Automatic reply language (last foreign message)",
    "Opacite": "Opacity",
    "Taille du texte": "Text size",
    "Theme": "Theme",
    "Langue de l'interface": "Interface language",
    "Enregistrer": "Save",
    "Placer sur le tchat de WoW": "Place over the WoW chat",
    "Se cacher quand un menu du jeu s'ouvre (menu du tchat, clic droit)": "Hide when a game menu opens (chat menu, right-click)",
    "Mises a jour automatiques (au lancement)": "Automatic updates (at launch)",
    "(le traducteur va se fermer puis se rouvrir tout seul)": "(the translator will close and reopen by itself)",
    "Nouvelle version %s : mise à jour automatique...": "New version %s: updating automatically...",
    "Pas encore recu de ChatFR (1.9.4 ou plus) : reessaie dans 30 s.": "Not received from ChatFR yet (1.9.4 or later): try again in 30 s.",
    "Log introuvable : %s (tape /chatlog dans WoW)": "Log not found: %s (type /chatlog in WoW)",
    "En ecoute...": "Listening...",
    "En ecoute... (%d lignes lues, %d messages)": "Listening... (%d lines read, %d messages)",
    "En ecoute... %d lignes, %d msg | log %d Ko, ecrit il y a %ds": "Listening... %d lines, %d msg | log %d KB, written %ds ago",
    "Erreur lecture : %s": "Read error: %s",
    "Pont image : fenetre WoW introuvable": "Image bridge: WoW window not found",
    "Pont image : signal absent | WoW en (%d,%d) | capture %d%% non noire, moy %s | voir debug_pont.bmp":
        "Image bridge: no signal | WoW at (%d,%d) | capture %d%% non-black, avg %s | see debug_pont.bmp",
    "Pont image : OK (%d messages recus)": "Image bridge: OK (%d messages received)",
    "Pont image : erreur %s": "Image bridge: error %s",
    "Pont image : bande illisible (cases de %.2f px au lieu de 6) | mets la Resolution du jeu = celle de l'ecran et l'Echelle de rendu a 100 %%":
        "Image bridge: strip unreadable (%.2f px cells instead of 6) | set the game Resolution = your screen's and Render Scale to 100 %%",
    "⚠ traduction impossible : %s": "⚠ translation failed: %s",
    "Mise à jour %s dispo": "Update %s available",
    "Mettre à jour (%s)": "Update (%s)",
    "Téléchargement...": "Downloading...",
    "Mise à jour impossible : ouvrir la page": "Update failed: open the page",
    "Mise à jour impossible : %s": "Update failed: %s",
    "fichier inattendu": "unexpected file",
    "Mise à jour %s terminée ✓": "Update %s done ✓",
    "Mise à jour %s terminée ✓ Redémarrage dans %d s": "Update %s done ✓ Restarting in %d s",
    "✓ Mise à jour terminée : %s → %s. Pense aussi à mettre ChatFR à jour (CurseForge).": "✓ Update done: %s → %s. Remember to update ChatFR too (CurseForge).",
    "Erreur : %s": "Error: %s",
    "Copie ! (Entree, Ctrl+V, Entree dans WoW)  %s": "Copied! (Enter, Ctrl+V, Enter in WoW)  %s",
    "Vous → ": "You → ",
    "Vous → %s ": "You → %s ",
    "→ (en français : %s)": "→ (in English: %s)",
    "Fenetre verrouillee": "Window locked",
    "Fenetre deverrouillee": "Window unlocked",
    "Traduire + copier": "Translate + copy",
    "Voir sur Wowhead \u2197": "See on Wowhead \u2197",
    "Langue de reponse : %s (auto, d'apres %s)": "Reply language: %s (auto, from %s)",
    "Traduction en cours...": "Translating...",
    "Tout ce qu'il sait faire (?)": "Everything it can do (?)",
    "Canaux masques (virgules)": "Hidden channels (commas)",
    # themes (le nom francais reste la cle enregistree dans la config)
    "Sombre": "Dark", "Parchemin": "Parchment", "Ombre": "Shadow", "Druide": "Druid", "Sables": "Sands",
    "Marais": "Swamp", "Clair de lune": "Moonlight", "Aube dorée": "Golden dawn", "Givre": "Frost",
}


ERR_EN = [("Google en pause (trop de requetes), reprise dans", "Google paused (too many requests), resuming in"),
          ("Google limite les requetes (429), pause de", "Google is limiting requests (429), pausing for"),
          ("Google ne repond pas", "Google is not responding"), ("quota du jour atteint", "daily quota reached"),
          ("MyMemory a refuse la requete", "MyMemory refused the request"),
          ("aucun serveur ne repond", "no server responds"), ("serveurs en pause", "servers paused"),
          ("reponse vide", "empty response")]


def err_text(e):
    """Message d'erreur des services de traduction, en anglais si l'interface est en anglais."""
    t = str(e)
    if UI == "en":
        for fr, en in ERR_EN:
            t = t.replace(fr, en)
    return t


def _(s):
    return EN.get(s, s) if UI == "en" else s


# Noms des langues de reponse, selon la langue de l'interface
LANG_NAMES = {
    "fr": {"en": "Anglais", "de": "Allemand", "es": "Espagnol", "ru": "Russe", "pl": "Polonais", "it": "Italien",
           "pt": "Portugais", "nl": "Néerlandais", "sv": "Suédois", "da": "Danois", "no": "Norvégien",
           "fi": "Finnois", "cs": "Tchèque", "ro": "Roumain", "hu": "Hongrois", "tr": "Turc", "el": "Grec",
           "uk": "Ukrainien", "fr": "Français"},
    "en": {"en": "English", "de": "German", "es": "Spanish", "ru": "Russian", "pl": "Polish", "it": "Italian",
           "pt": "Portuguese", "nl": "Dutch", "sv": "Swedish", "da": "Danish", "no": "Norwegian", "fi": "Finnish",
           "cs": "Czech", "ro": "Romanian", "hu": "Hungarian", "tr": "Turkish", "el": "Greek", "uk": "Ukrainian",
           "fr": "French"},
}
LANGS_ORDER = ["ru", "pl", "it", "pt", "nl", "sv", "da", "no", "fi", "cs", "ro", "hu", "tr", "el", "uk"]


def lang_lists():
    """(rapides, autres) en paires (nom, code) dans la langue de l'interface."""
    names = LANG_NAMES[UI]
    quick = ["en", "de", "es"] if UI == "fr" else ["fr", "de", "es"]
    others = [c for c in LANGS_ORDER] + (["fr"] if UI == "fr" else ["en"])
    return [(names[c], c) for c in quick], [(names[c], c) for c in others]
# Pile de pieces (or, argent, cuivre) : clair, moyen, fonce, contour.
COIN_PAL = {
    "po": ((255, 243, 168), (245, 197, 24), (184, 134, 11), (92, 61, 0)),
    "pa": ((255, 255, 255), (217, 222, 230), (143, 151, 163), (60, 65, 74)),
    "pc": ((255, 210, 174), (217, 120, 58), (154, 74, 28), (74, 31, 8)),
}


def _coin_mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def _coin_pile(unit, u, v):
    """Couleur d'un point (u, v dans -1..1) d'une pile de 3 pieces vue de profil, ou None."""
    hi, mid, lo, out = COIN_PAL[unit]
    ry, th = 0.38, 0.36
    res = None
    for k in range(3):                       # de bas en haut : la piece du dessus recouvre
        top = 1 - ry - (k + 1) * th + 0.02
        e_top = u * u + ((v - top) / ry) ** 2
        e_bot = u * u + ((v - top - th) / ry) ** 2
        if abs(u) <= 1 and (top <= v <= top + th or e_bot <= 1):
            edge = abs(u) > 0.9 or (e_bot > 0.75 and v > top + th)
            res = out if edge else _coin_mix(mid, lo, 0.5 + 0.4 * u)
        if e_top <= 1:
            shine = (u + 0.35) ** 2 / 0.12 + ((v - top + 0.08) / ry) ** 2 / 0.25 < 1
            res = out if e_top > 0.72 else (hi if shine else mid)
    return res


def coin_png(unit, size, ss=4):
    """PNG (octets) d'une pile de pieces size x size, bords lisses (ss x ss echantillons par pixel)."""
    raw = bytearray()
    for y in range(size):
        raw.append(0)
        for x in range(size):
            r = g = b = n = 0
            for sy in range(ss):
                for sx in range(ss):
                    c = _coin_pile(unit, ((x + (sx + 0.5) / ss) / size * 2 - 1) * 1.02,
                                   ((y + (sy + 0.5) / ss) / size * 2 - 1) * 1.02)
                    if c is not None:
                        r += c[0]; g += c[1]; b += c[2]; n += 1
            raw += bytes((round(r / n), round(g / n), round(b / n), round(255 * n / (ss * ss)))) if n else b"\0\0\0\0"

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def corner_png(r, inside, outside, corner, ring=None, ring_w=0, hard_out=False, ss=4):
    """PNG (octets) d'un coin arrondi r x r, bord lisse : `inside` dans l'arrondi, `outside` autour.
    corner = "nw", "ne", "sw" ou "se" (coin haut-gauche, haut-droit...). `ring` : liseré de `ring_w` px
    le long de l'arrondi (cadre de la fenetre). `hard_out` : bord exterieur net, sans melange avec
    `outside` (couleur rendue transparente : un melange donnerait un halo)."""
    def rgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    ci, co = rgb(inside), rgb(outside)
    cr = rgb(ring) if ring else ci
    cx = r if corner[1] == "w" else 0
    cy = r if corner[0] == "n" else 0
    rin = (r - ring_w) if ring else r
    raw = bytearray()
    for y in range(r):
        raw.append(0)
        for x in range(r):
            n_out = n_ring = n_in = 0
            for sy in range(ss):
                for sx in range(ss):
                    d2 = (x + (sx + 0.5) / ss - cx) ** 2 + (y + (sy + 0.5) / ss - cy) ** 2
                    if d2 > r * r:
                        n_out += 1
                    elif d2 > rin * rin:
                        n_ring += 1
                    else:
                        n_in += 1
            tot = ss * ss
            if hard_out:
                if n_out * 2 >= tot:
                    raw += bytes(co)
                    continue
                tot = n_ring + n_in
                n_out = 0
            raw += bytes(round((ci[k] * n_in + cr[k] * n_ring + co[k] * n_out) / tot) for k in range(3))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", r, r, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def wow_grammar(text):
    """Codes de grammaire du client WoW : "|2 Stormwind" = "de Stormwind" / "d'Orgrimmar"."""
    if "|2" not in text:
        return text
    text = re.sub(r"\|2\s*(?=[AEIOUYHaeiouyh\u00c0-\u00c6\u00c8-\u00cf\u00d2-\u00d6\u00d9-\u00dc\u00e0-\u00e6\u00e8-\u00ef\u00f2-\u00f6\u00f9-\u00fc])", "d'", text)
    return re.sub(r"\|2\s*", "de ", text)
TRANS_COLOR = "#6fd3ff"
WIN_HOLE = "#010203"   # couleur rendue transparente (coins arrondis de la fenetre)
NAME_COLOR = "#e8b964"      # pseudo des autres joueurs
ALERT_BG = "#5a4a00"

# Themes de la fenetre (Reglages -> Theme, applique tout de suite).
# bg/fg : fond et texte du tchat ; bar : barre du haut ; btn : boutons ; accent : bouton principal ;
# border : cadre de la fenetre ; panel/entry : zone "Ecrire" ; trans : traductions ; name : pseudos ;
# emblem : petit dessin dans la barre ("shield", "banner" ou None) ; label : texte a cote de l'emblème.
_SOMBRE = dict(bg="#101418", fg="#e6e6e6", bar="#0b0e11", btn="#1b232c", btn_act="#2a343f", btn_fg="#e6e6e6",
               accent="#1f6f9f", accent_act="#2a86bd", accent_fg="white", border="#2a343f", border_w=1,
               icon="#9aa7b4", status="#6f7c8a", panel="#171d24", entry="#0b0e11", muted="#8a97a6",
               trans="#6fd3ff", name="#e8b964", badge="#9aa7b4", scroll="#2a343f", scroll_act="#3b4856",
               emblem=None, label="", label_fg="#e6e6e6",
               me="#ffd479", err="#ff7070", ok="#7ee787", alert_bg="#5a4a00",
               colors=None, links=None)    # None = couleurs normales des canaux et des liens
THEMES = {
    "Sombre": _SOMBRE,
    "Alliance": dict(_SOMBRE, bg="#0e1a2f", fg="#e8eef8", bar="#081120", btn="#16284a", btn_act="#21386a",
                     btn_fg="#f1e3b3", accent="#c9a227", accent_act="#dcb53a", accent_fg="#081120",
                     border="#c9a227", border_w=2, icon="#c9a227", status="#8fa3c4", panel="#081120",
                     entry="#16284a", muted="#8fa3c4", trans="#7fc4ff", name="#f0c75e", badge="#8fa3c4",
                     scroll="#2c4470", scroll_act="#3d5a8f", emblem="shield", label="ALLIANCE",
                     label_fg="#e0b84a"),
    "Horde": dict(_SOMBRE, bg="#1c0c0a", fg="#f2e6dc", bar="#110605", btn="#3a1410", btn_act="#55201a",
                  btn_fg="#f0d2b0", accent="#9c2a1e", accent_act="#b83526", accent_fg="#f7e6d0",
                  border="#9c2a1e", border_w=2, icon="#d1843a", status="#a88672", panel="#110605",
                  entry="#2a0f0c", muted="#a88672", trans="#f0b070", name="#e8a24a", badge="#a88672",
                  scroll="#4a1a14", scroll_act="#6a261d", emblem="banner", label="HORDE", label_fg="#d1843a"),
    "Parchemin": dict(_SOMBRE, bg="#2b2116", fg="#f3e6c4", bar="#1f170e", btn="#3d2f1e", btn_act="#54412a",
                      btn_fg="#e6d3a8", accent="#7a5320", accent_act="#946628", accent_fg="#f3e6c4",
                      border="#a8823e", border_w=2, icon="#e6d3a8", status="#b39a6e", panel="#1f170e",
                      entry="#3d2f1e", muted="#b39a6e", trans="#f0c878", name="#ffb84d", badge="#b39a6e",
                      scroll="#54412a", scroll_act="#6b5436"),
    "Ombre": dict(_SOMBRE, bg="#0b0b0e", fg="#d8d8e0", bar="#060608", btn="#18181e", btn_act="#26262e",
                  btn_fg="#b7b7c4", accent="#2e2e3a", accent_act="#3c3c4a", accent_fg="#d8d8e0",
                  border="#26262e", icon="#7a7a8a", status="#5c5c6a", panel="#121216", entry="#060608",
                  muted="#7a7a8a", trans="#9a9ab0", name="#ffffff", badge="#6a6a7a",
                  scroll="#26262e", scroll_act="#34343e"),
    "Forge": dict(_SOMBRE, bg="#1a1310", fg="#f2e0d0", bar="#110c0a", btn="#2e211b", btn_act="#432f26",
                  btn_fg="#ffcf9a", accent="#8a3510", accent_act="#a54214", accent_fg="#ffe6cc",
                  border="#c45a1a", border_w=2, icon="#ffb366", status="#a88a72", panel="#110c0a",
                  entry="#2e211b", muted="#a88a72", trans="#ffa04a", name="#ffb366", badge="#a88a72",
                  scroll="#432f26", scroll_act="#5c4134"),
    "Druide": dict(_SOMBRE, bg="#0f1a10", fg="#e8f2dc", bar="#0a120b", btn="#1c2e1d", btn_act="#284229",
                   btn_fg="#c9e6a0", accent="#3f6b1c", accent_act="#4f8424", accent_fg="#eaf6d8",
                   border="#5c8a2e", border_w=2, icon="#c9e6a0", status="#86a06e", panel="#0a120b",
                   entry="#1c2e1d", muted="#86a06e", trans="#a7e07a", name="#f0c860", badge="#86a06e",
                   scroll="#284229", scroll_act="#375a38"),
    "Arcane": dict(_SOMBRE, bg="#170f26", fg="#ece2ff", bar="#0f0a1a", btn="#28193f", btn_act="#382458",
                   btn_fg="#d6b8ff", accent="#5a32a8", accent_act="#6c40c4", accent_fg="#f3ecff",
                   border="#7a4fd1", border_w=2, icon="#d6b8ff", status="#9a88bf", panel="#0f0a1a",
                   entry="#28193f", muted="#9a88bf", trans="#c49bff", name="#ffd37a", badge="#9a88bf",
                   scroll="#382458", scroll_act="#4a3172"),
    "Sables": dict(_SOMBRE, bg="#241a0e", fg="#f7ecd2", bar="#19120a", btn="#3a2b17", btn_act="#523d21",
                   btn_fg="#f2d28a", accent="#8a6420", accent_act="#a57828", accent_fg="#fff3d6",
                   border="#c4943a", border_w=2, icon="#f2d28a", status="#b39a6e", panel="#19120a",
                   entry="#3a2b17", muted="#b39a6e", trans="#f0c060", name="#ffa64d", badge="#b39a6e",
                   scroll="#523d21", scroll_act="#6b502c"),
    "Marais": dict(_SOMBRE, bg="#121a16", fg="#dfe8da", bar="#0c120f", btn="#1e2b24", btn_act="#2a3d33",
                   btn_fg="#a9c9a0", accent="#355a3c", accent_act="#426f4a", accent_fg="#e6f2e2",
                   border="#4f6b4a", border_w=2, icon="#a9c9a0", status="#7f9a86", panel="#0c120f",
                   entry="#1e2b24", muted="#7f9a86", trans="#8ed4a8", name="#f0c860", badge="#7f9a86",
                   scroll="#2a3d33", scroll_act="#385244"),
    "Clair de lune": dict(_SOMBRE, bg="#101626", fg="#e6ecfa", bar="#0a0f1a", btn="#1c2540", btn_act="#283458",
                          btn_fg="#c8d4f0", accent="#3e5290", accent_act="#4c64ab", accent_fg="#eef2ff",
                          border="#6a7fb8", border_w=2, icon="#c8d4f0", status="#8894b4", panel="#0a0f1a",
                          entry="#1c2540", muted="#8894b4", trans="#b0c4ff", name="#ffd37a", badge="#8894b4",
                          scroll="#283458", scroll_act="#364574"),
    # theme clair : les couleurs des canaux et des liens sont foncees pour rester lisibles
    "Aube dorée": dict(_SOMBRE, bg="#fbf6ea", fg="#2b2416", bar="#efe4c8", btn="#e4d6b0", btn_act="#d8c79a",
                       btn_fg="#3d3218", accent="#c9a227", accent_act="#b89220", accent_fg="#2b2416",
                       border="#c9a227", border_w=2, icon="#7a5a10", status="#7a6a48", panel="#efe4c8",
                       entry="#ffffff", muted="#7a6a48", trans="#8a5a00", name="#7a5a10", badge="#8a7a58",
                       scroll="#d8c79a", scroll_act="#c4b07a", me="#8a5a00", err="#c0261f", ok="#2a7a1e",
                       alert_bg="#f2dc8a",
                       colors={"say": "#2b2416", "yell": "#c0261f", "party": "#1f5fae", "raid": "#b5530e",
                               "guild": "#2a7a1e", "officer": "#1f6016", "whisper": "#a8327e",
                               "channel": "#4a3f2a", "lfg": "#8a6a00", "other": "#4a3f2a",
                               "npc": "#6a5a00", "system": "#7a6a00", "loot": "#1d7a00", "spent": "#c0261f",
                               "whisper_out": "#a8327e", "faction": "#3a3ab0", "ping": "#1f5fae",
                               "emote": "#b5530e", "temote": "#b5530e"},
                       links={"q": "#8a6a00", "q0": "#6e6e6e", "q1": "#1d7a00", "q2": "#8a6a00", "q3": "#b5530e", "q4": "#c0261f", "i0": "#6e6e6e", "i1": "#2b2416", "i2": "#1d7a00", "i3": "#0058b0",
                              "i4": "#7a2fc0", "i5": "#b85a00", "i6": "#8a7440", "i7": "#0080a8", "i8": "#0080a8",
                              "s": "#0070a8", "e": "#8a6a00", "a": "#8a7a00", "o": "#8a6a00"}),
    "Givre": dict(_SOMBRE, bg="#0f1d26", fg="#eaf8ff", bar="#09141b", btn="#173040", btn_act="#204257",
                  btn_fg="#cfeefc", accent="#2f7fa8", accent_act="#3a93c0", accent_fg="white",
                  border="#5fb6d9", border_w=2, icon="#9fd8f0", status="#7fa9bf", panel="#09141b",
                  entry="#173040", muted="#7fa9bf", trans="#9fe3ff", name="#ffd37a", badge="#7fa9bf",
                  scroll="#204257", scroll_act="#2c5873"),
}

# 1.9.8 : themes retravailles pour qu'ils ne se ressemblent plus (une couleur dominante chacun)
_THEMES_198 = {
 "Ombre": dict(bg="#050505", fg="#f2f2f2", bar="#000000", btn="#1a1a1a", btn_act="#2b2b2b", btn_fg="#f2f2f2",
      accent="#f2f2f2", accent_act="#ffffff", accent_fg="#000000", border="#3a3a3a", border_w=1, icon="#d0d0d0",
      status="#8a8a8a", panel="#0d0d0d", entry="#141414", muted="#9a9a9a", trans="#cfcfcf", name="#ffffff",
      badge="#8a8a8a", scroll="#2b2b2b", scroll_act="#3d3d3d"),
 "Horde": dict(bg="#170505", fg="#f5e3dc", bar="#0d0202", btn="#3a0d0b", btn_act="#561410", btn_fg="#f5d0b8",
      accent="#b01e16", accent_act="#cc271d", accent_fg="#fff0e6", border="#b01e16", border_w=2, icon="#e2a24a",
      status="#b08478", panel="#0d0202", entry="#2a0807", muted="#b08478", trans="#ff9a7a", name="#e8b04a",
      badge="#b08478", scroll="#561410", scroll_act="#72201a"),
 "Parchemin": dict(bg="#2a2420", fg="#ece2d0", bar="#1e1915", btn="#3b332c", btn_act="#4f453b", btn_fg="#e0d2b8",
      accent="#6b5a45", accent_act="#7f6c54", accent_fg="#f5ecdc", border="#8c7a62", border_w=2, icon="#d8c8a8",
      status="#a09078", panel="#1e1915", entry="#3b332c", muted="#a09078", trans="#e6cfa0", name="#f0c070",
      badge="#a09078", scroll="#4f453b", scroll_act="#635749"),
 "Sables": dict(bg="#3a2c14", fg="#fff4d8", bar="#2c2010", btn="#55401c", btn_act="#6e5426", btn_fg="#ffe39a",
      accent="#d9a530", accent_act="#ebb83e", accent_fg="#2c2010", border="#e8bd55", border_w=2, icon="#ffe39a",
      status="#cdb383", panel="#2c2010", entry="#55401c", muted="#cdb383", trans="#ffd768", name="#ff9f4a",
      badge="#cdb383", scroll="#6e5426", scroll_act="#86682f"),
 "Marais": dict(bg="#0c1c1c", fg="#d8ece6", bar="#071313", btn="#163030", btn_act="#204444", btn_fg="#9fd8c8",
      accent="#2d7a6a", accent_act="#36917e", accent_fg="#e6faf4", border="#3f8f7c", border_w=2, icon="#9fd8c8",
      status="#76a39a", panel="#071313", entry="#163030", muted="#76a39a", trans="#7fe0c8", name="#e8d070",
      badge="#76a39a", scroll="#204444", scroll_act="#2c5a5a"),
 "Arcane": dict(bg="#22092a", fg="#f8e6ff", bar="#16051c", btn="#3a1046", btn_act="#521862", btn_fg="#f0b8ff",
      accent="#b03ad0", accent_act="#c64ce6", accent_fg="#fff0ff", border="#d060f0", border_w=2, icon="#f0b8ff",
      status="#b08cc0", panel="#16051c", entry="#3a1046", muted="#b08cc0", trans="#ff9cf0", name="#ffd37a",
      badge="#b08cc0", scroll="#521862", scroll_act="#6a2280"),
 "Clair de lune": dict(bg="#1a1b26", fg="#eceef8", bar="#121320", btn="#2a2c3e", btn_act="#383b52", btn_fg="#d0d4ec",
      accent="#7a7fb8", accent_act="#8d92cc", accent_fg="#0f1020", border="#c0c4dc", border_w=2, icon="#d0d4ec",
      status="#9a9db8", panel="#121320", entry="#2a2c3e", muted="#9a9db8", trans="#c8ccff", name="#f2e0a0",
      badge="#9a9db8", scroll="#383b52", scroll_act="#484c68"),
}
for _k, _v in _THEMES_198.items():
    THEMES[_k] = dict(THEMES[_k], **_v)


# Fenetre "?" : ce que font le traducteur et l'addon. "# " = titre, "- " = puce.
HELP_TEXT = """# Comment ça marche
- Deux morceaux travaillent ensemble : l'addon ChatFR dans le jeu, et ce traducteur sur Windows.
- Un addon WoW n'a pas accès à Internet. ChatFR écrit donc chaque message du tchat sous forme d'une petite bande de cases colorées, en haut à gauche de l'écran.
- Le traducteur fait une capture de cette bande plusieurs fois par seconde, la décode, envoie le texte à Google Traduction, puis affiche le message et sa traduction ici.
- La barre du haut indique l'état : « Pont image : OK (N messages reçus) » veut dire que tout fonctionne. Un autre message veut dire que la bande n'est pas visible (WoW réduit, fenêtre par-dessus, mode plein écran exclusif).
- Rien n'est envoyé au jeu : le traducteur lit l'écran, il ne touche ni au jeu ni au clavier.
# Pour commencer
- Lance WoW en mode Fenêtré ou Plein écran (fenêtré), puis le traducteur avec « Lancer le traducteur.bat ».
- Attends « Pont image : OK » : les messages arrivent traduits en 1 à 2 secondes, avec la langue d'origine entre crochets ([EN], [DE]...).
- Ne recouvre pas la bande de cases colorées : sans elle, le traducteur ne reçoit plus rien.
# Traduction du tchat
- Traduit en direct les messages de toutes les langues (anglais, espagnol, allemand, russe...) vers le français, ou vers la langue choisie dans les Réglages.
- Tous les canaux : dire, crier, groupe, raid, guilde, chuchotements (en jeu et Battle.net), Général, Commerce, Recherche de groupe...
- Lexique de joueur : abréviations (gg, ty, lfm, pst, wts, any1...), jargon gardé tel quel (tank, heal, DPS, gank), donjons et zones en français (SFK -> Donjon d'Ombrecroc), prix en pièces jamais traduits.
- Liens d'objets et de quêtes colorés comme dans le jeu, marqueurs de raid affichés en symboles.
- Passe la souris sur un objet ou une quête en lien : sa fiche s'affiche (stats, niveau, prix), comme dans WoW.
- Les messages déjà en français ne passent pas par Google.
# Répondre
- Écris en français dans « Écrire (FR) » puis clique sur « Traduire + copier » : la traduction est copiée. Dans WoW : Entrée, Ctrl+V, Entrée.
- Clique sur un message : la langue de réponse se règle sur celle du joueur.
- Clique sur un pseudo : ta réponse est copiée avec /w Pseudo devant, pour lui chuchoter. La croix à côté du pseudo annule.
- Le traducteur n'envoie jamais rien au jeu : c'est toujours toi qui colles.
# Remplacer le tchat du jeu
- Dans les réglages de ChatFR en jeu (roue dentée), coche « Traducteur : PNJ », « messages système » et « butin et argent » pour voir aussi les PNJ, le système, la réputation (bleu), l'expérience, le butin, les ventes (vert) et les dépenses (rouge).
- Tes chuchotements envoyés (« À Pseudo ») s'affichent toujours.
# Fenêtre
- Réglages : thème (13 au choix), opacité, taille du texte, canaux masqués, alertes sur ton pseudo ou des mots.
- Cadenas (en haut à droite) : verrouille la position et la taille de la fenêtre.
- Se cache quand WoW n'est pas la fenêtre active et revient avec lui (option dans les Réglages).
- Se ferme toute seule quand WoW se ferme. Un bouton apparaît quand une nouvelle version est disponible.
# Addon ChatFR
- La bande de cases colorées en haut à gauche de l'écran transmet le tchat au traducteur : ne la recouvre pas.
- /cfr pont : affiche ou masque la bande. /cfr : liste des commandes.
- Fenêtre de traduction hors ligne dans le jeu, facultative (/cfr show, /cfr hide).
# Soutenir le projet
- WoW Traducteur et ChatFR sont et resteront gratuits, sans fonction réservée aux donateurs.
- Si ces outils te rendent service et que tu veux me soutenir : https://ko-fi.com/puenteur
# Avertissement
- Projet de fan non officiel : ni créé, ni soutenu, ni approuvé par Blizzard Entertainment (World of Warcraft est une marque de Blizzard). Ce n'est pas une méthode prévue par Blizzard, et il n'y a pas encore de confirmation officielle de Blizzard à ce sujet. Fourni tel quel, sans garantie : utilisation sous ta responsabilité.
"""

HELP_TEXT_EN = """# How it works
- Two parts work together: the ChatFR addon in the game, and this translator on Windows.
- A WoW addon has no Internet access. So ChatFR writes each chat message as a small strip of colored squares at the top left of the screen.
- The translator captures that strip several times per second, decodes it, sends the text to Google Translate, then shows the message and its translation here.
- The top bar shows the status: "Image bridge: OK (N messages received)" means everything works. Any other message means the strip is not visible (WoW minimized, a window on top, exclusive fullscreen).
- Nothing is sent to the game: the translator only reads the screen, it never touches the game or the keyboard.
# Getting started
- Run WoW in Windowed or Fullscreen (windowed) mode, then start the translator with "Lancer le traducteur.bat".
- Wait for "Image bridge: OK": messages arrive translated within 1 to 2 seconds, with the original language in brackets ([DE], [FR]...).
- Don't cover the strip of colored squares: without it, the translator receives nothing.
# Chat translation
- Translates messages from any language (French, Spanish, German, Russian...) into English live, or into the language chosen in Settings.
- All channels: say, yell, party, raid, guild, whispers (in game and Battle.net), General, Trade, Looking for Group...
- Item and quest links colored like in the game, raid markers shown as symbols.
- Hover an item or quest link: its details show up (stats, level, price), like in WoW.
- Messages already in your language are not sent to Google.
# Replying
- Write in English in "Write (EN)" then click "Translate + copy": the translation is copied. In WoW: Enter, Ctrl+V, Enter.
- Click a message: the reply language switches to that player's language. You can also pick it in the list next to the button.
- Click a name: your reply is copied with /w Name in front, to whisper them. The cross next to the name cancels.
- The translator never sends anything to the game: you always paste yourself.
# Replacing the game chat
- In ChatFR's settings in game (gear icon), tick "Traducteur : PNJ", "messages système" and "butin et argent" to also see NPCs, system messages, reputation, experience, loot, sales and spending.
- Your sent whispers ("To Name") are always shown.
# Window
- Settings: theme (13 to choose from), opacity, text size, hidden channels, alerts on your name or chosen words, interface language.
- Padlock (top right): locks the window position and size.
- Hides when WoW is not the active window and comes back with it (option in Settings).
- Closes by itself when WoW closes. A button appears when a new version is available.
# ChatFR addon
- The strip of colored squares at the top left of the screen sends the chat to the translator: don't cover it.
- /cfr pont: shows or hides the strip. /cfr: list of commands.
# Support the project
- WoW Traducteur and ChatFR are and will stay free, with no donor-only features.
- If these tools help you and you'd like to support me: https://ko-fi.com/puenteur
# Disclaimer
- Unofficial fan project: not made, supported or endorsed by Blizzard Entertainment (World of Warcraft is a trademark of Blizzard). This is not a method intended by Blizzard, and there is no official confirmation from Blizzard yet. Provided as is, without warranty: use at your own risk.
"""


def _thick(x1, y1, x2, y2, w):
    """Trait epais -> polygone (4 coins)."""
    dx, dy = x2 - x1, y2 - y1
    n = math.hypot(dx, dy) or 1.0
    ox, oy = -dy / n * w / 2, dx / n * w / 2
    return [x1 + ox, y1 + oy, x2 + ox, y2 + oy, x2 - ox, y2 - oy, x1 - ox, y1 - oy]


# Emblèmes ORIGINAUX (pas les logos officiels de Blizzard) : formes en coordonnees 84 x 96, du fond vers le dessus.
EMBLEMS = {
    # ecu bleu borde d'or, chevron et etoile d'or (heraldique generique)
    "shield": [
        ([6, 6, 78, 6, 78, 46, 73, 64, 60, 79, 42, 92, 24, 79, 11, 64, 6, 46], "#d4ad3a"),
        ([13, 13, 71, 13, 71, 46, 67, 61, 56, 73, 42, 84, 28, 73, 17, 61, 13, 46], "#173a7a"),
        (_thick(21, 20, 63, 20, 3), "#2c5aa8"),
        ([13, 46, 42, 30, 71, 46, 71, 58, 42, 42, 13, 58], "#d4ad3a"),
        ([42, 50, 45.5, 59, 55, 60, 47.5, 66, 50, 75, 42, 70, 34, 75, 36.5, 66, 29, 60, 38.5, 59], "#f0d070"),
    ],
    # etendard de guerre rouge a queue fendue, haches croisees (motif generique)
    "banner": [
        ([4, 3, 80, 3, 80, 10, 4, 10], "#6a4a2a"),
        ([12, 9, 72, 9, 72, 92, 42, 74, 12, 92], "#c9a06a"),
        ([17, 13, 67, 13, 67, 83, 42, 67, 17, 83], "#9c1f16"),
        (_thick(27, 60, 57, 22, 6), "#3a2414"),
        (_thick(57, 60, 27, 22, 6), "#3a2414"),
        ([50, 17, 65, 13, 67, 29, 58, 33], "#e8d2a8"),
        ([34, 17, 19, 13, 17, 29, 26, 33], "#e8d2a8"),
    ],
}


def _in_poly(x, y, poly):
    inside = False
    n = len(poly) // 2
    j = n - 1
    for i in range(n):
        xi, yi, xj, yj = poly[2 * i], poly[2 * i + 1], poly[2 * j], poly[2 * j + 1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi:
            inside = not inside
        j = i
    return inside


def emblem_png(kind, bg, w=20, ss=4):
    """PNG lisse (bords adoucis) de l'emblème, sur le fond `bg`."""
    shapes = EMBLEMS[kind]
    h = int(round(w * 96 / 84.0))
    sx, sy = 84.0 / w, 96.0 / h

    def rgb(c):
        c = c.lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    cols = [rgb(c) for _p, c in shapes]
    back = rgb(bg)
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            acc = [0, 0, 0]
            for j in range(ss):
                for i in range(ss):
                    px, py = (x + (i + .5) / ss) * sx, (y + (j + .5) / ss) * sy
                    c = back
                    for k in range(len(shapes) - 1, -1, -1):
                        if _in_poly(px, py, shapes[k][0]):
                            c = cols[k]
                            break
                    acc[0] += c[0]
                    acc[1] += c[1]
                    acc[2] += c[2]
            raw += bytes(round(v / (ss * ss)) for v in acc)

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


# Liens du tchat (envoyes par l'addon sous la forme \x02 code \x03 [Nom] \x04) :
# couleurs comme dans le tchat officiel de WoW.
LINK_COLORS = {
    "q": "#ffd100",                                   # quete (niveau inconnu)
    "q0": "#808080", "q1": "#40c040", "q2": "#ffff00", "q3": "#ff8040", "q4": "#ff1a1a",  # quete selon ton niveau
    "i0": "#9d9d9d", "i1": "#ffffff", "i2": "#1eff00", "i3": "#0070dd",   # objets par qualite
    "i4": "#a335ee", "i5": "#ff8000", "i6": "#e6cc80", "i7": "#00ccff", "i8": "#00ccff",
    "s": "#71d5ff",                                   # sort, talent
    "e": "#ffd000",                                   # enchantement, metier
    "a": "#ffff00",                                   # haut fait
    "o": "#ffd100",                                   # autre lien
}
LINK_RE = re.compile(r"\x02([a-z0-9]+)\x03(.*?)(?:\x04|$)", re.S)
BRACKET_RE = re.compile(r"\[[^\]]*\]")


# Marqueurs de raid du tchat ({rt1}, {star}...) : la fenetre ne peut pas afficher l'image, on met un symbole.
RAID_MARKS = {
    "rt1": "\u2605", "star": "\u2605", "etoile": "\u2605", "\u00e9toile": "\u2605",
    "rt2": "\u25cf", "circle": "\u25cf", "rond": "\u25cf", "cercle": "\u25cf",
    "rt3": "\u25c6", "diamond": "\u25c6", "losange": "\u25c6",
    "rt4": "\u25b2", "triangle": "\u25b2",
    "rt5": "\u263e", "moon": "\u263e", "lune": "\u263e",
    "rt6": "\u25a0", "square": "\u25a0", "carre": "\u25a0", "carr\u00e9": "\u25a0",
    "rt7": "\u2716", "cross": "\u2716", "croix": "\u2716", "x": "\u2716",
    "rt8": "\u2620", "skull": "\u2620", "crane": "\u2620", "cr\u00e2ne": "\u2620",
    # noms des marques dans les autres langues du jeu (ru, de, es, pt, it) : "{звезда}" -> ★
    "звезда": "\u2605", "stern": "\u2605", "estrella": "\u2605", "estrela": "\u2605", "stella": "\u2605",
    "круг": "\u25cf", "kreis": "\u25cf", "círculo": "\u25cf", "circulo": "\u25cf", "cerchio": "\u25cf",
    "ромб": "\u25c6", "diamant": "\u25c6", "diamante": "\u25c6", "rombo": "\u25c6",
    "треугольник": "\u25b2", "dreieck": "\u25b2", "triángulo": "\u25b2", "triangulo": "\u25b2", "triângulo": "\u25b2", "triangolo": "\u25b2",
    "полумесяц": "\u263e", "луна": "\u263e", "mond": "\u263e", "luna": "\u263e", "lua": "\u263e",
    "квадрат": "\u25a0", "quadrat": "\u25a0", "cuadrado": "\u25a0", "quadrado": "\u25a0", "quadrato": "\u25a0",
    "крест": "\u2716", "kreuz": "\u2716", "cruz": "\u2716", "xis": "\u2716", "croce": "\u2716",
    "череп": "\u2620", "totenschädel": "\u2620", "schädel": "\u2620", "calavera": "\u2620", "caveira": "\u2620", "teschio": "\u2620",
}
_MARK_RE = re.compile(r"\{(" + "|".join(sorted(RAID_MARKS, key=len, reverse=True)) + r")\}", re.I)


# Pings du groupe (Alt + clic) : le jeu met une icone devant le texte, la fenetre ne peut pas l'afficher.
# On met un symbole de la meme couleur. (mots de debut du ping, symbole, couleur)
PING_ICONS = [
    (("avertissement", "warning"), "\u26a0", "#ff4a3d"),
    (("aide", "assist"), "\u2691", "#4cd14c"),
    (("je me dirige", "on my way"), "\u2b07", "#3fa7ff"),
    (("attaque", "attack"), "\u2694", "#ff9d3a"),
    (("pas une menace", "pas de menace", "sans danger", "non-threat", "non threat", "not a threat"), "\u25ce", "#4cd14c"),
    (("menace", "threat"), "\u25c9", "#ff4a3d"),
    (("par ici", "look", "ping"), "\u25c8", "#3fa7ff"),       # ping simple : losange bleu dans le jeu
]


# Pings dessines en petite image (plus proche du jeu qu'un caractere) : numero dans PING_ICONS -> couleurs
# (clair, moyen, fonce, contour) d'un losange avec un losange plus sombre au centre.
PING_SHAPES = {
    5: ((255, 150, 130), (226, 38, 38), (120, 10, 14), (40, 0, 4)),        # Menace : losange rouge
    6: ((170, 215, 255), (52, 150, 245), (14, 64, 140), (4, 22, 52)),       # Par ici : losange bleu
}


def _ping_diamond(cols, u, v):
    """Couleur d'un point (u, v dans -1..1) du losange de ping, ou None (transparent)."""
    hi, mid, lo, out = cols
    d = abs(u) + abs(v)
    if d > 1:
        return None
    if d > 0.84:
        return out                                   # contour
    if d > 0.5:
        return _coin_mix(hi, mid, (u + v + 1) / 2)   # bord, eclaire en haut a gauche
    if d > 0.38:
        return out
    if d > 0.16:
        return lo                                    # creux sombre au milieu
    return mid                                       # point central


def ping_png(index, size, ss=4):
    """PNG (octets) du losange d'un ping, size x size, bords lisses."""
    cols = PING_SHAPES[index]
    raw = bytearray()
    for y in range(size):
        raw.append(0)
        for x in range(size):
            r = g = b = n = 0
            for sy in range(ss):
                for sx in range(ss):
                    c = _ping_diamond(cols, (x + (sx + 0.5) / ss) / size * 2 - 1,
                                      (y + (sy + 0.5) / ss) / size * 2 - 1)
                    if c is not None:
                        r += c[0]; g += c[1]; b += c[2]; n += 1
            raw += bytes((round(r / n), round(g / n), round(b / n), round(255 * n / (ss * ss)))) if n else b"\0\0\0\0"

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def ping_icon(text):
    """-> (symbole, nom du style) pour un ping, ou None."""
    low = text.strip().lower()
    for i, (words, sym, _c) in enumerate(PING_ICONS):
        if any(low.startswith(w) for w in words):
            return sym, "ping_%d" % i
    return None


def replace_raid_marks(text):
    return _MARK_RE.sub(lambda m: RAID_MARKS[m.group(1).lower()], text)


# Liens de quete Questie : "[[18] Collecting Memories (168)]" (niveau + numero) -> "[Collecting Memories]",
# colore comme une quete. Le niveau et le numero encombraient la ligne et la traduction.
_QUESTIE_RE = re.compile(r"(?:\x02\w+\x03)?\[\[\d+[+]?\]\s*([^\[\]]+?)\s*\(\d+\)\](?:\x04)?")


def clean_questie(text):
    return _QUESTIE_RE.sub(lambda m: "\x02q\x03[%s]\x04" % m.group(1), text)


def split_links(text):
    """Texte de l'addon -> (texte brut sans marqueurs, [(segment, code ou None), ...])."""
    spans, pos = [], 0
    for m in LINK_RE.finditer(text):
        if m.start() > pos:
            spans.append((text[pos:m.start()], None))
        spans.append((m.group(2), m.group(1) if m.group(1) in LINK_COLORS else "o"))
        pos = m.end()
    if pos < len(text):
        spans.append((text[pos:], None))
    plain = "".join(seg for seg, _ in spans)
    return plain, spans


def color_brackets(trans, codes):
    """Colore les [liens] d'une traduction, dans l'ordre des liens du message d'origine.
    Si Google a change le nombre de crochets, on ne colore rien (mieux que de se tromper)."""
    found = list(BRACKET_RE.finditer(trans))
    if not codes or len(found) != len(codes):
        return [(trans, None)]
    out, pos = [], 0
    for m, code in zip(found, codes):
        if m.start() > pos:
            out.append((trans[pos:m.start()], None))
        out.append((m.group(0), code))
        pos = m.end()
    if pos < len(trans):
        out.append((trans[pos:], None))
    return out


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# --------------------------------------------------------------------------
# Lecture du log
# --------------------------------------------------------------------------
TS = re.compile(r"^\S+\s+(\d{1,2}:\d{2}):\d{2}(?:\.\d+)?\s+(.*)$")
RE_CHAN = re.compile(r"^\[(\d+)\.\s*([^\]]+)\]\s*\[?([^\]:]+?)\]?\s*:\s*(.*)$")
RE_GROUP = re.compile(r"^\[([^\]\d][^\]]*)\]\s*\[?([^\]:]+?)\]?\s*:\s*(.*)$")
RE_WHISPER = re.compile(r"^\[?([^\]\s]+)\]?\s+(?:whispers|chuchote|fl\u00fcstert|susurra)[^:]*:\s*(.*)$", re.I)
RE_SAY = re.compile(r"^\[?([^\]\s]+)\]?\s+(says|yells|dit|crie|sagt|schreit|dice|grita)[^:]*:\s*(.*)$", re.I)


def clean_name(n):
    return n.strip().strip("[]").split("-")[0]


def group_kind(label):
    l = label.lower()
    if "offic" in l:
        return "officer"
    if "guil" in l or "gilde" in l:
        return "guild"
    if "raid" in l:
        return "raid"
    return "party"


def parse(line):
    """-> (heure, type, nom_du_canal, auteur, texte) ou None"""
    line = line.strip()
    m = TS.match(line)
    if not m:
        return None
    hhmm, body = m.group(1), m.group(2)
    m = RE_CHAN.match(body)
    if m:
        chan = m.group(2)
        low = chan.lower()
        kind = "lfg" if ("looking" in low or "recherche" in low or "suche" in low) else "channel"
        return hhmm, kind, chan, clean_name(m.group(3)), m.group(4)
    m = RE_WHISPER.match(body)
    if m:
        return hhmm, "whisper", "Chuchote", clean_name(m.group(1)), m.group(2)
    m = RE_SAY.match(body)
    if m:
        kind = "yell" if m.group(2).lower() in ("yells", "crie", "schreit", "grita") else "say"
        return hhmm, kind, "Dire", clean_name(m.group(1)), m.group(3)
    m = RE_GROUP.match(body)
    if m:
        return hhmm, group_kind(m.group(1)), m.group(1), clean_name(m.group(2)), m.group(3)
    # format inconnu : on coupe au premier ": "
    mm = re.match(r"^(.*?)\s*:\s+(.+)$", body)
    if mm:
        left, text = mm.group(1), mm.group(2)
        names = re.findall(r"\[([^\]]+)\]", left)
        words = re.findall(r"[^\s\[\]]+", left)
        who = names[-1] if names else (words[-1] if words else "")
        if who and text.strip():
            return hhmm, "other", left, clean_name(who), text
    return None


# --------------------------------------------------------------------------
# Traduction (Google, sans installation)
# --------------------------------------------------------------------------
# translate.googleapis.com d'abord (c'est celle qui marche dans le navigateur), l'autre en dernier recours.
_GT_HOSTS = ("translate.googleapis.com", "translate.google.com")
# En-tete d'un vrai navigateur : avec un simple "Mozilla/5.0", Google renvoie plus vite des 429.
_GT_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
_gt_lock = threading.Lock()
_gt_last = [0.0]
_gt_cache = {}
_gt_pause = [0.0]          # apres un 429 : plus aucune requete jusqu'a cette heure (sinon Google prolonge le blocage)
GT_PAUSE = 120             # secondes (1er blocage)
# Pause qui s'allonge si Google rebloque peu apres (il "n'oublie" pas en 2 min) : 2, 5, 10, puis 20 min.
# Une heure sans blocage : on repart a 2 min. Pendant la pause, les secours (Bing...) traduisent.
GT_PAUSES = (120, 300, 600, 1200)
_gt_level = [-1, 0.0]      # palier de pause actuel (-1 = aucun blocage recent), heure du dernier blocage


# ---- Historique des services de traduction (services.txt) --------------------
# Par jour : combien de messages chaque service a traduits, et les incidents (Google bloque, en panne...).
# JAMAIS le texte des messages ni les pseudos : seulement des chiffres et des heures.
SERVICES_TXT = os.path.join(DATA_DIR, "services.txt")
SERVICES_JSON = os.path.join(DATA_DIR, "services.json")      # memes donnees, pour les relire au lancement
_svc_lock = threading.Lock()
_svc = {"days": {}, "events": []}
_svc_dirty = [False]
try:
    with open(SERVICES_JSON, "r", encoding="utf-8") as _f:
        _svc.update(json.load(_f))
except Exception:  # noqa
    pass


def svc_count(service):
    """Un message traduit par ce service ("google", "bing", "reverso", "yandex", "mymemory") ou "echec"."""
    day = time.strftime("%Y-%m-%d")
    with _svc_lock:
        d = _svc["days"].setdefault(day, {})
        d[service] = d.get(service, 0) + 1
        _svc_dirty[0] = True


def svc_event(text):
    """Un incident, avec la date et l'heure."""
    with _svc_lock:
        _svc["events"].append("%s  %s" % (time.strftime("%Y-%m-%d %H:%M"), text))
        del _svc["events"][:-200]                     # les 200 derniers seulement
        _svc_dirty[0] = True


def svc_save():
    """Ecrit services.json et services.txt (lisible au Bloc-notes). Appele toutes les 30 s et a la fermeture."""
    with _svc_lock:
        if not _svc_dirty[0]:
            return
        _svc_dirty[0] = False
        for old in sorted(_svc["days"])[:-30]:          # les 30 derniers jours seulement
            del _svc["days"][old]
        data = json.loads(json.dumps(_svc))
    try:
        with open(SERVICES_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f)
        names = (("google", "Google"), ("bing", "Bing"), ("reverso", "Reverso"), ("yandex", "Yandex"),
                 ("mymemory", "MyMemory"), ("echec", "Echecs"))
        lines = ["WoW Traducteur %s - services de traduction utilises" % VERSION,
                 "(seulement des chiffres et des heures, jamais le texte des messages)", "",
                 "Messages traduits par jour :"]
        for day in sorted(data["days"], reverse=True):
            d = data["days"][day]
            lines.append("  %s   " % day + "   ".join("%s %d" % (lab, d.get(k, 0)) for k, lab in names))
        lines += ["", "Incidents (les plus recents en haut) :"]
        lines += ["  " + e for e in reversed(data["events"])] or ["  aucun"]
        with open(SERVICES_TXT, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception:  # noqa
        pass


def _google(text, target, source="auto", timeout=8):
    """-> (traduction, langue_detectee). Google limite le nombre de requetes (erreur 429) :
    on espace les appels, on garde un cache et on reessaie apres une courte pause."""
    key = (text, target, source)
    with _gt_lock:
        if key in _gt_cache:
            return _gt_cache[key]
    reste = _gt_pause[0] - time.time()
    if reste > 0:
        raise RuntimeError("Google en pause (trop de requetes), reprise dans %d s" % reste)
    params = urllib.parse.urlencode({"client": "gtx", "sl": source, "tl": target, "dt": "t", "q": text})
    last_err = None
    for attempt in range(2):                           # 2 essais courts, puis les services de secours
        host = _GT_HOSTS[attempt]
        with _gt_lock:                                 # 0,3 s minimum entre deux requetes
            wait = 0.3 - (time.time() - _gt_last[0])
            if wait > 0:
                time.sleep(wait)
            _gt_last[0] = time.time()
        req = urllib.request.Request("https://%s/translate_a/single?%s" % (host, params),
                                     headers={"User-Agent": _GT_UA, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429:
                break                                  # bloque : inutile d'insister, on passe au secours
            if e.code >= 500:                          # panne passagere chez Google (500, 502, 503...) :
                time.sleep(0.5)                        # on reessaie sur l'autre serveur, puis le secours
                continue
            break                                      # autre refus (400, 403...) : directement le secours
        except (urllib.error.URLError, OSError, ValueError) as e:
            # coupure reseau, delai depasse, reponse tronquee : on reessaie aussi
            last_err = e
            time.sleep(0.5)
            continue
        out = "".join(seg[0] for seg in data[0] if seg and seg[0])
        lang = data[2] if len(data) > 2 and isinstance(data[2], str) else "?"
        svc_count("google")
        with _gt_lock:
            if len(_gt_cache) > 500:
                _gt_cache.clear()
            _gt_cache[key] = (out, lang)
        return out, lang
    if getattr(last_err, "code", None) == 429:
        now = time.time()
        lvl, last = _gt_level
        if lvl < 0 or now - last > 3600:              # 1er blocage, ou une heure calme : 2 min
            lvl = 0
        elif now - _gt_pause[0] <= 900:               # rebloque moins de 15 min apres la fin de la pause
            lvl = min(lvl + 1, len(GT_PAUSES) - 1)    # -> pause plus longue
        pause = GT_PAUSES[lvl]
        _gt_level[0], _gt_level[1] = lvl, now
        _gt_pause[0] = now + pause
        svc_event("Google bloque (trop de demandes, erreur 429) : pause de %d min" % (pause // 60))
        raise RuntimeError("Google limite les requetes (429), pause de %d s" % pause)
    code = getattr(last_err, "code", None)
    raise RuntimeError("Google ne repond pas (%s)" % ("erreur %s" % code if code else
                                                      getattr(last_err, "reason", None) or last_err))


def _mymemory(text, target, source, timeout=8):
    """Service de secours gratuit (api.mymemory.translated.net), sans cle, ~5000 caracteres/jour."""
    out_lang = "?" if source == "auto" else source
    # "autodetect" d'abord ; si MyMemory le refuse : anglais (le plus courant), ou francais si on traduit vers l'anglais
    for src in ([("autodetect"), ("fr" if target == "en" else "en")] if source == "auto" else [source]):
        params = urllib.parse.urlencode({"q": text, "langpair": "%s|%s" % (src, target)})
        req = urllib.request.Request("https://api.mymemory.translated.net/get?" + params,
                                     headers={"User-Agent": _GT_UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        rd = data.get("responseData") or {}
        out = (rd.get("translatedText") or "").strip()
        status = str(data.get("responseStatus"))
        if status == "200" and out and not out.upper().startswith("MYMEMORY WARNING"):
            det = rd.get("detectedLanguage") or (src if src != "autodetect" else out_lang)
            return out, str(det).lower().split("-")[0]
        if "MYMEMORY WARNING" in out.upper() or status == "429":
            raise RuntimeError("quota du jour atteint")
    raise RuntimeError("MyMemory a refuse la requete (%s)" % status)


# Secours quand Google bloque (1.9.8, essai) : Bing, Reverso, Yandex, puis MyMemory.
# Tous sans compte ni cle : on passe par l'acces qu'utilise leur propre site (comme pour Google).
# Fragile : si un service change son site ou demande un captcha, il echoue et on l'oublie 10 min.
# (Lingva retire : ses serveurs n'obtenaient plus rien de Google. Microsoft/Edge : ferme en 2026.)
import http.cookiejar
_MS_LANG = {"zh": "zh-Hans", "zh-cn": "zh-Hans", "zh-tw": "zh-Hant", "no": "nb", "iw": "he", "tl": "fil"}
_bing = {"opener": None, "ig": "", "iid": "", "key": "", "token": "", "at": 0.0, "n": 0}
_bing_lock = threading.Lock()


def _bing_setup(timeout):
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    req = urllib.request.Request("https://www.bing.com/translator", headers={"User-Agent": _GT_UA,
                                 "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"})
    with op.open(req, timeout=timeout) as r:
        page = r.read().decode("utf-8", "replace")
    ig = re.search(r'IG:"([^"]+)"', page)
    iid = re.search(r'data-iid="([^"]+)"', page)
    ab = re.search(r'params_AbusePreventionHelper\s*=\s*\[\s*(\d+)\s*,\s*"([^"]+)"', page)
    if not (ig and ab):
        raise RuntimeError("page Bing inattendue (captcha ?)")
    _bing.update(opener=op, ig=ig.group(1), iid=(iid.group(1) if iid else "translator.5028"),
                 key=ab.group(1), token=ab.group(2), at=time.time(), n=0)


def _bing_translate(text, target, source, timeout=5):
    """Bing Traduction (moteur Microsoft) -> (traduction, langue_detectee)."""
    with _bing_lock:
        if not _bing["opener"] or time.time() - _bing["at"] > 1500:      # codes du site : refaits toutes les 25 min
            _bing_setup(timeout)
        _bing["n"] += 1
        url = "https://www.bing.com/ttranslatev3?isVertical=1&IG=%s&IID=%s.%d" % (_bing["ig"], _bing["iid"], _bing["n"])
        data = urllib.parse.urlencode({
            "fromLang": "auto-detect" if source in ("", "auto") else _MS_LANG.get(source, source),
            "to": _MS_LANG.get(target, target), "text": text, "token": _bing["token"], "key": _bing["key"],
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={
            "User-Agent": _GT_UA, "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://www.bing.com/translator", "Origin": "https://www.bing.com"})
        try:
            with _bing["opener"].open(req, timeout=timeout) as r:
                raw = r.read().decode("utf-8", "replace")
        except Exception:
            _bing["opener"] = None                   # on recharge la page la prochaine fois
            raise
    try:
        data = json.loads(raw)
    except ValueError:
        _bing["opener"] = None
        raise RuntimeError("reponse illisible (captcha ?)")
    if isinstance(data, dict):                       # {"statusCode": 400...} : codes perimes
        _bing["opener"] = None
        raise RuntimeError("refus %s" % data.get("statusCode", "?"))
    item = data[0] if data else {}
    out = ((item.get("translations") or [{}])[0].get("text") or "").strip()
    if not out:
        raise RuntimeError("reponse vide")
    det = (item.get("detectedLanguage") or {}).get("language") or (source if source != "auto" else "?")
    return out, str(det).lower().split("-")[0]


# Reverso : codes de langue a 3 lettres, et seulement ces langues-la
_REV_LANG = {"en": "eng", "fr": "fra", "de": "ger", "es": "spa", "it": "ita", "pt": "por", "ru": "rus",
             "pl": "pol", "nl": "dut", "sv": "swe", "tr": "tur", "uk": "ukr", "ro": "rum", "ar": "ara",
             "he": "heb", "iw": "heb", "ja": "jpn", "ko": "kor", "zh": "chi", "zh-cn": "chi"}
_REV_BACK = {v: k for k, v in _REV_LANG.items()}


def _reverso(text, target, source, timeout=5):
    to = _REV_LANG.get(target)
    if not to:
        raise RuntimeError("langue %s non geree" % target)
    src = _REV_LANG.get(source) if source not in ("", "auto") else ("fra" if to == "eng" else "eng")
    if not src:
        raise RuntimeError("langue %s non geree" % source)
    body = json.dumps({"format": "text", "from": src, "to": to, "input": text,
                       "options": {"sentenceSplitter": True, "origin": "translation.web",
                                   "contextResults": False, "languageDetection": True}}).encode("utf-8")
    req = urllib.request.Request("https://api.reverso.net/translate/v1/translation", data=body, headers={
        "User-Agent": _GT_UA, "Content-Type": "application/json", "Accept": "application/json",
        "Origin": "https://www.reverso.net", "Referer": "https://www.reverso.net/"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))
    out = " ".join(t for t in (data.get("translation") or []) if t).strip()
    if not out:
        raise RuntimeError("reponse vide")
    det = ((data.get("languageDetection") or {}).get("detectedLanguage") or src)
    return out, _REV_BACK.get(det, det[:2])


_yandex = {"sid": "", "at": 0.0}
_yandex_lock = threading.Lock()


def _yandex_translate(text, target, source, timeout=5):
    with _yandex_lock:
        if not _yandex["sid"] or time.time() - _yandex["at"] > 1500:
            req = urllib.request.Request("https://translate.yandex.com/", headers={"User-Agent": _GT_UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                page = r.read().decode("utf-8", "replace")
            m = re.search(r"SID:\s*'([^']+)'", page) or re.search(r'"SID"\s*:\s*"([^"]+)"', page)
            if not m:
                raise RuntimeError("page Yandex inattendue (captcha ?)")
            _yandex["sid"] = ".".join(w[::-1] for w in m.group(1).split("."))
            _yandex["at"] = time.time()
        sid = _yandex["sid"]
    lang = target if source in ("", "auto") else "%s-%s" % (source, target)
    url = "https://translate.yandex.net/api/v1/tr.json/translate?" + urllib.parse.urlencode(
        {"id": sid + "-0-0", "srv": "tr-text", "lang": lang, "reason": "auto", "format": "text"})
    req = urllib.request.Request(url, data=urllib.parse.urlencode({"text": text, "options": "4"}).encode("utf-8"),
                                 headers={"User-Agent": _GT_UA, "Content-Type": "application/x-www-form-urlencoded",
                                          "Referer": "https://translate.yandex.com/"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        _yandex["sid"] = ""
        raise
    if data.get("code") != 200:
        _yandex["sid"] = ""
        raise RuntimeError("refus %s" % data.get("code"))
    out = " ".join(data.get("text") or []).strip()
    if not out:
        raise RuntimeError("reponse vide")
    det = str(data.get("lang") or "").split("-")[0] or (source if source != "auto" else "?")
    return out, det


_BACKUPS = (("bing", "Bing", _bing_translate), ("reverso", "Reverso", _reverso), ("yandex", "Yandex", _yandex_translate))
_backup_dead = {}      # service -> heure jusqu'a laquelle on ne l'essaie plus (10 min apres un echec)


def _svc_reason(e):
    """Raison courte pour l'historique : "Google en panne (erreur 500)", "Google bloque (429)"..."""
    m = re.search(r"\b(4\d\d|5\d\d)\b", str(e))
    if "en pause" in str(e) or (m and m.group(1) == "429"):
        return "Google en pause (bloque)"
    return "Google en panne (erreur %s)" % m.group(1) if m else "Google ne repond pas"


def google_translate(text, target, source="auto", timeout=8):
    """Google ; s'il bloque (429) ou ne repond pas : Bing, Reverso, Yandex, puis MyMemory."""
    try:
        return _google(text, target, source, timeout)
    except RuntimeError as e:
        paused = "en pause" in str(e) or "429" in str(e)    # Google bloque : deja note, pas un incident par message
        res, fails = None, []
        for key, name, fn in _BACKUPS:
            if _backup_dead.get(key, 0) > time.time():
                continue
            try:
                res = fn(text, target, source)
                svc_count(key)
                if not paused or fails:
                    svc_event("%s%s -> traduit par %s" % (_svc_reason(e), "".join(fails), name))
                break
            except Exception as eb:  # noqa
                _backup_dead[key] = time.time() + 600       # en panne / captcha : on l'oublie 10 min
                fails.append(", %s echoue (%s)" % (name, str(eb)[:50]))
        if res is None:
            try:
                res = _mymemory(text, target, source, 5)
                svc_count("mymemory")
                if not paused or fails:
                    svc_event("%s%s -> traduit par MyMemory" % (_svc_reason(e), "".join(fails)))
            except Exception as e2:  # noqa
                svc_count("echec")
                svc_event("ECHEC : aucun service ne repond (%s%s)" % (_svc_reason(e), "".join(fails)))
                raise RuntimeError("%s ; MyMemory : %s" % (e, e2))
        with _gt_lock:
            _gt_cache[(text, target, source)] = res
        return res


# Noms propres que Google prend pour des mots communs ("hogger" -> "porc"). Ils sont remplaces par
# un code avant l'envoi a Google puis remis tels quels dans la traduction. Ajoute les tiens ici.
LEX_NAMES = ["Hogger"]

# Donjons, raids, zones et villes (repris du Dictionary.lua de ChatFR) : masques comme LEX_NAMES,
# puis remplaces par leur nom francais (seulement quand la langue cible est le francais).
# "SFK" -> "Donjon d'Ombrecroc". Ajoute les tiens ici : "abreviation en minuscules": "nom francais".
LEX_PLACES = {
    # objets de camp de Forever (nom officiel francais, verifie en jeu)
    'tanning racks': 'chevalets de tannage', 'tanning rack': 'chevalet de tannage',
    # race de Forever (nom officiel Blizzard fr : Eolides / Eolide) et sa zone de depart ; "skybron" : faute vue en jeu
    'skyborne': '\u00c9olide', 'skyborn': '\u00c9olide', 'skybron': '\u00c9olide',
    'zephras isle': "\u00cele de Z\u00e9phras", 'zephras': 'Z\u00e9phras',
    'northshire valley': 'Vall\u00e9e de Comt\u00e9-du-Nord', 'northshire': 'Comt\u00e9-du-Nord',
    'rfc': 'Gouffre de Ragefeu', 'ragefire chasm': 'Gouffre de Ragefeu', 'wc': 'Cavernes des lamentations',
    'wailing caverns': 'Cavernes des lamentations', 'vc': 'Mortemines',
    'dm': 'Mortemines (ou Hache-tripes)', 'deadmines': 'Mortemines', 'deadmine': 'Mortemines', 'sfk': "Donjon d'Ombrecroc",
    'shadowfang keep': "Donjon d'Ombrecroc", 'bfd': 'Profondeurs de Brassenoire',
    'blackfathom deeps': 'Profondeurs de Brassenoire', 'stockades': 'La Prison', 'stocks': 'La Prison',
    'the stockade': 'La Prison', 'stockade': 'La Prison', 'gnomer': 'Gnomeregan',
    'gnomeregan': 'Gnomeregan', 'rfk': 'Kraal de Tranchebauge', 'razorfen kraul': 'Kraal de Tranchebauge',
    'sm': 'Monastère écarlate', 'scarlet monastery': 'Monastère écarlate',
    'sm gy': 'Monastère écarlate : cimetière', 'sm lib': 'Monastère écarlate : bibliothèque',
    'sm arm': 'Monastère écarlate : armurerie', 'sm cath': 'Monastère écarlate : cathédrale',
    'rfd': 'Souilles de Tranchebauge', 'razorfen downs': 'Souilles de Tranchebauge', 'uld': 'Uldaman',
    'ulda': 'Uldaman', 'uldaman': 'Uldaman', 'zf': "Zul'Farrak", "zul'farrak": "Zul'Farrak",
    'mara': 'Maraudon', 'maraudon': 'Maraudon', 'st': "Temple d'Atal'Hakkar",
    'sunken temple': "Temple d'Atal'Hakkar", "temple of atal'hakkar": "Temple d'Atal'Hakkar",
    'brd': 'Profondeurs de Blackrock', 'blackrock depths': 'Profondeurs de Blackrock',
    'lbrs': 'Pic Blackrock inférieur', 'ubrs': 'Pic Blackrock supérieur',
    'lower blackrock spire': 'Pic Blackrock inférieur', 'upper blackrock spire': 'Pic Blackrock supérieur',
    'brs': 'Pic Blackrock', 'strat': 'Stratholme', 'stratholme': 'Stratholme', 'scholo': 'Scholomance',
    'scholomance': 'Scholomance', 'dire maul': 'Hache-tripes', 'dme': 'Hache-tripes est',
    'dmw': 'Hache-tripes ouest', 'dmn': 'Hache-tripes nord', 'dm east': 'Hache-tripes est',
    'dm west': 'Hache-tripes ouest', 'dm north': 'Hache-tripes nord', 'mc': 'Cœur du Magma',
    'molten core': 'Cœur du Magma', 'bwl': "Repaire de l'Aile noire",
    'blackwing lair': "Repaire de l'Aile noire", 'zg': "Zul'Gurub", "zul'gurub": "Zul'Gurub",
    'aq20': "Ruines d'Ahn'Qiraj", 'aq40': "Temple d'Ahn'Qiraj", 'aq': "Ahn'Qiraj", 'ony': 'Onyxia',
    'onyxia': 'Onyxia', 'naxx': 'Naxxramas', 'naxxramas': 'Naxxramas', 'kara': 'Karazhan',
    'karazhan': 'Karazhan', 'gruul': 'Repaire de Gruul', 'mag': 'Magtheridon',
    'magtheridon': 'Magtheridon', 'ssc': 'Caverne du sanctuaire du Serpent', 'tk': 'Donjon de la Tempête',
    'tempest keep': 'Donjon de la Tempête', 'bt': 'Temple noir', 'black temple': 'Temple noir',
    'mh': "Sommet d'Hyjal", 'hyjal': "Sommet d'Hyjal", 'swp': 'Plateau du Puits de soleil',
    'sunwell': 'Puits de soleil', 'za': "Zul'Aman", "zul'aman": "Zul'Aman", 'ulduar': 'Ulduar',
    'toc': 'Épreuve du croisé', 'icc': 'Citadelle de la Couronne de glace', 'voa': "Caveau d'Archavon",
    'os': 'Sanctum Obsidien', 'eoe': "Œil de l'éternité", 'fl': 'Terres de Feu',
    'dragon soul': 'Âme des dragons', 'hellfire': 'Péninsule des Flammes infernales',
    'ramparts': 'Remparts des Flammes infernales', 'blood furnace': 'Fournaise du sang',
    'shattered halls': 'Salles brisées', 'slave pens': 'Les enclos aux esclaves',
    'underbog': 'Basse-tourbière', 'steamvault': 'Caveau de la vapeur', 'mana tombs': 'Tombes-mana',
    'auchenai crypts': 'Cryptes Auchenaï', 'sethekk halls': 'Salles des Sethekk',
    'shadow labyrinth': 'Labyrinthe des ombres', 'mechanar': 'Méchanar', 'botanica': 'Botanica',
    'arcatraz': 'Arcatraz', 'old hillsbrad': "Contreforts de Hautebrande d'antan",
    'black morass': 'Le Noir Marécage', 'magisters terrace': 'Terrasse des Magistères',
    'stormwind': 'Hurlevent', 'sw': 'Hurlevent', 'ironforge': 'Forgefer', 'darnassus': 'Darnassus',
    'exodar': 'Exodar', 'orgrimmar': 'Orgrimmar', 'org': 'Orgrimmar',
    'thunder bluff': 'Les Pitons-du-Tonnerre', 'tb': 'Les Pitons-du-Tonnerre', 'undercity': 'Fossoyeuse',
    'uc': 'Fossoyeuse', 'silvermoon': "Lune-d'argent", 'shattrath': 'Shattrath', 'dalaran': 'Dalaran',
    'booty bay': 'Baie-du-Butin', 'gadgetzan': 'Gadgetzan', 'ratchet': 'Cabestan', 'menethil': 'Menethil',
    'theramore': 'Theramore', 'auberdine': 'Auberdine', 'astranaar': 'Astranaar',
    'crossroads': 'Le Carrefour', 'the crossroads': 'Le Carrefour', 'xroads': 'Le Carrefour',
    'sentinel hill': 'Colline-aux-Sentinelles', 'goldshire': "Comté-de-l'Or", 'lakeshire': 'Bourg-du-Lac',
    'darkshire': 'Sombre-comté', 'southshore': 'Southshore', 'tarren mill': 'Moulin-de-Tarren',
    'brill': 'Brill', 'razor hill': 'Tranchecolline', 'valley of trials': 'Vallée des Épreuves',
    'elwynn forest': "Forêt d'Elwynn", 'elwynn': "Forêt d'Elwynn", 'westfall': "Marche de l'Ouest",
    'duskwood': 'Bois de la Pénombre', 'redridge': 'Les Carmines', 'redridge mountains': 'Les Carmines',
    'stranglethorn': 'Strangleronce', 'stranglethorn vale': 'Vallée de Strangleronce',
    'stv': 'Vallée de Strangleronce', 'barrens': 'Les Tarides', 'the barrens': 'Les Tarides',
    'northern barrens': 'Tarides du nord', 'southern barrens': 'Tarides du sud', 'tanaris': 'Tanaris',
    'ungoro': "Un'Goro", "un'goro": "Un'Goro", "un'goro crater": "Cratère d'Un'Goro",
    'winterspring': "Berceau-de-l'Hiver", 'silithus': 'Silithus', 'felwood': 'Gangrebois',
    'ashenvale': 'Orneval', 'stonetalon': 'Les Serres-Rocheuses', 'desolace': 'Désolace',
    'feralas': 'Féralas', 'dustwallow': "Marécage d'Âprefange", 'dustwallow marsh': "Marécage d'Âprefange",
    'thousand needles': 'Mille pointes', 'azshara': 'Azshara', 'hillsbrad': 'Contreforts de Hautebrande',
    'hillsbrad foothills': 'Contreforts de Hautebrande', 'arathi': 'Arathi',
    'arathi highlands': "Hautes-terres d'Arathi", 'alterac': 'Alterac',
    'alterac mountains': "Montagnes d'Alterac", 'badlands': 'Terres ingrates',
    'searing gorge': 'Gorge des Vents brûlants', 'burning steppes': 'Steppes ardentes',
    'blasted lands': 'Terres foudroyées', 'swamp of sorrows': 'Marais des Chagrins',
    'deadwind pass': 'Défilé de Deuillevent', 'tirisfal': 'Clairières de Tirisfal',
    'tirisfal glades': 'Clairières de Tirisfal', 'silverpine': 'Forêt des Pins-Argentés',
    'silverpine forest': 'Forêt des Pins-Argentés', 'hinterlands': 'Les Hinterlands',
    'the hinterlands': 'Les Hinterlands', 'wetlands': 'Les Paluns', 'loch modan': 'Loch Modan',
    'dun morogh': 'Dun Morogh', 'teldrassil': 'Teldrassil', 'darkshore': 'Sombrivage',
    'moonglade': 'Reflet-de-Lune', 'mulgore': 'Mulgore', 'durotar': 'Durotar',
    'epl': "Maleterres de l'est", 'wpl': "Maleterres de l'ouest",
    'eastern plaguelands': "Maleterres de l'est", 'western plaguelands': "Maleterres de l'ouest",
    'plaguelands': 'Maleterres', 'eversong': 'Bois des Chants éternels', 'ghostlands': 'Orfraie',
    'azuremyst': 'Île de Brume-azur', 'bloodmyst': 'Île de Brume-sang',
    'hellfire peninsula': 'Péninsule des Flammes infernales', 'zangarmarsh': 'Marécage de Zangar',
    'terokkar': 'Forêt de Terokkar', 'nagrand': 'Nagrand', "blade's edge": 'Les Tranchantes',
    'blades edge': 'Les Tranchantes', 'netherstorm': 'Raz-de-Néant',
    'shadowmoon valley': "Vallée d'Ombrelune", 'northrend': 'Norfendre', 'outland': 'Outreterre',
    'kalimdor': 'Kalimdor', 'eastern kingdoms': "Royaumes de l'est", 'ek': "Royaumes de l'est",
    'azeroth': 'Azeroth', 'gg': 'bien joué',
}
# Jargon que les joueurs francais utilisent tel quel : masque comme LEX_NAMES pour que Google ne le
# traduise pas ("need heal" -> "besoin de heal", pas "besoin de soins").
LEX_KEEP = {"tank": "tank", "tanks": "tanks", "heal": "heal", "heals": "heals",
            "healer": "healer", "healers": "healers", "dps": "DPS",
            "gank": "gank", "ganked": "ganké", "ganking": "gank", "ganks": "gank",
            "boss": "boss", "bosses": "boss", "full": "full",
            "proc": "proc", "procs": "procs",   # "procs" -> "procédures" sinon
            "hunt": "hunt", "hunts": "hunts",
            "craft": "craft", "crafts": "crafts", "crafted": "crafté", "crafting": "craft",   # "artisanat" sinon
            "mob": "mob", "mobs": "mobs", "pull": "pull", "pulls": "pulls", "pulled": "pull",
            "rush": "rush", "rushes": "rushs"}   # "prison rush" : traversee rapide du donjon par un haut niveau   # chasseur, pas "chasse"   # "full for boss" -> "full pour le boss"
# Classes que Google traduit mal ("rogue" -> "voyou", "warlock" -> "sorcier") : nom francais du jeu.
LEX_CLASSES = {"rogue": "voleur", "rogues": "voleurs", "warlock": "démoniste", "warlocks": "démonistes"}
# Enchantements et stats : nom francais du jeu ("Got FIERY WEP" restait en anglais, "+2 End" donnait "+2 Fin")
LEX_ENCHANTS = {"fiery weapon": "Arme flamboyante", "fiery weapons": "Arme flamboyante", "crusader": "Croisé",
                "stamina": "Endurance", "stam": "Endurance"}
# "dm me" / "dm pls" = message prive, pas les Mortemines.
_PLACE_NOT_BEFORE = {"dm": r"(?!\s*(?:me|him|her|them|u|you|pls|plz)\b)"}


LEX_PLACES_FOREIGN = {
    # noms allemands et espagnols ("TODESMINE" = Mortemines)
    'todesminen': 'Mortemines', 'todesmine': 'Mortemines', 'burg schattenfang': "Donjon d'Ombrecroc",
    'das verlies': 'La Prison', 'verlies': 'La Prison', 'h\u00f6hlen des wehklagens': 'Cavernes des lamentations',
    'tiefschwarze grotte': 'Profondeurs de Brassenoire', 'scharlachrotes kloster': 'Monast\u00e8re \u00e9carlate',
    'flammenschlund': 'Gouffre de Ragefeu', 'minas de la muerte': 'Mortemines',
    'castillo de colmillo oscuro': "Donjon d'Ombrecroc", 'las mazmorras': 'La Prison',
    'cuevas de los lamentos': 'Cavernes des lamentations', 'monasterio escarlata': 'Monast\u00e8re \u00e9carlate',
}
LEX_PLACES_EN = dict(LEX_PLACES)        # cles anglaises seulement (pour la table francais -> anglais)
LEX_PLACES.update(LEX_PLACES_FOREIGN)


def _name_re(name):
    """Regex d'un nom propre qui tolere les lettres repetees ("hoggeer", "hoggerr")."""
    return "".join(re.escape(c) + "+" for c in name.lower())


def _protected(target):
    """{nom ou abreviation: texte remis apres Google}, les plus longs d'abord ("sm gy" avant "sm")."""
    d = {n: n for n in LEX_NAMES}
    if (target or "").lower() == "fr":
        d.update(LEX_PLACES)
        d.update(LEX_KEEP)
        d.update(LEX_CLASSES)
        d.update(LEX_ENCHANTS)
    return dict(sorted(d.items(), key=lambda kv: len(kv[0]), reverse=True))


def _names_pattern(target):
    names = _protected(target)
    if not names:
        return None
    return r"(?<!\w)(?:%s)(?!\w)" % "|".join(_name_re(n) + _PLACE_NOT_BEFORE.get(n.lower(), "")
                                             for n in names)


def google_translate_safe(text, target, source="auto", timeout=8):
    """Comme google_translate, mais sans laisser Google traduire les noms de LEX_NAMES / LEX_PLACES."""
    found = {}
    names = _protected(target)
    pat = _names_pattern(target)

    def mask(m):
        key = "Zq%dx" % len(found)
        found[key] = next(v for n, v in names.items() if re.fullmatch(_name_re(n), m.group(0), re.I))
        return key
    if pat:
        text = re.sub(pat, mask, text, flags=re.I)
    out, lang = google_translate(text, target, source, timeout)
    for key, name in found.items():
        out = re.sub(re.escape(key), lambda _m, n=name: n, out, flags=re.I)
    return out, lang


# Quand TU ecris en francais : on garde le jargon (tank, heal...) et on remplace les donjons par leur
# nom anglais, connu de tous ("Mortemines" -> "Deadmines" et pas "mina de muerte").
OUT_JARGON = ["tank", "tanks", "heal", "heals", "healer", "healers", "dps", "pull", "mob", "mobs", "boss",
              "full", "proc", "procs", "hunt", "gank", "lfg", "lfm", "wts", "wtb", "pst", "gg", "afk", "brb"]


def _fr_to_en_places():
    best = {}
    for k, v in LEX_PLACES_EN.items():
        if "(" in v or len(k) < 5 or not re.fullmatch(r"[a-z' ]+", k) or max(len(w) for w in k.split()) < 4 \
                or k.startswith(("sm ", "dm ")):
            continue
        if len(k) > len(best.get(v.lower(), "")):
            best[v.lower()] = k
    def nice(en):          # "swamp of sorrows" -> "Swamp of Sorrows", "blade's edge" -> "Blade's Edge"
        out = []
        for i, w in enumerate(en.split()):
            if i and w in ("of", "the"):
                out.append(w)
                continue
            parts = w.split("'")
            out.append("'".join([parts[0][:1].upper() + parts[0][1:]] +
                                [q if q == "s" else q[:1].upper() + q[1:] for q in parts[1:]]))
        return " ".join(out)
    return {fr: nice(en) for fr, en in best.items()}


OUT_PLACES = _fr_to_en_places()
# Noms des donjons dans le jeu espagnol / allemand (sinon : nom anglais, compris partout)
OUT_PLACES_LANG = {
    "es": {"Deadmines": "Minas de la Muerte", "The Stockade": "Las Mazmorras",
           "Shadowfang Keep": "Castillo de Colmillo Oscuro", "Wailing Caverns": "Cuevas de los Lamentos",
           "Scarlet Monastery": "Monasterio Escarlata", "Ragefire Chasm": "Sima \u00cdgnea",
           "Dire Maul": "La Masacre", "Blackfathom Deeps": "Cavernas de Brazanegra"},
    "de": {"Deadmines": "Die Todesminen", "The Stockade": "Das Verlies", "Shadowfang Keep": "Burg Schattenfang",
           "Wailing Caverns": "Die H\u00f6hlen des Wehklagens", "Scarlet Monastery": "Das Scharlachrote Kloster",
           "Ragefire Chasm": "Der Flammenschlund", "Dire Maul": "D\u00fcsterbruch",
           "Blackfathom Deeps": "Die Tiefschwarze Grotte"},
}
_ACC = {"e": "[e\u00e9\u00e8\u00ea\u00eb]", "a": "[a\u00e0\u00e2]", "o": "[o\u00f4]", "u": "[u\u00f9\u00fb]",
        "i": "[i\u00ee\u00ef]", "c": "[c\u00e7]"}
_ACC_BASE = str.maketrans("\u00e9\u00e8\u00ea\u00eb\u00e0\u00e2\u00f4\u00f9\u00fb\u00ee\u00ef\u00e7", "eeeeaaouuiic")


def _loose(name):
    """'Hache-tripes' -> motif qui accepte 'hache tripe', 'hachetripes', 'Hache-Tripes'..."""
    words = re.split(r"[\s\-]+", name.lower().translate(_ACC_BASE))
    out = []
    for w in words:
        w = w[:-1] if len(w) > 3 and w.endswith("s") else w
        out.append("".join(_ACC.get(ch, re.escape(ch)) for ch in w) + ("s?" if len(w) > 2 else ""))
    return r"[\s\-]*".join(out)


def _out_key(w):
    """Retrouve le nom francais de la table a partir de ce que tu as tape."""
    k = re.sub(r"[\s\-]+", " ", w.lower().translate(_ACC_BASE))
    for fr in OUT_PLACES:
        if re.fullmatch(_loose(fr), w, re.I):
            return fr
    return None


_OUT_RE = re.compile(r"(?<![\w'])(" + "|".join(_loose(n) for n in sorted(list(OUT_PLACES) + OUT_JARGON, key=len, reverse=True))
                     + r")(?![\w'])", re.I)


LANGUAGETOOL_URL = "https://api.languagetool.org/v2/check"

# Fautes "au son" frequentes que le correcteur en ligne ne retrouve pas bien (mot trop loin du vrai).
# Seulement des mots SANS ambiguite : "sa" -> "ca" n'y est pas ("sa quete" est juste).
PHONETIC_FR = {
    # mots de tous les jours
    "ojourdui": "aujourd'hui", "ojourd'hui": "aujourd'hui", "aujourdui": "aujourd'hui", "ajourdui": "aujourd'hui",
    "aujourdhui": "aujourd'hui", "aujourd hui": "aujourd'hui",
    "kel": "quel", "kelle": "quelle", "kels": "quels", "kelles": "quelles", "ke": "que", "ki": "qui",
    "koi": "quoi", "keske": "qu'est-ce que", "kesk": "qu'est-ce que", "kesque": "qu'est-ce que",
    "kan": "quand", "koman": "comment", "coman": "comment", "coment": "comment", "pourkoi": "pourquoi",
    "pourquoit": "pourquoi", "conbien": "combien", "kombien": "combien",
    "quelqun": "quelqu'un", "kelkun": "quelqu'un", "quelquun": "quelqu'un", "quelquechose": "quelque chose",
    "kelke chose": "quelque chose",
    "jsui": "je suis", "jsuis": "je suis", "chui": "je suis", "chuis": "je suis", "jesui": "je suis",
    "jvais": "je vais", "jveux": "je veux", "jpeux": "je peux", "jsais": "je sais",
    "chépa": "je sais pas", "chepa": "je sais pas", "chaipa": "je sais pas", "chaipas": "je sais pas",
    "bocou": "beaucoup", "boucou": "beaucoup", "bocoup": "beaucoup", "beaucou": "beaucoup", "beaucoups": "beaucoup",
    "tanpi": "tant pis", "tempi": "tant pis", "sava": "\u00e7a va", "sa va": "\u00e7a va",
    "sa vas": "\u00e7a va", "\u00e7a vas": "\u00e7a va", "ca vas": "\u00e7a va", "dormie": "dormi",
    # "sa" devant un pronom ou "fait" ne peut pas etre "sa" (sa quete) : c'est "ca"
    "sa me": "\u00e7a me", "sa te": "\u00e7a te", "sa nous": "\u00e7a nous", "sa vous": "\u00e7a vous",
    "sa fait": "\u00e7a fait", "sai": "sais", "apel": "appelle", "apelle": "appelle", "apeler": "appeler",
    # verbe apres "tu" / "je" : jamais "peu" (tu peux), "appel moi" -> "appelle-moi" (exemples reels)
    "tu peu": "tu peux", "je peu": "je peux", "peuc": "peux", "des que": "d\u00e8s que",
    "tu va": "tu vas", "pigpompe": "ping-pong", "pingpong": "ping-pong", "pinpong": "ping-pong",
    "aux ping-pong": "au ping-pong", "aux ping pong": "au ping-pong",
    "je les depuis": "je les ai depuis", "depuis de moi": "depuis un mois", "depuis de mois": "depuis un mois",
    "apel mois": "appelle-moi", "apel moi": "appelle-moi", "apelle mois": "appelle-moi", "apelle moi": "appelle-moi",
    "appel mois": "appelle-moi", "appel moi": "appelle-moi", "appelle mois": "appelle-moi", "appelle moi": "appelle-moi",
    "mintenan": "maintenant", "maintenan": "maintenant", "maintenent": "maintenant", "mintenant": "maintenant",
    "dacor": "d'accord", "dacord": "d'accord", "daccord": "d'accord",
    "vraimen": "vraiment", "vrément": "vraiment", "vrèment": "vraiment",
    "parske": "parce que", "parsk": "parce que", "parceque": "parce que", "pasque": "parce que",
    "jamé": "jamais", "jamai": "jamais", "pluto": "plut\u00f4t", "toujour": "toujours", "toujoure": "toujours",
    "peutetre": "peut-\u00eatre", "peut etre": "peut-\u00eatre", "petetre": "peut-\u00eatre",
    "ossi": "aussi", "osi": "aussi", "oci": "aussi", "tro": "trop", "mieu": "mieux", "apré": "apr\u00e8s",
    "deja": "d\u00e9j\u00e0", "déja": "d\u00e9j\u00e0", "labas": "l\u00e0-bas", "bientot": "bient\u00f4t",
    "abientot": "\u00e0 bient\u00f4t", "orevoir": "au revoir", "aurevoir": "au revoir",
    "toutalheure": "tout \u00e0 l'heure", "enfaite": "en fait", "enfète": "en fait", "malgrès": "malgr\u00e9",
    "parmis": "parmi", "lontemps": "longtemps", "longtant": "longtemps", "bezoin": "besoin",
    "escuse": "excuse", "mersi": "merci", "desole": "d\u00e9sol\u00e9",
    # mots du jeu
    "kete": "qu\u00eate", "kète": "qu\u00eate", "kête": "qu\u00eate", "ketes": "qu\u00eates",
    "nivo": "niveau", "nivos": "niveaux", "armur": "armure", "donjont": "donjon",
}
# pas colle a une lettre, une apostrophe ou un tiret : "Ki-Ra" (un nom) reste tel quel
_PHONETIC_RE = re.compile(r"(?<![\w'-])(" + "|".join(sorted(map(re.escape, PHONETIC_FR), key=len, reverse=True))
                          + r")(?![\w'-])", re.I)


def phonetic_fix(text, done=None):
    """Remplace les fautes "au son" de la liste. -> (texte, nombre de remplacements).
    `done` (liste) recoit les mots mis a la place, pour que le correcteur en ligne n'y touche plus."""
    count = [0]

    def sub(m):
        count[0] += 1
        new = PHONETIC_FR[m.group(1).lower()]
        if done is not None:
            done.append(new)
        return new[:1].upper() + new[1:] if m.group(1)[:1].isupper() else new
    text = _PHONETIC_RE.sub(sub, text)
    return _PHONETIC_RE.sub(sub, text), count[0]     # 2e passage : "aux pigpompe" -> "aux ping-pong" -> "au ping-pong"


# Regles du correcteur en ligne qu'on ignore : la majuscule en debut de phrase (dans un tchat, personne
# n'en met, et ca n'aide pas a se faire comprendre).
_LT_SKIP_RULES = ("UPPERCASE_SENTENCE_START",)


def _wow_words():
    """Mots a ne jamais "corriger" : noms des zones, villes et donjons (francais et anglais)."""
    words = set()
    # abreviations de tchat : tapees expres, ce ne sont pas des fautes
    words.update(w.lower() for w in OUT_JARGON)
    words.update(("lol", "mdr", "ptdr", "xd", "gg", "wp", "ty", "thx", "np", "ok", "omg", "jsp", "stp", "svp",
                  "slt", "bcp", "tkt", "dsl", "cc", "bjr", "bsr", "pk", "pq", "mp", "inv", "grp", "pt", "lvl",
                  "up", "rez", "buff", "loot", "quest", "afk", "brb", "re", "wb", "bg", "pvp", "pve", "hs"))
    words.update(FR_SLANG)                 # argot francais (cv, tlm, mtn...) : "cv" devenait "cavé"
    for src in (LEX_PLACES.keys(), LEX_PLACES.values(), OUT_PLACES.keys(), OUT_PLACES.values(), LEX_NAMES):
        for v in src:
            for w in re.split(r"[\s:()]+", str(v).lower()):
                if len(w) > 2:
                    words.add(w)
    return words


_WOW_WORDS = None


def correct_text(text, lang="fr", timeout=8, keep=(), keep_phrases=()):
    """Correction d'orthographe et de grammaire (LanguageTool, gratuit, sans compte ni cle).
    Ne touche pas aux noms propres (mot avec une majuscule : Hurlevent, Ki-Ra), aux noms du jeu (meme
    ecrits en minuscules) ni aux pseudos de `keep`. -> (texte corrige, nombre de corrections)."""
    global _WOW_WORDS
    if _WOW_WORDS is None:
        _WOW_WORDS = _wow_words()
    protect = _WOW_WORDS | {k.lower() for k in keep if k}
    data = urllib.parse.urlencode({"text": text, "language": lang}).encode("utf-8")
    req = urllib.request.Request(LANGUAGETOOL_URL, data=data, headers={"User-Agent": "WoW-Traducteur"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        res = json.loads(r.read().decode("utf-8"))
    # passages deja corriges par la liste "au son" ("ça va") : on n'y touche plus ("ça va je" -> "cavé-je")
    locked = []
    for ph in set(p for p in keep_phrases if p):
        locked += [(x.start(), x.end()) for x in re.finditer(r"(?<!\w)" + re.escape(ph) + r"(?!\w)", text, re.I)]
    fixes = 0
    for m in sorted(res.get("matches", []), key=lambda m: m["offset"], reverse=True):   # de la fin au debut
        reps = m.get("replacements") or []
        if not reps:
            continue
        rule = m.get("rule") or {}
        if rule.get("id") in _LT_SKIP_RULES:
            continue
        a, n = m["offset"], m["length"]
        orig, new = text[a:a + n], reps[0]["value"]
        words = [w.lower() for w in re.findall(r"[\w'-]+", orig)]
        if rule.get("issueType") == "misspelling":
            if any(c.isupper() for c in orig):          # nom propre (Hurlevent, Ki-Ra, un pseudo) : on laisse
                continue
            if new[:1].isupper():                       # "sav" -> "Save" : proposition de nom propre, on laisse
                continue
        if any(w in protect for w in words):            # nom du jeu ou pseudo, meme en minuscules
            continue
        if any(a < e and a + n > b0 for b0, e in locked):   # chevauche un passage garde
            continue
        text = text[:a] + new + text[a + n:]
        fixes += 1
    return text, fixes


def translate_out(text, target, source):
    """Traduit ce que tu ecris, sans abimer le jargon de jeu ni les noms de donjons."""
    found = {}

    def mask(m):
        w = m.group(0)
        key = "Zq%dx" % len(found)
        fr = _out_key(w)
        en = OUT_PLACES.get(fr) if fr else None
        found[key] = OUT_PLACES_LANG.get(target, {}).get(en, en) if en else w
        return key
    masked = _OUT_RE.sub(mask, text) if source == "fr" else text
    out, lang = google_translate(masked, target, source)
    for key, val in found.items():
        out = re.sub(re.escape(key), lambda _m, v=val: v, out, flags=re.I)
    return out, lang


def has_protected_name(text, target="fr"):
    pat = _names_pattern(target)
    return bool(pat) and bool(re.search(pat, text, re.I))


# --------------------------------------------------------------------------
# Pont image : l'addon dessine une bande de cases colorees en haut a gauche de
# l'ecran de WoW (64 x 16 cases de 6 px, 3 bits par case). On la lit par capture d'ecran.
# --------------------------------------------------------------------------
B_COLS, B_ROWS, B_CELL = 64, 16, 6   # 16 lignes depuis ChatFR 1.5 (12 avant : les longs messages etaient coupes)
B_W, B_H = B_COLS * B_CELL, B_ROWS * B_CELL
B_MAGIC = [(1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 1)]
B_SEARCH = 48     # decalage maximal cherche (pixels) : la bande est a ~12 px du coin


def _lvl(v):
    """0..255 -> 0 ou 1. L'ecran deforme les couleurs (rouge pur -> 255,26,66 ; vert -> 0,229,0) :
    deux niveaux seulement, seuil au milieu."""
    return 1 if v >= 128 else 0


def _cell(buf, width, x0, y0):
    sr = sg = sb = 0
    for dy in (0, 1):
        for dx in (0, 1):
            p = ((y0 + dy) * width + x0 + dx) * 4
            sb += buf[p]
            sg += buf[p + 1]
            sr += buf[p + 2]
    return _lvl(sr // 4), _lvl(sg // 4), _lvl(sb // 4)


B_PMIN, B_PMAX = 3.0, 10.0   # taille de case acceptee : jeu etire (resolution perso) ou echelle de rendu reduite


def _cell_at(buf, width, ox, oy, i, p=B_CELL):
    c, r = i % B_COLS, i // B_COLS
    return _cell(buf, width, int(ox + (c + 0.5) * p) - 1, int(oy + (r + 0.5) * p) - 1)


def bridge_magic_ok(buf, width, ox, oy, p=B_CELL):
    return all(_cell_at(buf, width, ox, oy, i, p) == B_MAGIC[i] for i in range(len(B_MAGIC)))


def decode_bridge(buf, width, ox=0, oy=0, p=B_CELL):
    """buf : pixels BGRA. -> (seq, payload) ou None si pas de signal / paquet corrompu.
    p : taille d'une case en pixels (6, ou autre si le jeu est etire a l'ecran)."""
    height = len(buf) // (4 * width)
    if ox < 0 or oy < 0 or int(ox + (B_COLS - 0.5) * p) >= width or int(oy + (B_ROWS - 0.5) * p) >= height:
        return None
    if not bridge_magic_ok(buf, width, ox, oy, p):
        return None
    bits = nbits = 0
    out = bytearray()
    for i in range(len(B_MAGIC), B_COLS * B_ROWS):
        r, g, b = _cell_at(buf, width, ox, oy, i, p)
        bits = (bits << 3) | (r << 2) | (g << 1) | b
        nbits += 3
        while nbits >= 8:
            nbits -= 8
            out.append((bits >> nbits) & 0xFF)
        bits &= (1 << nbits) - 1
    seq = out[0]
    n = (out[1] << 8) | out[2]
    crc = (out[3] << 8) | out[4]
    if n > len(out) - 5:
        return None
    payload = bytes(out[5:5 + n])
    if binascii.crc_hqx(payload, 0) != crc:
        return None
    return seq, payload


def find_bridge_offset(buf, width, height, maxd=None):
    """Cherche la bande (cases de 6 px) ; renvoie le decalage qui vise le CENTRE des cases (milieu
    de la plage de decalages qui reconnaissent la bande), plus sur face au flou des bords."""
    ymax, xmax = height - B_H, width - B_W
    if maxd is not None:
        ymax, xmax = min(ymax, maxd), min(xmax, maxd)
    for dy in range(0, ymax + 1):
        for dx in range(0, xmax + 1):
            if bridge_magic_ok(buf, width, dx, dy):
                dx2 = dx
                while dx2 + 1 <= xmax and bridge_magic_ok(buf, width, dx2 + 1, dy):
                    dx2 += 1
                mx = (dx + dx2) // 2
                dy2 = dy
                while dy2 + 1 <= ymax and bridge_magic_ok(buf, width, mx, dy2 + 1):
                    dy2 += 1
                return mx, (dy + dy2) // 2
    return None


def _cls(buf, width, x, y):
    """Couleur d'un pixel en 3 bits (rouge, vert, bleu allume ou non)."""
    q = (y * width + x) * 4
    return (4 if buf[q + 2] >= 128 else 0) | (2 if buf[q + 1] >= 128 else 0) | (1 if buf[q] >= 128 else 0)


def _magic_coarse(buf, width, height):
    """Repere a l'oeil les 4 cases rouge, vert, bleu, blanc, quelle que soit leur taille.
    -> (x, y, p) : bord gauche et haut de la case rouge, taille approchee d'une case."""
    want = (4, 2, 1, 7)
    for y in range(height):
        runs, prev, start = [], None, 0
        for x in range(width):
            k = _cls(buf, width, x, y)
            if k != prev:
                if prev is not None:
                    runs.append((prev, start, x - start))
                prev, start = k, x
        runs.append((prev, start, width - start))
        for i, (k, s, n) in enumerate(runs):
            if k != 4 or not 2 <= n <= B_PMAX + 3:
                continue
            found, j = [(k, s, n)], i + 1
            while len(found) < 4 and j < len(runs):
                k2, s2, n2 = runs[j]
                if k2 == want[len(found)] and n2 >= 2:
                    found.append(runs[j])
                elif n2 > 2:              # plus qu'un pixel de flou entre deux cases : rate
                    break
                j += 1
            if len(found) < 4:
                continue
            p = (found[3][1] - s) / 3.0
            if not B_PMIN <= p <= B_PMAX or any(abs(f[2] - p) > max(2.0, 0.35 * p) for f in found[:3]):
                continue
            xc, top = s + n // 2, y
            while top > 0 and _cls(buf, width, xc, top - 1) == 4:
                top -= 1
            return s, top, p
    return None


def _fit_grid(buf, width, height, x0, y0, p0):
    """Affine la taille des cases et la position de la grille avec tous les bords entre cases
    (un decalage de 0,4 px par case fait 25 px au bout d'une ligne : il faut etre precis)."""
    xs, ys = [], []
    xe = min(width, int(x0 + B_COLS * p0 * 0.97))
    ye = min(height, int(y0 + B_ROWS * p0 * 0.97))
    for r in range(B_ROWS):
        y = int(y0 + (r + 0.5) * p0)
        if y >= ye:
            break
        prev = _cls(buf, width, int(x0), y)
        for x in range(int(x0) + 1, xe):
            k = _cls(buf, width, x, y)
            if k != prev:
                xs.append(x)
                prev = k
    for c in range(B_COLS):
        x = int(x0 + (c + 0.5) * p0)
        if x >= xe:
            break
        prev = _cls(buf, width, x, int(y0))
        for y in range(int(y0) + 1, ye):
            k = _cls(buf, width, x, y)
            if k != prev:
                ys.append(y)
                prev = k
    if len(xs) < 12:
        return x0, y0, p0
    xs, ys = xs[:1500], ys[:1500]
    best = None
    p = p0 - 0.6
    while p <= p0 + 0.6:
        w = 2 * math.pi / p
        cx = sum(math.cos(w * v) for v in xs)
        sx = sum(math.sin(w * v) for v in xs)
        cy = sum(math.cos(w * v) for v in ys)
        sy = sum(math.sin(w * v) for v in ys)
        score = cx * cx + sx * sx + cy * cy + sy * sy
        if best is None or score > best[0]:
            best = (score, p, cx, sx, cy, sy)
        p += 0.004
    _, p, cx, sx, cy, sy = best
    fx = (math.atan2(sx, cx) / (2 * math.pi) * p) % p
    ox = fx + p * round((x0 - fx) / p)
    oy = y0
    if ys:
        fy = (math.atan2(sy, cy) / (2 * math.pi) * p) % p
        oy = fy + p * round((y0 - fy) / p)
    return ox, oy, p


def locate_bridge(buf, width, height):
    """-> (ox, oy, p) : coin de la bande et taille d'une case en pixels, ou None si pas de bande.
    D'abord les cases normales de 6 px ; sinon (jeu etire a l'ecran) on mesure leur vraie taille."""
    off = find_bridge_offset(buf, width, height, B_SEARCH)
    if off and decode_bridge(buf, width, off[0], off[1]) is not None:
        return off[0], off[1], float(B_CELL)
    c = _magic_coarse(buf, width, height)
    if c is None:
        return (off[0], off[1], float(B_CELL)) if off else None
    ox, oy, p = _fit_grid(buf, width, height, *c)
    for dp in (0.0, -0.01, 0.01, -0.02, 0.02, -0.04, 0.04):
        for dx in (0.0, -0.5, 0.5, -1.0, 1.0):
            for dy in (0.0, -0.5, 0.5, -1.0, 1.0):
                if decode_bridge(buf, width, ox + dx, oy + dy, p + dp) is not None:
                    return ox + dx, oy + dy, p + dp
    if off:
        return off[0], off[1], float(B_CELL)
    return ox, oy, p


# Couleur de classe des joueurs, envoyee par ChatFR ("say#C69B6D") : pseudo -> "#c69b6d"
NAME_COLS = {}
OWN_NAMES = set()      # tes propres pseudos (messages "Vous") : le correcteur ne les touche pas


def parse_bridge_record(payload):
    """payload = 'kind\\x1fcanal\\x1fauteur\\x1ftexte' -> tuple comme parse()."""
    try:
        kind, chan, author, text = payload.decode("utf-8", "replace").split("\x1f", 3)
    except ValueError:
        return None
    if kind == "tip":                    # infobulle d'objet : lignes dans le champ canal, nom en auteur
        return time.strftime("%H:%M"), "tip", chan, author, ""
    if kind == "geo":                    # place du tchat de WoW (ChatFR 1.9.4) : "x,y,l,h,hauteur du jeu"
        return time.strftime("%H:%M"), "geo", chan, "", ""
    if kind == "ui":                     # menu du jeu ouvert ("1") ou ferme ("0") (ChatFR 1.9.4)
        return time.strftime("%H:%M"), "ui", chan, "", ""
    if kind == "ver":                    # version de ChatFR (ChatFR 1.9.6)
        return time.strftime("%H:%M"), "ver", chan, "", ""
    if not text.strip():
        return None
    kind, _sep, ncol = kind.partition("#")
    if ncol and re.fullmatch(r"[0-9A-Fa-f]{6}", ncol) and author.strip():
        NAME_COLS[clean_name(author)] = "#" + ncol.lower()
    low = chan.lower()
    if kind == "channel" and ("looking" in low or "recherche" in low or "suche" in low):
        kind = "lfg"
    return time.strftime("%H:%M"), kind, chan, clean_name(author), text


def color_name_in(spans, author, ctag):
    """Premiere apparition du pseudo dans le texte (hors liens) -> morceau avec la couleur de classe."""
    out, done = [], False
    for seg, code in spans:
        i = -1 if (done or code) else seg.find(author)
        if i < 0:
            out.append((seg, code))
            continue
        if seg[:i]:
            out.append((seg[:i], code))
        out.append((author, ctag))
        if seg[i + len(author):]:
            out.append((seg[i + len(author):], code))
        done = True
    return out


_gdi_ready = False


def _gdi_setup():
    global _gdi_ready
    if _gdi_ready:
        return
    from ctypes import c_void_p, c_int, c_uint
    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    u.GetDC.restype = c_void_p
    u.GetDC.argtypes = [c_void_p]
    u.ReleaseDC.argtypes = [c_void_p, c_void_p]
    u.FindWindowW.restype = c_void_p
    u.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
    u.ClientToScreen.argtypes = [c_void_p, ctypes.POINTER(wintypes.POINT)]
    g.CreateCompatibleDC.restype = c_void_p
    g.CreateCompatibleDC.argtypes = [c_void_p]
    g.CreateCompatibleBitmap.restype = c_void_p
    g.CreateCompatibleBitmap.argtypes = [c_void_p, c_int, c_int]
    g.SelectObject.restype = c_void_p
    g.SelectObject.argtypes = [c_void_p, c_void_p]
    g.BitBlt.argtypes = [c_void_p, c_int, c_int, c_int, c_int, c_void_p, c_int, c_int, wintypes.DWORD]
    g.GetDIBits.argtypes = [c_void_p, c_void_p, c_uint, c_uint, c_void_p, c_void_p, c_uint]
    g.DeleteObject.argtypes = [c_void_p]
    g.DeleteDC.argtypes = [c_void_p]
    _gdi_ready = True


class _BMI(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD),
                ("colors", wintypes.DWORD * 3)]


def grab(x, y, w, h):
    """Capture l'ecran (x, y, w, h en pixels) -> octets BGRA, haut en bas."""
    _gdi_setup()
    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    hdc = u.GetDC(None)
    mdc = g.CreateCompatibleDC(hdc)
    bmp = g.CreateCompatibleBitmap(hdc, w, h)
    old = g.SelectObject(mdc, bmp)
    try:
        g.BitBlt(mdc, 0, 0, w, h, hdc, x, y, 0x00CC0020)      # SRCCOPY
        bmi = _BMI()
        bmi.biSize = 40
        bmi.biWidth, bmi.biHeight = w, -h                       # hauteur negative : haut en bas
        bmi.biPlanes, bmi.biBitCount, bmi.biCompression = 1, 32, 0
        buf = ctypes.create_string_buffer(w * h * 4)
        g.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bmi), 0)
        return buf.raw
    finally:
        g.SelectObject(mdc, old)
        g.DeleteObject(bmp)
        g.DeleteDC(mdc)
        u.ReleaseDC(None, hdc)


def wow_client_origin():
    """Coin haut-gauche (en pixels ecran) de la zone de jeu de WoW, ou None."""
    _gdi_setup()
    u = ctypes.windll.user32
    hwnd = u.FindWindowW("GxWindowClass", None) or u.FindWindowW(None, "World of Warcraft")
    if not hwnd:
        return None
    pt = wintypes.POINT(0, 0)
    if not u.ClientToScreen(hwnd, ctypes.byref(pt)) or pt.x < -10000:
        return None
    return pt.x, pt.y


def wow_or_me_in_front():
    """True si la fenetre au premier plan est WoW ou le traducteur (pour montrer le cache-bande)."""
    try:
        u = ctypes.windll.user32
        fg = u.GetForegroundWindow()
        if not fg:
            return False
        if fg == (u.FindWindowW("GxWindowClass", None) or u.FindWindowW(None, "World of Warcraft")):
            return True
        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(fg, ctypes.byref(pid))
        return pid.value == os.getpid()
    except Exception:  # noqa
        return True


def wow_client_height():
    """Hauteur (pixels ecran) de la zone de jeu de WoW, ou None."""
    _gdi_setup()
    u = ctypes.windll.user32
    hwnd = u.FindWindowW("GxWindowClass", None) or u.FindWindowW(None, "World of Warcraft")
    if not hwnd:
        return None
    rc = wintypes.RECT()
    u.GetClientRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.RECT)]
    if not u.GetClientRect(hwnd, ctypes.byref(rc)):
        return None
    return rc.bottom - rc.top


def save_bmp(path, bgra, w, h):
    """Enregistre une capture BGRA (haut en bas) en .bmp (aucune dependance)."""
    hdr = b"BM" + (54 + w * h * 4).to_bytes(4, "little") + b"\0\0\0\0" + (54).to_bytes(4, "little")
    dib = (40).to_bytes(4, "little") + w.to_bytes(4, "little") + (-h).to_bytes(4, "little", signed=True) \
        + (1).to_bytes(2, "little") + (32).to_bytes(2, "little") + b"\0" * 24
    with open(path, "wb") as f:
        f.write(hdr + dib + bgra)


def capture_stats(buf):
    """-> (part de pixels non noirs en %, couleur moyenne R,V,B)"""
    n = len(buf) // 4
    if not n:
        return 0, (0, 0, 0)
    step = 4 * max(1, n // 4000)
    cnt = tot = sr = sg = sb = 0
    for p in range(0, len(buf) - 3, step):
        b_, g_, r_ = buf[p], buf[p + 1], buf[p + 2]
        tot += 1
        sr += r_
        sg += g_
        sb += b_
        if r_ + g_ + b_ > 24:
            cnt += 1
    return 100 * cnt // max(1, tot), (sr // tot, sg // tot, sb // tot)


def wow_window_exists():
    """True si la fenetre de WoW existe (meme reduite). None si on ne peut pas savoir."""
    if os.name != "nt":
        return None
    try:
        _gdi_setup()
        u = ctypes.windll.user32
        return bool(u.FindWindowW("GxWindowClass", None) or u.FindWindowW(None, "World of Warcraft"))
    except Exception:  # noqa
        return None


def wow_in_front():
    """True si WoW (ou le traducteur lui-meme) est la fenetre active, False si c'est une autre
    application (WoW reduit, Alt+Tab, touche Windows...), None si WoW est introuvable."""
    if os.name != "nt":
        return None
    try:
        _gdi_setup()
        u = ctypes.windll.user32
        wow = u.FindWindowW("GxWindowClass", None) or u.FindWindowW(None, "World of Warcraft")
        if not wow:
            return None
        u.GetForegroundWindow.restype = ctypes.c_void_p
        u.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)]
        u.IsIconic.argtypes = [ctypes.c_void_p]
        if u.IsIconic(wow):
            return False
        fg = u.GetForegroundWindow()
        if not fg:
            return None                      # pas de fenetre active (verrouillage...) : ne rien changer
        pid_fg, pid_wow = wintypes.DWORD(), wintypes.DWORD()
        u.GetWindowThreadProcessId(fg, ctypes.byref(pid_fg))
        u.GetWindowThreadProcessId(wow, ctypes.byref(pid_wow))
        return pid_fg.value in (pid_wow.value, os.getpid())
    except Exception:  # noqa
        return None


def wow_running():
    """True si un processus WoW (wow*.exe) tourne. None si on ne peut pas savoir."""
    if os.name != "nt":
        return None
    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                             timeout=10, creationflags=0x08000000).stdout
    except Exception:  # noqa
        return None
    for line in out.splitlines():
        name = line.split('","')[0].strip('"').lower()
        if name.startswith("wow") and name.endswith(".exe") and "wowup" not in name:
            return True
    return False


PLAUSIBLE_LANGS = {"en", "fr", "de", "es", "pt", "it", "ru", "pl", "nl"}
FR_WORDS = set("le les une des du et est pas que qui pour avec dans sur je tu il elle nous vous ils "
               "ca mon mes ton tes oui non merci salut bonjour bonsoir cherche groupe donjon quelqu "
               "aller faire veux peux besoin ici sont suis ont mais donc".split())


def looks_french(text):
    t = text.lower()
    if re.search(r"[\u00e0\u00e2\u00e7\u00e8\u00e9\u00ea\u00eb\u00ee\u00ef\u00f4\u00f9\u00fb\u0153]", t):
        return True
    words = re.findall(r"[a-z']+", t)
    hits = sum(1 for w in words if w.split("'")[0] in FR_WORDS or "'" in w and w.split("'")[0] in ("l", "d", "j", "qu", "c", "n", "s", "m", "t"))
    return hits >= 2 or (len(words) <= 3 and hits >= 1)


# Pour ne pas interroger Google sur les messages deja en francais (moins de requetes = moins de 429).
# Mots surement francais (pas de mots partages avec l'anglais, l'espagnol ou l'italien comme "la", "de", "a").
SURE_FR = set("je j tu il elle nous vous ils elles est suis sont es ai as avons avez ont et ou mais donc "
              "le les un une des du au aux ce cet cette ces mon ma mes ton ta tes son sa ses notre votre leur "
              "pour avec dans sur sous chez pas ne plus rien jamais qui quoi quel quelle quels quand comment "
              "pourquoi combien ou oui ouais merci salut bonjour bonsoir svp stp cherche cherchons recrute "
              "vend vends achete achète groupe guilde donjon quelqu quelqu'un personne besoin veux veut peux "
              "peut faut faire avoir etre être connait connais sais quelqun qqn aller viens venir ici ça ca c qu d l m n s t y bien très tres trop aussi encore "
              "deja déjà alors voila voilà fait mort mdr ptdr bonne bon nuit dispo dispos "
              # argot de salut : seul, Google le traduisait mal ("slt" -> "salope", "lut" -> "lutin")
              "slt lut bjr bsr bjour tlm kikou coucou cv mrc mci merki dr bvn bienvenue dsl jsp jpp chepa osef tkt tqt "
              "bcp pcq psk pq pkoi koi kwa keske kestu qd qqch qqun qq1 rdv mtn auj ajd dmn tjr tjrs ptet ptetre "
              "jvais jvien jviens jreviens jarrive jsuis chui chuis jte jpense dac dacc ouep ouai frr frero "
              "bsx biz bisous bn aplus bonap trkl tranquille ptn wesh wsh tg fdp ntm xptdr pex pexe pexer "
              "donj donjs grp".split())
# Mots d'une autre langue : s'il y en a un, on laisse Google decider (message mixte ou etranger).
NOT_FR = set("the an is are was be been i you he she we they it my your his her our their this that "
             "these those and or but to of in at for with from by as if so not no yes any some anyone "
             "someone need needs looking want wants sell selling buy buying have has can could would will "
             "do does please pls plz thanks thx ty hi hello hey what where when who why how there here "
             "last first just all only lf lfm lfg wts wtb el los las para por hay alguien busco necesito "
             "gracias hola ich und der die das nicht ist wer sucht bitte danke per che sono cerco gilda "
             "ciao grazie voce você não obrigado".split())
_FOREIGN_CHARS = re.compile("[\u00f1\u00e3\u00f5\u00df\u00e4\u00f6\u00fc\u00e1\u00ed\u00f3\u00fa\u0105\u0119\u0142\u017c\u017a\u015b\u0107\u0144]")
_FR_ACCENTS = re.compile("[\u00e0\u00e2\u00e7\u00e8\u00e9\u00ea\u00eb\u00ee\u00ef\u00f4\u00f9\u00fb\u0153]")


# Smileys (":D", ";p", "xD"...) : le "d" de ":D" etait compte comme le "d'" francais, et
# "wow cheers :D" etait pris pour du francais (donc pas traduit).
_SMILEY = re.compile(r"(?<!\w)(?:[:;=8][-'^o]?[dDpPoO)(\]\[/\\|*3sS]+|[xX][dDpP]+)(?!\w)")


FR_AMBIG = set("bien es tu un son y ma mais ou ai ne ca c d l m n s t".split())


def sure_french(text):
    """True seulement si le message est clairement en francais (sans mot etranger)."""
    t = _SMILEY.sub(" ", text).lower()
    if not is_latin_text(t) or _FOREIGN_CHARS.search(t):
        return False
    words = [w.strip("'") for w in re.findall("[a-z\u00e0-\u00ff\u0153']+", t)]
    parts = []
    for w in words:
        parts.extend(p for p in w.split("'") if p)      # j'ai -> j, ai
    if not parts or any(p in NOT_FR for p in parts):
        return False
    hits = sum(1 for p in parts if p in SURE_FR)
    # mots aussi espagnols / italiens / portugais ("comiste bien" est de l'espagnol) : il faut au moins
    # un mot vraiment francais pour se passer de Google
    strong = sum(1 for p in parts if p in SURE_FR and p not in FR_AMBIG)
    if not strong:
        return False
    return hits >= 2 or (hits >= 1 and (len(parts) <= 3 or bool(_FR_ACCENTS.search(t))))


def is_latin_text(text):
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and all(ord(c) < 0x250 for c in letters)


EN_ONLY = set("the is are was were been you he she we they my your his her our their this that these those "
              "and but to of with from by if not yes any some anyone someone need needs looking want wants "
              "sell selling buy buying have has can could would will do does please pls plz thanks thx ty "
              "hi hello hey what where when who why how there here last first just only lf lfm lfg wts wtb "
              "lol im i'm it's don't can't ok okay guys group dungeon quest a i it in on at for me go get got "
              "new now good well did doing done eat guild players player tank heal healer dps run inv cheap "
              "pst whisper come help kill boss".split())


def sure_english(text):
    """True si le message est clairement en anglais (pour ne pas payer un appel a Google en mode anglais)."""
    t = _SMILEY.sub(" ", text).lower()
    if not is_latin_text(t) or _FOREIGN_CHARS.search(t) or _FR_ACCENTS.search(t):
        return False
    words = re.findall("[a-z']+", t)
    if not words or any(w in SURE_FR and w not in FR_AMBIG and w not in EN_ONLY for w in words):
        return False
    hits = sum(1 for w in words if w in EN_ONLY)
    return hits >= 2 and hits * 3 >= len(words)


def near_same(a, b):
    """Meme texte a la ponctuation / une lettre pres ("Welp, pack it up boys" -> "Well, pack it up, boys.")."""
    a, b = re.sub(r"\W+", "", a).lower(), re.sub(r"\W+", "", b).lower()
    if a == b:
        return True
    return len(b) >= 12 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.9


def unreliable_detection(text, lang):
    """Google devine n'importe quelle langue sur 2-3 mots (ex. 'alor andans?' -> islandais)."""
    return (len(text) < 30 and is_latin_text(text)
            and (lang or "").lower().split("-")[0] not in PLAUSIBLE_LANGS)


# --------------------------------------------------------------------------
# Petit lexique de joueur (utilise seulement quand la langue cible est le francais)
# --------------------------------------------------------------------------
# 1) Messages ENTIERS courts traduits directement, sans Google (evite "who" -> "OMS").
#    Ajoute tes propres entrees ici : "message en minuscules": "traduction".
LEX_FULL = {
    "who": "qui", "who me": "qui, moi", "me": "moi", "where": "où", "when": "quand",
    "why": "pourquoi", "what": "quoi", "how": "comment", "how much": "combien",
    "yes": "oui", "yep": "ouais", "yeah": "ouais", "ya": "ouais", "yup": "ouais",
    "no": "non", "nope": "non", "nah": "non", "ok": "ok", "okay": "ok", "k": "ok", "kk": "ok",
    "sure": "bien sûr", "maybe": "peut-être", "idk": "je ne sais pas", "dunno": "je ne sais pas",
    "ty": "merci", "thx": "merci", "thanks": "merci", "tyvm": "merci beaucoup",
    "thank you": "merci", "ty all": "merci à tous", "thanks all": "merci à tous",
    "np": "pas de souci", "no problem": "pas de souci", "yw": "de rien", "you're welcome": "de rien",
    "hi": "salut", "hello": "bonjour", "hey": "salut", "hi all": "salut tout le monde",
    "hello all": "bonjour à tous", "hey all": "salut tout le monde", "sup": "quoi de neuf",
    "bye": "au revoir", "cya": "à plus", "see ya": "à plus", "gn": "bonne nuit", "good night": "bonne nuit",
    "gm": "bonjour", "good morning": "bonjour",
    "gg": "bien joué", "gg wp": "bien joué", "gj": "bien joué", "wp": "bien joué", "ggwp": "bien joué",
    "gz": "félicitations", "grats": "félicitations", "gratz": "félicitations", "congrats": "félicitations",
    "lol": "mdr", "lmao": "mdr", "lmfao": "mdr", "rofl": "mdr", "haha": "haha", "xd": "xD",
    "brb": "je reviens", "afk": "absent (AFK)", "back": "de retour", "re": "re",   # dit aussi en francais : pas de traduction
    "un": "un",                             # seul, c'est du francais ("un" -> "ONU" par Google)
    "yo": "yo",                             # salut familier, dit pareil en francais : pas de "-> salut"
    "omw": "j'arrive", "otw": "j'arrive", "coming": "j'arrive", "wait": "attends", "sec": "une seconde",
    "1 sec": "une seconde", "1 min": "une minute", "ready": "prêt", "rdy": "prêt", "r": "prêt",
    "go": "on y va", "lets go": "allez, on y va", "let's go": "allez, on y va",
    "inv": "invite-moi", "inv pls": "invite-moi stp", "inv plz": "invite-moi stp", "invite": "invite-moi",
    "inv me": "invite-moi", "pls inv": "invite-moi stp", "plz inv": "invite-moi stp",
    "lfg": "cherche groupe", "lfm": "cherche du monde", "lfr": "cherche un raid", "lf1m": "cherche 1 joueur",
    "lf2m": "cherche 2 joueurs", "lf3m": "cherche 3 joueurs", "lf tank": "cherche un tank",
    "lf heal": "cherche un soigneur", "lf healer": "cherche un soigneur", "lf dps": "cherche des DPS",
    "wts": "je vends", "wtb": "j'achète", "wtt": "j'échange", "pst": "écris-moi en privé",
    "pm me": "écris-moi en privé", "dm me": "écris-moi en privé", "w me": "chuchote-moi",
    "sry": "désolé", "sorry": "désolé", "my bad": "ma faute", "mb": "ma faute", "oops": "oups",
    "oom": "plus de mana", "pull": "j'engage", "pulling": "j'engage", "wipe": "on est tous morts",
    "rez": "ressuscite-moi", "rez pls": "ressuscite-moi stp", "res pls": "ressuscite-moi stp",
    "buff": "un buff", "buff pls": "un buff stp", "water": "de l'eau", "water pls": "de l'eau stp",
    "nice": "sympa", "cool": "cool", "wow": "waouh", "omg": "oh mon dieu", "wtf": "c'est quoi ce délire",
    "ez": "facile", "rip": "paix à son âme (RIP)", "same": "pareil", "me too": "moi aussi",
    "agreed": "d'accord", "true": "c'est vrai", "fr": "sérieux", "ikr": "je sais, hein",
    "please": "s'il te plaît", "pls": "stp", "plz": "stp", "help": "à l'aide", "help pls": "aide-moi stp",
    "anyone": "quelqu'un ?", "any1": "quelqu'un ?", "where are you": "où es-tu", "where r u": "où es-tu",
    # groupe ("pt ?" etait traduit "pd ?" par Google)
    "pt": "on se groupe", "party": "on se groupe", "grp": "on se groupe", "group": "on se groupe",
    "inv pt": "invite-moi dans le groupe", "join": "tu rejoins", "tank": "un tank", "heal": "un soigneur",
    "healer": "un soigneur", "dps": "des DPS", "duo": "on se met en duo", "full": "groupe complet",
    "los": "ligne de vue (los)",
}

# 2) Abreviations remplacees par l'anglais complet AVANT Google (le reste de la phrase
#    passe toujours par Google, qui la comprend mieux).
LEX_EXPAND = {
    "u": "you", "r": "are", "ur": "your", "bvn": "welcome",   # "Hello bvn" (bvn = bienvenue)
    "ty": "thank you", "thx": "thanks",
    "tyvm": "thank you very much", "pls": "please", "plz": "please", "ppl": "people",
    "lfg": "looking for group", "lfm": "looking for more", "lfr": "looking for raid", "lf": "looking for",
    "wts": "want to sell", "wtb": "want to buy", "wtt": "want to trade", "cod": "cash on delivery", "ea": "each",
    "idk": "I don't know", "imo": "in my opinion", "btw": "by the way", "tbh": "to be honest",
    "brb": "be right back", "afk": "away from keyboard", "omw": "on my way",
    "np": "no problem", "sry": "sorry", "thru": "through", "cuz": "because", "bc": "because",
    "w/": "with", "w/o": "without", "rn": "right now", "atm": "at the moment", "nvm": "never mind",
    "dunno": "don't know", "gonna": "going to", "wanna": "want to", "gotta": "have to",
    "im": "I'm", "dont": "don't", "cant": "can't", "wont": "won't", "didnt": "didn't",
    "inv": "invite", "dmg": "damage", "lvl": "level", "lvling": "leveling", "dungeon": "dungeon",
    "dps": "DPS", "oom": "out of mana", "gz": "congratulations", "gj": "good job", "wp": "well played",
    "whisp": "whisper", "wisp": "whisper", "whis": "whisper", "pst": "whisper me",
    "pt": "group", "grp": "group",
    "any1": "anyone", "some1": "someone", "every1": "everyone",
    "mats": "materials", "mat": "material",
    "lfw": "looking for work", "wep": "weapon", "weap": "weapon",   # "Enchanter in SW LFW. Got FIERY WEP."
    "los": "line of sight",          # seulement pour l'anglais (en espagnol, "los" = "les")
}

# Expressions entieres (regex, remplacement) appliquees avant les mots seuls : "LFM Hogger" ne doit pas
# devenir "cherche plus de Hogger", ni "whisp for inv" "fouette pour inviter".
LEX_PHRASES = [
    (r"(?<![\w/])w/\s*(?=now\b|for inv)", "whisper "),     # "w/ now for inv" = chuchote-moi, pas "with"
    (r"\blfm(?:\s+for)?\b", "looking for more players for"),
    # "last tank prison rush" en debut de message = il manque un dernier tank (Google : "derniere ruee...")
    (r"(^|\]\s*)last\s+(tank|heal|healer|dps|spot)\b(?!\s+for\b)", r"\1need one last \2 for"),
    # "prison rush" / "stocks run" = la Prison (le donjon), pas une prison : "rush of the stockade"
    (r"\b(?:prison|stockades?|stocks)\s+(rush(?:es)?|runs?|boosts?)\b", r"\1 of the stockade"),
    (r"\blf(\d)m\b", r"looking for \1 more players"),
    # "in IF" en fin de message = a Forgefer (Ironforge) : "lf enchanter ... in if" donnait "... si"
    (r"\bin\s+if\b(?=\s*(?:$|[.!?,;:]|(?:pst|pm|w|whisper|plz|pls|please)\b))", "in Ironforge"),
    # "End" = Endurance (stat) apres "+2" ou colle a "stam" : Google donnait "+2 Fin"
    (r"(\+\s*\d+\s*)(?:end|stam|stamina)(?:\s*/\s*(?:end|stam|stamina))?\b", r"\1stamina"),
    (r"\b(?:end|stam|stamina)\s*/\s*(?:end|stam|stamina)\b", "stamina"),
    (r"\b(?:whisp|wisp|whis|whisper|pst|pm|w/)\s+(?:me\s+)?for\s+(?:an?\s+)?(?:inv|invite|invites)\b",
     "whisper me for an invite"),
    (r"\bfor\s+inv\b", "for an invite"),
    # enchantement demande : "LF enchant gloves riding skill, i have mats" etait traduit
    # "je cherche des competences de conduite avec des gants enchanteurs, j'ai du materiel"
    (r"\b(lf|looking for|wtb|need|want)\s+(?:an?\s+)?(?:enchanter\s+(?:for|to)\s+)?enchant(?:ment)?s?\s+"
     r"(gloves?|boots?|bracers?|chest|cloak|weapon|2h|shield)\b", r"\1 an enchantment on \2"),
    (r"\b(gloves?)\s+(?:\+\s*\d+%?\s*)?riding(?:\s+skill)?\b", r"\1 for mount speed"),
    # "3 more slots" = places libres dans le groupe (pas "creneaux") ; "16 slot bag" reste un sac
    (r"\b(\d+|a|one|two|three|four)\s+(more\s+)?(?:slots?|spots?)\b(?!\s*bags?)", r"\1 \2places in the group"),
    (r"\b(have|got|has|with|bring)\s+(?:own\s+|my\s+|the\s+)?mats\b", r"\1 the materials"),
    # question qui commence par "any" ("any group for SFK?") : Google traduit "tout groupe".
    (r"(^|\]\s*)any\s+(?!(?:one|body|1|more|way|ways|time|how)\b)", r"\1is there any "),
    # "anyone need X" sans point d'interrogation : Google traduisait "tout le monde a besoin de X".
    (r"(^|\]\s*)any(?:one|body|1)\s+(need|want|know|sell)s?\b", r"\1does anyone \2"),
    (r"(^|\]\s*)any(?:one|body|1)\s+(?:have|has|got)\b", r"\1does anyone have"),
    (r"(^|\]\s*)any(?:one|body|1)\s+(selling|going|up|around|online|here)\b", r"\1is anyone \2"),
    (r"(^|\]\s*)any(?:one|body|1)\s+(?:seen|saw)\b", r"\1has anyone seen"),
    (r"(^|\]\s*)any(?:one|body|1)\s+can\b", r"\1can anyone"),
    # "WTB Tiger Meat" : "want to buy" seul donnait "voulez acheter" (sans sujet)
    (r"^\s*wtb\b", "I want to buy"), (r"^\s*wts\b", "I want to sell"), (r"^\s*wtt\b", "I want to trade"),
]

# Prix dans un message de commerce ("2s each", "5g", "50c") : en pieces, pas "2s" laisse tel quel.
# Seulement si le message parle d'achat ou de vente ("1s" peut aussi vouloir dire "1 seconde").
_TRADE_RE = re.compile(r"(?i)\b(?:wts|wtb|wtt|want to (?:buy|sell|trade)|each|ea|per|cod|price|selling|buying)\b")
_PRICE_RE = re.compile(r"(?i)\b(\d+)\s?([gsc])\b")
_PRICE_UNIT = {"g": "gold", "s": "silver", "c": "copper"}
# Metier abrege suivi d'un niveau ("Any BS 215+ ?") -> nom entier ("blacksmith 215+"). Sans chiffre on ne touche
# a rien ("bs" = aussi "n'importe quoi" en anglais).
_PROF_ABBR = {"bs": "blacksmith", "lw": "leatherworker", "alch": "alchemist", "alchy": "alchemist",
              "engi": "engineer", "eng": "engineer", "ench": "enchanter", "tailor": "tailor"}
_PROF_RE = re.compile(r"(?i)\b(%s)(?=\s*\d{2,3}\s*\+?)" % "|".join(sorted(_PROF_ABBR, key=len, reverse=True)))
# "q" en fin de phrase apres un mot = quete ("anyone for the attack q ?") ; ailleurs ("q up") = file d'attente
_Q_END_RE = re.compile(r"(?i)(?<=[a-z\]])\s+q(?=\s*[?!.]*\s*$)")
_LFG_PLACE_RE = re.compile(r"(?i)\b(lfg|lfm)\s+(?=(?:%s)\b)" % "|".join(
    re.escape(k) for k in sorted(LEX_PLACES_EN, key=len, reverse=True)))

# 3) Francais qui contient du jargon anglais ("un last tank et on part") : Google le prend pour de
#    l'anglais et traduit "tank" par "reservoir". Si la phrase contient des mots francais sans
#    ambiguite, on remplace ces expressions par leur forme francaise AVANT l'envoi a Google.
LEX_FR_MIX = [
    (r"\blast\s+(tank|heal|healer|dps)\b", r"dernier \1"),
]
_FR_ONLY_WORDS = set("un une et le les pour des du avec je tu est pas qui dans mon nous vous sur".split())


def fr_mix_fix(text):
    """Francais avec du jargon anglais -> jargon francise (pour Google seulement)."""
    if not (set(re.findall(r"[a-z\u00e0-\u00ff]+", text.lower())) & _FR_ONLY_WORDS):
        return text
    for pat, repl in LEX_FR_MIX:
        text = re.sub(pat, repl, text, flags=re.I)
    return text


_PUNCT_END = re.compile(r"[\s?!.¿¡…:;,~*]+$")
_PUNCT_START = re.compile(r"^[\s?!.¿¡…:;,~*]+")


def _lex_key(text, max_run):
    """minuscules, sans ponctuation au debut / a la fin, lettres repetees ramenees a max_run."""
    t = _PUNCT_START.sub("", _PUNCT_END.sub("", text.strip().lower()))
    t = re.sub(r"\s+", " ", t)
    return re.sub(r"(\w)\1{%d,}" % max_run, r"\1" * max_run, t)


# Jargon WoW ecrit en cyrillique ("ЛФГ ТЮРЬМА" = "LFG Prison") : Google le prend pour des mots russes
RU_SLANG = {"лфг": "LFG", "лфм": "LFM", "втс": "WTS", "втб": "WTB", "гс": "GS", "дд": "DPS", "дпс": "DPS",
            "хил": "heal", "танк": "tank", "тюрьма": "Stockade", "тюрьму": "Stockade", "тюрьмы": "Stockade",
            "дедмайны": "Deadmines", "дм": "DM", "вк": "WC", "сфк": "SFK", "ск": "SM"}
_RU_SLANG_RE = re.compile(r"(?<![\w])(" + "|".join(sorted(RU_SLANG, key=len, reverse=True)) + r")(?![\w])", re.I)


def ru_slang(text):
    if not re.search("[\u0400-\u04ff]", text):
        return text
    return _RU_SLANG_RE.sub(lambda m: RU_SLANG[m.group(1).lower()], text)


# Argot de joueur francais, remis en mots normaux avant Google quand on traduit DEPUIS le francais
# (interface anglaise) : "groupe de pexing" -> "groupe de leveling", "slt tlm" -> "salut tout le monde"
FR_SLANG = {"pex": "leveling", "pexing": "leveling", "pexe": "monte de niveau", "pexer": "monter de niveau",
            "slt": "salut", "cc": "coucou", "bjr": "bonjour", "bsr": "bonsoir", "stp": "s'il te pla\u00eet",
            "svp": "s'il vous pla\u00eet", "qqn": "quelqu'un", "qqun": "quelqu'un", "qq1": "quelqu'un",
            "tlm": "tout le monde", "bcp": "beaucoup", "dsl": "d\u00e9sol\u00e9", "dr": "de rien", "jsp": "je ne sais pas",
            "pb": "probl\u00e8me", "pr": "pour", "mdr": "lol", "ptdr": "lol", "donj": "donjon", "donjs": "donjons",
            "grp": "groupe", "jvais": "je vais", "chui": "je suis", "chuis": "je suis", "tkt": "t'inqui\u00e8te",
            "dispo": "disponible", "dispos": "disponibles",
            "lut": "salut", "bjour": "bonjour", "kikou": "coucou", "cv": "\u00e7a va", "mrc": "merci", "mci": "merci",
            "merki": "merci", "bvn": "bienvenue", "jpp": "j'en peux plus", "chepa": "je ne sais pas",
            "osef": "on s'en fout", "tqt": "t'inqui\u00e8te", "pcq": "parce que", "psk": "parce que",
            "pq": "pourquoi", "pkoi": "pourquoi", "koi": "quoi", "kwa": "quoi", "keske": "qu'est-ce que",
            "kestu": "qu'est-ce que tu", "qd": "quand", "qqch": "quelque chose", "rdv": "rendez-vous",
            "mtn": "maintenant", "auj": "aujourd'hui", "ajd": "aujourd'hui", "dmn": "demain", "tjr": "toujours",
            "tjrs": "toujours", "ptet": "peut-\u00eatre", "ptetre": "peut-\u00eatre", "jvien": "je viens",
            "jviens": "je viens", "jreviens": "je reviens", "jsuis": "je suis", "jte": "je te", "jpense": "je pense",
            "dac": "d'accord", "dacc": "d'accord", "ouep": "ouais", "frr": "fr\u00e8re", "frero": "fr\u00e8re",
            "bsx": "bisous", "biz": "bisous", "bn": "bonne nuit", "aplus": "\u00e0 plus", "bonap": "bon app\u00e9tit",
            "trkl": "tranquille", "xptdr": "lol"}
_FR_SLANG_RE = re.compile(r"(?<![\w'])(" + "|".join(sorted(FR_SLANG, key=len, reverse=True)) + r")(?![\w'])", re.I)


def fr_slang(text):
    # "[Quete] du monde ?" = "qui vient ?" (et pas "of the world")
    text = re.sub(r"(?i)\b(?:y a |il y a )?du monde\s*(?:pour|\?)", lambda m: "quelqu'un pour" if m.group(0).lower().endswith("pour") else "qui vient ?", text)
    if not looks_french(text) and not sure_french(text) and len(_FR_SLANG_RE.findall(text)) < 2:
        return text
    return _FR_SLANG_RE.sub(lambda m: FR_SLANG[m.group(1).lower()], text)


def lexicon_full(text):
    """Traduction directe d'un message entier court, ou None."""
    if len(text) > 40:
        return None
    for run in (2, 1):                      # "yesss" -> "yess" -> "yes" ; "lolll" -> "lol"
        val = LEX_FULL.get(_lex_key(text, run))
        if val is not None:
            if "?" in text and not val.endswith("?"):
                val += " ?"
            return val
    if "/" in text:                         # "lfg/lfm" -> "cherche groupe / cherche du monde"
        parts = [p for p in text.split("/") if p.strip()]
        vals = [lexicon_full(p) for p in parts]
        if len(parts) > 1 and all(vals):
            return " / ".join(vals)
    return None


def lexicon_expand(text):
    """Remplace les abreviations par l'anglais complet (mots entiers seulement)."""
    for pat, repl in LEX_PHRASES:
        text = re.sub(pat, repl, text, flags=re.I)
    # "LFG Stockades" -> "looking for a group for Stockades" ("lfg" seul devant un nom de donjon donnait
    # "je recherche le groupe La Prison", comme si c'etait le nom du groupe)
    text = _LFG_PLACE_RE.sub(lambda m: "looking for a group for " if m.group(1).lower() == "lfg"
                             else "looking for more players for ", text)
    text = _PROF_RE.sub(lambda m: _PROF_ABBR[m.group(1).lower()], text)
    text = _Q_END_RE.sub(lambda m: m.group(0) if re.search(
        r"(?i)\b(?:anyone|anybody|someone|who|u|you|we|i|pls|plz)$", text[:m.start()]) else " quest", text)
    if _TRADE_RE.search(text):
        text = _PRICE_RE.sub(lambda m: "%s %s" % (m.group(1), _PRICE_UNIT[m.group(2).lower()]), text)

    def rep(m):
        w = m.group(0)
        full = LEX_EXPAND.get(w.lower())
        return full if full is not None else w
    return re.sub(r"(?<![\w/])[A-Za-z][A-Za-z0-9']*(?:/o|/)?(?![\w])", rep, text)


# Prix en pieces ("100 po", "2pa 50pc") : jamais traduits (po = "apres" en polonais, etc.).
_COIN_RE = re.compile(r"^(?:\s*\d+(?:[.,]\d+)?\s*k?\s*(?:po|pa|pc)(?![A-Za-z\u00c0-\u024f])[\s,.+&;!?-]*(?:et\s+)?)+$", re.I)


def is_coin_only(text):
    """True si le message ne contient que des montants en po / pa / pc (ex. '100 po')."""
    return bool(_COIN_RE.match(text.strip()))


# Mots de jeu que Google traduit dans leur sens courant. (mot du message, langue du message, remplacements
# dans la traduction). Islandais "gildi" = guilde (pas "valeur") ; "unstuck" = se debloquer (pas "se decoller").
WORD_FIXES = [
    (r"(?i)\bgild", "is", [("valeurs", "guildes"), ("valeur", "guilde"), ("values", "guilds"), ("value", "guild")]),
    (r"(?i)\bunstuck\b", "en", [("d\u00e9coll", "d\u00e9bloqu")]),
    # "salty" (argot de joueur) = vexe, aigri ; Google : "sale" (le gout). Les plus longs d'abord.
    (r"(?i)\bsalty\b", "en", [("sal\u00e9es", "vex\u00e9es"), ("sal\u00e9e", "vex\u00e9e"),
                              ("sal\u00e9s", "vex\u00e9s"), ("sal\u00e9", "vex\u00e9")]),
]


def fix_words(src, trans, lang):
    if not trans:
        return trans
    for pat, lg, pairs in WORD_FIXES:
        if lang != lg or not re.search(pat, src):
            continue
        for a, b in pairs:
            trans = re.sub(r"\b%s" % a, b, trans)
            trans = re.sub(r"\b%s" % a.capitalize(), b.capitalize(), trans)
    return trans


# Petites phrases etrangeres que Google traduit mal quand elles sont seules (souvent sans accents).
# (motif du message entier, langue, {langue cible: traduction})
FOREIGN_FULL = [
    # "dobro dosly" (croate / serbe / bosnien "dobro dosli" = bienvenue) -> Google : "bien joue"
    (r"dobro\s*do[s\u0161]l[iy]", "hr", {"fr": "bienvenue", "en": "welcome"}),
]


def foreign_full(text, target):
    """-> (traduction, langue) si le message entier est une de ces phrases, sinon None."""
    t = re.sub(r"[\s!?.,:;^)(*xXdDpP3<>-]+$", "", text.strip())     # smileys / ponctuation a la fin
    for pat, lang, tr in FOREIGN_FULL:
        if re.fullmatch(pat, t, flags=re.I) and target.lower() in tr:
            return tr[target.lower()], lang
    return None


# Annonces automatiques de Questie ("★ Questie : Foulard en laine rouge : 10/10 pour [La couleur du Sang] !") :
# le lien de quete est deja dans la langue du jeu et les chiffres se lisent seuls -> pas de traduction.
# Annonce de Questie ("{rt1} Questie : ..."). Nom different du motif des liens Questie plus haut :
# en 1.9.5 les deux s'appelaient _QUESTIE_RE, celui-ci remplacait l'autre et chaque annonce de Questie
# faisait planter le traitement des messages (plus rien ne s'affichait ensuite).
_QUESTIE_ANNOUNCE_RE = re.compile(r"^\s*(?:\{[^}]*\}\s*|[\u2605\u25cf\u25c6\u25b2\u263e\u25a0\u2716\u2620]\s*)*Questie\s*:", re.I)


def is_questie(text):
    return bool(_QUESTIE_ANNOUNCE_RE.match(text or ""))


def unknown_abbrev(text):
    """Abreviation inconnue sans voyelle ("lfr", "mm") : Google invente une langue ("lfr" pris pour de
    l'islandais -> "selon"). On l'affiche telle quelle. Les abreviations connues ("brb", "thx") passent."""
    if re.search(r"[^\sA-Za-z0-9?!.,]", text):
        return False
    words = re.findall(r"[A-Za-z]+", text)
    if not words or len(words) > 3:
        return False
    return all(not re.search("[aeiouyAEIOUY]", w) and w.lower() not in LEX_EXPAND and w.lower() not in LEX_FULL
               and w.lower() not in SURE_FR and w.lower() not in FR_SLANG for w in words)


def worth_translating(text):
    letters = re.sub(r"[^A-Za-z\u00c0-\u024f\u0400-\u04ff\u0600-\u06ff\u3040-\u9fff]", "", text)
    return len(letters) >= 2


# --------------------------------------------------------------------------
# Application
# --------------------------------------------------------------------------
class App:
    def __init__(self):
        self.cfg = load_config()
        self.tips = {}                       # infobulles recues de ChatFR : nom (minuscules) -> lignes
        try:
            with open(TIPS_PATH, encoding="utf-8") as f:
                self.tips = {k: v for k, v in json.load(f).items() if isinstance(v, list)}
        except (OSError, ValueError, AttributeError):
            self.tips = {}
        self._tips_dirty = False
        self.T = THEMES.get(str(self.cfg.get("theme", "")), _SOMBRE)
        self.root = tk.Tk()
        # erreur dans un bouton ou une minuterie de la fenetre : notee dans erreurs.txt
        def _tk_err(exc, val, tb):
            try:
                raise val
            except Exception:  # noqa
                log_error("fenetre")
        self.root.report_callback_exception = _tk_err
        self.root.title("WoW Traducteur")
        self.root.configure(bg=self.T["bg"])
        self.root.overrideredirect(True)      # pas de barre de titre Windows : on a la notre
        # coins arrondis de la fenetre : cette couleur (jamais utilisee ailleurs) devient transparente
        try:
            self.root.wm_attributes("-transparentcolor", WIN_HOLE)
        except tk.TclError:          # hors Windows : les coins restent presque noirs
            pass
        geo = str(self.cfg.get("geometry", ""))
        # premier lancement : la fenetre se placera sur le tchat de WoW des que ChatFR en donne la place
        self.geo_auto, self.last_geo = not re.match(r"^\d+x\d+\+-?\d+\+-?\d+$", geo), None
        if not re.match(r"^\d+x\d+\+-?\d+\+-?\d+$", geo):     # en attendant : a peu pres sur le tchat
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            gw, gh = min(540, sw), min(300, sh)                      # en bas a gauche, au-dessus des barres
            geo = "%dx%d+%d+%d" % (gw, gh, int(sw * 0.016), max(0, int(sh * 0.885) - gh))
        self.root.geometry(geo)
        self.root.configure(highlightthickness=self.T["border_w"], highlightbackground=self.T["border"],
                            highlightcolor=self.T["border"])
        self.root.minsize(MIN_W, MIN_H)
        self.inq = queue.Queue()
        self.outq = queue.Queue()
        self.stop = False
        self.nlines = 0
        self.nparsed = 0
        global UI
        if self.cfg.get("ui_lang") not in ("fr", "en"):
            if self.cfg.get("help_seen"):
                # mise a jour depuis une version francaise : on garde le francais sans rien demander
                self.cfg["ui_lang"] = "fr"
                save_config(self.cfg)
            else:
                self.ask_ui_lang()
        UI = self.cfg.get("ui_lang") or "fr"
        self.status = tk.StringVar(value=_("Demarrage..."))
        self.line_lang = {}          # numero de ligne -> langue d'origine
        self.apply_window_cfg()
        self._first_run = not self.cfg.get("help_seen")
        self.build_ui()
        # cliquer sur la fenetre ne prend plus le clavier a WoW (seule la zone "Ecrire" le prend)
        self.root.bind("<FocusOut>", lambda e: self.root.after(80, self._give_back_keyboard), add="+")
        self.root.after(300, lambda: self.set_noactivate(True))
        self.show_welcome()                          # tout en haut, avant les messages
        self.root.after(1500, self.show_news)
        self.root.after(30000, self._svc_tick)       # historique des services : enregistre toutes les 30 s
        if os.environ.get("WOWTRAD_UPDATED"):        # relance juste apres une mise a jour en un clic
            self.root.after(300, self.show_updated)
        threading.Thread(target=self.reader, daemon=True).start()
        threading.Thread(target=self.bridge_reader, daemon=True).start()
        threading.Thread(target=self.worker, daemon=True).start()
        threading.Thread(target=self.watch_wow, daemon=True).start()
        threading.Thread(target=self.watch_front, daemon=True).start()
        if not self.cfg.get("help_seen"):            # premier lancement : on montre l'aide une fois
            self.root.after(800, self._first_help)
        threading.Thread(target=self.check_update, daemon=True).start()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self.poll)

    def ask_ui_lang(self):
        """Premier lancement : Francais (premier choix) ou English. Anglais -> tchat traduit en anglais."""
        T = self.T
        self.root.withdraw()
        w = tk.Toplevel(self.root)
        w.title("WoW Traducteur")
        w.configure(bg=T["panel"])
        w.attributes("-topmost", True)
        w.resizable(False, False)
        sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
        w.geometry("360x190+%d+%d" % (max(0, (sw - 360) // 2), max(0, (sh - 190) // 2)))
        tk.Label(w, text="Choisis ta langue\nChoose your language", bg=T["panel"], fg=T["fg"],
                 font=("Segoe UI", 12, "bold"), justify="center").pack(pady=(18, 14))
        choice = {"v": "fr"}

        def pick(code):
            choice["v"] = code
            w.destroy()
        for label, code, main in (("Fran\u00e7ais", "fr", True), ("English", "en", False)):
            tk.Button(w, text=label, command=lambda c=code: pick(c), width=18,
                      bg=T["accent"] if main else T["btn"], fg=T["accent_fg"] if main else T["btn_fg"],
                      activebackground=T["accent_act"] if main else T["btn_act"], relief="flat", bd=0,
                      pady=5, cursor="hand2", font=("Segoe UI", 10, "bold" if main else "normal")).pack(pady=3)
        w.protocol("WM_DELETE_WINDOW", lambda: pick("fr"))
        w.grab_set()
        self.root.wait_window(w)
        self.set_ui_lang(choice["v"], first=True)
        self.root.deiconify()

    def set_ui_lang(self, code, first=False):
        """Change la langue de l'interface ; en passant a l'anglais, le tchat est traduit en anglais (et inversement)."""
        old = self.cfg.get("ui_lang")
        self.cfg["ui_lang"] = code
        if first or (old and old != code and self.cfg.get("target") == old):
            self.cfg["target"] = code
            if self.cfg.get("out_lang") == code:
                self.cfg["out_lang"] = "en" if code == "fr" else "fr"
        save_config(self.cfg)

    # ---- ne pas prendre le clavier a WoW ----------------------------------
    def set_noactivate(self, on):
        """WS_EX_NOACTIVATE : un clic sur la fenetre (lien, defilement, bouton) ne lui donne pas le
        clavier, WoW le garde (on peut continuer a bouger, parler aux PNJ). Seule la zone "Ecrire"
        reprend le clavier quand on clique dedans (take_keyboard)."""
        if os.name != "nt":
            return
        try:
            u = ctypes.windll.user32
            get = getattr(u, "GetWindowLongPtrW", None) or u.GetWindowLongW
            put = getattr(u, "SetWindowLongPtrW", None) or u.SetWindowLongW
            get.restype, get.argtypes = ctypes.c_ssize_t, [ctypes.c_void_p, ctypes.c_int]
            put.restype, put.argtypes = ctypes.c_ssize_t, [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
            u.GetParent.restype, u.GetParent.argtypes = ctypes.c_void_p, [ctypes.c_void_p]
            h = u.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            st = get(h, -20)                                 # GWL_EXSTYLE
            new = (st | 0x08000000) if on else (st & ~0x08000000)
            if new != st:
                put(h, -20, new)
        except Exception:  # noqa
            pass

    def _follow_cursor(self, _e=None):
        """Le texte defile pour que la fin (la ou on ecrit) reste visible dans la case."""
        try:
            if self.out_entry.index("insert") >= self.out_entry.index("end"):
                self.out_entry.xview_moveto(1.0)
        except tk.TclError:
            pass

    def take_keyboard(self, _e=None):
        """Clic dans "Ecrire" (ou sur un pseudo) : la fenetre prend le clavier pour que tu ecrives."""
        self.set_noactivate(False)
        try:
            self.root.focus_force()
            self.out_entry.focus_set()
        except tk.TclError:
            pass

    def _give_back_keyboard(self):
        """Tu es reparti dans WoW (ou ailleurs) : la fenetre redevient "sans clavier" au clic."""
        try:
            if self.root.focus_get() is None:
                self.set_noactivate(True)
        except (tk.TclError, KeyError):
            self.set_noactivate(True)

    # ---- interface -------------------------------------------------------
    def apply_window_cfg(self):
        self.root.attributes("-topmost", bool(self.cfg["topmost"]))
        try:
            self.root.attributes("-alpha", float(self.cfg["alpha"]))
        except tk.TclError:
            pass

    def build_ui(self):
        r = self.root
        T = self.T
        BAR = T["bar"]
        bar = tk.Frame(r, bg=BAR)
        self._bar = bar
        bar.pack(fill="x")
        if T["border_w"] > 1:       # liseré sous la barre, couleur du cadre
            tk.Frame(r, bg=T["border"], height=1).pack(fill="x")
        btn = dict(bg=T["btn"], fg=T["btn_fg"], relief="flat", bd=0, padx=8, pady=2, activebackground=T["btn_act"],
                   activeforeground=T["btn_fg"], cursor="hand2", font=("Segoe UI", 9), highlightthickness=0)
        drag = [bar]
        if T["emblem"]:
            self._emblem_img = tk.PhotoImage(data=base64.b64encode(emblem_png(T["emblem"], BAR)).decode("ascii"),
                                             format="png")
            cv = tk.Label(bar, image=self._emblem_img, bg=BAR, bd=0, highlightthickness=0)
            cv.pack(side="left", padx=(6, 2), pady=2)
            drag.append(cv)
        if T["label"]:
            lab = tk.Label(bar, text=T["label"], bg=BAR, fg=T["label_fg"], font=("Segoe UI", 9, "bold"))
            lab.pack(side="left", padx=(2, 2))
            drag.append(lab)
        setb = tk.Button(bar, text=_("\u2699 R\u00e9glages"), command=self.open_settings, **btn)
        setb.pack(side="left", padx=(6, 3), pady=4)
        self._clear_btn = tk.Button(bar, text=_("Effacer"), command=self.clear, **btn)
        self._clear_btn.pack(side="left", padx=3, pady=4)
        helpb = tk.Button(bar, text="?", command=self.open_help, **dict(btn, padx=7))
        helpb.pack(side="left", padx=3, pady=4)
        for b in (setb, self._clear_btn, helpb):        # boutons aux coins arrondis
            self._round(b, 5, T["btn"], BAR)
        # bouton cache, affiche seulement si une nouvelle version existe sur GitHub
        self.update_btn = tk.Button(bar, text="", command=self.do_update,
                                    **dict(btn, bg=T["accent"], fg=T["accent_fg"], activebackground=T["accent_act"]))
        self._round(self.update_btn, 5, T["accent"], BAR)
        closeb = tk.Button(bar, text="\u2715", command=self.on_close, bg=BAR, fg=T["icon"], relief="flat", bd=0,
                           padx=10, pady=2, activebackground="#c0392b", activeforeground="white",
                           cursor="hand2", font=("Segoe UI", 10), highlightthickness=0)
        closeb.pack(side="right", padx=(0, 4), pady=4)
        minb = tk.Button(bar, text="\u2014", command=self.minimize, bg=BAR, fg=T["icon"], relief="flat", bd=0,
                         padx=10, pady=2, activebackground=T["btn_act"], activeforeground="white",
                         cursor="hand2", font=("Segoe UI", 10), highlightthickness=0)
        minb.pack(side="right", pady=4)
        self._minb = minb
        # cadenas : dessine (pas d'emoji, mal affiche par tkinter sous Windows)
        self.lock_cv = tk.Canvas(bar, width=22, height=22, bg=BAR, highlightthickness=0, bd=0, cursor="hand2")
        self.lock_cv.pack(side="right", padx=(0, 2), pady=3)
        self.lock_cv.bind("<Button-1>", lambda e: self.toggle_lock())
        self.draw_lock()
        self._minimized = False
        r.bind("<Map>", self._on_map)
        # texte d'etat : raccourci quand la fenetre est etroite ("OK · 12 msg"), au lieu d'etre coupe au debut
        stat = tk.Label(bar, text="", bg=BAR, fg=T["status"], anchor="e", font=("Segoe UI", 8), width=1)
        stat.pack(side="right", fill="x", expand=True, padx=6)
        self._stat_lbl = stat

        def fit_status(*a):
            try:
                full = self.status.get()
                room = stat.winfo_width() - 4
                f = tkfont.Font(font=stat.cget("font"))
                txt = full
                if room > 20 and f.measure(txt) > room:
                    m = re.search(r"OK\D*?(\d+)", full)
                    txt = ("OK \u00b7 %s msg" % m.group(1)) if m else full
                    while len(txt) > 2 and f.measure(txt + "\u2026") > room:
                        txt = txt[:-1]
                    if txt != full and not txt.endswith("msg"):
                        txt = txt.rstrip() + "\u2026"
                stat.config(text=txt)
            except tk.TclError:
                pass
        if getattr(self, "_stat_trace", None):
            try:
                self.status.trace_remove("write", self._stat_trace)
            except tk.TclError:
                pass
        self._stat_trace = self.status.trace_add("write", fit_status)
        stat.bind("<Configure>", fit_status)
        fit_status()
        # glisser la barre pour deplacer la fenetre
        for w in drag + [stat]:
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)
            w.bind("<ButtonRelease-1>", lambda e: self._save_geometry())

        mid = tk.Frame(r, bg=T["bg"])
        mid.pack(fill="both", expand=True, padx=8, pady=(2, 4))
        self.text = tk.Text(mid, bg=T["bg"], fg=T["fg"], wrap="word", relief="flat", state="disabled",
                            font=("Segoe UI", int(self.cfg["font_size"])), cursor="arrow",
                            insertbackground=T["fg"], spacing1=3, padx=2, height=4, highlightthickness=0, bd=0)
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Dark.Vertical.TScrollbar", background=T["scroll"], troughcolor=T["bg"], bordercolor=T["bg"],
                        lightcolor=T["scroll"], darkcolor=T["scroll"], gripcount=0, width=7)
        style.map("Dark.Vertical.TScrollbar", background=[("active", T["scroll_act"])])
        style.layout("Dark.Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
            ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
        sb = ttk.Scrollbar(mid, command=self.text.yview, style="Dark.Vertical.TScrollbar")
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        for k, c in (T["colors"] or COLORS).items():
            self.text.tag_configure(k, foreground=c)
        self.text.tag_configure("trans", foreground=T["trans"], lmargin1=18, lmargin2=18)
        self.text.bind("<Motion>", self.on_motion)          # survol des liens -> fiche de l'objet
        self.text.bind("<Leave>", self.on_text_leave)
        self.text.tag_configure("alert", background=T["alert_bg"])
        self.text.tag_configure("badge", foreground=T["badge"])
        self.text.tag_configure("err", foreground=T["err"])
        for unit in COIN_COLORS:                 # texte "po" / "pa" / "pc" cache derriere son icone
            self.text.tag_configure("coin_" + unit, elide=True)
        for i in PING_SHAPES:                    # symbole du ping cache derriere son image
            self.text.tag_configure("pingimg_%d" % i, elide=True)
        self.text.tag_configure("me", foreground=T["me"])
        self.text.tag_configure("name", foreground=T["name"],    # apres les canaux : la couleur du pseudo prime
                                font=("Segoe UI", int(self.cfg["font_size"]), "bold"))
        # ton propre pseudo : en gras comme les autres, mais pas "cliquable pour repondre"
        self.text.tag_configure("myname", font=("Segoe UI", int(self.cfg["font_size"]), "bold"))
        # lien Ko-fi du message d'accueil (au lancement du traducteur seulement, jamais dans le jeu)
        self.text.tag_configure("kofi", foreground="#6fa8ff" if not T["colors"] else "#0058b0", underline=True)
        self.text.tag_bind("kofi", "<Button-1>", lambda e: webbrowser.open(KOFI_URL))
        self.text.tag_bind("kofi", "<Enter>", lambda e: self.text.config(cursor="hand2"))
        self.text.tag_bind("kofi", "<Leave>", lambda e: self.text.config(cursor=""))
        self.text.tag_configure("news", foreground=T["name"], font=("Segoe UI", int(self.cfg["font_size"]), "bold"))
        for i, (_w, _s, c) in enumerate(PING_ICONS):             # icones des pings, dans leur couleur
            self.text.tag_configure("ping_%d" % i, foreground=c)
        for code, c in (T["links"] or LINK_COLORS).items():     # en dernier : la couleur du lien prime
            self.text.tag_configure("link_" + code, foreground=c)
            if code == "o":                                      # lien sans fiche : pas de main au survol
                continue
            # main au survol : un clic ouvre la fiche sur Wowhead (voir on_click)
            self.text.tag_bind("link_" + code, "<Enter>", lambda e: self.text.config(cursor="hand2"))
            self.text.tag_bind("link_" + code, "<Leave>", lambda e: self.text.config(cursor=""))
        self.text.bind("<Button-1>", self.on_click)

        P = T["panel"]
        out = tk.Frame(r, bg=P)
        out.pack(side="bottom", fill="x", padx=8, pady=(0, 8), before=mid)
        # une seule barre (1.9.8) : [FR -> EN] [ta phrase] [x] | [ABC] [Traduire + copier], sur fond de case
        E = T["entry"]
        bar = tk.Frame(out, bg=E, highlightthickness=0)
        bar.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 3))
        out.columnconfigure(0, weight=1)
        bar.columnconfigure(1, weight=1)
        B = T["btn"]
        lf = tk.Frame(bar, bg=B)
        lf.grid(row=0, column=0, sticky="ns")
        # destinataire du chuchotement (clic sur un pseudo) : "A Nom (FR) ->" + croix pour annuler
        self.reply_lbl = tk.Label(lf, text=("%s \u2192" % UI.upper()), bg=B, fg=T["name"],
                                  font=("Segoe UI", 9, "bold"), padx=0)
        self.reply_lbl.pack(side="left", padx=(8, 0))
        self.reply_x = tk.Button(lf, text="\u2715", command=lambda: self.set_reply_to(None), bg=B, fg=T["muted"],
                                 activebackground=B, activeforeground=T["fg"], relief="flat", bd=0,
                                 highlightthickness=0, padx=2, pady=0, cursor="hand2", font=("Segoe UI", 8))
        # width=1 : la case prend juste la place restante (avec sa largeur par defaut, dans une petite
        # fenetre, une partie passait sous les boutons et le curseur sortait de la partie visible)
        self.out_entry = tk.Entry(bar, bg=T["entry"], fg=T["fg"], insertbackground=T["fg"], relief="flat",
                                  highlightthickness=0, width=1)
        self.out_entry.grid(row=0, column=1, sticky="ew", padx=(8, 0), ipady=4)
        # texte d'aide en gris DANS la case vide (pas du vrai texte : il n'est jamais traduit ni copie)
        self.out_ph = tk.Label(self.out_entry, text=_("\u00c9cris ici en fran\u00e7ais\u2026"), bg=T["entry"],
                               fg=T["muted"], anchor="w", padx=0, pady=0, bd=0, cursor="xterm")
        self.out_ph.bind("<Button-1>", lambda e: (self.out_entry.focus_set(), self.take_keyboard()))
        if not getattr(self, "_ph_loop", False):        # une seule boucle, meme si la fenetre est refaite
            self._ph_loop = True
            self.root.after(150, self._ph_update)
        # croix : efface vite le texte a traduire et le dernier resultat (touche Echap aussi)
        xb = tk.Button(bar, text="\u2715", command=self.clear_out, bg=T["entry"], fg=T["muted"],
                  activebackground=T["btn_act"], activeforeground=T["err"], relief="flat", bd=0,
                  highlightthickness=0, padx=2, pady=0, cursor="hand2",
                  font=("Segoe UI", 8))
        xb.grid(row=0, column=2, sticky="ns", padx=(0, 4))    # petite croix
        self._add_hint(xb, _("\u2715 : efface ta phrase (touche \u00c9chap aussi)."))
        self.out_lang = tk.StringVar(value=self.cfg["out_lang"])
        # langue de reponse : bouton "EN ▴" qui ouvre une liste VERS LE HAUT (la fenetre est souvent en bas)
        self.out_lang_btn = tk.Button(lf, text="", command=self.open_lang_menu, bg=B, fg=T["name"],
                                      activebackground=T["btn_act"], activeforeground=T["name"], relief="flat", bd=0,
                                      highlightthickness=0, padx=6, cursor="hand2", font=("Segoe UI", 9, "bold"))
        self.out_lang_btn.pack(side="left", fill="y", padx=(2, 2))
        self._add_hint(self.out_lang_btn, _("Langue dans laquelle ta phrase sera traduite (clique pour la changer)."))
        # correcteur (orthographe / grammaire) : corrige le texte de la case, sans le traduire.
        # Active par defaut seulement en francais (lexique de fautes teste en francais) ;
        # en anglais, il faut l'activer soi-meme ("correcteur": true dans les reglages).
        if self.cfg.get("correcteur", UI == "fr"):
            # petit bouton "ABC✓" (symbole des correcteurs) : la case Ecrire garde presque toute sa place
            tk.Frame(bar, bg=T["btn_act"], width=1).grid(row=0, column=3, sticky="ns")   # petit trait
            cb = tk.Button(bar, text="\u2713 ABC", command=self.correct_out, bg=T["entry"], fg=T["fg"],
                           activebackground=T["btn_act"], activeforeground=T["fg"], relief="flat", bd=0,
                           highlightthickness=0, padx=8, cursor="hand2", font=("Segoe UI", 8, "bold"))
            cb.grid(row=0, column=4, sticky="ns")
            self._add_hint(cb, _("ABC (b\u00eata) : corrige et copie en fran\u00e7ais, SANS traduire. Correcteur en d\u00e9veloppement : relis avant d'envoyer."))
        self.out_lang.trace_add("write", lambda *a: self._show_lang())
        self._show_lang()
        tb = tk.Button(bar, text=_("Traduire + copier"), command=self.send_out, bg=T["accent"], fg=T["accent_fg"],
                       activebackground=T["accent_act"], activeforeground=T["accent_fg"],
                       relief="flat", highlightthickness=0, bd=0, padx=12, font=("Segoe UI", 9, "bold"))
        tb.grid(row=0, column=5, sticky="ns")
        # coins arrondis de la barre : 4 petites images posees par-dessus les coins (tkinter n'arrondit pas)
        self._corner_imgs = []
        for corner, inside, rx, ry in (("nw", B, 0, 0), ("sw", B, 0, 1),
                                       ("ne", T["accent"], 1, 0), ("se", T["accent"], 1, 1)):
            try:
                img = tk.PhotoImage(data=base64.b64encode(corner_png(9, inside, P, corner)).decode("ascii"),
                                    format="png")
            except tk.TclError:
                continue
            self._corner_imgs.append(img)
            tk.Label(bar, image=img, bd=0, padx=0, pady=0, highlightthickness=0).place(
                relx=rx, rely=ry, anchor={"nw": "nw", "sw": "sw", "ne": "ne", "se": "se"}[corner])
        self._add_hint(tb, _("Traduit ta phrase dans la langue choisie et copie la traduction."))
        self.out_result = tk.Label(out, text=_("Clique sur un message pour repondre dans sa langue."),
                                   bg=P, fg=T["muted"], anchor="w", justify="left", wraplength=520)
        self.out_result.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 3))
        # Entree ne fait rien : on clique sur "Traduire + copier" ou "ABC" (par reflexe, ca traduisait sans le vouloir)
        self.out_entry.bind("<Button-1>", self.take_keyboard, add="+")
        self.out_entry.bind("<Escape>", lambda e: self.clear_out())
        self.out_entry.bind("<KeyRelease>", self._follow_cursor, add="+")
        self.set_reply_to(getattr(self, "reply_to", None), quiet=True)

        grip = tk.Label(r, text="\u25e2", bg=T["bg"], fg=T["scroll_act"], font=("Segoe UI", 9))
        try:
            grip.configure(cursor="size_nw_se")
        except tk.TclError:
            pass
        grip.place(relx=1.0, rely=1.0, x=-3, y=-2, anchor="se")    # decale : laisse la place au coin arrondi
        self._round_window()
        grip.bind("<ButtonPress-1>", self._resize_start)
        grip.bind("<B1-Motion>", self._resize_move)
        grip.bind("<ButtonRelease-1>", lambda e: self._save_geometry())

    def _coin_image(self, unit):
        """Petite pile de pieces (or, argent, cuivre) aux bords lisses, a la taille du texte."""
        cache = self.__dict__.setdefault("_coin_imgs", {})
        try:
            px = int(self.cfg["font_size"]) * self.root.winfo_fpixels("1i") / 72.0   # taille du texte en pixels
        except Exception:  # noqa
            px = int(self.cfg["font_size"]) * 4 / 3.0
        size = max(12, int(round(px * 1.05)))     # un peu plus haut que les chiffres
        key = (unit, size)
        if key not in cache:
            data = base64.b64encode(coin_png(unit, size)).decode("ascii")
            cache[key] = tk.PhotoImage(data=data, format="png")
        return cache[key]

    def _ping_image(self, index):
        """Losange du ping (Menace, Par ici), a la taille du texte."""
        cache = self.__dict__.setdefault("_ping_imgs", {})
        try:
            px = int(self.cfg["font_size"]) * self.root.winfo_fpixels("1i") / 72.0
        except Exception:  # noqa
            px = int(self.cfg["font_size"]) * 4 / 3.0
        size = max(12, int(round(px * 1.15)))
        key = (index, size)
        if key not in cache:
            cache[key] = tk.PhotoImage(data=base64.b64encode(ping_png(index, size)).decode("ascii"), format="png")
        return cache[key]

    def _insert_with_coins(self, text, tags):
        """Insere du texte ; dans les messages du jeu, po / pa / pc deviennent une icone de piece.
        Le texte reste la (cache) : il revient au copier-coller et au changement de theme."""
        t = self.text
        tags = tuple(tags)
        ping_tag = next((g for g in tags if g.startswith("pingimg_")), None)
        if ping_tag:                             # losange du ping (et son symbole cache, pour le copier-coller)
            t.image_create("end", image=self._ping_image(int(ping_tag[8:])), padx=1, align="center")
            t.insert("end", text, tags)
            return
        unit_tag = next((g for g in tags if g.startswith("coin_")), None)
        if unit_tag:                             # restauration (changement de theme) : remettre l'icone
            t.image_create("end", image=self._coin_image(unit_tag[5:]), padx=1, align="baseline")
            t.insert("end", text, tags)
            return
        if "coins" not in tags:
            t.insert("end", text, tags)
            return
        text = COIN_WORDS_RE.sub(lambda m: " " + COIN_WORDS[m.group(1).lower()], text)
        pos = 0
        for m in COIN_RE.finditer(text):
            t.insert("end", text[pos:m.start()], tags)     # piece collee au chiffre, comme dans WoW
            t.image_create("end", image=self._coin_image(m.group(2)), padx=1, align="baseline")
            t.insert("end", m.group(2), tags + ("coin_" + m.group(2),))
            pos = m.end()
        t.insert("end", text[pos:], tags)

    def add(self, *parts):
        """parts: (texte, tag...)"""
        t = self.text
        # on ne descend tout seul que si la toute derniere ligne est visible : avant (98 % du texte),
        # avec un long historique, remonter de quelques messages comptait encore comme "en bas"
        # "end-2l" : debut du dernier message (la toute derniere ligne, vide, n'est pas toujours affichee)
        at_end = t.yview()[1] >= 0.999 or t.dlineinfo("end-2l") is not None or t.dlineinfo("end-1c") is not None
        t.configure(state="normal")
        for p in parts:
            self._insert_with_coins(p[0], p[1:])
        t.configure(state="disabled")
        if at_end:
            t.see("end")
        n = int(t.index("end-1c").split(".")[0])
        if n > 1500:
            t.configure(state="normal")
            t.delete("1.0", "400.0")
            t.configure(state="disabled")
            self.line_lang = {}

    def _show_lang(self):
        code = (self.out_lang.get() or "en").strip().lower()
        try:
            self.out_lang_btn.config(text="%s \u25b4" % code.upper())
        except Exception:  # noqa
            pass

    def open_lang_menu(self):
        """Liste des langues de reponse : 3 rapides, puis "Autre langue..." ; s'ouvre au-dessus du bouton."""
        T = self.T
        kw = dict(tearoff=0, bg=T["entry"], fg=T["fg"], activebackground=T["accent"],
                  activeforeground=T["accent_fg"], bd=0)
        m = tk.Menu(self.root, **kw)
        sub = tk.Menu(m, **kw)
        quick, others = lang_lists()
        for name, code in quick:
            m.add_radiobutton(label="%s (%s)" % (name, code), variable=self.out_lang, value=code)
        m.add_separator()
        for name, code in others:
            sub.add_radiobutton(label="%s (%s)" % (name, code), variable=self.out_lang, value=code)
        m.add_cascade(label=_("Autre langue\u2026"), menu=sub)
        m.update_idletasks()
        b = self.out_lang_btn
        x, y = b.winfo_rootx(), b.winfo_rooty() - m.winfo_reqheight()
        try:
            m.tk_popup(x, max(0, y))
        finally:
            m.grab_release()

    def apply_theme(self, name):
        """Change de theme tout de suite : reconstruit la fenetre en gardant le tchat affiche."""
        self.T = THEMES.get(name, _SOMBRE)
        cov = getattr(self, "_cover", None)          # cache-bande refait aux couleurs du nouveau theme
        if cov is not None:
            try:
                cov.destroy()
            except tk.TclError:
                pass
            self._cover, self._cover_shown = None, False
        dump = self.text.dump("1.0", "end-1c", text=True, tag=True)
        out_lang = self.out_lang.get()
        out_msg = self.out_result.cget("text")
        upd = self.update_btn.cget("text") if self.update_btn.winfo_manager() else ""
        for wdg in self.root.winfo_children():
            if not isinstance(wdg, tk.Toplevel):
                wdg.destroy()
        self.root.configure(bg=self.T["bg"], highlightthickness=self.T["border_w"],
                            highlightbackground=self.T["border"], highlightcolor=self.T["border"])
        self.build_ui()
        self.text.configure(state="normal")
        tags = []
        for kind, val, _idx in dump:
            if kind == "tagon":
                tags.append(val)
            elif kind == "tagoff":
                if val in tags:
                    tags.remove(val)
            elif kind == "text":
                self._insert_with_coins(val, tuple(tags))
        self.text.configure(state="disabled")
        self.text.see("end")
        self.out_lang.set(out_lang)
        self.out_result.config(text=out_msg)
        if upd:
            self.update_btn.config(text=upd)
            self.update_btn.pack(side="left", padx=3, pady=4, after=self._clear_btn)

    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self.line_lang = {}

    def save_tips(self):
        self._tips_dirty = False
        try:
            tmp = TIPS_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.tips, f, ensure_ascii=False)
            os.replace(tmp, TIPS_PATH)
        except OSError:
            pass

    def close_tip(self):
        w = getattr(self, "_tip_win", None)
        if w is not None and w.winfo_exists():
            w.destroy()
        self._tip_win = None

    def show_tip(self, name, lines, color, x, y):
        """Petit cadre facon infobulle de WoW, pres de la souris. Clic dessus pour fermer."""
        self.close_tip()
        w = tk.Toplevel(self.root)
        self._tip_win = w
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.configure(bg="#c0c0c0")                          # liseré gris clair
        f = tk.Frame(w, bg="#0a0d1c", padx=10, pady=7)
        f.pack(padx=1, pady=1)
        fs = int(self.cfg["font_size"])
        tk.Label(f, text=name, bg="#0a0d1c", fg=color, font=("Segoe UI", fs + 1, "bold"),
                 anchor="w", justify="left", wraplength=340).pack(fill="x")
        for ln in lines:
            ln = re.sub(r"\s*\|n\s*", " ", ln).strip()   # "|n" = retour a la ligne de WoW ("Composants : |nRouleau...")
            if not ln:
                continue
            low = ln.lower()
            if low.startswith(("utiliser", "équipé", "chances quand", "use:", "equip:")):
                c = "#1eff00"
            elif ln.startswith(("\"", "\u00ab", "\u201c")):
                c = "#ffd100"
            elif low.startswith(("requiert", "niveau", "level", "requires")):
                c = "#ffffff"
            else:
                c = "#e8e8e8"
            if COIN_RE.search(COIN_WORDS_RE.sub(lambda m: " " + COIN_WORDS[m.group(1).lower()], ln)):
                self._tip_coin_line(f, ln, c, fs)       # "Prix de vente : 11 pa 36 pc" -> pieces, comme dans WoW
                continue
            tk.Label(f, text=ln, bg="#0a0d1c", fg=c, font=("Segoe UI", fs), anchor="w",
                     justify="left", wraplength=340).pack(fill="x")
        more = tk.Label(f, text=_("Voir sur Wowhead \u2197"), bg="#0a0d1c", fg="#6fa8ff", cursor="hand2",
                        font=("Segoe UI", fs - 1, "underline"), anchor="w")
        more.pack(fill="x", pady=(6, 0))
        more.bind("<Button-1>", lambda e: (webbrowser.open(WOWHEAD_SEARCH + urllib.parse.quote(name)),
                                           self.close_tip()))
        for wdg in [w, f] + [c for c in f.winfo_children() if c is not more]:
            wdg.bind("<ButtonRelease-1>", lambda e: self.close_tip())
        w.bind("<Escape>", lambda e: self.close_tip())
        # se ferme aussi toute seule : quand la souris en sort, ou au bout de 8 s si on n'y va pas
        state = {"in": False}

        def enter(_e):
            state["in"] = True

        def leave(_e):
            def check():
                if self._tip_win is w and w.winfo_exists() and getattr(self, "_hover_name", None) != name:
                    px, py = w.winfo_pointerxy()
                    x0, y0 = w.winfo_rootx(), w.winfo_rooty()
                    if not (x0 <= px < x0 + w.winfo_width() and y0 <= py < y0 + w.winfo_height()):
                        self.close_tip()
            w.after(300, check)

        def timeout():
            if self._tip_win is w and w.winfo_exists() and not state["in"]:
                if getattr(self, "_hover_name", None) == name:   # souris toujours sur le lien
                    w.after(1000, timeout)
                else:
                    self.close_tip()
        w.bind("<Enter>", enter)
        w.bind("<Leave>", leave)
        w.after(8000, timeout)
        w.update_idletasks()
        tw, th = w.winfo_reqwidth(), w.winfo_reqheight()
        sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
        px = min(max(0, x + 14), sw - tw)
        py = y + 14 if y + 14 + th <= sh else max(0, y - th - 10)
        w.geometry("+%d+%d" % (px, py))

    def _tip_coin_line(self, parent, ln, color, fs):
        """Ligne de fiche avec un prix : le texte, et une petite piece a la place de po / pa / pc."""
        row = tk.Frame(parent, bg="#0a0d1c")
        row.pack(fill="x", anchor="w")
        text = COIN_WORDS_RE.sub(lambda m: " " + COIN_WORDS[m.group(1).lower()], ln)
        pos = 0
        for m in COIN_RE.finditer(text):
            part = text[pos:m.start()]
            if part:
                tk.Label(row, text=part, bg="#0a0d1c", fg=color, font=("Segoe UI", fs),
                         padx=0).pack(side="left", padx=(1 if pos == 0 else 0, 0))
            tk.Label(row, image=self._coin_image(m.group(2)), bg="#0a0d1c", padx=0,
                     bd=0).pack(side="left", padx=(2, 1))      # piece collee au chiffre, comme dans WoW
            pos = m.end()
        if text[pos:].strip():
            tk.Label(row, text=text[pos:], bg="#0a0d1c", fg=color, font=("Segoe UI", fs),
                     padx=0).pack(side="left")
        for wdg in [row] + row.winfo_children():           # clic dessus : ferme la fiche, comme le reste
            wdg.bind("<ButtonRelease-1>", lambda e: self.close_tip())
        return row

    def set_reply_to(self, name, quiet=False):
        """Destinataire des reponses : "Traduire + copier" copiera "/w Nom texte"."""
        self.reply_to = name or None
        if self.reply_to:
            self.reply_lbl.config(text=_("\u00c0 %s (%s) \u2192") % (self.reply_to, UI.upper()), fg=self.T["name"])
            self.reply_x.pack(side="left", padx=(3, 0), after=self.reply_lbl)
            if not quiet:
                self.out_result.config(text=_("Chuchotement \u00e0 %s : ta reponse sera copiee avec /w %s")
                                       % (self.reply_to, self.reply_to), fg=self.T["muted"])
                self.take_keyboard()
        else:
            self.reply_lbl.config(text=("%s \u2192" % UI.upper()), fg=self.T["name"])
            self.reply_x.pack_forget()
            if not quiet:
                self.out_result.config(text=_("Reponse normale (sans /w)."), fg=self.T["muted"])

    def link_at(self, idx):
        """(tag, nom) du lien d'objet / de quete sous l'index, ou (None, "")."""
        link = next((t for t in self.text.tag_names(idx) if t.startswith("link_")), None)
        if not link or link == "link_o":         # autre lien du jeu ([Vous avez succombe.]...) : pas de fiche
            return None, ""
        rng = self.text.tag_prevrange(link, idx + "+1c")
        if not rng:
            return link, ""
        # plusieurs liens colles ("[A][B][C]") forment une seule zone : on garde celui vise
        full = self.text.get(*rng)
        off = len(self.text.get(rng[0], idx))
        a, b = full.rfind("[", 0, off + 1), full.find("]", off)
        if a != -1 and b != -1 and a < b:
            return link, full[a + 1:b].strip()
        return link, full.strip().strip("[]").strip()

    def open_link_tip(self, link, name, x, y):
        lines = self.tips.get(name.lower())
        col = self.text.tag_cget(link, "foreground") or self.T["fg"]
        if not lines:                            # pas recue (lien d'avant la mise a jour...)
            if link == "link_a":                 # haut fait : le jeu n'envoie pas de fiche
                lines = [_("(haut fait : le détail est sur Wowhead)")]
            elif link == "link_e" and name.lower() in PROFESSIONS:   # lien de metier : pas de fiche
                lines = [_("(lien de métier : clique dessus dans WoW pour voir ses recettes)")]
            elif link.startswith("link_q"):        # quete inconnue du jeu (pas dans ton journal) : jamais recue
                lines = [_("(le jeu ne donne pas la fiche de cette quête, souvent tant qu'elle n'est pas "
                           "dans ton journal : vois-la sur Wowhead)")]
            else:
                lines = [_("(fiche pas encore reçue du jeu : elle arrivera au prochain lien de cet objet)")]
        self.show_tip(name, lines, col, x, y)
        self._tip_name = name

    def on_motion(self, event):
        """Survol d'un lien : la fiche s'affiche apres un court instant, comme dans WoW."""
        idx = self.text.index("@%d,%d" % (event.x, event.y))
        link, name = self.link_at(idx)
        job = getattr(self, "_hover_job", None)
        if name and name == getattr(self, "_hover_name", None):
            return
        if job:
            self.root.after_cancel(job)
            self._hover_job = None
        self._hover_name = name or None
        if name:
            self._hover_job = self.root.after(250, lambda: (
                setattr(self, "_hover_job", None),
                self.open_link_tip(link, name, self.root.winfo_pointerx(), self.root.winfo_pointery())))
        elif getattr(self, "_tip_win", None) is not None:
            self.root.after(300, self._close_tip_if_away)

    def on_text_leave(self, _event):
        job = getattr(self, "_hover_job", None)
        if job:
            self.root.after_cancel(job)
            self._hover_job = None
        self._hover_name = None
        self.root.after(300, self._close_tip_if_away)

    def _close_tip_if_away(self):
        """Ferme la fiche si la souris n'est ni sur son lien ni sur la fiche elle-meme."""
        w = getattr(self, "_tip_win", None)
        if w is None or not w.winfo_exists():
            return
        if getattr(self, "_hover_name", None) == getattr(self, "_tip_name", None):
            return
        px, py = w.winfo_pointerxy()
        x0, y0 = w.winfo_rootx(), w.winfo_rooty()
        if not (x0 <= px < x0 + w.winfo_width() and y0 <= py < y0 + w.winfo_height()):
            self.close_tip()

    def on_click(self, event):
        idx = self.text.index("@%d,%d" % (event.x, event.y))
        link, name = self.link_at(idx)
        if link:                                         # clic sur un objet / une quete : sa fiche
            if name:
                self.open_link_tip(link, name, event.x_root, event.y_root)
            return
        self.close_tip()
        if "name" in self.text.tag_names(idx):         # clic sur un pseudo : on lui repondra en chuchotement
            rng = self.text.tag_prevrange("name", idx + "+1c")
            if rng:
                who = self.text.get(*rng).strip()      # sur Forever les pseudos ont souvent 2 mots
                if who:
                    self.set_reply_to(who)
        ln = int(idx.split(".")[0])
        for k in (ln, ln - 1):
            if k in self.line_lang:
                lang = self.line_lang[k]
                if lang and lang not in ("?", self.cfg["target"]):
                    self.out_lang.set(lang)
                    self.out_result.config(text=_("Langue de reponse : %s") % lang)
                return

    def show_welcome(self):
        """Message d'accueil a chaque lancement : la version. Le lien Ko-fi seulement au premier
        lancement d'une nouvelle version (apres une mise a jour), pas tous les jours."""
        self.add((_("Bienvenue dans WoW Traducteur %s !") % VERSION + "\n", "news"))
        if not self._first_run and self.cfg.get("last_version") != VERSION:
            self.add((_("Le traducteur est gratuit. Pour me soutenir : "), "badge"),
                     (KOFI_URL.replace("https://", ""), "kofi"), ("\n", "badge"))

    def on_chatfr_ver(self, ver):
        """ChatFR envoie sa version toutes les 30 s : si elle differe de la notre, on previent (une fois)."""
        def num(v):
            return tuple(int(x) for x in re.findall(r"\d+", v))
        if not ver or num(ver) == num(VERSION) or getattr(self, "_ver_warned", None) == ver:
            return
        self._ver_warned = ver
        if num(ver) < num(VERSION):
            msg = _("\u26a0 ChatFR est en %s, le traducteur en %s : mets ChatFR \u00e0 jour (CurseForge), puis relance le jeu.")
        else:
            msg = _("\u26a0 ChatFR est en %s, le traducteur en %s : mets le traducteur \u00e0 jour (bouton dans les R\u00e9glages).")
        self.add((msg % (ver, VERSION) + "\n", "err"))

    def show_updated(self):
        old = os.environ.pop("WOWTRAD_UPDATED", "")
        self.add((_("\u2713 Mise \u00e0 jour termin\u00e9e : %s \u2192 %s. Pense aussi \u00e0 mettre ChatFR \u00e0 jour (CurseForge).")
                  % (old, VERSION) + "\n", "news"))

    def show_news(self):
        """Apres une mise a jour (jamais au premier lancement, qui montre deja l'aide) :
        une petite fenetre avec les nouveautes, une seule fois."""
        if self.cfg.get("last_version") == VERSION:
            return
        self.cfg["last_version"] = VERSION
        save_config(self.cfg)
        if self._first_run:
            return
        T = self.T
        lines = NEWS["en" if UI == "en" else "fr"]
        w = tk.Toplevel(self.root)
        w.title(lines[0].rstrip(" :"))
        w.configure(bg=T["panel"])
        w.attributes("-topmost", True)
        sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
        w.geometry("560x400+%d+%d" % (max(0, (sw - 560) // 2), max(0, (sh - 400) // 2)))
        fs = int(self.cfg["font_size"])
        tk.Label(w, text=lines[0], bg=T["panel"], fg=T["name"], font=("Segoe UI", fs + 2, "bold"),
                 anchor="w").pack(fill="x", padx=14, pady=(12, 6))
        bar = tk.Frame(w, bg=T["panel"])
        bar.pack(side="bottom", pady=10)
        t = tk.Text(w, bg=T["bg"], fg=T["fg"], wrap="word", relief="flat", padx=12, pady=8,
                    font=("Segoe UI", fs), highlightthickness=0, bd=0, spacing1=2, spacing3=4, cursor="arrow")
        t.pack(fill="both", expand=True, padx=12)
        for ln in lines[1:]:
            t.insert("end", "\u2022  " + ln.lstrip("- ") + "\n")
        t.configure(state="disabled")

        def help_():
            w.destroy()
            self.open_help()
        tk.Button(bar, text="OK", command=w.destroy, bg=T["accent"], fg=T["accent_fg"],
                  activebackground=T["accent_act"], activeforeground=T["accent_fg"], relief="flat", bd=0,
                  padx=18, pady=3, cursor="hand2").pack(side="left", padx=6)
        tk.Button(bar, text=_("Tout ce qu'il sait faire (?)"), command=help_, bg=T["btn"], fg=T["btn_fg"],
                  activebackground=T["btn_act"], activeforeground=T["btn_fg"], relief="flat", bd=0,
                  padx=12, pady=3, cursor="hand2").pack(side="left", padx=6)

    # ---- aide ("?") --------------------------------------------------------
    def _first_help(self):
        self.cfg["help_seen"] = True
        save_config(self.cfg)
        self.open_help()

    def open_help(self):
        old = getattr(self, "_help_win", None)
        if old is not None and old.winfo_exists():
            old.deiconify()
            old.lift()
            return
        T = self.T
        w = tk.Toplevel(self.root)
        self._help_win = w
        w.title(_("WoW Traducteur %s - ce qu'il sait faire") % VERSION)
        w.configure(bg=T["panel"])
        w.attributes("-topmost", True)
        sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()         # centree a l'ecran
        w.geometry("560x520+%d+%d" % (max(0, (sw - 560) // 2), max(0, (sh - 520) // 2)))
        fs = int(self.cfg["font_size"])
        t = tk.Text(w, bg=T["bg"], fg=T["fg"], wrap="word", relief="flat", padx=12, pady=10,
                    font=("Segoe UI", fs), highlightthickness=0, bd=0, spacing1=2, spacing3=2, cursor="arrow")
        tk.Button(w, text=_("Fermer"), command=w.destroy, bg=T["accent"], fg=T["accent_fg"],
                  activebackground=T["accent_act"], activeforeground=T["accent_fg"],
                  relief="flat", bd=0, padx=12, pady=3).pack(side="bottom", pady=8)
        sb = ttk.Scrollbar(w, orient="vertical", command=t.yview, style="Dark.Vertical.TScrollbar")
        t.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        t.pack(fill="both", expand=True)
        t.tag_configure("h", font=("Segoe UI", fs + 2, "bold"), foreground=T["name"], spacing1=10, spacing3=4)
        t.tag_configure("li", lmargin1=8, lmargin2=22)
        t.tag_configure("url", foreground="#6fa8ff", underline=True)
        t.tag_bind("url", "<Button-1>", lambda e: webbrowser.open(KOFI_URL))
        t.tag_bind("url", "<Enter>", lambda e: t.configure(cursor="hand2"))
        t.tag_bind("url", "<Leave>", lambda e: t.configure(cursor="arrow"))
        for line in (HELP_TEXT_EN if UI == "en" else HELP_TEXT).strip().splitlines():
            if line.startswith("# "):
                t.insert("end", line[2:] + "\n", "h")
            elif line.startswith("- ") and KOFI_URL in line:
                head = line[2:].split(KOFI_URL)[0]
                t.insert("end", "\u2022  " + head, "li")
                t.insert("end", KOFI_URL, ("li", "url"))
                t.insert("end", "\n", "li")
            elif line.startswith("- "):
                t.insert("end", "\u2022  " + line[2:] + "\n", "li")
            else:
                t.insert("end", line + "\n")
        t.configure(state="disabled")

    # ---- reglages --------------------------------------------------------
    def open_settings(self):
        old = getattr(self, "_settings_win", None)
        if old is not None and old.winfo_exists():     # deja ouverte : on la ramene devant
            old.deiconify()
            old.lift()
            old.focus_force()
            return
        w = tk.Toplevel(self.root)
        self._settings_win = w
        w.title(_("Reglages"))
        T = self.T
        P = T["panel"]
        w.configure(bg=P)
        w.attributes("-topmost", True)
        self._color_titlebar(w)
        fields = [
            (_("Source (pont ou log)"), "source", 8),
            (_("Fichier de log (si source=log)"), "log_path", 52),
            (_("Traduire vers (fr, en...)"), "target", 6),
            (_("Ton pseudo (alerte)"), "my_name", 20),
            (_("Mots surveilles (virgules)"), "keywords", 40),
            (_("Canaux masques (virgules)"), "hidden", 40),
        ]
        vars_ = {}
        for i, (lab, key, wd) in enumerate(fields):
            tk.Label(w, text=lab, bg=P, fg=T["fg"]).grid(row=i, column=0, sticky="w", padx=6, pady=3)
            v = tk.StringVar(value=str(self.cfg[key]))
            vars_[key] = v
            ent = tk.Entry(w, textvariable=v, width=wd, bg=T["entry"], fg=T["fg"],
                           insertbackground=T["fg"], relief="flat", highlightthickness=0)
            ent.grid(row=i, column=1, sticky="w", padx=6, pady=2, ipady=2)
            self._round(ent, 4, T["entry"], P)
        bools = [(_("Son pour les alertes"), "sound"), (_("Toujours au premier plan"), "topmost"),
                 (_("Afficher aussi les messages deja dans ta langue"), "show_french"),
                 (_("Se fermer quand WoW se ferme"), "autoclose"),
                 (_("Se cacher quand WoW n'est pas la fenetre active"), "follow_wow"),
                 (_("Langue de reponse automatique (dernier message etranger)"), "reply_lang_auto"),
                 (_("Se cacher quand un menu du jeu s'ouvre (menu du tchat, clic droit)"), "hide_on_menu"),
                 (_("Mises a jour automatiques (au lancement)"), "auto_update"),
                 (_("Bouton \u2713 ABC (correcteur d'orthographe, b\u00eata)"), "correcteur"),
                 (_("Cacher la bande de cases color\u00e9es (essai)"), "cover_band")]
        bv = {}
        row = len(fields)
        for lab, key in bools:
            dflt = (UI == "fr") if key == "correcteur" else DEFAULTS.get(key, True)   # correcteur : coche d'office en francais seulement
            v = tk.BooleanVar(value=bool(self.cfg.get(key, dflt)))
            bv[key] = v
            tk.Checkbutton(w, text=lab, variable=v, bg=P, fg=T["fg"], selectcolor=T["entry"],
                           activebackground=P, activeforeground=T["fg"], highlightthickness=0).grid(
                row=row, column=0, columnspan=2, sticky="w", padx=6)
            row += 1
        # curseurs aux couleurs du theme (avant : gris de Windows)
        st = ttk.Style()
        st.configure("Theme.Horizontal.TScale", background=T["accent"], troughcolor=T["btn_act"],
                     bordercolor=P, lightcolor=T["accent"], darkcolor=T["accent"], gripcount=0)
        st.map("Theme.Horizontal.TScale", background=[("active", T["accent_act"])])

        def slider(var, lo, hi, fmt, step):
            """Curseur aux couleurs du theme + sa valeur a droite (arrondie au pas)."""
            fr = tk.Frame(w, bg=P)
            val = tk.Label(fr, bg=P, fg=T["fg"], width=5, anchor="w")

            def show(*a):
                x = round(float(var.get()) / step) * step
                val.config(text=fmt % x)
            sc = ttk.Scale(fr, from_=lo, to=hi, orient="horizontal", variable=var, length=200,
                           style="Theme.Horizontal.TScale", command=show)
            sc.pack(side="left", pady=4)
            val.pack(side="left", padx=(8, 0))
            show()
            return fr
        av = tk.DoubleVar(value=float(self.cfg["alpha"]))
        tk.Label(w, text=_("Opacite"), bg=P, fg=T["fg"]).grid(row=row, column=0, sticky="w", padx=6)
        slider(av, 0.3, 1.0, "%.2f", 0.05).grid(row=row, column=1, sticky="w", padx=6)
        row += 1
        fv = tk.DoubleVar(value=int(self.cfg["font_size"]))
        tk.Label(w, text=_("Taille du texte"), bg=P, fg=T["fg"]).grid(row=row, column=0, sticky="w", padx=6)
        slider(fv, 8, 20, "%d", 1).grid(row=row, column=1, sticky="w", padx=6)
        row += 1
        tv = tk.StringVar(value=str(self.cfg.get("theme", "Sombre")) if self.cfg.get("theme") in THEMES else "Sombre")
        tk.Label(w, text=_("Theme"), bg=P, fg=T["fg"]).grid(row=row, column=0, sticky="w", padx=6, pady=3)
        theme_names = {_(k): k for k in THEMES}
        tshow = tk.StringVar(value=_(tv.get()))
        tshow.trace_add("write", lambda *a: tv.set(theme_names.get(tshow.get(), tv.get())))

        def theme_now(*a):
            """Theme applique des qu'on le choisit (avant : seulement apres "Enregistrer")."""
            name = tv.get()
            if name in THEMES and name != self.cfg.get("theme"):
                self.cfg["theme"] = name
                save_config(self.cfg)
                self.apply_theme(name)
                self._update_cover()
                try:
                    w.lift()                      # la fenetre Reglages reste devant
                except tk.TclError:
                    pass
        tv.trace_add("write", theme_now)
        om = tk.OptionMenu(w, tshow, *theme_names.keys())
        om.configure(bg=T["entry"], fg=T["fg"], activebackground=T["btn_act"], activeforeground=T["fg"],
                     relief="flat", highlightthickness=0, bd=0)
        om["menu"].configure(bg=T["entry"], fg=T["fg"], activebackground=T["btn_act"], activeforeground=T["fg"])
        om.grid(row=row, column=1, sticky="w", padx=6)
        self._round(om, 4, T["entry"], P)
        row += 1
        # langue de l'interface
        uv = tk.StringVar(value="English" if UI == "en" else "Fran\u00e7ais")
        tk.Label(w, text=_("Langue de l'interface"), bg=P, fg=T["fg"]).grid(row=row, column=0, sticky="w", padx=6, pady=3)
        um = tk.OptionMenu(w, uv, "Fran\u00e7ais", "English")
        um.configure(bg=T["entry"], fg=T["fg"], activebackground=T["btn_act"], activeforeground=T["fg"],
                     relief="flat", highlightthickness=0, bd=0)
        um["menu"].configure(bg=T["entry"], fg=T["fg"], activebackground=T["btn_act"], activeforeground=T["fg"])
        um.grid(row=row, column=1, sticky="w", padx=6)
        self._round(um, 4, T["entry"], P)
        row += 1

        def ok():
            global UI
            new_ui = "en" if uv.get() == "English" else "fr"
            ui_changed = new_ui != UI
            corr_changed = bool(bv["correcteur"].get()) != bool(self.cfg.get("correcteur", UI == "fr"))
            for k, v in vars_.items():
                self.cfg[k] = v.get().strip()
            for k, v in bv.items():
                self.cfg[k] = bool(v.get())
            self.cfg["alpha"] = round(round(float(av.get()) / 0.05) * 0.05, 2)
            self.cfg["font_size"] = int(round(float(fv.get())))
            self.cfg["target"] = self.cfg["target"] or UI
            if ui_changed:
                self.set_ui_lang(new_ui)
                UI = new_ui
            new_theme = tv.get() != self.cfg.get("theme", "Sombre") or ui_changed or corr_changed   # refait la fenetre
            self.cfg["theme"] = tv.get()
            self.text.configure(font=("Segoe UI", self.cfg["font_size"]))
            self.text.tag_configure("name", font=("Segoe UI", self.cfg["font_size"], "bold"))
            self.text.tag_configure("myname", font=("Segoe UI", self.cfg["font_size"], "bold"))
            self.apply_window_cfg()
            save_config(self.cfg)
            # langue automatique desactivee : on retire "(auto, d'apres ...)" reste affiche sous la case
            auto_txt = _("Langue de reponse : %s (auto, d'apres %s)").split("%s")[1]
            if not self.cfg.get("reply_lang_auto") and auto_txt in str(self.out_result.cget("text")):
                self.out_result.config(text="")
            w.destroy()
            if new_theme:
                self.apply_theme(self.cfg["theme"])
            self._update_cover()

        def on_chat():
            if self.place_on_chat():
                place_lbl.config(text="")
            else:
                place_lbl.config(text=_("Pas encore recu de ChatFR (1.9.4 ou plus) : reessaie dans 30 s."))
        pb = tk.Button(w, text=_("Placer sur le tchat de WoW"), command=on_chat, bg=T["entry"], fg=T["fg"],
                       activebackground=T["entry"], activeforeground=T["fg"], relief="flat", bd=0,
                       highlightthickness=0, padx=10, pady=4, cursor="hand2")
        pb.grid(row=row, column=0, sticky="w", padx=6, pady=(6, 0))
        self._round(pb, 5, T["entry"], P)
        place_lbl = tk.Label(w, text="", bg=P, fg=T["muted"], wraplength=300, justify="left")
        place_lbl.grid(row=row, column=1, sticky="w", padx=6, pady=(6, 0))
        row += 1
        sb_ = tk.Button(w, text=_("Enregistrer"), command=ok, bg=T["accent"], fg=T["accent_fg"],
                        activebackground=T["accent_act"], activeforeground=T["accent_fg"],
                        relief="flat", bd=0, highlightthickness=0, padx=16, pady=5, cursor="hand2",
                        font=("Segoe UI", 9, "bold"))
        sb_.grid(row=row, column=0, columnspan=2, pady=10)
        self._round(sb_, 5, T["accent"], P)

    # ---- lecture du log (thread) ------------------------------------------
    def reader(self):
        f = None
        path = None
        buf = ""
        while not self.stop:
            if str(self.cfg.get("source", "pont")).strip().lower() != "log":
                if f:
                    f.close()
                    f = None
                time.sleep(1)
                continue
            try:
                want = self.cfg["log_path"].strip().strip('"').strip()
                if f is None or want != path:
                    if f:
                        f.close()
                        f = None
                    path = want
                    if not os.path.exists(path):
                        self.outq.put(("status", _("Log introuvable : %s (tape /chatlog dans WoW)") % path))
                        time.sleep(2)
                        continue
                    f = open(path, "r", encoding="utf-8", errors="replace")
                    f.seek(0, os.SEEK_END)
                    buf = ""
                    self.outq.put(("status", _("En ecoute...")))
                chunk = f.read()
                if chunk:
                    buf += chunk
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        self.nlines += 1
                        p = parse(line)
                        if p:
                            self.nparsed += 1
                            self.inq.put(p)
                        self.outq.put(("status", _("En ecoute... (%d lignes lues, %d messages)")
                                       % (self.nlines, self.nparsed)))
                else:
                    st = os.stat(path)
                    if st.st_size < f.tell():  # fichier recree
                        f.close()
                        f = None
                    now = time.time()
                    if now - getattr(self, "_last_diag", 0) >= 1:
                        self._last_diag = now
                        self.outq.put(("status", _("En ecoute... %d lignes, %d msg | log %d Ko, ecrit il y a %ds")
                                       % (self.nlines, self.nparsed, st.st_size // 1024,
                                          max(0, int(now - st.st_mtime)))))
                    time.sleep(0.25)
            except Exception as e:  # noqa
                self.outq.put(("status", _("Erreur lecture : %s") % e))
                f = None
                time.sleep(2)

    # ---- pont image : lecture de la bande de couleur par capture d'ecran ---------
    def bridge_reader(self):
        if os.name != "nt":
            return
        off, last_seq, seen_first, bad, nmsg, last_status, stuck = None, None, False, 0, 0, 0.0, 0
        band_rect = None          # place de la bande sur l'ecran (pour le cache-bande)
        while not self.stop:
            if str(self.cfg.get("source", "pont")).strip().lower() != "pont":
                time.sleep(1)
                continue
            try:
                org = wow_client_origin()
                if org is None:
                    if band_rect is not None:
                        band_rect = None
                        self.outq.put(("bandrect", None))
                    self.outq.put(("status", _("Pont image : fenetre WoW introuvable")))
                    off = None
                    time.sleep(1)
                    continue
                x, y = org
                if off is None:
                    sw, sh = int(B_COLS * B_PMAX) + B_SEARCH, int(B_ROWS * B_PMAX) + B_SEARCH
                    cap = grab(x, y, sw, sh)
                    off = locate_bridge(cap, sw, sh)
                    if off is None:
                        pct, avg = capture_stats(cap)
                        try:
                            save_bmp(os.path.join(HERE, "debug_pont.bmp"), cap, sw, sh)
                        except OSError:
                            pass
                        self.outq.put(("status", _("Pont image : signal absent | WoW en (%d,%d) | capture %d%% non noire, moy %s | voir debug_pont.bmp")
                                       % (x, y, pct, avg)))
                        time.sleep(2)
                        continue
                ox, oy, p = off
                gx, gy = int(ox), int(oy)
                bw, bh = int(B_COLS * p) + 3, int(B_ROWS * p) + 3
                buf = grab(x + gx, y + gy, bw, bh)
                res = decode_bridge(buf, bw, ox - gx, oy - gy, p)
                if res is None:
                    bad += 1
                    if bad > 25 and getattr(self, "_cover_shown", False):
                        # illisible juste apres la pose du cache-bande : Windows ne l'ignore pas a la capture
                        since = time.time() - getattr(self, "_cover_since", 0)
                        if since < 8 and not getattr(self, "_cover_ok", False):           # ce que la capture a vu (noir ? le rectangle ?) pour comprendre
                            try:
                                save_bmp(os.path.join(os.path.dirname(ERROR_LOG), "debug_cache_bande.bmp"),
                                         buf, bw, bh)
                                pct, avg = capture_stats(buf)
                                log_error("cache-bande : capture illisible", "%d%% non noir, moyenne %s"
                                          % (pct, avg), tb=False)
                            except Exception:  # noqa
                                pass
                        # "fail" seulement si le rectangle n'a JAMAIS marche dans la session : un ecran de chargement
                        # ou un /reload juste apres sa pose le desactivait a tort
                        broken = since < 8 and not getattr(self, "_cover_ok", False)
                        self.outq.put(("bandrect", "fail" if broken else None))
                        self._cover_shown = False
                        band_rect = None
                    if bad > 25:        # bande illisible, deplacee ou disparue : on la recherche (et on remesure les cases)
                        off, bad = None, 0
                        stuck += 1
                        if stuck >= 3:  # toujours illisible apres plusieurs recherches : on le dit
                            self.outq.put(("status", _("Pont image : bande illisible (cases de %.2f px au lieu de 6) | mets la Resolution du jeu = celle de l'ecran et l'Echelle de rendu a 100 %%") % p))
                    time.sleep(0.03)
                    continue
                stuck = 0
                bad = 0
                if getattr(self, "_cover_shown", False) and time.time() - getattr(self, "_cover_since", 0) > 2:
                    self._cover_ok = True       # lu a travers le rectangle : Windows le gere bien
                rect = (int(round(x + ox)), int(round(y + oy)), int(round(B_COLS * p)), int(round(B_ROWS * p)))
                # le rectangle reste meme quand un autre programme passe devant WoW ;
                # il ne part que si WoW est reduit ou ferme
                if rect != band_rect:
                    band_rect = rect
                    self.outq.put(("bandrect", rect))
                seq, payload = res
                if seq != last_seq:
                    last_seq = seq
                    if not seen_first:
                        seen_first = True      # paquet deja affiche avant le lancement : ignore
                    elif payload:
                        p = parse_bridge_record(payload)
                        if p and p[1] == "tip":
                            self.outq.put(("tip", p[3], p[2]))
                        elif p and p[1] == "geo":
                            self.outq.put(("geo", p[2], x, y))
                        elif p and p[1] == "ui":
                            self.outq.put(("wowmenu", p[2] == "1"))
                        elif p and p[1] == "ver":
                            self.outq.put(("chatfr_ver", p[2]))
                        elif p:
                            nmsg += 1
                            self.nparsed += 1
                            self.inq.put(p)
                now = time.time()
                if now - last_status >= 1:
                    last_status = now
                    self.outq.put(("status", _("Pont image : OK (%d messages recus)") % nmsg))
                time.sleep(0.04)
            except Exception as e:  # noqa
                self.outq.put(("status", _("Pont image : erreur %s") % e))
                off = None
                time.sleep(2)

    # ---- se cacher quand WoW n'est pas la fenetre active ---------------------
    def watch_front(self):
        last, same = None, 0
        while not self.stop:
            time.sleep(0.4)
            if not self.cfg.get("follow_wow", True):
                if last is False:
                    self.outq.put(("wowfront", True))   # option coupee : on se remontre
                last = None
                continue
            f = wow_in_front()
            if f is None:
                continue
            same = same + 1 if f == last else 1
            if same == 2 or (f and same == 1 and last is False):   # 2 lectures pour cacher, 1 pour revenir
                self.outq.put(("wowfront", f))
            last = f

    # ---- fermeture automatique quand WoW se ferme ---------------------------
    def watch_wow(self):
        seen, missing = False, 0
        while not self.stop:
            time.sleep(1)
            if not self.cfg.get("autoclose", True):
                continue
            # La fenetre du jeu fait foi (le nom du .exe de Forever n'est pas fiable).
            r = wow_window_exists()
            if r is None:
                continue
            if r:
                seen, missing = True, 0
            elif seen:
                missing += 1
                if missing >= 2:      # ~2-3 s sans WoW
                    self.outq.put(("quit",))
                    return

    # ---- traduction (thread) ----------------------------------------------
    def worker(self):
        """Traite les messages un par un. Si un message fait planter le traitement, on note l'erreur
        (erreurs.txt) et on passe au suivant : avant, un seul message bloquait tout jusqu'au redemarrage."""
        while not self.stop:
            try:
                item = self.inq.get(timeout=0.5)
            except queue.Empty:
                continue
            self._busy = (time.time(), item)
            try:
                self.handle_message(*item)
            except Exception:  # noqa
                log_error("traitement du message", item)
            finally:
                self._busy = None

    def handle_message(self, hhmm, kind, chan, author, text):
        me_mark = chan.endswith("\u00a0")          # ChatFR marque tes propres messages
        chan = chan.rstrip("\u00a0")
        cfg = self.cfg
        raw = clean_questie(replace_raid_marks(wow_grammar(text)))
        text, _spans = split_links(raw)
        low_chan = chan.lower()
        hidden = [h.strip().lower() for h in cfg["hidden"].split(",") if h.strip()]
        if any(h in low_chan for h in hidden):
            return
        if kind in NO_TRANSLATE:
            # PNJ, systeme, butin : texte du jeu, deja dans sa langue -> affiche tel quel
            self.outq.put(("msg", hhmm, kind, chan, author, text, None, "?", False, False, raw))
            return
        me = cfg["my_name"].strip().lower()
        mine = me_mark or (bool(me) and author.lower() == me)
        if mine and author:
            OWN_NAMES.add(author)
        low = text.lower()
        alert = False
        if not mine:
            if me and me in low:
                alert = True
            for kw in cfg["keywords"].split(","):
                kw = kw.strip().lower()
                if kw and kw in low:
                    alert = True
        trans, lang = None, "?"
        # Liens ([Quete], [Objet]) : leur nom est deja dans la langue du jeu. On juge la langue et on
        # traduit SANS eux ("[Controler la population des raptors] lfm" n'est pas du francais) :
        # chaque lien devient un jeton remis tel quel apres Google.
        has_links = any(c for _, c in _spans)
        outside_links = "".join(seg for seg, code in _spans if not code)
        judge = outside_links if has_links else text
        link_segs = [seg for seg, code in _spans if code]
        gtext = "".join(seg if not code else "Zl%dx" % link_segs.index(seg) for seg, code in _spans) \
            if has_links else text
        if has_links:   # "[Enchantement]dispo" : jeton colle au mot -> Google ne lit plus "dispo"
            gtext = re.sub(r"(?<=\w)(Zl\d+x)", r" \1", re.sub(r"(Zl\d+x)(?=\w)", r"\1 ", gtext))

        def relink(t):
            if not t or not has_links:
                return t
            for i, seg in enumerate(link_segs):
                t = re.sub(r"Zl%dx" % i, lambda _m, sg=seg: sg, t, flags=re.I)
            return t
        lex = None
        if not mine and cfg["target"].lower() == "fr":
            lex = lexicon_full(judge.strip())
            outs = [seg for seg, code in _spans if not code and seg.strip()]
            if lex and has_links:
                # "[Quete] lfm" -> "[Quete] cherche du monde" (un seul morceau de texte hors liens)
                lex = relink(gtext.replace(outs[0].strip(), lex, 1)) if len(outs) == 1 else None
        if is_coin_only(text):
            pass                                   # "100 po" : affiche tel quel, sans traduction
        elif has_links and not worth_translating(outside_links):
            pass                                   # seulement des liens ("[Quete] ?") : rien a traduire
        elif lex and lex.strip().lower() == judge.strip().lower():
            lang = "fr"                            # "re" : mot deja compris en francais, rien a ajouter
        elif lex:
            trans, lang = lex, "en"           # lexique : pas d'appel a Google
        elif not mine and foreign_full(judge, cfg["target"]):
            trans, lang = foreign_full(judge, cfg["target"])      # "dobro dosly" -> "bienvenue"
        elif not mine and cfg["target"].lower() == "fr" and sure_french(judge):
            lang = "fr"                            # deja en francais : pas d'appel a Google
        elif not mine and cfg["target"].lower() == "en" and (lexicon_full(judge.strip()) or sure_english(judge)):
            lang = "en"                            # "lfm", "wts", "lfg/lfm" : jargon anglais, rien a traduire
        elif is_questie(judge):
            pass                                   # annonce de Questie : affichee telle quelle
        elif not mine and unknown_abbrev(judge):
            pass                                   # "lfr" : abreviation inconnue, affichee telle quelle
        elif not mine and worth_translating(judge):
            try:
                src_text = ru_slang(gtext)
                if cfg["target"].lower() != "fr":
                    src_text = fr_slang(src_text)      # argot francais ("pex", "slt", "tlm") avant Google
                if cfg["target"].lower() == "fr" and sure_english(judge):
                    # clairement anglais : abreviations developpees et noms proteges DES la 1re demande
                    # (avant : une demande pour apprendre "c'est de l'anglais", puis une 2e : 2x plus de 429)
                    trans, _x = google_translate_safe(lexicon_expand(gtext), cfg["target"], source="en")
                    lang, one_call = "en", True
                else:
                    trans, lang = google_translate(fr_mix_fix(src_text), cfg["target"])
                    one_call = False
                if one_call:
                    pass                               # deja traduit proprement en une seule demande
                elif lang == "en" and cfg["target"].lower() == "fr":
                    exp = lexicon_expand(gtext)
                    if exp != gtext or has_protected_name(gtext, cfg["target"]):
                        # abreviations / noms propres : on retraduit la phrase developpee
                        trans, _x = google_translate_safe(exp, cfg["target"], source="en")
                elif lang not in ("?", "") and has_protected_name(gtext, cfg["target"]):
                    trans, _x = google_translate_safe(gtext, cfg["target"], source=lang)
                if unreliable_detection(judge, lang):
                    # 2-3 mots, langue improbable (ex. "more for hogger" -> norvegien) :
                    # francais mal ecrit, sinon on reessaie en supposant de l'anglais
                    first = (trans, lang)
                    trans, lang = None, "?"
                    if looks_french(judge):
                        lang = "fr"
                    else:
                        t2, _x = google_translate_safe(lexicon_expand(gtext), cfg["target"], source="en")
                        if t2 and t2.strip().lower() != gtext.strip().lower():
                            trans, lang = t2, "en"
                        elif first[0] and first[0].strip().lower() != gtext.strip().lower():
                            # pas de l'anglais non plus ("A TE IR KADS LATVIETIS?" = letton) :
                            # on garde la premiere traduction de Google
                            trans, lang = first
                trans = relink(trans)
                trans = fix_words(judge, trans, lang)
            except Exception as e:  # noqa
                # affiche l'erreur sous le message (la barre d'etat est vite ecrasee par le pont)
                trans, lang = _("\u26a0 traduction impossible : %s") % err_text(e), "?"
        if trans and not trans.startswith("\u26a0") and near_same(trans, text):
            # "traduction" identique au message ("lfg/lfm" pris pour de l'allemand) : rien a traduire,
            # c'est deja lisible dans ta langue -> pas de ligne en double, badge de ta langue
            trans, lang = None, "?"     # pas de badge : on ne sait pas vraiment quelle langue c'etait
        if lang == "en" and re.search("[\u0400-\u04ff]", judge):
            lang = "ru"                            # "ЛФГ ТЮРЬМА" : jargon remplace, mais le joueur ecrit en russe
        self.outq.put(("msg", hhmm, kind, chan, author, text, trans, lang, alert, mine, raw))

    def check_update(self):
        """Une seule requete au demarrage. Sans Internet ou si GitHub ne repond pas : rien."""
        try:
            req = urllib.request.Request(VERSION_URL, headers={"User-Agent": "WoW-Traducteur"})
            with urllib.request.urlopen(req, timeout=8) as r:
                latest = r.read(32).decode("utf-8", "replace").strip()
            num = lambda v: tuple(int(x) for x in re.findall(r"\d+", v))
            if num(latest) and num(latest) > num(VERSION):
                self.outq.put(("update", latest))
        except Exception:
            pass

    def do_update(self):
        """Telecharge translator.py et le .bat de la release GitHub, les remplace (copie .old gardee)
        et relance le traducteur. Rien n'est remplace si un telechargement echoue."""
        latest = getattr(self, "latest", None)
        if not latest:
            return
        self.update_btn.config(text=_("T\u00e9l\u00e9chargement..."), state="disabled")

        def run():
            try:
                got = download_update(latest)
                code = got["translator.py"]
                # verification : bon numero de version et code Python valide, sinon on ne touche a rien
                if ('VERSION = "%s"' % latest).encode() not in code:
                    raise ValueError(_("fichier inattendu"))
                compile(code, "translator.py", "exec")
                for name, data in got.items():
                    path = os.path.join(HERE, name)
                    if os.path.exists(path):
                        shutil.copy2(path, path + ".old")
                    tmp = path + ".new"
                    with open(tmp, "wb") as f:
                        f.write(data)
                    os.replace(tmp, path)
                self.outq.put(("updated",))
            except Exception as e:  # noqa
                self.outq.put(("update_failed", err_text(e)))
        threading.Thread(target=run, daemon=True).start()

    def update_countdown(self, n):
        """Compte a rebours visible avant la relance (5, 4, 3...) : dans le bouton, la barre d'etat et
        sous la case Ecrire, pour qu'on ne croie pas a un plantage quand la fenetre se ferme."""
        self._updating = True
        if n <= 0:
            self.restart()
            return
        msg = _("Mise \u00e0 jour %s termin\u00e9e \u2713 Red\u00e9marrage dans %d s") % (getattr(self, "latest", ""), n)
        self.update_btn.config(text=msg, state="disabled")
        self.status.set(msg)
        try:
            self.out_result.config(text=msg + "  " + _("(le traducteur va se fermer puis se rouvrir tout seul)"),
                                   fg=self.T["name"])
        except tk.TclError:
            pass
        self.root.after(1000, lambda: self.update_countdown(n - 1))

    def restart(self):
        """Relance le traducteur (apres une mise a jour) puis ferme celui-ci."""
        try:
            exe = sys.executable
            if exe.lower().endswith("python.exe") and os.path.exists(exe[:-10] + "pythonw.exe"):
                exe = exe[:-10] + "pythonw.exe"                 # pas de fenetre noire
            env = dict(os.environ, WOWTRAD_UPDATED=VERSION)     # le nouveau traducteur dira "mis a jour"
            subprocess.Popen([exe, os.path.join(HERE, "translator.py")], cwd=HERE, env=env)
        except Exception:  # noqa
            pass
        self.on_close()

    # ---- affichage ---------------------------------------------------------
    def poll(self):
        try:
            while True:
                item = self.outq.get_nowait()
                try:
                    if self.poll_item(item):
                        return
                except Exception:  # noqa
                    log_error("affichage", item)
        except queue.Empty:
            pass
        self.check_stuck()
        self._poll_rest()

    def check_stuck(self):
        """Traitement bloque plus de 30 s sur le meme message (service de traduction qui ne repond
        plus...) : on le note une fois dans erreurs.txt."""
        busy = getattr(self, "_busy", None)
        if busy and time.time() - busy[0] > 30 and getattr(self, "_stuck_logged", None) is not busy:
            self._stuck_logged = busy
            log_error("traitement bloque depuis plus de 30 s", busy[1], tb=False)

    def poll_item(self, item):
        """Un element de la file d'affichage. Renvoie True si le traducteur se ferme."""
        if item[0] == "status":
            if not getattr(self, "_updating", False):   # pendant la mise a jour : on garde son message
                self.status.set(item[1])
        elif item[0] == "msg":
            self.show(*item[1:])
        elif item[0] == "quit":
            self.on_close()
            return True
        elif item[0] == "out":
            self.show_out(*item[1:])
        elif item[0] == "geo":
            self.on_geo(*item[1:])
        elif item[0] == "bandrect":
            self.on_bandrect(item[1])
        elif item[0] == "wowmenu":
            self.on_wow_menu(item[1])
        elif item[0] == "corrected":
            self.on_corrected(*item[1:])
        elif item[0] == "chatfr_ver":
            self.on_chatfr_ver(item[1])
        elif item[0] == "tip":
            key = item[1].strip().lower()
            self.tips.pop(key, None)
            self.tips[key] = [l for l in item[2].split("\x1e") if l.strip()]
            while len(self.tips) > 3000:              # garde les plus recents
                self.tips.pop(next(iter(self.tips)))
            if not self._tips_dirty:                  # enregistre au plus toutes les 5 s
                self._tips_dirty = True
                self.root.after(5000, self.save_tips)
        elif item[0] == "wowfront":
            self.follow_wow(item[1])
        elif item[0] == "update":
            self.latest = item[1]
            self.update_btn.config(text=_("Mettre \u00e0 jour (%s)") % item[1], state="normal")
            self.update_btn.pack(side="left", padx=3, pady=4, after=self._clear_btn)
            # mise a jour automatique : seulement ici, au lancement (jamais en pleine partie)
            if self.cfg.get("auto_update", True):
                self.add((_("Nouvelle version %s : mise \u00e0 jour automatique...") % item[1] + "\n", "news"))
                self.do_update()
        elif item[0] == "updated":
            # on le dit avant de fermer : sinon la fenetre qui disparait ressemble a un plantage
            self.add((_("Mise \u00e0 jour %s termin\u00e9e \u2713") % getattr(self, "latest", "") + "\n", "news"))
            self.update_countdown(10)
        elif item[0] == "update_failed":
            self.update_btn.config(text=_("Mise \u00e0 jour impossible : ouvrir la page"), state="normal",
                                   command=lambda: webbrowser.open(RELEASE_URL))
            self.status.set(_("Mise \u00e0 jour impossible : %s") % item[1])

    def _poll_rest(self):
        # menu ferme sans qu'on le sache (ChatFR repete "ouvert" toutes les 3 s) : on revient
        try:
            if getattr(self, "_menu_hidden", False) and time.time() - getattr(self, "_menu_last", 0) > 5:
                self.end_menu_hide()
        except Exception:  # noqa
            log_error("menu du jeu")
        self.root.after(100, self.poll)

    def show(self, hhmm, kind, chan, author, text, trans, lang, alert, mine, raw=None):
        tgt = self.cfg["target"].lower()
        same = (lang or "").lower().split("-")[0] == tgt
        if same and not self.cfg["show_french"] and not alert:
            return
        tag = kind          # tes messages aussi : couleur du canal, comme dans WoW (groupe = bleu)
        badge = "[%s] " % lang.upper() if lang not in ("?", "") and not mine else ""
        tail = chan if kind in ("channel", "lfg") else KIND_LABEL.get(kind, ("", ""))[UI == "en"]
        start_line = int(self.text.index("end-1c").split(".")[0])
        parts = [(hhmm + " ", "badge")]
        if badge:
            parts.append((badge, "badge"))
        if tail:
            parts.append(("(%s) " % tail, "badge"))
        marks = (tag, "alert") if alert else (tag,)
        ctag = self.class_tag(author)        # couleur de classe du joueur (si le jeu l'affiche)
        if author and kind != "temote":      # messages systeme / butin : pas d'auteur
            nm = ((author, *marks, "myname") if mine else (author, *marks) if kind in NO_TRANSLATE
                  else (author, *marks, "name"))
            parts.append(nm + ((ctag,) if ctag else ()))
            parts.append((" " if kind == "emote" else ": ", *marks))     # /e : "Malya danse.", comme dans WoW
        _plain, spans = split_links(raw if raw is not None else text)
        if kind == "temote" and ctag and author:   # "Malya salue Bob." : le nom colore dans la phrase
            spans = color_name_in(spans, author, ctag)
        coin = ("coins",) if kind in COIN_KINDS else ()
        icon = ping_icon(text) if kind == "ping" else None
        if icon:                                       # "Avertissement" -> "⚠ Avertissement", comme dans le jeu
            idx = int(icon[1][5:])
            if idx in PING_SHAPES:                     # Menace, Par ici : petit losange dessine, comme dans le jeu
                parts.append((icon[0], *marks, icon[1], "pingimg_%d" % idx))
                parts.append((" ", *marks))
            else:
                parts.append((icon[0] + " ", *marks, icon[1]))
        for seg, code in spans:
            if code and code.startswith("cls_"):
                parts.append((seg, *marks, code))
                continue
            parts.append((seg, *marks, "link_" + code) if code else (seg, *marks, *coin))
        parts.append(("\n", *marks))
        if trans and not same and trans.strip().lower() != text.strip().lower():
            tmarks = ("trans", "alert") if alert else ("trans",)
            parts.append(("\u2192 ", *tmarks))
            codes = [c for _, c in spans if c and not c.startswith("cls_")]
            for seg, code in color_brackets(trans, codes):
                parts.append((seg, *tmarks, "link_" + code) if code else (seg, *tmarks))
            parts.append(("\n", *tmarks))
        self.add(*parts)
        self.line_lang[start_line] = lang if not same else None
        if (not mine and not same and trans and lang not in ("?", "")
                and trans.strip().lower() != text.strip().lower()):
            self.auto_reply_lang(lang, author, kind)
        if alert:
            self.beep()

    def class_tag(self, author):
        """Tag de couleur de classe pour ce pseudo (cree au besoin), ou None."""
        col = NAME_COLS.get(author or "")
        if not col:
            return None
        if self.T.get("colors"):                     # theme clair : couleur assombrie pour rester lisible
            col = "#%02x%02x%02x" % tuple(int(int(col[i:i + 2], 16) * 0.55) for i in (1, 3, 5))
        tag = "cls_" + col[1:]
        self.text.tag_configure(tag, foreground=col)  # cree apres les autres : sa couleur prime
        return tag

    def auto_reply_lang(self, lang, author, kind):
        """Regle la langue de reponse sur celle du dernier message etranger recu.
        Un chuchotement reste prioritaire 60 s ; on ne change rien pendant que tu ecris."""
        if not self.cfg.get("reply_lang_auto", False) or self.out_entry.get().strip():
            return
        now = time.time()
        if kind != "whisper" and now - getattr(self, "_last_whisper", 0) < 60:
            return
        if kind == "whisper":
            self._last_whisper = now
        lang = lang.lower()
        if self.out_lang.get().strip().lower() != lang:
            self.out_lang.set(lang)
            self.out_result.config(text=_("Langue de reponse : %s (auto, d'apres %s)") % (lang, author), fg=self.T["muted"])

    def beep(self):
        if not self.cfg["sound"]:
            return
        try:
            if winsound:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            else:
                self.root.bell()
        except Exception:  # noqa
            pass

    # ---- ce que tu ecris --------------------------------------------------
    def clear_out(self):
        self.out_entry.delete(0, "end")
        self.out_result.config(text="", fg=self.T["muted"])
        self.out_entry.focus_set()

    def correct_out(self):
        """Bouton "Corriger" : remplace le texte de la case par sa version corrigee (pas de traduction)."""
        txt = self.out_entry.get().strip()
        if not txt:
            return
        self.out_result.config(text=_("Correction en cours..."), fg=self.T["muted"])

        def run():
            done = []
            base, n0 = phonetic_fix(txt, done) if UI == "fr" else (txt, 0)   # 1) fautes "au son" de la liste
            try:
                keep = list(NAME_COLS) + [getattr(self, "reply_to", None) or ""]  # pseudos vus dans le tchat
                keep += list(OWN_NAMES) + [self.cfg.get("my_name", "").strip()]        # + ton propre pseudo
                fixed, n = correct_text(base, UI, keep=keep, keep_phrases=done)   # 2) correcteur en ligne
                self.outq.put(("corrected", txt, fixed, n0 + n, True))
            except Exception:  # noqa
                self.outq.put(("corrected", txt, base if n0 else None, n0, False))
        threading.Thread(target=run, daemon=True).start()

    def on_corrected(self, before, fixed, n, online=True):
        if fixed is None:
            self.out_result.config(text=_("Correcteur indisponible pour le moment."), fg=self.T["err"])
            return
        if self.out_entry.get().strip() != before:      # on a retape entre-temps : on ne touche a rien
            return
        self.out_entry.delete(0, "end")
        self.out_entry.insert(0, fixed)
        # la phrase corrigee est aussi copiee : pour un joueur francais, il n'y a plus qu'a coller.
        # (pour un etranger, "Traduire + copier" remplacera ensuite la copie par la traduction)
        to = getattr(self, "reply_to", None)
        self.root.clipboard_clear()
        self.root.clipboard_append("/w %s %s" % (to, fixed) if to else fixed)
        self.root.update()
        if not online:
            msg = _("\u2713 %d correction(s) de base (correcteur en ligne indisponible). Copi\u00e9 en fran\u00e7ais, sans traduction") % n
        elif n:
            msg = _("\u2713 %d correction(s). Copi\u00e9 en fran\u00e7ais, sans traduction (Ctrl+V dans WoW)") % n
        else:
            msg = _("\u2713 Aucune faute. Copi\u00e9 en fran\u00e7ais, sans traduction (Ctrl+V dans WoW)")
        self.out_result.config(text=msg, fg=self.T["ok"])

    def send_out(self):
        txt = self.out_entry.get().strip()
        lang = (self.out_lang.get() or "en").strip().lower()
        if not txt:
            return
        self.out_result.config(text=_("Traduction en cours..."), fg=self.T["muted"])

        def run():
            try:
                if lang == UI:      # reponse dans ta propre langue (joueur francais) : copie telle quelle
                    self.outq.put(("out", txt, txt, lang, None))
                    return
                # "coucou" seul : Google donne "cuckoo" (l'oiseau)
                m = re.fullmatch(r"(?i)\s*coucou+\s*([!.?]*)\s*", txt)
                if m and lang == "en" and UI == "fr":
                    res = ("Hi" if txt.strip()[:1].isupper() else "hi") + m.group(1)
                    self.outq.put(("out", txt, res, lang, None))
                    return
                # argot francais remis en mots normaux avant Google ("slt" donnait "pls", "lu" donnait "read")
                src = txt
                if UI == "fr" and not sure_english(txt):
                    m = re.fullmatch(r"(?i)\s*lu+\s*([!.?]*)\s*", txt)   # "lu" seul = salut (pas dans "j'ai lu")
                    src = ("salut" + m.group(1)) if m else fr_slang(txt)
                # tu ecris en francais : on le dit a Google (sinon "bonjour" seul est pris pour de l'anglais).
                # Mais une phrase clairement dans une autre langue (allemand recopie...) : detection auto,
                # sinon Google la lit comme du francais et invente une traduction.
                res = None
                native = looks_french(src) if UI == "fr" else sure_english(src)
                if not native and len(re.findall(r"\w+", src)) >= 3:
                    try:
                        r2, det = google_translate(src, lang)
                        if (det or "").lower().split("-")[0] not in ("", "?", UI):
                            res = r2
                    except Exception:  # noqa
                        res = None
                if res is None:
                    res, _x = translate_out(src, lang, UI)
                check = None
                if res.strip().lower() == txt.strip().lower():
                    res, _x = google_translate(txt, lang)   # pas dans ta langue finalement : detection auto
                    if res.strip().lower() == txt.strip().lower() and lang != UI:
                        # deja ecrit dans la langue cible ("you speak english") : on montre le sens
                        # en francais pour verifier, mais c'est bien ton texte qui est copie
                        try:
                            check, _x = google_translate(txt, UI, source=lang)
                            if check.strip().lower() == txt.strip().lower():
                                check = None
                        except Exception:  # noqa
                            check = None
                # un service de secours renvoie parfois tout en MAJUSCULES ("Merci" -> "THANKS")
                if res.isupper() and not txt.isupper():
                    res = res.lower()
                    if txt[:1].isupper():
                        res = res[:1].upper() + res[1:]
                self.outq.put(("out", txt, res, lang, None, check))
            except Exception as e:  # noqa
                self.outq.put(("out", txt, "", lang, str(e)))

        threading.Thread(target=run, daemon=True).start()

    def show_out(self, src, res, lang, err, check=None):
        if err:
            self.out_result.config(text=_("Erreur : %s") % err, fg=self.T["err"])
            return
        to = getattr(self, "reply_to", None)
        copy = "/w %s %s" % (to, res) if to else res
        self.root.clipboard_clear()
        self.root.clipboard_append(copy)
        self.root.update()
        self.out_result.config(text=_("Copie ! (Entree, Ctrl+V, Entree dans WoW)  %s") % copy, fg=self.T["ok"])
        who = _("Vous \u2192 %s ") % to if to else _("Vous \u2192 ")
        if check:
            self.add((who + "[%s] " % lang.upper(), "me"), (src + "\n", "me"),
                     (_("\u2192 (en fran\u00e7ais : %s)") % check + "\n", "trans"))
        elif res.strip().lower() == src.strip().lower():   # meme langue : pas de ligne en double
            self.add((who + "[%s] " % lang.upper(), "me"), (src + "\n", "me"))
        else:
            self.add((who + "[%s] " % lang.upper(), "me"), (src + "\n", "me"), ("\u2192 " + res + "\n", "trans"))
        self.out_entry.delete(0, "end")
        self.cfg["out_lang"] = lang
        save_config(self.cfg)

    # ---- fenetre sans cadre : deplacement / redimensionnement -------------
    def follow_wow(self, front):
        """WoW plus au premier plan -> on se cache ; WoW revient -> on revient (sauf si tu avais
        reduit le traducteur toi-meme avec son bouton)."""
        if not front:
            self.close_tip()
            if not self._minimized and not getattr(self, "_auto_hidden", False):
                self._save_geometry()
                self._auto_hidden = True
                self.root.withdraw()
        elif getattr(self, "_auto_hidden", False):
            self._auto_hidden = False
            if not getattr(self, "_menu_hidden", False):     # un menu du jeu est encore ouvert : on attend
                self.root.deiconify()
                self.apply_window_cfg()

    def _corner_img(self, *args, **kw):
        cache = self.__dict__.setdefault("_corner_cache", {})
        key = (args, tuple(sorted(kw.items())))
        if key not in cache:
            cache[key] = tk.PhotoImage(data=base64.b64encode(corner_png(*args, **kw)).decode("ascii"),
                                       format="png")
        return cache[key]

    def _round(self, w, r, inside, outside):
        """Arrondit les 4 coins d'un bouton : 4 petites images posees dans ses coins (tkinter n'arrondit pas)."""
        for c in ("nw", "ne", "sw", "se"):
            try:
                img = self._corner_img(r, inside, outside, c)
            except tk.TclError:
                return
            # image posee PAR-DESSUS le bouton (a cote de lui, pas dedans) : sous Windows, un vrai bouton
            # se dessine au-dessus de ce qu'il contient, les coins mis dedans restaient invisibles
            lab = tk.Label(w.master, image=img, bd=0, padx=0, pady=0, highlightthickness=0, cursor="hand2")
            lab.place(in_=w, relx=1 if c[1] == "e" else 0, rely=1 if c[0] == "s" else 0, anchor=c)
            lab.lift(w)
            if isinstance(w, tk.Button):
                lab.bind("<ButtonRelease-1>", lambda e, b=w: b.invoke())

    # ---- cache-bande : rectangle par-dessus la bande de cases colorees ---------
    def on_bandrect(self, rect):
        if rect == "fail":
            self._cover_broken = True
            self._band_rect = None
            self._update_cover()
            try:
                self.out_result.config(text=_("Cache-bande d\u00e9sactiv\u00e9 : Windows ne permet pas de le cacher \u00e0 la capture (Windows trop ancien ?)."),
                                       fg=self.T["muted"])
            except tk.TclError:
                pass
            return
        self._band_rect = rect
        self._update_cover()

    def _update_cover(self):
        """Pose, deplace ou retire le rectangle. Il est invisible pour la capture d'ecran
        (SetWindowDisplayAffinity, Windows 10 2004+) : le traducteur lit la bande a travers."""
        cov = getattr(self, "_cover", None)
        rect = getattr(self, "_band_rect", None)
        want = (os.name == "nt" and rect and self.cfg.get("cover_band", False)
                and not getattr(self, "_cover_broken", False))
        if not want:
            if cov is not None:
                try:
                    cov.withdraw()
                except tk.TclError:
                    pass
            self._cover_shown = False
            return
        x, y, w, h = rect
        if cov is None or not cov.winfo_exists():
            T = self.T
            cov = tk.Toplevel(self.root)
            cov.overrideredirect(True)
            cov.configure(bg=T["bar"], highlightthickness=0)
            # dessin : rectangle aux coins arrondis + "ChatFR" (refait quand la taille change)
            cv = tk.Canvas(cov, bg=T["bar"], highlightthickness=0, bd=0)
            cv.pack(fill="both", expand=True)
            cov._cv = cv
            cov.attributes("-topmost", True)
            cov.geometry("%dx%d+%d+%d" % (w + 4, h + 4, x - 2, y - 2))
            cov.update_idletasks()
            ok = False
            try:
                u = ctypes.windll.user32
                u.GetParent.restype, u.GetParent.argtypes = ctypes.c_void_p, [ctypes.c_void_p]
                hwnd = u.GetParent(cov.winfo_id()) or cov.winfo_id()
                get = getattr(u, "GetWindowLongPtrW", None) or u.GetWindowLongW
                put = getattr(u, "SetWindowLongPtrW", None) or u.SetWindowLongW
                get.restype, get.argtypes = ctypes.c_ssize_t, [ctypes.c_void_p, ctypes.c_int]
                put.restype, put.argtypes = ctypes.c_ssize_t, [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
                # jamais le clavier, pas de bouton dans la barre des taches.
                # (2e essai : plus de fenetre "en couches" / clics au travers, qui peuvent empecher Windows
                # de la retirer de la capture)
                put(hwnd, -20, get(hwnd, -20) | 0x08000000 | 0x80)
                u.SetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, ctypes.c_uint]
                ok = bool(u.SetWindowDisplayAffinity(hwnd, 0x11))      # WDA_EXCLUDEFROMCAPTURE
                cov._hwnd = hwnd
            except Exception:  # noqa
                ok = False
            if not ok:                      # Windows trop ancien : on n'insiste pas
                cov.destroy()
                self._cover, self._cover_broken, self._cover_shown = None, True, False
                return
            self._cover = cov
        else:
            cov.geometry("%dx%d+%d+%d" % (w + 4, h + 4, x - 2, y - 2))
        self._draw_cover(cov, w + 4, h + 4)
        if not getattr(self, "_cover_shown", False):
            cov.deiconify()
            cov.lift()
            self._cover_since = time.time()
            self._cover_shown = True

    def _draw_cover(self, cov, W, H):
        """Coins arrondis du cache-bande : forme de la fenetre arrondie (SetWindowRgn, pas une fenetre
        "en couches" qui empecherait de la cacher a la capture) + liseré dessine le long de l'arrondi."""
        if getattr(cov, "_drawn", None) == (W, H):
            return
        cov._drawn = (W, H)
        T, r = self.T, 10
        cv = cov._cv
        cv.delete("all")
        pts = []                       # contour : 4 quarts de cercle de rayon r, reperes par leurs centres
        for cx, cy, a0 in ((W - 1 - r, r, -90), (W - 1 - r, H - 1 - r, 0), (r, H - 1 - r, 90), (r, r, 180)):
            for k in range(7):
                a = math.radians(a0 + k * 15)
                pts += [cx + (r - 0.5) * math.cos(a), cy + (r - 0.5) * math.sin(a)]
        cv.create_polygon(pts, fill=T["bar"], outline=T["border"], width=1)
        cv.create_text(W // 2, H // 2, text="ChatFR", fill=T["status"], font=("Segoe UI", 8))
        try:
            g, u = ctypes.windll.gdi32, ctypes.windll.user32
            g.CreateRoundRectRgn.restype = ctypes.c_void_p
            rgn = g.CreateRoundRectRgn(0, 0, W + 1, H + 1, 2 * r, 2 * r)
            u.SetWindowRgn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
            u.SetWindowRgn(cov._hwnd, rgn, 1)          # Windows garde la forme (pas a liberer)
        except Exception:  # noqa
            pass

    def _color_titlebar(self, win):
        """Barre de titre Windows aux couleurs du theme (Windows 11 ; ailleurs, rien ne change)."""
        if not sys.platform.startswith("win"):
            return
        try:
            win.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
            dwm = ctypes.windll.dwmapi
            def bgr(h):
                h = h.lstrip("#")
                return int(h[4:6] + h[2:4] + h[0:2], 16)
            light = sum(int(self.T["bar"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) > 384
            dark = ctypes.c_int(0 if light else 1)
            dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))   # mode sombre
            for attr, col in ((35, self.T["bar"]), (36, self.T["fg"]), (34, self.T["border"])):
                c = ctypes.c_uint(bgr(col))                  # 35 fond, 36 texte, 34 bordure
                dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(c), ctypes.sizeof(c))
        except Exception:  # noqa  (Windows 10 ou plus ancien : barre normale)
            pass

    def _round_window(self):
        """Coins arrondis de la fenetre (cadre compris). Bas : couleur du fond, ou de la barre si repliee."""
        T = self.T
        bw = int(T["border_w"])
        rolled = bool(getattr(self, "_rolled", None))
        for lab in getattr(self, "_win_corners", []):
            try:
                lab.destroy()
            except tk.TclError:
                pass
        self._win_corners = []
        for c in ("nw", "ne", "sw", "se"):
            inside = T["bar"] if (c[0] == "n" or rolled) else T["bg"]
            try:
                img = self._corner_img(10, inside, WIN_HOLE, c, ring=T["border"], ring_w=bw, hard_out=True)
            except tk.TclError:
                return
            lab = tk.Label(self.root, image=img, bd=0, padx=0, pady=0, highlightthickness=0)
            lab.place(relx=1 if c[1] == "e" else 0, rely=1 if c[0] == "s" else 0,
                      x=bw if c[1] == "e" else -bw, y=bw if c[0] == "s" else -bw, anchor=c)
            self._win_corners.append(lab)

    def minimize(self):
        """Bouton "—" : replie la fenetre sur sa seule barre du haut ; un 2e clic la deplie.
        (Avant : reduction dans la barre des taches. Mais une fenetre qui ne prend pas le clavier a WoW
        n'y a pas de bouton : reduite, on ne la retrouvait plus, et elle grandissait a chaque retour.)"""
        if getattr(self, "_rolled", None):
            geo, self._rolled = self._rolled, None
            self.root.minsize(MIN_W, MIN_H)
            self.root.geometry(geo)
            self._minb.config(text="\u2014")
            self._round_window()
            self._save_geometry()
            return
        self._save_geometry()
        self.close_tip()
        self._rolled = self.root.geometry()
        self.root.update_idletasks()
        h = self._bar.winfo_height() + 2 * int(self.T["border_w"])
        self.root.minsize(MIN_W, 1)
        self.root.geometry("%dx%d" % (self.root.winfo_width(), max(h, 20)))
        self._minb.config(text="\u25a2")
        self._round_window()

    def _on_map(self, e):
        # remettre le cadre Windows fait reapparaitre la fenetre un instant, juste avant la reduction :
        # ce n'est pas un vrai retour (le journal le montrait), on l'ignore
        if e.widget is self.root and self._minimized and (
                time.time() - getattr(self, "_min_at", 0) < 0.7 or self.root.state() != "normal"):
            return
        if e.widget is self.root and self._minimized:
            self._minimized = False
            self.root.overrideredirect(True)
            # le cadre Windows remis pour la reduction agrandissait la fenetre a chaque fois (sa bordure
            # et sa barre de titre s'ajoutaient) : on remet la taille et la place d'avant la reduction,
            # plusieurs fois (Windows termine sa restauration apres l'evenement) sans rien enregistrer entre-temps
            geo = getattr(self, "_pre_min_geo", "") or str(self.cfg.get("geometry", ""))
            self._restoring_until = time.time() + 1.0
            if re.match(r"^\d+x\d+\+-?\d+\+-?\d+$", geo):
                for ms in (0, 60, 250, 600):
                    self.root.after(ms, lambda g=geo: self.root.geometry(g))
                self.root.after(900, lambda g=geo: self._force_save_geometry(g))
            self.apply_window_cfg()
            self.root.after(100, lambda: self.set_noactivate(True))

    def draw_lock(self):
        """Cadenas ferme (couleur d'accent) ou ouvert (gris)."""
        cv, locked = self.lock_cv, bool(self.cfg.get("locked"))
        cv.delete("all")
        col = self.T["label_fg"] if self.T["emblem"] else self.T["icon"]
        col = col if locked else self.T["status"]
        cv.create_rectangle(6, 10, 17, 19, fill=col, outline=col)            # corps
        if locked:
            cv.create_arc(7, 3, 16, 14, start=0, extent=180, style="arc", outline=col, width=2)
            cv.create_line(8, 8, 8, 11, fill=col, width=2)
            cv.create_line(15, 8, 15, 11, fill=col, width=2)
        else:                                                                 # anse levee et decalee
            cv.create_arc(10, 1, 19, 12, start=0, extent=180, style="arc", outline=col, width=2)
            cv.create_line(18, 6, 18, 9, fill=col, width=2)
        cv.create_rectangle(11, 13, 12, 16, fill=self.T["bar"], outline=self.T["bar"])   # trou de serrure

    def toggle_lock(self):
        self.cfg["locked"] = not self.cfg.get("locked")
        save_config(self.cfg)
        self.draw_lock()
        self.status.set(_("Fenetre verrouillee") if self.cfg["locked"] else _("Fenetre deverrouillee"))

    def _drag_start(self, e):
        self._dx, self._dy = e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y()

    def _drag_move(self, e):
        if self.cfg.get("locked"):
            return
        self.root.geometry("+%d+%d" % (e.x_root - self._dx, e.y_root - self._dy))

    def _resize_start(self, e):
        self._rx, self._ry = e.x_root, e.y_root
        self._rw, self._rh = self.root.winfo_width(), self.root.winfo_height()

    def _resize_move(self, e):
        if self.cfg.get("locked") or getattr(self, "_rolled", None):
            return
        w = max(MIN_W, self._rw + e.x_root - self._rx)
        h = max(MIN_H, self._rh + e.y_root - self._ry)
        self.root.geometry("%dx%d" % (w, h))

    def on_geo(self, data, ox, oy):
        """Place du tchat de WoW envoyee par ChatFR (pixels de l'image du jeu) -> pixels de l'ecran."""
        try:
            l, t, w, h, ph = [int(v) for v in data.split(",")]
        except ValueError:
            return
        ch = wow_client_height()
        k = ch / ph if ch and ph > 0 else 1.0           # jeu etire a l'ecran (resolution personnalisee)
        self.last_geo = (int(ox + l * k), int(oy + t * k), max(MIN_W, int(w * k)), max(MIN_H, int(h * k)))
        if self.geo_auto:
            self.geo_auto = False
            self.place_on_chat()

    def on_wow_menu(self, open_):
        """Menu du jeu ouvert (menu du tchat, clic droit...) : on s'efface pour ne pas le cacher."""
        if open_:
            self._menu_last = time.time()
            if (self.cfg.get("hide_on_menu", True) and not getattr(self, "_menu_hidden", False)
                    and not self._minimized and not getattr(self, "_auto_hidden", False)):
                self.close_tip()
                self._save_geometry()
                self._menu_hidden = True
                self.root.withdraw()
        else:
            self.end_menu_hide()

    def end_menu_hide(self):
        if getattr(self, "_menu_hidden", False):
            self._menu_hidden = False
            if not getattr(self, "_auto_hidden", False):
                self.root.deiconify()
                self.apply_window_cfg()

    def place_on_chat(self):
        if not self.last_geo:
            return False
        x, y, w, h = self.last_geo
        self.root.geometry("%dx%d+%d+%d" % (w, h, x, y))
        self._save_geometry()
        return True

    def _save_geometry(self):
        if getattr(self, "_minimized", False) or time.time() < getattr(self, "_restoring_until", 0):
            return                     # pendant une reduction / un retour : taille pas encore la bonne
        if getattr(self, "_rolled", None):
            return                     # repliee sur sa barre : on garde la taille depliee
        try:
            self.cfg["geometry"] = self.root.geometry()
            save_config(self.cfg)
        except tk.TclError:
            pass

    def _force_save_geometry(self, geo):
        self.cfg["geometry"] = geo
        save_config(self.cfg)

    def _add_hint(self, widget, text):
        """Au survol d'un bouton : explication sur la ligne d'info (une ligne), puis on remet l'ancien message."""
        def on(_e):
            self._hint_prev = (self.out_result.cget("text"), self.out_result.cget("fg"))
            self.out_result.config(text=text, fg=self.T["muted"])

        def off(_e):
            try:                                     # vraiment sortie ? (evite un clignotement si la fenetre bouge)
                if self.root.winfo_containing(*self.root.winfo_pointerxy()) is widget:
                    return
            except Exception:  # noqa
                pass
            prev = getattr(self, "_hint_prev", None)
            if prev and self.out_result.cget("text") == text:
                self.out_result.config(text=prev[0], fg=prev[1])
        widget.bind("<Enter>", on, add="+")
        widget.bind("<Leave>", off, add="+")

    def _ph_update(self):
        """Affiche le texte d'aide gris quand la case "Ecrire" est vide et qu'on n'y ecrit pas."""
        try:
            show = not self.out_entry.get() and self.root.focus_get() is not self.out_entry
            if show and not self.out_ph.winfo_ismapped():
                self.out_ph.place(x=2, rely=0.5, anchor="w")
            elif not show and self.out_ph.winfo_ismapped():
                self.out_ph.place_forget()
        except Exception:  # noqa  (fenetre refaite : nouvelle case, on continue)
            pass
        self.root.after(150, self._ph_update)

    def _svc_tick(self):
        threading.Thread(target=svc_save, daemon=True).start()
        self.root.after(30000, self._svc_tick)

    def on_close(self):
        self.stop = True
        self.save_tips()
        svc_save()
        try:
            self.cfg["geometry"] = getattr(self, "_rolled", None) or self.root.geometry()
        except tk.TclError:
            pass
        save_config(self.cfg)
        self.root.destroy()


def main():
    if os.name == "nt":      # coordonnees en vrais pixels (necessaire pour lire la bande)
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:  # noqa
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:  # noqa
                pass
    if len(sys.argv) > 1:   # chemin du log en argument (optionnel)
        cfg = load_config()
        cfg["log_path"] = sys.argv[1]
        save_config(cfg)
    App().root.mainloop()


if __name__ == "__main__":
    main()
