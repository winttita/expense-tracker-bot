"""Entrypoint: arranca el bot de Telegram en modo long polling."""

import asyncio
import logging

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from .config import cargar_config
from .handlers import (
    cmd_borrar,
    cmd_corregir,
    cmd_help,
    manejador_errores,
    manejar_texto,
)
from .llm_client import LLMClient
from .sheets_client import SheetsClient


async def _inicializar(app: Application) -> None:
    """Crea el cliente de Sheets e inicializa encabezados si la hoja está vacía."""
    config = app.bot_data["config"]
    sheets = await SheetsClient.crear(
        config.google_service_account_json,
        config.google_sheet_id,
        config.google_sheet_name,
    )
    await sheets.inicializar_encabezados()
    app.bot_data["sheets"] = sheets
    app.bot_data["llm"] = LLMClient(config.nvidia_api_key, config.nvidia_model)
    app.bot_data["allowed_chat_id"] = config.telegram_allowed_chat_id
    app.bot_data["timezone"] = config.timezone


def main() -> None:
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    env_file = sys.argv[1] if len(sys.argv) > 1 else None
    config = cargar_config(env_file)

    app = Application.builder().token(config.telegram_bot_token).build()
    app.bot_data["config"] = config
    app.post_init = _inicializar

    app.add_handler(CommandHandler("corregir", cmd_corregir))
    app.add_handler(CommandHandler("borrar", cmd_borrar))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_help))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_texto)
    )
    app.add_error_handler(manejador_errores)

    logging.getLogger(__name__).info("Bot iniciado (long polling)")
    app.run_polling()


if __name__ == "__main__":
    main()
