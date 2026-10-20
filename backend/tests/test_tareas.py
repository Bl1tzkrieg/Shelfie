"""Limpieza diaria: intentos de acceso, sesiones cerradas y registro de acciones."""

from datetime import timedelta

from app import models
from app.core.tiempo import ahora
from scripts.tareas import limpiar


def test_limpiar_borra_intentos_viejos_y_sesiones_expiradas(db):
    I, S, R = models.IntentoAcceso, models.SesionCerrada, models.RegistroAccion
    db.add_all([
        I(identificador="viejo", ip="1.1.1.1", fecha=ahora() - timedelta(days=2)),
        I(identificador="reciente", ip="1.1.1.1", fecha=ahora() - timedelta(hours=2)),
        S(jti="vencida", expira=ahora() - timedelta(minutes=1)),
        S(jti="vigente", expira=ahora() + timedelta(hours=3)),
        R(fecha=ahora() - timedelta(days=800), modulo="sesion", accion="entrada", descripcion="viejo"),
        R(fecha=ahora() - timedelta(days=10), modulo="sesion", accion="entrada", descripcion="reciente"),
    ])
    db.commit()

    assert limpiar(db) == {"intentos_borrados": 1, "sesiones_borradas": 1, "acciones_borradas": 1}

    db.expire_all()
    assert [i.identificador for i in db.query(I).all()] == ["reciente"]
    assert [s.jti for s in db.query(S).all()] == ["vigente"]
    assert [r.descripcion for r in db.query(R).all()] == ["reciente"]
