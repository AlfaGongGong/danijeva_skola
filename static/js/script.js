// static/js/script.js

// --- UTILITY: Safe HTML sanitizer ---
function sanitizeHTML(html) {
  const div = document.createElement('div');
  div.innerHTML = html;
  // Remove script tags and event handlers
  div.querySelectorAll('script').forEach(el => el.remove());
  div.querySelectorAll('*').forEach(el => {
    for (const attr of [...el.attributes]) {
      if (attr.name.startsWith('on')) el.removeAttribute(attr.name);
    }
  });
  return div.innerHTML;
}

// --- GLOBALNE VARIJABLE ---
let USER = "", CUR_P = "", CUR_L = "", CUR_MODE = "", LOGIN_TIME = 0;
let START_TIME = 0, QS = [], CUR_Q = 0, SCORE = 0;
let SERVER_DATA = {}, MODULES_DATA = null, CUR_MODULE_IDX = 0;

// TELEMETRIJA I IDLE DETECTOR
let TELEMETRY = [];
let LAST_MOUSE_MOVE = Date.now();
let idleSeconds = 0;
let idleInterval;
let hasWarnedIdle = false;

// TIMING
let MODULE_START_TIME = 0, TOTAL_DURATION = 0, LESSON_WORD_COUNT = 0;
let QUESTION_TIMER = null, TIME_LEFT = 0;
const TIME_PER_QUESTION = 45;

const MAX_RETRIES = 5;
const RETRY_DELAY = 3000;

const MEDAL_ICONS = {
  "FIRST_BLOOD": '<i class="fa-solid fa-shoe-prints medal-icon"></i>',
  "NERD": '<i class="fa-solid fa-glasses medal-icon"></i>',
  "SURVIVOR": '<i class="fa-solid fa-kit-medical medal-icon"></i>',
  "SPEED_DEMON": '<i class="fa-solid fa-bolt medal-icon"></i>',
  "BOOKWORM": '<i class="fa-solid fa-book-open medal-icon"></i>',
  "IRON_MAN": '<i class="fa-solid fa-robot medal-icon"></i>',
  "SPEEDING_TICKET": '<i class="fa-solid fa-file-invoice-dollar medal-icon"></i>',
  "BROKEN_STICK": '<i class="fa-solid fa-crutch medal-icon"></i>',
  "SLEEPING_BEAUTY": '<i class="fa-solid fa-bed medal-icon"></i>',
  "CHEATER": '<i class="fa-solid fa-user-secret medal-icon"></i>'
};

const MEDAL_DETAILS = {
  "FIRST_BLOOD": { name: "Prvi Korak", desc: "Završio prvu lekciju.", type: "good" },
  "NERD": { name: "Štreber", desc: "100% na testu.", type: "good" },
  "SURVIVOR": { name: "Preživjeli", desc: "Jedva prošao.", type: "good" },
  "SPEED_DEMON": { name: "Brzi Gonzales", desc: "Brzo rješavanje.", type: "good" },
  "BOOKWORM": { name: "Knjiški Moljac", desc: "3000 XP.", type: "good" },
  "IRON_MAN": { name: "Iron Man", desc: "Bez izlaska iz taba.", type: "good" },
  "SPEEDING_TICKET": { name: "Kazna za Brzinu", desc: "Klikanje bez čitanja!", type: "bad" },
  "BROKEN_STICK": { name: "Slomljena Palica", desc: "Manje od 20% na testu.", type: "bad" },
  "SLEEPING_BEAUTY": { name: "Trnoružica", desc: "Zaspao za računalom.", type: "bad" },
  "CHEATER": { name: "Prevarant", desc: "Izašao iz taba.", type: "bad" }
};

// --- TASK 9: Subject Icons ---
const SUBJECT_ICONS = {
    "Matematika":            "📐",
    "Kemija":                "⚗️",
    "Anatomija":             "🦴",
    "Osnove zdravstvene njege": "🩺",
    "Biologija":             "🧬",
    "Latinski jezik":        "🏛️"
};

// --- TASK 10: Timer Bar ---
function updateTimerBar(timeLeft, total) {
    const pct = (timeLeft / total) * 100;
    const fill = document.getElementById('timer-bar-fill');
    const secs = document.getElementById('timer-seconds');
    const counter = document.getElementById('question-counter');

    if (secs) secs.textContent = timeLeft + 's';
    if (fill) {
        fill.style.width = pct + '%';
        if (pct > 50)      fill.style.background = 'var(--primary)';
        else if (pct > 25) fill.style.background = '#f59e0b';
        else               fill.style.background = 'var(--danger)';
    }
    if (counter) counter.textContent = `Pitanje ${CUR_Q + 1}/${QS.length}`;
}

// --- TASK 11: Answer Feedback ---
function showAnswerFeedback(result, correctAnswer, userAnswer) {
    const container = document.getElementById('feedback-area');
    if (!container) return;

    if (result === 'CORRECT') {
        container.innerHTML = `
            <div class="feedback feedback-correct">
                <i class="fa-solid fa-check"></i> Tačno!
            </div>`;
    } else if (result === 'PARTIAL') {
        container.innerHTML = `
            <div class="feedback feedback-partial">
                <i class="fa-solid fa-circle-half-stroke"></i> Djelimično tačno
                <div class="feedback-answer">Potpun odgovor: <strong>${correctAnswer}</strong></div>
            </div>`;
    } else {
        container.innerHTML = `
            <div class="feedback feedback-wrong">
                <i class="fa-solid fa-xmark"></i> Netačno
                <div class="feedback-answer">Tačan odgovor: <strong>${correctAnswer}</strong></div>
            </div>`;
    }
}

