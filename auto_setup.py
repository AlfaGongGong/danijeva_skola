import logging
import sys
import time
from typing import List, Union, Dict, Any, Optional
from pathlib import Path

# --------------------------------------------------------------------------------
# 1. TQDM FALLBACK MEHANIZAM (Type-Safe Fix)
# --------------------------------------------------------------------------------
# Rješenje za Pylance "reportAssignmentType" grešku:
# Definišemo Mock klasu pod drugim imenom (_MockTqdm), a zatim je dodijelimo.
try:
    from tqdm import tqdm
except ImportError:
    # Definišemo klasu sa donjom crtom da izbjegnemo konflikt imena tokom definicije
    class _MockTqdm:
        """
        Mock klasa koja simulira tqdm ponašanje ako biblioteka nije instalirana.
        """

        def __init__(self, iterable=None, total=None, **kwargs):
            self.iterable = iterable
            self.total = total
            self.n = 0
            if iterable:
                self.iterator = iter(iterable)
            else:
                self.iterator = None

        def __iter__(self):
            return self.iterator if self.iterator else iter([])

        def __next__(self):
            if self.iterator:
                return next(self.iterator)
            raise StopIteration

        def update(self, n=1):
            self.n += n

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

    # Eksplicitna dodjela uz ignorisanje strogog type check-a za ovu liniju
    # Pylance ovdje griješi jer ne može predvidjeti runtime fallback, pa ga utišavamo.
    tqdm = _MockTqdm  # type: ignore


# --------------------------------------------------------------------------------
# 2. KONFIGURACIJA LOGOVANJA
# --------------------------------------------------------------------------------
def setup_logging(log_file: str = "process_audit.log"):
    logger = logging.getLogger("RobustProcessor")
    logger.setLevel(logging.DEBUG)

    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] - %(message)s", datefmt="%H:%M:%S"
    )

    # File Handler
    fh = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)

    # Console Handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger


logger = setup_logging()


# --------------------------------------------------------------------------------
# 3. NORMALIZACIJA TIPOVA
# --------------------------------------------------------------------------------
def normalize_input_paths(data: Union[str, List[Any], Dict[Any, Any]]) -> List[str]:
    """
    Prima bilo koji tip (str, list, dict) i vraća listu stringova.
    """
    normalized_paths = []

    try:
        if isinstance(data, str):
            normalized_paths.append(data)

        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (str, Path)):
                    normalized_paths.append(str(item))
                elif isinstance(item, list):
                    normalized_paths.extend(normalize_input_paths(item))
                else:
                    logger.debug(
                        f"Ignorisan element u listi (nepodržan tip): {type(item)}"
                    )

        elif isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (str, Path)):
                    normalized_paths.append(str(value))
                elif isinstance(value, list):
                    normalized_paths.extend(normalize_input_paths(value))

        elif data is None:
            pass

        else:
            logger.warning(f"Primljen nepodržan tip podataka: {type(data)}")

    except Exception as e:
        logger.critical(f"Greška u normalizaciji: {e}")

    # Vraćamo samo neprazne stringove
    return [p for p in normalized_paths if p and str(p).strip()]


# --------------------------------------------------------------------------------
# 4. SIMULACIJA OBRADE
# --------------------------------------------------------------------------------
def process_file(file_path: str):
    # Pretvaranje u string eksplicitno za svaki slučaj
    clean_path = str(file_path).lower().strip()

    time.sleep(0.1)  # Brža simulacija

    if clean_path.endswith(".pdf"):
        return {"status": "OK", "msg": "PDF Validiran"}
    elif clean_path.endswith(".txt"):
        return {"status": "OK", "msg": "TXT Validiran"}
    else:
        return {"status": "SKIP", "msg": "Nepoznat format"}


# --------------------------------------------------------------------------------
# 5. GLAVNA FUNKCIJA
# --------------------------------------------------------------------------------
def main():
    logger.info("--- Start Skripte ---")

    # Simulacija različitih inputa
    raw_inputs = [
        "C:\\Dokumenti\\file1.pdf",
        ["file2.txt", 123, None],
        {"config": "file3.pdf", "meta": ["file4.txt"]},
    ]

    # Priprema
    all_paths = []
    for raw in raw_inputs:
        paths = normalize_input_paths(raw)
        all_paths.extend(paths)

    total_files = len(all_paths)
    logger.info(f"Pronađeno {total_files} fajlova.")

    # Izvršavanje (Koristi tqdm ili fallback _MockTqdm)
    stats = {"OK": 0, "SKIP": 0, "ERR": 0}

    # Sada je 'tqdm' siguran za korištenje bez obzira na izvor
    with tqdm(total=total_files, desc="Procesiranje", unit="file") as pbar:
        for idx, path in enumerate(all_paths):
            try:
                result = process_file(path)

                if result["status"] == "OK":
                    stats["OK"] += 1
                    logger.info(f"[{idx+1}/{total_files}] OK: {path}")
                else:
                    stats["SKIP"] += 1
                    logger.warning(f"[{idx+1}/{total_files}] SKIP: {path}")

            except Exception as e:
                stats["ERR"] += 1
                logger.error(f"ERR: {path} -> {e}")

            pbar.update(1)

    logger.info(f"KRAJ: OK={stats['OK']}, SKIP={stats['SKIP']}, ERR={stats['ERR']}")


if __name__ == "__main__":
    main()
