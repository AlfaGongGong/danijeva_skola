# Arhitektura podataka

## Source of truth za lekcije

- `gradivo.json` — **Kurikulum**: lista predmeta, tema i kratkih opisa.
  Koristi se za prikaz navigacije i kao `{info}` kontekst u AI promptu.
  Ručno se uređuje.

- `skola.db` → tabela `lessons` — **Sadržaj**: AI-generirani tekstovi lekcija
  (JSON moduli + blic pitanja). Generirani dinamički, mogu se regenerirati.

- `skola.db` → tabela `questions` — **Testna pitanja**: AI-generirani testovi.

Ako dodaješ novi predmet: dodaj u `gradivo.json`, baza će se popuniti
pri prvom pozivu `/generate_lesson` za tu lekciju.

## Struktura aplikacije

```
app/
├── __init__.py          ← create_app() factory
├── routes/
│   ├── auth.py          ← /api/auth
│   ├── lessons.py       ← /api/content (learn + test generation)
│   ├── test.py          ← /api/grade
│   ├── stats.py         ← /api/stats, /api/save, /get_analytics, admin routes
│   └── atlas.py         ← /atlas/<filename>
config.py                ← konfiguracija (env vars)
database.py              ← SQLite helpers
utils.py                 ← auth decorator, JSON extraction, atlas search
run.py                   ← entry point
```
