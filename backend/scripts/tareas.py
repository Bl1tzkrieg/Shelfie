"""Limpieza diaria, para cron o el Programador de tareas.

    python -m scripts.tareas

Borra los intentos de acceso de más de un día, las sesiones cerradas cuyo token ya
venció y las anotaciones del registro más viejas que los días de retención
(Configuración → Registro de acciones; 0 = guardar todo).
"""

import json
import sys
from datetime import timedelta

from sqlalchemy.orm import Session

from app import models
from app.core.tiempo import ahora
from app.database import SessionLocal
from app.services import registro


def limpiar(db: Session) -> dict:
    """Hace la limpieza con su commit y devuelve cuántas filas borró de cada tabla."""
    intentos = db.query(models.IntentoAcceso).filter(
        models.IntentoAcceso.fecha < ahora() - timedelta(days=1)).delete(synchronize_session=False)
    sesiones = db.query(models.SesionCerrada).filter(
        models.SesionCerrada.expira < ahora()).delete(synchronize_session=False)
    acciones = registro.depurar(db)
    db.commit()
    return {"intentos_borrados": intentos, "sesiones_borradas": sesiones,
            "acciones_borradas": acciones}


def main(argumentos) -> int:
    if "-h" in argumentos or "--help" in argumentos:
        print(__doc__)
        return 0
    db = SessionLocal()
    try:
        resultado = limpiar(db)
    finally:
        db.close()
    print(json.dumps(resultado, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
