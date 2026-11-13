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

try:
    import winsound
except ImportError:  # pas sous Windows
    winsound = None

VERSION = "1.9"
# Verification de mise a jour : le fichier version.txt du depot contient le numero de la derniere version.
VERSION_URL = "https://raw.githubusercontent.com/puenteur/Wow-traducteur/main/version.txt"
KOFI_URL = "https://ko-fi.com/puenteur"
# Fiche d'un objet / d'une quete cliques dans la fenetre (recherche par nom, en francais).
WOWHEAD_SEARCH = "https://www.wowhead.com/classic/fr/search?q="
RELEASE_URL = "https://github.com/puenteur/Wow-traducteur/releases/latest"

HERE = os.path.dirname(os.path.abspath(__file__))

# Nouveautes affichees une fois dans la fenetre apres une mise a jour (pas au premier lancement).
NEWS = {
    "fr": ["WoW Traducteur %s : maintenant aussi en anglais !" % VERSION,
           "- La grande nouveaut\u00e9 : tout le traducteur existe en anglais. Au premier lancement, on choisit Fran\u00e7ais ou English ; en anglais, le tchat est traduit vers l'anglais. Pratique pour tes amis anglophones ! (changeable dans les R\u00e9glages)",
           "- Pi\u00e8ces d'or, d'argent et de cuivre en ic\u00f4nes bien visibles, m\u00eame quand le jeu \u00e9crit \u00ab 25 Cuivre \u00bb.",
           "- Langue de r\u00e9ponse : une liste qui s'ouvre vers le haut (EN, DE, ES, puis Autre langue\u2026).",
           "- Fen\u00eatre des nouveaut\u00e9s apr\u00e8s chaque mise \u00e0 jour (celle-ci !).",
           "- Meilleures traductions : lfg/lfm, wts/wtb, Deadmines, jargon russe (\u041b\u0424\u0413), mots coll\u00e9s aux liens, petits messages en espagnol ou en letton, moins d'appels inutiles \u00e0 Google."],
    "en": ["WoW Traducteur %s: now in English!" % VERSION,
           "- The big one: the whole translator is now available in English. Choose Fran\u00e7ais or English at first launch; in English, the chat is translated into English (can be changed in Settings).",
           "- Gold, silver and copper coins shown as clear icons, even when the game writes \"25 Copper\".",
           "- Reply language: a list that opens upwards (FR, DE, ES, then Other language\u2026).",
           "- A window like this one after each update.",
           "- Better translations: French gamer slang (pex, slt, tlm, \"du monde ?\"), Russian jargon, lfg/lfm, words stuck to links, and fewer useless calls to Google."],
}
CONFIG_PATH = os.path.join(HERE, "translator_config.json")
TIPS_PATH = os.path.join(HERE, "infobulles.json")     # infobulles d'objets gardees entre deux lancements

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
    "auto_reply_lang": True,        # langue de reponse = langue du dernier message etranger
    "theme": "Sombre",              # theme de la fenetre (voir THEMES)
    "locked": False,                # cadenas : fenetre verrouillee (ni deplacement ni redimensionnement)
    "help_seen": False,             # fenetre d'aide deja montree une fois (premier lancement)
    "ui_lang": "",                  # langue de l'interface : "fr" ou "en" (choisie au premier lancement)
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
}
NO_TRANSLATE = ("npc", "system", "loot", "spent", "whisper_out", "faction", "ping")   # ping : texte du jeu
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
    "⚙ Réglages": "⚙ Settings",
    "Effacer": "Clear",
    "Clique sur un message pour repondre dans sa langue.": "Click a message to reply in its language.",
    "Autre langue…": "Other language…",
    "À %s (%s) →": "To %s (%s) →",
    "Ecrire (%s) →": "Write (%s) →",
    "Chuchotement à %s : ta reponse sera copiee avec /w %s": "Whisper to %s: your reply will be copied with /w %s",
    "Reponse normale (sans /w).": "Normal reply (no /w).",
    "(haut fait : le détail est sur Wowhead)": "(achievement: details are on Wowhead)",
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
    "⚠ traduction impossible : %s": "⚠ translation failed: %s",
    "Mise à jour %s dispo": "Update %s available",
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


def wow_grammar(text):
    """Codes de grammaire du client WoW : "|2 Stormwind" = "de Stormwind" / "d'Orgrimmar"."""
    if "|2" not in text:
        return text
    text = re.sub(r"\|2\s*(?=[AEIOUYHaeiouyh\u00c0-\u00c6\u00c8-\u00cf\u00d2-\u00d6\u00d9-\u00dc\u00e0-\u00e6\u00e8-\u00ef\u00f2-\u00f6\u00f9-\u00fc])", "d'", text)
    return re.sub(r"\|2\s*", "de ", text)
