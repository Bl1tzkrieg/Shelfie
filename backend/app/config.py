from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    PROJECT_NAME: str = "Shelfie Backend API"
    # Firma de los tokens de acceso. En producción debe venir del entorno.
    SECRET_KEY: str = "shelfie-dev-only-cambiar-en-produccion"
    # Orígenes permitidos por CORS, separados por coma.
    CORS_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    class Config:
        env_file = ".env"


settings = Settings()
