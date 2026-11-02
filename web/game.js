/* ═══════════════════════════════════════════════════════════════════════════════
   AEGYPTUS: THE LABYRINTH — Library of Babel Edition v5.2
   ─────────────────────────────────────────────────────────────────────────────
   Architecture: Complex → Hall → Room → Chamber
   77,683 corpus texts · 8 Levels · 41 Halls · 79 Chambers
   Oracle at the geometric center of all creation
   Dense inscriptions from REAL corpus passages
   Hieroglyph rain · Torch flicker · Portal rings · Sigil animations
   Oracle chat with HTML input capture (FIXED and reliable)
   ═══════════════════════════════════════════════════════════════════════════════ */

const API = window.location.origin;

// ══════════════════════════════════════════════════════════════════════════════
// CONFIGURATION
// ══════════════════════════════════════════════════════════════════════════════
const CFG = {
  TILE: 28,
  FONT: 'Fira Code, monospace',
  // 'Noto Egyptian Canvas' is loaded by FontFace API (no unicode-range, works
  // in Firefox/Zen). Falls back to CSS @font-face 'Noto Egyptian', then serif.
  HIERO_FONT: "'Noto Egyptian Canvas', 'Noto Egyptian', serif",
  FOV_RADIUS: 24,
  MOVE_SPEED: 65,
  COLORS: {
    bg: '#0a0a08', dark: '#050504', void: '#020201',
    floor: '#1e1a15', floorAlt: '#191510', floorDot: '#2e2618',
    wall: '#4a3e34', wallLit: '#6a5848', wallGold: '#5a4a38',
    gold: '#e4a830', goldDim: '#b07828', goldBright: '#ffcc50', goldFaint: '#7a5a28',
    text: '#f0e4cc', textDim: '#b09888', textFaint: '#786858', textGhost: '#483828',
    green: '#98d4ac', greenDim: '#6aaa7a', greenBright: '#b8ecc8',
    player: '#ffcc50', oracle: '#98d4ac', oracleBright: '#c0f0d8',
    corridor: '#332c24', inscr: '#7a6040', inscrHi: '#e4a830', inscrGlow: '#ffd060',
    danger: '#c85040', dangerDim: '#904030',
    panelBg: 'rgba(8,7,6,0.97)', panelBorder: '#3a2e24', panelBorderLit: '#5a4838',
    stairUp: '#80c090', stairDown: '#c0a050',
    torch: '#f0b840', torchGlow: 'rgba(240,184,64,0.08)',
    hieroBg: 'rgba(228,168,48,0.04)',
    levelColors: ['#e4a830', '#e49030', '#c05838', '#7888c4', '#9a78aa', '#d07040', '#8899cc', '#bfa878'],
    hallColors: {
      oracle: '#98d4ac',
      utterance: '#e4a830',
      body:      '#e4b844',
      dead:      '#c05838',
      power:     '#e04040',
      secrets:   '#7888c4',
      cosmos:    '#88a8e4',
      wisdom:    '#9a78aa',
    },
  },
  PANEL_W: 440,
  MINIMAP_W: 200, MINIMAP_H: 140,
};

// ── Egyptian hieroglyphs ──
const HIERO_CHARS = '𓀀𓀁𓀂𓀃𓀄𓀅𓀆𓀇𓀈𓀉𓀊𓁟𓁹𓂋𓂝𓃀𓃭𓄂𓅓𓅱𓆈𓆣𓆤𓇋𓇌𓇥𓇯𓈖𓈗𓉐𓉔𓊃𓊹𓊽𓋴𓌃𓌙𓍯𓎛𓏏𓏤𓏥𓏭𓏮𓐍𓐎𓐏𓊪𓁶𓁷𓁸𓁹𓂀𓂁𓂂𓂃𓂄𓂅𓂆𓂇𓂈𓂉𓂊𓂋𓂌𓂍𓂎𓂏𓂐𓂑𓂒𓃭𓃮𓃯𓃰𓃱𓃲𓃳𓃴𓃵𓃶𓃷𓃸𓃹𓃺𓄂𓄃𓄄𓄅𓄆𓄇𓄈𓄉𓄊'.split('');
const HIERO_SIMPLE = '𓊹𓁟𓂋𓊽𓇋𓈖𓏤𓁹𓂝𓅱𓆣𓆤𓇯𓉐𓃀𓄂𓅓𓈗𓉔𓊃𓌃𓌙𓍯𓏥𓏭𓎛𓅓'.split('');

// Room border styles per hall type
const HALL_BORDERS = {
  oracle:    { tl:'╔', tr:'╗', bl:'╚', br:'╝', h:'═', v:'║', inner:'·' },
  utterance: { tl:'┌', tr:'┐', bl:'└', br:'┘', h:'─', v:'│', inner:'·' },
  body:      { tl:'╒', tr:'╕', bl:'╘', br:'╛', h:'═', v:'│', inner:'.' },
  dead:      { tl:'╓', tr:'╖', bl:'╙', br:'╜', h:'─', v:'║', inner:'░' },
  power:     { tl:'╔', tr:'╗', bl:'╚', br:'╝', h:'═', v:'║', inner:'▒' },
  secrets:   { tl:'┏', tr:'┓', bl:'┗', br:'┛', h:'━', v:'┃', inner:'·' },
  cosmos:    { tl:'╭', tr:'╮', bl:'╰', br:'╯', h:'─', v:'│', inner:'*' },
  wisdom:    { tl:'▛', tr:'▜', bl:'▙', br:'▟', h:'─', v:'│', inner:'·' },
};

// Wall inscription characters — dense, per level
const INSCR_DENSE = [
  ['▒','░','▓','▐','▌','▄','▀'],       // L0 Oracle — blocks
  ['☰','☱','☲','☳','☴','☵','☶','☷'], // L1 Utterance — trigrams
  ['†','‡','✦','✧','◆','◇','●','○'],  // L2 Dead/Power — ritual
  ['⊕','⊗','⊙','⊛','⊞','⊟','⊠','⊡'], // L3 Secrets — sigils
  ['∞','∅','∇','∆','◊','□','▷','◁'],  // L4 Wisdom — abstract
];

// ── SCROLL/TEXT OBJECT GLYPHS — physical named-text objects you can walk up to ──
// Rules:
//   1. NO character may appear in INSCR_DENSE (wall text) — avoids visual confusion.
//   2. Chars must read as OBJECTS (tiles, tablets, codices) not text bands.
//   3. All chars are BMP; render in Fira Code + any monospace fallback.
const SCROLL_GLYPHS = [
  ['◈', '◉', '◎'],  // L0 Oracle    — medallion discs
  ['▤', '▦', '▣'],  // L1 Old Kingdom — checked squares (papyrus stacks)
  ['▧', '▨', '▩'],  // L2 First Int   — diagonal-fill squares (ostraca)
  ['▭', '▬', '▮'],  // L3 Middle KG   — horizontal bars (rolled papyrus)
  ['◫', '◪', '◩'],  // L4 Second Int  — split squares (broken stelae)
  ['◐', '◑', '◒'],  // L5 New Kingdom — half-discs (amulet tablets)
  ['◓', '◔', '◕'],  // L6 Late Period  — quarter-circle tablets
  ['◖', '◗', '◌'],  // L7 Greco-Roman  — arc discs (Ptolemaic roundels)
];
// Frame: vertical bars so the scroll reads as a contained object, not wall text.
const SCROLL_FRAME = { left: '▏', right: '▕' };
// User-generated Oracle articles use a special glyph so they stand out
const ARTICLE_GLYPH = '𓋹';  // ankh — the "living article" the user co-authored

// ══════════════════════════════════════════════════════════════════════════════
// STATE
// ══════════════════════════════════════════════════════════════════════════════
const G = {
  canvas: null, ctx: null, cols: 0, rows: 0, dpr: 1,
  currentLevel: 0, levels: {}, levelMeta: {},
  tiles: [], worldW: 0, worldH: 0,
  player: { x: 5, y: 5, tx: 5, ty: 5, moveT: 0, moving: false, ox: 5, oy: 5 },
  camera: { x: 0, y: 0 },
  chambers: [], chambersById: {},
  rooms: [],
  explored: null,
  exploredByLevel: {},
  guideText: '', guideTextFade: 0,
  // Unified center-stage panel — replaces guideText + scattered overlays
  center: null,  // { mode, title, body, source, startTime, duration, fadeOut }
  messages: [],
  keys: {},
  lastFrame: 0, frameCount: 0,
  currentRoom: null,
  inspectedInscr: null,
  inspectedScroll: null,      // { textLabel, canonicalId, period, chamberId, x, y } — named-text scroll
  // Held quotes tray — quotes the user has "lifted" from the Oracle chat,
  // to be fused into a bespoke article via Kimi on demand.
  heldQuotes: [],             // [{text, source, chamber_id, canonical_id}]
  articleComposerOpen: false, // UI state: held-quotes tray panel
  userArticles: {},           // chamber_id -> {article_id, content, placed_at:{x,y}, theme}
  // Oracle
  oracleRoomIdx: -1, oraclePos: null,
  oracleChatActive: false,
  oracleChatHistory: [],
  oracleWs: null, oracleWaiting: false,
  oracleChatCursor: true, oracleCursorTimer: 0,
  // Input capture element
  inputEl: null, lastInputVal: '',
  // Overlays
  showMap: false, showHelp: false,
  speakActive: false, speakAbort: null, speakSessionId: 0,
  // Pathfinding
  oraclePath: new Set(),
  // Particles & effects
  particles: [], torches: [], hieroRain: [],
  sigils: [],   // Animated floating sigils
  portalRings: [], // Oracle portal rings
  hoverStair: null,  // { x, y, dir, targetLevel } — mouse hover over stair zone
  // Map overlay navigation
  mapCursor: 0,       // index into flat chamber list
  mapCursorLevel: 0,  // level currently browsed in map
  mapScrollY: 0,      // pixel scroll offset for the map overlay
  // Oracle agentic state
  highlightedChambers: new Set(),  // chamber ids Oracle has highlighted
  portalOpen: false,
  portalChamberId: null,           // chamber the portal is tuned to
  // Room passages cache
  roomPassages: {},
  // Transition animation
  transitioning: false, transitionAlpha: 0, transitionTarget: -1, transitionDir: '',
  // Boot animation
  booted: false, initialized: false,
  bootLines: [], bootDone: false,
  // Stair positions
  stairsUp: [], stairsDown: [],
  interactTarget: null,
  // Complex map: computed center for Oracle
  complexCenter: { x: 0, y: 0 },
  // Pulse timers
  oraclePulse: 0,
  // Custom cursor
  cursorX: -1, cursorY: -1,
};

// ══════════════════════════════════════════════════════════════════════════════
// BOOT SEQUENCE
// ══════════════════════════════════════════════════════════════════════════════
const BOOT_SEQUENCE = [
  { text: '', delay: 150 },
  { text: '    ╔═══════════════════════════════════════════════════════════════╗', delay: 50, color: 'gold' },
  { text: '    ║                                                               ║', delay: 20, color: 'gold' },
  { text: '    ║   𓊹  A E G Y P T U S  ·  T H E  L A B Y R I N T H  𓊹      ║', delay: 80, color: 'goldBright' },
  { text: '    ║                                                               ║', delay: 20, color: 'gold' },
  { text: '    ║            L I B R A R Y   O F   B A B E L                   ║', delay: 60, color: 'textDim' },
  { text: '    ║                                                               ║', delay: 20, color: 'gold' },
  { text: '    ║   77,683 texts  ·  8 levels  ·  41 halls  ·  79 chambers     ║', delay: 60, color: 'textDim' },
  { text: '    ║   Three millennia of Egyptian knowledge  ·  3000 BCE–400 CE  ║', delay: 50, color: 'textFaint' },
  { text: '    ║                                                               ║', delay: 20, color: 'gold' },
  { text: '    ╚═══════════════════════════════════════════════════════════════╝', delay: 50, color: 'gold' },
  { text: '', delay: 200 },
  { text: '    𓁟  Hermes-4-70B     · Oracle & Navigator', delay: 40, color: 'green' },
  { text: '    𓂋  Kimi K2.5        · Knowledge Synthesis', delay: 40, color: 'green' },
  { text: '', delay: 120 },
  { text: '    [ OPENING THE MOUTHS OF THE ANCIENT TEXTS ]', delay: 80, color: 'goldDim' },
  { text: '', delay: 100 },
  { text: '    𓊽 Loading chambers...', delay: 40, color: 'textFaint' },
];

async function boot() {
  G.canvas = document.getElementById('game');
  G.ctx = G.canvas.getContext('2d');
  G.dpr = window.devicePixelRatio || 1;
  G.explored = new Set();
  G.inputEl = document.getElementById('oracle-input-capture');

  resize();
  window.addEventListener('resize', resize);
  window.addEventListener('keydown', onKeyDown);
  window.addEventListener('wheel', e => {
    if (G.showMap) {
      e.preventDefault();
      const tile = Math.floor(Math.min(window.innerWidth, window.innerHeight) / 28);
      const levelH = tile * 7;
      const rowH = levelH + Math.floor(tile * 1.2);
      const totalMapH = tile * 5 + 8 * rowH + tile * 3;
      const maxScroll = Math.max(0, totalMapH - G.canvas.height / G.dpr);
      G.mapScrollY = Math.max(0, Math.min(maxScroll, G.mapScrollY + e.deltaY * 0.5));
    }
  }, { passive: false });
  window.addEventListener('keyup', onKeyUp);
  window.addEventListener('mousemove', e => {
    G.cursorX = e.clientX; G.cursorY = e.clientY;
    // Detect stair zone under cursor for hover tooltip
    // Use camera state set during last render — valid after boot
    if (G.initialized) {
      const viewCols = G.cols - Math.floor(CFG.PANEL_W / CFG.TILE);
      // clientX in CSS pixels, CFG.TILE in CSS pixels — direct division
      const tileX = Math.floor(e.clientX / CFG.TILE);
      const tileY = Math.floor(e.clientY / CFG.TILE);
      if (tileX < viewCols) {
        const wx = G.camera.x + tileX;
        const wy = G.camera.y + tileY;
        const t = getTile(wx, wy);
        if (t?.isStair) {
          G.hoverStair = {
            screenX: e.clientX, screenY: e.clientY,
            dir: t.stairDir,
            targetLevel: t.targetLevel,
          };
        } else {
          G.hoverStair = null;
        }
      } else {
        G.hoverStair = null;
      }
    }
  });

  // Input element — syncs to G.oracleChatInput
  G.inputEl.addEventListener('input', () => {
    G.oracleChatInput = G.inputEl.value;
  });
  G.inputEl.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      e.preventDefault();
      sendOracleMsg();
    }
    if (e.key === 'Escape') {
      closeOracleChat();
    }
  });

  requestAnimationFrame(gameLoop);

  // v4.0 §8: Preload hieroglyph font via FontFace API.
  // Hieroglyph font loading strategy:
  //
  // 1. CSS @font-face in index.html declares 'Noto Egyptian' with unicode-range.
  //    Chrome uses this fine for canvas; Firefox/Zen may ignore it for canvas
  //    because unicode-range tells the browser only to swap in that font for
  //    HTML text, not necessarily canvas 2D drawing.
  //
  // 2. We ALSO load via FontFace API as 'Noto Egyptian Canvas' (different name,
  //    NO unicode-range). Firefox always respects explicit FontFace additions.
  //
  // 3. CFG.HIERO_FONT = "'Noto Egyptian Canvas', 'Noto Egyptian', serif"
  //    so canvas always tries the explicitly-loaded name first.
  G.hieroFallback = false;
  const FONT_BASE = `${window.location.origin}/web/fonts/NotoSansEgyptianHieroglyphs-Regular`;
  async function loadHieroForCanvas() {
    const sources = [
      `url('${FONT_BASE}.woff2') format('woff2'), url('${FONT_BASE}.ttf') format('truetype')`,
      `url('${FONT_BASE}.ttf') format('truetype')`,
    ];
    for (const src of sources) {
      try {
        // 'Noto Egyptian Canvas' — no unicode-range so Firefox/Zen uses it on canvas.
        const f = new FontFace('Noto Egyptian Canvas', src);
        await f.load();
        document.fonts.add(f);
        console.log('Hieroglyph canvas font loaded:', f.status);
        return true;
      } catch(e) {
        console.warn('FontFace load attempt failed:', e.message);
      }
    }
    return false;
  }
  try {
    await document.fonts.ready;  // let CSS @font-face settle first
    await loadHieroForCanvas();
    await Promise.allSettled([
      document.fonts.load("32px 'Noto Egyptian Canvas'"),
      document.fonts.load("28px 'Fira Code'"),
      document.fonts.load("16px 'EB Garamond'"),
    ]);
  } catch(e) {
    console.warn('Font load partial:', e);
  }
  // Ink test on 96×96 canvas with a wide glyph at 60px.
  try {
    const tc = document.createElement('canvas');
    tc.width = 96; tc.height = 96;
    const tx = tc.getContext('2d');
    tx.font = "60px 'Noto Egyptian Canvas'";
    tx.fillStyle = '#fff';
    tx.fillText('\u{13007}', 4, 68);  // A008 walking man — wide, high coverage
    const d = tx.getImageData(0, 0, 96, 96).data;
    let ink = 0;
    for (let i = 3; i < d.length; i += 4) { if (d[i] > 30) ink++; }
    G.hieroFallback = ink < 5;
    console.log(G.hieroFallback ? `Hieroglyph FAILED (${ink}px) — fallback` : `Hieroglyph OK (${ink}px)`);
  } catch(e) {
    G.hieroFallback = true;
    console.warn('Hieroglyph test error:', e);
  }
  await new Promise(r => setTimeout(r, 50));

  // Boot animation
  await renderBootSequence();

  // v5.0 Day 4: load the kit-of-parts JSON before we touch topology —
  // Kit.size_room_for() drives per-chamber bay dimensions in the
  // cruciform placement loop below.
  try {
    if (window.Kit && typeof window.Kit.load === 'function') {
      await window.Kit.load();
      console.log(`Kit v${window.Kit.version} loaded (${Object.keys(window.Kit.parts).length} parts).`);
    }
  } catch (e) {
    console.warn('Kit failed to load — falling back to LEVEL_ROOM_SIZES:', e);
  }

  // Load data — v5.0 live topology.
  // L0 (Sanctum) comes from v3.1 chambers.json (hand-authored, 9 tablets).
  // L1..L7 come from /hackathon/levels + /hackathon/level/<id>/halls
  //   (Louvain clustering on the live corpus).
  try {
    const legacyResp = await fetch(`${API}/hackathon/graph`);
    const legacy = await legacyResp.json();
    // Keep only the L0 Sanctum from the legacy graph.
    const sanctum = legacy.filter(c => c.level === 0);

    const levelsResp = await fetch(`${API}/hackathon/levels`);
    const levelsMeta = await levelsResp.json();
    G.levelMeta = levelsMeta;

    G.chambers = [...sanctum];
    G.chambers.forEach(c => G.chambersById[c.id] = c);

    // Eagerly fetch halls for levels that actually have content. Each call
    // triggers Louvain clustering server-side (cached), ~1s each first time.
    for (const L of levelsMeta) {
      if (L.id === 0 || L.text_count < 80) continue;
      try {
        const hr = await fetch(`${API}/hackathon/level/${L.id}/halls`);
        const payload = await hr.json();
        (payload.halls || []).forEach(h => {
          // Shape a live hall as a v3.1-compatible chamber object.
          const term_eg = h.defining_lemmata.slice(0, 3).map(lr => lr.form).join(' · ');
          const term_en = h.defining_lemmata.slice(0, 3)
            .map(lr => (lr.gloss_en || lr.form).split(';')[0].split(',')[0].trim())
            .join(' · ');
          const ch = {
            id: h.chamber_id,
            name_en: h.name_en,
            level: h.level_id,
            hall: h.chamber_id,          // each hall is its own wing for now
            term_eg,
            term_en,
            defining_lemmata: h.defining_lemmata,
            text_count: h.text_count,
            // Full canonical_id list for storage-pass scroll binding.
            // Fall back to the 8-entry top_text_ids if the server didn't
            // return assigned_ids (older builds).
            assigned_ids: h.assigned_ids || h.top_text_ids || [],
            canonical_ids: h.assigned_ids || h.top_text_ids || [],
            // Kit-driven room sizing — used by the cruciform placer.
            text_type_composition: h.text_type_composition || {},
            suggested_size: h.suggested_size || null,
            period_range: L.date_range,
            corridors: [],                // no pre-wired connectivity; halls = rooms
            description: '',
            live: true,
          };
          G.chambers.push(ch);
          G.chambersById[ch.id] = ch;
        });
      } catch (e) {
        console.warn(`Level ${L.id} halls failed:`, e);
      }
    }

    for (let i = 0; i <= 7; i++) {
      G.levels[i] = G.chambers.filter(c => c.level === i);
    }
  } catch (e) {
    addMsg('Failed to load topology. Is the server running?', CFG.COLORS.danger);
    console.error(e);
    return;
  }

  generateLevel(0);
  G.booted = true;
  G.initialized = true;

  addMsg('𓊹 THE LABYRINTH OF AEGYPTUS. The Oracle awaits at the center.', CFG.COLORS.gold);
  addMsg('↑↓←→ navigate · [E] interact · [SPACE] SPEAK · [M] map · [?] help', CFG.COLORS.textDim);
}

async function renderBootSequence() {
  return new Promise(resolve => {
    const lines = [];
    let idx = 0;

    const drawFrame = () => {
      const ctx = G.ctx;
      const tile = CFG.TILE * G.dpr;
      ctx.fillStyle = CFG.COLORS.dark;
      ctx.fillRect(0, 0, G.canvas.width, G.canvas.height);

      // Scanlines
      for (let y = 0; y < G.canvas.height; y += 2) {
        ctx.fillStyle = 'rgba(0,0,0,0.035)';
        ctx.fillRect(0, y, G.canvas.width, 1);
      }

      const fs = Math.floor(tile * 0.82);
      ctx.font = `${fs}px ${CFG.FONT}`;
      ctx.textBaseline = 'top';
      const startY = G.canvas.height * 0.12;

      lines.forEach((line, i) => {
        const color = CFG.COLORS[line.color] || CFG.COLORS.text;
        ctx.fillStyle = color;
        ctx.fillText(line.text, tile * 1.5, startY + i * (fs + 3));
      });

      if (idx < BOOT_SEQUENCE.length) {
        lines.push(BOOT_SEQUENCE[idx]);
        const delay = BOOT_SEQUENCE[idx].delay;
        idx++;
        setTimeout(drawFrame, delay);
      } else {
        // Flicker then resolve
        let flickers = 0;
        const flicker = () => {
          if (flickers++ > 5) { setTimeout(resolve, 300); return; }
          ctx.fillStyle = `rgba(196,146,42,${0.04 + Math.random() * 0.06})`;
          ctx.fillRect(0, 0, G.canvas.width, G.canvas.height);
          setTimeout(flicker, 60 + Math.random() * 80);
        };
        setTimeout(flicker, 500);
      }
    };
    drawFrame();
  });
}

// ══════════════════════════════════════════════════════════════════════════════
// LEVEL & ARCHITECTURE — Library of Babel hierarchy
// ══════════════════════════════════════════════════════════════════════════════

// Level names with conceptual depth
const LEVEL_NAMES = [
  'THE ORACLE SANCTUM',
  'THE OLD KINGDOM',
  'THE FIRST INTERMEDIATE',
  'THE MIDDLE KINGDOM',
  'THE SECOND INTERMEDIATE',
  'THE NEW KINGDOM',
  'THE LATE PERIOD',
  'THE GRECO-ROMAN AGE',
];

const LEVEL_SUBTITLES = [
  'Center of all creation — Hermes speaks here',
  'Pyramid texts · tomb biographies · first writings',
  'Kingless years · regional voices · coffin spells',
  'Classical Egyptian · Sinuhe · Middle Kingdom literature',
  'Hyksos · disruption · northern rule',
  'Empire · Amarna · Book of the Dead · royal tombs',
  'Saite revival · Persian rule · priestly archives',
  'Ptolemies · Demotic · temple libraries · Rosetta',
];

// Room size by level — deeper = more labyrinthine, cramped, intricate
const LEVEL_ROOM_SIZES = [
  { w: 56, h: 34 },  // L0 — vast Oracle sanctum
  { w: 42, h: 26 },  // L1 — Old Kingdom (largest corpus: ~21k texts)
  { w: 36, h: 22 },  // L2 — First Intermediate (sparse)
  { w: 36, h: 22 },  // L3 — Middle Kingdom (classical)
  { w: 30, h: 18 },  // L4 — Second Intermediate (sparse)
  { w: 40, h: 24 },  // L5 — New Kingdom (dense)
  { w: 32, h: 20 },  // L6 — Late Period
  { w: 28, h: 18 },  // L7 — Greco-Roman
];

