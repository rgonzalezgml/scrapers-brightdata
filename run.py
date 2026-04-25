"""Entry point para ejecutar scrapers GLI.

Uso:
    python run.py all
    python run.py alibaba
    python run.py alibaba indiamart cosme
"""

import asyncio
import logging
import sys
from pathlib import Path

# Asegurar que gli_scrapers sea importable desde cualquier directorio
sys.path.insert(0, str(Path(__file__).parent))

# Cargar .env si existe
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)

RUNNERS = {
    "alibaba":           "gli_scrapers.alibaba.runner",
    "indiamart":         "gli_scrapers.indiamart.runner",
    "made_in_china":     "gli_scrapers.made_in_china.runner",
    "olive_young":       "gli_scrapers.olive_young.runner",
    "cosmetics_design":  "gli_scrapers.cosmetics_design.runner",
    "cosme":             "gli_scrapers.cosme.runner",
}


def _load_main(module_path: str):
    import importlib
    mod = importlib.import_module(module_path)
    return mod.main


async def run_targets(targets: list[str]) -> None:
    mains = [_load_main(RUNNERS[t]) for t in targets]
    results = await asyncio.gather(*[fn() for fn in mains], return_exceptions=True)

    print("\n── Resultados ──────────────────────────────")
    for name, res in zip(targets, results):
        if isinstance(res, Exception):
            print(f"  {name:20s}  ERROR    {res}")
        elif res.get("status") == "ok":
            print(f"  {name:20s}  OK       inserted={res['inserted']}  job={res['job_id']}")
        else:
            print(f"  {name:20s}  FAILED   {res.get('reason', '?')}")
    print("────────────────────────────────────────────")


def main() -> None:
    args = sys.argv[1:] or ["all"]

    if args == ["all"]:
        targets = list(RUNNERS.keys())
    else:
        unknown = [a for a in args if a not in RUNNERS]
        if unknown:
            print(f"Scrapers desconocidos: {unknown}")
            print(f"Disponibles: {list(RUNNERS.keys())}")
            sys.exit(1)
        targets = args

    print(f"Ejecutando: {targets}")
    asyncio.run(run_targets(targets))


if __name__ == "__main__":
    main()
