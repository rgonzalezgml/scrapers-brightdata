"""
Tests for local_scrapers/word_clinical.
Require the real .docx files in local_scrapers/word_clinical/input/.
"""
from pathlib import Path

import pytest

from local_scrapers.word_clinical.password import derive_password
from local_scrapers.word_clinical.runner import process_file

INPUT = Path(__file__).parent.parent.parent / "local_scrapers/word_clinical/input"

INTIMO = INPUT / "008MB33B CSD_INTIMO BY LOMECAN JABÓN LÍQUIDO ULTRA FRESH 1.docx"
TIO_NACHO = INPUT / "058IH51B CSD_TÍO NACHO SHAMPOO CAPILAR TONALIZADOR USA 1.docx"


# ── password ──────────────────────────────────────────────────────────────────

def test_password_intimo():
    assert derive_password(INTIMO) == "B33B"

def test_password_tio_nacho():
    assert derive_password(TIO_NACHO) == "B15H"


# ── Íntimo By Lomecan ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def intimo_doc():
    return process_file(INTIMO)

def test_intimo_metadata(intimo_doc):
    assert intimo_doc.codigo_formula == "008MB33B"
    assert intimo_doc.nombre_producto == "Intimo By Lomecan Jabón Líquido Ultra Fresh"
    assert intimo_doc.fecha_documento == "30/06/25"
    assert intimo_doc.version == "001"

def test_intimo_estudios(intimo_doc):
    assert len(intimo_doc.estudios) == 5
    codigos = [e.codigo for e in intimo_doc.estudios]
    assert "IME.EC.185" in codigos
    assert "GMM712-25-E-2" in codigos

def test_intimo_proclamas(intimo_doc):
    assert len(intimo_doc.proclamas) == 9
    tipos = {p.tipo_soporte for p in intimo_doc.proclamas if p.tipo_soporte}
    assert "Subjetivo" in tipos    # antes: Sensorial
    assert "Objetivo" in tipos     # antes: Instrumental / Seguridad
    assert "Bibliográfico" in tipos

def test_intimo_proclamas_soporte_not_empty(intimo_doc):
    # proclamas con evidencia real deben tener texto de soporte
    for p in intimo_doc.proclamas:
        if p.tipo_soporte in ("Subjetivo", "Objetivo", "Mixto"):
            assert p.soporte, f"Falta soporte en: {p.proclama[:40]}"

def test_intimo_referencias(intimo_doc):
    assert len(intimo_doc.referencias) >= 1
    numeros = [r.numero for r in intimo_doc.referencias]
    assert "1" in numeros

def test_intimo_intro(intimo_doc):
    assert intimo_doc.intro_texto
    assert len(intimo_doc.intro_texto) > 100


# ── Tío Nacho ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def tio_nacho_doc():
    return process_file(TIO_NACHO)

def test_tio_nacho_metadata(tio_nacho_doc):
    assert tio_nacho_doc.codigo_formula == "058IH51B"
    assert "NACHO" in tio_nacho_doc.nombre_producto
    assert tio_nacho_doc.fecha_documento == "13/02/26"

def test_tio_nacho_estudios(tio_nacho_doc):
    assert len(tio_nacho_doc.estudios) == 9
    assert tio_nacho_doc.estudios[0].codigo == "IE-GMM746-25-D-1"

def test_tio_nacho_proclamas(tio_nacho_doc):
    assert len(tio_nacho_doc.proclamas) == 14
    tipos = {p.tipo_soporte for p in tio_nacho_doc.proclamas if p.tipo_soporte}
    assert "Objetivo" in tipos
    assert "Bibliográfico" in tipos

def test_tio_nacho_modo_uso(tio_nacho_doc):
    assert tio_nacho_doc.modo_uso is not None
    assert len(tio_nacho_doc.modo_uso) > 10
