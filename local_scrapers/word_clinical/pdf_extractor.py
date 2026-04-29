"""
Extrae los PDFs incrustados en los documentos Word de Sustento de Proclamas.

Los PDFs están almacenados como OLE objects dentro del .docx (ZIP).
Cada estudio en Tabla 2 tiene un PDF en la columna INFORME.
"""
import io
import re
import zipfile
from pathlib import Path

import olefile
from docx import Document
from docx.oxml.ns import qn
from lxml import etree

NS_R = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_R2 = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_O = "urn:schemas-microsoft-com:office:office"


def _safe_filename(text: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", text).strip()[:80]


def _build_rid_map(zip_buf: io.BytesIO) -> dict[str, str]:
    """rId → relative path inside ZIP (e.g. 'embeddings/oleObject1.bin')"""
    zip_buf.seek(0)
    with zipfile.ZipFile(zip_buf) as z:
        rels_xml = z.read("word/_rels/document.xml.rels")
    tree = etree.fromstring(rels_xml)
    return {
        r.get("Id"): r.get("Target")
        for r in tree.findall(f"{{{NS_R}}}Relationship")
        if "oleObject" in r.get("Type", "")
    }


def _extract_pdf_bytes(zip_buf: io.BytesIO, target: str) -> bytes | None:
    """Extract PDF bytes from an OLE bin file inside the ZIP."""
    zip_buf.seek(0)
    with zipfile.ZipFile(zip_buf) as z:
        ole_bytes = z.read(f"word/{target}")
    ole = olefile.OleFileIO(io.BytesIO(ole_bytes))
    if not ole.exists("CONTENTS"):
        return None
    data = ole.openstream("CONTENTS").read()
    return data if data[:4] == b"%PDF" else None


def _pdf_page_count(pdf_bytes: bytes) -> int | None:
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        return doc.page_count
    except Exception:
        return None


def _ole_rids_from_table(doc: Document, table_idx: int, skip_header: bool = False) -> list[str | None]:
    """Returns one rId per row in doc.tables[table_idx]. None if no OLE in that row."""
    rows = doc.tables[table_idx].rows
    if skip_header:
        rows = rows[1:]
    rids = []
    for row in rows:
        rid = None
        for ole_el in row._tr.findall(f".//{{{NS_O}}}OLEObject"):
            rid = ole_el.get(f"{{{NS_R2}}}id")
            break
        rids.append(rid)
    return rids


def _informe_rids_from_doc(doc: Document) -> list[str | None]:
    """Returns one rId per data row in Tabla 2 (studies table)."""
    return _ole_rids_from_table(doc, table_idx=2, skip_header=True)


def extract_informes(
    zip_buf: io.BytesIO,
    doc: Document,
    estudios_codigos: list[str],
    output_dir: str | Path,
) -> list[tuple[str | None, int | None]]:
    """
    Extract one PDF per study from the embedded OLE objects.
    Saves them to output_dir named as '{codigo}.pdf'.
    Returns list of (filename, page_count) per study.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rid_map = _build_rid_map(zip_buf)
    rids = _informe_rids_from_doc(doc)

    seen: dict[str, int] = {}
    results: list[tuple[str | None, int | None]] = []
    for rid, codigo in zip(rids, estudios_codigos):
        if not rid or rid not in rid_map:
            results.append((None, None))
            continue

        pdf_bytes = _extract_pdf_bytes(zip_buf, rid_map[rid])
        if not pdf_bytes:
            results.append((None, None))
            continue

        base = _safe_filename(codigo)
        count = seen.get(base, 0)
        seen[base] = count + 1
        filename = f"{base}_{count + 1}.pdf" if count > 0 else f"{base}.pdf"
        (output_dir / filename).write_bytes(pdf_bytes)
        results.append((filename, _pdf_page_count(pdf_bytes)))

    return results


def get_informe_page_counts(
    zip_buf: io.BytesIO,
    doc: Document,
) -> list[int | None]:
    """Returns page count for each study's PDF (without saving to disk)."""
    rid_map = _build_rid_map(zip_buf)
    rids = _informe_rids_from_doc(doc)
    counts = []
    for rid in rids:
        if not rid or rid not in rid_map:
            counts.append(None)
            continue
        pdf_bytes = _extract_pdf_bytes(zip_buf, rid_map[rid])
        counts.append(_pdf_page_count(pdf_bytes) if pdf_bytes else None)
    return counts


def get_referencia_page_counts(
    zip_buf: io.BytesIO,
    doc: Document,
) -> list[int | None]:
    """Returns page count for each bibliography reference PDF (without saving to disk)."""
    rid_map = _build_rid_map(zip_buf)
    rids = _ole_rids_from_table(doc, table_idx=4, skip_header=False)
    counts = []
    for rid in rids:
        if not rid or rid not in rid_map:
            counts.append(None)
            continue
        pdf_bytes = _extract_pdf_bytes(zip_buf, rid_map[rid])
        counts.append(_pdf_page_count(pdf_bytes) if pdf_bytes else None)
    return counts


def extract_referencias_informes(
    zip_buf: io.BytesIO,
    doc: Document,
    refs_numeros: list[str],
    output_dir: str | Path,
) -> list[tuple[str | None, int | None]]:
    """Extract one PDF per bibliography reference from Tabla 4 OLE objects.

    Saves files as ref_{numero}.pdf in output_dir.
    Returns list of (filename, page_count) per reference.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rid_map = _build_rid_map(zip_buf)
    rids = _ole_rids_from_table(doc, table_idx=4, skip_header=False)

    results: list[tuple[str | None, int | None]] = []
    for rid, numero in zip(rids, refs_numeros):
        if not rid or rid not in rid_map:
            results.append((None, None))
            continue
        pdf_bytes = _extract_pdf_bytes(zip_buf, rid_map[rid])
        if not pdf_bytes:
            results.append((None, None))
            continue
        filename = f"ref_{_safe_filename(numero)}.pdf"
        (output_dir / filename).write_bytes(pdf_bytes)
        results.append((filename, _pdf_page_count(pdf_bytes)))

    return results
