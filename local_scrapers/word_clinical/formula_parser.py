"""
Parse the formula PDF embedded in the bibliography reference whose description
contains 'fórmula'. The PDF contains a 'FÓRMULA DE PRODUCTO TERMINADO' table
with columns: [BASE*,] INGREDIENTES [INCI], FUNCIÓN, % (n/n).
"""
import fitz

from .models import FormulaIngrediente

_SKIP_INGREDIENTE = {"", "0", "total"}


def parse_formula_pdf(pdf_bytes: bytes) -> list[FormulaIngrediente]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    tabs = page.find_tables()
    if not tabs.tables:
        return []

    tab = tabs.tables[0]
    rows = tab.extract()

    # Locate the header row by finding the one that contains INGREDIENTES and %
    header_idx = None
    col_base = col_ingrediente = col_funcion = col_porcentaje = None

    for i, row in enumerate(rows):
        cells = [(c or "").strip() for c in row]
        if any("INGREDIENTES" in c for c in cells):
            header_idx = i
            for j, c in enumerate(cells):
                if "INGREDIENTES" in c:
                    col_ingrediente = j
                elif "FUNCIÓN" in c or "FUNCION" in c:
                    col_funcion = j
                elif "%" in c:
                    col_porcentaje = j
                elif "BASE" in c:
                    col_base = j
            break

    if header_idx is None or col_ingrediente is None:
        return []

    resultado: list[FormulaIngrediente] = []
    for row in rows[header_idx + 1:]:
        cells = [(c or "").strip() for c in row]

        def get(idx) -> str:
            return cells[idx] if idx is not None and idx < len(cells) else ""

        ingrediente = get(col_ingrediente)
        if not ingrediente or ingrediente.lower() in _SKIP_INGREDIENTE:
            continue

        porcentaje_str = get(col_porcentaje)
        try:
            porcentaje = float(porcentaje_str) if porcentaje_str else None
        except ValueError:
            porcentaje = None

        if porcentaje == 0.0:
            continue

        funcion = get(col_funcion) or None
        es_base: bool | None = None
        if col_base is not None:
            es_base = bool(get(col_base))

        resultado.append(FormulaIngrediente(
            ingrediente=ingrediente,
            funcion=funcion,
            porcentaje=porcentaje,
            es_base=es_base,
        ))

    return resultado