// --- TASK 12: Result Dashboard ---
function showResultDashboard(data) {
    const prevDiff = data.prevScore
        ? `<span class="result-diff ${data.scorePercent >= data.prevScore ? 'pos' : 'neg'}">
               ${data.scorePercent >= data.prevScore ? '▲' : '▼'}
               ${Math.abs(data.scorePercent - data.prevScore).toFixed(1)}% vs prošli put
           </span>`
        : '';

    const container = document.getElementById('result-container') || document.getElementById('work-content');
    if (!container) return;

    container.innerHTML = `
        <div class="result-dashboard">
            <div class="result-score-row">
                <span class="result-big-num">${data.scorePercent.toFixed(0)}</span>
                <span class="result-denom">/100</span>
                ${prevDiff}
            </div>
            <div class="result-breakdown">
                <div class="rb-card rb-correct"><div class="rb-n">${data.correct}</div><div class="rb-l">Tačno</div></div>
                <div class="rb-card rb-partial"><div class="rb-n">${data.partial}</div><div class="rb-l">Djelimično</div></div>
                <div class="rb-card rb-wrong"><div class="rb-n">${data.wrong}</div><div class="rb-l">Netačno</div></div>
            </div>
            <div class="result-xp-row">+${data.xpGained} XP — ${Math.floor(data.duration)}s</div>
            ${data.medals.map(m => `<div class="result-medal">${MEDAL_ICONS[m] || '🏅'} ${MEDAL_DETAILS[m]?.name || m}</div>`).join('')}
            <button class="btn btn-primary btn-lg" onclick="goBack('view-select')" style="margin-top:15px;">NASTAVI</button>
        </div>`;
}

// --- TASK 13: Modal Helpers ---
function openModal(id)  { document.getElementById(id)?.classList.add('active'); }
function closeModal(id) { document.getElementById(id)?.classList.remove('active'); }

// --- TASK 14: XP Bar with Rank Progress ---
const RANK_THRESHOLDS = [
    { xp:     0, name: "PODRUMAR (LVL 1)" },
    { xp:   500, name: "ULIČNI SVIRAČ (LVL 2)" },
    { xp:  1200, name: "GAŽER (LVL 3)" },
    { xp:  2500, name: "PREDGRUPA (LVL 4)" },
    { xp:  5000, name: "STUDIO MUZIČAR (LVL 5)" },
    { xp: 10000, name: "ROCK ZVIJEZDA (LVL 10)" },
    { xp: 99999, name: "LEGENDA (MAX)" }
];

function getRankInfo(xp) {
    let current = RANK_THRESHOLDS[0];
    let next = RANK_THRESHOLDS[1];
    for (let i = 0; i < RANK_THRESHOLDS.length - 1; i++) {
        if (xp >= RANK_THRESHOLDS[i].xp) {
            current = RANK_THRESHOLDS[i];
            next = RANK_THRESHOLDS[i + 1];
        }
    }
    const pct = Math.min(100, ((xp - current.xp) / (next.xp - current.xp)) * 100);
    return { current: current.name, next: next.name, pct, toNext: next.xp - xp };
}

function renderXPBar(xp) {
    const container = document.getElementById('xp-bar-container');
    if (!container) return;
    const { current, next, pct, toNext } = getRankInfo(xp);
    container.innerHTML = `
        <div class="xp-rank-name">${current}</div>
        <div class="xp-bar-top">
            <span>${xp} XP</span>
            <span>${toNext} do sljedećeg</span>
        </div>
        <div class="xp-bar-bg"><div class="xp-bar-fill" style="width:${pct}%"></div></div>`;
}

// --- TASK 15: Cheat Overlay Animation ---
function showCheatOverlay() {
    const el = document.getElementById('cheat-overlay');
    if (!el) return;
    el.style.display = 'flex';
    el.style.animation = 'none';
    el.offsetHeight; // force reflow
    el.style.animation = '';
}

// --- TASK 16: Sidebar Toggle ---
document.addEventListener('DOMContentLoaded', function() {
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');

    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('open');
            if (backdrop) backdrop.classList.toggle('visible');
        });
    }
    if (backdrop) {
        backdrop.addEventListener('click', function() {
            if (sidebar) sidebar.classList.remove('open');
            backdrop.classList.remove('visible');
        });
    }

    // Close modal on overlay click
    document.querySelectorAll('.modal-overlay').forEach(function(m) {
        m.addEventListener('click', function(e) { if (e.target === m) closeModal(m.id); });
    });
});

function resetIdle() {
  idleSeconds = 0;
  hasWarnedIdle = false;
  LAST_MOUSE_MOVE = Date.now();
}
document.addEventListener("mousemove", resetIdle);
document.addEventListener("keypress", resetIdle);
document.addEventListener("click", resetIdle);
document.addEventListener("scroll", resetIdle);

function logEvent(type, msg, detail = "") {
  TELEMETRY.push({
    time: new Date().toLocaleTimeString(),
    timestamp: Date.now(),
    type: type, msg: msg, detail: detail
  });
}

function initTelemetry(mode) {
  TELEMETRY = [];
  START_TIME = Date.now();
  resetIdle();
  clearInterval(idleInterval);

  logEvent("INFO", "Start " + mode, `${CUR_P} - ${CUR_L}`);

  idleInterval = setInterval(() => {
    if (CUR_MODE === "") return;
    idleSeconds++;
    if (idleSeconds >= 60 && !hasWarnedIdle) {
      logEvent("WARNING", "Neaktivnost", "Korisnik neaktivan duže od 60s");
      hasWarnedIdle = true;
    }
  }, 1000);
}

