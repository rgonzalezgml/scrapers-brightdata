"""Jerarquía de excepciones del middleware IMPI.

Todas las excepciones del dominio heredan de `IMPIError` para que los
callers puedan atrapar solo errores del scraper sin enmascarar excepciones
genéricas de la stdlib o de httpx.
"""

from __future__ import annotations


class IMPIError(Exception):
    """Clase base para todos los errores del middleware IMPI."""


class XSRFMissingError(IMPIError):
    """La cookie `XSRF-TOKEN` no fue emitida por el portal.

    Usualmente indica que el sitio cambió el flujo de inicialización o que
    hay un firewall / WAF intermedio interceptando la respuesta.
    """


class SearchIdMissingError(IMPIError):
    """El endpoint `/marcas/search/internal/record` devolvió una respuesta
    sin `id` ni `searchId`, por lo que no podemos pedir resultados."""


class IMPIAPIError(IMPIError):
    """El portal devolvió un status HTTP no-2xx.

    Conserva `status_code`, una vista previa del body y la URL para
    facilitar el diagnóstico desde logs.
    """

    def __init__(self, status_code: int, body: str, url: str) -> None:
        self.status_code = status_code
        self.body = body
        self.url = url
        super().__init__(
            f"IMPI API error {status_code} on {url}: {body[:200]}"
        )


class TimeoutError(IMPIError):  # noqa: A001 - intencional, shadow de builtin
    """Wrapper del `httpx.TimeoutException` para mantener la jerarquía."""