function generateLevel(levelNum) {
  G.currentLevel = levelNum;
  const levelChambers = G.levels[levelNum] || [];

  if (G.explored) G.exploredByLevel[G.currentLevel] = new Set(G.explored);
  G.explored = G.exploredByLevel[levelNum] || new Set();

  G.rooms = [];
  G.stairsUp = [];
  G.stairsDown = [];
  G.torches = [];
  G.particles = [];
  G.hieroRain = [];
  G.sigils = [];
  G.portalRings = [];
  G.currentRoom = null;
  G.inspectedInscr = null;
  G.interactTarget = null;
  G.oracleRoomIdx = -1;
  G.oraclePos = null;
  G.oraclePath.clear();

  if (levelChambers.length === 0) {
    G.worldW = 40; G.worldH = 28;
    G.tiles = createEmptyGrid(G.worldW, G.worldH);
    return;
  }

  const sz = LEVEL_ROOM_SIZES[levelNum] || { w: 28, h: 16 };
  const RW = sz.w, RH = sz.h;

  const placements = [];
  const spines = [];   // per-level: [{dir, x1,y1,x2,y2, hallId}]
  let courtBounds = null;

  if (levelNum === 0) {
    // Level 0: Single grand Oracle sanctum — perfectly centered
    const ch = levelChambers[0];
    placements.push({
      chamber: ch, x: 6, y: 6, w: RW, h: RH,
      centerX: 6 + Math.floor(RW / 2), centerY: 6 + Math.floor(RH / 2),
      inscriptions: [], scrolls: [], isOracleRoom: true, hallId: 'oracle',
    });
  } else {
    // ========================================================================
    // v5.0 CRUCIFORM LEVEL LAYOUT
    //
    //   central court (with stairs) — four spine-halls in cardinal directions
    //   — chambers branch off each spine on alternating sides.
    //
    //          [ N-SPINE chambers ]
    //                 ┃
    //                 ┃
    // [W-chambers]──[ COURT ]──[E-chambers]
    //                 ┃
    //                 ┃
    //          [ S-SPINE chambers ]
    //
    // Each cardinal spine gets its own hall style; each chamber has a
    // 3-wide gateway punched in its spine-facing wall.
    // ========================================================================

    // 1. Bucket chambers across 4 cardinal halls (round-robin by text_count
    //    desc) so the biggest chambers distribute across the cross instead
    //    of piling up on one arm.
    // v5.2 INFINITY PASS — split large halls into a single-file SHELF RUN
    // along their arm. A hall with 600 texts becomes ~5 sub-chambers of 120
    // texts each, threaded in order down the spine. This turns the labyrinth
    // from 2-7 rooms per floor into 10-40, and the scale reads as vast.
    //
    // v5.3: ADAPTIVE sub-chamber size — sparse levels (L2-L7) use smaller
    // intervals so even 15-text halls produce 2-3 rooms, giving every era
    // architecturally deep corridors. Rich levels (L1) stay at 90 texts/room.
    const SUBCHAMBER_CAP   = 8;            // max sub-chambers per hall
    const totalLevelTexts  = levelChambers.reduce((s, c) => s + (c.text_count || 0), 0);
    // Ideal: ~20 sub-chambers total across the level → solve for texts/room.
    // Clamp to [10, 90] so rooms are neither too tiny nor too few.
    const SUBCHAMBER_TEXTS = Math.max(10, Math.min(90, Math.floor(totalLevelTexts / 20)));
    function splitHall(ch) {
      const n = ch.text_count || 0;
      if (n < SUBCHAMBER_TEXTS * 1.5) return [ch];   // single room for truly tiny halls
      const ids = (ch.assigned_ids || ch.canonical_ids || []);
      const parts = Math.min(SUBCHAMBER_CAP, Math.max(2, Math.ceil(n / SUBCHAMBER_TEXTS)));
      const sub = [];
      for (let i = 0; i < parts; i++) {
        const start = Math.floor((i * ids.length) / parts);
        const end   = Math.floor(((i + 1) * ids.length) / parts);
        const slice = ids.slice(start, end);
        // Sub-chamber carries a roman-numeral suffix so map/oracle can still
        // target the parent hall, but each sub reads as a distinct room.
        const suffix = ['I','II','III','IV','V','VI','VII','VIII'][i] || String(i+1);
        const subCount = Math.max(1, Math.round(n * (end - start) / Math.max(1, ids.length)));
        sub.push({
          ...ch,
          id: `${ch.id}::${i + 1}`,
          parentChamberId: ch.id,
          name_en: parts > 1 ? `${ch.name_en} · ${suffix}` : ch.name_en,
          assigned_ids: slice,
          canonical_ids: slice,
          text_count: subCount,
          isSubChamber: parts > 1,
          subIndex: i,
          subTotal: parts,
        });
      }
      return sub;
    }

    const expandedChambers = [];
    for (const ch of levelChambers) {
      for (const s of splitHall(ch)) expandedChambers.push(s);
    }
    // Register every sub-chamber in G.chambersById so the map, the Oracle,
    // and interactions resolve them.
    expandedChambers.forEach(c => {
      if (!G.chambersById[c.id]) G.chambersById[c.id] = c;
    });

    const chambersSorted = [...expandedChambers].sort(
      (a, b) => (b.text_count || 0) - (a.text_count || 0)
    );
    const CARDINALS = [
      { dir: 'N', dx: 0,  dy: -1, hallId: 'utterance' },
      { dir: 'E', dx: 1,  dy: 0,  hallId: 'cosmos'    },
      { dir: 'S', dx: 0,  dy: 1,  hallId: 'power'     },
      { dir: 'W', dx: -1, dy: 0,  hallId: 'wisdom'    },
    ];
    // Bucketing strategy: keep sub-chambers from the SAME parent hall on the
    // SAME arm so the player walks down a coherent shelf run. Largest halls
    // get their own cardinal; remaining halls round-robin.
    const buckets = { N: [], E: [], S: [], W: [] };
    const hallToDir = new Map();          // parentChamberId -> dir
    let rr = 0;
    for (const ch of chambersSorted) {
      const parent = ch.parentChamberId || ch.id;
      let dir = hallToDir.get(parent);
      if (!dir) {
        dir = CARDINALS[rr++ % 4].dir;
        hallToDir.set(parent, dir);
      }
      buckets[dir].push(ch);
    }
    // Within each arm, sort sub-chambers of the same hall by subIndex so
    // the shelf run reads in order (I, II, III, …).
    for (const d of ['N','E','S','W']) {
      buckets[d].sort((a, b) => {
        const pa = a.parentChamberId || a.id;
        const pb = b.parentChamberId || b.id;
        if (pa !== pb) return 0;                     // preserve inter-hall order
        return (a.subIndex || 0) - (b.subIndex || 0);
      });
    }

    // 2. Architectural archetypes. Assigned to each chamber; carveRoom uses
    //    the archetype to lay out interior structure (pillars, aisles,
    //    apses). Keyed by text_count bucket so large chambers get hypostyle
    //    forests, small ones get intimate cellas.
    const ARCHETYPES = ['hypostyle', 'peristyle', 'colonnade', 'aisled', 'cella'];
    // Distribute archetypes so each level feels varied. Scale-bucket the
    // chamber first, then rotate within the level so neighboring chambers
    // don't repeat.
    let archetypeRot = 0;
    function pickArchetype(ch) {
      const n = ch.text_count || 0;
      if (n >= 550) return 'hypostyle';     // only the very largest
      if (n >= 250) return 'peristyle';     // perimeter colonnade
      if (n >= 110) return ['colonnade', 'aisled'][archetypeRot++ % 2];
      if (n >=  60) return ['aisled', 'cella'][archetypeRot++ % 2];
      return 'cella';                        // intimate
    }

    // 3. Geometry. Court at center. Each arm = single file of chambers
    //    threaded by the spine (nave-and-chapels pattern). Chamber bays
    //    are oriented with their long axis PERPENDICULAR to the spine so
    //    the spine passes through each bay from gateway to far gateway.
    const COURT_W = 32, COURT_H = 22;
    const GATE_W  = 3;
    const SPINE_W = 5;
    const GAP     = 4;

    // Per-arm cruciform constraints. For non-overlap at the cross corners,
    // the bay's long axis must STAY INSIDE its arm's lane:
    //   N/S chambers: width  <= COURT_W    (so they never reach E/W lanes)
    //   E/W chambers: height <= COURT_H    (so they never reach N/S lanes)
    // Short axis is free to grow outward along the arm.
    const BAY_CONSTRAINTS_NS = {
      maxLong:  COURT_W,                       // w <= court width
      maxShort: Math.max(14, RH - 4),
      minLong:  Math.max(18, Math.floor(COURT_W * 0.75)),
      minShort: 12,
    };
    const BAY_CONSTRAINTS_EW = {
      maxLong:  COURT_H,                       // h <= court height
      maxShort: Math.max(14, RW - 8),
      minLong:  Math.max(14, Math.floor(COURT_H * 0.75)),
      minShort: 12,
    };
    const constraintsFor = (armDir) =>
      (armDir === 'N' || armDir === 'S') ? BAY_CONSTRAINTS_NS : BAY_CONSTRAINTS_EW;

    // 3a. Resolve per-chamber bay dimensions from the kit (if loaded) or
    //     fall back to the old fixed LEVEL_ROOM_SIZES values. Done before
    //     we compute arm extents so each arm's outer reach tracks its
    //     chambers' actual depths.
    function bayFor(ch, armDir) {
      const c = constraintsFor(armDir);
      if (window.Assembler && window.Kit && window.Kit.__loaded) {
        return window.Assembler.bayDimsFor(ch, armDir, c);
      }
      // Legacy path: clamp to per-arm lane constraints.
      const isNS = armDir === 'N' || armDir === 'S';
      if (isNS) {
        return { w: Math.min(c.maxLong, RW), h: Math.min(c.maxShort, Math.max(c.minShort, RH - 4)) };
      }
      return { w: Math.min(c.maxShort, Math.max(c.minShort, RH - 4)), h: Math.min(c.maxLong, RW) };
    }

    // Pre-compute bay dims per arm to size the world grid.
    const armBays = { N: [], E: [], S: [], W: [] };
    for (const d of ['N','E','S','W']) {
      for (const ch of buckets[d]) {
        armBays[d].push(bayFor(ch, d));
      }
    }

    // Arm extent: sum of chamber depths (short axis) + GAP between.
    const armExt = {};
    for (const d of ['N','E','S','W']) {
      const isNS = d === 'N' || d === 'S';
      let ext = GAP;
      for (const b of armBays[d]) {
        const depth = isNS ? b.h : b.w;   // rotation-aware: "depth" = short axis in world space
        ext += depth + GAP;
      }
      armExt[d] = ext;
    }
    // Widest chamber on any arm expands the world grid sideways.
    const maxLongN = Math.max(0, ...armBays.N.map(b => b.w));
    const maxLongS = Math.max(0, ...armBays.S.map(b => b.w));
    const maxLongE = Math.max(0, ...armBays.E.map(b => b.h));
    const maxLongW = Math.max(0, ...armBays.W.map(b => b.h));

    // Margin on each side of the cross. Archetype placement + masonry +
    // torch rings need ~6 tiles clearance; we give 10 for luxury.
    const EDGE_PAD = 10;
    const worldW = Math.max(COURT_W + 2 * EDGE_PAD,
                            armExt.W + COURT_W + armExt.E + 2 * EDGE_PAD,
                            Math.max(maxLongN, maxLongS) + 2 * EDGE_PAD);
    const worldH = Math.max(COURT_H + 2 * EDGE_PAD,
                            armExt.N + COURT_H + armExt.S + 2 * EDGE_PAD,
                            Math.max(maxLongE, maxLongW) + 2 * EDGE_PAD);
    G.worldW = worldW; G.worldH = worldH;
    G.tiles = createEmptyGrid(G.worldW, G.worldH);

    // Court position is NOT the world centre when arms are asymmetric.
    // We anchor by the arm extents so the W arm doesn't overflow when E
    // is much longer. Courts always fits inside (checked above).
    const courtX = Math.max(EDGE_PAD, Math.min(worldW - COURT_W - EDGE_PAD,
                                                Math.floor(armExt.W + EDGE_PAD)));
    const courtY = Math.max(EDGE_PAD, Math.min(worldH - COURT_H - EDGE_PAD,
                                                Math.floor(armExt.N + EDGE_PAD)));
    courtBounds = { x: courtX, y: courtY, w: COURT_W, h: COURT_H,
      cx: courtX + Math.floor(COURT_W/2), cy: courtY + Math.floor(COURT_H/2) };
    G.complexCenter = { x: courtBounds.cx, y: courtBounds.cy };

    // 4. Place chambers: one per rank, centered on the spine axis, with
    //    per-chamber bay dims from the kit. Outer bays stack past inner
    //    ones by the cumulative depth of everything before them on the arm.
    function placeArm(dir) {
      const card = CARDINALS.find(c => c.dir === dir);
      const bucket = buckets[dir];
      if (!bucket.length) return;
      const cx = courtBounds.cx, cy = courtBounds.cy;
      const isNS = dir === 'N' || dir === 'S';

      let runningDepth = GAP;   // distance from court edge along the arm
      for (let rank = 0; rank < bucket.length; rank++) {
        const ch = bucket[rank];
        const bay = armBays[dir][rank];
        const w = bay.w, h = bay.h;
        const depth = isNS ? h : w;

        let rx, ry;
        if (isNS) {
          rx = cx - Math.floor(w / 2);
          ry = dir === 'N' ? (courtBounds.y - runningDepth - h)
                           : (courtBounds.y + COURT_H + runningDepth);
        } else {
          ry = cy - Math.floor(h / 2);
          rx = dir === 'W' ? (courtBounds.x - runningDepth - w)
                           : (courtBounds.x + COURT_W + runningDepth);
        }
        rx = Math.max(2, Math.min(worldW - w - 2, rx));
        ry = Math.max(2, Math.min(worldH - h - 2, ry));
        placements.push({
          chamber: ch,
          x: rx, y: ry, w, h,
          centerX: rx + Math.floor(w/2),
          centerY: ry + Math.floor(h/2),
          inscriptions: [], scrolls: [],
          hallId: card.hallId,
          armDir: dir,
          rank,
          archetype: pickArchetype(ch),
        });

        runningDepth += depth + GAP;
      }
    }
    for (const d of ['N','E','S','W']) placeArm(d);
  }

  // Compute world size (L0 only; L>0 already set above)
  if (levelNum === 0) {
    const maxX = Math.max(80, ...placements.map(p => p.x + p.w)) + 12;
    const maxY = Math.max(50, ...placements.map(p => p.y + p.h)) + 12;
    G.worldW = maxX; G.worldH = maxY;
    G.tiles = createEmptyGrid(G.worldW, G.worldH);
  }

  // STRUCTURAL PASS: carve chamber shells (walls + floors only).
  placements.forEach(p => carveRoomShell(p, levelNum));
  G.rooms = placements;

  // COURT + SPINES (L>0): punch gateways before chambers get inscribed so
  // inscription placement can avoid the gateway strips.
  if (levelNum > 0 && courtBounds) {
    carveCourt(courtBounds, levelNum);
    for (const dir of ['N','E','S','W']) {
      carveSpineAndGateways(dir, courtBounds, placements.filter(p => p.armDir === dir), levelNum);
    }
  }

  // DRESS PASS: name, inscriptions, archetype, scrolls — now gateway-aware.
  placements.forEach(p => dressRoom(p, levelNum));

  // MASONRY PASS (L>0): thicken exterior walls + style gates + enclose spines.
  if (levelNum > 0 && courtBounds) {
    placements.forEach(p => thickenMasonry(p));
    thickenMasonry({ x: courtBounds.x, y: courtBounds.y, w: courtBounds.w, h: courtBounds.h, isCourt: true });
    styleGateways();
    encloseSpines(courtBounds, placements);
  }

  // Oracle placement
  if (levelNum === 0 && placements.length > 0) {
    G.oracleRoomIdx = 0;
    const oRoom = placements[0];
    const ox = oRoom.centerX, oy = oRoom.centerY - 3;
    // Oracle sigil cluster
    setTile(ox, oy, { ch: '𓁟', fg: CFG.COLORS.oracle, walk: false, isOracle: true, oracleCore: true });
    setTile(ox - 2, oy, { ch: '𓊹', fg: CFG.COLORS.goldDim, walk: false, isOracle: true });
    setTile(ox + 2, oy, { ch: '𓊹', fg: CFG.COLORS.goldDim, walk: false, isOracle: true });
    setTile(ox, oy - 1, { ch: '𓂋', fg: CFG.COLORS.greenDim, walk: false, isOracle: true });
    setTile(ox, oy + 1, { ch: '𓊽', fg: CFG.COLORS.greenDim, walk: false, isOracle: true });
    // Make surroundings walkable
    for (const [dx, dy] of [
      [0, 2], [0, 3], [-1, 2], [1, 2], [-2, 2], [2, 2],
      [0, -2], [-1, -1], [1, -1], [-3, 0], [3, 0],
    ]) {
      const t = getTile(ox + dx, oy + dy);
      if (t && !t.walk && !t.isOracle) setTile(ox + dx, oy + dy, mkFloor(0));
    }
    G.oraclePos = { x: ox, y: oy };
    G.complexCenter = { x: ox, y: oy };

    // Portal rings (concentric decorative circles)
    spawnPortalRings(ox, oy);
  }

  // Stairs
  placeStairs(placements, levelNum);

  // Torches
  placeTorches(levelNum);

  // Ambient sigils
  // Sigils removed — too distracting

  // Player position
  if (levelNum > 0 && G.complexCenter) {
    // Spawn in the court, just south of dead center.
    G.player.x = G.complexCenter.x;
    G.player.y = G.complexCenter.y + 2;
    G.player.tx = G.player.x; G.player.ty = G.player.y;
    G.player.ox = G.player.x; G.player.oy = G.player.y;
    G.currentRoom = null;
  } else if (placements.length > 0) {
    const first = placements[0];
    G.player.x = first.centerX;
    G.player.y = first.centerY + (first.isOracleRoom ? 6 : 3);
    G.player.tx = G.player.x; G.player.ty = G.player.y;
    G.player.ox = G.player.x; G.player.oy = G.player.y;
    G.currentRoom = first;
  }

  if (levelNum === 0) computeOraclePath();

  addMsg(
    `𓂋 ${LEVEL_NAMES[levelNum]} — ${levelChambers.length} chambers · ${LEVEL_SUBTITLES[levelNum]}`,
    CFG.COLORS.levelColors[levelNum] || CFG.COLORS.gold
  );
}

function createEmptyGrid(w, h) {
  const tiles = [];
  for (let y = 0; y < h; y++) {
    tiles[y] = [];
    for (let x = 0; x < w; x++) {
      tiles[y][x] = { ch: ' ', fg: CFG.COLORS.void, walk: false };
    }
  }
  return tiles;
}

// ══════════════════════════════════════════════════════════════════════════════
// ROOM CARVING — distinct visual identity per hall type
// ══════════════════════════════════════════════════════════════════════════════
// Legacy entry-point retained for L0 (oracle sanctum): runs shell + dress
// in one call. For L>0 we split into carveRoomShell → [gateways] → dressRoom.
function carveRoom(p, level) {
  carveRoomShell(p, level);
  dressRoom(p, level);
}

function carveRoomShell(p, level) {
  const { x: rx, y: ry, w: rw, h: rh, chamber } = p;
  const hallId = p.hallId || 'default';
  const borders = HALL_BORDERS[hallId] || HALL_BORDERS.utterance;
  const isOracle = p.isOracleRoom;

  // ── OUTER WALLS (bright gold) ──
  for (let x = rx + 1; x < rx + rw - 1; x++) {
    setTile(x, ry,           { ch: borders.h, fg: CFG.COLORS.wallGold, walk: false, isChamberWall: true });
    setTile(x, ry + rh - 1,  { ch: borders.h, fg: CFG.COLORS.wallGold, walk: false, isChamberWall: true });
  }
  for (let y = ry + 1; y < ry + rh - 1; y++) {
    setTile(rx,          y, { ch: borders.v, fg: CFG.COLORS.wallGold, walk: false, isChamberWall: true });
    setTile(rx + rw - 1, y, { ch: borders.v, fg: CFG.COLORS.wallGold, walk: false, isChamberWall: true });
  }
  setTile(rx,           ry,           { ch: borders.tl, fg: CFG.COLORS.gold, walk: false, isChamberWall: true, isCorner: true });
  setTile(rx + rw - 1,  ry,           { ch: borders.tr, fg: CFG.COLORS.gold, walk: false, isChamberWall: true, isCorner: true });
  setTile(rx,           ry + rh - 1,  { ch: borders.bl, fg: CFG.COLORS.gold, walk: false, isChamberWall: true, isCorner: true });
  setTile(rx + rw - 1,  ry + rh - 1,  { ch: borders.br, fg: CFG.COLORS.gold, walk: false, isChamberWall: true, isCorner: true });

  // ── INNER DECORATIVE BORDER — L0 sanctum only ──
  //    L>0 chambers are dressed by their archetype (pillars/aisles/etc.)
  //    which would clash with a second "decor" layer.
  if (isOracle && rw > 30 && rh > 18) {
    for (let x = rx + 2; x < rx + rw - 2; x++) {
      setTile(x, ry + 2,          { ch: '─', fg: CFG.COLORS.goldFaint, walk: true, isDecor: true });
      setTile(x, ry + rh - 3,     { ch: '─', fg: CFG.COLORS.goldFaint, walk: true, isDecor: true });
    }
    for (let y = ry + 3; y < ry + rh - 3; y++) {
      setTile(rx + 2,          y, { ch: '│', fg: CFG.COLORS.textGhost, walk: true, isDecor: true });
      setTile(rx + rw - 3,     y, { ch: '│', fg: CFG.COLORS.textGhost, walk: true, isDecor: true });
    }
    const orn = '◈';
    setTile(rx + 2,          ry + 2,          { ch: orn, fg: CFG.COLORS.goldFaint, walk: true, isDecor: true });
    setTile(rx + rw - 3,     ry + 2,          { ch: orn, fg: CFG.COLORS.goldFaint, walk: true, isDecor: true });
    setTile(rx + 2,          ry + rh - 3,     { ch: orn, fg: CFG.COLORS.goldFaint, walk: true, isDecor: true });
    setTile(rx + rw - 3,     ry + rh - 3,     { ch: orn, fg: CFG.COLORS.goldFaint, walk: true, isDecor: true });
  }

  // ── FLOOR — varies by hall ──
  for (let y = ry + 1; y < ry + rh - 1; y++) {
    for (let x = rx + 1; x < rx + rw - 1; x++) {
      setTile(x, y, mkFloorForHall(hallId));
    }
  }
}

function dressRoom(p, level) {
  const { x: rx, y: ry, w: rw, h: rh, chamber } = p;
  const hallId = p.hallId || 'default';
  const hallColor = CFG.COLORS.hallColors[hallId] || CFG.COLORS.wall;
  const isOracle = p.isOracleRoom;

  // ── ORACLE ROOM special: concentric rings + cardinal markers ──
  if (isOracle) {
    const cx = p.centerX, cy = p.centerY - 3;
    // Concentric rings at radii 5, 9, 13
    for (const rad of [5, 9, 13]) {
      for (let a = 0; a < 360; a += 3) {
        const radRad = a * Math.PI / 180;
        const tx = Math.round(cx + Math.cos(radRad) * rad);
        const ty = Math.round(cy + Math.sin(radRad) * (rad * 0.5));
        const t = getTile(tx, ty);
        if (t && t.walk && !t.isDecor) {
          setTile(tx, ty, { ch: '·', fg: CFG.COLORS.greenDim, walk: true, isDecor: true, ringRadius: rad });
        }
      }
    }
    // Cardinal axis markers
    const cardinals = [[0, -5, '𓂋'], [5, 0, '𓈖'], [0, 5, '𓏤'], [-5, 0, '𓊽']];
    cardinals.forEach(([dx, dy, ch]) => {
      const t = getTile(cx + dx, cy + dy);
      if (t && t.walk) setTile(cx + dx, cy + dy, { ch, fg: CFG.COLORS.goldDim, walk: true, isDecor: true });
    });
    return;
  }

  // ── CHAMBER NAME — architectural header, multi-line aware ──
  //
  // Chamber names can be up to ~80 chars (corpus-derived from defining
  // lemmata, e.g. "CHAMBER OF OSIRIS · JUSTIFIED PERSON · OSIRIS-KHENTI…").
  // Never let a name spill past the chamber's interior width or pile on top
  // of the pillar grid. Strategy:
  //   1. Reserve an interior "name band" of up to 3 rows (ry+1 .. ry+3).
  //   2. Wrap on " · " first (keeps lemma fragments whole), then on spaces.
  //   3. If we still overflow, truncate with an ellipsis.
  //   4. Tile every label cell with isLabel=true so placeArchetype skips
  //      the whole band (it already skips ry+1 and ry+3; now also ry+2).
  const name = chamber.name_en || '';
  const term = chamber.term_eg || '';
  const innerW = Math.max(1, rw - 4);        // leave 2-tile margin either side
  // Vertical budget for the name band: rh is chamber height in tiles;
  // reserve 3 tiles for walls + first archetype row, use up to 5 lines.
  const maxLines = Math.max(2, Math.min(5, rh - 6));

  function wrapName(s, width) {
    if (!s) return [];
    // Split on middot first — these are lemma boundaries, always clean.
    const pieces = s.split(' · ');
    const lines = [];
    let cur = '';
    const push = () => { if (cur) { lines.push(cur); cur = ''; } };
    const sep = ' · ';
    for (let i = 0; i < pieces.length; i++) {
      const p = pieces[i];
      const candidate = cur ? (cur + sep + p) : p;
      if (candidate.length <= width) { cur = candidate; continue; }
      // Current line is full — flush.
      push();
      if (p.length <= width) { cur = p; continue; }
      // A single lemma itself overflows — hard wrap on spaces.
      const words = p.split(' ');
      for (const w of words) {
        const c2 = cur ? (cur + ' ' + w) : w;
        if (c2.length <= width) { cur = c2; continue; }
        push();
        cur = (w.length <= width) ? w : (w.slice(0, width - 1) + '…');
      }
    }
    push();
    return lines;
  }

  // Strategy: try the full name, then progressively compact:
  //   1. full name + word wrap  (wide chambers: one line, maybe two)
  //   2. strip "CHAMBER OF " / "HALL OF " prefix
  //   3. fall back to line-per-lemma with the prefix on its own line
  function fitName(s, width, lines) {
    // Pass 1: natural wrap
    let attempt = wrapName(s, width);
    if (attempt.length <= lines) return attempt;

    // Pass 2: strip boilerplate prefix; promote it to its own header line
    const m = s.match(/^(CHAMBER OF |HALL OF |CHAMBER\s+|HALL\s+)(.*)$/i);
    if (m) {
      const prefix = m[1].trim();
      const rest   = m[2];
      const restLines = wrapName(rest, width);
      if (1 + restLines.length <= lines) return [prefix, ...restLines];
      // Pass 3: lemma-per-line
      const lemmata = rest.split(' · ').map(p => {
        return p.length <= width ? p : (p.slice(0, width - 1) + '…');
      });
      if (1 + lemmata.length <= lines) return [prefix, ...lemmata];
      // Pass 4: drop the prefix entirely, lemmata with ellipsis overflow
      if (lemmata.length <= lines) return lemmata;
      const kept = lemmata.slice(0, lines - 1);
      kept.push('… ' + (lemmata.length - (lines - 1)) + ' more');
      return kept;
    }

    // No prefix — truncate with ellipsis on final kept line
    const kept = attempt.slice(0, lines);
    const last = kept[lines - 1];
    kept[lines - 1] = (last.length + 1 <= width) ? (last + ' …')
                                                  : (last.slice(0, width - 1) + '…');
    return kept;
  }

  let nameLines = fitName(name, innerW, maxLines);

  // Render name lines centered, starting at ry+1. Each char isLabel=true.
  const writeLine = (text, y, color) => {
    if (!text) return;
    const startX = rx + Math.floor((rw - text.length) / 2);
    for (let i = 0; i < text.length; i++) {
      const tx = startX + i;
      if (tx <= rx || tx >= rx + rw - 1) continue;
      setTile(tx, y, { ch: text[i], fg: color, walk: true, isLabel: true });
    }
  };

  for (let i = 0; i < nameLines.length; i++) {
    writeLine(nameLines[i], ry + 1 + i, CFG.COLORS.gold);
  }

  // Decorative brackets on first name line if it fits
  if (nameLines.length > 0) {
    const l0 = nameLines[0];
    const sx = rx + Math.floor((rw - l0.length) / 2);
    if (sx - 2 > rx) {
      setTile(sx - 2, ry + 1, { ch: '⟨', fg: hallColor, walk: true, isLabel: true });
    }
    if (sx + l0.length + 1 < rx + rw - 1) {
      setTile(sx + l0.length + 1, ry + 1, { ch: '⟩', fg: hallColor, walk: true, isLabel: true });
    }
  }

  // Egyptian term — one row below the name block, dimmer. Truncate if needed.
  if (term) {
    const termY = ry + 1 + nameLines.length + 1;   // blank separator row
    if (termY < ry + rh - 2) {
      const t = term.length <= innerW ? term
               : (term.slice(0, innerW - 1) + '…');
      writeLine(t, termY, CFG.COLORS.goldDim);
    }
  }

  // Record the occupied label rows so archetype + inscriptions can avoid them.
  p.labelRows = [];
  for (let i = 0; i < nameLines.length; i++) p.labelRows.push(ry + 1 + i);
  if (term) p.labelRows.push(ry + 1 + nameLines.length + 1);

  // ── WALL INSCRIPTIONS — sparse bands, never where gateways open ──
  const cids = chamber.canonical_ids || [];
  const quotes = chamber.highlight_quotes || [];
  const inscrChars = INSCR_DENSE[Math.min(level, INSCR_DENSE.length - 1)];

  // Build a gate-exclusion predicate: walls whose adjacent wall tile is a
  // gateway must stay clear, so text can't block the opening.
  const wouldBlockGate = (x, y) => {
    for (const [dx, dy] of [[-1,0],[1,0],[0,-1],[0,1]]) {
      const t = getTile(x + dx, y + dy);
      if (t?.isGateway) return true;
    }
    return false;
  };
  // STEP across the wall at intervals of 3 (not 2) so inscriptions are
  // architecturally spaced. Pad 3 tiles from the corners so inscriptions
  // never sit next to a doorway or corner. Skip the top row if the label
  // band reaches it (name text lives there now).
  const labelRowSet2 = new Set(p.labelRows || []);
  if (!labelRowSet2.has(ry + 1)) {
    inscribeRow(rx + 4, rx + rw - 5, ry + 1,           p, chamber, cids, quotes, inscrChars, wouldBlockGate, 3);
  }
  inscribeRow(rx + 4, rx + rw - 5, ry + rh - 2,      p, chamber, cids, quotes, inscrChars, wouldBlockGate, 3);
  const labelMaxY = (p.labelRows && p.labelRows.length) ? Math.max(...p.labelRows) : (ry + 3);
  const colStartY = Math.max(ry + 5, labelMaxY + 2);
  inscribeCol(rx + 1,           colStartY, ry + rh - 6, p, chamber, cids, quotes, inscrChars, wouldBlockGate, 3);
  inscribeCol(rx + rw - 2,      colStartY, ry + rh - 6, p, chamber, cids, quotes, inscrChars, wouldBlockGate, 3);

  // ── ARCHITECTURAL ARCHETYPE — interior structure per chamber ──
  placeArchetype(p, chamber, cids, quotes, inscrChars);

  // ── PHYSICAL SCROLLS — named texts as touchable objects ──
  // L0 Sanctum uses v3.1 chamber.physical_texts (hand-authored tablets).
  // L>0 chambers consume chamber.assigned_ids via the kit-of-parts
  // assembler so every scroll glyph is backed by a real canonical_id.
  if (level === 0 || (chamber.physical_texts && chamber.physical_texts.length)) {
    placeScrolls(p, level);
  } else if (window.Assembler && (chamber.assigned_ids || []).length) {
    const glyphs = SCROLL_GLYPHS[Math.min(level, SCROLL_GLYPHS.length - 1)];
    window.Assembler.placeStorageScrolls(p, {
      setTile, getTile,
      glyphs,
      frame: SCROLL_FRAME,
      fgGlyph: CFG.COLORS.greenDim,
      fgFrame: CFG.COLORS.textGhost,
      roomIdx: G.rooms.length,
      budget: 8,    // keep rooms uncluttered; texts exist, not all need icons
    });
  }

  // ── TORCHES — interior corners only; never on spine, never near gates ──
  const spineAxis = (p.armDir === 'N' || p.armDir === 'S') ? 'vertical'
                  : (p.armDir === 'E' || p.armDir === 'W') ? 'horizontal'
                  : null;
  const nearGate = (x, y) => {
    for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) {
      const t = getTile(x + dx, y + dy);
      if (t?.isGateway) return true;
    }
    return false;
  };
  const onSpineCh = (x, y) => {
    if (spineAxis === 'vertical')   return Math.abs(x - p.centerX) <= 2;
    if (spineAxis === 'horizontal') return Math.abs(y - p.centerY) <= 2;
    return false;
  };
  const torchPos = [
    [rx + 3, ry + 5], [rx + rw - 4, ry + 5],
    [rx + 3, ry + rh - 5], [rx + rw - 4, ry + rh - 5],
  ];
  torchPos.forEach(([tx, ty]) => {
    if (tx <= rx || tx >= rx + rw - 1 || ty <= ry || ty >= ry + rh - 1) return;
    if (onSpineCh(tx, ty) || nearGate(tx, ty)) return;
    const t = getTile(tx, ty);
    if (!t || !t.walk || t.isLabel || t.isStructure) return;
    G.torches.push({ x: tx, y: ty, phase: Math.random() * Math.PI * 2, intensity: 0.7 + Math.random() * 0.3 });
    setTile(tx, ty, { ch: '☉', fg: CFG.COLORS.torch, walk: false, isTorch: true });
  });
}

