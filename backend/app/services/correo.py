"""Envío de correo: SMTP real o, para desarrollo, un archivo .eml por mensaje.

Es la única pieza que habla con el mundo exterior; el resto de los avisos solo
arma mensajes y los deja en la cola. CORREO_MODO elige el transporte:

- archivo (por defecto): cada correo se escribe en CARPETA_CORREO como .eml, que
  se abre con cualquier cliente de correo. Sirve para probar sin un servidor.
- smtp: se envía con SMTP_HOST/SMTP_PUERTO, con STARTTLS, SSL o sin cifrar.
- desactivado: nada sale; los avisos esperan en la cola.
"""

import re
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

from app.config import settings

MODOS = ("archivo", "smtp", "desactivado")


class CorreoNoEnviado(Exception):
    """El transporte rechazó el mensaje o no está configurado."""


def modo() -> str:
    valor = (settings.CORREO_MODO or "archivo").strip().lower()
    return valor if valor in MODOS else "archivo"


def estado() -> dict:
    """Lo que la intranet muestra del transporte (sin la clave)."""
    m = modo()
    return {
        "modo": m,
        "remitente": settings.CORREO_REMITENTE,
        "servidor": f"{settings.SMTP_HOST}:{settings.SMTP_PUERTO}" if m == "smtp" else None,
        "carpeta": str(_carpeta()) if m == "archivo" else None,
        "listo": m == "archivo" or (m == "smtp" and bool(settings.SMTP_HOST)),
    }


def _carpeta() -> Path:
    carpeta = Path(settings.CARPETA_CORREO)
    if not carpeta.is_absolute():
        carpeta = Path(__file__).resolve().parents[2] / carpeta
    return carpeta


def _mensaje(destinatario: str, asunto: str, cuerpo: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = settings.CORREO_REMITENTE
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="shelfie")
    msg.set_content(cuerpo)
    return msg


def enviar(destinatario: str, asunto: str, cuerpo: str) -> None:
    """Entrega un correo o levanta CorreoNoEnviado con el motivo."""
    m = modo()
    msg = _mensaje(destinatario, asunto, cuerpo)
    if m == "desactivado":
        raise CorreoNoEnviado("El envío de correo está desactivado (CORREO_MODO=desactivado)")
    if m == "archivo":
        carpeta = _carpeta()
        carpeta.mkdir(parents=True, exist_ok=True)
        nombre = re.sub(r"[^\w.@-]+", "_", destinatario)[:60]
        archivo = carpeta / f"{datetime.now():%Y%m%d-%H%M%S-%f}-{nombre}.eml"
        archivo.write_bytes(bytes(msg))
        return
    if not settings.SMTP_HOST:
        raise CorreoNoEnviado("Falta SMTP_HOST en el .env del backend")
    try:
        seguridad = (settings.SMTP_SEGURIDAD or "starttls").lower()
        if seguridad == "ssl":
            servidor = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PUERTO, timeout=20,
                                        context=ssl.create_default_context())
        else:
            servidor = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PUERTO, timeout=20)
        with servidor:
            if seguridad == "starttls":
                servidor.starttls(context=ssl.create_default_context())
            if settings.SMTP_USUARIO:
                servidor.login(settings.SMTP_USUARIO, settings.SMTP_CLAVE)
            servidor.send_message(msg)
    except (smtplib.SMTPException, OSError) as error:
        raise CorreoNoEnviado(f"{type(error).__name__}: {error}") from error
