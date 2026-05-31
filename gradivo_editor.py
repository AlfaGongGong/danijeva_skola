"""
gradivo_editor.py — Standalone alat za dodavanje gradiva.
Pokretanje: python gradivo_editor.py
Otvori: http://localhost:5001
"""

import os
import json
import logging
import time
import re
import sqlite3
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv

load_dotenv()

# =====================================================================
# KONFIGURACIJA
# =====================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GRADIVO_FILE = os.path.join(BASE_DIR, "gradivo.json")
DB_FILE = os.path.join(BASE_DIR, "skola.db")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

MODEL_CANDIDATES = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
]

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("GradivoEditor")

# =====================================================================
# AI KLIJENT
# =====================================================================
ai_client = None
MODEL_ID = MODEL_CANDIDATES[0]

if GOOGLE_API_KEY:
    try:
        from google import genai

        ai_client = genai.Client(api_key=GOOGLE_API_KEY)
        # Brza detekcija radnog modela
        for candidate in MODEL_CANDIDATES:
            try:
                r = ai_client.models.generate_content(model=candidate, contents="OK?")
                if r and r.text:
                    MODEL_ID = candidate
                    logger.info(f"[AI] Aktivan model: {MODEL_ID}")
                    break
            except Exception:
                continue
    except Exception as e:
        logger.error(f"[AI] Init greška: {e}")

# =====================================================================
# POMOĆNE FUNKCIJE
# =====================================================================