function mkFloorForHall(hallId) {
  const r = Math.random();
  if (hallId === 'oracle') {
    if (r > 0.97) return { ch: '·', fg: CFG.COLORS.greenDim, walk: true };
    if (r > 0.94) return { ch: '∘', fg: CFG.COLORS.textGhost, walk: true };
    return { ch: ' ', fg: CFG.COLORS.floor, walk: true };
  }
  if (hallId === 'dead' || hallId === 'secrets') {
    if (r > 0.97) return { ch: '░', fg: '#1a1614', walk: true };
    if (r > 0.94) return { ch: '·', fg: CFG.COLORS.textGhost, walk: true };
    return { ch: ' ', fg: CFG.COLORS.floor, walk: true };
  }
  if (r > 0.97) return { ch: '·', fg: CFG.COLORS.floorDot, walk: true };
  if (r > 0.94) return { ch: '.', fg: CFG.COLORS.floorAlt, walk: true };
  return { ch: ' ', fg: CFG.COLORS.floor, walk: true };
}

function inscribeRow(x1, x2, y, room, chamber, cids, quotes, chars, blockFn, step) {
  step = step || 2;
  for (let x = x1; x <= x2; x += step) {
    if (x >= G.worldW - 1) break;
    const t = getTile(x, y);
    if (!t || t.isLabel || t.isDecor) continue;
    if (blockFn && blockFn(x, y)) continue;
    const idx = room.inscriptions.length;
    const cid = cids[idx % Math.max(1, cids.length)] || '';
    room.inscriptions.push({
      x, y, chamberId: chamber.id, canonicalId: cid, idx,
      quote: quotes[idx % Math.max(1, quotes.length)] || null,
    });
    setTile(x, y, {
      ch: chars[idx % chars.length], fg: CFG.COLORS.inscrHi, walk: false,
      isInscription: true, inscrIdx: idx, roomPtrIdx: G.rooms.length,
    });
  }
}

function inscribeCol(x, y1, y2, room, chamber, cids, quotes, chars, blockFn, step) {
  step = step || 2;
  for (let y = y1; y <= y2; y += step) {
    if (y >= G.worldH - 1) break;
    const t = getTile(x, y);
    if (!t || t.isLabel || t.isDecor) continue;
    if (blockFn && blockFn(x, y)) continue;
    const idx = room.inscriptions.length;
    const cid = cids[idx % Math.max(1, cids.length)] || '';
    room.inscriptions.push({
      x, y, chamberId: chamber.id, canonicalId: cid, idx,
      quote: quotes[idx % Math.max(1, quotes.length)] || null,
    });
    setTile(x, y, {
      ch: chars[idx % chars.length], fg: CFG.COLORS.inscrHi, walk: false,
      isInscription: true, inscrIdx: idx, roomPtrIdx: G.rooms.length,
    });
  }
}

// ════════════════════════════════════════════════════════════════════════════
// ARCHITECTURAL ARCHETYPES — interior structure per chamber
// ════════════════════════════════════════════════════════════════════════════
// Pillar glyph: double-line box-drawing col that reads as a column from above.
// We use █ (solid block) capped by ▛ / ▟ (half-block caps) for feet.
function placeArchetype(p, chamber, cids, quotes, chars) {
  const { x: rx, y: ry, w: rw, h: rh, archetype, armDir } = p;
  if (!archetype) return;
  const spineAxis = (armDir === 'N' || armDir === 'S') ? 'vertical' : 'horizontal';
  const cx = p.centerX, cy = p.centerY;

  // Forbidden placement:
  //  1. any wall tile, gateway tile
  //  2. 3-wide spine channel (always clear for through-traffic)
  //  3. label rows (the name strip) — ry+1 and ry+3
  //  4. 2 tiles adjacent to each gateway (so pillars don't trap the player)
  const labelRows = p.labelRows || [ry + 1, ry + 3];
  const labelRowSet = new Set(labelRows);
  const maxLabelY = labelRows.length ? Math.max(...labelRows) : (ry + 3);
  const isForbidden = (x, y) => {
    const t = getTile(x, y);
    if (!t) return true;
    if (t.isChamberWall || t.isGateway || t.isLabel) return true;
    // spine channel
    if (spineAxis === 'vertical' && Math.abs(x - cx) <= 1) return true;
    if (spineAxis === 'horizontal' && Math.abs(y - cy) <= 1) return true;
    // label band (any row that currently holds name/term text, plus a
    // 1-tile buffer below so the first pillar row doesn't kiss the text)
    if (labelRowSet.has(y)) return true;
    if (y === maxLabelY + 1) return true;
    // gateway-adjacency buffer (2 tiles out from any gateway)
    for (let dy = -2; dy <= 2; dy++) {
      for (let dx = -2; dx <= 2; dx++) {
        const n = getTile(x + dx, y + dy);
        if (n?.isGateway) return true;
      }
    }
    return false;
  };

  const pillar = (x, y, ch='█', carryText=false) => {
    if (isForbidden(x, y)) return;
    const idx = p.inscriptions.length;
    const cid = carryText ? (cids[idx % Math.max(1, cids.length)] || '') : '';
    if (carryText) {
      p.inscriptions.push({
        x, y, chamberId: chamber.id, canonicalId: cid, idx,
        quote: null, isPillar: true,
      });
    }
    setTile(x, y, {
      ch, fg: CFG.COLORS.gold, walk: false,
      isStructure: true, isPillar: true,
      ...(carryText ? { isInscription: true, inscrIdx: idx, roomPtrIdx: G.rooms.length } : {}),
    });
  };

  // Helpers to carry chamber-axis dimension
  const longAxis = spineAxis === 'vertical' ? rh : rw;

  if (archetype === 'hypostyle') {
    // grid of columns, 4-tile spacing (3 walkable between any pair).
    for (let y = ry + 4; y < ry + rh - 4; y += 4) {
      for (let x = rx + 4; x < rx + rw - 4; x += 4) {
        pillar(x, y, '█', true);
      }
    }
  } else if (archetype === 'peristyle') {
    // ring of columns 3 tiles in from the perimeter, 4-tile spacing.
    const inset = 3;
    for (let x = rx + inset; x <= rx + rw - 1 - inset; x += 4) {
      pillar(x, ry + inset, '█', true);
      pillar(x, ry + rh - 1 - inset, '█', true);
    }
    for (let y = ry + inset + 4; y <= ry + rh - 1 - inset - 4; y += 4) {
      pillar(rx + inset,           y, '█', true);
      pillar(rx + rw - 1 - inset,  y, '█', true);
    }
  } else if (archetype === 'colonnade') {
    // two parallel rows of columns flanking the spine, loosely spaced.
    if (spineAxis === 'vertical') {
      for (let y = ry + 4; y < ry + rh - 4; y += 3) {
        pillar(cx - 4, y, '█', true);
        pillar(cx + 4, y, '█', true);
      }
    } else {
      for (let x = rx + 4; x < rx + rw - 4; x += 3) {
        pillar(x, cy - 4, '█', true);
        pillar(x, cy + 4, '█', true);
      }
    }
  } else if (archetype === 'aisled') {
    // single row of thin pillars divides nave from side aisle, each side.
    if (spineAxis === 'vertical') {
      for (let y = ry + 5; y < ry + rh - 5; y += 3) {
        pillar(cx - 5, y, '│', true);
        pillar(cx + 5, y, '│', true);
      }
    } else {
      for (let x = rx + 5; x < rx + rw - 5; x += 3) {
        pillar(x, cy - 5, '─', true);
        pillar(x, cy + 5, '─', true);
      }
    }
  } else if (archetype === 'cella') {
    // intimate: one freestanding plinth at the far end, nothing else.
    if (spineAxis === 'vertical') {
      const mx = cx, my = armDir === 'N' ? ry + 2 : ry + rh - 3;
      // spine passes through cx; plinth sits just OFF the spine axis.
      pillar(mx - 2, my, '▬', true);
      pillar(mx + 2, my, '▬', true);
    } else {
      const mx = armDir === 'W' ? rx + 2 : rx + rw - 3, my = cy;
      pillar(mx, my - 2, '▬', true);
      pillar(mx, my + 2, '▬', true);
    }
  }
}

function placeTablet(tx, ty, room, chamber, cids, quotes, chars, hallId) {
  const idx = room.inscriptions.length;
  const cid = cids[idx % Math.max(1, cids.length)] || '';
  room.inscriptions.push({
    x: tx, y: ty, chamberId: chamber.id, canonicalId: cid, idx,
    quote: quotes[idx % Math.max(1, quotes.length)] || null,
    isTablet: true,
  });
  // Tablet base: 3x3 symbol cluster
  const tabletChars = ['𓁹', '𓊹', '𓂋', '𓊽', '𓈖', '𓇋'];
  const tabletCh = tabletChars[idx % tabletChars.length];
  setTile(tx, ty, {
    ch: tabletCh, fg: CFG.COLORS.goldDim, walk: false,
    isInscription: true, inscrIdx: idx, roomPtrIdx: G.rooms.length, isTablet: true,
  });
  // Flanking chars
  setTile(tx - 1, ty, { ch: '│', fg: CFG.COLORS.wallGold, walk: false, isDecor: true });
  setTile(tx + 1, ty, { ch: '│', fg: CFG.COLORS.wallGold, walk: false, isDecor: true });
}

// ──────────────────────────────────────────────────────────────────────────────
// SCROLL PLACEMENT — the physical named-text objects
// ──────────────────────────────────────────────────────────────────────────────
// Each chamber.physical_texts entry becomes a tangible standing scroll on the
// interior grid. The placement scans the room for free floor tiles (no tablet,
// no corridor, not a wall) and drops one scroll at each candidate spot in a
// diamond pattern expanding out from the room center. This fills even small
// rooms with a felt density of objects.
function placeScrolls(room, level) {
  const chamber = room.chamber;
  const texts = chamber.physical_texts || [];
  if (!texts.length) return;

  const { x: rx, y: ry, w: rw, h: rh } = room;
  const cx = rx + Math.floor(rw / 2);
  const cy = ry + Math.floor(rh / 2);
  const glyphs = SCROLL_GLYPHS[Math.min(level, SCROLL_GLYPHS.length - 1)];

  // Candidate positions: a diamond lattice, 3 tiles apart, skipping the
  // Oracle center zone on L0 and room-center standing tablets elsewhere.
  const candidates = [];
  for (let dy = -Math.floor(rh / 2) + 4; dy <= Math.floor(rh / 2) - 4; dy++) {
    for (let dx = -Math.floor(rw / 2) + 3; dx <= Math.floor(rw / 2) - 3; dx++) {
      // Diamond lattice: pick every 3rd with a checker offset
      if ((Math.abs(dx) + Math.abs(dy)) % 3 !== 0) continue;
      if (Math.abs(dx) < 2 && Math.abs(dy) < 2) continue;  // clear center
      candidates.push({ x: cx + dx, y: cy + dy, dist: Math.abs(dx) + Math.abs(dy) });
    }
  }
  // Sort by distance from center (inner rings first, like a library's reading floor)
  candidates.sort((a, b) => a.dist - b.dist);

  let placed = 0;
  for (const pos of candidates) {
    if (placed >= texts.length) break;
    const t = getTile(pos.x, pos.y);
    if (!t || !t.walk) continue;
    if (t.isInscription || t.isTablet || t.isDecor || t.isStair || t.isOracle || t.isLabel || t.isTorch) continue;
    // Also require the two flanking tiles to be walkable (for the [ ] frame)
    const tl = getTile(pos.x - 1, pos.y);
    const tr = getTile(pos.x + 1, pos.y);
    if (!tl?.walk || !tr?.walk) continue;
    if (tl.isScroll || tr.isScroll) continue;

    const txt = texts[placed];
    const glyph = glyphs[placed % glyphs.length];
    const scrollRec = {
      x: pos.x, y: pos.y,
      chamberId: chamber.id,
      textName: txt.name,
      canonicalId: txt.canonical_id,
      period: txt.period,
      scrollIdx: placed,
    };
    room.scrolls.push(scrollRec);

    // The scroll tile — WALKABLE so the user can step onto it; interaction fires
    // automatically on proximity + enables [E] to read.
    setTile(pos.x, pos.y, {
      ch: glyph,
      fg: CFG.COLORS.greenDim,
      walk: true,
      isScroll: true,
      scrollIdx: placed,
      roomPtrIdx: G.rooms.length,
      chamberId: chamber.id,
    });
    setTile(pos.x - 1, pos.y, {
      ch: SCROLL_FRAME.left, fg: CFG.COLORS.textGhost, walk: true,
      isScrollFrame: true,
    });
    setTile(pos.x + 1, pos.y, {
      ch: SCROLL_FRAME.right, fg: CFG.COLORS.textGhost, walk: true,
      isScrollFrame: true,
    });

    placed++;
  }
}

// Place a user-generated article as a physical scroll in a chamber. Called
// when Kimi finishes composing an article from held quotes.
function placeArticleScroll(chamberId, articleId, theme) {
  const room = G.rooms.find(r => r.chamber.id === chamberId);
  if (!room) return null;
  const { x: rx, y: ry, w: rw, h: rh } = room;
  const cx = rx + Math.floor(rw / 2);
  const cy = ry + Math.floor(rh / 2);
  // Find a free tile near center that isn't already a scroll/tablet
  for (let r = 1; r < Math.max(rw, rh); r++) {
    for (let dy = -r; dy <= r; dy++) {
      for (let dx = -r; dx <= r; dx++) {
        if (Math.abs(dx) + Math.abs(dy) !== r) continue;
        const x = cx + dx, y = cy + dy;
        const t = getTile(x, y);
        if (!t?.walk) continue;
        if (t.isInscription || t.isTablet || t.isScroll || t.isDecor || t.isStair || t.isOracle || t.isLabel || t.isTorch) continue;
        const tl = getTile(x - 1, y);
        const tr = getTile(x + 1, y);
        if (!tl?.walk || !tr?.walk) continue;
        setTile(x, y, {
          ch: ARTICLE_GLYPH,
          fg: CFG.COLORS.greenBright,
          walk: true,
          isArticle: true,
          articleId,
          chamberId,
          theme,
        });
        setTile(x - 1, y, { ch: '{', fg: CFG.COLORS.greenDim, walk: true, isScrollFrame: true });
        setTile(x + 1, y, { ch: '}', fg: CFG.COLORS.greenDim, walk: true, isScrollFrame: true });
        room.scrolls.push({
          x, y, chamberId, textName: theme, canonicalId: articleId,
          period: 'Your synthesis', scrollIdx: room.scrolls.length, isArticle: true, articleId,
        });
        addMsg(`𓋹 Your article has taken form in ${room.chamber.name_en}.`, CFG.COLORS.greenBright);
        return { x, y };
      }
    }
  }
  return null;
}

