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
import binascii
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
import webbrowser
from ctypes import wintypes
import tkinter as tk
from tkinter import ttk

try:
    import winsound
except ImportError:  # pas sous Windows
    winsound = None

VERSION = "1.2"
# Verification de mise a jour : le fichier version.txt du depot contient le numero de la derniere version.
VERSION_URL = "https://raw.githubusercontent.com/puenteur/Wow-traducteur/main/version.txt"
RELEASE_URL = "https://github.com/puenteur/Wow-traducteur/releases/latest"

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "translator_config.json")

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
    "auto_reply_lang": True,        # langue de reponse = langue du dernier message etranger
}

BG = "#101418"
FG = "#e6e6e6"
COLORS = {
    "say": "#ffffff", "yell": "#ff5555", "party": "#7fb2ff", "raid": "#ff9a3c",
    "guild": "#5fe05f", "officer": "#40c040", "whisper": "#ff8bd8",
    "channel": "#c8c8c8", "lfg": "#ffe066", "other": "#c8c8c8",
}
TRANS_COLOR = "#6fd3ff"
NAME_COLOR = "#e8b964"      # pseudo des autres joueurs
ALERT_BG = "#5a4a00"

# Liens du tchat (envoyes par l'addon sous la forme \x02 code \x03 [Nom] \x04) :
# couleurs comme dans le tchat officiel de WoW.
LINK_COLORS = {
    "q": "#ffd100",                                   # quete
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
_GT_HOSTS = ("translate.googleapis.com", "translate.google.com")
_gt_lock = threading.Lock()
_gt_last = [0.0]
_gt_cache = {}
_gt_pause = [0.0]          # apres un 429 : plus aucune requete jusqu'a cette heure (sinon Google prolonge le blocage)
GT_PAUSE = 120             # secondes


def google_translate(text, target, source="auto", timeout=8):
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
    for attempt in range(4):
        host = _GT_HOSTS[attempt % 2]                  # on alterne entre les deux adresses
        with _gt_lock:                                 # 0,3 s minimum entre deux requetes
            wait = 0.3 - (time.time() - _gt_last[0])
            if wait > 0:
                time.sleep(wait)
            _gt_last[0] = time.time()
        req = urllib.request.Request("https://%s/translate_a/single?%s" % (host, params),
                                     headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 503):
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, OSError, ValueError) as e:
            # coupure reseau, delai depasse, reponse tronquee : on reessaie aussi
            last_err = e
            time.sleep(1.0 * (attempt + 1))
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


# Noms propres que Google prend pour des mots communs ("hogger" -> "porc"). Ils sont remplaces par
# un code avant l'envoi a Google puis remis tels quels dans la traduction. Ajoute les tiens ici.
LEX_NAMES = ["Hogger"]


def _name_re(name):
    """Regex d'un nom propre qui tolere les lettres repetees ("hoggeer", "hoggerr")."""
    return "".join(re.escape(c) + "+" for c in name.lower())


def _names_pattern():
    return r"(?<!\w)(?:%s)(?!\w)" % "|".join(_name_re(n) for n in LEX_NAMES)


def google_translate_safe(text, target, source="auto", timeout=8):
    """Comme google_translate, mais sans laisser Google traduire les noms de LEX_NAMES."""
    found = {}

    def mask(m):
        key = "Zq%dx" % len(found)
        found[key] = next(n for n in LEX_NAMES if re.fullmatch(_name_re(n), m.group(0), re.I))
        return key
    if LEX_NAMES:
        text = re.sub(_names_pattern(), mask, text, flags=re.I)
    out, lang = google_translate(text, target, source, timeout)
    for key, name in found.items():
        out = re.sub(re.escape(key), lambda _m, n=name: n, out, flags=re.I)
    return out, lang


def has_protected_name(text):
    return bool(LEX_NAMES) and bool(re.search(_names_pattern(), text, re.I))