def load_gradivo():
    if not os.path.exists(GRADIVO_FILE):
        return {}
    with open(GRADIVO_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_gradivo(data):
    with open(GRADIVO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def db_upsert_lesson(subject, topic, content_text):
    """Dodaje ili ažurira lekciju u SQLite bazi bez restarta."""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        # Provjeri postoji li već AI-generisan sadržaj (ne želimo ga prepisati sirovim tekstom)
        c.execute(
            "SELECT content FROM lessons WHERE subject=? AND topic=?", (subject, topic)
        )
        row = c.fetchone()
        if row:
            existing = row["content"] or ""
            # Ako već ima validan AI JSON (modules+cards), ne diraj ga
            if existing.strip().startswith("{"):
                try:
                    parsed = json.loads(existing)
                    if "modules" in parsed and "cards" in parsed:
                        conn.close()
                        return "exists_ai"  # Već ima AI sadržaj
                except Exception:
                    pass
            # Inače ažuriraj s novim sirovim tekstom
            c.execute(
                "UPDATE lessons SET content=? WHERE subject=? AND topic=?",
                (content_text, subject, topic),
            )
        else:
            c.execute(
                "INSERT INTO lessons (subject, topic, content) VALUES (?, ?, ?)",
                (subject, topic, content_text),
            )
        conn.commit()
        conn.close()
        return "ok"
    except Exception as e:
        logger.error(f"[DB] Greška: {e}")
        return f"error: {e}"


def extract_json_safe(text):
    """Pokušava izvući JSON iz AI odgovora."""
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    for pattern in [r"```json\s*([\s\S]*?)\s*```", r"```\s*([\s\S]*?)\s*```"]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except Exception:
                pass
    # Heuristika
    for sc, ec in [("{", "}"), ("[", "]")]:
        si, ei = text.find(sc), text.rfind(ec)
        if si != -1 and ei > si:
            try:
                return json.loads(text[si : ei + 1])
            except Exception:
                pass
    return None


def ai_struktura_gradivo(raw_text, subject, topic):
    """
    AI parsira sirovi tekst u strukturirani kontekst za gradivo.json.
    Vraća čisti tekst (string) — format koji gradivo.json koristi.
    """
    if not ai_client:
        return None

    prompt = f"""
Ti si asistent koji strukturira školsko gradivo za predmet "{subject}", tema "{topic}".

ULAZNI TEKST (kopiran/ukucan):
{raw_text}

ZADATAK:
Pretvori ovaj tekst u strukturirani, informativan sažetak koji će se koristiti kao kontekst za AI generiranje lekcija.
Format: jedan dugi string koji sadrži SVE ključne informacije, definicije, formule, primjere i činjenice iz teksta.
Koristiti CAPS i kratice za naslove sekcija (npr. "DEFINICIJA:", "PRIMJERI:", "FORMULA:").
Sačuvaj sve brojeve, formule i specifične podatke.
Nemoj gubiti informacije — budi sveobuhvatan.

VRATI ISKLJUČIVO čisti tekst (string), bez JSON-a, bez markdown-a, bez objašnjenja.
"""
    try:
        resp = ai_client.models.generate_content(model=MODEL_ID, contents=prompt)
        return resp.text.strip() if resp and resp.text else None
    except Exception as e:
        logger.error(f"[AI] Greška pri strukturiranju: {e}")
        return None


def ai_predlozi_teme(raw_text, subject):
    """AI analizira tekst i predlaže podjelu na lekcije/teme."""
    if not ai_client:
        return []

    prompt = f"""
Analiziraj ovaj školski tekst za predmet "{subject}" i predloži logičnu podjelu na lekcije.

TEKST:
{raw_text[:3000]}

Vrati JSON listu objekata. Svaki objekt ima:
- "topic": naziv teme (npr. "L1: Naziv teme")
- "summary": kratki opis što ta tema pokriva (1-2 rečenice)

VRATI ISKLJUČIVO JSON listu, bez ikakvog drugog teksta:
[{{"topic": "L1: ...", "summary": "..."}}, ...]
"""
    try:
        resp = ai_client.models.generate_content(model=MODEL_ID, contents=prompt)
        result = extract_json_safe(resp.text if resp else "")
        return result if isinstance(result, list) else []
    except Exception as e:
        logger.error(f"[AI] Greška pri prijedlogu tema: {e}")
        return []


# =====================================================================
# FLASK APP
# =====================================================================
app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="hr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GRADIVO EDITOR</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap" rel="stylesheet">
<style>
:root {
    --bg: #0d0d0f;
    --surface: #141418;
    --surface2: #1c1c22;
    --border: #2a2a35;
    --accent: #7fff6e;
    --accent2: #6e9fff;
    --danger: #ff6e6e;
    --warn: #ffbe6e;
    --text: #e8e8f0;
    --muted: #6b6b80;
    --mono: 'Space Mono', monospace;
    --sans: 'Syne', sans-serif;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    min-height: 100vh;
    padding: 0;
}

/* Scanline efekt */
body::before {
    content: '';
    position: fixed;
    inset: 0;
    background: repeating-linear-gradient(
        0deg,
        transparent,
        transparent 2px,
        rgba(0,0,0,0.03) 2px,
        rgba(0,0,0,0.03) 4px
    );
    pointer-events: none;
    z-index: 9999;
}

header {
    border-bottom: 1px solid var(--border);
    padding: 18px 32px;
    display: flex;
    align-items: center;
    gap: 16px;
    background: var(--surface);
}

.logo {
    font-family: var(--mono);
    font-size: 11px;
    color: var(--accent);
    letter-spacing: 3px;
    text-transform: uppercase;
}

.logo span { color: var(--muted); }

.model-badge {
    margin-left: auto;
    font-family: var(--mono);
    font-size: 10px;
    color: var(--muted);
    background: var(--surface2);
    border: 1px solid var(--border);
    padding: 4px 10px;
    border-radius: 4px;
}

.model-badge b { color: var(--accent2); }

.layout {
    display: grid;
    grid-template-columns: 340px 1fr;
    height: calc(100vh - 57px);
}

/* LEFT PANEL */
.left {
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: var(--surface);
}

.panel-title {
    font-family: var(--mono);
    font-size: 9px;
    letter-spacing: 3px;
    color: var(--muted);
    text-transform: uppercase;
    padding: 14px 20px 10px;
    border-bottom: 1px solid var(--border);
}

.subjects-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
}

.subject-group { margin-bottom: 4px; }

.subject-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    cursor: pointer;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 700;
    color: var(--text);
    transition: background 0.15s;
    user-select: none;
}
.subject-header:hover { background: var(--surface2); }
.subject-header .chevron { font-size: 10px; color: var(--muted); transition: transform 0.2s; }
.subject-header.open .chevron { transform: rotate(90deg); }
.subject-header .count {
    margin-left: auto;
    font-family: var(--mono);
    font-size: 9px;
    color: var(--muted);
    background: var(--surface2);
    border: 1px solid var(--border);
    padding: 2px 7px;
    border-radius: 3px;
}