document.addEventListener("visibilitychange", () => {
  if (document.hidden && document.getElementById('view-work').classList.contains('active')) {
    logEvent("WARNING", "Tab Switch", "Otišao sa stranice.");
    showCheatOverlay();
    setTimeout(() => {
      let overlay = document.getElementById('cheat-overlay');
      if (overlay) overlay.style.display = 'none';
    }, 3000);
  }
});

// --- NAVIGACIJA ---
function show(id) {
  document.querySelectorAll(".screen").forEach((s) => {
    s.classList.remove("active");
    if (s.id === "view-work") {
      let scrollEl = document.getElementById("content-scroll");
      if (scrollEl) scrollEl.scrollTop = 0;
    }
  });
  let tgt = document.getElementById(id);
  if (tgt) tgt.classList.add("active");
}

function goBack(t) {
  if (CUR_MODE !== "") logEvent("INFO", "Povratak na meni");
  CUR_MODE = "";
  clearInterval(idleInterval);
  clearInterval(QUESTION_TIMER);
  show(t);
}
function toggleSidebar() { document.getElementById("sidebar").classList.toggle("open"); }
function toggleTheme() { document.body.classList.toggle("light-mode"); }

// --- AUTH ---
async function doLogin() {
  let u = document.getElementById("login-user").value;
  let p = document.getElementById("login-pass").value;
  let btn = document.querySelector("#view-login .btn");
  if (btn) { btn.innerText = "PROVJERAVAM..."; btn.disabled = true; }

  try {
    let r = await fetch("/api/auth", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user: u, pw: p }),
    });
    let d = await r.json();

    if (d.ok) {
      USER = u || "Dani";
      LOGIN_TIME = Date.now();
      await loadServerData();
      if (d.role == "admin") {
        show("view-admin");
        document.getElementById("editor-area").value = JSON.stringify(SERVER_DATA, null, 4);
      } else {
        updateStatsUI();
        show("view-select");
      }
    } else { alert("KRIVO! PROBAJ OPET."); }
  } catch (e) { alert("Greška servera: " + e); }
  finally { if (btn) { btn.innerText = "KRENI S MUČENJEM"; btn.disabled = false; } }
}

async function loadServerData() {
  try {
    let r = await fetch("/api/gradivo");
    SERVER_DATA = await r.json();
  } catch (e) { SERVER_DATA = {}; }
}

function handleLogout() {
  if (CUR_MODE !== "") {
    abortSession();
  } else {
    let durationSecs = Math.floor((Date.now() - LOGIN_TIME) / 1000);
    if (durationSecs < 120 && LOGIN_TIME !== 0) {
      let doomContent = document.getElementById('doom-content');
      if (doomContent) {
        doomContent.innerHTML = `
            <b>AKTIVNO VRIJEME:</b> ${durationSecs} sekundi<br><br>
            <span style='color:#ef4444; font-weight:bold;'>KATASTROFA. Ušao si i izašao brže nego što ti treba da otvoriš TikTok!</span><br><br>
            <span style='color:#eab308; font-weight:bold;'>Zabilježen pokušaj lažiranja prisustva. Sistem te je ulovio.</span><br><br>
            <i style='color:#a1a1aa;'>Sjedi i izaberi muku, nema bježanja.</i>
        `;
        openModal('doom-modal');
      }
    } else {
      location.reload();
    }
  }
}
// --- CORE LOGIKA ---
function startLearnLesson(p, l) { CUR_P = p; CUR_L = l; startMode("LEARN"); }
function startTotalExam(p) { CUR_P = p; CUR_L = "ALL"; startMode("TEST"); }

async function startMode(m) {
  CUR_MODE = m;
  show("view-work");
  initTelemetry(m);

  QS = []; SCORE = 0; CUR_Q = 0; CUR_MODULE_IDX = 0;
  MODULE_START_TIME = 0; TOTAL_DURATION = 0; LESSON_WORD_COUNT = 0;

  document.getElementById("work-header").innerText = CUR_L === "ALL" ? "TEST ZNANJA" : CUR_L;
  const loader = document.getElementById("ai-loader");
  const content = document.getElementById("work-content");

  if (content) { content.innerHTML = ""; content.style.display = "none"; }
  if (loader) {
    loader.style.display = "block";
    let p = loader.querySelector("p");
    if (p) p.innerText = m === "TEST" ? "Sastavljam pitanja..." : "Učitavam materijale...";
  }

  const apiUrl = `/api/content?p=${encodeURIComponent(CUR_P)}&l=${encodeURIComponent(CUR_L)}&mode=${m}`;
  let d = null;
  let success = false;

  for (let i = 0; i <= MAX_RETRIES; i++) {
    try {
      let r = await fetch(apiUrl);
      if (!r.ok) throw new Error("HTTP Error " + r.status);
      d = await r.json();
      if (d.error) throw new Error(d.error);
      success = true;
      break;
    } catch (e) {
      console.warn(`Pokušaj ${i + 1} neuspio:`, e);
      if (i < MAX_RETRIES) {
        await new Promise(resolve => setTimeout(resolve, RETRY_DELAY));
      }
    }
  }

  if (loader) loader.style.display = "none";
  if (content) { content.style.display = "block"; content.classList.add("fade-in"); }

  if (success && d) {
    if (m == "LEARN") {
      if (d.modules || (Array.isArray(d) && d.length > 0)) {
        if (!d.modules && Array.isArray(d)) { d = { modules: d, cards: [] }; }
        MODULES_DATA = d;
        renderModule(0);
      } else {
        renderError("Podaci lekcije su prazni.");
      }
    } else {
      QS = d;
      nextQuestion();
    }
  } else {
    renderError("Sistem ne odgovara. Pokušaj ponovo.");
    logEvent("DANGER", "Greška u učitavanju sadržaja");
  }
}