# --------------------------------------------------------------------------
# Pont image : l'addon dessine une bande de cases colorees en haut a gauche de
# l'ecran de WoW (64 x 12 cases de 6 px, 3 bits par case). On la lit par capture d'ecran.
# --------------------------------------------------------------------------
B_COLS, B_ROWS, B_CELL = 64, 12, 6
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
SURE_FR = set("je j tu il elle nous vous ils elles on est suis sont es ai as avons avez ont et ou mais donc "
              "le les un une des du au aux ce cet cette ces mon ma mes ton ta tes son sa ses notre votre leur "
              "pour avec dans sur sous chez pas ne plus rien jamais qui quoi quel quelle quels quand comment "
              "pourquoi combien ou oui ouais merci salut bonjour bonsoir svp stp cherche cherchons recrute "
              "vend vends achete achète groupe guilde donjon quelqu quelqu'un personne besoin veux veut peux "
              "peut faut faire aller viens venir ici ça ca c qu d l m n s t y bien très tres trop aussi encore "
              "deja déjà alors voila voilà fait mort mdr ptdr bonne bon nuit".split())
# Mots d'une autre langue : s'il y en a un, on laisse Google decider (message mixte ou etranger).
NOT_FR = set("the a an is are was be been i you he she we they it my your his her our their this that "
             "these those and or but to of in on at for with from by as if so not no yes any some anyone "
             "someone need needs looking want wants sell selling buy buying have has can could would will "
             "do does please pls plz thanks thx ty hi hello hey what where when who why how there here "
             "last first just all only lf lfm lfg wts wtb el los las para por hay alguien busco necesito "
             "gracias hola ich und der die das nicht ist wer sucht bitte danke per che sono cerco gilda "
             "ciao grazie voce você não obrigado".split())
_FOREIGN_CHARS = re.compile("[\u00f1\u00e3\u00f5\u00df\u00e4\u00f6\u00fc\u00e1\u00ed\u00f3\u00fa\u0105\u0119\u0142\u017c\u017a\u015b\u0107\u0144]")
_FR_ACCENTS = re.compile("[\u00e0\u00e2\u00e7\u00e8\u00e9\u00ea\u00eb\u00ee\u00ef\u00f4\u00f9\u00fb\u0153]")


def sure_french(text):
    """True seulement si le message est clairement en francais (sans mot etranger)."""
    t = text.lower()
    if not is_latin_text(t) or _FOREIGN_CHARS.search(t):
        return False
    words = [w.strip("'") for w in re.findall("[a-z\u00e0-\u00ff\u0153']+", t)]
    parts = []
    for w in words:
        parts.extend(p for p in w.split("'") if p)      # j'ai -> j, ai
    if not parts or any(p in NOT_FR for p in parts):
        return False
    hits = sum(1 for p in parts if p in SURE_FR)
    return hits >= 2 or (hits >= 1 and (len(parts) <= 3 or bool(_FR_ACCENTS.search(t))))


def is_latin_text(text):
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and all(ord(c) < 0x250 for c in letters)


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
}

