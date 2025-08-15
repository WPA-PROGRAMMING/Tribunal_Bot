# backend/models.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class Usuario(BaseModel):
    telegram_id: int
    nombre: str
    prueba_activa: bool
    fecha_inicio_prueba: Optional[datetime]
    suscrito: bool

class Expediente(BaseModel):
    usuario_id: int
    distrito: str
    juzgado: str
    numero: str
    ano: str
    identificador: str
    ultimo_chequeo: Optional[datetime]
    ultima_actualizacion: Optional[str]
    historial: List[dict] = []


class Suscripcion(BaseModel):
    usuario_id: int
    activa: bool
    fecha_inicio: datetime
    fecha_fin: datetime
