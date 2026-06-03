from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Any, Dict

class CheckoutRequest(BaseModel):
    codigo_barras: str
    nro_carnet: str

class CheckinRequest(BaseModel):
    codigo_barras: str

class PrestamoResponse(BaseModel):
    id: int
    item_id: int
    usuario_id: int
    fecha_prestamo: datetime
    fecha_vencimiento: datetime
    fecha_devolucion: Optional[datetime] = None

    class Config:
        from_attributes = True

class ReturnResponse(BaseModel):
    mensaje: str
    multa_aplicada: float
    nuevo_estado_item: str