"""SnowflakeMapper — mapper universal raw-scraper → tabla Snowflake DDL.

Uso por scraper:

    from gli_scrapers.snowflake import SnowflakeMapper

    MAPPER = SnowflakeMapper(
        table="DEV_STG.GNM_MEX.SRC_ALIBABA_PROV_HIST",
        source="alibaba",
        field_map={"product_url": "URL_PRODUCTO", ...},
        variant_fields={"DS_INPUT"},
    )

    inserted = MAPPER.insert(rows, conn, job_id="run-001")

Contrato:
- ``field_map``   : raw_key → nombre de columna DDL. Claves ausentes en el
                    raw row se insertan como NULL.
- ``variant_fields``: columnas tipo VARIANT — el valor se serializa a JSON
                    string antes de enviarlo al conector.
- Campo de auditoría FT_FUENTE se agrega automáticamente. CREATED_AT la pone Snowflake vía DEFAULT.
- Campos del raw que NO están en field_map se descartan silenciosamente.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SnowflakeMapper:
    table: str
    source: str
    field_map: dict[str, str]
    variant_fields: set[str] = field(default_factory=set)

    def map_row(self, raw: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for raw_key, col in self.field_map.items():
            val = raw.get(raw_key)
            # VARIANT: serializar a JSON string — el SQL usará parse_json(%s)
            if col in self.variant_fields and val is not None:
                val = json.dumps(val, ensure_ascii=False)
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
