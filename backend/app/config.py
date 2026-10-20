import warnings
from pathlib import Path

from pydantic_settings import BaseSettings

# Valores de ejemplo que trae el código o la plantilla .env.example: firmar con ellos
# es como no firmar (cualquiera que los lea puede re-firmar un token observado).
CLAVES_CONOCIDAS = {"shelfie-dev-only-cambiar-en-produccion", "cambiar-esta-clave"}
LARGO_MINIMO_CLAVE = 32


class Settings(BaseSettings):
    DATABASE_URL: str
    PROJECT_NAME: str = "Shelfie Backend API"
    # desarrollo o produccion. En produccion el backend no arranca con una SECRET_KEY débil.
    ENTORNO: str = "desarrollo"
    # Firma de los tokens de acceso. En producción debe venir del entorno.
    SECRET_KEY: str = "shelfie-dev-only-cambiar-en-produccion"
    # Orígenes permitidos por CORS, separados por coma.
    CORS_ORIGINS: str = "http://localhost:3000"
    # Sesión de la intranet (cookie httpOnly).
    SESION_HORAS: int = 12
    # En producción (HTTPS) debe ser true para que la cookie solo viaje cifrada.
    COOKIE_SECURE: bool = False
    # Zona horaria de la biblioteca: define "qué día es" para vencimientos y calendario.
    ZONA_HORARIA: str = "America/Caracas"
    # El frontend exportado que sirve el backend. Una ruta relativa se toma desde
    # backend/ (no desde la carpeta en la que se arranque uvicorn).
    FRONTEND_DIR: str = "../frontend/out"

    @property
    def frontend_dir(self) -> Path:
        ruta = Path(self.FRONTEND_DIR)
        if not ruta.is_absolute():
            ruta = Path(__file__).resolve().parent.parent / ruta
        return ruta.resolve()

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        # Un .env de Shelfie completo (correo, tareas automáticas) sigue sirviendo: lo que
        # lite ya no usa se ignora en vez de impedir el arranque.
        extra = "ignore"


def problema_de_clave(s: "Settings") -> str | None:
    """Por qué la SECRET_KEY no sirve para producción, o None si está bien."""
    if s.SECRET_KEY in CLAVES_CONOCIDAS:
        return "SECRET_KEY tiene el valor de ejemplo"
    if len(s.SECRET_KEY.encode()) < LARGO_MINIMO_CLAVE:
        return f"SECRET_KEY tiene menos de {LARGO_MINIMO_CLAVE} bytes"
    return None


def comprobar_clave_de_firma(s: "Settings") -> None:
    """Al arrancar: en producción (o con cookies solo HTTPS) una clave débil detiene el backend;
    en desarrollo solo se advierte."""
    problema = problema_de_clave(s)
    if not problema:
        return
    consejo = 'Genera una con: python -c "import secrets; print(secrets.token_urlsafe(48))"'
    if s.ENTORNO.strip().lower() == "produccion" or s.COOKIE_SECURE:
        raise RuntimeError(f"{problema}. {consejo}")
    warnings.warn(f"{problema}: vale para desarrollo, no para producción. {consejo}", stacklevel=2)


settings = Settings()