# Expressions entieres (regex, remplacement) appliquees avant les mots seuls : "LFM Hogger" ne doit pas
# devenir "cherche plus de Hogger", ni "whisp for inv" "fouette pour inviter".
LEX_PHRASES = [
    (r"\blfm(?:\s+for)?\b", "looking for more players for"),
    (r"\blf(\d)m\b", r"looking for \1 more players"),
    (r"\b(?:whisp|wisp|whis|whisper|pst|pm|w/)\s+(?:me\s+)?for\s+(?:an?\s+)?(?:inv|invite|invites)\b",
     "whisper me for an invite"),
    (r"\bfor\s+inv\b", "for an invite"),
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
        self.root = tk.Tk()
        self.root.title("WoW Traducteur")
        self.root.configure(bg=BG)
        self.root.overrideredirect(True)      # pas de barre de titre Windows : on a la notre
        geo = str(self.cfg.get("geometry", ""))
        if not re.match(r"^\d+x\d+\+-?\d+\+-?\d+$", geo):
            geo = "560x520+40+80"
        self.root.geometry(geo)
        self.root.configure(highlightthickness=1, highlightbackground="#2a343f", highlightcolor="#2a343f")
        self.root.minsize(380, 300)
        self.inq = queue.Queue()
        self.outq = queue.Queue()
        self.stop = False
        self.nlines = 0
        self.nparsed = 0
        self.status = tk.StringVar(value="Demarrage...")
        self.line_lang = {}          # numero de ligne -> langue d'origine
        self.apply_window_cfg()
        self.build_ui()
        threading.Thread(target=self.reader, daemon=True).start()
        threading.Thread(target=self.bridge_reader, daemon=True).start()
        threading.Thread(target=self.worker, daemon=True).start()
        threading.Thread(target=self.watch_wow, daemon=True).start()
        threading.Thread(target=self.check_update, daemon=True).start()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self.poll)

    # ---- interface -------------------------------------------------------
    def apply_window_cfg(self):
        self.root.attributes("-topmost", bool(self.cfg["topmost"]))
        try:
            self.root.attributes("-alpha", float(self.cfg["alpha"]))
        except tk.TclError:
            pass

    def build_ui(self):
        r = self.root
        BAR = "#0b0e11"
        bar = tk.Frame(r, bg=BAR)
        bar.pack(fill="x")
        btn = dict(bg="#1b232c", fg=FG, relief="flat", bd=0, padx=8, pady=2, activebackground="#2a343f",
                   activeforeground=FG, cursor="hand2", font=("Segoe UI", 9), highlightthickness=0)
        tk.Button(bar, text="\u2699 R\u00e9glages", command=self.open_settings, **btn).pack(side="left", padx=(6, 3), pady=4)
        self._clear_btn = tk.Button(bar, text="Effacer", command=self.clear, **btn)
        self._clear_btn.pack(side="left", padx=3, pady=4)
        # bouton cache, affiche seulement si une nouvelle version existe sur GitHub
        self.update_btn = tk.Button(bar, text="", command=lambda: webbrowser.open(RELEASE_URL),
                                    **dict(btn, bg="#1f6f9f", fg="white", activebackground="#2a86bd"))
        closeb = tk.Button(bar, text="\u2715", command=self.on_close, bg=BAR, fg="#9aa7b4", relief="flat", bd=0,
                           padx=10, pady=2, activebackground="#c0392b", activeforeground="white",
                           cursor="hand2", font=("Segoe UI", 10), highlightthickness=0)
        closeb.pack(side="right", padx=(0, 4), pady=4)
        minb = tk.Button(bar, text="\u2014", command=self.minimize, bg=BAR, fg="#9aa7b4", relief="flat", bd=0,
                         padx=10, pady=2, activebackground="#2a343f", activeforeground="white",
                         cursor="hand2", font=("Segoe UI", 10), highlightthickness=0)
        minb.pack(side="right", pady=4)
        self._minimized = False
        r.bind("<Map>", self._on_map)
        stat = tk.Label(bar, textvariable=self.status, bg=BAR, fg="#6f7c8a", anchor="e", font=("Segoe UI", 8))
        stat.pack(side="right", fill="x", expand=True, padx=6)
        # glisser la barre pour deplacer la fenetre
        for w in (bar, stat):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)
            w.bind("<ButtonRelease-1>", lambda e: self._save_geometry())

        mid = tk.Frame(r, bg=BG)
        mid.pack(fill="both", expand=True, padx=8, pady=(2, 4))
        self.text = tk.Text(mid, bg=BG, fg=FG, wrap="word", relief="flat", state="disabled",
                            font=("Segoe UI", int(self.cfg["font_size"])), cursor="arrow",
                            insertbackground=FG, spacing1=3, padx=2, height=4, highlightthickness=0, bd=0)
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Dark.Vertical.TScrollbar", background="#2a343f", troughcolor=BG, bordercolor=BG,
                        lightcolor="#2a343f", darkcolor="#2a343f", gripcount=0, width=7)
        style.map("Dark.Vertical.TScrollbar", background=[("active", "#3b4856")])
        style.layout("Dark.Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
            ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
        sb = ttk.Scrollbar(mid, command=self.text.yview, style="Dark.Vertical.TScrollbar")
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        for k, c in COLORS.items():
            self.text.tag_configure(k, foreground=c)
        self.text.tag_configure("trans", foreground=TRANS_COLOR, lmargin1=18, lmargin2=18)
        self.text.tag_configure("alert", background=ALERT_BG)
        self.text.tag_configure("badge", foreground="#9aa7b4")
        self.text.tag_configure("err", foreground="#ff7070")
        self.text.tag_configure("me", foreground="#ffd479")
        self.text.tag_configure("name", foreground=NAME_COLOR)   # apres les canaux : la couleur du pseudo prime
        for code, c in LINK_COLORS.items():     # en dernier : la couleur du lien prime
            self.text.tag_configure("link_" + code, foreground=c)
        self.text.bind("<Button-1>", self.on_click)

        out = tk.Frame(r, bg="#171d24")
        out.pack(side="bottom", fill="x", padx=8, pady=(0, 8), before=mid)
        tk.Label(out, text="Ecrire (FR) \u2192", bg="#171d24", fg=FG).grid(row=0, column=0, padx=4, pady=3)
        self.out_entry = tk.Entry(out, bg="#0b0e11", fg=FG, insertbackground=FG, relief="flat", highlightthickness=0)
        self.out_entry.grid(row=0, column=1, sticky="ew", padx=2)
        self.out_lang = tk.StringVar(value=self.cfg["out_lang"])
        tk.Entry(out, textvariable=self.out_lang, width=4, bg="#0b0e11", fg=FG,
                 insertbackground=FG, relief="flat", justify="center", highlightthickness=0).grid(row=0, column=2, padx=3)
        tk.Button(out, text="Traduire + copier", command=self.send_out, bg="#1f6f9f", fg="white",
                  relief="flat", highlightthickness=0, bd=0, padx=8).grid(row=0, column=3, padx=3)
        out.columnconfigure(1, weight=1)
        self.out_result = tk.Label(out, text="Clique sur un message pour repondre dans sa langue.",
                                   bg="#171d24", fg="#8a97a6", anchor="w", justify="left", wraplength=520)
        self.out_result.grid(row=1, column=0, columnspan=4, sticky="ew", padx=4, pady=(0, 3))
        self.out_entry.bind("<Return>", lambda e: self.send_out())

        grip = tk.Label(r, text="\u25e2", bg=BG, fg="#3b4856", font=("Segoe UI", 9))
        try:
            grip.configure(cursor="size_nw_se")
        except tk.TclError:
            pass
        grip.place(relx=1.0, rely=1.0, anchor="se")
        grip.bind("<ButtonPress-1>", self._resize_start)
        grip.bind("<B1-Motion>", self._resize_move)
        grip.bind("<ButtonRelease-1>", lambda e: self._save_geometry())

    def add(self, *parts):
        """parts: (texte, tag...)"""
        t = self.text
        at_end = t.yview()[1] >= 0.98
        t.configure(state="normal")
        for p in parts:
            t.insert("end", p[0], p[1:])
        t.configure(state="disabled")
        if at_end:
            t.see("end")
        n = int(t.index("end-1c").split(".")[0])
        if n > 1500:
            t.configure(state="normal")
            t.delete("1.0", "400.0")
            t.configure(state="disabled")
            self.line_lang = {}

    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self.line_lang = {}

    def on_click(self, event):
        ln = int(self.text.index("@%d,%d" % (event.x, event.y)).split(".")[0])
        for k in (ln, ln - 1):
            if k in self.line_lang:
                lang = self.line_lang[k]
                if lang and lang not in ("?", self.cfg["target"]):
                    self.out_lang.set(lang)
                    self.out_result.config(text="Langue de reponse : %s" % lang)
                return

    # ---- reglages --------------------------------------------------------
    def open_settings(self):
        w = tk.Toplevel(self.root)
        w.title("Reglages")
        w.configure(bg="#171d24")
        w.attributes("-topmost", True)
        fields = [
            ("Source (pont ou log)", "source", 8),
            ("Fichier de log (si source=log)", "log_path", 52),
            ("Traduire vers (fr, en...)", "target", 6),
            ("Ton pseudo (alerte)", "my_name", 20),
            ("Mots surveilles (virgules)", "keywords", 40),
            ("Canaux masques (virgules)", "hidden", 40),
        ]
        vars_ = {}
        for i, (lab, key, wd) in enumerate(fields):
            tk.Label(w, text=lab, bg="#171d24", fg=FG).grid(row=i, column=0, sticky="w", padx=6, pady=3)
            v = tk.StringVar(value=str(self.cfg[key]))
            vars_[key] = v
            tk.Entry(w, textvariable=v, width=wd, bg="#0b0e11", fg=FG,
                     insertbackground=FG, relief="flat").grid(row=i, column=1, sticky="w", padx=6)
        bools = [("Son pour les alertes", "sound"), ("Toujours au premier plan", "topmost"),
                 ("Afficher aussi les messages deja en francais", "show_french"),
                 ("Se fermer quand WoW se ferme", "autoclose"),
                 ("Langue de reponse automatique (dernier message etranger)", "auto_reply_lang")]
        bv = {}
        row = len(fields)
        for lab, key in bools:
            v = tk.BooleanVar(value=bool(self.cfg.get(key, True)))
            bv[key] = v
            tk.Checkbutton(w, text=lab, variable=v, bg="#171d24", fg=FG, selectcolor="#0b0e11",
                           activebackground="#171d24", activeforeground=FG, highlightthickness=0).grid(
                row=row, column=0, columnspan=2, sticky="w", padx=6)
            row += 1
        av = tk.DoubleVar(value=float(self.cfg["alpha"]))
        tk.Label(w, text="Opacite", bg="#171d24", fg=FG).grid(row=row, column=0, sticky="w", padx=6)
        tk.Scale(w, from_=0.3, to=1.0, resolution=0.05, orient="horizontal", variable=av, length=200,
                 bg="#171d24", fg=FG, highlightthickness=0).grid(row=row, column=1, sticky="w")
        row += 1
        fv = tk.IntVar(value=int(self.cfg["font_size"]))
        tk.Label(w, text="Taille du texte", bg="#171d24", fg=FG).grid(row=row, column=0, sticky="w", padx=6)
        tk.Scale(w, from_=8, to=20, orient="horizontal", variable=fv, length=200,
                 bg="#171d24", fg=FG, highlightthickness=0).grid(row=row, column=1, sticky="w")
        row += 1

        def ok():
            for k, v in vars_.items():
                self.cfg[k] = v.get().strip()
            for k, v in bv.items():
                self.cfg[k] = bool(v.get())
            self.cfg["alpha"] = float(av.get())
            self.cfg["font_size"] = int(fv.get())
            self.cfg["target"] = self.cfg["target"] or "fr"
            self.text.configure(font=("Segoe UI", self.cfg["font_size"]))
            self.apply_window_cfg()
            save_config(self.cfg)
            w.destroy()

        tk.Button(w, text="Enregistrer", command=ok, bg="#1f6f9f", fg="white",
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
                        self.outq.put(("status", "Log introuvable : %s (tape /chatlog dans WoW)" % path))
                        time.sleep(2)
                        continue
                    f = open(path, "r", encoding="utf-8", errors="replace")
                    f.seek(0, os.SEEK_END)
                    buf = ""
                    self.outq.put(("status", "En ecoute..."))
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
                        self.outq.put(("status", "En ecoute... (%d lignes lues, %d messages)"
                                       % (self.nlines, self.nparsed)))
                else:
                    st = os.stat(path)
                    if st.st_size < f.tell():  # fichier recree
                        f.close()
                        f = None
                    now = time.time()
                    if now - getattr(self, "_last_diag", 0) >= 1:
                        self._last_diag = now
                        self.outq.put(("status", "En ecoute... %d lignes, %d msg | log %d Ko, ecrit il y a %ds"
                                       % (self.nlines, self.nparsed, st.st_size // 1024,
                                          max(0, int(now - st.st_mtime)))))
                    time.sleep(0.25)
            except Exception as e:  # noqa
                self.outq.put(("status", "Erreur lecture : %s" % e))
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
                    self.outq.put(("status", "Pont image : fenetre WoW introuvable"))
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
                        self.outq.put(("status", "Pont image : signal absent | WoW en (%d,%d) | capture %d%% non noire, moy %s | voir debug_pont.bmp"
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
                        if p:
                            nmsg += 1
                            self.nparsed += 1
                            self.inq.put(p)
                now = time.time()
                if now - last_status >= 1:
                    last_status = now
                    self.outq.put(("status", "Pont image : OK (%d messages recus)" % nmsg))
                time.sleep(0.04)
            except Exception as e:  # noqa
                self.outq.put(("status", "Pont image : erreur %s" % e))
                off = None
                time.sleep(2)

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
            raw = replace_raid_marks(text)
            text, _spans = split_links(raw)
            low_chan = chan.lower()
            hidden = [h.strip().lower() for h in cfg["hidden"].split(",") if h.strip()]
            if any(h in low_chan for h in hidden):
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
            lex = None
            if not mine and cfg["target"].lower() == "fr":
                lex = lexicon_full(text)
            if is_coin_only(text):
                pass                                   # "100 po" : affiche tel quel, sans traduction
            elif lex:
                trans, lang = lex, "en"           # lexique : pas d'appel a Google
            elif not mine and cfg["target"].lower() == "fr" and sure_french(text):
                lang = "fr"                            # deja en francais : pas d'appel a Google
            elif not mine and worth_translating(text):
                try:
                    trans, lang = google_translate(fr_mix_fix(text), cfg["target"])
                    if lang == "en" and cfg["target"].lower() == "fr":
                        exp = lexicon_expand(text)
                        if exp != text or has_protected_name(text):
                            # abreviations / noms propres : on retraduit la phrase developpee
                            trans, _ = google_translate_safe(exp, cfg["target"], source="en")
                    elif lang not in ("?", "") and has_protected_name(text):
                        trans, _ = google_translate_safe(text, cfg["target"], source=lang)
                    if unreliable_detection(text, lang):
                        # 2-3 mots, langue improbable (ex. "more for hogger" -> norvegien) :
                        # francais mal ecrit, sinon on reessaie en supposant de l'anglais
                        trans, lang = None, "?"
                        if looks_french(text):
                            lang = "fr"
                        else:
                            t2, _ = google_translate_safe(lexicon_expand(text), cfg["target"], source="en")
                            if t2 and t2.strip().lower() != text.strip().lower():
                                trans, lang = t2, "en"
                except Exception as e:  # noqa
                    # affiche l'erreur sous le message (la barre d'etat est vite ecrasee par le pont)
                    trans, lang = "\u26a0 traduction impossible : %s" % e, "?"
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
                elif item[0] == "update":
                    self.update_btn.config(text="Mise \u00e0 jour %s dispo" % item[1])
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
        parts.append((author, *marks) if mine else (author, *marks, "name"))
        parts.append((": ", *marks))
        _plain, spans = split_links(raw if raw is not None else text)
        for seg, code in spans:
            parts.append((seg, *marks, "link_" + code) if code else (seg, *marks))
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
            self.out_result.config(text="Langue de reponse : %s (auto, d'apres %s)" % (lang, author), fg="#8a97a6")

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
    def send_out(self):
        txt = self.out_entry.get().strip()
        lang = (self.out_lang.get() or "en").strip().lower()
        if not txt:
            return
        self.out_result.config(text="Traduction en cours...", fg="#8a97a6")

        def run():
            try:
                res, _ = google_translate(txt, lang)
                self.outq.put(("out", txt, res, lang, None))
            except Exception as e:  # noqa
                self.outq.put(("out", txt, "", lang, str(e)))

        threading.Thread(target=run, daemon=True).start()

    def show_out(self, src, res, lang, err):
        if err:
            self.out_result.config(text="Erreur : %s" % err, fg="#ff7070")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(res)
        self.root.update()
        self.out_result.config(text="Copie ! (Ctrl+V dans WoW)  [%s] %s" % (lang.upper(), res), fg="#7ee787")
        self.add(("Vous \u2192 [%s] " % lang.upper(), "me"), (src + "\n", "me"), ("\u2192 " + res + "\n", "trans"))
        self.out_entry.delete(0, "end")
        self.cfg["out_lang"] = lang
        save_config(self.cfg)

    # ---- fenetre sans cadre : deplacement / redimensionnement -------------
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

    def _drag_start(self, e):
        self._dx, self._dy = e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y()

    def _drag_move(self, e):
        self.root.geometry("+%d+%d" % (e.x_root - self._dx, e.y_root - self._dy))

    def _resize_start(self, e):
        self._rx, self._ry = e.x_root, e.y_root
        self._rw, self._rh = self.root.winfo_width(), self.root.winfo_height()

    def _resize_move(self, e):
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