TRANS_COLOR = "#6fd3ff"
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
                               "whisper_out": "#a8327e", "faction": "#3a3ab0", "ping": "#1f5fae"},
                       links={"q": "#8a6a00", "q0": "#6e6e6e", "q1": "#1d7a00", "q2": "#8a6a00", "q3": "#b5530e", "q4": "#c0261f", "i0": "#6e6e6e", "i1": "#2b2416", "i2": "#1d7a00", "i3": "#0058b0",
                              "i4": "#7a2fc0", "i5": "#b85a00", "i6": "#8a7440", "i7": "#0080a8", "i8": "#0080a8",
                              "s": "#0070a8", "e": "#8a6a00", "a": "#8a7a00", "o": "#8a6a00"}),
    "Givre": dict(_SOMBRE, bg="#0f1d26", fg="#eaf8ff", bar="#09141b", btn="#173040", btn_act="#204257",
                  btn_fg="#cfeefc", accent="#2f7fa8", accent_act="#3a93c0", accent_fg="white",
                  border="#5fb6d9", border_w=2, icon="#9fd8f0", status="#7fa9bf", panel="#09141b",
                  entry="#173040", muted="#7fa9bf", trans="#9fe3ff", name="#ffd37a", badge="#7fa9bf",
                  scroll="#204257", scroll_act="#2c5873"),
}


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
"""


def draw_emblem(cv, kind):
    """Petit emblème original dessine dans un Canvas de 18x21 (coordonnees d'origine 84x96)."""
    k = 18 / 84.0

    def pts(seq):
        return [v * k for v in seq]
    if kind == "shield":
        cv.create_polygon(pts([8, 8, 76, 8, 76, 44, 72, 62, 60, 77, 42, 90, 24, 77, 12, 62, 8, 44]), fill="#c9a227", outline="")
        cv.create_polygon(pts([14, 14, 70, 14, 70, 44, 66, 60, 56, 72, 42, 83, 28, 72, 18, 60, 14, 44]), fill="#1d3a6e", outline="")
        cv.create_polygon(pts([42, 30, 46.5, 42.5, 59, 44, 49, 52, 52.5, 64.5, 42, 57, 31.5, 64.5, 35, 52, 25, 44, 37.5, 42.5]),
                          fill="#e8c55a", outline="")
    elif kind == "banner":
        cv.create_polygon(pts([16, 6, 68, 6, 68, 90, 42, 74, 16, 90]), fill="#b0702e", outline="")
        cv.create_polygon(pts([21, 11, 63, 11, 63, 81, 42, 68, 21, 81]), fill="#8e2219", outline="")
        cv.create_polygon(pts([42, 24, 50, 34, 53, 44, 51, 54, 46, 60, 42, 62, 38, 60, 33, 54, 32, 46, 35, 40, 38, 36,
                               40, 43, 42, 46, 41, 36]), fill="#e2913f", outline="", smooth=True)

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
    "rt1": "\u2605", "star": "\u2605", "etoile": "\u2605",
    "rt2": "\u25cf", "circle": "\u25cf", "rond": "\u25cf", "cercle": "\u25cf",
    "rt3": "\u25c6", "diamond": "\u25c6", "losange": "\u25c6",
    "rt4": "\u25b2", "triangle": "\u25b2",
    "rt5": "\u263e", "moon": "\u263e", "lune": "\u263e",
    "rt6": "\u25a0", "square": "\u25a0", "carre": "\u25a0",
    "rt7": "\u2716", "cross": "\u2716", "croix": "\u2716", "x": "\u2716",
    "rt8": "\u2620", "skull": "\u2620", "crane": "\u2620",
}
_MARK_RE = re.compile(r"\{(" + "|".join(sorted(RAID_MARKS, key=len, reverse=True)) + r")\}", re.I)


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
GT_PAUSE = 120             # secondes


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
            if e.code == 503:
                time.sleep(0.5)
                continue
            raise
        except (urllib.error.URLError, OSError, ValueError) as e:
            # coupure reseau, delai depasse, reponse tronquee : on reessaie aussi
            last_err = e
            time.sleep(0.5)
            continue
        out = "".join(seg[0] for seg in data[0] if seg and seg[0])
        lang = data[2] if len(data) > 2 and isinstance(data[2], str) else "?"
        with _gt_lock:
            if len(_gt_cache) > 500:
                _gt_cache.clear()
            _gt_cache[key] = (out, lang)
        return out, lang
    if getattr(last_err, "code", None) == 429:
        _gt_pause[0] = time.time() + GT_PAUSE
        raise RuntimeError("Google limite les requetes (429), pause de %d s" % GT_PAUSE)
    raise RuntimeError("Google ne repond pas (%s)" % (getattr(last_err, "reason", None) or last_err))


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


# Lingva : serveurs publics gratuits, sans compte, qui interrogent Google a notre place
# (ils passent donc meme quand Google bloque notre adresse). Serveurs de benevoles : ils tombent parfois.
LINGVA_HOSTS = ["lingva.ml", "lingva.lunar.icu", "translate.plausibility.cloud"]
_lingva_dead = {}          # serveur -> heure jusqu'a laquelle on ne l'essaie plus


def _lingva(text, target, source, timeout=4):
    last = None
    for host in LINGVA_HOSTS:
        if _lingva_dead.get(host, 0) > time.time():
            continue
        url = "https://%s/api/v1/%s/%s/%s" % (host, source, target, urllib.parse.quote(text, safe=""))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _GT_UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
            out = (data.get("translation") or "").strip()
            if not out:
                raise ValueError(data.get("error") or "reponse vide")
            det = (data.get("info") or {}).get("detectedSource") or (source if source != "auto" else "?")
            return out, str(det).lower().split("-")[0]
        except Exception as e:  # noqa
            last = e
            _lingva_dead[host] = time.time() + 600      # serveur en panne : on l'oublie 10 min
    raise RuntimeError("aucun serveur ne repond (%s)" % last if last else "serveurs en pause")


