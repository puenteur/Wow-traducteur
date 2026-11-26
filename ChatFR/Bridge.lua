-- Pont image : WoW n'ecrit le log du tchat sur le disque qu'a la fermeture du jeu.
-- On dessine donc en haut a gauche de l'ecran une petite bande de cases colorees qui
-- contient le dernier message ; translator.py la lit par capture d'ecran.
-- Cases : 64 x 16, 6 pixels chacune. Chaque case = 3 bits (couleur R/V/B allumee ou non :
-- l'ecran deforme les couleurs, 2 niveaux seulement pour rester lisible).

local ADDON_NAME, ns = ...

local COLS, ROWS, CELL = 64, 16, 6      -- 16 lignes : assez pour un message de 255 caracteres + canal + pseudo
local INSET = 12
local NCELLS = COLS * ROWS
local MAGIC = { { 1, 0, 0 }, { 0, 1, 0 }, { 0, 0, 1 }, { 1, 1, 1 } }
local HOLD = 0.40        -- secondes d'affichage de chaque message
local MAXQ = 60          -- file d'attente maximale
local MAXREC = math.floor((NCELLS - #MAGIC) * 3 / 8) - 5   -- octets utiles par message

local floor = math.floor
local frame
local cells = {}
local queue = {}
local seq = math.random(1, 255)
local nextAt = 0

local KIND = {
  CHAT_MSG_SAY = "say", CHAT_MSG_EMOTE = "emote", CHAT_MSG_YELL = "yell",   -- /e : orange, comme dans le jeu
  CHAT_MSG_PARTY = "party", CHAT_MSG_PARTY_LEADER = "party", CHAT_MSG_PING = "ping",   -- pings ("Par ici"...) : texte du jeu, sans traduction
  CHAT_MSG_INSTANCE_CHAT = "party", CHAT_MSG_INSTANCE_CHAT_LEADER = "party",
  CHAT_MSG_RAID = "raid", CHAT_MSG_RAID_LEADER = "raid", CHAT_MSG_RAID_WARNING = "raid",
  CHAT_MSG_GUILD = "guild", CHAT_MSG_OFFICER = "officer",
  CHAT_MSG_WHISPER = "whisper", CHAT_MSG_BN_WHISPER = "whisper",
  CHAT_MSG_CHANNEL = "channel", CHAT_MSG_COMMUNITIES_CHANNEL = "channel",
  -- options (Reglages ChatFR, decochees par defaut) : affiches par le traducteur sans traduction
  CHAT_MSG_MONSTER_SAY = "npc", CHAT_MSG_MONSTER_YELL = "npc", CHAT_MSG_MONSTER_WHISPER = "npc",
  CHAT_MSG_MONSTER_EMOTE = "npc", CHAT_MSG_MONSTER_PARTY = "npc",
  CHAT_MSG_RAID_BOSS_EMOTE = "npc", CHAT_MSG_RAID_BOSS_WHISPER = "npc",
  CHAT_MSG_SYSTEM = "system", CHAT_MSG_TEXT_EMOTE = "temote",   -- /genou, /salut... : orange, sans traduction
  CHAT_MSG_COMBAT_FACTION_CHANGE = "faction",
  CHAT_MSG_COMBAT_XP_GAIN = "faction",   -- experience : bleu-violet dans le jeu, comme la reputation
  CHAT_MSG_COMBAT_HONOR_GAIN = "system",
  CHAT_MSG_SKILL = "faction",   -- competences : bleu dans le jeu, comme la reputation (meme couleur dans le traducteur)
  CHAT_MSG_AFK = "system", CHAT_MSG_DND = "system",
  CHAT_MSG_LOOT = "loot", CHAT_MSG_MONEY = "loot", CHAT_MSG_CURRENCY = "loot",
  CHATFR_SPENT = "spent",
  -- tes propres chuchotements envoyes ("A [Jonathan] : Yo") : affiches sans traduction
  CHAT_MSG_WHISPER_INFORM = "whisper_out", CHAT_MSG_BN_WHISPER_INFORM = "whisper_out",          -- pas un evenement du jeu : argent depense chez un marchand (en rouge)
}
ns.BRIDGE_KIND = KIND

-- CRC-16/XMODEM (identique a binascii.crc_hqx(data, 0) cote Python)
local function crc16(s)
  local crc = 0
  for i = 1, #s do
    crc = bit.bxor(crc, bit.lshift(s:byte(i), 8))
    for _ = 1, 8 do
      if bit.band(crc, 0x8000) ~= 0 then
        crc = bit.band(bit.bxor(bit.lshift(crc, 1), 0x1021), 0xFFFF)
      else
        crc = bit.band(bit.lshift(crc, 1), 0xFFFF)
      end
    end
  end
  return crc
end

local function Pack(rec)
  local n, crc = #rec, crc16(rec)
  return string.char(seq, floor(n / 256), n % 256, floor(crc / 256), crc % 256) .. rec
end

local function SetCell(i, r, g, b)
  cells[i]:SetColorTexture(r, g, b, 1)
end

local function Render(packet)
  for i = 1, #MAGIC do SetCell(i, MAGIC[i][1], MAGIC[i][2], MAGIC[i][3]) end
  local idx = #MAGIC + 1
  local function emit(v)
    if idx <= NCELLS then
      SetCell(idx, floor(v / 4), floor(v / 2) % 2, v % 2)
      idx = idx + 1
    end
  end
  local acc, nb = 0, 0
  for i = 1, #packet do
    acc = acc * 256 + packet:byte(i)
    nb = nb + 8
    while nb >= 3 do
      local p = 2 ^ (nb - 3)
      local v = floor(acc / p)
      acc = acc - v * p
      nb = nb - 3
      emit(v)
    end
  end
  if nb > 0 then emit(acc * 2 ^ (3 - nb)) end
  for i = idx, NCELLS do SetCell(i, 0, 0, 0) end
end

local function Layout()
  local ph
  if GetPhysicalScreenSize then
    local _, h = GetPhysicalScreenSize()
    ph = h
  end
  local u
  if ph and ph > 0 then
    u = CELL * UIParent:GetHeight() / ph
  else
    u = CELL / UIParent:GetEffectiveScale()
  end
  frame:SetSize(COLS * u, ROWS * u)
  -- decalee de 12 pixels vers l'interieur : le bord de la fenetre de jeu peut depasser de
  -- l'ecran (fenetre maximisee) et couper la premiere ligne de cases.
  frame:ClearAllPoints()
  -- u = taille d'une case (CELL pixels) : INSET est en pixels
  -- coin choisi avec /cfr pont coin (haut-gauche par defaut) ; le traducteur cherche dans les 4 coins
  local corner = ChatFRDB and ChatFRDB.bridgecorner
  if corner ~= "TOPRIGHT" and corner ~= "BOTTOMLEFT" and corner ~= "BOTTOMRIGHT" then corner = "TOPLEFT" end
  local d = INSET * u / CELL
  local sx = (corner == "TOPRIGHT" or corner == "BOTTOMRIGHT") and -d or d
  local sy = (corner == "BOTTOMLEFT" or corner == "BOTTOMRIGHT") and d or -d
  frame:SetPoint(corner, UIParent, corner, sx, sy)
  for i = 1, NCELLS do
    local c, r = (i - 1) % COLS, floor((i - 1) / COLS)
    local t = cells[i]
    t:ClearAllPoints()
    t:SetPoint("TOPLEFT", frame, "TOPLEFT", c * u, -r * u)
    t:SetSize(u, u)
  end
end

local function Tick(_, el)
  nextAt = nextAt - el
  if nextAt > 0 or #queue == 0 then return end
  local rec = table.remove(queue, 1)
  seq = seq % 255 + 1
  Render(Pack(rec))
  nextAt = HOLD
end

function ns.BridgeLayout()
  if frame then Layout() end
end

function ns.BridgeSetShown(on)
  if not frame then return end
  if on then frame:Show() else frame:Hide() end
end

-- Liens du tchat : on garde le type (objet, quete, sort...) et la qualite de l'objet pour que
-- le traducteur puisse les colorer. Format : \2 code \3 [Nom] \4  (code = i0..i7 objet par
-- qualite, q quete, s sort, e enchantement/metier, a haut fait, o autre).
local QUALITY = { ["9d9d9d"] = "0", ["ffffff"] = "1", ["1eff00"] = "2", ["0070dd"] = "3",
                  ["a335ee"] = "4", ["ff8000"] = "5", ["e6cc80"] = "6", ["00ccff"] = "7" }
local LTYPE = { item = "i", quest = "q", questie = "q", spell = "s", talent = "s", enchant = "e",
                trade = "e", achievement = "a" }

-- Quete : couleur selon son niveau et le tien, comme dans le tchat du jeu (q0 gris, q1 vert, q2 jaune,
-- q3 orange, q4 rouge). Lien "|Hquest:ID:niveau...|h". Niveau inconnu ou adaptatif : "q" (couleur par defaut).
local QDIFF = { trivial = "q0", standard = "q1", difficult = "q2", verydifficult = "q3", impossible = "q4" }

-- Couleurs de difficulte du jeu (repli si QuestDifficultyColors est absent)
local QHEX = { q0 = { 0.5, 0.5, 0.5 }, q1 = { 0.25, 0.75, 0.25 }, q2 = { 1, 1, 0 },
               q3 = { 1, 0.5, 0.25 }, q4 = { 1, 0.1, 0.1 } }

local function CodeFromRGB(r, g, b)
  local best, bestD = nil, 0.12                        -- tolerance : couleur tres proche seulement
  for key, code in pairs(QDIFF) do
    local q = type(QuestDifficultyColors) == "table" and QuestDifficultyColors[key]
    local qr, qg, qb
    if q and q.r then qr, qg, qb = q.r, q.g, q.b else qr, qg, qb = unpack(QHEX[code]) end
    local d = math.abs(qr - r) + math.abs(qg - g) + math.abs(qb - b)
    if d < bestD then best, bestD = code, d end
  end
  return best
end

local function QuestCode(data, color)
  local id = tonumber((data or ""):match("^:(%d+)"))
  local lvl = tonumber((data or ""):match("^:%d+:(%-?%d+)"))
  -- Forever : niveau 0 dans le lien ("quest:202:0") -> on demande le niveau au jeu
  if (not lvl or lvl <= 0) and id and C_QuestLog and C_QuestLog.GetQuestDifficultyLevel then
    local ok, l = pcall(C_QuestLog.GetQuestDifficultyLevel, id)
    if ok and type(l) == "number" and l > 0 then lvl = l end
  end
  local me = UnitLevel and UnitLevel("player")
  if not lvl or lvl <= 0 or not me or me <= 0 then
    -- dernier recours : la couleur que le jeu a mise sur le lien (|cffff1a1a...)
    local hex = type(color) == "string" and color:match("^%x%x(%x%x%x%x%x%x)$")
    if hex then
      local code = CodeFromRGB(tonumber(hex:sub(1, 2), 16) / 255, tonumber(hex:sub(3, 4), 16) / 255,
                               tonumber(hex:sub(5, 6), 16) / 255)
      if code then return code end
    end
    return "q"
  end
  -- d'abord les couleurs du jeu lui-meme (memes regles que son tchat)
  local okC, c = pcall(GetQuestDifficultyColor, lvl)
  if okC and type(c) == "table" and c.r then
    local code = CodeFromRGB(c.r, c.g, c.b)
    if code then return code end
  end
  -- sinon : regles classiques
  local d = lvl - me
  if d >= 5 then return "q4" elseif d >= 3 then return "q3" elseif d >= -2 then return "q2" end
  local okG, green = pcall(function()
    return (GetQuestGreenRange and GetQuestGreenRange("player"))
        or (UnitQuestTrivialLevelRange and UnitQuestTrivialLevelRange("player"))
  end)
  if not okG or type(green) ~= "number" then
    green = me <= 5 and 5 or me <= 39 and (5 + math.floor(me / 10)) or me <= 59 and (1 + math.floor(me / 5)) or 9
  end
  return (-d <= green) and "q1" or "q0"
end

-- Quete d'un autre joueur, hors de ton journal : le jeu ne la connait pas encore (niveau 0, nom dans
-- la langue de l'envoyeur). On lui demande de la charger (BridgePush attend un peu), puis on prend
-- son niveau (couleur) et son nom dans la langue de TON jeu.
local function QuestTitle(id)
  local f = id and C_QuestLog and C_QuestLog.GetTitleForQuestID
  if not f then return nil end
  local ok, t = pcall(f, id)
  if ok and type(t) == "string" and t ~= "" and not (issecretvalue and issecretvalue(t)) then return t end
end

local function QuestKnown(id)
  if QuestTitle(id) then return true end
  local f = C_QuestLog and C_QuestLog.GetQuestDifficultyLevel
  local ok, l = pcall(f, id)
  return ok and type(l) == "number" and l > 0
end

-- Lien de quete reecrit par Questie : "|Hquestie:180:joueur|h[[26] WANTED: X (180)]|h"
-- -> nom "[WANTED: X]" et niveau 26 (pris dans le texte du lien)
local function QuestieName(name)
  local lv, nm = name:match("^%[%[(%-?%d+)[^%]]*%]%s*(.-)%s*%(%d+%)%]$")
  if nm and nm ~= "" then return "[" .. nm .. "]", tonumber(lv) end
  return name, nil
end

local function LinkMark(color, ltype, data, name)
  local code = LTYPE[ltype] or "o"
  if code == "i" then
    -- couleur en hexa (|cffa335ee) ou par nom (|cnIQ4: = qualite 4)
    local q = color and (color:match("^IQ(%d)$") or QUALITY[color:lower():sub(3)])
    code = "i" .. (q or "1")
  elseif code == "q" then
    if ltype == "questie" then
      local nm, lv = QuestieName(name)
      name = nm
      data = ":" .. ((data or ""):match("^:(%d+)") or "0") .. ":" .. (lv or 0)
    end
    local ok, qc = pcall(QuestCode, data, color)
    code = ok and qc or "q"
    local t = QuestTitle(tonumber((data or ""):match("^:(%d+)")))
    if t then name = "[" .. t:gsub("[\1-\31]", " ") .. "]" end
  end
  return "\2" .. code .. "\3" .. name .. "\4"
end

-- Infobulles des objets / quetes lies dans le tchat : lues dans le jeu (en francais, vraies stats)
-- et envoyees UNE fois par session et par objet. Le texte va dans le champ "canal" et le message
-- reste vide : les anciens traducteurs ignorent ces enregistrements.
local tipSent, scan = {}, nil

-- Icones de pieces ("25|A:coin-copper:14:14:2:0|a", ou |T...CopperIcon|t) -> "25 pc", puis on
-- enleve les autres icones et codes couleur.
local function CleanCodes(t)
  t = t:gsub("|A:[^|]*coin%-gold[^|]*|a", " po"):gsub("|A:[^|]*coin%-silver[^|]*|a", " pa")
       :gsub("|A:[^|]*coin%-copper[^|]*|a", " pc")
  t = t:gsub("|T[^|]*[Gg]old[Ii]con[^|]*|t", " po"):gsub("|T[^|]*[Ss]ilver[Ii]con[^|]*|t", " pa")
       :gsub("|T[^|]*[Cc]opper[Ii]con[^|]*|t", " pc")
  -- marque de raid en image (croix, crane...) -> "{rt7}" : le traducteur l'affiche en symbole
  t = t:gsub("|T[^|]*RaidTargetingIcon_(%d)[^|]*|t", "{rt%1}")
  t = t:gsub("|c%x%x%x%x%x%x%x%x", ""):gsub("|cn[%w_]+:", ""):gsub("|r", "")
       :gsub("|T.-|t", ""):gsub("|A.-|a", "")
  return t
end
local TIP_TYPES = { item = true, quest = true, spell = true, enchant = true }

local function TipLines(hlink)
  if not scan then
    scan = CreateFrame("GameTooltip", "ChatFRScanTip", nil, "GameTooltipTemplate")
  end
  scan:SetOwner(WorldFrame, "ANCHOR_NONE")
  scan:ClearLines()
  if not pcall(scan.SetHyperlink, scan, hlink) then return {} end
  local out = {}
  for i = 2, math.min(scan:NumLines() or 0, 18) do          -- ligne 1 = le nom, deja connu
    local l, r = _G["ChatFRScanTipTextLeft" .. i], _G["ChatFRScanTipTextRight" .. i]
    local t = l and l:GetText()
    if t and not (issecretvalue and issecretvalue(t)) and t ~= "" then
      local rt = r and r:IsShown() and r:GetText()
      if rt and not (issecretvalue and issecretvalue(rt)) and rt ~= "" then t = t .. "   " .. rt end
      t = CleanCodes(t):gsub("[\1-\31]", " ")
      out[#out + 1] = t
    end
  end
  scan:Hide()
  return out
end

local function PushTip(hlink, name, tries)
  -- une fois toutes les 2 min par objet au plus (si le traducteur a ete relance entre-temps)
  local now = GetTime and GetTime() or 0
  if (tipSent[name] and now - tipSent[name] < 120) or not frame then return end
  local lines = TipLines(hlink)
  -- objectif de quete dont le nom n'est pas encore charge par le jeu ("- 1 x") : on reessaie
  local partial = false
  for _, t in ipairs(lines) do
    if t:match("^%s*%-?%s*%d+%s*x%s*$") then partial = true; break end
  end
  if #lines == 0 or partial then                           -- pas encore connu du jeu : on reessaie
    if (tries or 0) < 3 and C_Timer and C_Timer.After then
      C_Timer.After(1, function() pcall(PushTip, hlink, name, (tries or 0) + 1) end)
      return
    end
    if #lines == 0 then return end
    -- toujours incomplet : on retire les objectifs vides (et le titre "Conditions :" s'il reste seul)
    local kept = {}
    for _, t in ipairs(lines) do
      if not t:match("^%s*%-?%s*%d+%s*x%s*$") then kept[#kept + 1] = t end
    end
    if #kept > 0 and kept[#kept]:match(":%s*$") then kept[#kept] = nil end
    lines = kept
    if #lines == 0 then return end
  end
  local body, nm = "", name:gsub("[\1-\31]", " ")
  -- page Wowhead de l'objet (par son numero) : "item=12345" dans le dernier champ (vide avant la 2.1.0,
  -- ignore par les anciens traducteurs). Avant, le traducteur cherchait le nom sur Wowhead : souvent rien.
  local lt, id = hlink:match("^(%a+):(%d+)")
  local wh = ({ item = "item", quest = "quest", spell = "spell", enchant = "spell" })[lt or ""]
  wh = (wh and id) and (wh .. "=" .. id) or ""
  for _, t in ipairs(lines) do
    local nb = (body == "") and t or (body .. "\30" .. t)
    if #nb + #nm + #wh + 8 > MAXREC then break end
    body = nb
  end
  tipSent[name] = now
  queue[#queue + 1] = "tip\31" .. body .. "\31" .. nm .. "\31" .. wh
  if #queue > MAXQ then table.remove(queue, 1) end
end

-- [Vous avez succombe.] : les derniers coups recus, lus dans le recapitulatif de mort du jeu
-- (C_DeathRecap, celui de la fenetre de Blizzard). Envoye comme une fiche : le traducteur l'affiche au survol.
-- Pas de limite de 2 min : chaque mort a son recapitulatif. Valeur illisible ("secrete") : ligne sautee.
local function Plain(v)
  if v == nil or (issecretvalue and issecretvalue(v)) then return nil end
  return v
end

local function PushDeath(hlink, name)
  local id = tonumber(hlink:match("^death:(%d+)"))
  -- recapitulatif de mort : C_DeathRecap.GetRecapEvents (Forever / jeu actuel), DeathRecap_GetEvents (ancien nom)
  local get = (C_DeathRecap and C_DeathRecap.GetRecapEvents) or DeathRecap_GetEvents
  if not (frame and get) then return end
  local ok, events = pcall(get, id)
  if not ok or type(events) ~= "table" or #events == 0 then return end
  local list = {}
  for _, e in ipairs(events) do
    if type(e) == "table" then list[#list + 1] = e end
  end
  -- le plus recent d'abord (le coup fatal en haut), comme le recapitulatif de Blizzard
  table.sort(list, function(a, b) return (Plain(a.timestamp) or 0) > (Plain(b.timestamp) or 0) end)
  local last = Plain(list[1] and list[1].timestamp)
  local lines = { "Derniers coups re\195\167us :" }
  for _, e in ipairs(list) do
    local amount = Plain(e.amount)
    local spell = Plain(e.spellName)
    local ev = Plain(e.event) or ""
    if not spell then
      if ev:find("^SWING") then spell = "M\195\170l\195\169e"
      elseif ev:find("^ENVIRONMENTAL") then spell = "Environnement"
      else spell = "?" end
    end
    local src = (not Plain(e.hideCaster)) and Plain(e.sourceName) or nil
    local t = Plain(e.timestamp)
    local when = (t and last) and string.format("%.1f s", t - last):gsub("%.", ",") or ""
    if amount and type(amount) == "number" then
      local l = string.format("-%d  %s", amount, spell)
      if src and src ~= "" then l = l .. " (" .. src .. ")" end
      if Plain(e.critical) then l = l .. " critique" end
      if when ~= "" then l = when .. "   " .. l end
      lines[#lines + 1] = l:gsub("[\1-\31]", " ")
    end
    if #lines >= 11 then break end
  end
  if #lines < 2 then return end
  local body, nm = "", name:gsub("[\1-\31]", " ")
  for _, t in ipairs(lines) do
    local nb = (body == "") and t or (body .. "\30" .. t)
    if #nb + #nm + 10 > MAXREC then break end
    body = nb
  end
  queue[#queue + 1] = "tip\31" .. body .. "\31" .. nm .. "\31-"        -- "-" : pas de page Wowhead
end

-- Couleur de classe du joueur ("C69B6D"), seulement si le jeu colore les noms pour ce type de
-- message (option du tchat "Couleurs de classe"). nil pour un PNJ ou si l'info manque.
function ns.ClassColorHex(event, guid, chanIndex)
  if type(guid) ~= "string" or guid == "" or (issecretvalue and issecretvalue(guid)) then return nil end
  if not GetPlayerInfoByGUID then return nil end
  local t = event:sub(10)
  if t:sub(1, 7) == "CHANNEL" then t = "CHANNEL" .. tostring(chanIndex or "") end
  local info = ChatTypeInfo and ChatTypeInfo[t]
  if not info then return nil end
  local on
  if Chat_ShouldColorChatByClass then on = Chat_ShouldColorChatByClass(info) else on = info.colorNameByClass end
  if not on then return nil end
  local _, cls = GetPlayerInfoByGUID(guid)
  local c = cls and ((CUSTOM_CLASS_COLORS and CUSTOM_CLASS_COLORS[cls]) or (RAID_CLASS_COLORS and RAID_CLASS_COLORS[cls]))
  if not c or not c.r then return nil end
  return string.format("%02X%02X%02X", math.floor(c.r * 255 + 0.5), math.floor(c.g * 255 + 0.5), math.floor(c.b * 255 + 0.5))
end

-- Fiche du joueur au survol de son pseudo dans le traducteur : classe, race et niveau.
-- Classe et race : le jeu les donne pour tout joueur qui parle (GetPlayerInfoByGUID).
-- Niveau : seulement s'il est dans ton groupe, ta guilde, tes amis, ou en cible / sous la souris.
local whoSent, guildLvl, seenLvl, whoGuid, whoNoLvl, guildInfo = {}, {}, {}, {}, {}, {}
local gf = CreateFrame("Frame")
gf:RegisterEvent("GUILD_ROSTER_UPDATE")
gf:RegisterEvent("PLAYER_ENTERING_WORLD")
gf:RegisterEvent("UPDATE_MOUSEOVER_UNIT")
gf:RegisterEvent("PLAYER_TARGET_CHANGED")
gf:RegisterEvent("NAME_PLATE_UNIT_ADDED")
gf:RegisterEvent("WHO_LIST_UPDATE")
-- niveau d'un joueur vu en jeu (souris, cible, barre de vie, resultat d'un /qui) : garde pour la session.
-- S'il avait deja une fiche "niveau inconnu", elle est renvoyee avec le niveau.
local function Seen(name, lv)
  if type(name) ~= "string" or name == "" or type(lv) ~= "number" or lv <= 0 then return end
  if issecretvalue and (issecretvalue(name) or issecretvalue(lv)) then return end
  local short = name:match("^[^%-]+") or name
  if seenLvl[short] == lv then return end
  seenLvl[short] = lv
  for author in pairs(whoNoLvl) do
    if (author:match("^[^%-]+") or author) == short then
      whoNoLvl[author], whoSent[author] = nil, nil
      if ns.PushWho then pcall(ns.PushWho, author, whoGuid[author]) end
    end
  end
end
local function SeenUnit(u)
  local okP, isP = pcall(UnitIsPlayer, u)
  if not (okP and isP) then return end
  local okN, n = pcall(UnitName, u)
  local okL, l = pcall(UnitLevel, u)
  if okN and okL then Seen(n, l) end
end
gf:SetScript("OnEvent", function(_, event, arg1)
  if event == "UPDATE_MOUSEOVER_UNIT" then return SeenUnit("mouseover") end
  if event == "PLAYER_TARGET_CHANGED" then return SeenUnit("target") end
  if event == "NAME_PLATE_UNIT_ADDED" then return arg1 and SeenUnit(arg1) end
  if event == "WHO_LIST_UPDATE" then
    local n = (C_FriendList and C_FriendList.GetNumWhoResults and C_FriendList.GetNumWhoResults()) or 0
    for i = 1, n do
      local ok, w = pcall(C_FriendList.GetWhoInfo, i)
      if ok and type(w) == "table" then Seen(w.fullName, w.level) end
    end
    return
  end
  if event == "PLAYER_ENTERING_WORLD" then
    if C_GuildInfo and C_GuildInfo.GuildRoster then pcall(C_GuildInfo.GuildRoster) end
    return
  end
  if not (GetNumGuildMembers and GetGuildRosterInfo) then return end
  local n = GetNumGuildMembers() or 0
  for i = 1, n do
    local nm, rank, _, lv, cls, zone = GetGuildRosterInfo(i)
    if type(nm) == "string" and type(lv) == "number" then
      local short = nm:match("^[^%-]+") or nm
      guildLvl[short] = lv
      guildInfo[short] = { lv = lv, cls = cls, rank = rank, zone = zone }
    end
  end
end)

local function LevelOf(short, guid)
  for _, u in ipairs({ "target", "mouseover", "focus" }) do
    local okG, g = pcall(UnitGUID, u)
    if okG and g and g == guid then
      local okL, l = pcall(UnitLevel, u)
      if okL and type(l) == "number" and l > 0 then return l end
    end
  end
  if UnitInParty and (UnitInParty(short) or (UnitInRaid and UnitInRaid(short))) then
    local okL, l = pcall(UnitLevel, short)
    if okL and type(l) == "number" and l > 0 then return l end
  end
  if guildLvl[short] then return guildLvl[short] end
  if seenLvl[short] then return seenLvl[short] end
  if C_FriendList and C_FriendList.GetFriendInfo then
    local okF, f = pcall(C_FriendList.GetFriendInfo, short)
    if okF and type(f) == "table" and type(f.level) == "number" and f.level > 0 then return f.level end
  end
  return nil
end

function ns.PushWho(author, guid)
  if not frame or type(author) ~= "string" or author == "" or type(guid) ~= "string" or guid == "" then return end
  if issecretvalue and (issecretvalue(author) or issecretvalue(guid)) then return end
  if not GetPlayerInfoByGUID or not guid:find("^Player") then return end
  local now = GetTime and GetTime() or 0
  if whoSent[author] and now - whoSent[author] < 300 then return end
  if #queue > 20 then return end           -- tchat tres charge : les messages d'abord, la fiche plus tard
  local okI, cls, _, race = pcall(GetPlayerInfoByGUID, guid)
  if not okI or type(cls) ~= "string" or cls == "" then return end
  local short = author:match("^[^%-]+") or author
  local lv = LevelOf(short, guid)
  local L = ns.L or function(fr) return fr end
  local l1 = cls .. ((type(race) == "string" and race ~= "") and (" - " .. race) or "")
  local l2 = lv and (L("Niveau ", "Level ") .. lv)
    or L("Niveau inconnu : passe ta souris sur lui en jeu, cible-le ou fais /qui " .. short,
         "Level unknown: hover or target them in game, or type /who " .. short)
  whoSent[author], whoGuid[author], whoNoLvl[author] = now, guid, (not lv) or nil
  queue[#queue + 1] = "who\31" .. (l1 .. "\30" .. l2):gsub("[\1-\29\31]", " ") .. "\31" .. author:gsub("[\1-\31]", " ") .. "\31"
  if #queue > MAXQ then table.remove(queue, 1) end
end

-- Membre de ta guilde cite dans un message du jeu ("[Zziska Cj] vient de se connecter") : sa fiche vient
-- de la liste de guilde (classe, rang, niveau, zone), sans qu'il ait besoin d'avoir parle.
local function PushWhoName(name)
  if not frame or type(name) ~= "string" or name == "" then return end
  local short = name:match("^[^%-]+") or name
  local g = guildInfo[short]
  if not g then return end
  local now = GetTime and GetTime() or 0
  if whoSent[name] and now - whoSent[name] < 60 then return end
  if #queue > 20 then return end
  local L = ns.L or function(fr) return fr end
  local l1 = (type(g.cls) == "string" and g.cls ~= "") and g.cls or "?"
  if type(g.rank) == "string" and g.rank ~= "" then l1 = l1 .. " - " .. L("Guilde : ", "Guild: ") .. g.rank end
  local lines = l1 .. "\30" .. L("Niveau ", "Level ") .. g.lv
  if type(g.zone) == "string" and g.zone ~= "" then lines = lines .. "\30" .. g.zone end
  whoSent[name] = now
  queue[#queue + 1] = "who\31" .. lines:gsub("[\1-\29\31]", " ") .. "\31" .. name:gsub("[\1-\31]", " ") .. "\31"
  if #queue > MAXQ then table.remove(queue, 1) end
end

function ns.BridgePush(event, msg, author, chan, tries, ncol)
  if not frame or not (ChatFRDB and ChatFRDB.bridge) then return end
  local kind = KIND[event]
  if not kind or type(msg) ~= "string" or type(author) ~= "string" then return end
  if issecretvalue and (issecretvalue(msg) or issecretvalue(author) or issecretvalue(chan)) then return end
  -- Questie ecrit parfois la quete en simple texte, sans lien : "[[25] Les collines aux hurlements (126)]".
  -- On en fait un vrai lien de quete (niveau 25, numero 126) : couleur, nom du jeu et fiche comme les autres.
  if not tries and msg:find("[[", 1, true) then
    msg = msg:gsub("()%[%[(%-?%d+)[^%]]*%]%s*([^%[%]|]-)%s*%((%d+)%)%]", function(pos, lv, nm, id)
      if pos > 2 and msg:sub(pos - 2, pos - 1) == "|h" then return nil end   -- deja dans un lien
      return "|Hquest:" .. id .. ":" .. lv .. "|h[" .. nm .. "]|h"
    end)
  end
  -- quete liee pas encore connue du jeu : on la fait charger et on renvoie le message un peu plus tard
  -- (2 essais max, ~1 s), sinon il partirait en dore avec le nom de l'envoyeur
  local load = C_QuestLog and C_QuestLog.RequestLoadQuestByID
  if load and C_Timer and C_Timer.After and (tries or 0) < 2 then
    local wait = false
    for id in msg:gmatch("|Hquest[ie]*:(%d+)") do
      id = tonumber(id)
      if id and not QuestKnown(id) then pcall(load, id); wait = true end
    end
    if wait then
      C_Timer.After(0.5, function() pcall(ns.BridgePush, event, msg, author, chan, (tries or 0) + 1, ncol) end)
      return
    end
  end
  local raw = msg                                     -- liens d'origine, pour les infobulles
  msg = msg:gsub("[\1-\31]", " ")
  msg = msg:gsub("|c(%x%x%x%x%x%x%x%x)|H([^:|]+)([^|]*)|h(.-)|h|r", LinkMark)
  msg = msg:gsub("|cn([%w_]+):|H([^:|]+)([^|]*)|h(.-)|h|r", LinkMark)
  msg = msg:gsub("|H([^:|]+)([^|]*)|h(.-)|h", function(t, d, n) return LinkMark(nil, t, d, n) end)
  msg = CleanCodes(msg)
  -- le numero du canal ("2. ") est garde : le traducteur l'enleve a l'affichage et s'en sert pour repondre
  chan = (type(chan) == "string") and chan:gsub("[\1-\31]", " ") or ""
  -- pings : l'auteur arrive en lien "|Hplayer:Nom|h[Nom]|h" -> "Nom"
  author = CleanCodes(author:gsub("|H[^|]*|h(.-)|h", "%1")):gsub("[\1-\31]", " ")
  -- ping avec le role devant ("[Tank] [Lenkkah Foidefer]") : on garde seulement le dernier [Nom]
  author = author:match("%[([^%[%]]+)%]%s*$") or author
  -- tes propres messages : espace insecable (invisible) a la fin du canal -> le traducteur sait que
  -- c'est toi (pas de badge, ton pseudo n'est pas "cliquable pour repondre"), sans reglage a remplir
  local me = UnitName and UnitName("player")
  -- (le jeu donne "Malya", le tchat "Malya Effluvia" : on compare le premier mot, sans le royaume)
  if me and author ~= "" and (author == me or author:match("^[^%-%s]+") == me) then chan = chan .. "\194\160" end
  -- couleur de classe collee au type : "say#C69B6D" (le traducteur colore le pseudo)
  if type(ncol) == "string" and ncol:match("^%x%x%x%x%x%x$") then kind = kind .. "#" .. ncol end
  local rec = kind .. "\31" .. chan .. "\31" .. author .. "\31" .. msg
  if #rec > MAXREC then
    local cut = MAXREC
    -- ne pas couper au milieu d'un caractere UTF-8
    while cut > 0 do
      local b = rec:byte(cut + 1)
      if not b or b < 0x80 or b >= 0xC0 then break end
      cut = cut - 1
    end
    rec = rec:sub(1, cut)
  end
  queue[#queue + 1] = rec
  if #queue > MAXQ then table.remove(queue, 1) end
  for hl, ltype, name in (raw or ""):gmatch("|H(([^:|]+):[^|]*)|h%[(.-)%]|h") do
    if ltype == "questie" then                          -- fiche lue avec un vrai lien de quete
      local id = hl:match("^questie:(%d+)")
      name = (QuestieName("[" .. name .. "]")):sub(2, -2)
      hl, ltype = "quest:" .. (id or 0) .. ":0", "quest"
    end
    if ltype == "quest" then name = QuestTitle(tonumber(hl:match("^quest:(%d+)"))) or name end
    if TIP_TYPES[ltype] then pcall(PushTip, hl, name) end
    if ltype == "death" then pcall(PushDeath, hl, name) end
    if ltype == "player" then pcall(PushWhoName, name) end
  end
end

-- Place de la fenetre de tchat principale (onglet compris, zone de saisie NON comprise : le traducteur
-- se pose juste au-dessus, la barre ou l'on tape reste visible), en pixels depuis le coin
-- haut-gauche du jeu : le traducteur s'y place a son premier lancement. Message vide : les anciens
-- traducteurs l'ignorent. Envoye regulierement (le traducteur peut etre lance apres le jeu).
local function PushGeo()
  local cf = _G.ChatFrame1
  if not frame or not frame:IsShown() or not cf or not cf.GetLeft or not GetPhysicalScreenSize then return end
  local _, ph = GetPhysicalScreenSize()
  if not ph or ph <= 0 then return end
  local function edges(f)                                -- bords en unites d'echelle 1
    local l, r, b, t = f:GetLeft(), f:GetRight(), f:GetBottom(), f:GetTop()
    if not (l and r and b and t) then return nil end
    local s = f:GetEffectiveScale()
    return l * s, r * s, b * s, t * s
  end
  local l, r, b, t = edges(cf)
  if not l then return end
  for _, extra in ipairs({ _G.ChatFrame1Tab }) do
    if extra and extra.GetLeft and extra:IsShown() then
      local el, er, eb, et = edges(extra)
      if el then l, r, b, t = math.min(l, el), math.max(r, er), math.min(b, eb), math.max(t, et) end
    end
  end
  local k = ph / 768                                     -- pixels par unite a l'echelle 1
  -- 5e nombre : hauteur de l'image du jeu (le traducteur corrige si le jeu est etire a l'ecran)
  local geo = string.format("%d,%d,%d,%d,%d", floor(l * k), floor(ph - t * k), floor((r - l) * k), floor((t - b) * k), ph)
  queue[#queue + 1] = "geo\31" .. geo .. "\31\31"
  if #queue > MAXQ then table.remove(queue, 1) end
end

-- Version de ChatFR (celle du .toc) : le traducteur la compare a la sienne et previent si l'un des
-- deux n'est pas a jour. Message vide : les anciens traducteurs l'ignorent. Envoye avec la place du tchat.
local function PushVer()
  if not frame or not frame:IsShown() then return end
  local get = (C_AddOns and C_AddOns.GetAddOnMetadata) or GetAddOnMetadata
  if not get then return end
  local ok, v = pcall(get, ADDON_NAME, "Version")
  if not ok or type(v) ~= "string" or not v:match("^[%d%.]+$") then return end
  queue[#queue + 1] = "ver\31" .. v .. "\31\31"
  if #queue > MAXQ then table.remove(queue, 1) end
end

-- Menu du jeu ouvert (menu du tchat "Dire / Groupe...", clic droit sur un joueur, listes deroulantes) :
-- le traducteur, fenetre Windows posee par-dessus le jeu, le cacherait. On le lui signale ("1" / "0"),
-- en tete de file pour qu'il se cache tout de suite ; "1" est repete toutes les 3 s tant que le menu
-- reste ouvert (un traducteur lance entre-temps ne reste pas cache pour rien). Les anciens traducteurs
-- ignorent ce message (texte vide).
local menuOpen, menuSent, mapSince = false, 0, nil
local function BigMapOpen()
  local map = _G.WorldMapFrame
  if not (map and map.IsShown and map:IsShown()) then return false end
  local okM, big = false, nil
  if map.IsMaximized then okM, big = pcall(map.IsMaximized, map) end
  if okM then return big and true or false end
  -- pas de IsMaximized sur ce client : "en grand" = plus des 3/4 de la largeur de l'ecran
  local okW, w = pcall(function() return map:GetWidth() * map:GetEffectiveScale() end)
  local okU, uw = pcall(function() return UIParent:GetWidth() * UIParent:GetEffectiveScale() end)
  return (okW and okU and w and uw and uw > 0 and w >= uw * 0.75) and true or false
end

-- Grandes fenetres du jeu (transmogrification, hotel des ventes, metiers...) qui passent sous le traducteur :
-- s'il y en a une d'ouverte PAR-DESSUS le tchat, le traducteur s'efface comme pour un menu.
local PANELS_UNDER = { "TransmogFrame", "TransmogrifyFrame", "WardrobeFrame", "DressUpFrame", "CollectionsJournal",
  "AuctionHouseFrame", "AuctionFrame", "ProfessionsFrame", "TradeSkillFrame", "CraftFrame", "MerchantFrame",
  "MailFrame", "BankFrame", "AccountBankPanel", "QuestFrame", "GossipFrame", "TradeFrame", "EncounterJournal",
  "PVEFrame", "CommunitiesFrame", "GuildFrame", "AchievementFrame", "CharacterFrame", "SpellBookFrame",
  "PlayerSpellsFrame", "ClassTalentFrame", "TalentFrame", "BarberShopFrame", "ClassTrainerFrame",
  "ItemUpgradeFrame", "ItemSocketingFrame", "InspectFrame", "LootFrame", "TaxiFrame", "SettingsPanel",
  "GameMenuFrame", "CalendarFrame", "FriendsFrame", "HelpFrame", "AddonList" }

local function Box(fr)
  local ok, l, r, t, b, sc = pcall(function()
    return fr:GetLeft(), fr:GetRight(), fr:GetTop(), fr:GetBottom(), fr:GetEffectiveScale()
  end)
  if not ok or not (l and r and t and b and sc) then return nil end
  return l * sc, r * sc, t * sc, b * sc
end

local function PanelOverChat()
  local cf = _G.ChatFrame1
  if not cf then return false end
  local cl, cr, ct, cb = Box(cf)
  if not cl then return false end
  ct = ct + 40                                   -- onglets du tchat au-dessus
  local function Over(fr)
    if type(fr) ~= "table" or fr == cf or not (fr.IsShown and fr:IsShown()) then return false end
    local l, r, t, b = Box(fr)
    return l and l < cr and r > cl and b < ct and t > cb
  end
  for _, name in ipairs(PANELS_UNDER) do
    if Over(_G[name]) then return true end
  end
  -- toutes les fenetres que le jeu ouvre comme "panneaux" (nouvelles fenetres comprises, quel que soit leur nom)
  if GetUIPanel then
    for _, pos in ipairs({ "left", "center", "right", "doublewide", "fullscreen" }) do
      local ok, fr = pcall(GetUIPanel, pos)
      if ok and Over(fr) then return true end
    end
  end
  -- et celles qui se ferment avec Echap
  for _, name in ipairs(UISpecialFrames or {}) do
    if Over(_G[name]) then return true end
  end
  return false
end

local function MenuOpen()
  for _, name in ipairs({ "ChatMenu", "DropDownList1", "L_DropDownList1", "LibDropDownMenu_List1" }) do
    local fr = _G[name]
    if fr and fr.IsShown and fr:IsShown() then return true end
  end
  -- carte du monde ouverte EN GRAND (touche M) : le traducteur se poserait dessus.
  -- La petite carte (fenetree) ne cache pas le traducteur.
  if BigMapOpen() then return true end
  if PanelOverChat() then return true end
  if Menu and Menu.GetManager then
    local ok, open = pcall(function()
      local mg = Menu.GetManager()
      return mg and mg.GetOpenMenu and mg:GetOpenMenu()
    end)
    if ok and open then return true end
  end
  return false
end

local function WatchMenus()
  if not frame or not frame:IsShown() then return end
  local open, now = MenuOpen(), GetTime and GetTime() or 0
  if open ~= menuOpen or (open and now - menuSent > 3) then
    menuOpen, menuSent = open, now
    table.insert(queue, 1, "ui\31" .. (open and "1" or "0") .. "\31\31")
  end
  -- carte en grand : la bande de cases disparait aussi (apres 1 s, le temps que le traducteur lise "1" et se cache).
  -- Le traducteur reste cache tant qu'il ne voit plus la bande ; elle revient avec "0" a la fermeture.
  if BigMapOpen() then
    mapSince = mapSince or now
    if now - mapSince > 1 and frame:GetAlpha() > 0 then frame:SetAlpha(0) end
  else
    mapSince = nil
    if frame:GetAlpha() < 1 then frame:SetAlpha(1) end
  end
end

local function Create()
  frame = CreateFrame("Frame", "ChatFRBridge", UIParent)
  frame:SetFrameStrata("TOOLTIP")
  frame:SetFrameLevel(200)
  frame:EnableMouse(false)
  for i = 1, NCELLS do cells[i] = frame:CreateTexture(nil, "OVERLAY") end
  Layout()
  Render(Pack(""))
  frame:SetScript("OnUpdate", Tick)
  frame:RegisterEvent("UI_SCALE_CHANGED")
  frame:RegisterEvent("DISPLAY_SIZE_CHANGED")
  frame:SetScript("OnEvent", Layout)
  ns.BridgeSetShown(ChatFRDB and ChatFRDB.bridge)
  if C_Timer and C_Timer.After and C_Timer.NewTicker then
    C_Timer.After(5, function() pcall(PushGeo); pcall(PushVer) end)
    C_Timer.NewTicker(30, function() pcall(PushGeo); pcall(PushVer) end)
    C_Timer.NewTicker(0.2, function() pcall(WatchMenus) end)
  end
end

local init = CreateFrame("Frame")
init:RegisterEvent("PLAYER_LOGIN")
init:SetScript("OnEvent", function()
  local ok, err = pcall(Create)
  if not ok then print("|cff33ccffChatFR|r: " .. ((GetLocale and GetLocale() == "frFR") and "pont image indisponible : " or "image bridge unavailable: ") .. tostring(err)) end
end)
