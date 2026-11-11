-- ChatFR : annote le tchat avec la traduction francaise des abreviations
-- courantes, et active /chatlog pour le programme compagnon (translator.py).

local ADDON_NAME, ns = ...

-- Mots qui existent aussi en francais : jamais annotes seuls.
local FRENCH = {}
for w in ([[a an on as or me but de mine port sec tour camp base bar bars mail cap
rare common normal magic balance arms combat rage mana pet boss ah fin son plan place four main]]):gmatch("%S+") do
  FRENCH[w] = true
end

-- Petits mots anglais courants : annotes seulement si /cfr mots est actif.
local COMMON = {}
for w in ([[the i and if then else in at of to for from by like than that this these those
it its their they them we us our you your yours he his him she her hers my myself so with
within about around near close far under above below over into onto through across toward
towards away off out up down here there left right back is are was were be do does did
have has had can could would should will must not no yes yeah yep yup yea ye nope nah ok
okay kk alright fine sure true correct well dont don't doesnt doesn't didnt didn't isnt
isn't arent aren't wasnt wasn't werent weren't havent haven't hasnt hasn't wouldnt
wouldn't couldnt couldn't shouldnt shouldn't cant can't cannot won't wont lets let's
ill i'll ive i've id i'd im i'm youre you're we're]]):gmatch("%S+") do
  COMMON[w] = true
end