def google_translate(text, target, source="auto", timeout=8):
    """Google ; s'il bloque (429) ou ne repond pas : Lingva, puis MyMemory."""
    try:
        return _google(text, target, source, timeout)
    except RuntimeError as e:
        try:
            res = _lingva(text, target, source)
        except Exception as e1:  # noqa
            try:
                res = _mymemory(text, target, source, 5)
            except Exception as e2:  # noqa
                raise RuntimeError("%s ; Lingva : %s ; MyMemory : %s" % (e, e1, e2))
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
    'rfc': 'Gouffre de Ragefeu', 'ragefire chasm': 'Gouffre de Ragefeu', 'wc': 'Cavernes des lamentations',
    'wailing caverns': 'Cavernes des lamentations', 'vc': 'Mortemines',
    'dm': 'Mortemines (ou Hache-tripes)', 'deadmines': 'Mortemines', 'deadmine': 'Mortemines', 'sfk': "Donjon d'Ombrecroc",
    'shadowfang keep': "Donjon d'Ombrecroc", 'bfd': 'Profondeurs de Brassenoire',
    'blackfathom deeps': 'Profondeurs de Brassenoire', 'stockades': 'Les Cachots', 'stocks': 'Les Cachots',
    'the stockade': 'Les Cachots', 'stockade': 'Les Cachots', 'gnomer': 'Gnomeregan',
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
            "mob": "mob", "mobs": "mobs", "pull": "pull", "pulls": "pulls", "pulled": "pull"}   # chasseur, pas "chasse"   # "full for boss" -> "full pour le boss"
# Classes que Google traduit mal ("rogue" -> "voyou", "warlock" -> "sorcier") : nom francais du jeu.
LEX_CLASSES = {"rogue": "voleur", "rogues": "voleurs", "warlock": "démoniste", "warlocks": "démonistes"}
# "dm me" / "dm pls" = message prive, pas les Mortemines.
_PLACE_NOT_BEFORE = {"dm": r"(?!\s*(?:me|him|her|them|u|you|pls|plz)\b)"}


LEX_PLACES_FOREIGN = {
    # noms allemands et espagnols ("TODESMINE" = Mortemines)
    'todesminen': 'Mortemines', 'todesmine': 'Mortemines', 'burg schattenfang': "Donjon d'Ombrecroc",
    'das verlies': 'Les Cachots', 'verlies': 'Les Cachots', 'h\u00f6hlen des wehklagens': 'Cavernes des lamentations',
    'tiefschwarze grotte': 'Profondeurs de Brassenoire', 'scharlachrotes kloster': 'Monast\u00e8re \u00e9carlate',
    'flammenschlund': 'Gouffre de Ragefeu', 'minas de la muerte': 'Mortemines',
    'castillo de colmillo oscuro': "Donjon d'Ombrecroc", 'las mazmorras': 'Les Cachots',
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


def _cell_at(buf, width, ox, oy, i):
    c, r = i % B_COLS, i // B_COLS
    return _cell(buf, width, ox + c * B_CELL + B_CELL // 2 - 1, oy + r * B_CELL + B_CELL // 2 - 1)


def bridge_magic_ok(buf, width, ox, oy):
    return all(_cell_at(buf, width, ox, oy, i) == B_MAGIC[i] for i in range(len(B_MAGIC)))


def decode_bridge(buf, width, ox=0, oy=0):
    """buf : pixels BGRA. -> (seq, payload) ou None si pas de signal / paquet corrompu."""
    if not bridge_magic_ok(buf, width, ox, oy):
        return None
    bits = nbits = 0
    out = bytearray()
    for i in range(len(B_MAGIC), B_COLS * B_ROWS):
        r, g, b = _cell_at(buf, width, ox, oy, i)
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


def find_bridge_offset(buf, width, height):
    """Cherche la bande ; renvoie le decalage qui vise le CENTRE des cases (milieu de la
    plage de decalages qui reconnaissent la bande), plus sur face au flou des bords."""
    for dy in range(0, height - B_H + 1):
        for dx in range(0, width - B_W + 1):
            if bridge_magic_ok(buf, width, dx, dy):
                dx2 = dx
                while dx2 + 1 <= width - B_W and bridge_magic_ok(buf, width, dx2 + 1, dy):
                    dx2 += 1
                mx = (dx + dx2) // 2
                dy2 = dy
                while dy2 + 1 <= height - B_H and bridge_magic_ok(buf, width, mx, dy2 + 1):
                    dy2 += 1
                return mx, (dy + dy2) // 2
    return None


def parse_bridge_record(payload):
    """payload = 'kind\\x1fcanal\\x1fauteur\\x1ftexte' -> tuple comme parse()."""
    try:
        kind, chan, author, text = payload.decode("utf-8", "replace").split("\x1f", 3)
    except ValueError:
        return None
    if kind == "tip":                    # infobulle d'objet : lignes dans le champ canal, nom en auteur
        return time.strftime("%H:%M"), "tip", chan, author, ""
    if not text.strip():
        return None
    low = chan.lower()
    if kind == "channel" and ("looking" in low or "recherche" in low or "suche" in low):
        kind = "lfg"
    return time.strftime("%H:%M"), kind, chan, clean_name(author), text


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
              "deja déjà alors voila voilà fait mort mdr ptdr bonne bon nuit dispo dispos".split())
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
    "hi": "salut", "hello": "bonjour", "hey": "salut", "yo": "salut", "hi all": "salut tout le monde",
    "hello all": "bonjour à tous", "hey all": "salut tout le monde", "sup": "quoi de neuf",
    "bye": "au revoir", "cya": "à plus", "see ya": "à plus", "gn": "bonne nuit", "good night": "bonne nuit",
    "gm": "bonjour", "good morning": "bonjour",
    "gg": "bien joué", "gg wp": "bien joué", "gj": "bien joué", "wp": "bien joué", "ggwp": "bien joué",
    "gz": "félicitations", "grats": "félicitations", "gratz": "félicitations", "congrats": "félicitations",
    "lol": "mdr", "lmao": "mdr", "lmfao": "mdr", "rofl": "mdr", "haha": "haha", "xd": "xD",
    "brb": "je reviens", "afk": "absent (AFK)", "back": "de retour", "re": "re (de retour)",
    "omw": "j'arrive", "otw": "j'arrive", "coming": "j'arrive", "wait": "attends", "sec": "une seconde",
    "1 sec": "une seconde", "1 min": "une minute", "ready": "prêt", "rdy": "prêt", "r": "prêt",
    "go": "on y va", "lets go": "allez, on y va", "let's go": "allez, on y va",
    "inv": "invite-moi", "inv pls": "invite-moi stp", "inv plz": "invite-moi stp", "invite": "invite-moi",
    "inv me": "invite-moi", "pls inv": "invite-moi stp", "plz inv": "invite-moi stp",
    "lfg": "cherche groupe", "lfm": "cherche du monde", "lf1m": "cherche 1 joueur",
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
    "u": "you", "r": "are", "ur": "your", "ty": "thank you", "thx": "thanks",
    "tyvm": "thank you very much", "pls": "please", "plz": "please", "ppl": "people",
    "lfg": "looking for group", "lfm": "looking for more", "lf": "looking for",
    "wts": "want to sell", "wtb": "want to buy", "wtt": "want to trade",
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
    "los": "line of sight",          # seulement pour l'anglais (en espagnol, "los" = "les")
}

