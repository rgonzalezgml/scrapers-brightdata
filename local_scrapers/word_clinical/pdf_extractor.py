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


def _informe_rids_from_doc(doc: Document) -> list[str | None]:
    """
    Returns one rId per data row in Tabla 2 (studies table).
    None if a row has no embedded PDF.
    """
    t2 = doc.tables[2]
    rids = []
    for row in t2.rows[1:]:  # skip header
        rid = None
        for child in list(row._tr):
            local = child.tag.split("}")[-1]
            if local == "tc":
                for ole_el in child.findall(f".//{{{NS_O}}}OLEObject"):
                    rid = ole_el.get(f"{{{NS_R2}}}id")
                    break
        rids.append(rid)
    return rids


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
