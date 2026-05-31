# Danijeva E-Školica 📚🎸

AI-powered personalized learning platform built with Flask. Features gamification (XP, ranks, medals), AI-generated lessons and tests via Google Gemini, real-time telemetry, and an anatomy atlas with OCR indexing.

## Features

- **AI Lesson Generation** — Automatic lesson content and test questions via Google Gemini API
- **Gamification** — XP system, rank progression, positive/negative medals
- **Smart Grading** — AI-assisted semantic answer evaluation (handles typos, synonyms, paraphrasing)
- **Telemetry** — Tracks focus, idle time, tab switching; generates "Doomsday Reports"
- **Anatomy Atlas** — OCR-indexed PDF atlas with image search and display
- **Admin Panel** — Manage lessons, view logs, adjust student stats
- **Responsive UI** — Dark/light mode, mobile-friendly, calculator widget

## Quick Start

### Prerequisites

- Python 3.10+
- (Optional) [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) and [Poppler](https://poppler.freedesktop.org/) for atlas processing
- (Optional) [ngrok](https://ngrok.com/) account for remote access

### Installation

```bash
# Clone the repository
git clone https://github.com/AlfaGongGong/danijeva_skola.git
cd danijeva_skola

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your passwords and API keys
```

### Running

```bash
python run.py
```

The app starts at `http://localhost:5000`. If `NGROK_AUTH_TOKEN` is set, it also creates a public tunnel.

### Development Mode

Set `DEBUG=1` in `.env` to bypass password requirements during development:

```env
DEBUG=1
ACCESS_PASSWORD=test
ADMIN_PASSWORD=test
```

## Project Structure

```
├── app/                    # Flask application package
│   ├── __init__.py         # App factory (create_app)
│   └── routes/             # Blueprints
│       ├── auth.py         # Authentication endpoints
│       ├── lessons.py      # Lesson/content API + AI generation
│       ├── test.py         # AI grading endpoint
│       ├── stats.py        # Stats, save progress, admin routes
│       └── atlas.py        # Atlas image serving
├── static/
│   ├── css/style.css       # Full application styles
│   └── js/script.js        # Frontend SPA logic
├── templates/
│   └── index.html          # Single-page HTML template
├── config.py               # Configuration (loads from .env)
├── database.py             # SQLite database layer
├── grader.py               # Local text similarity grading
├── utils.py                # Auth decorator, JSON extraction, atlas search
├── atlas.py                # PDF→OCR atlas indexing tool
├── run.py                  # Application entry point
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
└── test.py                 # Legacy monolithic version (deprecated)
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ACCESS_PASSWORD` | ✅ | Student login password |
| `ADMIN_PASSWORD` | ✅ | Admin login password |
| `GOOGLE_API_KEY` | ❌ | Google Gemini API key for AI features |
| `NGROK_AUTH_TOKEN` | ❌ | Ngrok token for remote tunnel |
| `NGROK_DOMAIN` | ❌ | Custom ngrok domain |
| `TESSERACT_CMD` | ❌ | Path to Tesseract binary |
| `POPPLER_PATH` | ❌ | Path to Poppler bin directory |
| `DEBUG` | ❌ | Set to `1` for development mode |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth` | Authenticate user |
| GET | `/api/content` | Get/generate lesson content |
| POST | `/api/grade` | AI-grade a student answer |
| POST | `/api/save` | Save session results |
| GET | `/api/stats` | Get student stats |
| GET | `/api/gradivo` | List all subjects/lessons |
| POST | `/api/admin/gradivo/delete` | Delete a lesson (admin) |
| POST | `/api/admin/logs/list` | List log files (admin) |
| POST | `/api/admin/logs/read` | Read a log file (admin) |
| POST | `/api/admin/stats/update` | Update student XP (admin) |

## Technology Stack

- **Backend:** Python, Flask, SQLite
- **Frontend:** Vanilla JavaScript (SPA), CSS3 with custom properties
- **AI:** Google Gemini API (gemma-3-27b-it)
- **OCR:** Tesseract, pdf2image, Pillow

## License

Private educational project.
