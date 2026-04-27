# Spec — word_clinical

**Módulo:** `local_scrapers/word_clinical/`  
**Tipo:** Python standalone (sin BrightData)  
**Propósito:** Extraer datos estructurados de documentos Word de "Sustento de Proclamas" (estudios clínicos/cosméticos de Genomma Lab) para alimentar el agente de claims en GeommaAI.

---

## 1. Input

### Archivos
- Formato: `.docx` protegidos con contraseña
- Se procesan en lote desde `input/` (o ruta configurable)

### Derivación de contraseña
```
password = last4(first_word(filename))[::-1]
```
Donde `first_word` es el segmento antes del primer espacio en el nombre de archivo.

| Archivo | first_word | last4 | reversed = password |
|---------|-----------|-------|---------------------|
| `008MB33B CSD_INTIMO...docx` | `008MB33B` | `B33B` | `B33B` |
| `058IH51B CSD_TÍO NACHO...docx` | `058IH51B` | `H51B` | `B15H` |

---

## 2. Estructura del documento Word

Ambos documentos siguen el mismo template con **5 tablas fijas**:

| # | Nombre interno | Contenido |
|---|---------------|-----------|
| Tabla 0 | Header | Fecha del documento, Versión |
| Tabla 1 | Info del producto | Nombre, Código fórmula, Modo de uso, Precauciones (opcional) |
| Tabla 2 | Estudios seguridad/eficacia | CÓDIGO, NOMBRE, TIPO ESTUDIO, AGENCIA, FECHA, INFORME |
| Tabla 3 | Plan de sustento / Proclamas | PROCLAMA, TIPO SOPORTE, SOPORTE |
| Tabla 4 | Bibliografía | N°, Descripción |

**Secciones de texto (párrafos):**
- `INTRODUCCIÓN` + 3 párrafos de contexto regulatorio
- `ESTUDIOS SEGURIDAD Y EFICACIA` (encabezado de Tabla 2)
- `PLAN DE SUSTENTO` (encabezado de Tabla 3)
- `BIBLIOGRAFÍA` (encabezado de Tabla 4)

**Nota Tabla 2:** Las columnas TIPO ESTUDIO, AGENCIA, FECHA e INFORME pueden estar vacías (documentos en etapa temprana). Extraer si existen, `null` si no.

**Nota Tabla 3:** Las columnas TIPO SOPORTE y SOPORTE pueden aparecer fusionadas en la misma celda. En ese caso, la primera línea es el tipo y el resto es el texto de evidencia.

---

## 3. Output Schema (por documento)

```python
class Estudio(BaseModel):
    codigo: str
    nombre: str
    tipo_estudio: str | None
    agencia: str | None
    fecha: str | None
    informe: str | None          # nombre del PDF incrustado (TBD)

class Proclama(BaseModel):
    proclama: str
    tipo_soporte: str | None     # Sensorial / Instrumental / Seguridad / Formulación / etc.
    soporte: str | None          # texto de evidencia

class Referencia(BaseModel):
    numero: str
    descripcion: str

class SustentoProclamasDoc(BaseModel):
    # Metadata
    archivo: str                 # nombre del archivo fuente
    codigo_formula: str          # Tabla 1 · Código fórmula
    nombre_producto: str         # Tabla 1 · Nombre
    fecha_documento: str | None  # Tabla 0 · Fecha
    version: str | None          # Tabla 0 · Versión
    modo_uso: str | None         # Tabla 1 · Modo de uso
    precauciones: str | None     # Tabla 1 · Precauciones (opcional)
    intro_texto: str | None      # párrafos bajo INTRODUCCIÓN

    # Contenido
    estudios: list[Estudio]
    proclamas: list[Proclama]
    referencias: list[Referencia]
```

---

## 4. Módulos del paquete

```
local_scrapers/word_clinical/
├── __init__.py
├── parser.py          # extracción con python-docx → SustentoProclamasDoc
├── decryptor.py       # msoffcrypto-tool: descifrar .docx → BytesIO
├── password.py        # lógica de derivación de contraseña
├── models.py          # Pydantic models (schema de arriba)
├── runner.py          # procesa carpeta input/ → lista de resultados
└── input/             # archivos .docx a procesar
```

---

## 5. Comportamiento esperado

1. `runner.py` escanea `input/` buscando `*.docx`
2. Para cada archivo: deriva la contraseña, desencripta en memoria, parsea
3. Si la contraseña falla → loguea error, continua con el siguiente
4. Output: lista de `SustentoProclamasDoc` (JSON o directo a Snowflake)
5. Los campos vacíos se almacenan como `null`, no se omiten del output

---

## 6. Preguntas pendientes (ver `preguntas_nancy.md`)

- ¿Las columnas vacías en Tabla 2 (TIPO, AGENCIA, FECHA, INFORME) son normales?  → **Asumido: sí, se extraen como `null`**
- ¿`Ingrediente activo`, `Duración`, `n=`, `País` del card UI vienen de este Word o de otro documento?
- ¿La estructura de 5 tablas es siempre fija?
- ¿Necesitamos extraer el contenido de los PDFs incrustados?
- ¿Documentos en inglés, español o mixtos?

---

## 7. Dependencias Python

```
python-docx
msoffcrypto-tool
pydantic>=2
```
