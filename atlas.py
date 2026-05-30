import pytesseract
from pytesseract import Output
from pdf2image import convert_from_path
from PIL import Image
import os
import sys
import json
import logging
from pathlib import Path
from tqdm import tqdm

# ==============================================================================
# 1. KONFIGURACIJA (Vaše putanje su ubačene ovdje)
# ==============================================================================

# Putanja do vašeg PDF fajla (Zamijenite ako je drugačije)
INPUT_PDF = (
    r"C:\Users\AlfaGongGong\Документы\GitHub\testovi\sobotta-anatomski-atlas.pdf"
)

# Vaše sistemske putanje
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER_PATH = r"C:\Program Files\poppler-xx\bin"  # <--- PROVJERITE DA LI SE FOLDER STVARNO ZOVE 'xx'

# Folderi za izlaz
BASE_OUTPUT_DIR = "atlas_processed"
DB_FILE_NAME = "atlas_index.json"

# ==============================================================================
# 2. SETUP I LOGOVANJE
# ==============================================================================
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("AtlasOCR")


def check_system_paths():
    """Provjerava da li alati stvarno postoje na disku prije početka."""
    checks = [
        ("Tesseract EXE", TESSERACT_CMD),
        ("Poppler BIN", POPPLER_PATH),
        ("Input PDF", INPUT_PDF),
    ]

    all_ok = True
    logger.info("--- Provjera sistema ---")
    for name, path in checks:
        if os.path.exists(path):
            logger.info(f"[OK] {name} pronađen: {path}")
        else:
            logger.critical(f"[GRESKA] {name} NIJE PRONAĐEN na putanji: {path}")
            all_ok = False

    if not all_ok:
        logger.error("Zaustavljam skriptu jer nedostaju ključne komponente.")
        sys.exit(1)
    logger.info("Sistemska provjera prošla. Krećemo...")


def setup_directories():
    img_dir = os.path.join(BASE_OUTPUT_DIR, "images")
    Path(img_dir).mkdir(parents=True, exist_ok=True)
    return img_dir


# ==============================================================================
# 3. CORE LOGIKA (OCR I INDEKSIRANJE)
# ==============================================================================
def analyze_atlas_page(image_path, page_number):
    """
    Vrši OCR nad slikom i vraća koordinate riječi.
    """
    try:
        img = Image.open(image_path)

        # Konfiguracija za atlas:
        # --psm 11: Sparse text (traži riječi razbacane po slici)
        # lang='srp_latn': Srpska latinica (ako je nemate, vratite na 'eng')
        # Ako nemate srp_latn data fajl, kod će pući, pa koristim 'eng' kao safe default.
        # Ako ste instalirali srpski tokom setupa tesseracta, promijenite u 'srp_latn'.
        ocr_lang = "eng"

        data = pytesseract.image_to_data(
            img, lang=ocr_lang, output_type=Output.DICT, config="--psm 11"
        )

        valid_words = []
        num_boxes = len(data["text"])

        for i in range(num_boxes):
            # Filtriranje loših rezultata
            confidence = int(data["conf"][i])
            text = data["text"][i].strip()

            # Uslovi: Pouzdanost > 60%, Dužina > 3 slova, Nije broj
            if confidence > 60 and len(text) > 3 and not text.isnumeric():
                entry = {
                    "term": text,
                    "page": page_number,
                    "image_rel_path": os.path.basename(
                        image_path
                    ),  # Čuvamo relativnu putanju
                    "bbox": {
                        "x": data["left"][i],
                        "y": data["top"][i],
                        "w": data["width"][i],
                        "h": data["height"][i],
                    },
                }
                valid_words.append(entry)

        return valid_words

    except Exception as e:
        logger.error(f"Greška na stranici {page_number}: {e}")
        return []


# ==============================================================================
# 4. GLAVNI PROCES (PIPELINE)
# ==============================================================================
def main():
    # 1. Sigurnosna provjera
    check_system_paths()

    output_img_dir = setup_directories()
    full_database = []

    # 2. Konverzija PDF u Slike
    logger.info("FAZA 1/2: Konverzija PDF-a u slike...")
    try:
        # thread_count=4 koristi 4 procesora za bržu konverziju
        images = convert_from_path(
            INPUT_PDF, dpi=300, poppler_path=POPPLER_PATH, thread_count=4
        )
        logger.info(f"PDF uspješno učitan. Ukupno stranica: {len(images)}")
    except Exception as e:
        logger.critical(f"Neuspjela konverzija PDF-a: {e}")
        sys.exit(1)

    # 3. OCR Procesiranje
    logger.info("FAZA 2/2: OCR Analiza i Indeksiranje...")

    # Koristimo tqdm za progress bar
    with tqdm(total=len(images), desc="Analiza atlasa", unit="str") as pbar:
        for pg_idx, image in enumerate(images):
            pg_num = pg_idx + 1

            # Ime fajla slike
            img_filename = f"atlas_page_{pg_num:03d}.png"
            full_img_path = os.path.join(output_img_dir, img_filename)

            # Snimanje slike na disk (ovo je baza za pitanja kasnije)
            image.save(full_img_path, "PNG")

            # OCR Analiza te slike
            page_words = analyze_atlas_page(full_img_path, pg_num)
            full_database.extend(page_words)

            pbar.update(1)

    # 4. Čuvanje JSON baze
    final_db_path = os.path.join(BASE_OUTPUT_DIR, DB_FILE_NAME)
    with open(final_db_path, "w", encoding="utf-8") as f:
        json.dump(full_database, f, indent=4, ensure_ascii=False)

    logger.info("=" * 40)
    logger.info("PROCES USPJEŠNO ZAVRŠEN")
    logger.info(f"Slike su u folderu: {output_img_dir}")
    logger.info(f"Baza podataka: {final_db_path}")
    logger.info(f"Ukupno indeksirano pojmova: {len(full_database)}")
    logger.info("=" * 40)


if __name__ == "__main__":
    main()
