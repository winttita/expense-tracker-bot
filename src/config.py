"""Carga y validación de la configuración por variables de entorno."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    telegram_allowed_chat_id: int
    nvidia_api_key: str
    nvidia_model: str
    google_service_account_json: str
    google_sheet_id: str
    google_sheet_name: str
    timezone: str


def cargar_config(env_file: str | None = None) -> Config:
    load_dotenv(env_file)

    requeridas = [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_ALLOWED_CHAT_ID",
        "NVIDIA_API_KEY",
        "GOOGLE_SERVICE_ACCOUNT_JSON",
        "GOOGLE_SHEET_ID",
    ]
    faltantes = [k for k in requeridas if not os.environ.get(k)]
    if faltantes:
        raise RuntimeError(
            f"Faltan variables de entorno: {', '.join(faltantes)}. "
            "Copiá .env.example a .env y completá los valores."
        )

    try:
        chat_id = int(os.environ["TELEGRAM_ALLOWED_CHAT_ID"])
    except ValueError as exc:
        raise RuntimeError("TELEGRAM_ALLOWED_CHAT_ID debe ser numérico") from exc

    return Config(
        telegram_bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        telegram_allowed_chat_id=chat_id,
        nvidia_api_key=os.environ["NVIDIA_API_KEY"],
        nvidia_model=os.environ.get("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct"),
        google_service_account_json=os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"],
        google_sheet_id=os.environ["GOOGLE_SHEET_ID"],
        google_sheet_name=os.environ.get("GOOGLE_SHEET_NAME", "Sheet1"),
        timezone=os.environ.get("TIMEZONE", "America/Argentina/Buenos_Aires"),
    )