function renderError(msg) {
  document.getElementById("work-content").innerHTML = `
      <div style="text-align:center; padding:40px;">
          <h2 style="color:var(--danger)">Greška 😞</h2>
          <p>${msg}</p>
          <button class="btn btn-primary" onclick="goBack('view-select')">NAZAD</button>
      </div>`;
}

function renderModule(idx) {
  if (MODULE_START_TIME > 0) {
    TOTAL_DURATION += (Date.now() - MODULE_START_TIME) / 1000;
  }
  CUR_MODULE_IDX = idx;
  if (!MODULES_DATA.modules) return;

  let mods = MODULES_DATA.modules;
  let currentMod = mods[idx];
  MODULE_START_TIME = Date.now();
  LESSON_WORD_COUNT += (currentMod.content || "").split(" ").length;

  let imageHTML = "";
  if (idx === 0) {
    if (MODULES_DATA.local_image) {
      imageHTML = `<div style="margin:20px 0; text-align:center;"><img src="/atlas/${MODULES_DATA.local_image}" class="atlas-img" onclick="zoomImg(this.src, 'ATLAS')"><p style="font-size:0.8rem; color:var(--text-muted);">ATLAS</p></div>`;
    } else {
      let q = encodeURIComponent(`${CUR_L} diagram`);
      imageHTML = `<div style="margin:20px 0; text-align:center;"><img src="https://tse2.mm.bing.net/th?q=${q}&w=800&c=7&rs=1&p=0" class="atlas-img" onclick="zoomImg(this.src, 'WEB')" onerror="this.style.display='none'"><p style="font-size:0.8rem; color:var(--text-muted);">ILUSTRACIJA</p></div>`;
    }
  }

  let container = document.getElementById("work-content");
  container.style.opacity = 0;
  setTimeout(() => {
    container.innerHTML = `
          <div class="subject-card" style="border-top: 4px solid var(--primary);">
              <div style="display:flex; justify-content:space-between; margin-bottom:15px;">
                  <span class="badge">DIO ${idx + 1} / ${mods.length}</span>
                  <span style="color:var(--text-muted); font-weight:bold;">${currentMod.title}</span>
              </div>
              <div style="font-size:1.1rem; line-height:1.7; white-space:pre-wrap; margin-bottom:20px;">${currentMod.content}</div>
              ${imageHTML}
              <div style="display:flex; gap:10px; margin-top:20px;">
                  ${idx > 0 ? `<button class="btn" onclick="renderModule(${idx - 1})">⏮ NAZAD</button>` : ''}
                  <div style="flex:1"></div>
                  ${idx < mods.length - 1 ? `<button class="btn btn-primary" onclick="renderModule(${idx + 1})">DALJE ➜</button>` : `<button class="btn btn-success" onclick="renderCards()">KARTICE ✅</button>`}
              </div>
          </div>`;
    container.style.opacity = 1;
    let scrollEl = document.getElementById("content-scroll");
    if (scrollEl) scrollEl.scrollTop = 0;
  }, 100);
}

function renderCards() {
  if (MODULE_START_TIME > 0) TOTAL_DURATION += (Date.now() - MODULE_START_TIME) / 1000;
  MODULE_START_TIME = 0;

  let cards = MODULES_DATA.cards || [];
  let html = `<h2 style="text-align:center; margin-bottom:20px;">KARTICE ZA PONAVLJANJE</h2>`;

  if (cards.length > 0) {
    cards.forEach((c, i) => {
      html += `<div class="subject-card" onclick="this.querySelector('.ans').style.display='block'; this.style.borderColor='var(--success)';" style="cursor:pointer; margin-bottom:10px;">
              <div style="font-weight:bold; color:var(--primary);">PITANJE ${i + 1}:</div>
              <div style="font-size:1.1rem;">${c[0]}</div>
              <div class="ans" style="display:none; margin-top:15px; padding-top:15px; border-top:1px dashed var(--border); color:var(--text);">
                  <span style="color:var(--success); font-weight:bold;">ODGOVOR:</span> ${c[1]}
              </div>
          </div>`;
    });
  } else { html += "<p style='text-align:center'>Nema kartica.</p>"; }

  html += `<button class="btn btn-primary btn-lg" onclick="finishSession(false)" style="margin-top:20px;">ZAVRŠI LEKCIJU</button>`;
  document.getElementById("work-content").innerHTML = html;
}

