"""Modelos pydantic v2 del middleware IMPI."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SearchInputs(BaseModel):
    """Parámetros de entrada para `IMPIClient.search`."""

    owner: str = Field(..., description="Titular (substring) a buscar.")
    expires_within_days: int | None = Field(
        None,
        ge=0,
        description=(
            "Si se provee, filtra por DATE_EXPIRY en [hoy, hoy+N]. Si es None, "
            "no aplica filtro de fecha (trae todo el universo del titular)."
        ),
    )
    page_size: int = Field(100, gt=0, le=200, description="Tamaño de página.")
    max_marks: int | None = Field(
        None,
        gt=0,
        description="Corta el listado antes de paginar todo. Útil para probar.",
    )
    fetch_details: bool = Field(
        False,
        description="Si True, llama /view/{id} por cada marca para enriquecer.",
    )
    detail_concurrency: int = Field(
        8, gt=0, le=16, description="Hilos paralelos para traer detalles."
    )


class Marca(BaseModel):
    """Una fila combinada listado + (opcional) detalle.

    Campos del listado siempre presentes; `detalle` solo si `fetch_details=True`.
    """

    # --- listado ---
    id: str | None = None
    denominacion: str | None = None
    expediente: str | None = None
    registro: str | None = None
    estatus: str | None = None
    tipo_solicitud: str | None = None
    titular: str | None = None
    clases: list[int] = Field(default_factory=list)
    productos_servicios: str | None = None
    fecha_solicitud: str | None = None
    fecha_terminacion: str | None = None
    fecha_cancelacion: str | None = None
    imagen: Any = None

    # --- detalle (passthrough, presente si fetch_details=True) ---
    detalle: dict[str, Any] | None = None

    # --- meta ---
    scraped_date: str
    scraper_flags: list[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    rows: list[Marca]
    total: int
    search_id: str
    fetched: int
    pages: int