.topics-list { display: none; padding-left: 12px; }
.topics-list.open { display: block; }

.topic-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 10px;
    margin: 1px 0;
    border-radius: 5px;
    font-size: 12px;
    color: var(--muted);
    cursor: pointer;
    transition: all 0.15s;
    border-left: 2px solid transparent;
    font-family: var(--mono);
}
.topic-item:hover { background: var(--surface2); color: var(--text); border-left-color: var(--border); }
.topic-item.has-ai { color: var(--accent); border-left-color: var(--accent); }
.topic-item.has-raw { color: var(--warn); border-left-color: var(--warn); }
.topic-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.topic-item.has-ai .topic-dot { background: var(--accent); }
.topic-item.has-raw .topic-dot { background: var(--warn); }

.left-footer {
    padding: 12px;
    border-top: 1px solid var(--border);
}

.legend {
    display: flex;
    gap: 14px;
    font-family: var(--mono);
    font-size: 9px;
    color: var(--muted);
}
.legend-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; margin-right: 4px; }

/* RIGHT PANEL */
.right {
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.editor-header {
    padding: 16px 28px;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
    display: flex;
    align-items: center;
    gap: 12px;
}

.step-indicator {
    display: flex;
    gap: 6px;
    align-items: center;
    font-family: var(--mono);
    font-size: 10px;
    color: var(--muted);
}

.step {
    padding: 3px 10px;
    border-radius: 3px;
    border: 1px solid var(--border);
    transition: all 0.2s;
}
.step.active { background: var(--accent); color: #000; border-color: var(--accent); font-weight: 700; }
.step.done { border-color: var(--accent); color: var(--accent); }
.step-arrow { color: var(--border); }

.editor-body {
    flex: 1;
    overflow-y: auto;
    padding: 28px;
}

/* FORM ELEMENTS */
.form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 20px;
}

.field { display: flex; flex-direction: column; gap: 6px; }

label {
    font-family: var(--mono);
    font-size: 10px;
    letter-spacing: 2px;
    color: var(--muted);
    text-transform: uppercase;
}

input[type="text"], textarea, select {
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 10px 14px;
    border-radius: 6px;
    font-family: var(--mono);
    font-size: 13px;
    outline: none;
    transition: border-color 0.2s;
    width: 100%;
}
input[type="text"]:focus, textarea:focus, select:focus {
    border-color: var(--accent2);
}
select option { background: var(--surface2); }

textarea {
    resize: vertical;
    min-height: 180px;
    line-height: 1.6;
}

/* BUTTONS */
.btn-row { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 8px; }

.btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 10px 20px;
    border-radius: 6px;
    border: none;
    font-family: var(--mono);
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 1px;
    cursor: pointer;
    transition: all 0.15s;
    text-transform: uppercase;
}
.btn:disabled { opacity: 0.4; cursor: not-allowed; }