function nextQuestion() {
  if (CUR_Q >= QS.length) return finishSession(false);
  let q = QS[CUR_Q];

  clearInterval(QUESTION_TIMER);
  TIME_LEFT = TIME_PER_QUESTION;

  let html = `
  <div class="subject-card fade-in" id="question-card">
      <div class="timer-container"><div id="timer-bar" class="timer-fill"></div></div>
      <div style="display:flex; justify-content:space-between; margin-bottom:15px;">
          <h3>Pitanje ${CUR_Q + 1} / ${QS.length}</h3>
          <span class="badge" id="timer-text">${TIME_LEFT}s</span>
      </div>
      <div style="font-size:1.2rem; margin-bottom:20px; font-weight:bold;">${q.q}</div>
      <div id="opts" style="display:flex; flex-direction:column; gap:10px;"></div>
      <div id="feedback-area"></div>
  </div>`;
  document.getElementById("work-content").innerHTML = html;

  let optsContainer = document.getElementById("opts");
  if (q.t == "radio") {
    q.o.forEach((o) => {
      let b = document.createElement("button");
      b.className = "btn option-btn"; b.innerText = o;
      b.onclick = () => submitAnswer(o, q.a);
      optsContainer.appendChild(b);
    });
  } else {
    optsContainer.innerHTML = `<div class="input-group"><input type="text" id="ans" placeholder=" " autocomplete="off"><label>Tvoj odgovor</label></div><button class="btn btn-primary" id="confirm-btn">POTVRDI</button>`;
    document.getElementById("confirm-btn").addEventListener("click", () => submitAnswer(document.getElementById('ans').value, q.a));
    document.getElementById("ans").addEventListener("keypress", function (e) { if (e.key === "Enter") submitAnswer(this.value, q.a); });
  }
  startTimer();
}

function startTimer() {
  const bar = document.getElementById("timer-bar");
  const text = document.getElementById("timer-text");
  const card = document.getElementById("question-card");
  const timerContainer = document.getElementById("timer-container");

  if (bar) bar.style.backgroundColor = "var(--primary)";
  if (card) card.classList.remove("drama-mode");
  if (timerContainer) timerContainer.style.display = "block";

  updateTimerBar(TIME_LEFT, TIME_PER_QUESTION);

  QUESTION_TIMER = setInterval(() => {
    TIME_LEFT--;
    if (text) text.innerText = TIME_LEFT + "s";
    if (bar) bar.style.width = (TIME_LEFT / TIME_PER_QUESTION) * 100 + "%";

    updateTimerBar(TIME_LEFT, TIME_PER_QUESTION);

    if (TIME_LEFT <= 10 && card && bar) {
      card.classList.add("drama-mode");
      bar.style.backgroundColor = "red";
    }
    if (TIME_LEFT <= 0) {
      clearInterval(QUESTION_TIMER);
      submitAnswer("TIMEOUT", QS[CUR_Q].a);
    }
  }, 1000);
}

async function submitAnswer(u, a) {
  clearInterval(QUESTION_TIMER);
  let timeSpent = TIME_PER_QUESTION - TIME_LEFT;
  TOTAL_DURATION += timeSpent;

  let opts = document.getElementById("opts");
  if (opts) { opts.style.pointerEvents = "none"; opts.style.opacity = "0.6"; }

  let userDisplay = u === "TIMEOUT" ? "⏰ ISTEKLO VRIJEME" : (u || "Prazno");
  // Escape HTML entities to prevent XSS
  let safeUserDisplay = userDisplay.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  let safeAnswer = String(a).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  let score = 0;

  if (u !== "TIMEOUT") {
    try {
      let r = await fetch("/api/grade", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ q: QS[CUR_Q].q, a: a, u: u }),
      });
      let d = await r.json();
      score = d.score;
    } catch (e) { score = 0; }
  }
  SCORE += score;

  let result = score >= 1.0 ? 'CORRECT' : (score >= 0.5 ? 'PARTIAL' : 'WRONG');

  showAnswerFeedback(result, a, userDisplay);

  let feedbackHtml = `
  <div class="feedback-box ${score >= 0.5 ? 'fb-correct' : 'fb-wrong'}">
      <h2 style="margin:0">${score >= 0.5 ? '✅ TOČNO' : '❌ KRIVO'}</h2>
      <div style="margin:15px 0; text-align:left;">
          <p style="margin:5px 0; color:var(--text-muted);">Tvoj odgovor:</p>
          <div style="font-size:1.1rem; font-weight:bold;">${safeUserDisplay}</div>
          ${score < 0.5 ? `<hr style="border-color:rgba(0,0,0,0.1); margin:10px 0;"><p style="margin:5px 0; color:var(--text-muted);">Točan odgovor:</p><div style="font-size:1.1rem; font-weight:bold;">${safeAnswer}</div>` : ''}
      </div>
      <button class="btn btn-primary" onclick="CUR_Q++; nextQuestion()" id="next-btn">${CUR_Q < QS.length - 1 ? 'SLJEDEĆE ➜' : 'KRAJ 🏁'}</button>
  </div>`;

  let fbArea = document.getElementById("feedback-area");
  if (fbArea) {
    fbArea.innerHTML = feedbackHtml;
    fbArea.scrollIntoView({ behavior: "smooth" });
  }
  setTimeout(() => { let b = document.getElementById("next-btn"); if (b) b.focus(); }, 100);
}
async function abortSession() {
  logEvent("WARNING", "Odustajanje", "Pobjegao ko kukavica.");
  await finishSession(true);
}

