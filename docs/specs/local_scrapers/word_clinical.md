# Spec — word_clinical

**Módulo:** `local_scrapers/word_clinical/`  
**Tipo:** Python standalone (sin BrightData)  
**Estado:** Archivado (proyecto cancelado 2026-04-27). Implementación completa y funcional.  
**Propósito:** Extraer datos estructurados de documentos Word de "Sustento de Proclamas" (estudios clínicos/cosméticos de Genomma Lab) para alimentar el agente de claims en GeommaAI.

---

## 1. Input

### Archivos
- Formato: `.docx` protegidos con contraseña
- Se procesan en lote desde `input/` (o ruta configurable)
- Los archivos de muestra están en `input/` dentro del repo

### Derivación de contraseña
```
password = last4(first_word(filename))[::-1]
```
Donde `first_word` es el segmento antes del primer espacio en el nombre de archivo.

| Archivo | first_word | last4 | reversed = password |
|---------|-----------|-------|---------------------|
| `008MB33B CSD_INTIMO...docx` | `008MB33B` | `B33B` | `B33B` |
| `058IH51B CSD_TÍO NACHO...docx` | `058IH51B` | `H51B` | `B15H` |

> **Nota importante:** `B33B` parece no estar invertido porque es palíndromo. La regla siempre es invertir.

---

## 2. Estructura del documento Word

Todos los documentos siguen el mismo template con **5 tablas fijas**:

| # | Nombre interno | Contenido |
|---|---------------|-----------|
| Tabla 0 | Header | Fecha del documento, Versión |
| Tabla 1 | Info del producto | Nombre, Código fórmula, Modo de uso, Precauciones (opcional) |
| Tabla 2 | Estudios seguridad/eficacia | CÓDIGO, NOMBRE, TIPO ESTUDIO, AGENCIA, FECHA, INFORME |
| Tabla 3 | Plan de sustento / Proclamas | PROCLAMA, TIPO SOPORTE, SOPORTE |
| Tabla 4 | Bibliografía | N°, Descripción |

### Quirks técnicos críticos (aprendidos en implementación)

**Tabla 2 — controles de formulario (`w:sdt`):**  
Las columnas TIPO ESTUDIO, AGENCIA y FECHA están implementadas como **dropdowns y date pickers de Word** (`<w:sdt>`), no como celdas normales (`<w:tc>`). La librería `python-docx` no los ve con su API estándar. Hay que iterar los children del `<w:tr>` directamente via XML y manejar tanto `<w:tc>` como `<w:sdt><w:sdtContent><w:tc>`.

Valores observados de TIPO ESTUDIO: `Eficacia - Clínico`, `Eficacia - Sensorial`, `Eficacia - Instrumental`, `Seguridad - In vivo`, `Seguridad - In vitro`.

**Tabla 2 — columna INFORME:**  
Contiene un **OLE object** (PDF incrustado), no texto. El PDF vive dentro del `.docx` (ZIP) en `word/embeddings/oleObject{N}.bin`. El `rId` del OLE se obtiene del atributo `r:id` del elemento `<o:OLEObject>` en la celda. El PDF se extrae del stream `CONTENTS` dentro del OLE (formato OLE compound document).

**Tabla 3 — celdas fusionadas:**  
Las columnas TIPO SOPORTE y SOPORTE a veces están fusionadas. En ese caso col1 contiene ambas separadas por `\n`. El TIPO SOPORTE viene también de un `<w:sdt>` dropdown con valores: `Subjetivo`, `Objetivo`, `Bibliográfico`, `Mixto`, `N.A.`.

**Iteración de filas con celdas fusionadas:**  
`python-docx` lanza `ValueError: no tc element at grid_offset=N` al iterar filas con `row.cells` cuando hay merges multi-fila. Solución: leer XML directamente con `row._tr.findall(qn("w:tc"))` y manejar `w:sdt` manualmente.

---

## 3. Output Schema

