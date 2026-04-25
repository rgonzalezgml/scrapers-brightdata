"""Paquete `impi_scraper_mx` — middleware local para el portal IMPI México.

Expone el cliente principal y los modelos de dominio. Ver `README.md` para
detalles de uso.
"""

from impi_scraper_mx.client import IMPIClient
from impi_scraper_mx.errors import (
    IMPIAPIError,
    IMPIError,
    SearchIdMissingError,
    TimeoutError,
    XSRFMissingError,
)
from impi_scraper_mx.models import Marca, SearchInputs, SearchResult

__all__ = [
    "IMPIClient",
    "SearchInputs",
    "SearchResult",
    "Marca",
    "IMPIError",
    "XSRFMissingError",
    "SearchIdMissingError",
    "IMPIAPIError",
    "TimeoutError",
]

__version__ = "0.1.0"
