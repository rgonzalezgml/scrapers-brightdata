"""Pytest config para los tests del harness.

- Asegura ``asyncio_mode = "auto"`` (viene del pytest.ini raíz).
- Resetea `_SESSIONS` y el contador del fixture mode entre tests para evitar
  sangrado de estado entre casos.
- Aisla las env vars que ``agent_harness.app`` filtra al proceso vía
  ``load_dotenv()`` (BRIGHTDATA_*) para que no contaminen a los tests de
  ``middlewares/core`` que esperan un entorno pelado.
"""

from __future__ import annotations

import os

import pytest

from agent_harness import app as app_module
from agent_harness import registry as registry_module

# Variables que el import de agent_harness.app puede filtrar vía load_dotenv.
# Las unset al final de cada test del harness para que el resto del pytest
# run vea el entorno que esperaban los tests originales del middleware.
_LEAKY_ENV_VARS = (
    "BRIGHTDATA_API_KEY",
    "BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN",
    "BRIGHTDATA_COLLECTOR_ID_COSMETICS_DESIGN",
)


@pytest.fixture(autouse=True)
def _reset_harness_state() -> None:
    app_module._SESSIONS.clear()
    registry_module.reset_fixture_state()
    yield
    app_module._SESSIONS.clear()


@pytest.fixture(autouse=True, scope="session")
def _isolate_leaky_dotenv_vars() -> None:
    """Quita las vars de BrightData que dotenv metio al importar el app."""
    saved = {k: os.environ.pop(k, None) for k in _LEAKY_ENV_VARS}
    yield
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
