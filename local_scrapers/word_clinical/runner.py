import json
import logging
from pathlib import Path

from .decryptor import decrypt_docx
from .models import SustentoProclamasDoc
from .parser import parse_document
from .password import derive_password
from .pdf_extractor import extract_informes, get_informe_page_counts

logger = logging.getLogger(__name__)

DEFAULT_INPUT = Path(__file__).parent / "input"
DEFAULT_OUTPUT = Path(__file__).parent / "output"


def process_file(
    filepath: str | Path,
    output_dir: str | Path | None = None,
    extract_pdfs: bool = True,
) -> SustentoProclamasDoc:
    from docx import Document

    filepath = Path(filepath)
    password = derive_password(filepath)
    buf = decrypt_docx(filepath, password)

    result = parse_document(buf, filepath.name)

    # Carpeta de salida por documento
    doc_output = Path(output_dir or DEFAULT_OUTPUT) / filepath.stem
    doc_output.mkdir(parents=True, exist_ok=True)

    buf.seek(0)
    doc = Document(buf)
    codigos = [e.codigo for e in result.estudios]

    if extract_pdfs:
        extracted = extract_informes(buf, doc, codigos, doc_output)
        for estudio, (fname, pages) in zip(result.estudios, extracted):
            estudio.informe = fname
            estudio.informe_paginas = pages
        logger.info("PDFs extraídos en %s", doc_output)
    else:
        page_counts = get_informe_page_counts(buf, doc)
        for estudio, pages in zip(result.estudios, page_counts):
            estudio.informe_paginas = pages

    # Guardar JSON nombrado con el código de fórmula
    json_path = doc_output / f"{result.codigo_formula}.json"
    json_path.write_text(
        json.dumps(result.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("JSON guardado en %s", json_path)

    return result


def run(
    input_dir: str | Path = DEFAULT_INPUT,
    output_dir: str | Path | None = None,
    extract_pdfs: bool = True,
) -> list[SustentoProclamasDoc]:
    input_dir = Path(input_dir)
    out_dir = Path(output_dir or DEFAULT_OUTPUT)
    results = []
    for docx_file in sorted(input_dir.glob("*.docx")):
        if docx_file.name.startswith("~$"):
            continue
        try:
            logger.info("Procesando %s", docx_file.name)
            result = process_file(docx_file, output_dir=out_dir, extract_pdfs=extract_pdfs)
            results.append(result)
            logger.info("OK — %s (%d estudios, %d proclamas)",
                        result.nombre_producto, len(result.estudios), len(result.proclamas))
        except Exception as e:
            logger.error("ERROR %s: %s", docx_file.name, e)

    # JSON consolidado con todos los documentos
    if results:
        consolidated = out_dir / "result.json"
        consolidated.write_text(
            json.dumps([r.model_dump() for r in results], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Consolidado guardado en %s", consolidated)

    return results


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    extract = "--extract-pdfs" in sys.argv
    docs = run(extract_pdfs=extract)
    print(json.dumps([d.model_dump() for d in docs], ensure_ascii=False, indent=2))
