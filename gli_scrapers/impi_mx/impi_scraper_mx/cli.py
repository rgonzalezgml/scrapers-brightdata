"""Entry point de `python -m impi_scraper_mx`."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from impi_scraper_mx.client import IMPIClient
from impi_scraper_mx.errors import IMPIError
from impi_scraper_mx.models import SearchInputs

logger = logging.getLogger("impi_scraper_mx.cli")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m impi_scraper_mx",
        description="Middleware local IMPI: listado + detalle de marcas por titular.",
    )
    parser.add_argument("--owner", default="GENOMMA LAB",
                        help='Titular a buscar (default: "GENOMMA LAB")')
    parser.add_argument("--days", type=int, default=None,
                        help="Filtra por DATE_EXPIRY en ventana [hoy, hoy+N]. Omite para traer todo.")
    parser.add_argument("--page-size", type=int, default=100,
                        help="Tamaño de página del listado (default: 100, max 200)")
    parser.add_argument("--max-marks", type=int, default=None,
                        help="Corta el listado tras N filas. Útil para prototipar.")
    parser.add_argument("--with-details", action="store_true",
                        help="Enriquece cada fila con GET /view/{id} (detalle completo).")
    parser.add_argument("--concurrency", type=int, default=8,
                        help="Hilos paralelos para detalles (default: 8, max 16)")
    parser.add_argument("--output", type=Path, default=None,
                        help="Archivo JSON de salida. Default: stdout.")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    _configure_logging(args.verbose)

    inputs = SearchInputs(
        owner=args.owner,
        expires_within_days=args.days,
        page_size=args.page_size,
        max_marks=args.max_marks,
        fetch_details=args.with_details,
        detail_concurrency=args.concurrency,
    )

    try:
        with IMPIClient(timeout=args.timeout) as client:
            result = client.search(inputs)
    except IMPIError as exc:
        logger.error("IMPI error: %s", exc, exc_info=args.verbose)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    payload = {
        "search_id": result.search_id,
        "total": result.total,
        "fetched": result.fetched,
        "pages": result.pages,
        "scraped_date": datetime.now(timezone.utc).date().isoformat(),
        "owner": args.owner,
        "expires_within_days": args.days,
        "with_details": args.with_details,
        "rows": [row.model_dump() for row in result.rows],
    }

    encoded = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
        print(f"Escritas {result.fetched}/{result.total} rows en {args.output}",
              file=sys.stderr)
    else:
        print(encoded)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