async function finishSession(aborted = false) {
  clearInterval(idleInterval);
  clearInterval(QUESTION_TIMER);

  if (CUR_MODE === 'LEARN' && MODULE_START_TIME > 0) {
    TOTAL_DURATION += (Date.now() - MODULE_START_TIME) / 1000;
    MODULE_START_TIME = 0;
  }

  let max_score = (CUR_MODE === 'TEST' && QS.length > 0) ? QS.length : 1;
  let s = aborted ? 0 : (CUR_MODE === 'LEARN' ? 100 : (SCORE / max_score) * 100);

  try {
    let r = await fetch("/api/save", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        student: USER, score_percent: s, telemetry: TELEMETRY,
        mode: CUR_MODE, duration: TOTAL_DURATION, word_count: LESSON_WORD_COUNT,
        subject: CUR_P, lesson: CUR_L, rushed: aborted
      }),
    });
    let resp = await r.json();

    if (resp.report) {
      let doomContent = document.getElementById('doom-content');
      if (doomContent) {
        doomContent.innerHTML = sanitizeHTML(resp.report);
        openModal('doom-modal');
      }
    }

    let html = `<div class="subject-card" style="text-align:center; padding:40px;">`;
    if (resp.rushed || aborted) {
      html += `<h1 style="color:var(--danger);">0 XP</h1><h3>🚨 ALARM!</h3><p>Prebrzo ili odustao! (${TOTAL_DURATION.toFixed(0)}s)</p>`;
    } else {
      html += `<h1 style="color:var(--success);">+${resp.xp_gained} XP</h1>
               <h3>${CUR_MODE === 'TEST' ? (s > 50 ? "PROLAZ!" : "PAD!") : "LEKCIJA GOTOVA!"}</h3>
               <p>Čin: <b style="color:var(--primary);">${resp.new_rank}</b></p>`;

      if (resp.medals && resp.medals.length > 0) {
        html += `<div style="margin-top:20px; padding:20px; background:rgba(255,215,0,0.05); border-radius:15px; border:1px solid gold;">
                 <h3 style="color:#FFD700; margin-bottom:20px;">🏆 NOVO POSTIGNUĆE!</h3>
                 <div style="display:flex; justify-content:center; flex-wrap:wrap; gap:15px;">`;
        resp.medals.forEach(m => {
          let iconHtml = MEDAL_ICONS[m] || '🏅';
          let name = MEDAL_DETAILS[m] ? MEDAL_DETAILS[m].name : m;
          html += `<div class="medal-container fade-in">${iconHtml}<div style="font-weight:bold; color:#fff; margin-top:5px;">${name}</div></div>`;
        });
        html += `</div></div>`;
      }
    }
    html += `<button class="btn btn-primary btn-lg" onclick="goBack('view-select')" style="margin-top:30px;">NASTAVI</button></div>`;

    document.getElementById("work-content").innerHTML = html;
    updateStatsUI();

  } catch (e) {
    console.error(e);
    alert("Greška pri spremanju. Server nije dostupan.");
    goBack('view-select');
  }
}

// --- UTILS ---
function updateStatsUI() {
  fetch("/api/stats").then(r => r.json()).then(d => {
    let elLvl = document.getElementById("xp-lvl");
    let elPts = document.getElementById("xp-points");
    let elRank = document.getElementById("xp-rank");

    if (elLvl) elLvl.innerText = d.lvl;
    if (elPts) elPts.innerText = d.xp + " XP";
    if (elRank && d.rank_title) elRank.innerText = d.rank_title;

    let fill = document.querySelector(".xp-fill");
    if (fill) fill.style.width = `${Math.min((d.xp % 500) / 500 * 100, 100)}%`;

    renderXPBar(d.xp || 0);

    if (d.medals) {
      let badgesHtml = d.medals.map(m => `<span style="margin-right:5px; font-size:1.2rem;">${MEDAL_ICONS[m] || '🏅'}</span>`).join("");
      let bc = document.getElementById("user-badges");
      if (bc) bc.innerHTML = badgesHtml;
    }
  }).catch(e => console.log("Stats fetch fail"));
}

function zoomImg(s, type) {
  let tgt = document.getElementById("img-zoom-target");
  let mod = document.getElementById("img-modal");
  if (tgt && mod) {
    tgt.src = s;
    mod.style.display = "flex";
  }
}

// Admin
async function saveAdminData() { try { let d = JSON.parse(document.getElementById("editor-area").value); await fetch("/api/admin/save", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(d) }); alert("Spremljeno!"); location.reload(); } catch (e) { alert("JSON Error!"); } }
async function adminLoadLogs() { let r = await fetch("/api/admin/logs/list", { method: "POST" }); let d = await r.json(); let container = document.getElementById("admin-logs-list"); if (d.files) { container.innerHTML = ''; d.files.forEach(f => { let div = document.createElement('div'); div.textContent = '📄 ' + f; div.style.cursor = 'pointer'; div.addEventListener('click', () => adminViewLog(f)); container.appendChild(div); }); } else { container.innerHTML = "Nema logova."; } }
async function adminViewLog(f) { let r = await fetch("/api/admin/logs/read", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ filename: f }) }); let d = await r.json(); document.getElementById("log-content").innerText = JSON.stringify(d.data, null, 2); openModal('log-modal'); }

function toggleFloatingCalc() {
  let f = document.getElementById("floating-calc");
  if (f) f.style.display = f.style.display == "block" ? "none" : "block";
}
function cIn(v) {
  let d = document.getElementById("fc-disp");
  if (d) d.innerText = d.innerText == "0" ? v : d.innerText + v;
}
function cClr() {
  let d = document.getElementById("fc-disp");
  if (d) d.innerText = "0";
}
function cCalc() {
  let d = document.getElementById("fc-disp");
  if (d) {
    try {
      // Safe math evaluation without eval()
      let expr = d.innerText.replace(/[^0-9+\-*/.() ]/g, '');
      d.innerText = Function('"use strict"; return (' + expr + ')')();
    }
    catch (e) { d.innerText = "ERR"; }
  }
}

