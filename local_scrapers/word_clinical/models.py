from pydantic import BaseModel


class Estudio(BaseModel):
    codigo: str
    nombre: str
    tipo_estudio: str | None = None
    agencia: str | None = None
    fecha: str | None = None
    informe: str | None = None


class Proclama(BaseModel):
    proclama: str
    tipo_soporte: str | None = None
    soporte: str | None = None


class Referencia(BaseModel):
    numero: str
    descripcion: str


class SustentoProclamasDoc(BaseModel):
    archivo: str
    codigo_formula: str
    nombre_producto: str
    fecha_documento: str | None = None
    version: str | None = None
    modo_uso: str | None = None
    precauciones: str | None = None
    intro_texto: str | None = None
    estudios: list[Estudio] = []
    proclamas: list[Proclama] = []
    referencias: list[Referencia] = []