.btn-primary { background: var(--accent); color: #000; }
.btn-primary:hover:not(:disabled) { background: #a0ffaa; }

.btn-secondary { background: transparent; border: 1px solid var(--border); color: var(--text); }
.btn-secondary:hover:not(:disabled) { border-color: var(--accent2); color: var(--accent2); }

.btn-danger { background: transparent; border: 1px solid var(--danger); color: var(--danger); }
.btn-danger:hover:not(:disabled) { background: var(--danger); color: #000; }

.btn-warn { background: transparent; border: 1px solid var(--warn); color: var(--warn); }
.btn-warn:hover:not(:disabled) { background: var(--warn); color: #000; }

/* TOPICS SUGGEST */
.topics-suggest {
    margin-top: 16px;
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
}

.topics-suggest-header {
    padding: 10px 16px;
    background: var(--surface2);
    font-family: var(--mono);
    font-size: 10px;
    color: var(--muted);
    letter-spacing: 2px;
}

.topic-suggestion {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 16px;
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    transition: background 0.15s;
}
.topic-suggestion:last-child { border-bottom: none; }
.topic-suggestion:hover { background: var(--surface2); }
.topic-suggestion.selected { background: rgba(127,255,110,0.08); }

.topic-suggestion input[type="checkbox"] { accent-color: var(--accent); width: 14px; height: 14px; }
.topic-name { font-family: var(--mono); font-size: 12px; color: var(--text); font-weight: 700; }
.topic-summary { font-size: 12px; color: var(--muted); margin-top: 2px; }

/* PREVIEW */
.preview-box {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    margin-top: 16px;
    font-family: var(--mono);
    font-size: 11px;
    color: var(--muted);
    line-height: 1.7;
    max-height: 200px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-word;
}

/* LOG */
.log-box {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px;
    font-family: var(--mono);
    font-size: 11px;
    line-height: 1.8;
    max-height: 160px;
    overflow-y: auto;
}

.log-entry { display: flex; gap: 10px; }
.log-time { color: var(--muted); flex-shrink: 0; }
.log-ok { color: var(--accent); }
.log-err { color: var(--danger); }
.log-info { color: var(--accent2); }
.log-warn { color: var(--warn); }

/* SPINNER */
.spinner {
    width: 14px; height: 14px;
    border: 2px solid rgba(255,255,255,0.2);
    border-top-color: currentColor;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* SECTION */
.section {
    margin-bottom: 28px;
}
.section-title {
    font-family: var(--mono);
    font-size: 9px;
    letter-spacing: 3px;
    color: var(--muted);
    text-transform: uppercase;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 10px;
}
.section-title::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border);
}

.divider { height: 1px; background: var(--border); margin: 24px 0; }

/* STATUS CHIPS */
.chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 10px;
    border-radius: 20px;
    font-family: var(--mono);
    font-size: 10px;
    font-weight: 700;
}
.chip-ok { background: rgba(127,255,110,0.12); color: var(--accent); border: 1px solid rgba(127,255,110,0.3); }
.chip-warn { background: rgba(255,190,110,0.12); color: var(--warn); border: 1px solid rgba(255,190,110,0.3); }
.chip-err { background: rgba(255,110,110,0.12); color: var(--danger); border: 1px solid rgba(255,110,110,0.3); }

/* SCROLLBAR */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-track { background: transparent; }
</style>
</head>
<body>

<header>
    <div class="logo">⚡ <span>DANIJEVA ŠKOLICA /</span> GRADIVO EDITOR</div>
    <div class="model-badge">AI: <b id="model-name">detektujem...</b></div>
</header>

<div class="layout">

    <!-- LEFT: Pregled gradiva -->
    <div class="left">
        <div class="panel-title">Trenutno gradivo</div>
        <div class="subjects-list" id="subjects-list">
            <div style="padding:20px;font-family:var(--mono);font-size:11px;color:var(--muted)">Učitavam...</div>
        </div>
        <div class="left-footer">
            <div class="legend">
                <span><span class="legend-dot" style="background:var(--accent);"></span>AI sadržaj</span>
                <span><span class="legend-dot" style="background:var(--warn);"></span>Sirovi tekst</span>
                <span><span class="legend-dot" style="background:var(--muted);"></span>Prazno</span>
            </div>
        </div>
    </div>

    <!-- RIGHT: Editor -->
    <div class="right">
        <div class="editor-header">
            <div class="step-indicator">
                <div class="step active" id="step1">1 UNOS</div>
                <div class="step-arrow">→</div>
                <div class="step" id="step2">2 AI ANALIZA</div>
                <div class="step-arrow">→</div>
                <div class="step" id="step3">3 SPREMI</div>
            </div>
        </div>

        <div class="editor-body">

            <!-- KORAK 1: UNOS -->
            <div id="phase-input">
                <div class="section">
                    <div class="section-title">Predmet i tema</div>
                    <div class="form-row">
                        <div class="field">
                            <label>Predmet</label>
                            <select id="subject-select" onchange="onSubjectChange()">
                                <option value="">-- odaberi ili upiši novo --</option>
                            </select>
                        </div>
                        <div class="field">
                            <label>Novi predmet (ako ne postoji)</label>
                            <input type="text" id="subject-new" placeholder="npr. Fizika">
                        </div>
                    </div>
                    <div class="field">
                        <label>Naziv teme / lekcije</label>
                        <input type="text" id="topic-input" placeholder="npr. L3: Sila i zakoni gibanja">
                    </div>
                </div>

                <div class="section">
                    <div class="section-title">Tekst gradiva</div>
                    <div class="field">
                        <label>Zalijepite ili ukucajte tekst</label>
                        <textarea id="raw-text" placeholder="Zalijepite tekst iz udžbenika, worda, AI chata...&#10;&#10;Ne mora biti savršeno formatiran — AI će ga strukturirati."></textarea>
                    </div>
                </div>

                <div class="btn-row">
                    <button class="btn btn-secondary" onclick="aiPredloziTeme()" id="btn-suggest">
                        🔍 AI predloži podjelu na teme
                    </button>
                    <button class="btn btn-primary" onclick="goToAnalysis()" id="btn-analyze">
                        ⚡ Analiziraj i strukturiraj →
                    </button>
                </div>

                <div id="topics-suggest-box" style="display:none; margin-top:16px;"></div>
            </div>

            <!-- KORAK 2: PREVIEW i POTVRDA -->
            <div id="phase-preview" style="display:none;">
                <div class="section">
                    <div class="section-title">AI strukturirani sadržaj</div>
                    <p style="font-size:13px;color:var(--muted);margin-bottom:12px;">
                        AI je parsirao vaš tekst u strukturirani format. Pregledajte i po potrebi uredite.
                    </p>
                    <div class="field">
                        <label>Predmet / Tema</label>
                        <div style="display:flex;gap:10px;">
                            <div class="preview-box" id="preview-subject" style="flex:1;max-height:42px;padding:10px 14px;"></div>
                            <div class="preview-box" id="preview-topic" style="flex:2;max-height:42px;padding:10px 14px;"></div>
                        </div>
                    </div>
                    <div class="field" style="margin-top:12px;">
                        <label>Strukturirani tekst (gradivo.json sadržaj)</label>
                        <textarea id="structured-text" style="min-height:260px;font-size:11px;"></textarea>
                    </div>
                </div>

                <div class="btn-row">
                    <button class="btn btn-secondary" onclick="goBack()">← Natrag</button>
                    <button class="btn btn-primary" onclick="saveGradivo()" id="btn-save">
                        💾 Spremi u gradivo.json i bazu →
                    </button>
                </div>
            </div>

            <!-- KORAK 3: REZULTAT -->
            <div id="phase-done" style="display:none;">
                <div class="section">
                    <div class="section-title">Rezultat</div>
                    <div id="result-chips" style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px;"></div>
                    <div class="log-box" id="log-box"></div>
                </div>
                <div class="btn-row" style="margin-top:20px;">
                    <button class="btn btn-primary" onclick="resetAll()">+ Dodaj sljedeće gradivo</button>
                    <button class="btn btn-secondary" onclick="reloadLeft()">↻ Osvježi popis</button>
                </div>
            </div>

        </div>
    </div>
</div>

<script>
// =====================================================================
// STATE
// =====================================================================
let currentSubject = "";
let currentTopic = "";
let structuredContent = "";
let gradivoData = {};

// =====================================================================
// INIT
// =====================================================================
async function init() {
    await fetchStatus();
    await loadGradivo();
}

async function fetchStatus() {
    try {
        const r = await fetch("/api/status");
        const d = await r.json();
        document.getElementById("model-name").textContent = d.model || "nepoznat";
    } catch(e) {
        document.getElementById("model-name").textContent = "greška";
    }
}

async function loadGradivo() {
    try {
        const r = await fetch("/api/gradivo");
        gradivoData = await r.json();
        renderSubjectsList();
        populateSubjectSelect();
    } catch(e) {
        console.error(e);
    }
}

function renderSubjectsList() {
    const container = document.getElementById("subjects-list");
    if (!gradivoData || Object.keys(gradivoData).length === 0) {
        container.innerHTML = '<div style="padding:20px;font-family:var(--mono);font-size:11px;color:var(--muted)">gradivo.json je prazan.</div>';
        return;
    }

    let html = "";
    for (const [subject, topics] of Object.entries(gradivoData)) {
        const topicEntries = Object.entries(topics || {});
        const count = topicEntries.length;
        html += `<div class="subject-group">
            <div class="subject-header" onclick="toggleSubject(this)">
                <span class="chevron">▶</span>
                ${subject}
                <span class="count">${count}</span>
            </div>
            <div class="topics-list">`;
        for (const [topic, content] of topicEntries) {
            let cls = "";
            let dotClass = "";
            if (content && typeof content === "string") {
                if (content.trim().startsWith("{") && content.includes("modules")) {
                    cls = "has-ai";
                } else if (content.trim().length > 20) {
                    cls = "has-raw";
                }
            }
            const shortTopic = topic.length > 32 ? topic.slice(0, 30) + "…" : topic;
            html += `<div class="topic-item ${cls}" title="${topic}" onclick="fillFromExisting('${escHtml(subject)}','${escHtml(topic)}')">
                <div class="topic-dot"></div>
                <span>${escHtml(shortTopic)}</span>
            </div>`;
        }
        html += `</div></div>`;
    }
    container.innerHTML = html;
}

function escHtml(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); }

function toggleSubject(el) {
    el.classList.toggle("open");
    el.nextElementSibling.classList.toggle("open");
}

function populateSubjectSelect() {
    const sel = document.getElementById("subject-select");
    const subjects = Object.keys(gradivoData);
    sel.innerHTML = '<option value="">-- odaberi predmet --</option>';
    for (const s of subjects) {
        sel.innerHTML += `<option value="${escHtml(s)}">${escHtml(s)}</option>`;
    }
}

function onSubjectChange() {
    const val = document.getElementById("subject-select").value;
    if (val) document.getElementById("subject-new").value = "";
}

function fillFromExisting(subject, topic) {
    document.getElementById("subject-select").value = subject;
    document.getElementById("subject-new").value = "";
    document.getElementById("topic-input").value = topic;
    document.getElementById("raw-text").focus();
}

// =====================================================================
// STEP 1: AI PRIJEDLOG TEMA
// =====================================================================
async function aiPredloziTeme() {
    const rawText = document.getElementById("raw-text").value.trim();
    const subject = getSubject();
    if (!rawText || rawText.length < 50) {
        alert("Unesite više teksta (min. 50 znakova) za analizu tema.");
        return;
    }

    const btn = document.getElementById("btn-suggest");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Analiziram...';

    try {
        const r = await fetch("/api/suggest-topics", {
            method: "POST",
            headers: {"Content-Type":"application/json"},
            body: JSON.stringify({ text: rawText, subject: subject || "Opće" })
        });
        const topics = await r.json();

        if (!topics || !topics.length) {
            alert("AI nije uspio predložiti teme. Pokušajte ručno unijeti naziv teme.");
            return;
        }

        let html = `<div class="topics-suggest">
            <div class="topics-suggest-header">AI PRIJEDLOZI TEMA — kliknite za odabir</div>`;
        for (const t of topics) {
            html += `<div class="topic-suggestion" onclick="selectSuggestedTopic(this, '${escHtml(t.topic)}')">
                <input type="checkbox">
                <div>
                    <div class="topic-name">${escHtml(t.topic)}</div>
                    <div class="topic-summary">${escHtml(t.summary || "")}</div>
                </div>
            </div>`;
        }
        html += `</div>`;

        const box = document.getElementById("topics-suggest-box");
        box.innerHTML = html;
        box.style.display = "block";
    } catch(e) {
        alert("Greška pri dohvatu prijedloga: " + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '🔍 AI predloži podjelu na teme';
    }
}

function selectSuggestedTopic(el, topicName) {
    document.querySelectorAll(".topic-suggestion").forEach(x => x.classList.remove("selected"));
    el.classList.add("selected");
    el.querySelector("input[type=checkbox]").checked = true;
    document.getElementById("topic-input").value = topicName;
}

// =====================================================================
// STEP 2: ANALIZA I STRUKTURIRANJE
// =====================================================================
function getSubject() {
    const sel = document.getElementById("subject-select").value.trim();
    const newVal = document.getElementById("subject-new").value.trim();
    return newVal || sel;
}

async function goToAnalysis() {
    const rawText = document.getElementById("raw-text").value.trim();
    const subject = getSubject();
    const topic = document.getElementById("topic-input").value.trim();

    if (!rawText || rawText.length < 20) return alert("Unesite tekst gradiva.");
    if (!subject) return alert("Odaberite ili unesite naziv predmeta.");
    if (!topic) return alert("Unesite naziv teme/lekcije.");

    const btn = document.getElementById("btn-analyze");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> AI strukturira...';

    try {
        const r = await fetch("/api/struktura", {
            method: "POST",
            headers: {"Content-Type":"application/json"},
            body: JSON.stringify({ text: rawText, subject, topic })
        });
        const d = await r.json();

        if (!d.content) {
            alert("AI nije uspio strukturirati tekst. Pokušajte ponovo ili zalijepite tekst direktno.");
            return;
        }

        currentSubject = subject;
        currentTopic = topic;
        structuredContent = d.content;

        document.getElementById("preview-subject").textContent = subject;
        document.getElementById("preview-topic").textContent = topic;
        document.getElementById("structured-text").value = structuredContent;

        setStep(2);
        document.getElementById("phase-input").style.display = "none";
        document.getElementById("phase-preview").style.display = "block";

    } catch(e) {
        alert("Greška: " + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '⚡ Analiziraj i strukturiraj →';
    }
}

function goBack() {
    setStep(1);
    document.getElementById("phase-preview").style.display = "none";
    document.getElementById("phase-input").style.display = "block";
}

// =====================================================================
// STEP 3: SPREMI
// =====================================================================
async function saveGradivo() {
    const finalContent = document.getElementById("structured-text").value.trim();
    if (!finalContent) return alert("Nema sadržaja za spremanje.");

    const btn = document.getElementById("btn-save");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Sprema...';

    try {
        const r = await fetch("/api/save", {
            method: "POST",
            headers: {"Content-Type":"application/json"},
            body: JSON.stringify({
                subject: currentSubject,
                topic: currentTopic,
                content: finalContent
            })
        });
        const d = await r.json();

        setStep(3);
        document.getElementById("phase-preview").style.display = "none";
        document.getElementById("phase-done").style.display = "block";

        renderResult(d);
        await loadGradivo();

    } catch(e) {
        alert("Greška pri spremanju: " + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '💾 Spremi u gradivo.json i bazu →';
    }
}

function renderResult(d) {
    const chips = document.getElementById("result-chips");
    const log = document.getElementById("log-box");

    chips.innerHTML = "";
    log.innerHTML = "";

    if (d.gradivo_ok) {
        chips.innerHTML += `<span class="chip chip-ok">✓ gradivo.json ažuriran</span>`;
        addLog(log, "ok", `Predmet "${currentSubject}" / tema "${currentTopic}" zapisana u gradivo.json`);
    } else {
        chips.innerHTML += `<span class="chip chip-err">✗ gradivo.json greška</span>`;
        addLog(log, "err", d.gradivo_err || "Nepoznata greška");
    }

    if (d.db_status === "ok") {
        chips.innerHTML += `<span class="chip chip-ok">✓ baza ažurirana</span>`;
        addLog(log, "ok", "Lekcija upisana u skola.db (bez restarta Flaska)");
    } else if (d.db_status === "exists_ai") {
        chips.innerHTML += `<span class="chip chip-warn">⚠ baza: već ima AI sadržaj</span>`;
        addLog(log, "warn", "Ova lekcija već ima AI-generisan sadržaj u bazi — nije prepisana. Ako želite regenerisati, obrišite je iz admin panela.");
    } else {
        chips.innerHTML += `<span class="chip chip-err">✗ baza greška</span>`;
        addLog(log, "err", d.db_status || "Greška u bazi");
    }

    addLog(log, "info", "Sljedeći put kad Dani otvori ovu lekciju, AI će generisati sadržaj.");
}

function addLog(container, type, msg) {
    const time = new Date().toLocaleTimeString("hr", {hour:"2-digit",minute:"2-digit",second:"2-digit"});
    const cls = {ok:"log-ok", err:"log-err", info:"log-info", warn:"log-warn"}[type] || "log-info";
    container.innerHTML += `<div class="log-entry"><span class="log-time">${time}</span><span class="${cls}">${msg}</span></div>`;
}

// =====================================================================
// HELPERS
// =====================================================================
function setStep(n) {
    [1,2,3].forEach(i => {
        const el = document.getElementById(`step${i}`);
        el.classList.remove("active","done");
        if (i < n) el.classList.add("done");
        else if (i === n) el.classList.add("active");
    });
}

function resetAll() {
    setStep(1);
    document.getElementById("phase-done").style.display = "none";
    document.getElementById("phase-input").style.display = "block";
    document.getElementById("raw-text").value = "";
    document.getElementById("topic-input").value = "";
    document.getElementById("topics-suggest-box").style.display = "none";
    document.getElementById("result-chips").innerHTML = "";
    document.getElementById("log-box").innerHTML = "";
    currentSubject = currentTopic = structuredContent = "";
}

async function reloadLeft() {
    await loadGradivo();
}

init();
</script>
</body>
</html>
"""


# =====================================================================
# ROUTES
# =====================================================================
@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/status")
def api_status():
    return jsonify({"model": MODEL_ID, "ai_ok": ai_client is not None})


@app.route("/api/gradivo")
def api_gradivo():
    return jsonify(load_gradivo())


@app.route("/api/suggest-topics", methods=["POST"])
def api_suggest_topics():
    data = request.json or {}
    text = data.get("text", "")
    subject = data.get("subject", "")
    topics = ai_predlozi_teme(text, subject)
    return jsonify(topics)


@app.route("/api/struktura", methods=["POST"])
def api_struktura():
    data = request.json or {}
    text = data.get("text", "")
    subject = data.get("subject", "")
    topic = data.get("topic", "")

    if not text or not subject or not topic:
        return jsonify({"error": "Nedostaju parametri"}), 400

    structured = ai_struktura_gradivo(text, subject, topic)
    if not structured:
        # Fallback: vrati sirovi tekst ako AI ne radi
        structured = text

    return jsonify({"content": structured})


@app.route("/api/save", methods=["POST"])
def api_save():
    data = request.json or {}
    subject = data.get("subject", "").strip()
    topic = data.get("topic", "").strip()
    content = data.get("content", "").strip()

    if not subject or not topic or not content:
        return jsonify({"error": "Nedostaju parametri"}), 400

    result = {"gradivo_ok": False, "gradivo_err": None, "db_status": None}

    # 1. Spremi u gradivo.json
    try:
        gradivo = load_gradivo()
        if subject not in gradivo:
            gradivo[subject] = {}
        gradivo[subject][topic] = content
        save_gradivo(gradivo)
        result["gradivo_ok"] = True
        logger.info(f"[Save] gradivo.json ažuriran: {subject}/{topic}")
    except Exception as e:
        result["gradivo_err"] = str(e)
        logger.error(f"[Save] gradivo.json greška: {e}")

    # 2. Spremi u SQLite (live, bez restarta)
    db_status = db_upsert_lesson(subject, topic, content)
    result["db_status"] = db_status
    logger.info(f"[Save] DB status: {db_status}")

    return jsonify(result)


# =====================================================================
# MAIN
# =====================================================================
if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  GRADIVO EDITOR")
    print(f"  Model: {MODEL_ID}")
    print(f"  gradivo.json: {GRADIVO_FILE}")
    print(f"  baza: {DB_FILE}")
    print("  URL: http://localhost:5001")
    print("=" * 50 + "\n")
    app.run(port=5001, debug=False)
