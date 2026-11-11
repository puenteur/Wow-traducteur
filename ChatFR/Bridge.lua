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
  CHAT_MSG_SAY = "say", CHAT_MSG_EMOTE = "say", CHAT_MSG_YELL = "yell",
  CHAT_MSG_PARTY = "party", CHAT_MSG_PARTY_LEADER = "party",
  CHAT_MSG_INSTANCE_CHAT = "party", CHAT_MSG_INSTANCE_CHAT_LEADER = "party",
  CHAT_MSG_RAID = "raid", CHAT_MSG_RAID_LEADER = "raid", CHAT_MSG_RAID_WARNING = "raid",
  CHAT_MSG_GUILD = "guild", CHAT_MSG_OFFICER = "officer",
  CHAT_MSG_WHISPER = "whisper", CHAT_MSG_BN_WHISPER = "whisper",
  CHAT_MSG_CHANNEL = "channel", CHAT_MSG_COMMUNITIES_CHANNEL = "channel",
  -- options (Reglages ChatFR, decochees par defaut) : affiches par le traducteur sans traduction
  CHAT_MSG_MONSTER_SAY = "npc", CHAT_MSG_MONSTER_YELL = "npc", CHAT_MSG_MONSTER_WHISPER = "npc",
  CHAT_MSG_MONSTER_EMOTE = "npc", CHAT_MSG_MONSTER_PARTY = "npc",
  CHAT_MSG_RAID_BOSS_EMOTE = "npc", CHAT_MSG_RAID_BOSS_WHISPER = "npc",
  CHAT_MSG_SYSTEM = "system", CHAT_MSG_TEXT_EMOTE = "system", CHAT_MSG_COMBAT_FACTION_CHANGE = "faction",
  CHAT_MSG_COMBAT_XP_GAIN = "system", CHAT_MSG_COMBAT_HONOR_GAIN = "system", CHAT_MSG_SKILL = "system",
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
  frame:SetPoint("TOPLEFT", UIParent, "TOPLEFT", INSET * u / CELL, -INSET * u / CELL)
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

function ns.BridgeSetShown(on)
  if not frame then return end
  if on then frame:Show() else frame:Hide() end
end

-- Liens du tchat : on garde le type (objet, quete, sort...) et la qualite de l'objet pour que
-- le traducteur puisse les colorer. Format : \2 code \3 [Nom] \4  (code = i0..i7 objet par
-- qualite, q quete, s sort, e enchantement/metier, a haut fait, o autre).
local QUALITY = { ["9d9d9d"] = "0", ["ffffff"] = "1", ["1eff00"] = "2", ["0070dd"] = "3",
                  ["a335ee"] = "4", ["ff8000"] = "5", ["e6cc80"] = "6", ["00ccff"] = "7" }
local LTYPE = { item = "i", quest = "q", spell = "s", talent = "s", enchant = "e",
                trade = "e", achievement = "a" }

local function LinkMark(color, ltype, name)
  local code = LTYPE[ltype] or "o"
  if code == "i" then
    -- couleur en hexa (|cffa335ee) ou par nom (|cnIQ4: = qualite 4)
    local q = color and (color:match("^IQ(%d)$") or QUALITY[color:lower():sub(3)])
    code = "i" .. (q or "1")
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
  if #lines == 0 then                                      -- objet pas encore connu du jeu : on reessaie
    if (tries or 0) < 3 and C_Timer and C_Timer.After then
      C_Timer.After(1, function() pcall(PushTip, hlink, name, (tries or 0) + 1) end)
    end
    return
  end
  local body, nm = "", name:gsub("[\1-\31]", " ")
  for _, t in ipairs(lines) do
    local nb = (body == "") and t or (body .. "\30" .. t)
    if #nb + #nm + 8 > MAXREC then break end
    body = nb
  end
  tipSent[name] = now
  queue[#queue + 1] = "tip\31" .. body .. "\31" .. nm .. "\31"
  if #queue > MAXQ then table.remove(queue, 1) end
end

function ns.BridgePush(event, msg, author, chan)
  if not frame or not (ChatFRDB and ChatFRDB.bridge) then return end
  local kind = KIND[event]
  if not kind or type(msg) ~= "string" or type(author) ~= "string" then return end
  if issecretvalue and (issecretvalue(msg) or issecretvalue(author) or issecretvalue(chan)) then return end
  local raw = msg                                     -- liens d'origine, pour les infobulles
  msg = msg:gsub("[\1-\31]", " ")
  msg = msg:gsub("|c(%x%x%x%x%x%x%x%x)|H([^:|]+):[^|]*|h(.-)|h|r", LinkMark)
  msg = msg:gsub("|cn([%w_]+):|H([^:|]+):[^|]*|h(.-)|h|r", LinkMark)
  msg = msg:gsub("|H([^:|]+):[^|]*|h(.-)|h", function(t, n) return LinkMark(nil, t, n) end)
  msg = CleanCodes(msg)
  chan = (type(chan) == "string") and chan:gsub("^%d+%.%s*", ""):gsub("[\1-\31]", " ") or ""
  author = author:gsub("[\1-\31]", " ")
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
    if TIP_TYPES[ltype] then pcall(PushTip, hl, name) end
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
end

local init = CreateFrame("Frame")
init:RegisterEvent("PLAYER_LOGIN")
init:SetScript("OnEvent", function()
  local ok, err = pcall(Create)
  if not ok then print("|cff33ccffChatFR|r: pont image indisponible : " .. tostring(err)) end
end)
