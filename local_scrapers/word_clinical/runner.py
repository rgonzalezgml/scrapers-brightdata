import json
import logging
from pathlib import Path

from .decryptor import decrypt_docx
from .models import SustentoProclamasDoc
from .parser import parse_document
from .password import derive_password

logger = logging.getLogger(__name__)

DEFAULT_INPUT = Path(__file__).parent / "input"


def process_file(filepath: str | Path) -> SustentoProclamasDoc:
    filepath = Path(filepath)
    password = derive_password(filepath)
    buf = decrypt_docx(filepath, password)
    return parse_document(buf, filepath.name)


def run(input_dir: str | Path = DEFAULT_INPUT) -> list[SustentoProclamasDoc]:
    input_dir = Path(input_dir)
    results = []
    for docx_file in sorted(input_dir.glob("*.docx")):
        try:
            logger.info("Procesando %s", docx_file.name)
            result = process_file(docx_file)
            results.append(result)
            logger.info("OK — %s (%d estudios, %d proclamas)",
                        result.nombre_producto, len(result.estudios), len(result.proclamas))
        except Exception as e:
            logger.error("ERROR %s: %s", docx_file.name, e)
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    docs = run()
    print(json.dumps([d.model_dump() for d in docs], ensure_ascii=False, indent=2))