-- Dictionnaire : "expression=traduction", charge depuis Dictionary.lua
local DICT, MAXN, FRSUB = {}, 1, {}
for line in ((ns.RAW or "") .. "\n" .. (ns.RAW2 or "") .. "\n" .. (ns.RAW3 or "") .. "\n" .. (ns.RAW4 or "")):gmatch("[^\r\n]+") do
  if line:sub(1, 2) ~= "--" then
    local k, v = line:match("^(.-)=(.+)$")
    if k and v then
      k = k:lower()
      local words = select(2, k:gsub("%S+", ""))
      if words <= 1 and FRENCH[k] and k ~= v:lower() then FRSUB[k] = v end
      local skip = (words <= 1 and (FRENCH[k] or (#k < 2 and not COMMON[k]))) or k == v:lower()
      if not skip then
        DICT[k] = v
        if words > MAXN then MAXN = words end
      end
    end
  end
end

local EVENTS = {
  "CHAT_MSG_SAY", "CHAT_MSG_YELL", "CHAT_MSG_EMOTE",
  "CHAT_MSG_PARTY", "CHAT_MSG_PARTY_LEADER",
  "CHAT_MSG_RAID", "CHAT_MSG_RAID_LEADER", "CHAT_MSG_RAID_WARNING",
  "CHAT_MSG_INSTANCE_CHAT", "CHAT_MSG_INSTANCE_CHAT_LEADER",
  "CHAT_MSG_GUILD", "CHAT_MSG_OFFICER",
  "CHAT_MSG_CHANNEL", "CHAT_MSG_WHISPER", "CHAT_MSG_BN_WHISPER",
  "CHAT_MSG_COMMUNITIES_CHANNEL",
}

local stats = { hit = 0, total = 0 }
local unknown = {}   -- mots non traduits du dernier message

-- Recherche d'un mot seul : exact, puis sans 's, pluriel, -ing, -ed
local function Lookup1(l)
  local t = DICT[l]
  if t then return t, l end
  local b = l:gsub("'s$", "")
  if b ~= l and DICT[b] then return DICT[b], b end
  if #l > 3 then
    local cands = {}
    if l:sub(-3) == "ies" then cands[#cands + 1] = l:sub(1, -4) .. "y" end
    if l:sub(-2) == "es" then cands[#cands + 1] = l:sub(1, -3) end
    if l:sub(-1) == "s" then cands[#cands + 1] = l:sub(1, -2) end
    for _, c in ipairs(cands) do
      local ct = DICT[c]
      if ct and #c >= 3 then
        -- pluriel : on ajoute un "s" si c'est un seul mot simple
        if not ct:find("[%s/]") and not ct:find("[sxz]$") then ct = ct .. "s" end
        return ct, c
      end
    end
    local v = {}
    if l:sub(-3) == "ing" then
      local st = l:sub(1, -4)
      v = { st, st .. "e", (#st > 2 and st:sub(-1) == st:sub(-2, -2)) and st:sub(1, -2) or st }
    elseif l:sub(-2) == "ed" then
      local st = l:sub(1, -3)
      v = { st, l:sub(1, -2), (#st > 2 and st:sub(-1) == st:sub(-2, -2)) and st:sub(1, -2) or st }
    end
    for _, c in ipairs(v) do
      if #c >= 3 and DICT[c] then return DICT[c], c end
    end
  end
end

-- Annote un morceau de texte (sans liens) : plus longue expression d'abord
local function AnnotateChunk(chunk, sub)
  local toks = {}
  for st, w, en in chunk:gmatch("()([%w']+)()") do
    local prev = toks[#toks]
    local sep = prev and chunk:sub(prev.e, st - 1) or ""
    toks[#toks + 1] = { s = st, e = en, l = w:lower(),
      cap = (prev ~= nil and w:find("^%u%l+$") ~= nil and not sep:find("[%.!?]")) }
  end
  if #toks == 0 then return chunk end
  local out, last, i = {}, 1, 1
  while i <= #toks do
    local hitN, hitT
    for n = math.min(MAXN, #toks - i + 1), 1, -1 do
      local key
      if n == 1 then
        key = toks[i].l
      else
        local parts, ok = { toks[i].l }, true
        for k = i + 1, i + n - 1 do
          if not chunk:sub(toks[k - 1].e, toks[k].s - 1):match("^%s+$") then
            ok = false
            break
          end
          parts[#parts + 1] = toks[k].l
        end
        if ok then key = table.concat(parts, " ") end
      end
      local t, kk
      if n == 1 and sub and (key == "a" or key == "an") then
        t, kk = "un", key
      elseif n == 1 then
        t, kk = Lookup1(key)
        if not t and sub and FRSUB[key] then t, kk = FRSUB[key], key end
      else
        t, kk = DICT[key], key
      end
      if t and not (n == 1 and (COMMON[kk] or COMMON[key]) and not (sub or ChatFRDB.common)) then
        hitN, hitT = n, t
        break
      end
    end
    -- nom propre (majuscule en milieu de phrase) : on ne traduit que les vrais noms FR
    if hitN == 1 and sub and toks[i].cap and not hitT:find("^%u") then hitN = nil end
    if hitN then
      if sub then stats.hit = stats.hit + hitN; stats.total = stats.total + hitN end
      local lt = toks[i + hitN - 1]
      if sub then
        -- remplacement : on garde la 1re variante ("le/la/les" -> "le")
        local first = hitT:match("^(.-)%s*/%s*") or hitT
        out[#out + 1] = chunk:sub(last, toks[i].s - 1)
        out[#out + 1] = first
      else
        out[#out + 1] = chunk:sub(last, lt.e - 1)
        out[#out + 1] = " (=" .. hitT .. ")"
      end
      last = lt.e
      i = i + hitN
    else
      if sub then
        local tk = toks[i]
        if not tk.cap and #tk.l >= 2 and not tk.l:find("^%d+$") then
          stats.total = stats.total + 1
          if #tk.l >= 3 and tk.l:find("^%a[%a']*$") and not COMMON[tk.l] and not FRENCH[tk.l] then
            unknown[#unknown + 1] = tk.l
          end
        end
      end
      i = i + 1
    end
  end
  out[#out + 1] = chunk:sub(last)
  return table.concat(out)
end

-- Annote le texte en laissant intacts les liens (objets, joueurs, etc.)
local function Annotate(text, sub)
  local out, pos = {}, 1
  while true do
    local s, e = text:find("|H.-|h.-|h", pos)
    local s2, e2 = text:find("|c%x%x%x%x%x%x%x%x", pos)
    local s3, e3 = text:find("|r", pos, true)
    if s2 and (not s or s2 < s) then s, e = s2, e2 end
    if s3 and (not s or s3 < s) then s, e = s3, e3 end
    local chunk = s and text:sub(pos, s - 1) or text:sub(pos)
    out[#out + 1] = AnnotateChunk(chunk, sub)
    if not s then break end
    out[#out + 1] = text:sub(s, e)
    pos = e + 1
  end
  return table.concat(out)
end
ns.Annotate = Annotate

-- Version "traduite" : remplace les mots/expressions connus par leur equivalent FR
local function Translate(text)
  stats.hit, stats.total = 0, 0
  unknown = {}
  local out = Annotate(text, true)
  return out, stats.hit, stats.total
end
ns.Translate = Translate

-- Mots perso : /cfr add mot=traduction
local function AddWord(k, v)
  k = k:lower()
  if k == "" or v == "" or k == v:lower() then return false end
  DICT[k] = v
  local words = select(2, k:gsub("%S+", ""))
  if words > MAXN then MAXN = words end
  return true
end
ns.AddWord = AddWord

local function Filter(self, event, msg, ...)
  if not ChatFRDB or not ChatFRDB.enabled or not ChatFRDB.chatnotes then return false end
  if type(msg) ~= "string" then return false end
  -- Retail 12.x : certaines valeurs peuvent etre "secretes" (non lisibles)
  if issecretvalue and issecretvalue(msg) then return false end
  local ok, new = pcall(Annotate, msg)
  if ok and new ~= msg then
    return false, new, ...
  end
  return false
end

for _, ev in ipairs(EVENTS) do
  ChatFrame_AddMessageEventFilter(ev, Filter)
end

local function Say(text)
  print("|cff33ccffChatFR|r: " .. text)
end

---------------------------------------------------------------------------
-- Fenetre ChatFR : copie annotee du tchat, deplacable et redimensionnable
---------------------------------------------------------------------------
local win, msgs

local function SavePos()
  local p, _, rp, x, y = win:GetPoint()
  ChatFRDB.pos = { p, rp, x, y, win:GetWidth(), win:GetHeight() }
end

local settingsPanel

local function ApplyFont()
  if not msgs or not ChatFontNormal or not ChatFontNormal.GetFont then return end
  local path, size, flags = ChatFontNormal:GetFont()
  local sz = (ChatFRDB and ChatFRDB.fontsize) or size or 14
  if path then msgs:SetFont(path, sz, flags) end
end

local function ResetPos()
  ChatFRDB.pos = nil
  win:ClearAllPoints()
  win:SetPoint("TOPLEFT", UIParent, "TOPLEFT", 20, -120)
  win:SetSize(420, 240)
end

local function MakeCheck(parent, y, label, get, set)
  local ok, cb = pcall(CreateFrame, "CheckButton", nil, parent, "UICheckButtonTemplate")
  if not ok or not cb then
    cb = CreateFrame("CheckButton", nil, parent)
    cb:SetNormalTexture("Interface\\Buttons\\UI-CheckBox-Up")
    cb:SetPushedTexture("Interface\\Buttons\\UI-CheckBox-Down")
    cb:SetHighlightTexture("Interface\\Buttons\\UI-CheckBox-Highlight")
    cb:SetCheckedTexture("Interface\\Buttons\\UI-CheckBox-Check")
  end
  cb:SetSize(24, 24)
  cb:SetPoint("TOPLEFT", 8, y)
  local fs = cb:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  fs:SetPoint("LEFT", cb, "RIGHT", 2, 0)
  fs:SetText(label)
  cb:SetChecked(get())
  cb:SetScript("OnClick", function(self) set(self:GetChecked() and true or false) end)
  return cb
end

local function MakeSlider(parent, y, label, fmt, minv, maxv, step, get, set)
  local fs = parent:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  fs:SetPoint("TOPLEFT", 12, y)
  local sl = CreateFrame("Slider", nil, parent)
  sl:SetOrientation("HORIZONTAL")
  sl:SetSize(190, 14)
  sl:SetPoint("TOPLEFT", 12, y - 16)
  local bg = sl:CreateTexture(nil, "BACKGROUND")
  bg:SetAllPoints()
  bg:SetColorTexture(1, 1, 1, 0.15)
  sl:SetThumbTexture("Interface\\Buttons\\UI-SliderBar-Button-Horizontal")
  sl:SetMinMaxValues(minv, maxv)
  sl:SetValueStep(step)
  if sl.SetObeyStepOnDrag then sl:SetObeyStepOnDrag(true) end
  sl:SetValue(get())
  fs:SetText(label .. " : " .. string.format(fmt, get()))
  sl:SetScript("OnValueChanged", function(self, v)
    fs:SetText(label .. " : " .. string.format(fmt, v))
    set(v)
  end)
  return sl
end

local function MakeButton(parent, y, label, onclick)
  local ok, b = pcall(CreateFrame, "Button", nil, parent, "UIPanelButtonTemplate")
  if not ok or not b then b = CreateFrame("Button", nil, parent) end
  b:SetSize(200, 22)
  b:SetPoint("TOPLEFT", 12, y)
  b:SetText(label)
  b:SetScript("OnClick", onclick)
  return b
end

local function BuildSettings(title, close)
  -- Roue de reglages (icone d'engrenage) dans la barre de titre
  local gear = CreateFrame("Button", nil, title)
  gear:SetSize(14, 14)
  gear:SetPoint("RIGHT", close, "LEFT", -4, 0)
  gear:SetNormalTexture("Interface\\Icons\\INV_Misc_Gear_01")
  gear:SetHighlightTexture("Interface\\Buttons\\ButtonHilight-Square")

  settingsPanel = CreateFrame("Frame", "ChatFRSettings", UIParent, "BackdropTemplate")
  settingsPanel:SetSize(230, 502)
  settingsPanel:SetPoint("CENTER", UIParent, "CENTER", 0, 0)
  settingsPanel:SetFrameStrata("DIALOG")
  settingsPanel:SetClampedToScreen(true)
  settingsPanel:SetMovable(true)
  settingsPanel:EnableMouse(true)
  settingsPanel:RegisterForDrag("LeftButton")
  settingsPanel:SetScript("OnDragStart", function(self) self:StartMoving() end)
  settingsPanel:SetScript("OnDragStop", function(self) self:StopMovingOrSizing() end)
  settingsPanel:SetBackdrop({
    bgFile = "Interface\\Buttons\\WHITE8x8",
    edgeFile = "Interface\\Buttons\\WHITE8x8",
    edgeSize = 1,
  })
  settingsPanel:SetBackdropColor(0, 0, 0, 0.95)
  settingsPanel:SetBackdropBorderColor(0.2, 0.6, 0.9, 0.9)
  settingsPanel:Hide()

  local t = settingsPanel:CreateFontString(nil, "OVERLAY", "GameFontNormal")
  t:SetPoint("TOPLEFT", 12, -10)
  t:SetText("Réglages ChatFR")
  local sclose = CreateFrame("Button", nil, settingsPanel, "UIPanelCloseButton")
  sclose:SetSize(22, 22)
  sclose:SetPoint("TOPRIGHT", 2, 2)
  sclose:SetScript("OnClick", function() settingsPanel:Hide() end)

  MakeCheck(settingsPanel, -30, "Addon actif",
    function() return ChatFRDB.enabled end,
    function(v) ChatFRDB.enabled = v end)
  MakeCheck(settingsPanel, -56, "Ligne traduite (->)",
    function() return ChatFRDB.showfr end,
    function(v) ChatFRDB.showfr = v end)
  MakeCheck(settingsPanel, -82, "Annoter les petits mots",
    function() return ChatFRDB.common end,
    function(v) ChatFRDB.common = v end)
  MakeCheck(settingsPanel, -108, "Annotations dans le tchat",
    function() return ChatFRDB.chatnotes end,
    function(v) ChatFRDB.chatnotes = v end)
  MakeCheck(settingsPanel, -134, "Enregistrer le tchat (log)",
    function() return LoggingChat and LoggingChat() end,
    function(v)
      ChatFRDB.autolog = v
      if LoggingChat then LoggingChat(v) end
    end)

  MakeCheck(settingsPanel, -160, "Alertes (pseudo / mots)",
    function() return ChatFRDB.alert end,
    function(v) ChatFRDB.alert = v end)

  MakeCheck(settingsPanel, -186, "Masquer si une fenêtre est ouverte",
    function() return ChatFRDB.autohide end,
    function(v) ChatFRDB.autohide = v end)

  -- envoyes en plus au traducteur externe (affiches sans traduction)
  MakeCheck(settingsPanel, -212, "Traducteur : PNJ",
    function() return ChatFRDB.brNpc end,
    function(v) ChatFRDB.brNpc = v end)
  MakeCheck(settingsPanel, -238, "Traducteur : messages système",
    function() return ChatFRDB.brSystem end,
    function(v) ChatFRDB.brSystem = v end)
  MakeCheck(settingsPanel, -264, "Traducteur : butin et argent",
    function() return ChatFRDB.brLoot end,
    function(v) ChatFRDB.brLoot = v end)

  MakeSlider(settingsPanel, -298, "Opacité du fond", "%.2f", 0.2, 1, 0.05,
    function() return ChatFRDB.alpha or 0.92 end,
    function(v)
      ChatFRDB.alpha = v
      win:SetBackdropColor(0, 0, 0, v)
    end)
  local defSize = 14
  if ChatFontNormal and ChatFontNormal.GetFont then
    local _, sz = ChatFontNormal:GetFont()
    if sz then defSize = sz end
  end
  MakeSlider(settingsPanel, -344, "Taille du texte", "%d", 9, 20, 1,
    function() return ChatFRDB.fontsize or defSize end,
    function(v)
      ChatFRDB.fontsize = math.floor(v + 0.5)
      ApplyFont()
    end)

  MakeSlider(settingsPanel, -390, "Confiance minimale", "%d%%", 0, 100, 5,
    function() return math.floor((ChatFRDB.minconf or 0.75) * 100 + 0.5) end,
    function(v) ChatFRDB.minconf = math.floor(v + 0.5) / 100 end)

  MakeButton(settingsPanel, -438, "Vider la fenêtre", function() msgs:Clear() end)
  MakeButton(settingsPanel, -466, "Position par défaut", function() ResetPos(); SavePos() end)

  gear:SetScript("OnClick", function()
    if settingsPanel:IsShown() then settingsPanel:Hide() else settingsPanel:Show() end
  end)
end

local function CreateWindow()
  win = CreateFrame("Frame", "ChatFRWindow", UIParent, "BackdropTemplate")
  win:SetSize(420, 240)
  win:SetPoint("TOPLEFT", UIParent, "TOPLEFT", 20, -120)
  win:SetFrameStrata("HIGH")
  win:SetClampedToScreen(true)
  win:SetMovable(true)
  win:SetResizable(true)
  if win.SetResizeBounds then win:SetResizeBounds(220, 100, 900, 700) end
  win:EnableMouse(true)
  win:SetBackdrop({
    bgFile = "Interface\\Buttons\\WHITE8x8",
    edgeFile = "Interface\\Buttons\\WHITE8x8",
    edgeSize = 1,
  })
  win:SetBackdropColor(0, 0, 0, ChatFRDB.alpha or 0.92)
  win:SetBackdropBorderColor(0.2, 0.6, 0.9, 0.9)

  -- Barre de titre (glisser pour deplacer)
  local title = CreateFrame("Frame", nil, win)
  title:SetPoint("TOPLEFT")
  title:SetPoint("TOPRIGHT")
  title:SetHeight(18)
  title:EnableMouse(true)
  title:RegisterForDrag("LeftButton")
  title:SetScript("OnDragStart", function() win:StartMoving() end)
  title:SetScript("OnDragStop", function() win:StopMovingOrSizing(); SavePos() end)
  local tt = title:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
  tt:SetPoint("LEFT", 6, 0)
  tt:SetText("ChatFR")

  local close = CreateFrame("Button", nil, title, "UIPanelCloseButton")
  close:SetSize(18, 18)
  close:SetPoint("RIGHT", 2, 0)
  close:SetScript("OnClick", function() win:Hide(); ChatFRDB.hidden = true end)
  local okS, errS = pcall(BuildSettings, title, close)
  if not okS then Say("reglages indisponibles : " .. tostring(errS)) end

  -- Zone de messages
  msgs = CreateFrame("ScrollingMessageFrame", nil, win)
  msgs:SetPoint("TOPLEFT", 6, -22)
  msgs:SetPoint("BOTTOMRIGHT", -6, 6)
  msgs:SetFontObject(ChatFontNormal)
  msgs:SetJustifyH("LEFT")
  msgs:SetFading(false)
  msgs:SetMaxLines(300)
  ApplyFont()
  msgs:EnableMouseWheel(true)
  msgs:SetScript("OnMouseWheel", function(self, delta)
    if delta > 0 then self:ScrollUp() else self:ScrollDown() end
  end)

  -- Poignee de redimensionnement
  local grip = CreateFrame("Button", nil, win)
  grip:SetSize(14, 14)
  grip:SetPoint("BOTTOMRIGHT", -1, 1)
  grip:SetNormalTexture("Interface\\ChatFrame\\UI-ChatIM-SizeGrabber-Up")
  grip:SetPushedTexture("Interface\\ChatFrame\\UI-ChatIM-SizeGrabber-Down")
  grip:SetScript("OnMouseDown", function() win:StartSizing("BOTTOMRIGHT") end)
  grip:SetScript("OnMouseUp", function() win:StopMovingOrSizing(); SavePos() end)

  -- Position sauvegardee
  local p = ChatFRDB.pos
  if p then
    win:ClearAllPoints()
    win:SetPoint(p[1], UIParent, p[2], p[3], p[4])
    win:SetSize(p[5], p[6])
  end
  if ChatFRDB.hidden then win:Hide() end
end

---------------------------------------------------------------------------
-- Bouton de la minicarte (clic gauche : fenetre, clic droit : reglages,
-- glisser : deplacer autour de la minicarte)
---------------------------------------------------------------------------
local mmBtn

local function PlaceMinimapButton()
  if not mmBtn then return end
  local a = math.rad(ChatFRDB.mmangle or 215)
  local r = (Minimap:GetWidth() / 2) + 5
  mmBtn:ClearAllPoints()
  mmBtn:SetPoint("CENTER", Minimap, "CENTER", math.cos(a) * r, math.sin(a) * r)
end

local function ToggleWindow()
  if win:IsShown() then
    win:Hide(); ChatFRDB.hidden = true
  else
    win:Show(); ChatFRDB.hidden = false
  end
end

local function CreateMinimapButton()
  if not Minimap then return end
  mmBtn = CreateFrame("Button", "ChatFRMinimapButton", Minimap)
  mmBtn:SetSize(31, 31)
  mmBtn:SetFrameStrata("MEDIUM")
  mmBtn:SetFrameLevel(8)
  mmBtn:SetHighlightTexture("Interface\\Minimap\\UI-Minimap-ZoomButton-Highlight")
  local icon = mmBtn:CreateTexture(nil, "ARTWORK")
  icon:SetSize(20, 20)
  icon:SetPoint("CENTER", 0, 1)
  icon:SetTexture("Interface\\Icons\\INV_Misc_Note_01")
  local border = mmBtn:CreateTexture(nil, "OVERLAY")
  border:SetSize(53, 53)
  border:SetPoint("TOPLEFT")
  border:SetTexture("Interface\\Minimap\\MiniMap-TrackingBorder")
  mmBtn:RegisterForClicks("LeftButtonUp", "RightButtonUp")
  mmBtn:RegisterForDrag("LeftButton")
  mmBtn:SetScript("OnClick", function(_, button)
    if button == "RightButton" then
      if settingsPanel then
        if settingsPanel:IsShown() then settingsPanel:Hide() else settingsPanel:Show() end
      end
    else
      ToggleWindow()
    end
  end)
  mmBtn:SetScript("OnDragStart", function(self)
    self:SetScript("OnUpdate", function()
      local mx, my = Minimap:GetCenter()
      local cx, cy = GetCursorPosition()
      local sc = Minimap:GetEffectiveScale()
      ChatFRDB.mmangle = math.deg(math.atan2(cy / sc - my, cx / sc - mx))
      PlaceMinimapButton()
    end)
  end)
  mmBtn:SetScript("OnDragStop", function(self) self:SetScript("OnUpdate", nil) end)
  mmBtn:SetScript("OnEnter", function(self)
    GameTooltip:SetOwner(self, "ANCHOR_LEFT")
    GameTooltip:SetText("ChatFR")
    GameTooltip:AddLine("Clic gauche : afficher / masquer la fenêtre", 1, 1, 1)
    GameTooltip:AddLine("Clic droit : réglages", 1, 1, 1)
    GameTooltip:AddLine("Glisser : déplacer le bouton", 1, 1, 1)
    GameTooltip:Show()
  end)
  mmBtn:SetScript("OnLeave", function() GameTooltip:Hide() end)
  PlaceMinimapButton()
  if ChatFRDB.mmhide then mmBtn:Hide() end
end

---------------------------------------------------------------------------
-- Masquage automatique quand une fenetre du jeu est ouverte
---------------------------------------------------------------------------
local PANELS = { "SpellBookFrame", "PlayerSpellsFrame", "CharacterFrame", "WorldMapFrame",
  "GameMenuFrame", "AuctionHouseFrame", "AuctionFrame", "MerchantFrame", "MailFrame",
  "SendMailFrame", "BankFrame", "AccountBankPanel", "QuestFrame", "GossipFrame", "TradeFrame",
  "ProfessionsFrame", "TradeSkillFrame", "CraftFrame", "CollectionsJournal", "EncounterJournal",
  "PVEFrame", "PVPUIFrame", "FriendsFrame", "ClassTalentFrame", "TalentFrame", "HelpFrame",
  "AchievementFrame", "CommunitiesFrame", "GuildFrame", "ReputationFrame", "InspectFrame",
  "ItemUpgradeFrame", "BarberShopFrame", "ChannelFrame", "KeyBindingFrame", "SettingsPanel",
  "InterfaceOptionsFrame", "VideoOptionsFrame", "LootFrame", "TaxiFrame", "TabardFrame",
  "ClassTrainerFrame", "AddonList", "CalendarFrame", "TimeManagerFrame", "ItemSocketingFrame",
  "ScrappingMachineFrame", "ArtifactFrame", "GarrisonLandingPage", "OrderHallTalentFrame" }

local autoHidden = false
local function AnyPanelOpen()
  for i = 1, #PANELS do
    local fr = _G[PANELS[i]]
    if fr and fr.IsShown and fr:IsShown() then return true end
  end
  return false
end

local function StartAutoHide()
  local acc = 0
  local ticker = CreateFrame("Frame")
  ticker:SetScript("OnUpdate", function(_, el)
    acc = acc + (el or 0)
    if acc < 0.3 then return end
    acc = 0
    if not win then return end
    if ChatFRDB.autohide and AnyPanelOpen() then
      if win:IsShown() and not ChatFRDB.hidden then
        win:Hide(); autoHidden = true
      end
    elseif autoHidden then
      autoHidden = false
      if not ChatFRDB.hidden then win:Show() end
    end
  end)
end

-- WoW garde le log en memoire et ne l'ecrit que par blocs : on force l'ecriture
-- (fermeture/reouverture du fichier) peu apres chaque message recu.
local logDirty = false
local flushing = false

-- Chaque LoggingChat(false/true) affiche un message systeme ("Le tchat est maintenant
-- enregistre..." / "n'est plus enregistre...") : on le masque pendant le flush automatique.
local function LogMsgFilter(_, _, msg)
  if flushing and type(msg) == "string" and not (issecretvalue and issecretvalue(msg)) then
    if msg == CHATLOGENABLED or msg == CHATLOGDISABLED then return true end
    if msg:find("WoWChatLog", 1, true) then return true end
  end
  return false
end
ChatFrame_AddMessageEventFilter("CHAT_MSG_SYSTEM", LogMsgFilter)

local function StartLogFlush()
  local acc = 0
  local fl = CreateFrame("Frame")
  fl:SetScript("OnUpdate", function(_, el)
    acc = acc + (el or 0)
    if acc < 1 then return end
    acc = 0
    -- desactive par defaut : ce client n'ecrit pas le log avant la fermeture du jeu
    -- (le pont image de Bridge.lua le remplace). ChatFRDB.logflush = true pour reessayer.
    if logDirty and not flushing and ChatFRDB.logflush then
      logDirty = false
      if ChatFRDB.autolog and LoggingChat and LoggingChat() then
        -- fermeture, puis reouverture quelques images plus tard : dans la meme image,
        -- WoW ne ferme pas reellement le fichier et rien n'est ecrit sur le disque.
        flushing = true
        LoggingChat(false)
        local function reopen()
          if ChatFRDB.autolog then LoggingChat(true) end
          flushing = false
        end
        if C_Timer and C_Timer.After then
          C_Timer.After(0.25, reopen)
        else
          reopen()
        end
      end
    end
  end)
end

local function LooksFrench(m)
  m = m:gsub("|H.-|h.-|h", ""):gsub("|c%x%x%x%x%x%x%x%x", ""):gsub("|r", "")
  local l = " " .. m:lower() .. " "
  if l:find("[\195][\160-\191]") then return true end  -- lettres accentuees (UTF-8)
  for _, w in ipairs({ " le ", " la ", " les ", " je ", " tu ", " est ", " pas ", " pour ",
                       " une ", " des ", " vous ", " nous ", " quelqu'un ", " salut ", " merci ",
                       " et ", " de ", " du ", " un ", " ce ", " mon ", " ma ", " mes ", " ton ",
                       " sur ", " avec ", " dans ", " qui ", " que ", " oui ", " non ", " ici ",
                       " aime ", " bonjour ", " bonsoir ", " moi ", " toi ", " ils ", " elle ",
                       " ont ", " sont ", " suis ", " fait ", " faire ", " aller ", " veux ",
                       " peux ", " peut ", " cherche ", " groupe ", " donjon ",
                       " l'", " d'", " j'", " qu'", " c'", " n'", " s'", " m'", " t'" }) do
    if l:find(w, 1, true) then return true end
  end
  return false
end

local function ShortName(author)
  if type(author) ~= "string" then return "?" end
  return (author:gsub("%-.*$", ""))
end

local function OnChat(event, msg, author, chanFull, chanBase)
  if type(msg) ~= "string" then return end
  if issecretvalue and (issecretvalue(msg) or issecretvalue(author)) then return end
  -- pont image : envoie le message au traducteur (Bridge.lua)
  if ns.BridgePush then pcall(ns.BridgePush, event, msg, author, chanBase or chanFull) end
  if not win or not ChatFRDB.enabled then return end
  logDirty = true
  local ok, fr, hit, total = pcall(Translate, msg)
  if not ok then fr, hit, total = msg, 0, 0 end
  local ratio = (total and total > 0) and (hit / total) or 0
  local info = ChatTypeInfo and ChatTypeInfo[event:sub(10)]
  local r, g, b = 1, 1, 1
  if info then r, g, b = info.r, info.g, info.b end
  local french = LooksFrench(msg)
  -- mots non traduits : on les compte (hors messages francais)
  if not french and #unknown > 0 then
    local miss = ChatFRDB.missing
    local n = 0
    for _ in pairs(miss) do n = n + 1 end
    for _, w in ipairs(unknown) do
      if miss[w] then miss[w] = miss[w] + 1
      elseif n < 2000 then miss[w] = 1; n = n + 1 end
    end
  end
  -- alerte : mon pseudo ou un mot surveille
  local alert = false
  if ChatFRDB.alert and ShortName(author) ~= UnitName("player") then
    local low = msg:lower()
    local me = UnitName("player")
    if me and low:find(me:lower(), 1, true) then alert = true end
    if not alert then
      for _, kw in ipairs(ChatFRDB.keywords) do
        if low:find(kw, 1, true) then alert = true; break end
      end
    end
  end
  if alert then
    msgs:AddMessage("|cffffd100>> " .. ShortName(author) .. ": " .. msg .. "|r")
    pcall(function()
      if SOUNDKIT and SOUNDKIT.TELL_MESSAGE then PlaySound(SOUNDKIT.TELL_MESSAGE) else PlaySound(3081) end
    end)
  else
    msgs:AddMessage(ShortName(author) .. ": " .. msg, r, g, b)
  end
  if fr ~= msg and ChatFRDB.showfr and ratio >= (ChatFRDB.minconf or 0.75) and not french then
    msgs:AddMessage("   |cff7fd4ff-> " .. fr .. "|r")
  end
end

local f = CreateFrame("Frame")
f:RegisterEvent("ADDON_LOADED")
f:RegisterEvent("PLAYER_LOGIN")
for _, ev in ipairs(EVENTS) do
  f:RegisterEvent(ev)
end
-- Fenetre d'annonce "nouvelle version du traducteur" (voir PLAYER_LOGIN).
local TRAD_NOTICE = "1.7"
local TRAD_URL = "github.com/puenteur/Wow-traducteur"
local noticeFrame

local function ShowTradNotice()
  if not noticeFrame then
    local p = CreateFrame("Frame", "ChatFRNotice", UIParent, "BackdropTemplate")
    noticeFrame = p
    p:SetSize(440, 190)
    p:SetPoint("CENTER", 0, 120)
    p:SetFrameStrata("DIALOG")
    p:SetClampedToScreen(true)
    p:SetMovable(true)
    p:EnableMouse(true)
    p:RegisterForDrag("LeftButton")
    p:SetScript("OnDragStart", function(self) self:StartMoving() end)
    p:SetScript("OnDragStop", function(self) self:StopMovingOrSizing() end)
    p:SetBackdrop({ bgFile = "Interface\\Buttons\\WHITE8x8", edgeFile = "Interface\\Buttons\\WHITE8x8", edgeSize = 2 })
    p:SetBackdropColor(0, 0, 0, 0.95)
    p:SetBackdropBorderColor(1, 0.82, 0, 1)

    local title = p:CreateFontString(nil, "OVERLAY", "GameFontNormalLarge")
    title:SetPoint("TOP", 0, -14)
    title:SetText("ChatFR : mise à jour du traducteur")

    local body = p:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    body:SetPoint("TOP", title, "BOTTOM", 0, -12)
    body:SetWidth(400)
    body:SetJustifyH("CENTER")
    body:SetText("La version " .. TRAD_NOTICE .. " de WoW Traducteur est disponible.\n" ..
                 "Télécharge le zip WoW-Traducteur dans les Releases de :")

    -- Adresse dans une zone de texte : clic dedans puis Ctrl+C pour la copier.
    local eb = CreateFrame("EditBox", nil, p, "InputBoxTemplate")
    eb:SetSize(300, 24)
    eb:SetPoint("TOP", body, "BOTTOM", 0, -10)
    eb:SetAutoFocus(false)
    eb:SetText(TRAD_URL)
    eb:SetCursorPosition(0)
    eb:SetScript("OnTextChanged", function(self, user) if user then self:SetText(TRAD_URL) end end)
    eb:SetScript("OnEditFocusGained", function(self) self:HighlightText() end)
    eb:SetScript("OnEscapePressed", function(self) self:ClearFocus() end)
    eb:SetScript("OnEnterPressed", function(self) self:ClearFocus() end)

    local hint = p:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
    hint:SetPoint("TOP", eb, "BOTTOM", 0, -4)
    hint:SetText("(clique sur l'adresse puis Ctrl+C pour la copier)")

    local ok = CreateFrame("Button", nil, p, "UIPanelButtonTemplate")
    ok:SetSize(120, 24)
    ok:SetPoint("BOTTOM", 0, 14)
    ok:SetText("OK")
    ok:SetScript("OnClick", function()
      ChatFRDB.tradNotice = TRAD_NOTICE          -- ne plus afficher pour cette version
      p:Hide()
    end)
  end
  noticeFrame:Show()
end

-- Chuchotement Battle.net : l'auteur arrive sous forme de code protege ("|Ks18|k") que seul
-- le tchat du jeu sait afficher. On le remplace par le nom du BattleTag (ou du personnage).
local function BNetName(bnID)
  if not bnID or not C_BattleNet or not C_BattleNet.GetAccountInfoByID then return nil end
  local info = C_BattleNet.GetAccountInfoByID(bnID)
  if not info then return nil end
  if type(info.battleTag) == "string" and info.battleTag ~= "" then
    return (info.battleTag:gsub("#.*$", ""))
  end
  local g = info.gameAccountInfo
  if g and type(g.characterName) == "string" and g.characterName ~= "" then return g.characterName end
  return nil
end

-- Messages en option pour le traducteur (PNJ, systeme, butin) : deja en francais, ils vont
-- seulement au pont image, pas dans la fenetre ChatFR. Desactives par defaut (Reglages ChatFR).
local EXTRA_OPT = { npc = "brNpc", system = "brSystem", loot = "brLoot", spent = "brLoot", faction = "brSystem" }
for ev, kind in pairs(ns.BRIDGE_KIND or {}) do
  if EXTRA_OPT[kind] then pcall(f.RegisterEvent, f, ev) end   -- pcall : evenement absent de ce client
end

local function PushExtra(event, kind, text, author)
  if not ChatFRDB or not ChatFRDB[EXTRA_OPT[kind]] or not ns.BridgePush then return end
  -- en donjon / combat, le jeu rend certains textes "secrets" (illisibles pour les addons)
  if issecretvalue and (issecretvalue(text) or issecretvalue(author)) then return end
  if type(text) ~= "string" or text == "" then return end
  author = type(author) == "string" and author or ""
  if event == "CHAT_MSG_MONSTER_EMOTE" or event == "CHAT_MSG_RAID_BOSS_EMOTE" then
    text = text:gsub("%%s", (author:gsub("%%", "%%%%")))      -- "%s attaque !" -> "Hogger attaque !"
    author = ""
  elseif kind ~= "npc" then
    author = ""                                                -- le texte est deja une phrase complete
  end
  pcall(ns.BridgePush, event, text, author, nil)
end

-- Vente a un marchand : le jeu ecrit "Vous avez obtenu : 18 pc" directement dans le tchat, sans
-- evenement CHAT_MSG pour les addons. On le reconstruit a partir de l'argent gagne chez le marchand.
local lastMoney, atMerchant = nil, false
for _, ev in ipairs({ "PLAYER_MONEY", "MERCHANT_SHOW", "MERCHANT_CLOSED", "PLAYER_ENTERING_WORLD" }) do
  pcall(f.RegisterEvent, f, ev)
end

local function MoneyText(c)
  local g, s, cu = math.floor(c / 10000), math.floor(c / 100) % 100, c % 100
  local t = {}
  if g > 0 then t[#t + 1] = g .. " po" end
  if s > 0 then t[#t + 1] = s .. " pa" end
  if cu > 0 or #t == 0 then t[#t + 1] = cu .. " pc" end
  return table.concat(t, " ")
end

local function OnMoney(event)
  if event == "MERCHANT_SHOW" then atMerchant = true
  elseif event == "MERCHANT_CLOSED" then atMerchant = false end
  local m = GetMoney and GetMoney()
  if not m then return end
  -- MerchantFrame : marchand deja ouvert au moment d'un /reload (MERCHANT_SHOW deja passe)
  local merchant = atMerchant or (MerchantFrame and MerchantFrame:IsShown())
  if event == "PLAYER_MONEY" and merchant and lastMoney and m ~= lastMoney then
    if m > lastMoney then
      PushExtra("CHAT_MSG_MONEY", "loot", "Vous avez obtenu : " .. MoneyText(m - lastMoney), "")
    else                                     -- achat, rachat, reparation
      PushExtra("CHATFR_SPENT", "spent", "Vous avez dépensé : " .. MoneyText(lastMoney - m), "")
    end
  end
  lastMoney = m
end

for _, ev in ipairs({ "CHAT_MSG_WHISPER_INFORM", "CHAT_MSG_BN_WHISPER_INFORM" }) do
  pcall(f.RegisterEvent, f, ev)
end

f:SetScript("OnEvent", function(_, event, name, author, a3, a4, a5, a6, a7, a8, a9, ...)
  local xkind = ns.BRIDGE_KIND and ns.BRIDGE_KIND[event]
  if event == "CHAT_MSG_WHISPER_INFORM" or event == "CHAT_MSG_BN_WHISPER_INFORM" then
    -- chuchotement envoye : seulement vers le traducteur, avec "A <destinataire>" comme auteur
    if event == "CHAT_MSG_BN_WHISPER_INFORM" then
      local okN, bn = pcall(BNetName, (select(4, ...)))
      if okN and bn then author = bn end
    end
    if issecretvalue and (issecretvalue(name) or issecretvalue(author)) then return end
    if ns.BridgePush and type(name) == "string" and name ~= "" then
      local to = type(author) == "string" and author:gsub("%-.*$", "") or ""
      pcall(ns.BridgePush, event, name, "\195\128 " .. to, nil)     -- "A " avec accent
    end
    return
  end
  if event == "PLAYER_MONEY" or event == "MERCHANT_SHOW" or event == "MERCHANT_CLOSED"
      or event == "PLAYER_ENTERING_WORLD" then
    pcall(OnMoney, event)
    if event ~= "PLAYER_ENTERING_WORLD" then return end
  end
  if xkind and EXTRA_OPT[xkind] then
    pcall(PushExtra, event, xkind, name, author)
  elseif event:sub(1, 9) == "CHAT_MSG_" then
    if event == "CHAT_MSG_BN_WHISPER" then
      local okN, bn = pcall(BNetName, (select(4, ...)))   -- 13e argument : bnSenderID
      if okN and bn then author = bn end
    end
    local ok, err = pcall(OnChat, event, name, author, a4, a9)
    if not ok and not ns.errShown then
      ns.errShown = true
      Say("erreur (message ignore) : " .. tostring(err))
    end
  elseif event == "ADDON_LOADED" and name == ADDON_NAME then
    ChatFRDB = ChatFRDB or {}
    if ChatFRDB.enabled == nil then ChatFRDB.enabled = true end
    if ChatFRDB.autolog == nil then ChatFRDB.autolog = true end
    if ChatFRDB.common == nil then ChatFRDB.common = true end
    if ChatFRDB.chatnotes == nil then ChatFRDB.chatnotes = false end
    if ChatFRDB.showfr == nil then ChatFRDB.showfr = true end
    if ChatFRDB.alert == nil then ChatFRDB.alert = true end
    if ChatFRDB.autohide == nil then ChatFRDB.autohide = true end
    if ChatFRDB.bridge == nil then ChatFRDB.bridge = true end
    ChatFRDB.custom = ChatFRDB.custom or {}
    ChatFRDB.keywords = ChatFRDB.keywords or {}
    ChatFRDB.missing = ChatFRDB.missing or {}
    for k, v in pairs(ChatFRDB.custom) do AddWord(k, v) end
  elseif event == "PLAYER_LOGIN" then
    local okW, errW = pcall(CreateWindow)
    if not okW then Say("erreur fenetre : " .. tostring(errW)) end
    pcall(StartAutoHide)
    pcall(StartLogFlush)
    local okM, errM = pcall(CreateMinimapButton)
    if not okM then Say("bouton minicarte indisponible : " .. tostring(errM)) end
    -- Annonce d'une nouvelle version du traducteur externe : fenetre au centre de l'ecran,
    -- remontree a chaque connexion tant que le joueur n'a pas clique "OK".
    -- Changer TRAD_NOTICE (plus haut) a chaque nouvelle version du traducteur a annoncer.
    if ChatFRDB.tradNotice ~= TRAD_NOTICE then
      local function notice()
        Say("|cffffd100NOUVELLE VERSION DU TRADUCTEUR (" .. TRAD_NOTICE .. ")|r : a telecharger sur " .. TRAD_URL .. " (Releases).")
        local okN, errN = pcall(ShowTradNotice)
        if not okN then Say("annonce indisponible : " .. tostring(errN)) end
      end
      if C_Timer and C_Timer.After then C_Timer.After(5, notice) else notice() end
    end
    if ChatFRDB.autolog and LoggingChat and not LoggingChat() then
      LoggingChat(true)
      Say("log du tchat active (pour le traducteur externe).")
    end
  end
end)

SLASH_CHATFR1 = "/cfr"
SlashCmdList["CHATFR"] = function(msg)
  local raw = msg or ""
  local arg = raw:lower():match("^%s*%S+%s+(%S+)")
  local rest = raw:match("^%s*%S+%s*(.-)%s*$") or ""
  msg = raw:lower():match("^%s*(%S*)")
  if msg == "add" then
    local k, v = rest:match("^(.-)%s*=%s*(.+)$")
    if k and AddWord(k, v) then
      ChatFRDB.custom[k:lower()] = v
      Say("ajouté : " .. k:lower() .. " = " .. v)
    else
      Say("usage : /cfr add whers=où est")
    end
  elseif msg == "del" then
    local k = rest:lower()
    if ChatFRDB.custom[k] then
      ChatFRDB.custom[k] = nil
      DICT[k] = nil
      Say("supprimé : " .. k .. " (tapez /reload pour restaurer le mot d'origine)")
    else
      Say("mot perso introuvable : " .. k)
    end
  elseif msg == "list" then
    local n = 0
    for k, v in pairs(ChatFRDB.custom) do Say(k .. " = " .. v); n = n + 1 end
    if n == 0 then Say("aucun mot perso. Ex : /cfr add whers=où est") end
  elseif msg == "alert" or msg == "alerte" then
    local sub = arg
    local kw = rest:match("^%S+%s+(.+)$")
    if sub == "add" and kw then
      kw = kw:lower()
      table.insert(ChatFRDB.keywords, kw)
      Say("mot surveillé : " .. kw)
    elseif sub == "del" and kw then
      kw = kw:lower()
      for i = #ChatFRDB.keywords, 1, -1 do
        if ChatFRDB.keywords[i] == kw then table.remove(ChatFRDB.keywords, i) end
      end
      Say("mot retiré : " .. kw)
    elseif sub == "list" then
      Say("pseudo + : " .. (#ChatFRDB.keywords > 0 and table.concat(ChatFRDB.keywords, ", ") or "(aucun mot)"))
    else
      ChatFRDB.alert = not ChatFRDB.alert
      Say("alertes " .. (ChatFRDB.alert and "activées" or "désactivées") ..
        ". /cfr alert add LFM | del LFM | list")
    end
  elseif msg == "manquants" or msg == "missing" then
    if arg == "clear" then
      ChatFRDB.missing = {}
      Say("liste des mots manquants vidée.")
    else
      local list = {}
      for w, c in pairs(ChatFRDB.missing) do list[#list + 1] = { w, c } end
      table.sort(list, function(a, b) if a[2] ~= b[2] then return a[2] > b[2] end return a[1] < b[1] end)
      if #list == 0 then
        Say("aucun mot manquant pour l'instant.")
      else
        Say("mots les plus fréquents sans traduction (ajoutez avec /cfr add mot=traduction) :")
        local line = {}
        for i = 1, math.min(30, #list) do line[#line + 1] = list[i][1] .. " (" .. list[i][2] .. ")" end
        Say(table.concat(line, ", "))
      end
    end
  elseif msg == "on" then
    ChatFRDB.enabled = true
    Say("annotations activees.")
  elseif msg == "off" then
    ChatFRDB.enabled = false
    Say("annotations desactivees.")
  elseif msg == "log" then
    local state = not LoggingChat()
    LoggingChat(state)
    ChatFRDB.autolog = state
    Say("log du tchat " .. (state and "active." or "desactive."))
  elseif msg == "mots" then
    ChatFRDB.common = not ChatFRDB.common
    Say("petits mots courants " .. (ChatFRDB.common and "annotes." or "ignores."))
  elseif msg == "chat" then
    ChatFRDB.chatnotes = not ChatFRDB.chatnotes
    Say("annotations dans le tchat principal " .. (ChatFRDB.chatnotes and "activees." or "desactivees."))
  elseif msg == "alpha" then
    local a = tonumber(arg)
    if a and a >= 0.2 and a <= 1 then
      ChatFRDB.alpha = a
      win:SetBackdropColor(0, 0, 0, a)
      Say("opacite du fond : " .. a)
    else
      Say("/cfr alpha 0.2 a 1 (1 = fond opaque)")
    end
  elseif msg == "menu" or msg == "reglages" then
    if settingsPanel:IsShown() then settingsPanel:Hide() else settingsPanel:Show() end
  elseif msg == "auto" then
    ChatFRDB.autohide = not ChatFRDB.autohide
    Say("masquage automatique quand une fenêtre est ouverte : " .. (ChatFRDB.autohide and "activé." or "désactivé."))
  elseif msg == "pont" or msg == "bridge" then
    ChatFRDB.bridge = not ChatFRDB.bridge
    if ns.BridgeSetShown then ns.BridgeSetShown(ChatFRDB.bridge) end
    Say("pont image (bande de couleur en haut a gauche, lue par le traducteur) : " ..
      (ChatFRDB.bridge and "active." or "desactive."))
  elseif msg == "minimap" then
    ChatFRDB.mmhide = not ChatFRDB.mmhide
    if mmBtn then if ChatFRDB.mmhide then mmBtn:Hide() else mmBtn:Show() end end
    Say("bouton de la minicarte " .. (ChatFRDB.mmhide and "masqué." or "affiché."))
  elseif msg == "show" then
    ChatFRDB.hidden = false
    win:Show()
  elseif msg == "hide" then
    ChatFRDB.hidden = true
    win:Hide()
  elseif msg == "reset" then
    ChatFRDB.pos = nil
    win:ClearAllPoints()
    win:SetPoint("TOPLEFT", UIParent, "TOPLEFT", 20, -120)
    win:SetSize(420, 240)
    ChatFRDB.hidden = false
    win:Show()
  elseif msg == "clear" then
    msgs:Clear()
  else
    Say("/cfr on | off | menu | chat | mots | alpha | log | show | hide | reset | clear | add | del | list | alert | manquants | minimap | auto | pont   (annotations: " ..
      (ChatFRDB.enabled and "ON" or "OFF") .. ", log: " ..
      (LoggingChat() and "ON" or "OFF") .. ")")
  end
end
