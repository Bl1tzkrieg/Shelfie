"""Corre las tareas programadas desde la consola (para cron o el Programador de tareas).

    python -m scripts.tareas              # las diarias (y envía la cola)
    python -m scripts.tareas enviar_cola  # solo la cola de correos
    python -m scripts.tareas --lista      # qué tareas hay

Con TAREAS_AUTOMATICAS=true el backend ya las corre solo; esto sirve cuando está en
false (varios procesos, o se prefiere un cron) o para forzar una corrida.
"""

import json
import sys

from app.database import SessionLocal
from app.services import tareas


def main(argumentos) -> int:
    if "--lista" in argumentos or "-h" in argumentos or "--help" in argumentos:
        print(__doc__)
        for clave, t in tareas.TAREAS.items():
            print(f"  {clave:18} {t['descripcion']}")
        return 0
    nombre = argumentos[0] if argumentos else "diarias"
    db = SessionLocal()
    try:
        corrida = tareas.ejecutar(db, nombre, origen="consola")
    finally:
        db.close()
    print(json.dumps(corrida, ensure_ascii=False, indent=2, default=str))
    return 0 if corrida["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