```python
class Estudio(BaseModel):
    codigo: str
    nombre: str
    tipo_estudio: str | None      # del dropdown w:sdt
    agencia: str | None           # del dropdown w:sdt
    fecha: str | None             # del date picker w:sdt (dd/MM/yyyy)
    informe: str | None           # nombre del PDF extraído (e.g. "IME.EC.185.pdf")
    informe_paginas: int | None   # número de páginas del PDF

class Proclama(BaseModel):
    proclama: str
    tipo_soporte: str | None      # Subjetivo / Objetivo / Bibliográfico / Mixto / N.A.
    soporte: str | None           # texto de evidencia

class Referencia(BaseModel):
    numero: str
    descripcion: str

class SustentoProclamasDoc(BaseModel):
    archivo: str                  # nombre del .docx fuente
    codigo_formula: str           # Tabla 1 · Código fórmula (e.g. "008MB33B")
    nombre_producto: str          # Tabla 1 · Nombre
    fecha_documento: str | None   # Tabla 0 · Fecha
    version: str | None           # Tabla 0 · Versión
    modo_uso: str | None          # Tabla 1 · Modo de uso
    precauciones: str | None      # Tabla 1 · Precauciones (opcional)
    intro_texto: str | None       # párrafos bajo INTRODUCCIÓN
    estudios: list[Estudio]
    proclamas: list[Proclama]
    referencias: list[Referencia]
```

---

## 4. Módulos del paquete

```
local_scrapers/word_clinical/
├── __init__.py
├── models.py          # Pydantic v2 schemas
├── password.py        # derivación de contraseña del nombre de archivo
├── decryptor.py       # msoffcrypto-tool: descifrar .docx → BytesIO
├── parser.py          # extracción XML de las 5 tablas → SustentoProclamasDoc
├── pdf_extractor.py   # extrae PDFs incrustados (OLE) y cuenta páginas
├── runner.py          # orquesta input/ → output/; guarda JSON + PDFs
├── preguntas_nancy.md # preguntas pendientes al stakeholder
└── input/             # .docx de muestra (2 archivos)
```

---

## 5. Comportamiento del runner

```bash
# Procesa input/, extrae PDFs, guarda JSONs en output/
python -m local_scrapers.word_clinical.runner
```

Flujo por cada `.docx`:
1. Deriva contraseña del nombre de archivo
2. Desencripta en memoria (sin tocar disco)
3. Parsea las 5 tablas vía XML
4. Extrae PDFs incrustados → `output/{nombre_doc}/{codigo}.pdf`
   - Códigos duplicados → `IME.EC.185.pdf`, `IME.EC.185_2.pdf`
5. Guarda `output/{nombre_doc}/{codigo_formula}.json`
6. Al final guarda `output/result.json` consolidado con todos los docs

Archivos con nombre `~$*` se ignoran (temps de Word).

---

## 6. Resultados con los 2 docs de muestra

| Documento | Estudios | Proclamas | PDFs extraídos |
|-----------|----------|-----------|----------------|
| `008MB33B` Íntimo By Lomecan | 5 | 9 | 5 |
| `058IH51B` Tío Nacho Shampoo | 9 | 14 | 9 |

---

## 7. Tests

```bash
python -m pytest tests/word_clinical/ -v   # 12 tests, ~30s
```

Cubren: derivación de contraseña, metadata, conteo de estudios/proclamas, tipos de soporte, modo de uso, intro.

---

## 8. Dependencias Python

```
python-docx
msoffcrypto-tool
olefile
pymupdf          # extracción de páginas PDF
pydantic>=2
```

---

## 9. Preguntas abiertas (pendientes de Nancy)

Ver `local_scrapers/word_clinical/preguntas_nancy.md`. Las más relevantes si se reactiva el proyecto:

- ¿`Ingrediente activo`, `Duración`, `n=`, `País` del card UI de GeommaAI vienen de este Word o de otro documento?
- ¿La estructura de 5 tablas es siempre fija en todos los productos?
- ¿Necesitamos extraer el texto interno de los PDFs incrustados (no solo guardarlos)?
- ¿Los documentos pueden ser solo en inglés o mixtos? (Tío Nacho tiene proclamas bilingüe)
