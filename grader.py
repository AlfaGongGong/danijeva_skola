import difflib
import re


def normalize_text(text):
    """Čisti tekst od interpunkcije i pretvara u mala slova."""
    if not text:
        return ""
    text = text.lower().strip()
    # Ukloni sve osim slova i brojeva
    text = re.sub(r"[^\w\s]", "", text)
    return text


def check_answer(user_input, correct_answer, keywords=[]):
    """
    Vraća (score, feedback_type).
    Score: 0.0 do 1.0
    Type: 'CORRECT', 'PARTIAL', 'WRONG'
    """
    u_norm = normalize_text(user_input)
    c_norm = normalize_text(correct_answer)

    if not u_norm:
        return 0.0, "WRONG"

    # 1. DIREKTNA SLIČNOST (SequenceMatcher)
    # Ovo rješava tipfelere (npr. "akceleracija" vs "akcelercija")
    similarity = difflib.SequenceMatcher(None, u_norm, c_norm).ratio()

    # Ako je sličnost veća od 85%, to je točno bez obzira na ključne riječi
    if similarity > 0.85:
        return 1.0, "CORRECT"

    # 2. PROVJERA KLJUČNIH RIJEČI (Kontekst)
    if keywords:
        found_keywords = 0
        required_keywords = len(keywords)

        for kw in keywords:
            kw_norm = normalize_text(kw)
            # Tražimo riječ u tekstu (pazimo da nije dio druge riječi ako je moguće)
            if kw_norm in u_norm:
                found_keywords += 1

        # Izračunaj postotak pogođenih ključnih riječi
        kw_score = found_keywords / required_keywords if required_keywords > 0 else 0

        if kw_score >= 0.75:  # Ako ima 3 od 4 ključne riječi
            return 1.0, "CORRECT"
        elif kw_score >= 0.5:  # Ako ima pola ključnih riječi
            return 0.5, "PARTIAL"

    # 3. FALLBACK ZA KRATKE ODGOVORE
    # Ako je odgovor točan "5", a on napiše "5 metara", keyword check bi mogao pasti ako nema keyworda.
    if c_norm in u_norm:
        return 1.0, "CORRECT"

    return 0.0, "WRONG"
