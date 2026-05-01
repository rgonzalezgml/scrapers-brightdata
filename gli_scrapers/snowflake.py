"""SnowflakeMapper — mapper universal raw-scraper → tabla Snowflake DDL.

Uso por scraper:

    from gli_scrapers.snowflake import SnowflakeMapper

    MAPPER = SnowflakeMapper(
        table="DEV_STG.GNM_MEX.SRC_ALIBABA_PROV_HIST",
        source="alibaba",
        field_map={"product_url": "URL_PRODUCTO", ...},
        variant_fields={"DS_INPUT"},
        date_fields={"DT_PERIODO_INICIO", "DT_PERIODO_FIN"},
    )

    inserted = MAPPER.insert(rows, conn)

Contrato:
- ``field_map``    : raw_key → nombre de columna DDL. Claves ausentes en el
                     raw row se insertan como NULL.
- ``variant_fields``: columnas tipo VARIANT — el valor se serializa a JSON
                     string antes de enviarlo al conector.
- ``date_fields``  : columnas tipo DATE — el valor se normaliza a YYYY-MM-DD
                     (reemplaza separadores / o . por -) antes de insertar.
- Campo de auditoría FT_FUENTE se agrega automáticamente. CREATED_AT la pone Snowflake vía DEFAULT.
- Campos del raw que NO están en field_map se descartan silenciosamente.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


def _normalize_date(val: Any) -> str | None:
    """Normaliza una fecha a YYYY-MM-DD aceptada por Snowflake DATE.

    Soporta:
      - "2026/4/23"               → "2026-04-23"  (barras, sin zero-pad)
      - "2026.04.23"              → "2026-04-23"  (puntos)
      - "2021-10-15T00:00:00Z"    → "2021-10-15"  (ISO 8601 con hora)
      - "2021-10-15T00:00:00.000Z"→ "2021-10-15"  (ISO 8601 con ms)
    """
    if val is None:
        return None
    s = str(val).strip()
    # Truncar parte horaria si existe (ISO 8601: "2021-10-15T...")
    if "T" in s:
        s = s.split("T")[0]
    # Reemplaza separadores / o . por -
    s = re.sub(r"[/.]", "-", s)
    # Zero-pad month y day
    parts = s.split("-")
    if len(parts) == 3:
        return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
    return s


@dataclass
class SnowflakeMapper:
    table: str
    source: str
    field_map: dict[str, str]
    variant_fields: set[str] = field(default_factory=set)
    date_fields: set[str] = field(default_factory=set)

    def map_row(self, raw: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for raw_key, col in self.field_map.items():
            val = raw.get(raw_key)
            if col in self.variant_fields and val is not None:
                val = json.dumps(val, ensure_ascii=False)
            elif col in self.date_fields:
                val = _normalize_date(val)
            out[col] = val
        out["FT_FUENTE"] = self.source
        return out

    def insert(
        self,
        rows: list[dict[str, Any]],
        conn,
        job_id: str | None = None,
    ) -> int:
        if not rows:
            return 0

        mapped = [self.map_row(r) for r in rows]
        cols = list(mapped[0].keys())

        # parse_json() no es válido en VALUES con executemany → usar SELECT
        select_exprs = ", ".join(
            f"parse_json(%s)" if col in self.variant_fields else "%s"
            for col in cols
        )
        col_names = ", ".join(f'"{c}"' for c in cols)
        sql = f"INSERT INTO {self.table} ({col_names}) SELECT {select_exprs}"
        data = [[row[c] for c in cols] for row in mapped]

        cur = conn.cursor()
        for row_data in data:
            cur.execute(sql, row_data)
        return len(data)
