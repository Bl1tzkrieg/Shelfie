"""Limpieza del registro de acciones, para cron o el Programador de tareas.

    python -m scripts.tareas

Borra las anotaciones más viejas que los días de retención configurados
(Configuración → Registro de acciones; 0 = guardar todo).
"""

import sys

from app.database import SessionLocal
from app.services import registro


def main(argumentos) -> int:
    if "-h" in argumentos or "--help" in argumentos:
        print(__doc__)
        return 0
    db = SessionLocal()
    try:
        borradas = registro.depurar(db)
        db.commit()
    finally:
        db.close()
    print(f"Anotaciones borradas del registro: {borradas}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
