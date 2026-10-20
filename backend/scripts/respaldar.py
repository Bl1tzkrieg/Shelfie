"""Respaldo diario, para el Programador de tareas de Windows o cron.

    python -m scripts.respaldar

Deja `shelfie-AAAAMMDD-HHMM/` en la carpeta configurada (Configuración → Respaldo) y,
pase lo que pase con el respaldo, hace después la limpieza diaria (scripts.tareas),
porque esta es la única tarea programada. Sale con 0 si el respaldo salió bien y con 1 si no.
"""

import json
import logging
import sys

from app.database import SessionLocal
from app.services import respaldo
from scripts.tareas import limpiar


def main(argumentos) -> int:
    if "-h" in argumentos or "--help" in argumentos:
        print(__doc__)
        return 0
    db = SessionLocal()
    try:
        resultado = respaldo.ejecutar(db)
        try:
            limpiar(db)
        except Exception:  # noqa: BLE001 — la limpieza no cambia el resultado del respaldo
            db.rollback()
            logging.getLogger("shelfie.respaldo").exception("La limpieza diaria falló")
    finally:
        db.close()
    print(json.dumps(resultado, ensure_ascii=False))
    return 0 if resultado["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