// ══════════════════════════════════════════════════════════════════════════════
// CORRIDORS — architectural passages
// ══════════════════════════════════════════════════════════════════════════════
function carveCorridor(a, b, level) {
  let x = a.centerX, y = a.centerY;
  const tx = b.centerX, ty = b.centerY;

  // 3-wide passage
  function carveAt(cx, cy) {
    for (const [dx, dy] of [[0, 0], [-1, 0], [1, 0], [0, -1], [0, 1]]) {
      const nx = cx + dx, ny = cy + dy;
      const t = getTile(nx, ny);
      if (t && !t.walk && !t.isLabel && !t.isOracle && !t.isTorch && !t.isInscription && !t.isDecor) {
        // Corridor floor patterns
        const pat = ((nx + ny) % 11 === 0) ? '·'
          : ((nx * 3 + ny * 7) % 17 === 0) ? '.'
          : ' ';
        setTile(nx, ny, { ch: pat, fg: CFG.COLORS.corridor, walk: true, isCorridor: true });
      }
    }
  }

  // L-shaped path: horizontal then vertical
  const dx = tx > x ? 1 : -1;
  while (x !== tx) { carveAt(x, y); x += dx; }
  const dy = ty > y ? 1 : -1;
  while (y !== ty) { carveAt(x, y); y += dy; }
  carveAt(tx, ty);

  // Place corridor torches every 10 tiles
  let lx = a.centerX, ly = a.centerY;
  let step = 0;
  while (lx !== tx) {
    if (step % 10 === 5) {
      const t = getTile(lx, ly);
      if (t && t.isCorridor) {
        G.torches.push({ x: lx, y: ly, phase: Math.random() * Math.PI * 2, intensity: 0.4 + Math.random() * 0.3, corridor: true });
      }
    }
    lx += tx > lx ? 1 : -1;
    step++;
  }
  while (ly !== ty) {
    if (step % 10 === 5) {
      const t = getTile(lx, ly);
      if (t && t.isCorridor) {
        G.torches.push({ x: lx, y: ly, phase: Math.random() * Math.PI * 2, intensity: 0.4 + Math.random() * 0.3, corridor: true });
      }
    }
    ly += ty > ly ? 1 : -1;
    step++;
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// COURT + SPINES — L>0 cruciform layout (v5.0)
// ══════════════════════════════════════════════════════════════════════════════
function carveCourt(court, level) {
  const { x: cx, y: cy, w: cw, h: ch } = court;
  for (let x = cx; x < cx + cw; x++) {
    setTile(x, cy,          { ch: '═', fg: CFG.COLORS.wallLit, walk: false, isCourtWall: true });
    setTile(x, cy + ch - 1, { ch: '═', fg: CFG.COLORS.wallLit, walk: false, isCourtWall: true });
  }
  for (let y = cy; y < cy + ch; y++) {
    setTile(cx,          y, { ch: '║', fg: CFG.COLORS.wallLit, walk: false, isCourtWall: true });
    setTile(cx + cw - 1, y, { ch: '║', fg: CFG.COLORS.wallLit, walk: false, isCourtWall: true });
  }
  setTile(cx,          cy,          { ch: '╔', fg: CFG.COLORS.gold, walk: false, isCourtWall: true });
  setTile(cx + cw - 1, cy,          { ch: '╗', fg: CFG.COLORS.gold, walk: false, isCourtWall: true });
  setTile(cx,          cy + ch - 1, { ch: '╚', fg: CFG.COLORS.gold, walk: false, isCourtWall: true });
  setTile(cx + cw - 1, cy + ch - 1, { ch: '╝', fg: CFG.COLORS.gold, walk: false, isCourtWall: true });
  for (let y = cy + 1; y < cy + ch - 1; y++) {
    for (let x = cx + 1; x < cx + cw - 1; x++) {
      const r = Math.random();
      const tch = r > 0.95 ? '·' : r > 0.90 ? '∘' : ' ';
      setTile(x, y, { ch: tch, fg: CFG.COLORS.floorDot, walk: true, isCourt: true });
    }
  }
  // 3-wide cardinal gates
  const ccx = court.cx, ccy = court.cy;
  for (const g of [-1, 0, 1]) {
    setTile(ccx + g, cy,           { ch: ' ', fg: CFG.COLORS.floor, walk: true, isGateway: true });
    setTile(ccx + g, cy + ch - 1,  { ch: ' ', fg: CFG.COLORS.floor, walk: true, isGateway: true });
    setTile(cx,          ccy + g,  { ch: ' ', fg: CFG.COLORS.floor, walk: true, isGateway: true });
    setTile(cx + cw - 1, ccy + g,  { ch: ' ', fg: CFG.COLORS.floor, walk: true, isGateway: true });
  }
  for (const [dx, dy] of [[2, 2], [cw - 3, 2], [2, ch - 3], [cw - 3, ch - 3]]) {
    const tx = cx + dx, ty = cy + dy;
    G.torches.push({ x: tx, y: ty, phase: Math.random() * Math.PI * 2, intensity: 0.9 });
    setTile(tx, ty, { ch: '☉', fg: CFG.COLORS.torch, walk: false, isTorch: true });
  }
}

// Carve the spine of an arm and punch 3-wide gateways in each chamber the
// spine passes through. Spine threads chambers in single file: court →
// chamber 0 → chamber 1 → … → terminal wall.
function carveSpineAndGateways(dir, court, armChambers, level) {
  if (!armChambers.length) return;
  const ccx = court.cx, ccy = court.cy;
  const halfS = 2;   // SPINE_W=5
  armChambers.sort((a, b) => a.rank - b.rank);

  // Spine floor tile — lit, patterned so player feels the path
  const stamp = (x, y, kind) => {
    const t = getTile(x, y);
    if (!t) return;
    if (t.isCourtWall || t.isChamberWall) return;   // leave walls to gateway punch
    setTile(x, y, {
      ch: kind === 'center' ? '·' : ' ',
      fg: kind === 'center' ? CFG.COLORS.goldFaint : CFG.COLORS.corridor,
      walk: true, isSpine: true, spineDir: dir,
    });
  };

  // Spine runs from the court edge to the outer terminal of the arm.
  let start, end, stepSign;
  if (dir === 'N') { start = court.y - 1; end = armChambers[armChambers.length-1].y; stepSign = -1; }
  else if (dir === 'S') { start = court.y + court.h; end = armChambers[armChambers.length-1].y + armChambers[armChambers.length-1].h - 1; stepSign = 1; }
  else if (dir === 'W') { start = court.x - 1; end = armChambers[armChambers.length-1].x; stepSign = -1; }
  else { start = court.x + court.w; end = armChambers[armChambers.length-1].x + armChambers[armChambers.length-1].w - 1; stepSign = 1; }

  if (dir === 'N' || dir === 'S') {
    for (let y = start; stepSign < 0 ? y >= end : y <= end; y += stepSign) {
      for (let d = -halfS; d <= halfS; d++) {
        stamp(ccx + d, y, d === 0 ? 'center' : 'edge');
      }
    }
  } else {
    for (let x = start; stepSign < 0 ? x >= end : x <= end; x += stepSign) {
      for (let d = -halfS; d <= halfS; d++) {
        stamp(x, ccy + d, d === 0 ? 'center' : 'edge');
      }
    }
  }

  // Punch a 3-wide gateway on each wall where the spine enters/exits a chamber.
  // For N/S arms the spine is vertical, so chamber's NEAR wall (court-side) and
  // FAR wall (outer-side) each get a 3-wide opening at the spine x.
  armChambers.forEach((p, i) => punchChamberGates(p, dir, court, i === armChambers.length - 1));
}

// Open gateways in the chamber's spine-facing walls so the spine threads
// through. `isTerminal` = true for the outermost chamber on the arm; its far
// wall stays closed (arm terminates).
function punchChamberGates(p, dir, court, isTerminal) {
  const { x: rx, y: ry, w: rw, h: rh } = p;
  const open = (x, y) => {
    const t = getTile(x, y);
    if (!t) return;
    setTile(x, y, { ch: ' ', fg: CFG.COLORS.floor, walk: true, isGateway: true, chamberId: p.chamber.id });
  };
  if (dir === 'N' || dir === 'S') {
    const axisX = court.cx;
    const nearY = dir === 'N' ? (ry + rh - 1) : ry;
    const farY  = dir === 'N' ? ry : (ry + rh - 1);
    for (let dx = -1; dx <= 1; dx++) open(axisX + dx, nearY);
    if (!isTerminal) for (let dx = -1; dx <= 1; dx++) open(axisX + dx, farY);
  } else {
    const axisY = court.cy;
    const nearX = dir === 'W' ? (rx + rw - 1) : rx;
    const farX  = dir === 'W' ? rx : (rx + rw - 1);
    for (let dy = -1; dy <= 1; dy++) open(nearX, axisY + dy);
    if (!isTerminal) for (let dy = -1; dy <= 1; dy++) open(farX, axisY + dy);
  }
}

// ════════════════════════════════════════════════════════════════════════════
// MASONRY + GATES + SPINE ENCLOSURE — structural character pass (L>0)
// ════════════════════════════════════════════════════════════════════════════

// Add a ▓-block outer ring around a room shell (1 tile thick). Gateways
// puncture the inner wall AND the masonry layer. Skips tiles that are
// already walkable floor (spines, court interior).
function thickenMasonry(p) {
  const { x: rx, y: ry, w: rw, h: rh } = p;
  const mk = (x, y, cornerish) => {
    if (x < 0 || y < 0 || x >= G.worldW || y >= G.worldH) return;
    const t = getTile(x, y);
    if (!t) return;
    if (t.walk || t.isChamberWall || t.isCourtWall || t.isGateway) return;
    setTile(x, y, {
      ch: cornerish ? '▓' : '▒',
      fg: cornerish ? CFG.COLORS.wallLit : CFG.COLORS.wall,
      walk: false, isMasonry: true,
    });
  };
  // outer rectangle one tile out from the shell
  for (let x = rx - 1; x <= rx + rw; x++) {
    mk(x, ry - 1,    x === rx - 1 || x === rx + rw);
    mk(x, ry + rh,   x === rx - 1 || x === rx + rw);
  }
  for (let y = ry; y < ry + rh; y++) {
    mk(rx - 1,       y, false);
    mk(rx + rw,      y, false);
  }
}

// Any tile marked isGateway gets a glowing floor char; on the MIDDLE tile of
// each 3-tile gateway strip, stamp pylon jambs on the two flanking walls.
function styleGateways() {
  for (let y = 0; y < G.worldH; y++) {
    for (let x = 0; x < G.worldW; x++) {
      const t = G.tiles[y][x];
      if (!t?.isGateway) continue;
      setTile(x, y, {
        ch: '░', fg: CFG.COLORS.goldDim, walk: true,
        isGateway: true, chamberId: t.chamberId, isThreshold: true,
      });
    }
  }
  // Second pass: detect strip orientation + middle tile, then stamp jambs.
  for (let y = 0; y < G.worldH; y++) {
    for (let x = 0; x < G.worldW; x++) {
      const t = G.tiles[y][x];
      if (!t?.isGateway) continue;
      const left  = !!getTile(x - 1, y)?.isGateway;
      const right = !!getTile(x + 1, y)?.isGateway;
      const up    = !!getTile(x, y - 1)?.isGateway;
      const down  = !!getTile(x, y + 1)?.isGateway;
      const isHorizMid = left && right;
      const isVertMid  = up && down;
      const jamb = (jx, jy) => {
        const jt = getTile(jx, jy);
        if (!jt || jt.walk) return;
        setTile(jx, jy, { ch: '▓', fg: CFG.COLORS.gold, walk: false, isChamberWall: true, isJamb: true });
      };
      if (isHorizMid) { jamb(x, y - 1); jamb(x, y + 1); }
      if (isVertMid)  { jamb(x - 1, y); jamb(x + 1, y); }
    }
  }
}

// Enclose spine corridors between the court and the first chamber (and
// between chambers along a NS/EW arm) with masonry walls on both flanks.
// Already-enclosed segments (passing through a chamber's shell) are fine —
// the chamber walls already bound them.
function encloseSpines(court, placements) {
  for (let y = 0; y < G.worldH; y++) {
    for (let x = 0; x < G.worldW; x++) {
      const t = G.tiles[y][x];
      if (!t?.isSpine) continue;
      const dir = t.spineDir;
      // Only act on the spine's outer-edge tiles, so we stamp exactly one
      // wall on each flank. The spine is 5 wide, center+/-2.
      const cxAxis = court.cx, cyAxis = court.cy;
      if (dir === 'N' || dir === 'S') {
        const offset = x - cxAxis;
        if (offset === -2) stampSpineWall(x - 1, y);
        if (offset === +2) stampSpineWall(x + 1, y);
      } else {
        const offset = y - cyAxis;
        if (offset === -2) stampSpineWall(x, y - 1);
        if (offset === +2) stampSpineWall(x, y + 1);
      }
    }
  }
}

function stampSpineWall(x, y) {
  const t = getTile(x, y);
  if (!t) return;
  if (t.walk || t.isChamberWall || t.isCourtWall || t.isSpine || t.isGateway) return;
  setTile(x, y, { ch: '▒', fg: CFG.COLORS.wall, walk: false, isSpineWall: true });
}

// ══════════════════════════════════════════════════════════════════════════════
// STAIRS — 5×3 zone of chars, walkable, with hover tooltip
// ══════════════════════════════════════════════════════════════════════════════

// Stair zone patterns — down and up variants
// Each is a 5-wide × 3-tall ASCII art zone
const STAIR_ZONE_DOWN = [
  ['┌', '─', '▼', '─', '┐'],
  ['│', '▽', '▾', '▿', '│'],
  ['└', '─', '─', '─', '┘'],
];
const STAIR_ZONE_UP = [
  ['┌', '─', '─', '─', '┐'],
  ['│', '△', '▴', '▵', '│'],
  ['└', '─', '▲', '─', '┘'],
];

function placeStairZone(cx, cy, dir, targetLevel) {
  const pattern = dir === 'down' ? STAIR_ZONE_DOWN : STAIR_ZONE_UP;
  const color = dir === 'down' ? CFG.COLORS.stairDown : CFG.COLORS.stairUp;
  const zoneW = 5, zoneH = 3;
  const ox = cx - Math.floor(zoneW / 2);
  const oy = cy - Math.floor(zoneH / 2);

  for (let row = 0; row < zoneH; row++) {
    for (let col = 0; col < zoneW; col++) {
      const wx = ox + col, wy = oy + row;
      const t = getTile(wx, wy);
      if (!t || t.isOracle || t.isTorch || t.isLabel) continue;
      const ch = pattern[row][col];
      const isBorder = (ch === '┌' || ch === '┐' || ch === '└' || ch === '┘' || ch === '─' || ch === '│');
      setTile(wx, wy, {
        ch,
        fg: isBorder ? dimColor(color, 0.55) : color,
        walk: true,
        isStair: true,
        stairDir: dir,
        stairZoneAnchor: (row === 1 && col === 2), // center tile is the interaction anchor
        targetLevel,
      });
    }
  }
  // Register anchor at center
  return { x: cx, y: cy, targetLevel };
}

function placeStairs(placements, level) {
  if (!placements.length) return;
  // L0 (sanctum) keeps the original "stair-in-room" behavior.
  if (level === 0) {
    if (G.levels[1]?.length > 0) {
      const room = placements[0];
      const sx = room.x + room.w - 7, sy = room.centerY;
      G.stairsDown.push(placeStairZone(sx, sy, 'down', 1));
    }
    return;
  }
  // L>0: stairs live in the central court.
  const cc = G.complexCenter;
  if (!cc) return;
  // Stairs up: west side of court (anchor at cc.x - 6, cc.y)
  if (level > 0) {
    G.stairsUp.push(placeStairZone(cc.x - 6, cc.y, 'up', level - 1));
  }
  // Stairs down: east side (cc.x + 6, cc.y)
  if (level < 7 && G.levels[level + 1]?.length > 0) {
    G.stairsDown.push(placeStairZone(cc.x + 6, cc.y, 'down', level + 1));
  }
}

function placeTorches(level) {
  // Additional corridor torches based on tile scan
  for (let y = 2; y < G.worldH - 2; y++) {
    for (let x = 2; x < G.worldW - 2; x++) {
      const t = G.tiles[y]?.[x];
      if (!t?.isCorridor) continue;
      if (x % 14 !== 7 || y % 10 !== 5) continue;
      let nearWall = false;
      for (const [dx, dy] of [[-1, 0], [1, 0], [0, -1], [0, 1]]) {
        const adj = getTile(x + dx, y + dy);
        if (adj && !adj.walk) nearWall = true;
      }
      if (nearWall && !G.torches.find(t => t.x === x && t.y === y)) {
        G.torches.push({ x, y, phase: Math.random() * Math.PI * 2, intensity: 0.4 + Math.random() * 0.25, corridor: true });
      }
    }
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// PORTAL RINGS — Oracle room special effect
// ══════════════════════════════════════════════════════════════════════════════
function spawnPortalRings(cx, cy) {
  for (let i = 0; i < 3; i++) {
    G.portalRings.push({
      cx, cy,
      radius: 3 + i * 3,
      phase: (i / 3) * Math.PI * 2,
      speed: 0.008 + i * 0.003,
      opacity: 0.15 - i * 0.04,
    });
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// SIGILS — Floating ambient glyphs in corridors and chambers
// ══════════════════════════════════════════════════════════════════════════════
function spawnSigils(level, placements) {
  const sigilCount = Math.max(5, placements.length * 2);
  for (let i = 0; i < sigilCount; i++) {
    const room = placements[Math.floor(Math.random() * placements.length)];
    G.sigils.push({
      x: room.centerX + (Math.random() - 0.5) * room.w * 0.6,
      y: room.centerY + (Math.random() - 0.5) * room.h * 0.6,
      ch: HIERO_SIMPLE[Math.floor(Math.random() * HIERO_SIMPLE.length)],
      vx: (Math.random() - 0.5) * 0.0008,
      vy: (Math.random() - 0.5) * 0.0005,
      life: 0.5 + Math.random() * 0.5,
      decay: 0.00008 + Math.random() * 0.00012,
      baseAlpha: 0.04 + Math.random() * 0.08,
      phase: Math.random() * Math.PI * 2,
    });
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// ORACLE PATHFINDING
// ══════════════════════════════════════════════════════════════════════════════
function computeOraclePath() {
  G.oraclePath.clear();
  if (G.currentLevel !== 0 || G.oracleRoomIdx < 0 || !G.oraclePos) return;
  const target = G.rooms[G.oracleRoomIdx];
  if (!target || G.currentRoom === target) return;

  const adj = {};
  G.rooms.forEach(r => { adj[r.chamber.id] = []; });
  G.rooms.forEach(r => {
    (r.chamber.corridors || []).forEach(c => {
      if (adj[r.chamber.id]) adj[r.chamber.id].push(c.target_id);
    });
  });

  const startId = G.currentRoom?.chamber?.id;
  const endId = target.chamber.id;
  if (!startId || startId === endId) return;

  const visited = new Set([startId]);
  const parent = {};
  const queue = [startId];
  while (queue.length > 0) {
    const cur = queue.shift();
    if (cur === endId) break;
    for (const nid of (adj[cur] || [])) {
      if (!visited.has(nid)) { visited.add(nid); parent[nid] = cur; queue.push(nid); }
    }
  }

  const pathIds = [];
  let cur = endId;
  while (cur && cur !== startId) { pathIds.unshift(cur); cur = parent[cur]; }

  for (let i = 0; i < pathIds.length; i++) {
    const from = i === 0 ? G.currentRoom : G.rooms.find(r => r.chamber.id === pathIds[i - 1]);
    const to = G.rooms.find(r => r.chamber.id === pathIds[i]);
    if (from && to) markPathBetween(from, to);
  }
}

function markPathBetween(a, b) {
  let x = a.centerX, y = a.centerY;
  const tx = b.centerX, ty = b.centerY;
  const dx = tx > x ? 1 : tx < x ? -1 : 0;
  while (x !== tx) { G.oraclePath.add(`${x},${y}`); x += dx; }
  const dy = ty > y ? 1 : ty < y ? -1 : 0;
  while (y !== ty) { G.oraclePath.add(`${x},${y}`); y += dy; }
}

// ══════════════════════════════════════════════════════════════════════════════
// TILE HELPERS
// ══════════════════════════════════════════════════════════════════════════════
function setTile(x, y, t) {
  if (y >= 0 && y < G.worldH && x >= 0 && x < G.worldW) G.tiles[y][x] = { ...t };
}
function getTile(x, y) {
  return (y >= 0 && y < G.worldH && x >= 0 && x < G.worldW) ? G.tiles[y][x] : null;
}
function mkFloor(level) {
  const r = Math.random();
  if (r > 0.97) return { ch: '·', fg: CFG.COLORS.floorDot, walk: true };
  if (r > 0.94) return { ch: '.', fg: CFG.COLORS.floorAlt, walk: true };
  return { ch: ' ', fg: CFG.COLORS.floor, walk: true };
}
function mkWall(ch) { return { ch, fg: CFG.COLORS.wall, walk: false }; }

// ══════════════════════════════════════════════════════════════════════════════
// RENDERING
// ══════════════════════════════════════════════════════════════════════════════
function resize() {
  const w = window.innerWidth, h = window.innerHeight;
  G.canvas.width = w * G.dpr; G.canvas.height = h * G.dpr;
  G.canvas.style.width = w + 'px'; G.canvas.style.height = h + 'px';
  G.cols = Math.floor(w / CFG.TILE);
  G.rows = Math.floor(h / CFG.TILE);
}

function render() {
  const ctx = G.ctx, tile = CFG.TILE * G.dpr;

  ctx.fillStyle = CFG.COLORS.dark;
  ctx.fillRect(0, 0, G.canvas.width, G.canvas.height);

  if (!G.initialized) return;

  const viewCols = G.cols - Math.floor(CFG.PANEL_W / CFG.TILE);
  const camX = Math.round(G.player.tx) - Math.floor(viewCols / 2);
  const camY = Math.round(G.player.ty) - Math.floor(G.rows / 2);
  G.camera.x = camX; G.camera.y = camY;

  ctx.font = `${tile}px ${CFG.FONT}`;
  ctx.textBaseline = 'top';

  const px = Math.round(G.player.tx), py = Math.round(G.player.ty);
  let nearestInscr = null, nearestDist = 999;
  const time = G.frameCount * 0.016;

  // ── TORCH LIGHT MAP ──
  const torchLightMap = new Map();
  G.torches.forEach(torch => {
    const flicker = 0.85
      + Math.sin(time * 4.1 + torch.phase) * 0.09
      + Math.sin(time * 8.7 + torch.phase * 2) * 0.04
      + Math.sin(time * 17.3 + torch.phase * 3) * 0.02;
    const radius = (torch.corridor ? 4.5 : 7) * torch.intensity * flicker;
    for (let dy = -Math.ceil(radius); dy <= Math.ceil(radius); dy++) {
      for (let dx = -Math.ceil(radius); dx <= Math.ceil(radius); dx++) {
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist <= radius) {
          const key = `${torch.x + dx},${torch.y + dy}`;
          const existing = torchLightMap.get(key) || 0;
          const light = (1 - dist / radius) * flicker * torch.intensity * (torch.corridor ? 0.22 : 0.32);
          torchLightMap.set(key, Math.min(0.45, existing + light));
        }
      }
    }
  });

  // ── ORACLE AURA ──
  if (G.oraclePos && G.currentLevel === 0) {
    const auraR = 12 + Math.sin(time * 1.2) * 2;
    const oapulse = 0.4 + Math.sin(time * 0.8) * 0.15;
    for (let dy = -Math.ceil(auraR); dy <= Math.ceil(auraR); dy++) {
      for (let dx = -Math.ceil(auraR); dx <= Math.ceil(auraR); dx++) {
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist <= auraR) {
          const key = `${G.oraclePos.x + dx},${G.oraclePos.y + dy}`;
          const existing = torchLightMap.get(key) || 0;
          const light = (1 - dist / auraR) * oapulse * 0.18;
          torchLightMap.set(key, Math.min(0.5, existing + light));
        }
      }
    }
  }

  // ── TILES ──
  for (let sy = 0; sy < G.rows; sy++) {
    for (let sx = 0; sx < viewCols; sx++) {
      const wx = camX + sx, wy = camY + sy;
      if (wx < 0 || wy < 0 || wx >= G.worldW || wy >= G.worldH) continue;
      const t = G.tiles[wy][wx];
      if (!t || (t.ch === ' ' && !t.walk)) continue;

      const dist = Math.sqrt((wx - px) ** 2 + (wy - py) ** 2);
      const inFOV = dist <= CFG.FOV_RADIUS;
      const wasExplored = G.explored.has(`${wx},${wy}`);
      if (inFOV) G.explored.add(`${wx},${wy}`);
      else if (!wasExplored) continue;

      let fg = t.fg;
      const torchLight = torchLightMap.get(`${wx},${wy}`) || 0;

      if (!inFOV) {
        fg = dimColor(fg, 0.28 + torchLight * 1.4);
      } else {
        const bright = Math.max(0.55, 1.2 - (dist / CFG.FOV_RADIUS) * 0.65) + torchLight;
        fg = dimColor(fg, Math.min(1.5, bright));
      }

      // Oracle path — pulsing green guide
      if (t.isCorridor && G.oraclePath.has(`${wx},${wy}`) && inFOV) {
        const pulse = 0.45 + Math.sin(time * 2.5 + (wx + wy) * 0.4) * 0.35;
        fg = lerpColor(fg, CFG.COLORS.green, pulse * 0.7);
      }

      // Stair zone pulse — whole zone brightens together
      if (t.isStair && inFOV) {
        const pulse = 0.75 + Math.sin(time * 2.8 + (wx * 0.5)) * 0.25;
        fg = dimColor(fg, pulse + 0.5);
        if (dist < 4) {
          const nearGlow = (1 - dist / 4) * 0.4;
          fg = lerpColor(fg, t.stairDir === 'down' ? CFG.COLORS.stairDown : CFG.COLORS.stairUp, nearGlow);
        }
      }

      // Portal tiles — strong green pulse (the gateway)
      if (t.isPortal && inFOV) {
        const pulse = 0.6 + Math.sin(time * 3.5 + wx * 0.3 + wy * 0.3) * 0.4;
        fg = lerpColor(CFG.COLORS.green, CFG.COLORS.greenBright, pulse);
        if (t.portalCenter) {
          // Center is brightest
          const corePulse = 0.7 + Math.sin(time * 5) * 0.3;
          fg = dimColor(CFG.COLORS.greenBright, corePulse + 0.4);
        }
      }

      // Inscription glow near player
      if (t.isInscription && inFOV && dist < 3) {
        const glow = 0.6 + Math.sin(time * 3.5 + wx * 0.7 + wy * 0.3) * 0.4;
        fg = lerpColor(CFG.COLORS.inscr, CFG.COLORS.inscrGlow, glow * 0.8);
        if (dist < nearestDist) {
          nearestDist = dist;
          nearestInscr = { x: wx, y: wy, tile: t };
        }
      }

      // Tablet highlight — brighter
      if (t.isTablet && inFOV && dist < 4) {
        const glow = 0.5 + Math.sin(time * 2 + wx) * 0.5;
        fg = lerpColor(CFG.COLORS.goldDim, CFG.COLORS.gold, glow);
        if (dist < nearestDist) {
          nearestDist = dist;
          nearestInscr = { x: wx, y: wy, tile: t };
        }
      }

      // ── SCROLL glow — the primary felt object ──
      // Even at distance, scrolls are BRIGHT so the user sees "there is a text there"
      // and wants to walk to it. Near the player they pulse strongly.
      if (t.isScroll && inFOV) {
        // Green — clearly an interactive object, distinct from gold wall inscriptions.
        const near = Math.max(0, 1 - dist / 6);
        const glow = 0.45 + Math.sin(time * 2.0 + wx * 0.5 + wy * 0.3) * 0.3 * near;
        fg = lerpColor(CFG.COLORS.greenDim, CFG.COLORS.green, glow);
      }
      if (t.isArticle && inFOV) {
        const near = Math.max(0, 1 - dist / 6);
        const glow = 0.6 + Math.sin(time * 2.8 + wx * 0.3) * 0.4 * near;
        fg = lerpColor(CFG.COLORS.green, CFG.COLORS.greenBright, glow);
      }
      if (t.isScrollFrame && inFOV) {
        const near = Math.max(0, 1 - dist / 5);
        fg = lerpColor(fg, CFG.COLORS.gold, near * 0.4);
      }

      // Oracle pulsing glow
      if (t.isOracle && inFOV) {
        const pulse = 0.5 + Math.sin(time * 1.8) * 0.5;
        fg = lerpColor(CFG.COLORS.oracle, CFG.COLORS.oracleBright, pulse);
        if (t.oracleCore && dist < 4 && dist < nearestDist) {
          nearestDist = dist;
          nearestInscr = { x: wx, y: wy, tile: t, type: 'oracle' };
        }
      }

      // Inner border ring — subtle pulse at Oracle
      if (t.ringRadius && inFOV) {
        const pulse = 0.3 + Math.sin(time * 0.6 + t.ringRadius * 0.5) * 0.25;
        fg = dimColor(CFG.COLORS.greenDim, pulse);
      }

      // Torch animation + glow
      if (t.isTorch && inFOV) {
        const torch = G.torches.find(tr => tr.x === wx && tr.y === wy);
        if (torch) {
          const flicker = 0.65 + Math.sin(time * 5.2 + torch.phase) * 0.18 + Math.sin(time * 11.7 + torch.phase * 3) * 0.1;
          fg = dimColor(CFG.COLORS.torch, flicker + 0.2);
          const glowR = 4;
          ctx.fillStyle = `rgba(212,160,48,${0.018 * flicker})`;
          ctx.fillRect((sx - glowR) * tile, (sy - glowR) * tile, (glowR * 2 + 1) * tile, (glowR * 2 + 1) * tile);
        }
      }

      ctx.fillStyle = fg;
      ctx.fillText(t.ch, sx * tile, sy * tile);
    }
  }

  G.interactTarget = nearestInscr;

  // ── PORTAL RINGS (Oracle) ──
  renderPortalRings(ctx, camX, camY, tile, time);

  // ── HIEROGLYPH RAIN ──
  renderHieroRain(ctx, tile, time);

  // ── SIGILS ──
  // Sigils disabled — replaced with quieter ambient (none)
  // renderSigils(ctx, camX, camY, tile, time);

  // ── PLAYER ──
  renderPlayer(ctx, camX, camY, tile, time);

  // ── PARTICLES ──
  renderParticles(ctx, camX, camY, tile);

  // ── UI ──
  renderLevelBanner(ctx, tile, viewCols, time);
  renderCenterStage(ctx, tile, viewCols);
  renderInteractPrompt(ctx, tile, viewCols);
  renderStatusBar(ctx, tile);
  renderMessages(ctx, tile);
  renderSidePanel(ctx, tile);

  if (G.oracleChatActive) renderOracleChat(ctx, tile, viewCols, time);
  if (G.showMap) renderMapOverlay(ctx, tile);
  if (G.showHelp) renderHelpOverlay(ctx, tile);
  if (G.transitioning) renderTransition(ctx, tile);

  // Stair hover tooltip — always on top
  if (G.hoverStair) renderStairTooltip(ctx, tile);

  // Portal: subtle pulse on the portal tile + tooltip if hovering
  // (No floating panel — portal IS in the world)

  // ── CUSTOM CURSOR ──
  if (G.cursorX >= 0) {
    ctx.fillStyle = CFG.COLORS.gold;
    ctx.font = `${tile}px ${CFG.FONT}`;
    ctx.fillText('+', G.cursorX * G.dpr - tile / 2, G.cursorY * G.dpr - tile / 2);
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// PORTAL RINGS — Oracle sanctum concentric pulses
// ══════════════════════════════════════════════════════════════════════════════
function renderPortalRings(ctx, camX, camY, tile, time) {
  if (G.currentLevel !== 0 || !G.oraclePos) return;

  G.portalRings.forEach(ring => {
    ring.phase += ring.speed;
    const r = ring.radius * tile;
    const sx = (G.oraclePos.x - camX) * tile + tile / 2;
    const sy = (G.oraclePos.y - camY) * tile + tile / 2;
    const alpha = ring.opacity * (0.5 + Math.sin(ring.phase) * 0.5);

    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.strokeStyle = CFG.COLORS.green;
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 6]);
    ctx.lineDashOffset = ring.phase * 10;
    ctx.beginPath();
    ctx.ellipse(sx, sy, r, r * 0.55, ring.phase * 0.1, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.restore();
  });
}

// ══════════════════════════════════════════════════════════════════════════════
// HIEROGLYPH RAIN — Digital-rain of ancient symbols
// ══════════════════════════════════════════════════════════════════════════════
function updateHieroRain(dt) {
  if (Math.random() < 0.005 && G.hieroRain.length < 8) {
    const viewCols = G.cols - Math.floor(CFG.PANEL_W / CFG.TILE);
    G.hieroRain.push({
      x: Math.random() * viewCols,
      y: -2,
      speed: 0.0006 + Math.random() * 0.001,
      ch: HIERO_CHARS[Math.floor(Math.random() * HIERO_CHARS.length)],
      alpha: 0.025 + Math.random() * 0.05,
      size: 0.55 + Math.random() * 0.4,
      col: Math.random() > 0.7 ? CFG.COLORS.gold : CFG.COLORS.goldFaint,
    });
  }
  G.hieroRain = G.hieroRain.filter(h => {
    h.y += h.speed * 16;
    h.alpha *= 0.9998;
    return h.y < G.rows + 2 && h.alpha > 0.008;
  });
}

function renderHieroRain(ctx, tile, time) {
  G.hieroRain.forEach(h => {
    ctx.globalAlpha = h.alpha * (0.8 + Math.sin(time * 3 + h.x) * 0.2);
    ctx.font = `${Math.floor(tile * h.size)}px ${CFG.HIERO_FONT}`;
    ctx.fillStyle = h.col;
    ctx.fillText(h.ch, h.x * tile, h.y * tile);
  });
  ctx.globalAlpha = 1;
  ctx.font = `${tile}px ${CFG.FONT}`;
}

// ══════════════════════════════════════════════════════════════════════════════
// SIGILS — floating glyphs in chambers
// ══════════════════════════════════════════════════════════════════════════════
function updateSigils(dt) {
  G.sigils = G.sigils.filter(s => {
    s.x += s.vx * dt;
    s.y += s.vy * dt;
    s.life -= s.decay * dt;
    s.phase += 0.001 * dt;
    return s.life > 0;
  });
}

function renderSigils(ctx, camX, camY, tile, time) {
  const px = Math.round(G.player.tx), py = Math.round(G.player.ty);
  G.sigils.forEach(s => {
    const dist = Math.sqrt((s.x - px) ** 2 + (s.y - py) ** 2);
    if (dist > CFG.FOV_RADIUS * 1.2) return;
    const sx = (s.x - camX) * tile;
    const sy = (s.y - camY) * tile;
    const alpha = s.life * s.baseAlpha * (0.6 + Math.sin(s.phase * 5) * 0.4);
    ctx.globalAlpha = alpha;
    ctx.font = `${Math.floor(tile * 0.9)}px ${CFG.HIERO_FONT}`;
    ctx.fillStyle = CFG.COLORS.goldDim;
    ctx.fillText(s.ch, sx, sy);
  });
  ctx.globalAlpha = 1;
  ctx.font = `${tile}px ${CFG.FONT}`;
}

// ══════════════════════════════════════════════════════════════════════════════
// PLAYER
// ══════════════════════════════════════════════════════════════════════════════
function renderPlayer(ctx, camX, camY, tile, time) {
  const psx = (G.player.tx - camX) * tile;
  const psy = (G.player.ty - camY) * tile;

  // Player glow
  const glowAlpha = 0.04 + Math.sin(time * 2) * 0.015;
  ctx.fillStyle = `rgba(232,184,64,${glowAlpha})`;
  ctx.beginPath();
  ctx.arc(psx + tile / 2, psy + tile / 2, tile * 3.5, 0, Math.PI * 2);
  ctx.fill();

  // Player body
  ctx.fillStyle = CFG.COLORS.player;
  ctx.font = `bold ${tile}px ${CFG.FONT}`;
  ctx.fillText('@', psx, psy);
  ctx.font = `${tile}px ${CFG.FONT}`;
}

// ══════════════════════════════════════════════════════════════════════════════
// PARTICLES
// ══════════════════════════════════════════════════════════════════════════════
function updateParticles(dt) {
  if (Math.random() < 0.012 && G.particles.length < 18) {
    G.particles.push({
      x: G.player.tx + (Math.random() - 0.5) * CFG.FOV_RADIUS * 1.5,
      y: G.player.ty + (Math.random() - 0.5) * CFG.FOV_RADIUS * 1.5,
      vx: (Math.random() - 0.5) * 0.0025,
      vy: -Math.random() * 0.002 - 0.0003,
      life: 1, decay: 0.00018 + Math.random() * 0.0003,
      ch: '·',
      isHiero: false,
    });
  }
  G.particles = G.particles.filter(p => {
    p.x += p.vx * dt; p.y += p.vy * dt; p.life -= p.decay * dt;
    return p.life > 0;
  });
}

function renderParticles(ctx, camX, camY, tile) {
  G.particles.forEach(p => {
    const sx = (p.x - camX) * tile, sy = (p.y - camY) * tile;
    if (sx < -tile || sy < -tile || sx > G.canvas.width || sy > G.canvas.height) return;
    ctx.globalAlpha = p.life * (p.isHiero ? 0.1 : 0.18);
    ctx.fillStyle = p.isHiero ? CFG.COLORS.goldFaint : CFG.COLORS.textGhost;
    if (p.isHiero) {
      ctx.font = `${Math.floor(tile * 0.75)}px ${CFG.HIERO_FONT}`;
      ctx.fillText(p.ch, sx, sy);
      ctx.font = `${tile}px ${CFG.FONT}`;
    } else {
      ctx.fillText(p.ch, sx, sy);
    }
  });
  ctx.globalAlpha = 1;
}

// ══════════════════════════════════════════════════════════════════════════════
// LEVEL BANNER — top-left indicator with level pips
// ══════════════════════════════════════════════════════════════════════════════
function renderLevelBanner(ctx, tile, viewCols, time) {
  const fs = Math.floor(tile * 0.62);
  const x = tile * 0.5, y = tile * 0.3;
  const bgW = fs * 50;
  const bgH = fs * 2.8;

  ctx.fillStyle = 'rgba(5,5,4,0.88)';
  roundRect(ctx, x - 4, y - 2, bgW, bgH, 3); ctx.fill();
  ctx.strokeStyle = CFG.COLORS.panelBorder; ctx.lineWidth = 1;
  roundRect(ctx, x - 4, y - 2, bgW, bgH, 3); ctx.stroke();

  ctx.font = `${fs}px ${CFG.FONT}`;
  let lx = x;

  // Level pips
  for (let i = 0; i <= 7; i++) {
    const active = i === G.currentLevel;
    ctx.fillStyle = active ? CFG.COLORS.levelColors[i] : CFG.COLORS.textGhost;
    ctx.fillText(active ? '■' : '□', lx, y); lx += fs + 3;
  }
  lx += 6;

  // Level name + subtitle
  const lvlColor = CFG.COLORS.levelColors[G.currentLevel] || CFG.COLORS.gold;
  const pulse = 0.88 + Math.sin(time * 1.1) * 0.12;
  ctx.fillStyle = dimColor(lvlColor, pulse);
  ctx.fillText(`L${G.currentLevel} · ${LEVEL_NAMES[G.currentLevel]}`, lx, y);

  // Subtitle on second line
  const fs2 = Math.floor(fs * 0.75);
  ctx.font = `${fs2}px ${CFG.FONT}`;
  ctx.fillStyle = CFG.COLORS.textFaint;
  ctx.fillText(LEVEL_SUBTITLES[G.currentLevel], lx, y + fs + 2);
}

// ══════════════════════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════════════════════
// CENTER STAGE — unified centered panel for guide text AND reading text.
// Single hierarchy. Single timeout. One source of truth.
//
// Modes:
//   'guide'   — chamber entry hint, 5s timeout, gold tone, smaller
//   'reading' — full passage from inscription/tablet, 15s timeout, larger,
//               with title (text name), body (translation), source line
// ══════════════════════════════════════════════════════════════════════════════
function showCenterStage({ mode, title, body, source, duration }) {
  G.center = {
    mode,
    title: title || '',
    body: body || '',
    source: source || '',
    startTime: performance.now(),
    duration: duration || (mode === 'reading' ? 15000 : 5000),
    fadeIn: 250,
    fadeOut: 800,
  };
}

function clearCenterStage() {
  G.center = null;
}

function updateCenterStage(now) {
  if (!G.center) return;
  const elapsed = now - G.center.startTime;
  if (elapsed >= G.center.duration + G.center.fadeOut) {
    G.center = null;
  }
}

function renderCenterStage(ctx, tile, viewCols) {
  const c = G.center;
  if (!c) return;

  const now = performance.now();
  const elapsed = now - c.startTime;

  // Alpha curve: fade in → hold → fade out
  let alpha;
  if (elapsed < c.fadeIn) alpha = elapsed / c.fadeIn;
  else if (elapsed < c.duration) alpha = 1;
  else alpha = Math.max(0, 1 - (elapsed - c.duration) / c.fadeOut);
  if (alpha <= 0) return;

  const isReading = c.mode === 'reading';

  // Sizes per mode
  const titleFs = Math.floor(tile * (isReading ? 0.8 : 0.7));
  const bodyFs  = Math.floor(tile * (isReading ? 0.78 : 0.66));
  const sourceFs = Math.floor(tile * 0.55);
  const lineH   = bodyFs + 6;

  // Width: reading is wider for full passages
  const maxW = Math.floor(viewCols * tile * (isReading ? 0.62 : 0.5));

  // Wrap body
  ctx.font = `${bodyFs}px ${isReading ? "EB Garamond, serif" : CFG.FONT}`;
  const bodyLines = wrapText(ctx, c.body, maxW);
  const bodyLineCount = isReading ? bodyLines.length : Math.min(4, bodyLines.length);

  // Compute total height
  const titleHeight = c.title ? titleFs + 14 : 0;
  const bodyHeight = bodyLineCount * lineH;
  const sourceHeight = c.source ? sourceFs + 10 : 0;
  const padding = 24;
  const totalH = titleHeight + bodyHeight + sourceHeight + padding * 2;

  // Position: vertically biased toward upper-middle
  const bx = Math.floor((viewCols * tile - maxW - padding * 2) / 2);
  const by = isReading
    ? Math.floor(G.canvas.height * 0.18)
    : Math.floor(G.canvas.height * 0.22);
  const bw = maxW + padding * 2;

  // Background
  ctx.save();
  ctx.globalAlpha = alpha;

  // Outer glow halo
  ctx.fillStyle = isReading
    ? `rgba(196,146,42,${0.08 * alpha})`
    : `rgba(143,188,159,${0.05 * alpha})`;
  for (let g = 6; g > 0; g--) {
    roundRect(ctx, bx - g * 2, by - g * 2, bw + g * 4, totalH + g * 4, 6 + g);
    ctx.fill();
  }

  // Box
  ctx.fillStyle = 'rgba(8,7,5,0.96)';
  ctx.strokeStyle = isReading ? CFG.COLORS.gold : CFG.COLORS.goldDim;
  ctx.lineWidth = isReading ? 2 : 1;
  roundRect(ctx, bx, by, bw, totalH, 6);
  ctx.fill(); ctx.stroke();

  // Inner accent line
  if (isReading) {
    ctx.strokeStyle = CFG.COLORS.goldFaint;
    ctx.lineWidth = 1;
    roundRect(ctx, bx + 4, by + 4, bw - 8, totalH - 8, 4);
    ctx.stroke();
  }

  // Decorative corner glyphs
  const cornerGlyph = '𓊹';
  const cornerFs = Math.floor(tile * 0.7);
  ctx.font = `${cornerFs}px ${CFG.HIERO_FONT}`;
  ctx.fillStyle = isReading ? CFG.COLORS.goldDim : CFG.COLORS.greenDim;
  ctx.textBaseline = 'top';
  ctx.fillText(cornerGlyph, bx + 8, by + 6);
  const cw = ctx.measureText(cornerGlyph).width;
  ctx.fillText(cornerGlyph, bx + bw - cw - 8, by + 6);

  let ty = by + padding;

  // Title (text name or chamber name)
  if (c.title) {
    ctx.font = `${titleFs}px ${CFG.FONT}`;
    ctx.fillStyle = isReading ? CFG.COLORS.goldBright : CFG.COLORS.gold;
    const tw = ctx.measureText(c.title).width;
    ctx.fillText(c.title, bx + (bw - tw) / 2, ty);
    ty += titleFs + 14;

    // Title underline
    ctx.strokeStyle = isReading ? CFG.COLORS.gold : CFG.COLORS.goldFaint;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(bx + bw * 0.25, ty - 4);
    ctx.lineTo(bx + bw * 0.75, ty - 4);
    ctx.stroke();
    ty += 4;
  }

  // Body
  ctx.font = `${bodyFs}px ${isReading ? "EB Garamond, serif" : CFG.FONT}`;
  ctx.fillStyle = isReading ? CFG.COLORS.text : CFG.COLORS.text;
  bodyLines.slice(0, bodyLineCount).forEach(line => {
    const tw = ctx.measureText(line).width;
    if (isReading) {
      // Reading text is left-aligned for readability
      ctx.fillText(line, bx + padding, ty);
    } else {
      // Guide text is centered
      ctx.fillText(line, bx + (bw - tw) / 2, ty);
    }
    ty += lineH;
  });

  // Source citation (reading only)
  if (c.source) {
    ty += 6;
    ctx.font = `${sourceFs}px ${CFG.FONT}`;
    ctx.fillStyle = CFG.COLORS.goldDim;
    const sw = ctx.measureText(c.source).width;
    ctx.fillText(c.source, bx + (bw - sw) / 2, ty);
  }

  // Bottom timer bar (reading mode — visible countdown)
  if (isReading && elapsed < c.duration) {
    const remaining = 1 - (elapsed / c.duration);
    const barW = (bw - 40) * remaining;
    ctx.fillStyle = `rgba(196,146,42,${0.5 * alpha})`;
    ctx.fillRect(bx + 20, by + totalH - 8, barW, 2);
  }

  ctx.restore();
  ctx.font = `${tile}px ${CFG.FONT}`;
}

// ══════════════════════════════════════════════════════════════════════════════
// PORTAL OVERLAY — agentic gateway opened by Oracle
// ══════════════════════════════════════════════════════════════════════════════
function renderPortalOverlay(ctx, tile, viewCols, time) {
  if (!G.portalOpen || !G.portalChamberId) return;
  const ch = G.chambersById[G.portalChamberId];
  if (!ch) return;

  const viewW = viewCols * tile;
  const viewH = G.canvas.height;
  const fs = Math.floor(tile * 0.65);

  // Dim edge vignette
  const pulse = 0.5 + Math.sin(time * 1.3) * 0.3;
  ctx.fillStyle = `rgba(0,30,20,${0.08 * pulse})`;
  ctx.fillRect(0, 0, viewW, viewH);

  // Portal frame — bottom-right of viewport
  const pw = Math.floor(tile * 22);
  const ph = Math.floor(tile * 14);
  const ppx = viewW - pw - tile * 2;
  const ppy = viewH - ph - tile * 3;

  // Animated border
  ctx.save();
  ctx.globalAlpha = 0.88;
  ctx.fillStyle = 'rgba(8,20,14,0.97)';
  ctx.strokeStyle = CFG.COLORS.greenBright;
  ctx.lineWidth = 2;
  ctx.setLineDash([6, 4]);
  ctx.lineDashOffset = -(time * 18 % 20);
  roundRect(ctx, ppx, ppy, pw, ph, 6);
  ctx.fill(); ctx.stroke();
  ctx.setLineDash([]);

  // Inner glow ring
  ctx.strokeStyle = dimColor(CFG.COLORS.green, pulse);
  ctx.lineWidth = 1;
  roundRect(ctx, ppx + 4, ppy + 4, pw - 8, ph - 8, 4);
  ctx.stroke();
  ctx.restore();

  // Header
  ctx.font = `${Math.floor(fs * 0.65)}px ${CFG.FONT}`;
  ctx.fillStyle = CFG.COLORS.greenDim;
  ctx.fillText('𓊹 ORACLE PORTAL', ppx + 10, ppy + 8);

  ctx.font = `${fs}px ${CFG.FONT}`;
  ctx.fillStyle = CFG.COLORS.greenBright;
  ctx.fillText(ch.name_en, ppx + 10, ppy + fs + 12);

  ctx.font = `${Math.floor(fs * 0.75)}px ${CFG.FONT}`;
  ctx.fillStyle = CFG.COLORS.textDim;
  ctx.fillText(`L${ch.level} · ${(ch.hall || '').toUpperCase()} · ${ch.text_count || 0} texts`, ppx + 10, ppy + fs * 2 + 14);

  // Named texts
  const labels = ch.text_labels || [];
  ctx.font = `${Math.floor(fs * 0.68)}px ${CFG.FONT}`;
  ctx.fillStyle = CFG.COLORS.textFaint;
  labels.slice(0, 3).forEach((l, i) => {
    ctx.fillText(`· ${l}`, ppx + 14, ppy + fs * 3 + 16 + i * (Math.floor(fs * 0.68) + 4));
  });

  // Passage preview — cycles through loaded passages
  const passages = G.roomPassages[G.portalChamberId];
  if (passages?.length) {
    const p = passages[Math.floor(time * 0.3) % passages.length];
    const quote = p?.translation?.substring(0, 120);
    if (quote) {
      ctx.font = `${Math.floor(fs * 0.7)}px EB Garamond, serif`;
      ctx.fillStyle = CFG.COLORS.text;
      const qlines = wrapText(ctx, `"${quote}…"`, pw - 24);
      qlines.slice(0, 3).forEach((l, i) => {
        ctx.fillText(l, ppx + 10, ppy + ph - (3 - i) * (Math.floor(fs * 0.72) + 3) - 28);
      });
    }
  }

  // Footer
  ctx.font = `${Math.floor(fs * 0.58)}px ${CFG.FONT}`;
  ctx.fillStyle = CFG.COLORS.green;
  ctx.fillText('[M] see on map  [SPACE] SPEAK  [ESC] close portal', ppx + 10, ppy + ph - 10);

  // Animated hieroglyph orbit
  ctx.font = `${Math.floor(tile * 0.9)}px ${CFG.HIERO_FONT}`;
  for (let i = 0; i < 6; i++) {
    const angle = (i / 6) * Math.PI * 2 + time * 0.4;
    const rx = ppx + pw / 2 + Math.cos(angle) * (pw * 0.52);
    const ry = ppy + ph / 2 + Math.sin(angle) * (ph * 0.52);
    const glyph = HIERO_SIMPLE[i % HIERO_SIMPLE.length];
    ctx.globalAlpha = 0.18 + Math.sin(time * 2 + i) * 0.1;
    ctx.fillStyle = CFG.COLORS.green;
    ctx.fillText(glyph, rx, ry);
  }
  ctx.globalAlpha = 1;
  ctx.font = `${tile}px ${CFG.FONT}`;
}


// ══════════════════════════════════════════════════════════════════════════════
// STAIR HOVER TOOLTIP
// ══════════════════════════════════════════════════════════════════════════════
function renderStairTooltip(ctx, tile) {
  const h = G.hoverStair;
  if (!h) return;
  const dir = h.dir;
  const lvl = h.targetLevel;
  const lvlName = LEVEL_NAMES[lvl] || `Level ${lvl}`;
  const lvlSub  = LEVEL_SUBTITLES[lvl] || '';
  const color   = dir === 'down' ? CFG.COLORS.stairDown : CFG.COLORS.stairUp;
  const arrow   = dir === 'down' ? '▼' : '▲';
  const verb    = dir === 'down' ? 'DESCEND' : 'ASCEND';

  const line1 = `${arrow} ${verb} TO L${lvl}: ${lvlName}`;
  const line2 = lvlSub;
  const line3 = 'Walk onto zone · Press [E] to travel';

  const fs = Math.floor(tile * 0.62);
  ctx.font = `${fs}px ${CFG.FONT}`;
  const w1 = ctx.measureText(line1).width;
  const w2 = ctx.measureText(line2).width;
  const w3 = ctx.measureText(line3).width;
  const boxW = Math.max(w1, w2, w3) + 28;
  const boxH = fs * 3 + 24;

  // Position tooltip above cursor, flip down if near top
  const sx = h.screenX * G.dpr;
  const sy = h.screenY * G.dpr;
  let bx = sx - boxW / 2;
  let by = sy - boxH - tile * 0.8;
  if (by < 4) by = sy + tile * 1.5;
  bx = Math.max(4, Math.min(G.canvas.width - boxW - 4, bx));

  // Box
  ctx.fillStyle = 'rgba(6,6,5,0.96)';
  ctx.strokeStyle = color; ctx.lineWidth = 1;
  roundRect(ctx, bx, by, boxW, boxH, 4);
  ctx.fill(); ctx.stroke();

  // Accent top bar
  ctx.fillStyle = dimColor(color, 0.25);
  roundRect(ctx, bx, by, boxW, fs + 10, 4);
  ctx.fill();

  // Text
  ctx.textBaseline = 'top';
  ctx.fillStyle = color;
  ctx.font = `${fs}px ${CFG.FONT}`;
  ctx.fillText(line1, bx + 14, by + 6);

  ctx.fillStyle = CFG.COLORS.textDim;
  ctx.font = `${Math.floor(fs * 0.85)}px ${CFG.FONT}`;
  ctx.fillText(line2, bx + 14, by + fs + 12);

  ctx.fillStyle = CFG.COLORS.textGhost;
  ctx.font = `${Math.floor(fs * 0.75)}px ${CFG.FONT}`;
  ctx.fillText(line3, bx + 14, by + fs * 2 + 14);

  ctx.font = `${tile}px ${CFG.FONT}`; // restore
}


function renderInteractPrompt(ctx, tile, viewCols) {
  if (!G.interactTarget || G.oracleChatActive) return;
  const fs = Math.floor(tile * 0.62);
  ctx.font = `${fs}px ${CFG.FONT}`;

  let text = '';
  let color = CFG.COLORS.gold;
  if (G.interactTarget.type === 'scroll' && G.inspectedScroll) {
    const sc = G.inspectedScroll;
    const shortName = sc.textName.length > 42 ? sc.textName.slice(0, 40) + '…' : sc.textName;
    text = `𓏛  ${shortName}  ·  [E] read  ·  [SPACE] hear Kimi`;
    color = CFG.COLORS.goldBright;
  } else if (G.interactTarget.type === 'article' && G.inspectedScroll) {
    text = `𓋹 ${G.inspectedScroll.textName} — your article · [E] open`;
    color = CFG.COLORS.greenBright;
  } else if (G.interactTarget.type === 'oracle') {
    text = '𓁟 [E] Speak with the Oracle · Hermes-4-70B awaits';
    color = CFG.COLORS.greenBright;
  } else if (G.interactTarget.tile?.isPortal) {
    const ch = G.chambersById[G.interactTarget.tile.portalChamberId];
    text = ch ? `𓊹 PORTAL → ${ch.name_en} (L${ch.level}) · step on ▣ to enter`
              : `𓊹 PORTAL · step on ▣ to enter`;
    color = CFG.COLORS.greenBright;
  } else if (G.interactTarget.tile?.isStair) {
    const dir = G.interactTarget.tile.stairDir;
    const lvl = G.interactTarget.tile.targetLevel;
    text = dir === 'down'
      ? `▼ Step onto the stairwell · ${LEVEL_NAMES[lvl] || '?'}`
      : `▲ Step onto the stairwell · ${LEVEL_NAMES[lvl] || '?'}`;
    color = dir === 'down' ? CFG.COLORS.stairDown : CFG.COLORS.stairUp;
  } else if (G.interactTarget.tile?.isTablet) {
    text = '𓊹 [E] Read the standing tablet · [SPACE] Kimi synthesis';
  } else {
    text = '𓂋 [E] Read inscription · [SPACE] Invoke Kimi K2.5';
  }

  const tw = ctx.measureText(text).width;
  const x = (viewCols * tile - tw) / 2;
  const y = G.canvas.height - tile * 3.2;

  ctx.fillStyle = 'rgba(5,5,4,0.88)';
  ctx.strokeStyle = dimColor(color, 0.5); ctx.lineWidth = 1;
  roundRect(ctx, x - 14, y - 6, tw + 28, fs + 12, 4);
  ctx.fill(); ctx.stroke();
  ctx.fillStyle = color;
  ctx.fillText(text, x, y);
}

// ══════════════════════════════════════════════════════════════════════════════
// SIDE PANEL
// ══════════════════════════════════════════════════════════════════════════════
function renderSidePanel(ctx, tile) {
  const pw = CFG.PANEL_W * G.dpr;
  const px = G.canvas.width - pw;

  ctx.fillStyle = CFG.COLORS.panelBg;
  ctx.fillRect(px, 0, pw, G.canvas.height);

  ctx.strokeStyle = CFG.COLORS.panelBorder; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(px, 0); ctx.lineTo(px, G.canvas.height); ctx.stroke();
  ctx.strokeStyle = CFG.COLORS.panelBorderLit;
  ctx.beginPath(); ctx.moveTo(px + 1, 0); ctx.lineTo(px + 1, G.canvas.height); ctx.stroke();

  const margin = 10 * G.dpr;
  let y = margin;

  // Panel header
  const titleFs = Math.floor(tile * 0.62);
  ctx.font = `${titleFs}px ${CFG.FONT}`;
  ctx.fillStyle = CFG.COLORS.goldDim;
  ctx.fillText('AEGYPTUS · THE LABYRINTH', px + margin, y); y += titleFs + 3;
  ctx.font = `${Math.floor(tile * 0.48)}px ${CFG.FONT}`;
  ctx.fillStyle = CFG.COLORS.textGhost;
  ctx.fillText('77,683 texts · 8 levels · 41 halls · 79 chambers', px + margin, y);
  y += titleFs + 8;

  // Divider
  ctx.strokeStyle = CFG.COLORS.panelBorder;
  ctx.beginPath(); ctx.moveTo(px + margin, y); ctx.lineTo(px + pw - margin, y); ctx.stroke();
  y += 6;

  // Minimap
  y = renderMinimap(ctx, px + margin, y, pw - margin * 2);
  y += margin;

  // Divider
  ctx.strokeStyle = CFG.COLORS.panelBorder;
  ctx.beginPath(); ctx.moveTo(px + margin, y); ctx.lineTo(px + pw - margin, y); ctx.stroke();
  y += 6;

  // Wayfinder
  y = renderWayfinder(ctx, px + margin, y, pw - margin * 2);

  // Inscription panel
  if (G.inspectedInscr) {
    ctx.strokeStyle = CFG.COLORS.panelBorder;
    ctx.beginPath(); ctx.moveTo(px + margin, y); ctx.lineTo(px + pw - margin, y); ctx.stroke();
    y += 4;
    renderInscriptionPanel(ctx, px + margin, y + 4, pw - margin * 2);
  }
}

function renderMinimap(ctx, x, y, w) {
  const h = CFG.MINIMAP_H * G.dpr;
  const time = G.frameCount * 0.016;

  ctx.strokeStyle = CFG.COLORS.panelBorder;
  ctx.lineWidth = 1;
  ctx.strokeRect(x, y, w, h);

  if (!G.rooms.length) return y + h;

  const scaleX = w / G.worldW;
  const scaleY = h / G.worldH;
  const scale = Math.min(scaleX, scaleY) * 0.86;
  const ox = x + (w - G.worldW * scale) / 2;
  const oy = y + (h - G.worldH * scale) / 2;

  // Draw corridors on minimap
  for (let wy = 0; wy < G.worldH; wy += 2) {
    for (let wx = 0; wx < G.worldW; wx += 2) {
      const t = G.tiles[wy]?.[wx];
      if (t?.isCorridor && G.explored.has(`${wx},${wy}`)) {
        ctx.fillStyle = 'rgba(40,36,32,0.8)';
        ctx.fillRect(ox + wx * scale, oy + wy * scale, scale * 2, scale * 2);
      }
    }
  }

  // Draw rooms
  G.rooms.forEach((r, i) => {
    const rx = ox + r.x * scale, ry = oy + r.y * scale;
    const rw = r.w * scale, rh = r.h * scale;
    const isCurrent = G.currentRoom === r;
    const isOracle = i === G.oracleRoomIdx;
    const hallColor = CFG.COLORS.hallColors[r.hallId] || CFG.COLORS.wall;

    // Explored check
    const explored = G.explored.has(`${r.centerX},${r.centerY}`);

    if (!explored && !isCurrent) {
      ctx.fillStyle = 'rgba(20,18,16,0.3)';
      ctx.fillRect(rx, ry, rw, rh);
      ctx.strokeStyle = CFG.COLORS.textGhost; ctx.lineWidth = 0.5;
      ctx.strokeRect(rx, ry, rw, rh);
      return;
    }

    ctx.fillStyle = isCurrent ? 'rgba(196,146,42,0.1)' : isOracle ? 'rgba(143,188,159,0.06)' : 'rgba(42,36,32,0.35)';
    ctx.fillRect(rx, ry, rw, rh);

    const bColor = isCurrent ? CFG.COLORS.gold : isOracle ? CFG.COLORS.green : hallColor;
    ctx.strokeStyle = bColor;
    ctx.lineWidth = isCurrent ? 1.5 : 0.8;
    ctx.strokeRect(rx, ry, rw, rh);

    // Chamber label
    const labelFs = Math.max(5, Math.floor(scale * 6));
    ctx.font = `${labelFs}px ${CFG.FONT}`;
    ctx.fillStyle = isCurrent ? CFG.COLORS.gold : isOracle ? CFG.COLORS.green : CFG.COLORS.textFaint;
    ctx.fillText(r.chamber.id.slice(0, 4).toUpperCase(), rx + 2, ry + rh / 2);
  });

  // Oracle path on minimap
  if (G.currentLevel === 0) {
    ctx.fillStyle = CFG.COLORS.greenDim;
    G.oraclePath.forEach(key => {
      const [kx, ky] = key.split(',').map(Number);
      if (G.explored.has(key)) {
        ctx.fillRect(ox + kx * scale, oy + ky * scale, Math.max(1.5, scale), Math.max(1.5, scale));
      }
    });
    // Oracle dot pulse
    if (G.oraclePos) {
      const pulse = 0.6 + Math.sin(time * 1.5) * 0.4;
      ctx.fillStyle = dimColor(CFG.COLORS.oracle, pulse + 0.5);
      ctx.beginPath();
      ctx.arc(ox + G.oraclePos.x * scale, oy + G.oraclePos.y * scale, Math.max(3, scale * 2.5), 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // Stairs
  G.stairsDown.forEach(s => {
    ctx.fillStyle = CFG.COLORS.stairDown;
    ctx.fillRect(ox + s.x * scale - 2, oy + s.y * scale - 2, 5, 5);
  });
  G.stairsUp.forEach(s => {
    ctx.fillStyle = CFG.COLORS.stairUp;
    ctx.fillRect(ox + s.x * scale - 2, oy + s.y * scale - 2, 5, 5);
  });

  // Player
  ctx.fillStyle = CFG.COLORS.player;
  ctx.beginPath();
  ctx.arc(ox + G.player.tx * scale, oy + G.player.ty * scale, Math.max(2.5, scale * 2), 0, Math.PI * 2);
  ctx.fill();

  return y + h;
}

function renderWayfinder(ctx, x, y, w) {
  const fs = Math.floor(13 * G.dpr);
  ctx.font = `${fs}px ${CFG.FONT}`;
  const lineH = fs + 4;
  let cy = y;

  ctx.fillStyle = CFG.COLORS.goldDim;
  ctx.fillText('WAYFINDER', x, cy); cy += lineH + 3;

  if (G.currentRoom) {
    const ch = G.currentRoom.chamber;
    const hallColor = CFG.COLORS.hallColors[G.currentRoom.hallId] || CFG.COLORS.gold;

    // Chamber name — large
    ctx.fillStyle = CFG.COLORS.gold;
    ctx.font = `${Math.floor(fs * 1.2)}px ${CFG.FONT}`;
    ctx.fillText(ch.name_en || ch.id, x, cy); cy += Math.floor(fs * 1.2) + 5;

    // Hall + level
    ctx.font = `${fs}px ${CFG.FONT}`;
    ctx.fillStyle = hallColor;
    ctx.fillText(`HALL OF ${(ch.hall || '—').toUpperCase()} · L${ch.level}`, x, cy); cy += lineH;

    ctx.fillStyle = CFG.COLORS.textDim;
    ctx.fillText(`${ch.text_count || 0} texts · ${ch.period_range || ''}`, x, cy); cy += lineH;

    // Description
    if (ch.description) {
      ctx.fillStyle = CFG.COLORS.textFaint;
      ctx.font = `${Math.floor(fs * 0.92)}px ${CFG.FONT}`;
      const descLines = wrapText(ctx, ch.description, w);
      descLines.slice(0, 3).forEach(l => { ctx.fillText(l, x, cy); cy += lineH; });
      ctx.font = `${fs}px ${CFG.FONT}`;
    }
    cy += 4;

    // Corpus text labels for this chamber
    if (ch.text_labels?.length) {
      ctx.fillStyle = CFG.COLORS.goldDim;
      ctx.fillText('TEXTS IN THIS CHAMBER:', x, cy); cy += lineH;
      ch.text_labels.slice(0, 4).forEach(label => {
        ctx.fillStyle = CFG.COLORS.textFaint;
        ctx.fillText(`· ${label}`, x + 6, cy); cy += lineH;
      });
      cy += 4;
    }

    // Corridors
    ctx.fillStyle = CFG.COLORS.textFaint;
    ctx.fillText('PASSAGES TO:', x, cy); cy += lineH;
    const corridors = (ch.corridors || []).slice(0, 5);
    corridors.forEach(c => {
      const tgt = G.chambersById[c.target_id];
      const name = tgt?.name_en || c.target_id;
      const lvlColor = CFG.COLORS.levelColors[tgt?.level || 0];
      ctx.fillStyle = lvlColor || CFG.COLORS.textDim;
      ctx.fillText(`  → ${name}`, x + 6, cy); cy += lineH;
    });

    // Oracle pointer
    if (G.currentLevel === 0) {
      cy += 4;
      const oRoom = G.rooms[G.oracleRoomIdx];
      if (oRoom && G.currentRoom !== oRoom) {
        ctx.fillStyle = CFG.COLORS.green;
        ctx.fillText(`𓁟 Oracle: ${pathLength()} rooms away`, x, cy);
      } else if (G.currentRoom === oRoom) {
        ctx.fillStyle = CFG.COLORS.greenBright;
        ctx.fillText('𓁟 Oracle stands here. [E] to speak.', x, cy);
      }
      cy += lineH;
    }

    // Stairs info
    if (G.stairsDown.length || G.stairsUp.length) {
      cy += 2;
      if (G.stairsDown.length) {
        ctx.fillStyle = CFG.COLORS.stairDown;
        ctx.fillText(`▼ Descend to L${G.currentLevel + 1}`, x, cy); cy += lineH;
      }
      if (G.stairsUp.length) {
        ctx.fillStyle = CFG.COLORS.stairUp;
        ctx.fillText(`▲ Ascend to L${G.currentLevel - 1}`, x, cy); cy += lineH;
      }
    }
  }
  return cy;
}

function renderInscriptionPanel(ctx, x, y, w) {
  const ins = G.inspectedInscr;
  if (!ins) return y;

  const fs = Math.floor(13 * G.dpr);
  const bodyFs = Math.floor(15 * G.dpr);
  const lineH = fs + 4;
  let cy = y;

  ctx.font = `${fs}px ${CFG.FONT}`;
  ctx.fillStyle = CFG.COLORS.goldDim;
  ctx.fillText('𓊹 INSCRIPTION', x, cy); cy += lineH + 6;

  if (ins.passage) {
    ctx.font = `${bodyFs}px EB Garamond, serif`;
    ctx.fillStyle = CFG.COLORS.text;
    const lines = wrapText(ctx, `"${ins.passage.translation}"`, w);
    // Show ALL lines (panel scrolls visually because side panel has space)
    lines.slice(0, 18).forEach(line => { ctx.fillText(line, x, cy); cy += bodyFs + 4; });
    cy += 4;
    ctx.font = `${fs}px ${CFG.FONT}`;
    ctx.fillStyle = CFG.COLORS.textFaint;
    if (ins.passage.text_name) { ctx.fillText(ins.passage.text_name, x, cy); cy += lineH; }
    if (ins.passage.period) { ctx.fillText(ins.passage.period, x, cy); cy += lineH; }
    if (ins.passage.shelfmark) { ctx.fillText(ins.passage.shelfmark, x, cy); cy += lineH; }
  } else if (ins.quote) {
    ctx.font = `${bodyFs}px EB Garamond, serif`;
    ctx.fillStyle = CFG.COLORS.text;
    const lines = wrapText(ctx, `"${ins.quote.quote}"`, w);
    lines.slice(0, 18).forEach(line => { ctx.fillText(line, x, cy); cy += bodyFs + 4; });
    cy += 4;
    ctx.font = `${fs}px ${CFG.FONT}`;
    ctx.fillStyle = CFG.COLORS.textFaint;
    ctx.fillText(`${ins.quote.shelfmark || ''} · ${ins.quote.period || ''}`, x, cy); cy += lineH;
  }

  // SPEAK button
  cy += 10;
  ctx.font = `${fs}px ${CFG.FONT}`;
  ctx.strokeStyle = CFG.COLORS.green; ctx.lineWidth = 1;
  ctx.fillStyle = 'rgba(143,188,159,0.07)';
  roundRect(ctx, x, cy, w, lineH + 10, 3); ctx.fill(); ctx.stroke();
  ctx.fillStyle = CFG.COLORS.green;
  ctx.fillText('  [SPACE] SPEAK — Kimi K2.5 synthesis', x + 4, cy + 5);
  cy += lineH + 16;

  return cy;
}

// ══════════════════════════════════════════════════════════════════════════════
// MESSAGES
// ══════════════════════════════════════════════════════════════════════════════
function renderMessages(ctx, tile) {
  const now = Date.now();
  const fs = Math.floor(tile * 0.62);
  ctx.font = `${fs}px ${CFG.FONT}`;
  G.messages = G.messages.filter(m => now - m.time < 16000);
  const viewW = G.canvas.width - CFG.PANEL_W * G.dpr;
  let y = tile * 2.5;
  const recent = G.messages.slice(-5);
  recent.forEach((m, i) => {
    const age = now - m.time;
    const alpha = age > 11000 ? 1 - (age - 11000) / 5000 : Math.min(1, age / 250);
    ctx.fillStyle = `rgba(5,5,4,${0.85 * alpha})`;
    ctx.fillRect(0, y - 2, viewW, fs + 6);
    ctx.globalAlpha = alpha;
    ctx.fillStyle = m.color;
    ctx.fillText(' ' + m.text, tile * 0.5, y);
    ctx.globalAlpha = 1;
    y += fs + 4;
  });
}

// ══════════════════════════════════════════════════════════════════════════════
// STATUS BAR
// ══════════════════════════════════════════════════════════════════════════════
function renderStatusBar(ctx, tile) {
  const fs = Math.floor(tile * 0.62);
  const y = G.canvas.height - fs - 8;
  const viewW = G.canvas.width - CFG.PANEL_W * G.dpr;

  ctx.fillStyle = 'rgba(5,5,4,0.95)';
  ctx.fillRect(0, y - 5, viewW, fs + 13);
  ctx.strokeStyle = CFG.COLORS.panelBorder; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(0, y - 5); ctx.lineTo(viewW, y - 5); ctx.stroke();

  ctx.font = `${fs}px ${CFG.FONT}`;
  // Slim left side: just the most-essential locator. Side panel has details.
  const r = G.currentRoom;
  const left = r
    ? ` L${r.chamber.level} · ${r.chamber.name_en}`
    : ` L${G.currentLevel}: ${LEVEL_NAMES[G.currentLevel]}`;
  ctx.fillStyle = CFG.COLORS.textDim;
  ctx.fillText(left, tile * 0.5, y);

  // Right side: just key bindings
  const right = '[E] interact   [SPACE] speak   [M] map   [?] help';
  const rw = ctx.measureText(right).width;
  ctx.fillStyle = CFG.COLORS.textFaint;
  ctx.fillText(right, viewW - rw - tile, y);
}

// ══════════════════════════════════════════════════════════════════════════════
// ORACLE CHAT — FIXED: uses HTML input capture element
// ══════════════════════════════════════════════════════════════════════════════
function renderOracleChat(ctx, tile, viewCols, time) {
  const viewW = viewCols * tile;
  const viewH = G.canvas.height;

  // Full overlay with vignette
  ctx.fillStyle = 'rgba(5,5,4,0.94)';
  ctx.fillRect(0, 0, viewW, viewH);

  const fs = Math.floor(tile * 0.7);
  const bodyFs = Math.floor(tile * 0.63);
  const lineH = bodyFs + 5;
  const margin = tile * 2.5;
  const chatW = Math.min(viewW - margin * 2, tile * 52);
  const chatX = (viewW - chatW) / 2;

  // Oracle header — dramatic
  ctx.font = `${Math.floor(tile * 1.1)}px ${CFG.HIERO_FONT}`;
  ctx.fillStyle = dimColor(CFG.COLORS.oracle, 0.7 + Math.sin(time * 0.9) * 0.3);
  ctx.fillText('𓁟', chatX - tile * 1.5, tile * 2.8);

  ctx.font = `${fs}px ${CFG.FONT}`;
  ctx.fillStyle = CFG.COLORS.green;
  ctx.fillText('THE ORACLE — Hermes-4-70B', chatX, tile * 2.2);

  ctx.font = `${Math.floor(tile * 0.48)}px ${CFG.FONT}`;
  ctx.fillStyle = CFG.COLORS.textFaint;
  ctx.fillText('Navigator of 77,683 ancient texts · Ask about any chamber, text, or concept', chatX, tile * 3.0);

  // Separator
  ctx.strokeStyle = CFG.COLORS.greenDim; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(chatX, tile * 3.6); ctx.lineTo(chatX + chatW, tile * 3.6); ctx.stroke();

  // Chat messages rendered by HTML overlay (#oracle-chat-text) for
  // native scroll + text selection. Canvas only draws header + input box.
  const inputBoxY = viewH - tile * 5;

  // ── INPUT BOX ──
  const inputH = tile * 2;
  ctx.fillStyle = 'rgba(12,10,8,0.96)';
  ctx.strokeStyle = CFG.COLORS.green; ctx.lineWidth = 1;
  roundRect(ctx, chatX - 6, inputBoxY - 6, chatW + 12, inputH + 12, 5);
  ctx.fill(); ctx.stroke();

  // Input text
  ctx.font = `${bodyFs}px ${CFG.FONT}`;
  ctx.fillStyle = CFG.COLORS.greenDim;
  ctx.fillText('>', chatX + 4, inputBoxY + 5);
  ctx.fillStyle = CFG.COLORS.text;
  ctx.fillText(G.oracleChatInput, chatX + tile * 1.3, inputBoxY + 5);

  // Blinking cursor
  G.oracleCursorTimer++;
  if (G.oracleCursorTimer % 45 < 28) {
    const cursorX = chatX + tile * 1.3 + ctx.measureText(G.oracleChatInput).width + 2;
    ctx.fillStyle = CFG.COLORS.green;
    ctx.fillRect(cursorX, inputBoxY + 3, 2, bodyFs);
  }

  // Hint
  ctx.font = `${Math.floor(tile * 0.43)}px ${CFG.FONT}`;
  ctx.fillStyle = CFG.COLORS.textGhost;
  ctx.fillText('[Enter] send  ·  [Esc] close  ·  Ask about spells, the dead, the tongue, Osiris, creation...', chatX, inputBoxY + inputH + tile * 0.5);
}

// ── Oracle HTML chat overlay helpers ─────────────────────────────────────────
function _oracleChatEl() { return document.getElementById('oracle-chat-text'); }

function _positionOracleChatOverlay() {
  const el = _oracleChatEl();
  if (!el) return;
  const t = CFG.TILE;   // 28px CSS tile
  const margin = t * 2.5;  // must match renderOracleChat margin
  const viewW = window.innerWidth;
  const viewH = window.innerHeight;
  // Match canvas renderOracleChat: chatW = min(viewW_px - margin*2, tile*52)
  // where tile_px = CFG.TILE * dpr — so in CSS: min(viewW - margin*2/dpr, t*52)
  // Simplify: just use CSS-pixel equivalents directly.
  const chatW = Math.min(viewW - margin * 2, t * 52);
  const chatX = Math.floor((viewW - chatW) / 2);
  const top  = Math.floor(t * 3.8);        // below oracle header + separator
  const bot  = Math.floor(viewH - t * 5.5); // above input box
  el.style.left   = chatX + 'px';
  el.style.width  = chatW + 'px';
  el.style.top    = top + 'px';
  el.style.height = Math.max(40, bot - top) + 'px';
}

function syncOracleChatHtml() {
  const el = _oracleChatEl();
  if (!el || !G.oracleChatActive) return;
  const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  let html = '';
  G.oracleChatHistory.forEach(h => {
    if (h.role === 'tool') {
      const cls = h.status === 'error' ? 'error' : (h.status === 'pending' ? 'pending' : '');
      const arrow = h.status === 'pending' ? '…' : (h.status === 'error' ? '✗' : '→');
      const argsStr = Object.entries(h.args || {}).map(([k,v]) => {
        const vs = typeof v === 'string'
          ? '"' + v.slice(0,50) + (v.length>50?'…':'') + '"'
          : JSON.stringify(v);
        return k + '=' + vs;
      }).join(', ');
      html += '<div class="och-tool ' + cls + '">⟐ ' + esc(h.name) + '(' + esc(argsStr) + ')</div>';
      if (h.summary) {
        html += '<div class="och-tool-result ' + cls + '">' + arrow + ' ' + esc(h.summary) + '</div>';
      }
    } else if (h.role === 'user') {
      html += '<div class="och-user">' + esc(h.text) + '</div>';
    } else {
      const lines = esc(h.text).replace(/\n/g, '<br>');
      html += '<div class="och-oracle"><span class="label">ORACLE</span>' + lines + '</div>';
      if (h.chambers && h.chambers.length) {
        h.chambers.forEach(id => {
          const ch = G.chambersById[id];
          if (ch) html += '<div class="och-ref">→ ' + esc(ch.name_en) + ' (L' + ch.level + ')</div>';
        });
      }
    }
  });
  if (G.oracleWaiting) html += '<div class="och-waiting">⋯ the oracle consults the corpus…</div>';
  const wasAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
  el.innerHTML = html;
  if (wasAtBottom || G.oracleChatHistory.length <= 3) el.scrollTop = el.scrollHeight;
}

function openOracleChat() {
  G.oracleChatActive = true;
  G.oracleChatInput = '';
  G.oracleCursorTimer = 0;
  G.inputEl.value = '';
  G.inputEl.style.pointerEvents = 'auto';
  G.inputEl.focus();
  if (!G.oracleWs) initOracleWs();
  const el = _oracleChatEl();
  if (el) { el.style.display = 'block'; _positionOracleChatOverlay(); syncOracleChatHtml(); }
  window.addEventListener('resize', _positionOracleChatOverlay);
  addMsg('⊕ The Oracle awaits. Ask about any text, chamber, or path.', CFG.COLORS.oracle);
  addMsg('  Text is selectable · scroll the chat log above · [Esc] to close', CFG.COLORS.textFaint);
  syncOracleChatHtml();
}

// ── Portal — 5×5 ringed gateway; walking onto any inner tile teleports.
//
//       ╭─Ω─╮
//       │◇◇◇│
//       ═◇◆◇═   ← the 3×3 hot zone inside the ring; step anywhere inside
//       │◇◇◇│
//       ╰───╯
//
function openPortal(chamberId) {
  const ch = G.chambersById[chamberId];
  if (!ch) {
    addMsg(`☒ Portal target unknown: ${chamberId}`, CFG.COLORS.danger);
    console.warn('openPortal: unknown chamberId', chamberId,
                 'known=', Object.keys(G.chambersById).length);
    return;
  }

  if (G.portalOpen) closePortal();

  G.portalOpen = true;
  G.portalChamberId = chamberId;
  G.highlightedChambers.add(chamberId);

  // Portal only renders on L0. Off-level calls queue via G.pendingPortal
  // at handleOracleEvent; this function then only announces.
  if (G.currentLevel !== 0 || !G.oraclePos) {
    addMsg(`◇ Portal tuned to ${ch.name_en} (L${ch.level}).`, CFG.COLORS.greenDim);
    addMsg('  Ascend to the Sanctum (L0) to step through.', CFG.COLORS.greenDim);
    return;
  }

  // Find a clear 5×5 block near the Oracle. Accept walkable decor; reject
  // walls, stairs, Oracle core, torches.
  const ox = G.oraclePos.x, oy = G.oraclePos.y;
  const blockOk = (gx, gy) => {
    for (let dy = -2; dy <= 2; dy++) {
      for (let dx = -2; dx <= 2; dx++) {
        const t = getTile(gx + dx, gy + dy);
        if (!t) return false;
        if (!t.walk) return false;
        if (t.isOracle || t.isStair || t.isTorch) return false;
      }
    }
    return true;
  };

  let gx = null, gy = null;
  const prefer = [
    [0, 6], [0, 7], [0, 8], [0, 5],
    [6, 0], [-6, 0], [7, 0], [-7, 0],
    [0, -6], [4, 4], [-4, 4], [4, -4], [-4, -4],
  ];
  for (const [dx, dy] of prefer) {
    if (blockOk(ox + dx, oy + dy)) { gx = ox + dx; gy = oy + dy; break; }
  }
  if (gx === null) {
    outer:
    for (let r = 1; r <= 10; r++) {
      for (let dy = -r; dy <= r; dy++) {
        for (let dx = -r; dx <= r; dx++) {
          if (Math.abs(dx) !== r && Math.abs(dy) !== r) continue;
          if (blockOk(ox + dx, oy + dy)) {
            gx = ox + dx; gy = oy + dy; break outer;
          }
        }
      }
    }
  }
  if (gx === null) {
    gx = ox; gy = oy + 6;
    console.warn('openPortal: no clear 5x5; forcing at', gx, gy);
  }

  G.portalPos = { x: gx, y: gy };
  G.portalOriginalTiles = {};
  const saveOrig = (tx, ty) => {
    const key = `${tx},${ty}`;
    if (G.portalOriginalTiles[key]) return;
    const orig = getTile(tx, ty);
    if (orig) G.portalOriginalTiles[key] = { ...orig };
  };

  // Inner 3×3 hot zone (strong green) — walkable; stepping into any cell fires.
  const ringGlyphs = ['◇', '◈', '◎', '○'];
  for (let dy = -1; dy <= 1; dy++) {
    for (let dx = -1; dx <= 1; dx++) {
      const tx = gx + dx, ty = gy + dy;
      saveOrig(tx, ty);
      const isCentre = dx === 0 && dy === 0;
      setTile(tx, ty, {
        ch: isCentre ? '◆' : ringGlyphs[((dx + 1) * 3 + (dy + 1)) & 3],
        fg: isCentre ? CFG.COLORS.greenBright : CFG.COLORS.green,
        walk: true,
        isPortal: true,
        portalCenter: isCentre,
        portalHot: true,
        portalChamberId: chamberId,
      });
    }
  }
  // Outer 5×5 decorative frame. Also walkable so angled approaches don't
  // bounce. Frame tiles are portalHot so stepping on them teleports too.
  const frame = [
    [-2, -2, '╭'], [-1, -2, '─'], [0, -2, 'Ω'], [1, -2, '─'], [2, -2, '╮'],
    [-2, -1, '│'],                                                  [2, -1, '│'],
    [-2,  0, '═'],                                                  [2,  0, '═'],
    [-2,  1, '│'],                                                  [2,  1, '│'],
    [-2,  2, '╰'], [-1,  2, '─'], [0,  2, '─'], [1,  2, '─'], [2,  2, '╯'],
  ];
  for (const [dx, dy, glyph] of frame) {
    const tx = gx + dx, ty = gy + dy;
    saveOrig(tx, ty);
    setTile(tx, ty, {
      ch: glyph, fg: CFG.COLORS.greenDim, walk: true,
      isPortal: true, portalCenter: false, portalHot: true,
      portalChamberId: chamberId, portalFrame: true,
    });
  }

  spawnPortalFlash(gx, gy);
  addMsg(`◆ PORTAL OPENED → ${ch.name_en} (L${ch.level})`, CFG.COLORS.greenBright);
  addMsg('  Walk into the diamond to step through.', CFG.COLORS.greenDim);

  fetchRoomPassages({ chamber: ch });
}

function closePortal() {
  if (!G.portalOpen) return;
  if (G.portalOriginalTiles) {
    Object.entries(G.portalOriginalTiles).forEach(([key, orig]) => {
      const [x, y] = key.split(',').map(Number);
      setTile(x, y, orig);
    });
  }
  G.portalOpen = false;
  G.portalChamberId = null;
  G.portalPos = null;
  G.portalOriginalTiles = null;
}

function enterPortal() {
  if (!G.portalOpen || !G.portalChamberId) return;
  if (G.transitioning) return;   // debounce during warp
  const ch = G.chambersById[G.portalChamberId];
  if (!ch) {
    console.warn('enterPortal: chamber missing', G.portalChamberId);
    closePortal();
    return;
  }
  const dest = ch.id;
  const destLevel = (typeof ch.level === 'number') ? ch.level
                  : (typeof ch.level_id === 'number' ? ch.level_id : null);
  if (destLevel === null) {
    addMsg('Portal has no level set.', CFG.COLORS.danger);
    closePortal();
    return;
  }

  addMsg(`◆ Stepping through → ${ch.name_en}`, CFG.COLORS.greenBright);
  spawnPortalFlash(G.portalPos.x, G.portalPos.y);

  // Set teleport BEFORE transition so updateTransition can't miss it.
  G.pendingTeleport = { chamberId: dest, level: destLevel };
  closePortal();

  if (destLevel !== G.currentLevel) {
    startTransition(destLevel, destLevel > G.currentLevel ? 'down' : 'up');
  } else {
    const room = G.rooms.find(r => r.chamber.id === dest)
              || G.rooms.find(r => r.chamber.parentChamberId === dest);
    if (room) {
      G.player.x = room.centerX; G.player.y = room.centerY + 2;
      G.player.tx = G.player.x; G.player.ty = G.player.y;
      G.player.ox = G.player.x; G.player.oy = G.player.y;
      addMsg(`◆ Arrived at ${room.chamber.name_en}`, CFG.COLORS.greenBright);
      G.pendingTeleport = null;
    } else {
      addMsg('Portal destination not on this level.', CFG.COLORS.danger);
      G.pendingTeleport = null;
    }
  }
}

// Burst of green particles at the portal centre.
function spawnPortalFlash(cx, cy) {
  for (let i = 0; i < 32; i++) {
    const a = (i / 32) * Math.PI * 2;
    G.particles.push({
      x: cx + 0.5, y: cy + 0.5,
      vx: Math.cos(a) * 0.04, vy: Math.sin(a) * 0.04,
      life: 1.0, decay: 0.0015,
      ch: ['✦', '✧', '·', '◇'][i & 3],
      fg: CFG.COLORS.greenBright,
    });
  }
}

function closeOracleChat() {
  G.oracleChatActive = false;
  G.inputEl.blur();
  G.inputEl.style.pointerEvents = 'none';
  const el = _oracleChatEl();
  if (el) el.style.display = 'none';
  window.removeEventListener('resize', _positionOracleChatOverlay);
}

// ══════════════════════════════════════════════════════════════════════════════
// MAP OVERLAY
// ══════════════════════════════════════════════════════════════════════════════
// Scroll the map so `lvl` is fully visible.
function _mapScrollToLevel(lvl) {
  const tile = Math.floor(Math.min(window.innerWidth, window.innerHeight) / 28);
  const levelH = tile * 7;
  const rowH = levelH + Math.floor(tile * 1.2);
  const startY = tile * 5;
  const rowTop = startY + lvl * rowH - G.mapScrollY;
  const viewH = window.innerHeight;
  if (rowTop < startY) {
    G.mapScrollY = Math.max(0, startY + lvl * rowH - startY - 4);
  } else if (rowTop + rowH > viewH - tile * 3) {
    G.mapScrollY += (rowTop + rowH) - (viewH - tile * 3) + 4;
  }
}

function renderMapOverlay(ctx, tile) {
  ctx.fillStyle = 'rgba(5,5,4,0.97)';
  ctx.fillRect(0, 0, G.canvas.width, G.canvas.height);

  const fs = Math.floor(tile * 0.7);
  const smallFs = Math.floor(fs * 0.65);
  ctx.font = `${Math.floor(tile * 1.1)}px ${CFG.HIERO_FONT}`;
  ctx.fillStyle = CFG.COLORS.gold;
  ctx.fillText('𓊹', tile * 2, tile * 2.8);

  ctx.font = `${tile}px ${CFG.FONT}`;
  ctx.fillStyle = CFG.COLORS.gold;
  ctx.fillText('MAP OF THE LABYRINTH', tile * 3.5, tile * 2.2);

  ctx.font = `${Math.floor(fs * 0.75)}px ${CFG.FONT}`;
  ctx.fillStyle = CFG.COLORS.textFaint;
  ctx.fillText('77,683 ancient Egyptian texts · 8 levels · 41 halls · 79 chambers · 3000 BCE–400 CE', tile * 3.5, tile * 3.2);

  // Level rows
  const levelH = tile * 7;
  const rowH = levelH + Math.floor(tile * 1.2);
  const startY = tile * 5;
  const startX = tile * 4;
  const mapW = G.canvas.width - tile * 8 - CFG.PANEL_W * G.dpr;
  const viewH = G.canvas.height;

  // Clamp scroll
  const totalMapH = startY + 8 * rowH + tile * 3;
  const maxScroll = Math.max(0, totalMapH - viewH);
  G.mapScrollY = Math.max(0, Math.min(maxScroll, G.mapScrollY));

  // Scroll indicator
  if (maxScroll > 0) {
    const trackH = viewH - tile * 5;
    const thumbH = Math.max(24, trackH * (viewH / totalMapH));
    const thumbY = tile * 2.5 + (trackH - thumbH) * (G.mapScrollY / maxScroll);
    ctx.fillStyle = 'rgba(150,120,60,0.2)';
    ctx.fillRect(G.canvas.width - 8, tile * 2.5, 4, trackH);
    ctx.fillStyle = 'rgba(196,146,42,0.55)';
    ctx.fillRect(G.canvas.width - 8, thumbY, 4, thumbH);
  }

  // Apply scroll offset to the level rows region
  ctx.save();
  ctx.rect(0, startY - tile, G.canvas.width, viewH - startY + tile);
  ctx.clip();
  ctx.translate(0, -G.mapScrollY);

  for (let lvl = 0; lvl <= 7; lvl++) {
    const y = startY + lvl * rowH;
    const chambers = G.levels[lvl] || [];
    const active = lvl === G.currentLevel;
    const lvlColor = CFG.COLORS.levelColors[lvl];

    // Level row background
    if (active) {
      ctx.fillStyle = `rgba(${hexToRgb(lvlColor)},0.04)`;
      ctx.fillRect(startX - 4, y - 4, mapW + 8, levelH + tile * 0.8);
    }

    // Level header
    ctx.font = `${fs}px ${CFG.FONT}`;
    ctx.fillStyle = active ? lvlColor : CFG.COLORS.textFaint;
    ctx.fillText(`${active ? '▶ ' : '  '}L${lvl}: ${LEVEL_NAMES[lvl]}`, startX, y);

    ctx.font = `${smallFs}px ${CFG.FONT}`;
    ctx.fillStyle = active ? CFG.COLORS.textDim : CFG.COLORS.textGhost;
    ctx.fillText(LEVEL_SUBTITLES[lvl], startX + fs * 2, y + fs + 1);

    // Hall groupings
    const halls = {};
    chambers.forEach(ch => {
      const h = ch.hall || 'default';
      if (!halls[h]) halls[h] = [];
      halls[h].push(ch);
    });

    const boxH = Math.floor(levelH - fs * 2.5);
    const totalChambers = chambers.length;
    const boxW = Math.max(55, Math.floor(mapW / Math.max(1, totalChambers + Object.keys(halls).length * 0.5)) - 6);

    let bx = startX + fs * 0.5;

    Object.entries(halls).forEach(([hallId, hallChambers]) => {
      const hallColor = CFG.COLORS.hallColors[hallId] || CFG.COLORS.textFaint;

      // Hall bracket line
      const hallW = hallChambers.length * (boxW + 5);
      ctx.strokeStyle = active ? dimColor(hallColor, 0.4) : CFG.COLORS.textGhost;
      ctx.lineWidth = 0.8;
      ctx.beginPath();
      ctx.moveTo(bx, y + fs * 2.2);
      ctx.lineTo(bx + hallW - 3, y + fs * 2.2);
      ctx.stroke();

      ctx.font = `${smallFs}px ${CFG.FONT}`;
      ctx.fillStyle = active ? hallColor : CFG.COLORS.textGhost;
      ctx.fillText(hallId.toUpperCase(), bx + 2, y + fs * 2.4);

      hallChambers.forEach((ch, ci) => {
        const cx = bx + ci * (boxW + 5);
        const cy = y + fs * 3;

        const isCurrent = G.currentRoom?.chamber?.id === ch.id;
        const isOracle = ch.id === 'oracle';
        const isHighlighted = G.highlightedChambers.has(ch.id);
        const isPortal = G.portalChamberId === ch.id;
        // Map cursor: only on current browsed level (chambers here are already the level's chambers)
        const isCursorSelected = (lvl === G.mapCursorLevel) && (chambers.indexOf(ch) === G.mapCursor);

        // Box fill
        ctx.strokeStyle = isPortal ? CFG.COLORS.greenBright
          : isCursorSelected ? CFG.COLORS.gold
          : isHighlighted ? CFG.COLORS.green
          : isCurrent ? CFG.COLORS.gold
          : isOracle ? CFG.COLORS.green
          : active ? dimColor(hallColor, 0.4) : CFG.COLORS.textGhost;
        ctx.lineWidth = (isCursorSelected || isPortal) ? 2 : isCurrent ? 1.5 : 0.8;
        ctx.strokeRect(cx, cy, boxW, boxH);

        if (isPortal) {
          ctx.fillStyle = 'rgba(100,220,160,0.14)';
          ctx.fillRect(cx, cy, boxW, boxH);
        } else if (isCursorSelected) {
          ctx.fillStyle = 'rgba(196,146,42,0.14)';
          ctx.fillRect(cx, cy, boxW, boxH);
        } else if (isHighlighted) {
          const hpulse = 0.08 + Math.sin(G.frameCount * 0.05 + ci) * 0.04;
          ctx.fillStyle = `rgba(100,200,140,${hpulse})`;
          ctx.fillRect(cx, cy, boxW, boxH);
        } else if (isCurrent) {
          ctx.fillStyle = 'rgba(196,146,42,0.09)';
          ctx.fillRect(cx, cy, boxW, boxH);
        } else if (isOracle) {
          ctx.fillStyle = 'rgba(143,188,159,0.05)';
          ctx.fillRect(cx, cy, boxW, boxH);
        }

        // Chamber name
        ctx.font = `${smallFs}px ${CFG.FONT}`;
        ctx.fillStyle = isPortal ? CFG.COLORS.greenBright
          : isCursorSelected ? CFG.COLORS.gold
          : isHighlighted ? CFG.COLORS.green
          : isCurrent ? CFG.COLORS.gold
          : isOracle ? CFG.COLORS.green
          : (active ? CFG.COLORS.textDim : CFG.COLORS.textGhost);
        const shortId = ch.id.toUpperCase().slice(0, 5);
        ctx.fillText(shortId, cx + 3, cy + boxH / 2 - 2);

        ctx.font = `${Math.floor(smallFs * 0.8)}px ${CFG.FONT}`;
        ctx.fillStyle = CFG.COLORS.textFaint;
        ctx.fillText(`${ch.text_count || 0}t`, cx + 3, cy + boxH / 2 + smallFs * 0.7);

        // Cursor indicator
        if (isCursorSelected) {
          ctx.fillStyle = CFG.COLORS.gold;
          ctx.fillText('▲', cx + boxW / 2 - smallFs / 2, cy + boxH + 2);
        }

        // Text labels below box
        if (ch.text_labels?.length && active) {
          ctx.font = `${Math.floor(smallFs * 0.65)}px ${CFG.FONT}`;
          ctx.fillStyle = isHighlighted ? CFG.COLORS.greenDim : CFG.COLORS.textGhost;
          const label = ch.text_labels[0] || '';
          const shortened = label.length > boxW / (smallFs * 0.35) ? label.slice(0, Math.floor(boxW / (smallFs * 0.35))) + '…' : label;
          ctx.fillText(shortened, cx + 2, cy + boxH + smallFs);
        }
      });
      bx += hallChambers.length * (boxW + 5) + tile * 0.8;
    });

    // Stair connectors
    if (lvl < 7 && G.levels[lvl + 1]?.length > 0) {
      ctx.fillStyle = CFG.COLORS.stairDown;
      ctx.font = `${fs}px ${CFG.FONT}`;
      ctx.fillText('▼', startX + mapW, y + levelH * 0.4);
    }
    if (lvl > 0) {
      ctx.fillStyle = CFG.COLORS.stairUp;
      ctx.fillText('▲', startX + mapW - fs * 1.5, y + levelH * 0.4);
    }
  }

  ctx.restore();

  // Footer — always visible below scroll region
  ctx.font = `${fs}px ${CFG.FONT}`;
  ctx.fillStyle = CFG.COLORS.textDim;
  ctx.fillText('[M] close', tile * 3, G.canvas.height - tile * 2);
  ctx.fillStyle = CFG.COLORS.textFaint;
  ctx.fillText('  ↑↓ levels  ·  ←→ chambers  ·  [E] travel  ·  scroll/wheel', tile * 12, G.canvas.height - tile * 2);
  if (G.highlightedChambers.size > 0) {
    ctx.fillStyle = CFG.COLORS.greenDim;
    ctx.fillText(`  · Oracle highlighted ${G.highlightedChambers.size} chamber(s)`, tile * 38, G.canvas.height - tile * 2);
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// HELP OVERLAY
// ══════════════════════════════════════════════════════════════════════════════
function renderHelpOverlay(ctx, tile) {
  ctx.fillStyle = 'rgba(5,5,4,0.97)';
  ctx.fillRect(0, 0, G.canvas.width, G.canvas.height);

  const fs = Math.floor(tile * 0.68);
  ctx.font = `${Math.floor(tile * 1.0)}px ${CFG.FONT}`;
  ctx.fillStyle = CFG.COLORS.gold;
  ctx.fillText('𓊹  AEGYPTUS: THE LABYRINTH — Library of Babel', tile * 3, tile * 2.8);

  ctx.font = `${fs}px ${CFG.FONT}`;
  const col1X = tile * 3, col2X = G.canvas.width / 2;
  let y1 = tile * 4.5, y2 = tile * 4.5;
  const lh = fs + 4;

  const col1 = [
    ['CONTROLS', 'gold'],
    ['↑↓←→ / WASD', 'Move through the Labyrinth', 'textDim'],
    ['E', 'Interact · Read · Oracle · Stairs', 'textDim'],
    ['SPACE', 'SPEAK — Kimi K2.5 synthesis', 'textDim'],
    ['M', 'Full labyrinth map overlay', 'textDim'],
    ['ESC', 'Close overlay / Exit oracle', 'textDim'],
    ['?', 'This help screen', 'textDim'],
    ['', ''],
    ['THE ORACLE', 'green'],
    ['The Oracle (𓁟) stands at the center of L0.', '', 'textDim'],
    ['Hermes-4-70B answers any question about', '', 'textFaint'],
    ['the ancient texts, their chambers, their', '', 'textFaint'],
    ['meaning. It gives wayfinding coordinates.', '', 'textFaint'],
    ['', ''],
    ['SPEAK', 'greenDim'],
    ['SPACE triggers Kimi K2.5 to synthesize', '', 'textDim'],
    ['a scholarly article from corpus passages.', '', 'textFaint'],
    ['Three columns: hieroglyphs · text · article.', '', 'textFaint'],
  ];

  const col2 = [
    ['THE HIERARCHY', 'gold'],
    ['Complex → Hall → Room → Chamber', '', 'textDim'],
    ['', ''],
    ['L0  THE ORACLE SANCTUM', '', 'levelColors[0]'],
    ['    Hermes speaks here', '', 'textFaint'],
    ['', ''],
    ['L1  HALL OF THE LIVING WORD', '', 'levelColors[1]'],
    ['    Utterance · Body · Speech · Tongue', '', 'textFaint'],
    ['    8 chambers · 280+ texts', '', 'textGhost'],
    ['', ''],
    ['L2  HALL OF POWER AND DEATH', '', 'levelColors[2]'],
    ['    The Tomb · The King · War · Decree', '', 'textFaint'],
    ['    8 chambers · 270+ texts', '', 'textGhost'],
    ['', ''],
    ['L3  HALL OF HIDDEN KNOWLEDGE', '', 'levelColors[3]'],
    ['    Spells · Amulets · Healing · Cosmos', '', 'textFaint'],
    ['    8 chambers · 260+ texts', '', 'textGhost'],
    ['', ''],
    ['L4  THE ABYSS OF ETERNITY', '', 'levelColors[4]'],
    ['    Wisdom · Truth · The Pillar · Time', '', 'textFaint'],
    ['    4 chambers · 130+ texts', '', 'textGhost'],
    ['', ''],
    ['Nous Research × Kimi Creative Hackathon 2026', '', 'textFaint'],
  ];

  function drawCol(lines, x, startY) {
    let y = startY;
    lines.forEach(([key, val, colorKey]) => {
      if (!key) { y += lh * 0.4; return; }
      if (!val && !colorKey) {
        // Section header
        ctx.fillStyle = CFG.COLORS[key] || CFG.COLORS.gold;
        ctx.font = `${fs}px ${CFG.FONT}`;
        ctx.fillText(key, x, y);
      } else if (colorKey) {
        // Level color special
        let col = colorKey.startsWith('levelColors[')
          ? CFG.COLORS.levelColors[parseInt(colorKey.slice(12))]
          : CFG.COLORS[colorKey] || CFG.COLORS.textDim;
        ctx.fillStyle = col;
        ctx.font = `${fs}px ${CFG.FONT}`;
        if (val) {
          ctx.fillText(key, x, y);
          ctx.fillStyle = CFG.COLORS.textFaint;
          ctx.fillText(val, x + ctx.measureText(key).width + 10, y);
        } else {
          ctx.fillText(key, x, y);
        }
      } else {
        ctx.fillStyle = CFG.COLORS.gold;
        ctx.font = `${fs}px ${CFG.FONT}`;
        ctx.fillText(key, x, y);
        ctx.fillStyle = CFG.COLORS.textDim;
        ctx.fillText(val, x + 130, y);
      }
      y += lh;
    });
  }

  drawCol(col1, col1X, y1);
  drawCol(col2, col2X, y2);

  ctx.font = `${fs}px ${CFG.FONT}`;
  ctx.fillStyle = CFG.COLORS.textDim;
  ctx.fillText('[?] close', tile * 3, G.canvas.height - tile * 2);
}

// ══════════════════════════════════════════════════════════════════════════════
// LEVEL TRANSITION
// ══════════════════════════════════════════════════════════════════════════════
function startTransition(targetLevel, direction) {
  G.transitioning = true;
  G.transitionAlpha = 0;
  G.transitionTarget = targetLevel;
  G.transitionDir = direction;
}

function updateTransition(dt) {
  if (!G.transitioning) return;
  G.transitionAlpha += dt * 0.0028;

  if (G.transitionAlpha >= 1 && G.transitionTarget >= 0) {
    generateLevel(G.transitionTarget);

    // PORTAL teleport — place player in the destination chamber (overrides stair placement)
    if (G.pendingTeleport?.chamberId) {
      const dest = G.pendingTeleport.chamberId;
      // Exact match first; then try parent hall (dest is a hall, rooms are sub-chambers);
      // then try sub-chamber whose parent matches dest.
      let room = G.rooms.find(r => r.chamber.id === dest)
             || G.rooms.find(r => r.chamber.parentChamberId === dest)
             || G.rooms.find(r => dest.startsWith(r.chamber.parentChamberId || r.chamber.id));
      if (!room && G.rooms.length) {
        // Last resort: largest room on this level.
        room = G.rooms.reduce((a, b) => (a.w * a.h >= b.w * b.h ? a : b));
        console.warn('pendingTeleport: chamber', dest, 'not placed; landing at', room.chamber.id);
        addMsg(`⚠ ${dest} not laid out here — arrived at ${room.chamber.name_en}`, CFG.COLORS.goldDim);
      }
      if (room) {
        G.player.x = room.centerX; G.player.y = room.centerY + 2;
        G.player.tx = G.player.x; G.player.ty = G.player.y;
        G.player.ox = G.player.x; G.player.oy = G.player.y;
        addMsg(`◆ Arrived at ${room.chamber.name_en}`, CFG.COLORS.greenBright);
        spawnPortalFlash(G.player.x, G.player.y);
      } else {
        addMsg('⚠ No chambers on this level.', CFG.COLORS.danger);
      }
      G.pendingTeleport = null;
    } else if (G.transitionDir === 'down' && G.stairsUp.length > 0) {
      const s = G.stairsUp[0];
      G.player.x = s.x + 4; G.player.y = s.y;
      G.player.tx = G.player.x; G.player.ty = G.player.y;
      G.player.ox = G.player.x; G.player.oy = G.player.y;
    } else if (G.transitionDir === 'up' && G.stairsDown.length > 0) {
      const s = G.stairsDown[0];
      G.player.x = s.x - 4; G.player.y = s.y;
      G.player.tx = G.player.x; G.player.ty = G.player.y;
      G.player.ox = G.player.x; G.player.oy = G.player.y;
    }
    G._stairCooldown = true;
    setTimeout(() => { G._stairCooldown = false; }, 1500);

    // v5.0 Day-2 carry-over: Oracle queued a portal, but the player was
    // off-Sanctum. Now we're on L0 with an Oracle room ready — spawn it.
    if (G.pendingPortal && G.currentLevel === 0) {
      const pc = G.pendingPortal;
      G.pendingPortal = null;
      setTimeout(() => openPortal(pc), 250);
    }
    G.transitionTarget = -1;
  }

  if (G.transitionAlpha >= 2) {
    G.transitioning = false;
    G.transitionAlpha = 0;
  }
}

function renderTransition(ctx, tile) {
  const alpha = G.transitionAlpha <= 1 ? G.transitionAlpha : 2 - G.transitionAlpha;
  ctx.fillStyle = `rgba(2,2,1,${alpha})`;
  ctx.fillRect(0, 0, G.canvas.width, G.canvas.height);

  if (G.transitionAlpha > 0.25 && G.transitionAlpha < 1.75) {
    const lvl = G.transitionDir === 'down' ? G.currentLevel + 1 : G.currentLevel - 1;
    const clampedLvl = Math.max(0, Math.min(7, lvl));
    const dir = G.transitionDir === 'down' ? 'DESCENDING' : 'ASCENDING';
    const lvlColor = CFG.COLORS.levelColors[clampedLvl];
    const textAlpha = Math.min(1, alpha * 2.2);

    ctx.globalAlpha = textAlpha;

    // Direction text
    ctx.font = `${Math.floor(tile * 1.3)}px ${CFG.FONT}`;
    ctx.fillStyle = lvlColor;
    const t1 = `${dir}`;
    ctx.fillText(t1, (G.canvas.width - ctx.measureText(t1).width) / 2, G.canvas.height * 0.35);

    // Level name
    ctx.font = `${Math.floor(tile * 0.85)}px ${CFG.FONT}`;
    ctx.fillStyle = CFG.COLORS.text;
    const t2 = `L${clampedLvl}: ${LEVEL_NAMES[clampedLvl]}`;
    ctx.fillText(t2, (G.canvas.width - ctx.measureText(t2).width) / 2, G.canvas.height * 0.46);

    // Subtitle
    ctx.font = `${Math.floor(tile * 0.6)}px ${CFG.FONT}`;
    ctx.fillStyle = CFG.COLORS.textDim;
    const t3 = LEVEL_SUBTITLES[clampedLvl];
    ctx.fillText(t3, (G.canvas.width - ctx.measureText(t3).width) / 2, G.canvas.height * 0.53);

    // Hieroglyph band
    ctx.font = `${Math.floor(tile * 1.8)}px ${CFG.HIERO_FONT}`;
    ctx.fillStyle = dimColor(lvlColor, 0.15);
    const hieros = HIERO_CHARS.slice(clampedLvl * 10, clampedLvl * 10 + 12).join(' ');
    ctx.fillText(hieros, (G.canvas.width - ctx.measureText(hieros).width) / 2, G.canvas.height * 0.66);

    ctx.globalAlpha = 1;
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// UPDATE LOOP
// ══════════════════════════════════════════════════════════════════════════════
function update(dt) {
  G.frameCount++;

  if (G.transitioning) { updateTransition(dt); return; }

  // Smooth movement
  if (G.player.moving) {
    G.player.moveT += dt;
    const t = Math.min(1, G.player.moveT / CFG.MOVE_SPEED);
    const ease = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
    G.player.tx = G.player.ox + (G.player.x - G.player.ox) * ease;
    G.player.ty = G.player.oy + (G.player.y - G.player.oy) * ease;
    if (t >= 1) { G.player.tx = G.player.x; G.player.ty = G.player.y; G.player.moving = false; }
  }

  checkCurrentRoom();
  updateInscriptionProximity();
  checkStairProximity();

  // CenterStage auto-fade (replaces guideText fade)
  updateCenterStage(performance.now());

  // Movement (only when not in chat)
  if (!G.player.moving && !G.oracleChatActive && !G.speakActive && !G.showHelp && !G.showMap && !G.transitioning) {
    if (G.keys['ArrowUp'] || G.keys['w'] || G.keys['W']) tryMove(0, -1);
    else if (G.keys['ArrowDown'] || G.keys['s'] || G.keys['S']) tryMove(0, 1);
    else if (G.keys['ArrowLeft'] || G.keys['a'] || G.keys['A']) tryMove(-1, 0);
    else if (G.keys['ArrowRight'] || G.keys['d'] || G.keys['D']) tryMove(1, 0);
  }

  updateParticles(dt);
  updateHieroRain(dt);
  // updateSigils(dt);  // disabled

  // Sigil replenish disabled
  if (false && G.sigils.length < 8 && G.rooms.length > 0 && Math.random() < 0.005) {
    const room = G.rooms[Math.floor(Math.random() * G.rooms.length)];
    G.sigils.push({
      x: room.centerX + (Math.random() - 0.5) * room.w * 0.5,
      y: room.centerY + (Math.random() - 0.5) * room.h * 0.5,
      ch: HIERO_SIMPLE[Math.floor(Math.random() * HIERO_SIMPLE.length)],
      vx: (Math.random() - 0.5) * 0.0008, vy: (Math.random() - 0.5) * 0.0005,
      life: 0.5 + Math.random() * 0.5, decay: 0.00008 + Math.random() * 0.0001,
      baseAlpha: 0.05 + Math.random() * 0.08, phase: Math.random() * Math.PI * 2,
    });
  }
}

function tryMove(dx, dy) {
  const nx = G.player.x + dx, ny = G.player.y + dy;
  const t = getTile(nx, ny);
  if (!t || !t.walk) return;
  G.player.ox = G.player.tx; G.player.oy = G.player.ty;
  G.player.x = nx; G.player.y = ny;
  G.player.moveT = 0; G.player.moving = true;

  // ── POKÉMON-STYLE STAIRWELL TRIGGER ──
  // Walking onto a stair tile auto-triggers the level transition.
  // The anchor tile (center of the 5×3 zone) is the gate; stepping on any
  // stair tile fires, but we debounce so re-entering after teleport doesn't loop.
  if (t.isStair && !G.transitioning && !G._stairCooldown) {
    const targetLevel = t.targetLevel;
    const dir = t.stairDir;
    if (typeof targetLevel === 'number') {
      G._stairCooldown = true;
      setTimeout(() => { G._stairCooldown = false; }, 1500);
      addMsg(
        `${dir === 'down' ? '▼' : '▲'} ${dir === 'down' ? 'Descending to' : 'Ascending to'} L${targetLevel}: ${LEVEL_NAMES[targetLevel] || '?'}`,
        CFG.COLORS.levelColors[targetLevel] || CFG.COLORS.gold
      );
      startTransition(targetLevel, dir);
    }
  }
}

function checkCurrentRoom() {
  const px = G.player.x, py = G.player.y;
  let foundRoom = null;
  for (const r of G.rooms) {
    if (px > r.x && px < r.x + r.w - 1 && py > r.y && py < r.y + r.h - 1) {
      foundRoom = r;
      break;
    }
  }
  // Track room state with explicit transitions
  if (foundRoom !== G.currentRoom) {
    if (foundRoom) {
      // Entered a (different) room
      G.currentRoom = foundRoom;
      G.inspectedInscr = null;
      const hallColor = CFG.COLORS.hallColors[foundRoom.hallId] || CFG.COLORS.gold;
      addMsg(`𓂋 ${foundRoom.chamber.name_en}`, hallColor);
      // Show chamber entry on CenterStage in 'guide' mode
      const desc = foundRoom.chamber.description || `${foundRoom.chamber.text_count || 0} ancient texts dwell here.`;
      showCenterStage({
        mode: 'guide',
        title: foundRoom.chamber.name_en,
        body: desc,
        duration: 5000,
      });
      fetchHint(foundRoom.chamber);
      fetchRoomPassages(foundRoom);
      if (G.currentLevel === 0) computeOraclePath();
    } else {
      // Left the current room (now in corridor)
      G.currentRoom = null;
      G.inspectedInscr = null;
    }
  }
}

function updateInscriptionProximity() {
  // Priority: Scroll > Oracle > Inscription/Tablet > none
  // We scan a 3x3 neighborhood. Scrolls WIN because they are the primary
  // "felt" object — walking adjacent to one should immediately surface the
  // text's name above the player.
  const px = G.player.x, py = G.player.y;

  // First: is the player ON a scroll (walkable tile) — top priority
  const onTile = getTile(px, py);
  if (onTile?.isScroll || onTile?.isArticle) {
    const room = G.currentRoom;
    const roomSc = room?.scrolls || [];
    const sc = roomSc.find(s => s.x === px && s.y === py);
    if (sc) {
      G.inspectedScroll = { ...sc };
      G.interactTarget = { x: px, y: py, tile: onTile, type: onTile.isArticle ? 'article' : 'scroll' };
      G.inspectedInscr = null;
      return;
    }
  }

  // Then: scan adjacent tiles for scrolls
  for (let dy = -1; dy <= 1; dy++) {
    for (let dx = -1; dx <= 1; dx++) {
      if (dx === 0 && dy === 0) continue;
      const t = getTile(px + dx, py + dy);
      if (t?.isScroll || t?.isArticle) {
        const room = G.currentRoom;
        const sc = (room?.scrolls || []).find(s => s.x === px + dx && s.y === py + dy);
        if (sc) {
          G.inspectedScroll = { ...sc };
          G.interactTarget = { x: px + dx, y: py + dy, tile: t, type: t.isArticle ? 'article' : 'scroll' };
          G.inspectedInscr = null;
          return;
        }
      }
    }
  }

  // No scroll nearby → fall through to inscription logic
  G.inspectedScroll = null;

  if (G.interactTarget && G.interactTarget.tile?.isInscription && !G.interactTarget.type) {
    const t = G.interactTarget.tile;
    const room = G.currentRoom;
    if (room && t.inscrIdx !== undefined) {
      const inscr = room.inscriptions[t.inscrIdx];
      if (inscr) {
        const passages = G.roomPassages[room.chamber.id];
        const passage = passages?.[inscr.idx % (passages?.length || 1)] || null;
        G.inspectedInscr = { ...inscr, passage };
      }
    }
  } else if (!G.interactTarget?.tile?.isOracle && !G.interactTarget?.tile?.isStair) {
    G.inspectedInscr = null;
  }
}

function checkStairProximity() {
  const px = G.player.x, py = G.player.y;

  // PORTAL: stepping onto ANY portalHot tile auto-triggers. The hot zone
  // is the inner 3×3; the outer 5×5 frame is also hot so angled walks
  // can't bypass it. We check the player's current tile, not a distance
  // compare, so teleportation fires exactly when you *walk onto* a tile.
  if (G.portalOpen && G.portalPos) {
    const here = getTile(px, py);
    if (here?.isPortal && here?.portalHot) {
      enterPortal();
      return;
    }
    // Within 1 tile of any portalHot tile = show interact hint.
    for (let dy = -1; dy <= 1; dy++) {
      for (let dx = -1; dx <= 1; dx++) {
        const t = getTile(px + dx, py + dy);
        if (t?.isPortal && t?.portalHot) {
          if (!G.interactTarget?.tile?.isInscription) {
            G.interactTarget = {
              x: px + dx, y: py + dy,
              tile: { isPortal: true, portalCenter: true, portalChamberId: G.portalChamberId },
            };
          }
          return;
        }
      }
    }
  }

  // Scan a 3×3 area around player for any stair tile
  for (let dy = -2; dy <= 2; dy++) {
    for (let dx = -2; dx <= 2; dx++) {
      const t = getTile(px + dx, py + dy);
      if (!t?.isStair) continue;
      if (G.interactTarget?.tile?.isInscription) return;
      const allStairs = [...G.stairsDown, ...G.stairsUp];
      const stair = allStairs.find(s => Math.abs(s.x - (px + dx)) <= 3 && Math.abs(s.y - (py + dy)) <= 3)
        || { x: px + dx, y: py + dy, targetLevel: t.targetLevel };
      G.interactTarget = {
        x: px + dx, y: py + dy,
        tile: { isStair: true, stairDir: t.stairDir, targetLevel: t.targetLevel },
        stair,
      };
      return;
    }
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// NETWORK — Hints, passages, speak
// ══════════════════════════════════════════════════════════════════════════════
async function fetchHint(chamber) {
  try {
    const ctrl = new AbortController();
    setTimeout(() => ctrl.abort(), 18000);
    const resp = await fetch(`${API}/hackathon/hint`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chamber_id: chamber.id }), signal: ctrl.signal,
    });
    if (!resp.ok) return;
    const data = await resp.json();
    // Only upgrade the centerstage if user is still in this chamber AND the
    // current centerstage is still the 'guide' for THIS chamber (don't clobber
    // a 'reading' overlay or a different chamber's guide)
    if (data.hint && G.currentRoom?.chamber?.id === chamber.id
        && G.center?.mode === 'guide'
        && G.center?.title === chamber.name_en) {
      showCenterStage({
        mode: 'guide',
        title: chamber.name_en,
        body: data.hint,
        duration: 5000,
      });
    }
  } catch {
    // Silent — the initial description is already shown by checkCurrentRoom
  }
}

async function fetchRoomPassages(room) {
  const cid = room.chamber.id;
  if (G.roomPassages[cid]) return;
  try {
    // v5.0 Day 4: pull a deeper slice so scroll glyphs backed by
    // canonical_ids past the first 12 still resolve to real text names.
    const resp = await fetch(`${API}/hackathon/chamber/${cid}/texts?limit=120`);
    if (!resp.ok) {
      // Fallback to summary endpoint (first 12 passages only).
      const resp2 = await fetch(`${API}/hackathon/chamber/${cid}`);
      if (!resp2.ok) return;
      const data = await resp2.json();
      G.roomPassages[cid] = data.passages || [];
    } else {
      const data = await resp.json();
      G.roomPassages[cid] = data.passages || [];
    }
    // Backfill empty scroll.textName fields with real text_name from
    // passages (kit-assembler scrolls start with textName='').
    const byCid = {};
    for (const p of G.roomPassages[cid]) byCid[p.canonical_id] = p;
    for (const sc of room.scrolls || []) {
      if (sc.textName) continue;
      const p = byCid[sc.canonicalId];
      if (p) {
        sc.textName = p.text_name || sc.canonicalId;
        sc.period   = p.period    || sc.period;
      } else if (sc.canonicalId) {
        sc.textName = sc.canonicalId;
      }
    }
  } catch { /* silent */ }
}

// ══════════════════════════════════════════════════════════════════════════════
// INTERACTION
// ══════════════════════════════════════════════════════════════════════════════
function interact() {
  if (!G.interactTarget) return;

  // ── PORTAL — step through to destination ──
  if (G.interactTarget.tile?.isPortal) {
    enterPortal();
    return;
  }

  // ── SCROLL (named text) — open the full passage in CenterStage ──
  if (G.interactTarget.type === 'scroll' && G.inspectedScroll) {
    const sc = G.inspectedScroll;
    addMsg(`𓏛 ${sc.textName}`, CFG.COLORS.goldBright);
    const room = G.currentRoom;
    let body = '';
    let source = '';
    if (room) {
      const passages = G.roomPassages[room.chamber.id] || [];
      const match = passages.find(p => p.canonical_id === sc.canonicalId);
      if (match && match.translation) {
        body = match.translation;
        const parts = [match.text_name, match.shelfmark, match.period].filter(Boolean);
        source = parts.join(' · ');
      }
    }
    if (!body) body = '[Press SPACE to invoke Kimi K2.5 synthesis on this text]';
    if (!source) source = `${sc.period || ''} · ${sc.canonicalId || ''}`.trim();
    showCenterStage({
      mode: 'reading',
      title: sc.textName,
      body,
      source,
      duration: 15000,
    });
    return;
  }

  // ── USER-AUTHORED ARTICLE — read from userArticles cache ──
  if (G.interactTarget.type === 'article' && G.inspectedScroll?.articleId) {
    const art = Object.values(G.userArticles).find(a => a.article_id === G.inspectedScroll.articleId);
    if (art) {
      addMsg(`𓋹 ${art.theme}`, CFG.COLORS.greenBright);
      addMsg(`   Your synthesis · ${art.word_count || '?'} words`, CFG.COLORS.textFaint);
      openArticleOverlay(art);
    }
    return;
  }

  // Stairs — [E] still works as a backup (auto-trigger handles primary path)
  if (G.interactTarget.tile?.isStair) {
    const dir = G.interactTarget.tile.stairDir;
    const targetLevel = G.interactTarget.tile.targetLevel
      ?? G.interactTarget.stair?.targetLevel;
    if (targetLevel === undefined || targetLevel === null) {
      addMsg('Stair destination unknown.', CFG.COLORS.danger);
      return;
    }
    addMsg(
      `${dir === 'down' ? '▼' : '▲'} ${dir === 'down' ? 'Descending' : 'Ascending'} to L${targetLevel}: ${LEVEL_NAMES[targetLevel] || '?'}`,
      CFG.COLORS.levelColors[targetLevel] || CFG.COLORS.gold
    );
    startTransition(targetLevel, dir);
    return;
  }

  // Oracle
  if (G.interactTarget.type === 'oracle' || G.interactTarget.tile?.isOracle) {
    openOracleChat();
    return;
  }

  // Inscription / Tablet — open the full passage on CenterStage (15s)
  if (G.interactTarget.tile?.isInscription && G.inspectedInscr) {
    const ins = G.inspectedInscr;
    if (ins.passage) {
      const p = ins.passage;
      addMsg(`𓂋 ${p.text_name || 'Inscription'}`, CFG.COLORS.goldDim);
      const sourceParts = [p.text_name, p.shelfmark, p.period].filter(Boolean);
      showCenterStage({
        mode: 'reading',
        title: p.text_name || 'INSCRIPTION',
        body: p.translation || '[no translation available]',
        source: sourceParts.join(' · '),
        duration: 15000,
      });
    } else if (ins.quote) {
      addMsg(`𓂋 Quoted passage`, CFG.COLORS.goldDim);
      showCenterStage({
        mode: 'reading',
        title: 'INSCRIPTION',
        body: ins.quote.quote || '',
        source: `${ins.quote.shelfmark || ''} · ${ins.quote.period || ''}`.trim().replace(/^· | ·$/g, ''),
        duration: 15000,
      });
    }
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// ORACLE WEBSOCKET — reliable with HTML input capture
// ══════════════════════════════════════════════════════════════════════════════
// v4.0 §6.4: Oracle speaks to /ws_agent — Hermes-4-70B with tools. Events:
//   {type:'ready',  model, version}
//   {type:'tool_call',   name, args}
//   {type:'tool_result', name, result}
//   {type:'tool_error',  name, message}
//   {type:'final',  text}
//   {type:'error',  message}
function initOracleWs() {
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
  const url = `${protocol}://${location.host}/hackathon/ws_agent`;

  try {
    G.oracleWs = new WebSocket(url);
  } catch (e) {
    addMsg('Oracle connection failed: ' + e.message, CFG.COLORS.danger);
    return;
  }

  G.oracleWs.onopen = () => {
    addMsg('📜 Oracle connection established.', CFG.COLORS.greenDim);
  };

  G.oracleWs.onmessage = (e) => {
    let msg;
    try { msg = JSON.parse(e.data); }
    catch (err) { console.error('Oracle parse error:', err, e.data); return; }
    handleOracleEvent(msg);
  };

  G.oracleWs.onerror = (e) => {
    console.error('Oracle WebSocket error:', e);
    addMsg('Oracle connection error.', CFG.COLORS.danger);
  };

  G.oracleWs.onclose = () => {
    G.oracleWs = null;
    if (G.oracleChatActive) {
      addMsg('Oracle reconnecting...', CFG.COLORS.textDim);
      setTimeout(initOracleWs, 2000);
    }
  };
}

// One-line summary of a tool_result for inline display. Short. Always.
function summariseToolResult(name, result) {
  if (!result || typeof result !== 'object') return String(result ?? '');
  if (result.error) return '! ' + String(result.error).slice(0, 80);
  if (name === 'search_corpus') {
    const chs = (result.chambers_touched || []).slice(0, 3).join(', ');
    return `${result.total ?? 0} hits${chs ? ' · ' + chs : ''}`;
  }
  if (name === 'find_chamber') {
    if (!result.matches?.length) return 'no match';
    return result.matches.slice(0, 3).map(m => m.name_en || m.chamber_id).join(' · ');
  }
  if (name === 'show_on_map') {
    return `highlighted ${result.count ?? 0}${result.missing?.length ? ' (missing ' + result.missing.length + ')' : ''}`;
  }
  if (name === 'corpus_stats') {
    if (result.scope === 'corpus') return `${result.texts ?? 0} texts · ${result.sentences ?? 0} sentences`;
    if (result.texts != null) return `${result.texts} of 77,683 texts in ${result.chambers ?? '?'} chambers`;
    return result.scope || '';
  }
  if (name === 'open_portal') {
    if (result.ok) return `portal → ${result.name_en || result.chamber_id} (L${result.level_id})`;
    return '! ' + (result.error || 'failed');
  }
  if (name === 'speak') {
    if (result.ok) return `SPEAK → ${result.name_en || result.chamber_id}`;
    return '! ' + (result.error || 'failed');
  }
  if (name === 'read_article') {
    if (result.ok) return `article ${result.article_id} · ${result.theme || result.name || ''}`.slice(0, 80);
    return '! ' + (result.error || 'failed');
  }
  if (name === 'tts') {
    if (result.ok) return `audio · ${result.voice || 'oracle'}${result.cached ? ' (cached)' : ''}`;
    return '! ' + (result.error || 'failed');
  }
  return JSON.stringify(result).slice(0, 80);
}

function formatToolArgs(args) {
  if (!args || typeof args !== 'object') return '';
  const parts = [];
  for (const [k, v] of Object.entries(args)) {
    let vs;
    if (Array.isArray(v)) vs = '[' + v.slice(0, 3).join(',') + (v.length > 3 ? ',…' : '') + ']';
    else if (typeof v === 'string') vs = `"${v.length > 40 ? v.slice(0, 40) + '…' : v}"`;
    else vs = JSON.stringify(v);
    parts.push(`${k}=${vs}`);
  }
  return parts.join(', ');
}

// v5.0 Day-2 carry-over: Oracle-agent tool-result side-effect helpers.
function openReaderOverlayForArticle(toolResult) {
  if (!window.Reader) {
    addMsg('Reader overlay not loaded (web/reader.js missing?).', CFG.COLORS.danger);
    return;
  }
  const articles = G._articleCache || collectSanctumArticles();
  G._articleCache = articles;
  let article = { ...toolResult };
  const full = articles.find(a => a.article_id === toolResult.article_id)
            || articles.find(a => a.canonical_id === toolResult.canonical_id);
  if (full) {
    article = { ...full, ...article };
    article.body = full.body || article.preview || '';
    article.hiero_fallback = full.hiero_fallback || null;
  } else if (!article.body) {
    article.body = article.preview || '[No article body available.]';
  }
  window.Reader.open(article);
}

function collectSanctumArticles() {
  // Pull physical_texts from L0 Sanctum chambers so reader.js gets the
  // full body (not the tool_result's 400-char preview).
  const articles = [];
  const l0 = (G.levels[0] || []).slice();
  let idx = 1;
  for (const ch of l0) {
    for (const pt of (ch.physical_texts || [])) {
      articles.push({
        article_id:   idx,
        canonical_id: pt.canonical_id || '',
        name:         pt.name || `Tablet ${idx}`,
        period:       pt.period || '',
        theme:        pt.theme || pt.name || '',
        body:         pt.body || pt.description || '',
        hiero_fallback: pt.hiero_fallback || null,
        chamber_id:   ch.id || '',
      });
      idx++;
      if (idx > 9) return articles;
    }
  }
  return articles;
}

// Singleton audio element for Oracle-tool TTS. Re-play auto-stops prior.
function playOracleTTS(url) {
  let audio = G._oracleAudioEl;
  if (!audio) {
    audio = document.createElement('audio');
    audio.preload = 'auto'; audio.style.display = 'none';
    document.body.appendChild(audio);
    G._oracleAudioEl = audio;
  }
  try {
    audio.pause(); audio.currentTime = 0;
    audio.src = url;
    audio.play().catch(e => {
      addMsg('Oracle audio play blocked: ' + e.message, CFG.COLORS.textFaint);
    });
  } catch (e) {
    addMsg('Oracle audio error: ' + e.message, CFG.COLORS.danger);
  }
}

function handleOracleEvent(msg) {
  const t = msg.type;
  if (t === 'ready') return;
  if (t === 'tool_call') {
    G.oracleChatHistory.push({
      role: 'tool',
      name: msg.name,
      args: msg.args || {},
      status: 'pending',
      summary: '',
    });
    return;
  }
  if (t === 'tool_result' || t === 'tool_error') {
    for (let i = G.oracleChatHistory.length - 1; i >= 0; i--) {
      const h = G.oracleChatHistory[i];
      if (h.role === 'tool' && h.name === msg.name && h.status === 'pending') {
        h.status = (t === 'tool_error') ? 'error' : 'done';
        h.summary = (t === 'tool_error')
          ? String(msg.message || 'error').slice(0, 80)
          : summariseToolResult(msg.name, msg.result);
        h.result = msg.result;
        break;
      }
    }
    if (t === 'tool_result' && msg.name === 'show_on_map' && msg.result?.highlighted) {
      msg.result.highlighted.forEach(h => G.highlightedChambers.add(h.chamber_id));
      if (!G.showMap && msg.result.highlighted[0]) {
        setTimeout(() => {
          G.showMap = true;
          G.mapCursorLevel = msg.result.highlighted[0].level ?? 0;
        }, 300);
      }
    }
    if (t === 'tool_result' && msg.name === 'find_chamber' && msg.result?.matches) {
      msg.result.matches.slice(0, 3).forEach(m => G.highlightedChambers.add(m.chamber_id));
    }
    // v5.0 Day-2 carry-over: agentic actions on the world.
    if (t === 'tool_result' && msg.name === 'open_portal' && msg.result?.ok) {
      const cid = msg.result.chamber_id;
      if (G.currentLevel === 0) {
        openPortal(cid);
      } else {
        // Player isn't in Sanctum — queue the portal, announce.
        G.pendingPortal = cid;
        startTransition(0, 'up');
        addMsg(`🔮 Oracle prepares a portal to ${msg.result.name_en}. Ascend to the Sanctum (L0) to step through.`, CFG.COLORS.greenDim);
      }
    }
    if (t === 'tool_result' && msg.name === 'speak' && msg.result?.ok) {
      const cid = msg.result.chamber_id;
      // Delay closing chat so user sees the speak tool_result before overlay opens.
      setTimeout(() => {
        if (G.oracleChatActive) closeOracleChat();
        triggerSpeakForChamberId(cid, msg.result.topic || '');
      }, 1200);
    }
    if (t === 'tool_result' && msg.name === 'read_article' && msg.result?.ok) {
      const articleResult = msg.result;
      setTimeout(() => {
        if (G.oracleChatActive) closeOracleChat();
        openReaderOverlayForArticle(articleResult);
      }, 1200);
    }
    if (t === 'tool_result' && msg.name === 'tts' && msg.result?.ok && msg.result.url) {
      playOracleTTS(msg.result.url);
    }
    return;
  }
  if (t === 'final') {
    G.oracleWaiting = false;
    G.oracleChatHistory.push({ role: 'oracle', text: msg.text || '' });
    syncOracleChatHtml();
    return;
  }
  if (t === 'error') {
    G.oracleWaiting = false;
    addMsg('Oracle error: ' + (msg.message || 'unknown'), CFG.COLORS.danger);
    syncOracleChatHtml();
    return;
  }
  // Sync after tool_call / tool_result updates too
  syncOracleChatHtml();
}

function sendOracleMsg() {
  const msg = G.inputEl.value.trim();
  if (!msg) return;

  if (G.oracleWaiting) {
    addMsg('Oracle is still consulting the corpus...', CFG.COLORS.textDim);
    return;
  }

  G.oracleChatHistory.push({ role: 'user', text: msg });
  G.inputEl.value = '';
  G.oracleChatInput = '';
  syncOracleChatHtml();

  const doSend = () => {
    const payload = JSON.stringify({
      message: msg,
      chamber_id: G.currentRoom?.chamber?.id || '',
    });
    try {
      G.oracleWs.send(payload);
      G.oracleWaiting = true;
    } catch (e) {
      addMsg('Failed to send: ' + e.message, CFG.COLORS.danger);
      G.oracleChatHistory.pop();
    }
  };

  if (!G.oracleWs || G.oracleWs.readyState !== WebSocket.OPEN) {
    addMsg('Connecting to Oracle...', CFG.COLORS.textDim);
    initOracleWs();
    const waitInterval = setInterval(() => {
      if (G.oracleWs && G.oracleWs.readyState === WebSocket.OPEN) {
        clearInterval(waitInterval);
        doSend();
      }
    }, 150);
    setTimeout(() => clearInterval(waitInterval), 6000);
    return;
  }

  doSend();
}

// v5.0 Day-2 carry-over: expose Oracle chat controls to reader.js so the
// [✦ SPEAK ABOUT THIS] button can inject a prompt unconditionally.
window.openOracleChat = openOracleChat;
window.sendOracleMsg  = sendOracleMsg;

// ══════════════════════════════════════════════════════════════════════════════
// SPEAK — Kimi K2.5 synthesis
// ══════════════════════════════════════════════════════════════════════════════
async function triggerSpeakForChamber() {
  if (!G.currentRoom) return;
  return triggerSpeakForChamberId(G.currentRoom.chamber.id);
}

// v5.0 Day-2 carry-over: Oracle agent's `speak` tool lands here.
async function triggerSpeakForChamberId(chamberId, oracleContext) {
  const chamber = G.chambersById[chamberId];
  if (!chamber) {
    addMsg(`Oracle: chamber '${chamberId}' not found.`, CFG.COLORS.danger);
    return;
  }
  await _runSpeakFlow(chamber, oracleContext || '');
}

async function _runSpeakFlow(chamber, oracleContext) {
  const chamberId = chamber.id;

  // Check cache
  try {
    const cacheResp = await fetch(`${API}/hackathon/synthesis/${chamberId}`);
    if (cacheResp.ok) {
      const cached = await cacheResp.json();
      if (cached.cached) { showCachedSynthesis(chamber, cached); return; }
    }
  } catch { }

  if (G.speakAbort) G.speakAbort.abort();
  G.speakSessionId++;
  const sid = G.speakSessionId;
  G.speakActive = true;

  const overlay = document.getElementById('speak-overlay');
  overlay.classList.add('active');
  document.getElementById('speak-chamber-name').textContent = chamber.name_en;
  document.getElementById('col-hiero').innerHTML = '';
  document.getElementById('col-corpus').innerHTML = '<div style="padding:20px;color:#8a8070">𓂋 Fetching corpus passages...</div>';
  document.getElementById('col-synthesis').innerHTML = '<div class="synthesis-label">𓂋 Kimi K2.5 synthesis — summoning ancient knowledge</div>';
  document.getElementById('speak-status-left').textContent = 'Connecting to Kimi K2.5...';
  document.getElementById('speak-status-right').textContent = '';

  G.speakAbort = new AbortController();
  const md = { lineBuffer: '', wordCount: 0, container: document.getElementById('col-synthesis'), currentBlock: null };

  fetch(`${API}/hackathon/speak`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chamber_id: chamberId, oracle_context: oracleContext || null }),
    signal: G.speakAbort.signal,
  }).then(resp => {
    const reader = resp.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    function pump() {
      return reader.read().then(({ done, value }) => {
        if (sid !== G.speakSessionId) return;
        if (done) { flushSpeakLine(md); finishSpeakUI(md.wordCount); return; }
        buf += dec.decode(value, { stream: true });
        const lines = buf.split('\n'); buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try { handleSpeakEv(JSON.parse(line.slice(6)), md, sid); } catch { }
        }
        return pump();
      });
    }
    return pump();
  }).catch(err => {
    if (err.name !== 'AbortError') {
      document.getElementById('speak-status-left').textContent = 'Error: ' + err.message;
    }
  });
}

// v5.0 Day-2 carry-over: substitute the chamberId-aware speak call into the
// body above. (The fetch body was already built against `chamberId` from
// the outer function scope, so no further changes needed.)

function showCachedSynthesis(chamber, cached) {
  G.speakActive = true;
  const overlay = document.getElementById('speak-overlay');
  overlay.classList.add('active');
  document.getElementById('speak-chamber-name').textContent = chamber.name_en;
  document.getElementById('col-hiero').innerHTML = decorativeHiero();
  document.getElementById('col-corpus').innerHTML = '<div style="padding:20px;color:#8a8070">Passages from corpus cache.</div>';

  const synCol = document.getElementById('col-synthesis');
  synCol.innerHTML = '<div class="synthesis-label">𓂋 Kimi K2.5 synthesis (cached)</div>';

  let currentBlock = null;
  cached.content.split('\n').forEach(line => {
    if (!line.trim()) { currentBlock = null; return; }
    if (line.startsWith('## ') || line.startsWith('# ')) {
      const h = document.createElement('h2'); h.textContent = line.replace(/^#+\s*/, ''); synCol.appendChild(h); currentBlock = null;
    } else if (line.startsWith('> ')) {
      const bq = document.createElement('blockquote'); bq.textContent = line.slice(2); synCol.appendChild(bq); currentBlock = bq;
    } else if (/^—/.test(line)) {
      const p = document.createElement('p'); p.className = 'synthesis-citation'; p.textContent = line; synCol.appendChild(p); currentBlock = null;
    } else {
      if (!currentBlock || currentBlock.tagName !== 'P') { currentBlock = document.createElement('p'); synCol.appendChild(currentBlock); }
      currentBlock.innerHTML += (currentBlock.innerHTML ? ' ' : '') + esc(line);
    }
  });

  const d = document.createElement('div'); d.className = 'synthesis-complete'; d.innerHTML = '𓊹 ──────────── 𓊹';
  synCol.appendChild(d);
  document.getElementById('speak-status-left').textContent = 'Cached synthesis';
  document.getElementById('speak-status-right').textContent = `${cached.word_count || '?'} words`;
}

function handleSpeakEv(ev, md, sid) {
  if (sid !== G.speakSessionId) return;
  if (ev.type === 'passages') {
    renderSpeakPassages(ev.data);
    document.getElementById('speak-status-left').textContent = `${ev.data.length} passages · Kimi K2.5 synthesising...`;
  } else if (ev.type === 'chunk') { appendSpeakChunk(ev.data || '', md); }
  else if (ev.type === 'done') { flushSpeakLine(md); finishSpeakUI(ev.data?.word_count || md.wordCount, ev.data?.citation_count); }
  else if (ev.type === 'error') { document.getElementById('speak-status-left').textContent = 'Error: ' + ev.data; }
}

function renderSpeakPassages(passages) {
  document.getElementById('col-hiero').innerHTML = decorativeHiero();
  passages.forEach(p => {
    if (p.hieroglyphic) {
      document.getElementById('col-hiero').innerHTML += `<div style="margin:10px 0;word-break:break-all;font-size:20px">${esc(p.hieroglyphic.substring(0, 200))}</div>`;
    }
  });
  document.getElementById('col-corpus').innerHTML = passages.map(p => `
    <div class="corpus-passage">
      ${p.transliteration ? `<div class="translit">${esc(p.transliteration.substring(0, 200))}</div>` : ''}
      <div class="translation">${esc(p.translation)}</div>
      <div class="meta">${esc(p.text_name || '')} · ${esc(p.shelfmark || '')} · ${esc(p.period || '')}</div>
    </div>`).join('');
}

function decorativeHiero() {
  // v5.0 Day-2 carry-over: header scales with hieroglyph font availability.
  // When G.hieroFallback is set (boot font-test failed), render a gold dot
  // ornament instead of tofu glyphs.
  if (G.hieroFallback === true) {
    return ['❖', '·', '·', '❖', '·', '❖']
      .map(h => `<div style="font-size:14px;margin:6px 0;opacity:0.5;color:#8a6a1e">${h}</div>`).join('');
  }
  return ['𓀀', '𓀁', '𓀂', '𓀃', '𓀄', '𓀅',
          '𓀆', '𓀇', '𓀈', '𓀉', '𓀊', '𓀋']
    .map(h => `<div style="font-size:24px;margin:5px 0;opacity:0.42">${h}</div>`).join('');
}

function appendSpeakChunk(text, md) {
  md.wordCount += text.split(/\s+/).filter(Boolean).length;
  document.getElementById('speak-status-right').textContent = md.wordCount + ' words';
  for (const ch of text) { if (ch === '\n') flushSpeakLine(md); else md.lineBuffer += ch; }
  if (md.lineBuffer && md.currentBlock?.tagName === 'P') {
    let sp = md.currentBlock.querySelector('.sp');
    if (!sp) { sp = document.createElement('span'); sp.className = 'sp'; sp.style.color = '#8fbc9f'; md.currentBlock.appendChild(sp); }
    sp.textContent = md.lineBuffer;
  }
  md.container.scrollTop = md.container.scrollHeight;
}

function flushSpeakLine(md) {
  const line = md.lineBuffer; md.lineBuffer = '';
  if (!line) { md.currentBlock = null; return; }
  if (md.currentBlock) { const sp = md.currentBlock.querySelector('.sp'); if (sp) sp.remove(); }
  if (line.startsWith('## ') || line.startsWith('# ')) {
    const h = document.createElement('h2'); h.textContent = line.replace(/^#+\s*/, ''); md.container.appendChild(h); md.currentBlock = null;
  } else if (line.startsWith('> ')) {
    if (md.currentBlock?.tagName === 'BLOCKQUOTE') md.currentBlock.innerHTML += '<br>' + esc(line.slice(2));
    else { const bq = document.createElement('blockquote'); bq.textContent = line.slice(2); md.container.appendChild(bq); md.currentBlock = bq; }
  } else if (/^—/.test(line)) {
    const p = document.createElement('p'); p.className = 'synthesis-citation'; p.textContent = line; md.container.appendChild(p); md.currentBlock = null;
  } else {
    if (!md.currentBlock || md.currentBlock.tagName !== 'P' || md.currentBlock.className) {
      md.currentBlock = document.createElement('p'); md.container.appendChild(md.currentBlock);
    }
    md.currentBlock.innerHTML += (md.currentBlock.innerHTML ? ' ' : '') + esc(line).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\*(.+?)\*/g, '<em>$1</em>');
  }
}

function finishSpeakUI(wc, cc) {
  G.speakActive = false;
  document.getElementById('speak-status-left').textContent = '𓊹 Synthesis complete';
  document.getElementById('speak-status-right').textContent = `${wc || 0} words` + (cc ? ` · ${cc} citations` : '');
  const d = document.createElement('div'); d.className = 'synthesis-complete'; d.innerHTML = '𓊹 ──────────── 𓊹';
  document.getElementById('col-synthesis').appendChild(d);
}

function closeSpeakOverlay() {
  if (G.speakAbort) { G.speakAbort.abort(); G.speakAbort = null; }
  G.speakActive = false;
  document.getElementById('speak-overlay').classList.remove('active');
}

// ══════════════════════════════════════════════════════════════════════════════
// INPUT HANDLING — clean separation of game vs oracle mode
// ══════════════════════════════════════════════════════════════════════════════
function onKeyDown(e) {
  G.keys[e.key] = true;

  // SPEAK overlay: only ESC
  if (document.getElementById('speak-overlay').classList.contains('active')) {
    if (e.key === 'Escape') { e.preventDefault(); closeSpeakOverlay(); }
    return;
  }

  // ORACLE CHAT: managed by the HTML input element
  // The inputEl handles Enter/Escape directly via its own listeners
  // We only need to handle ESC to close the overlay from the game canvas
  if (G.oracleChatActive) {
    if (e.key === 'Escape') {
      e.preventDefault();
      closeOracleChat();
    }
    // All other keys go to the input element naturally (it has focus)
    return;
  }

  // NORMAL GAME MODE
  if (G.transitioning) return;

  if (e.key === 'Escape') {
    G.showMap = false; G.showHelp = false; G.inspectedInscr = null;
    G.portalOpen = false;
    return;
  }
  if (e.key === 'm' || e.key === 'M') {
    G.showMap = !G.showMap; G.showHelp = false;
    if (G.showMap) { G.mapCursorLevel = G.currentLevel; _mapScrollToLevel(G.currentLevel); }
    return;
  }
  if (e.key === '?') { G.showHelp = !G.showHelp; G.showMap = false; return; }

  // Map overlay navigation
  if (G.showMap) {
    const allChambers = G.chambers;
    const level = G.mapCursorLevel;
    const levelChambers = allChambers.filter(c => c.level === level);
    if (e.key === 'ArrowRight') { G.mapCursor = (G.mapCursor + 1) % Math.max(1, levelChambers.length); return; }
    if (e.key === 'ArrowLeft')  { G.mapCursor = (G.mapCursor - 1 + levelChambers.length) % Math.max(1, levelChambers.length); return; }
    if (e.key === 'ArrowDown')  {
      G.mapCursorLevel = Math.min(7, G.mapCursorLevel + 1); G.mapCursor = 0;
      _mapScrollToLevel(G.mapCursorLevel); return;
    }
    if (e.key === 'ArrowUp')    {
      G.mapCursorLevel = Math.max(0, G.mapCursorLevel - 1); G.mapCursor = 0;
      _mapScrollToLevel(G.mapCursorLevel); return;
    }
    if (e.key === 'Enter' || e.key === 'e' || e.key === 'E') {
      // Travel to selected chamber — trigger level transition if different level
      const selected = levelChambers[G.mapCursor];
      if (selected) {
        G.showMap = false;
        if (selected.level !== G.currentLevel) {
          G.pendingTeleport = { chamberId: selected.id, level: selected.level };
          startTransition(selected.level, selected.level > G.currentLevel ? 'down' : 'up');
        } else {
          // Teleport to room on same level
          const room = G.rooms.find(r => r.chamber.id === selected.id);
          if (room) {
            G.player.x = room.centerX; G.player.y = room.centerY + 2;
            G.player.tx = G.player.x; G.player.ty = G.player.y;
            G.player.ox = G.player.x; G.player.oy = G.player.y;
            addMsg(`𓂋 Moved to ${selected.name_en}`, CFG.COLORS.gold);
          }
        }
      }
      return;
    }
    return; // consume all keys while map open
  }

  if ((e.key === 'e' || e.key === 'E' || e.key === 'Enter') && !G.showHelp) {
    interact(); return;
  }
  if (e.key === ' ') {
    e.preventDefault();
    if (G.inspectedInscr || G.currentRoom) triggerSpeakForChamber();
    return;
  }
}

function onKeyUp(e) { G.keys[e.key] = false; }

// ══════════════════════════════════════════════════════════════════════════════
// HELPERS
// ══════════════════════════════════════════════════════════════════════════════
function addMsg(text, color) {
  G.messages.push({ text, time: Date.now(), color: color || CFG.COLORS.text });
  if (G.messages.length > 20) G.messages = G.messages.slice(-15);
}

function esc(t) {
  const d = document.createElement('div'); d.textContent = t; return d.innerHTML;
}

function dimColor(hex, f) {
  if (!hex || !hex.startsWith('#')) return hex || '#000';
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgb(${Math.min(255, Math.round(r * f))},${Math.min(255, Math.round(g * f))},${Math.min(255, Math.round(b * f))})`;
}

function lerpColor(hexA, hexB, t) {
  if (!hexA?.startsWith('#') || !hexB?.startsWith('#')) return hexA || hexB || '#000';
  const r1 = parseInt(hexA.slice(1, 3), 16), g1 = parseInt(hexA.slice(3, 5), 16), b1 = parseInt(hexA.slice(5, 7), 16);
  const r2 = parseInt(hexB.slice(1, 3), 16), g2 = parseInt(hexB.slice(3, 5), 16), b2 = parseInt(hexB.slice(5, 7), 16);
  return `rgb(${Math.round(r1 + (r2 - r1) * t)},${Math.round(g1 + (g2 - g1) * t)},${Math.round(b1 + (b2 - b1) * t)})`;
}

function hexToRgb(hex) {
  if (!hex?.startsWith('#')) return '0,0,0';
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `${r},${g},${b}`;
}

function wrapText(ctx, text, maxW) {
  if (!text) return [''];
  const words = text.split(' '), lines = [];
  let line = '';
  words.forEach(w => {
    const test = line ? line + ' ' + w : w;
    if (ctx.measureText(test).width > maxW && line) { lines.push(line); line = w; }
    else line = test;
  });
  if (line) lines.push(line);
  return lines.length ? lines : [''];
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y); ctx.lineTo(x + w - r, y); ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r); ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h); ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r); ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function pathLength() {
  if (G.currentLevel !== 0) return '?';
  const target = G.rooms[G.oracleRoomIdx];
  if (!target || !G.currentRoom) return '?';
  if (G.currentRoom === target) return 0;
  const adj = {};
  G.rooms.forEach(r => { adj[r.chamber.id] = (r.chamber.corridors || []).map(c => c.target_id); });
  const visited = new Set([G.currentRoom.chamber.id]);
  const queue = [[G.currentRoom.chamber.id, 0]];
  while (queue.length) {
    const [id, d] = queue.shift();
    if (id === target.chamber.id) return d;
    for (const n of (adj[id] || [])) {
      if (!visited.has(n)) { visited.add(n); queue.push([n, d + 1]); }
    }
  }
  return '?';
}

// ══════════════════════════════════════════════════════════════════════════════
// GAME LOOP
// ══════════════════════════════════════════════════════════════════════════════
function gameLoop(ts) {
  const dt = Math.min(50, ts - (G.lastFrame || ts));
  G.lastFrame = ts;
  if (G.initialized) { update(dt); }
  render();
  requestAnimationFrame(gameLoop);
}

// ── INIT ──
boot();
