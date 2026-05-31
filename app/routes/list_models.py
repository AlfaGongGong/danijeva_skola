"""
list_models.py — Ispis svih dostupnih Gemini modela za vaš API key.
Pokretanje: python list_models.py
"""

import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

if not GOOGLE_API_KEY:
    print("❌ Nije pronađen GOOGLE_API_KEY ni GEMINI_API_KEY u .env fajlu!")
    exit(1)

try:
    from google import genai
except ImportError:
    print("❌ Nije instaliran google-genai. Pokrenite: pip install google-genai")
    exit(1)

client = genai.Client(api_key=GOOGLE_API_KEY)

print("\n" + "=" * 60)
print("  DOSTUPNI MODELI ZA VAŠ API KEY")
print("=" * 60)

all_models = list(client.models.list())

# Modeli koji podržavaju generateContent
generate_models = []
other_models = []

for m in all_models:
    actions = [a for a in (m.supported_actions or [])]
    if "generateContent" in actions:
        generate_models.append(m)
    else:
        other_models.append(m)

print(f"\n✅ MODELI koji podržavaju generateContent ({len(generate_models)}):\n")
for m in generate_models:
    # Izvuci samo kratko ime (bez "models/" prefiksa)
    name = m.name.replace("models/", "") if m.name else "?"
    display = m.display_name or ""
    print(f'  MODEL_ID = "{name}"')
    if display:
        print(f"           ({display})")
    print()

if other_models:
    print(f"\n⚪ Ostali modeli (ne podržavaju generateContent) ({len(other_models)}):")
    for m in other_models:
        name = m.name.replace("models/", "") if m.name else "?"
        print(f"  - {name}")

print("\n" + "=" * 60)
print("  PREPORUKA ZA config.py:")
print("=" * 60)

# Pokušaj pronaći preporučeni model
preferred = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash"]
found = None
for pref in preferred:
    for m in generate_models:
        if pref in (m.name or ""):
            found = m.name.replace("models/", "")
            break
    if found:
        break

if found:
    print(f'\n  MODEL_ID = "{found}"')
else:
    if generate_models:
        first = generate_models[0].name.replace("models/", "")
        print(f'\n  MODEL_ID = "{first}"  ← prvi dostupni')
    else:
        print("\n  ⚠️  Nije pronađen nijedan model koji podržava generateContent!")

print()