function openTrophyRoom() {
  fetch("/api/stats").then(r => r.json()).then(d => {
    let goodHtml = "", badHtml = "";
    if (d.medals) {
      d.medals.forEach(mCode => {
        let info = MEDAL_DETAILS[mCode] || { name: mCode, desc: "", type: "good" };
        let icon = MEDAL_ICONS[mCode] || '🏅';
        let card = `<div class="trophy-card ${info.type === 'bad' ? 't-bad' : 't-good'}">${icon}<b>${info.name}</b><small>${info.desc}</small></div>`;
        if (info.type === 'bad') badHtml += card; else goodHtml += card;
      });
    }
    let goodL = document.getElementById("trophy-list-good");
    let badL = document.getElementById("trophy-list-bad");
    if (goodL) goodL.innerHTML = goodHtml || "<p>Prazno.</p>";
    if (badL) badL.innerHTML = badHtml || "<p>Čisto.</p>";
    let m = document.getElementById("trophy-modal");
    if (m) openModal('trophy-modal');
  }).catch(e => console.log(e));
}

function openPSE() {
  logEvent("INFO", "Otvorio PSE", "");
  let m = document.getElementById("pse-modal");
  if (m) openModal('pse-modal');

  const c = document.getElementById("pse-grid-container");
  if (!c || c.innerHTML.trim() !== "") return;

  const els = [
    ["H", "g-nonmetal", 1, "Vodik", "1.008", "Nemetal"], "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ["He", "g-noble", 2, "Helij", "4.002", "Plemeniti plin"],
    ["Li", "g-alkali", 3, "Litij", "6.94", "Alkalni metal"], ["Be", "g-alkaline", 4, "Berilij", "9.012", "Zemnoalkalni"], "", "", "", "", "", "", "", "", "", "", ["B", "g-semi", 5, "Bor", "10.81", "Polumetal"], ["C", "g-nonmetal", 6, "Ugljik", "12.01", "Nemetal"], ["N", "g-nonmetal", 7, "Dušik", "14.00", "Nemetal"], ["O", "g-nonmetal", 8, "Kisik", "15.99", "Nemetal"], ["F", "g-halogen", 9, "Fluor", "18.99", "Halogen"], ["Ne", "g-noble", 10, "Neon", "20.18", "Plemeniti plin"],
    ["Na", "g-alkali", 11, "Natrij", "22.99", "Alkalni metal"], ["Mg", "g-alkaline", 12, "Magnezij", "24.30", "Zemnoalkalni"], "", "", "", "", "", "", "", "", "", "", ["Al", "g-basic", 13, "Aluminij", "26.98", "Metal"], ["Si", "g-semi", 14, "Silicij", "28.08", "Polumetal"], ["P", "g-nonmetal", 15, "Fosfor", "30.97", "Nemetal"], ["S", "g-nonmetal", 16, "Sumpor", "32.06", "Nemetal"], ["Cl", "g-halogen", 17, "Klor", "35.45", "Halogen"], ["Ar", "g-noble", 18, "Argon", "39.95", "Plemeniti plin"],
    ["K", "g-alkali", 19, "Kalij", "39.10", "Alkalni metal"], ["Ca", "g-alkaline", 20, "Kalcij", "40.08", "Zemnoalkalni"], ["Sc", "g-transition", 21, "Skandij", "44.96", "Prijelazni"], ["Ti", "g-transition", 22, "Titanij", "47.87", "Prijelazni"], ["V", "g-transition", 23, "Vanadij", "50.94", "Prijelazni"], ["Cr", "g-transition", 24, "Krom", "52.00", "Prijelazni"], ["Mn", "g-transition", 25, "Mangan", "54.94", "Prijelazni"], ["Fe", "g-transition", 26, "Željezo", "55.85", "Prijelazni"], ["Co", "g-transition", 27, "Kobalt", "58.93", "Prijelazni"], ["Ni", "g-transition", 28, "Nikal", "58.69", "Prijelazni"], ["Cu", "g-transition", 29, "Bakar", "63.55", "Prijelazni"], ["Zn", "g-transition", 30, "Cink", "65.38", "Prijelazni"], ["Ga", "g-basic", 31, "Galij", "69.72", "Metal"], ["Ge", "g-semi", 32, "Germanij", "72.63", "Polumetal"], ["As", "g-semi", 33, "Arsen", "74.92", "Polumetal"], ["Se", "g-nonmetal", 34, "Selenij", "78.96", "Nemetal"], ["Br", "g-halogen", 35, "Brom", "79.90", "Halogen"], ["Kr", "g-noble", 36, "Kripton", "83.79", "Plemeniti plin"],
    ["Rb", "g-alkali", 37, "Rubidij", "85.47", "Alkalni"], ["Sr", "g-alkaline", 38, "Stroncij", "87.62", "Zemnoalkalni"], ["Y", "g-transition", 39, "Itrij", "88.91", "Prijelazni"], ["Zr", "g-transition", 40, "Cirkonij", "91.22", "Prijelazni"], ["Nb", "g-transition", 41, "Niobij", "92.91", "Prijelazni"], ["Mo", "g-transition", 42, "Molibden", "95.96", "Prijelazni"], ["Tc", "g-transition", 43, "Tehnecij", "98", "Prijelazni"], ["Ru", "g-transition", 44, "Rutenij", "101.1", "Prijelazni"], ["Rh", "g-transition", 45, "Rodij", "102.9", "Prijelazni"], ["Pd", "g-transition", 46, "Paladij", "106.4", "Prijelazni"], ["Ag", "g-transition", 47, "Srebro", "107.9", "Prijelazni"], ["Cd", "g-transition", 48, "Kadmij", "112.4", "Prijelazni"], ["In", "g-basic", 49, "Indij", "114.8", "Metal"], ["Sn", "g-basic", 50, "Kositar", "118.7", "Metal"], ["Sb", "g-semi", 51, "Antimon", "121.8", "Polumetal"], ["Te", "g-semi", 52, "Telurij", "127.6", "Polumetal"], ["I", "g-halogen", 53, "Jod", "126.9", "Halogen"], ["Xe", "g-noble", 54, "Ksenon", "131.3", "Plemeniti"],
    ["Cs", "g-alkali", 55, "Cezij", "132.9", "Alkalni"], ["Ba", "g-alkaline", 56, "Barij", "137.3", "Zemnoalkalni"], ["*", "g-lanthanoid", "57-71", "Lantanoidi", "", "Lantanoidi"], ["Hf", "g-transition", 72, "Hafnij", "178.5", "Prijelazni"], ["Ta", "g-transition", 73, "Tantal", "180.9", "Prijelazni"], ["W", "g-transition", 74, "Volfram", "183.8", "Prijelazni"], ["Re", "g-transition", 75, "Renij", "186.2", "Prijelazni"], ["Os", "g-transition", 76, "Osmij", "190.2", "Prijelazni"], ["Ir", "g-transition", 77, "Iridij", "192.2", "Prijelazni"], ["Pt", "g-transition", 78, "Platina", "195.1", "Prijelazni"], ["Au", "g-transition", 79, "Zlato", "197.0", "Prijelazni"], ["Hg", "g-transition", 80, "Živa", "200.6", "Prijelazni"], ["Tl", "g-basic", 81, "Talij", "204.4", "Metal"], ["Pb", "g-basic", 82, "Olovo", "207.2", "Metal"], ["Bi", "g-basic", 83, "Bizmut", "209.0", "Metal"], ["Po", "g-semi", 84, "Polonij", "209", "Polumetal"], ["At", "g-halogen", 85, "Astat", "210", "Halogen"], ["Rn", "g-noble", 86, "Radon", "222", "Plemeniti"],
    ["Fr", "g-alkali", 87, "Francij", "223", "Alkalni"], ["Ra", "g-alkaline", 88, "Radij", "226", "Zemnoalkalni"], ["**", "g-actinoid", "89-103", "Aktinoidi", "", "Aktinoidi"], ["Rf", "g-transition", 104, "Rutherfordij", "267", "Prijelazni"], ["Db", "g-transition", 105, "Dubnij", "268", "Prijelazni"], ["Sg", "g-transition", 106, "Seaborgij", "271", "Prijelazni"], ["Bh", "g-transition", 107, "Bohrij", "272", "Prijelazni"], ["Hs", "g-transition", 108, "Hassij", "270", "Prijelazni"], ["Mt", "g-transition", 109, "Meitnerij", "276", "Prijelazni"], ["Ds", "g-transition", 110, "Darmštatij", "281", "Prijelazni"], ["Rg", "g-transition", 111, "Roentgenij", "280", "Prijelazni"], ["Cn", "g-transition", 112, "Kopernicij", "285", "Prijelazni"], ["Nh", "g-basic", 113, "Nihonij", "284", "Metal"], ["Fl", "g-basic", 114, "Flerovij", "289", "Metal"], ["Mc", "g-basic", 115, "Moskovij", "288", "Metal"], ["Lv", "g-basic", 116, "Livermorij", "293", "Metal"], ["Ts", "g-halogen", 117, "Tenesi", "294", "Halogen"], ["Og", "g-noble", 118, "Oganes", "294", "Plemeniti"]
  ];

  els.forEach((e) => {
    let d = document.createElement("div");
    if (e === "") {
      d.className = "pse-empty";
    } else if (Array.isArray(e)) {
      d.className = `pse-cell ${e[1]}`;
      d.innerHTML = `<span class='pse-num'>${e[2]}</span><span class='pse-sym'>${e[0]}</span>`;

      d.onmouseenter = () => {
        const panel = document.getElementById("pse-info-panel");
        if (panel) {
          document.getElementById("pi-sym").innerText = e[0];
          document.getElementById("pi-name").innerText = e[3] || e[0];
          document.getElementById("pi-data").innerText = `Masa: ${e[4] || "?"} | Atomski broj: ${e[2]}`;
          document.getElementById("pi-cat").innerText = e[5] || e[1].replace("g-", "");

          panel.className = e[1];
          panel.style.borderLeft = "5px solid rgba(255,255,255,0.5)";
          panel.style.paddingLeft = "10px";
        }
      };
    } else {
      d.className = "pse-cell";
      d.innerText = e;
    }
    c.appendChild(d);
  });
}

// DRAG EVENT ZA KALKULATOR
let isDragging = false;
let dragStartX, dragStartY;
const calcEl = document.getElementById("floating-calc");
const calcHeader = document.getElementById("fc-header");

if (calcHeader && calcEl) {
  calcHeader.addEventListener('mousedown', (e) => {
    isDragging = true;
    dragStartX = e.clientX - calcEl.offsetLeft;
    dragStartY = e.clientY - calcEl.offsetTop;
  });

  document.addEventListener('mousemove', (e) => {
    if (isDragging) {
      calcEl.style.left = `${e.clientX - dragStartX}px`;
      calcEl.style.top = `${e.clientY - dragStartY}px`;
    }
  });

  document.addEventListener('mouseup', () => {
    isDragging = false;
  });
}