# Expressions entieres (regex, remplacement) appliquees avant les mots seuls : "LFM Hogger" ne doit pas
# devenir "cherche plus de Hogger", ni "whisp for inv" "fouette pour inviter".
LEX_PHRASES = [
    (r"(?<![\w/])w/\s*(?=now\b|for inv)", "whisper "),     # "w/ now for inv" = chuchote-moi, pas "with"
    (r"\blfm(?:\s+for)?\b", "looking for more players for"),
    (r"\blf(\d)m\b", r"looking for \1 more players"),
    (r"\b(?:whisp|wisp|whis|whisper|pst|pm|w/)\s+(?:me\s+)?for\s+(?:an?\s+)?(?:inv|invite|invites)\b",
     "whisper me for an invite"),
    (r"\bfor\s+inv\b", "for an invite"),
    # enchantement demande : "LF enchant gloves riding skill, i have mats" etait traduit
    # "je cherche des competences de conduite avec des gants enchanteurs, j'ai du materiel"
    (r"\b(lf|looking for|wtb|need|want)\s+(?:an?\s+)?(?:enchanter\s+(?:for|to)\s+)?enchant(?:ment)?s?\s+"
     r"(gloves?|boots?|bracers?|chest|cloak|weapon|2h|shield)\b", r"\1 an enchantment on \2"),
    (r"\b(gloves?)\s+(?:\+\s*\d+%?\s*)?riding(?:\s+skill)?\b", r"\1 for mount speed"),
    (r"\b(have|got|has|with|bring)\s+(?:own\s+|my\s+|the\s+)?mats\b", r"\1 the materials"),
    # question qui commence par "any" ("any group for SFK?") : Google traduit "tout groupe".
    (r"(^|\]\s*)any\s+(?!(?:one|body|1|more|way|ways|time|how)\b)", r"\1is there any "),
    # "anyone need X" sans point d'interrogation : Google traduisait "tout le monde a besoin de X".
    (r"(^|\]\s*)any(?:one|body|1)\s+(need|want|know|sell)s?\b", r"\1does anyone \2"),
    (r"(^|\]\s*)any(?:one|body|1)\s+(?:have|has|got)\b", r"\1does anyone have"),
    (r"(^|\]\s*)any(?:one|body|1)\s+(selling|going|up|around|online|here)\b", r"\1is anyone \2"),
    (r"(^|\]\s*)any(?:one|body|1)\s+(?:seen|saw)\b", r"\1has anyone seen"),
    (r"(^|\]\s*)any(?:one|body|1)\s+can\b", r"\1can anyone"),
]

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
            "tlm": "tout le monde", "bcp": "beaucoup", "dsl": "d\u00e9sol\u00e9", "jsp": "je ne sais pas",
            "pb": "probl\u00e8me", "pr": "pour", "mdr": "lol", "ptdr": "lol", "donj": "donjon", "donjs": "donjons",
            "grp": "groupe", "jvais": "je vais", "chui": "je suis", "chuis": "je suis", "tkt": "t'inqui\u00e8te",
            "dispo": "disponible", "dispos": "disponibles"}
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
        self.root.title("WoW Traducteur")
        self.root.configure(bg=self.T["bg"])
        self.root.overrideredirect(True)      # pas de barre de titre Windows : on a la notre
        geo = str(self.cfg.get("geometry", ""))
        if not re.match(r"^\d+x\d+\+-?\d+\+-?\d+$", geo):     # premier lancement : sur le tchat de WoW
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            gw, gh = min(540, sw), min(300, sh)                      # en bas a gauche, au-dessus des barres
            geo = "%dx%d+%d+%d" % (gw, gh, int(sw * 0.016), max(0, int(sh * 0.885) - gh))
        self.root.geometry(geo)
        self.root.configure(highlightthickness=self.T["border_w"], highlightbackground=self.T["border"],
                            highlightcolor=self.T["border"])
        self.root.minsize(380, 300)
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
        self.root.after(1500, self.show_news)
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
        bar.pack(fill="x")
        if T["border_w"] > 1:       # liseré sous la barre, couleur du cadre
            tk.Frame(r, bg=T["border"], height=1).pack(fill="x")
        btn = dict(bg=T["btn"], fg=T["btn_fg"], relief="flat", bd=0, padx=8, pady=2, activebackground=T["btn_act"],
                   activeforeground=T["btn_fg"], cursor="hand2", font=("Segoe UI", 9), highlightthickness=0)
        drag = [bar]
        if T["emblem"]:
            cv = tk.Canvas(bar, width=18, height=21, bg=BAR, highlightthickness=0, bd=0)
            draw_emblem(cv, T["emblem"])
            cv.pack(side="left", padx=(6, 2), pady=3)
            drag.append(cv)
        if T["label"]:
            lab = tk.Label(bar, text=T["label"], bg=BAR, fg=T["label_fg"], font=("Segoe UI", 9, "bold"))
            lab.pack(side="left", padx=(2, 2))
            drag.append(lab)
        tk.Button(bar, text=_("\u2699 R\u00e9glages"), command=self.open_settings, **btn).pack(side="left", padx=(6, 3), pady=4)
        self._clear_btn = tk.Button(bar, text=_("Effacer"), command=self.clear, **btn)
        self._clear_btn.pack(side="left", padx=3, pady=4)
        tk.Button(bar, text="?", command=self.open_help, **dict(btn, padx=7)).pack(side="left", padx=3, pady=4)
        # bouton cache, affiche seulement si une nouvelle version existe sur GitHub
        self.update_btn = tk.Button(bar, text="", command=lambda: webbrowser.open(RELEASE_URL),
                                    **dict(btn, bg=T["accent"], fg=T["accent_fg"], activebackground=T["accent_act"]))
        closeb = tk.Button(bar, text="\u2715", command=self.on_close, bg=BAR, fg=T["icon"], relief="flat", bd=0,
                           padx=10, pady=2, activebackground="#c0392b", activeforeground="white",
                           cursor="hand2", font=("Segoe UI", 10), highlightthickness=0)
        closeb.pack(side="right", padx=(0, 4), pady=4)
        minb = tk.Button(bar, text="\u2014", command=self.minimize, bg=BAR, fg=T["icon"], relief="flat", bd=0,
                         padx=10, pady=2, activebackground=T["btn_act"], activeforeground="white",
                         cursor="hand2", font=("Segoe UI", 10), highlightthickness=0)
        minb.pack(side="right", pady=4)
        # cadenas : dessine (pas d'emoji, mal affiche par tkinter sous Windows)
        self.lock_cv = tk.Canvas(bar, width=22, height=22, bg=BAR, highlightthickness=0, bd=0, cursor="hand2")
        self.lock_cv.pack(side="right", padx=(0, 2), pady=3)
        self.lock_cv.bind("<Button-1>", lambda e: self.toggle_lock())
        self.draw_lock()
        self._minimized = False
        r.bind("<Map>", self._on_map)
        stat = tk.Label(bar, textvariable=self.status, bg=BAR, fg=T["status"], anchor="e", font=("Segoe UI", 8))
        stat.pack(side="right", fill="x", expand=True, padx=6)
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
        self.text.tag_configure("me", foreground=T["me"])
        self.text.tag_configure("name", foreground=T["name"],    # apres les canaux : la couleur du pseudo prime
                                font=("Segoe UI", int(self.cfg["font_size"]), "bold"))
        self.text.tag_configure("news", foreground=T["name"], font=("Segoe UI", int(self.cfg["font_size"]), "bold"))
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
        lf = tk.Frame(out, bg=P)
        lf.grid(row=0, column=0, padx=4, pady=3)
        # destinataire du chuchotement (clic sur un pseudo) : "A Nom (FR) ->" + croix pour annuler
        self.reply_lbl = tk.Label(lf, text=_("Ecrire (%s) \u2192") % UI.upper(), bg=P, fg=T["fg"])
        self.reply_lbl.pack(side="left")
        self.reply_x = tk.Button(lf, text="\u2715", command=lambda: self.set_reply_to(None), bg=P, fg=T["muted"],
                                 activebackground=P, activeforeground=T["fg"], relief="flat", bd=0,
                                 highlightthickness=0, padx=2, pady=0, cursor="hand2", font=("Segoe UI", 8))
        self.out_entry = tk.Entry(out, bg=T["entry"], fg=T["fg"], insertbackground=T["fg"], relief="flat",
                                  highlightthickness=0)
        self.out_entry.grid(row=0, column=1, sticky="ew", padx=(2, 0))
        # croix : efface vite le texte a traduire et le dernier resultat (touche Echap aussi)
        tk.Button(out, text="\u2715", command=self.clear_out, bg=T["entry"], fg=T["err"],
                  activebackground=T["btn_act"], activeforeground=T["err"], relief="flat", bd=0,
                  highlightthickness=0, padx=6, pady=0, cursor="hand2",
                  font=("Segoe UI", 10, "bold")).grid(row=0, column=2, sticky="ns", padx=(0, 2))
        self.out_lang = tk.StringVar(value=self.cfg["out_lang"])
        # langue de reponse : bouton "EN ▴" qui ouvre une liste VERS LE HAUT (la fenetre est souvent en bas)
        self.out_lang_btn = tk.Button(out, text="", command=self.open_lang_menu, bg=T["entry"], fg=T["fg"],
                                      activebackground=T["btn_act"], activeforeground=T["fg"], relief="flat", bd=0,
                                      highlightthickness=0, padx=6, cursor="hand2")
        self.out_lang_btn.grid(row=0, column=3, padx=3, sticky="ns")
        self.out_lang.trace_add("write", lambda *a: self._show_lang())
        self._show_lang()
        tk.Button(out, text=_("Traduire + copier"), command=self.send_out, bg=T["accent"], fg=T["accent_fg"],
                  activebackground=T["accent_act"], activeforeground=T["accent_fg"],
                  relief="flat", highlightthickness=0, bd=0, padx=8).grid(row=0, column=4, padx=3)
        out.columnconfigure(1, weight=1)
        self.out_result = tk.Label(out, text=_("Clique sur un message pour repondre dans sa langue."),
                                   bg=P, fg=T["muted"], anchor="w", justify="left", wraplength=520)
        self.out_result.grid(row=1, column=0, columnspan=5, sticky="ew", padx=4, pady=(0, 3))
        self.out_entry.bind("<Return>", lambda e: self.send_out())
        self.out_entry.bind("<Escape>", lambda e: self.clear_out())
        self.set_reply_to(getattr(self, "reply_to", None), quiet=True)

        grip = tk.Label(r, text="\u25e2", bg=T["bg"], fg=T["scroll_act"], font=("Segoe UI", 9))
        try:
            grip.configure(cursor="size_nw_se")
        except tk.TclError:
            pass
        grip.place(relx=1.0, rely=1.0, anchor="se")
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

    def _insert_with_coins(self, text, tags):
        """Insere du texte ; dans les messages du jeu, po / pa / pc deviennent une icone de piece.
        Le texte reste la (cache) : il revient au copier-coller et au changement de theme."""
        t = self.text
        tags = tuple(tags)
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
        at_end = t.yview()[1] >= 0.98
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

    def set_reply_to(self, name, quiet=False):
        """Destinataire des reponses : "Traduire + copier" copiera "/w Nom texte"."""
        self.reply_to = name or None
        if self.reply_to:
            self.reply_lbl.config(text=_("\u00c0 %s (%s) \u2192") % (self.reply_to, UI.upper()), fg=self.T["name"])
            self.reply_x.pack(side="left", padx=(3, 0))
            if not quiet:
                self.out_result.config(text=_("Chuchotement \u00e0 %s : ta reponse sera copiee avec /w %s")
                                       % (self.reply_to, self.reply_to), fg=self.T["muted"])
                self.out_entry.focus_set()
        else:
            self.reply_lbl.config(text=_("Ecrire (%s) \u2192") % UI.upper(), fg=self.T["fg"])
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
            tk.Entry(w, textvariable=v, width=wd, bg=T["entry"], fg=T["fg"],
                     insertbackground=T["fg"], relief="flat").grid(row=i, column=1, sticky="w", padx=6)
        bools = [(_("Son pour les alertes"), "sound"), (_("Toujours au premier plan"), "topmost"),
                 (_("Afficher aussi les messages deja dans ta langue"), "show_french"),
                 (_("Se fermer quand WoW se ferme"), "autoclose"),
                 (_("Se cacher quand WoW n'est pas la fenetre active"), "follow_wow"),
                 (_("Langue de reponse automatique (dernier message etranger)"), "auto_reply_lang")]
        bv = {}
        row = len(fields)
        for lab, key in bools:
            v = tk.BooleanVar(value=bool(self.cfg.get(key, True)))
            bv[key] = v
            tk.Checkbutton(w, text=lab, variable=v, bg=P, fg=T["fg"], selectcolor=T["entry"],
                           activebackground=P, activeforeground=T["fg"], highlightthickness=0).grid(
                row=row, column=0, columnspan=2, sticky="w", padx=6)
            row += 1
        av = tk.DoubleVar(value=float(self.cfg["alpha"]))
        tk.Label(w, text=_("Opacite"), bg=P, fg=T["fg"]).grid(row=row, column=0, sticky="w", padx=6)
        tk.Scale(w, from_=0.3, to=1.0, resolution=0.05, orient="horizontal", variable=av, length=200,
                 bg=P, fg=T["fg"], highlightthickness=0).grid(row=row, column=1, sticky="w")
        row += 1
        fv = tk.IntVar(value=int(self.cfg["font_size"]))
        tk.Label(w, text=_("Taille du texte"), bg=P, fg=T["fg"]).grid(row=row, column=0, sticky="w", padx=6)
        tk.Scale(w, from_=8, to=20, orient="horizontal", variable=fv, length=200,
                 bg=P, fg=T["fg"], highlightthickness=0).grid(row=row, column=1, sticky="w")
        row += 1
        tv = tk.StringVar(value=str(self.cfg.get("theme", "Sombre")) if self.cfg.get("theme") in THEMES else "Sombre")
        tk.Label(w, text=_("Theme"), bg=P, fg=T["fg"]).grid(row=row, column=0, sticky="w", padx=6, pady=3)
        theme_names = {_(k): k for k in THEMES}
        tshow = tk.StringVar(value=_(tv.get()))
        tshow.trace_add("write", lambda *a: tv.set(theme_names.get(tshow.get(), tv.get())))
        om = tk.OptionMenu(w, tshow, *theme_names.keys())
        om.configure(bg=T["entry"], fg=T["fg"], activebackground=T["btn_act"], activeforeground=T["fg"],
                     relief="flat", highlightthickness=0, bd=0)
        om["menu"].configure(bg=T["entry"], fg=T["fg"], activebackground=T["btn_act"], activeforeground=T["fg"])
        om.grid(row=row, column=1, sticky="w", padx=6)
        row += 1
        # langue de l'interface
        uv = tk.StringVar(value="English" if UI == "en" else "Fran\u00e7ais")
        tk.Label(w, text=_("Langue de l'interface"), bg=P, fg=T["fg"]).grid(row=row, column=0, sticky="w", padx=6, pady=3)
        um = tk.OptionMenu(w, uv, "Fran\u00e7ais", "English")
        um.configure(bg=T["entry"], fg=T["fg"], activebackground=T["btn_act"], activeforeground=T["fg"],
                     relief="flat", highlightthickness=0, bd=0)
        um["menu"].configure(bg=T["entry"], fg=T["fg"], activebackground=T["btn_act"], activeforeground=T["fg"])
        um.grid(row=row, column=1, sticky="w", padx=6)
        row += 1

        def ok():
            global UI
            new_ui = "en" if uv.get() == "English" else "fr"
            ui_changed = new_ui != UI
            for k, v in vars_.items():
                self.cfg[k] = v.get().strip()
            for k, v in bv.items():
                self.cfg[k] = bool(v.get())
            self.cfg["alpha"] = float(av.get())
            self.cfg["font_size"] = int(fv.get())
            self.cfg["target"] = self.cfg["target"] or UI
            if ui_changed:
                self.set_ui_lang(new_ui)
                UI = new_ui
            new_theme = tv.get() != self.cfg.get("theme", "Sombre") or ui_changed
            self.cfg["theme"] = tv.get()
            self.text.configure(font=("Segoe UI", self.cfg["font_size"]))
            self.text.tag_configure("name", font=("Segoe UI", self.cfg["font_size"], "bold"))
            self.apply_window_cfg()
            save_config(self.cfg)
            w.destroy()
            if new_theme:
                self.apply_theme(self.cfg["theme"])

        tk.Button(w, text=_("Enregistrer"), command=ok, bg=T["accent"], fg=T["accent_fg"],
                  activebackground=T["accent_act"], activeforeground=T["accent_fg"],
                  relief="flat").grid(row=row, column=0, columnspan=2, pady=8)

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
        off, last_seq, seen_first, bad, nmsg, last_status = None, None, False, 0, 0, 0.0
        while not self.stop:
            if str(self.cfg.get("source", "pont")).strip().lower() != "pont":
                time.sleep(1)
                continue
            try:
                org = wow_client_origin()
                if org is None:
                    self.outq.put(("status", _("Pont image : fenetre WoW introuvable")))
                    off = None
                    time.sleep(1)
                    continue
                x, y = org
                if off is None:
                    sw, sh = B_W + B_SEARCH, B_H + B_SEARCH
                    cap = grab(x, y, sw, sh)
                    off = find_bridge_offset(cap, sw, sh)
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
                buf = grab(x + off[0], y + off[1], B_W, B_H)
                res = decode_bridge(buf, B_W)
                if res is None:
                    bad += 1
                    if bad > 60:        # fenetre deplacee ou bande disparue : on recherche
                        off, bad = None, 0
                    time.sleep(0.03)
                    continue
                bad = 0
                seq, payload = res
                if seq != last_seq:
                    last_seq = seq
                    if not seen_first:
                        seen_first = True      # paquet deja affiche avant le lancement : ignore
                    elif payload:
                        p = parse_bridge_record(payload)
                        if p and p[1] == "tip":
                            self.outq.put(("tip", p[3], p[2]))
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
        while not self.stop:
            try:
                hhmm, kind, chan, author, text = self.inq.get(timeout=0.5)
            except queue.Empty:
                continue
            cfg = self.cfg
            raw = clean_questie(replace_raid_marks(wow_grammar(text)))
            text, _spans = split_links(raw)
            low_chan = chan.lower()
            hidden = [h.strip().lower() for h in cfg["hidden"].split(",") if h.strip()]
            if any(h in low_chan for h in hidden):
                continue
            if kind in NO_TRANSLATE:
                # PNJ, systeme, butin : texte du jeu, deja dans sa langue -> affiche tel quel
                self.outq.put(("msg", hhmm, kind, chan, author, text, None, "?", False, False, raw))
                continue
            me = cfg["my_name"].strip().lower()
            mine = bool(me) and author.lower() == me
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
            elif lex:
                trans, lang = lex, "en"           # lexique : pas d'appel a Google
            elif not mine and cfg["target"].lower() == "fr" and sure_french(judge):
                lang = "fr"                            # deja en francais : pas d'appel a Google
            elif not mine and cfg["target"].lower() == "en" and (lexicon_full(judge.strip()) or sure_english(judge)):
                lang = "en"                            # "lfm", "wts", "lfg/lfm" : jargon anglais, rien a traduire
            elif not mine and worth_translating(judge):
                try:
                    src_text = ru_slang(gtext)
                    if cfg["target"].lower() != "fr":
                        src_text = fr_slang(src_text)      # argot francais ("pex", "slt", "tlm") avant Google
                    trans, lang = google_translate(fr_mix_fix(src_text), cfg["target"])
                    if lang == "en" and cfg["target"].lower() == "fr":
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

    # ---- affichage ---------------------------------------------------------
    def poll(self):
        try:
            while True:
                item = self.outq.get_nowait()
                if item[0] == "status":
                    self.status.set(item[1])
                elif item[0] == "msg":
                    self.show(*item[1:])
                elif item[0] == "quit":
                    self.on_close()
                    return
                elif item[0] == "out":
                    self.show_out(*item[1:])
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
                    self.update_btn.config(text=_("Mise \u00e0 jour %s dispo") % item[1])
                    self.update_btn.pack(side="left", padx=3, pady=4, after=self._clear_btn)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def show(self, hhmm, kind, chan, author, text, trans, lang, alert, mine, raw=None):
        tgt = self.cfg["target"].lower()
        same = (lang or "").lower().split("-")[0] == tgt
        if same and not self.cfg["show_french"] and not alert:
            return
        tag = "me" if mine else kind
        badge = "[%s] " % lang.upper() if lang not in ("?", "") and not mine else ""
        tail = chan if kind in ("channel", "lfg") else ""
        start_line = int(self.text.index("end-1c").split(".")[0])
        parts = [(hhmm + " ", "badge")]
        if badge:
            parts.append((badge, "badge"))
        if tail:
            parts.append(("(%s) " % tail, "badge"))
        marks = (tag, "alert") if alert else (tag,)
        if author:          # messages systeme / butin : pas d'auteur
            parts.append((author, *marks) if mine or kind in NO_TRANSLATE else (author, *marks, "name"))
            parts.append((": ", *marks))
        _plain, spans = split_links(raw if raw is not None else text)
        coin = ("coins",) if kind in COIN_KINDS else ()
        for seg, code in spans:
            parts.append((seg, *marks, "link_" + code) if code else (seg, *marks, *coin))
        parts.append(("\n", *marks))
        if trans and not same and trans.strip().lower() != text.strip().lower():
            tmarks = ("trans", "alert") if alert else ("trans",)
            parts.append(("\u2192 ", *tmarks))
            codes = [c for _, c in spans if c]
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

    def auto_reply_lang(self, lang, author, kind):
        """Regle la langue de reponse sur celle du dernier message etranger recu.
        Un chuchotement reste prioritaire 60 s ; on ne change rien pendant que tu ecris."""
        if not self.cfg.get("auto_reply_lang", True) or self.out_entry.get().strip():
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

    def send_out(self):
        txt = self.out_entry.get().strip()
        lang = (self.out_lang.get() or "en").strip().lower()
        if not txt:
            return
        self.out_result.config(text=_("Traduction en cours..."), fg=self.T["muted"])

        def run():
            try:
                # "coucou" seul : Google donne "cuckoo" (l'oiseau)
                m = re.fullmatch(r"(?i)\s*coucou+\s*([!.?]*)\s*", txt)
                if m and lang == "en" and UI == "fr":
                    res = ("Hi" if txt.strip()[:1].isupper() else "hi") + m.group(1)
                    self.outq.put(("out", txt, res, lang, None))
                    return
                # tu ecris en francais : on le dit a Google (sinon "bonjour" seul est pris pour de l'anglais)
                res, _x = translate_out(txt, lang, UI)
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
            self.root.deiconify()
            self.apply_window_cfg()

    def minimize(self):
        """Reduit dans la barre des taches (une fenetre sans cadre ne peut pas l'etre :
        on remet le cadre le temps de la reduction, puis on le retire au retour)."""
        self._save_geometry()
        self._minimized = True
        self.root.update_idletasks()
        self.root.overrideredirect(False)
        self.root.iconify()

    def _on_map(self, e):
        if e.widget is self.root and self._minimized:
            self._minimized = False
            self.root.overrideredirect(True)
            self.apply_window_cfg()

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
        if self.cfg.get("locked"):
            return
        w = max(380, self._rw + e.x_root - self._rx)
        h = max(300, self._rh + e.y_root - self._ry)
        self.root.geometry("%dx%d" % (w, h))

    def _save_geometry(self):
        try:
            self.cfg["geometry"] = self.root.geometry()
            save_config(self.cfg)
        except tk.TclError:
            pass

    def on_close(self):
        self.stop = True
        self.save_tips()
        try:
            self.cfg["geometry"] = self.root.geometry()
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
