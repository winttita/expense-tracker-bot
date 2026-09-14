"""Handlers de Telegram: flujo de gastos, /corregir, /borrar, /help."""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ContextTypes

from .llm_client import LLMClient, LLMError
from .models import Gasto
from .sheets_client import CAMPOS_CORREGIBLES, SheetsClient
from .taxonomia import es_valida, taxonomia_como_texto

logger = logging.getLogger(__name__)

HELP_TEXTO = (
    "Comandos disponibles:\n"
    "• Escribí un gasto en texto libre (ej: `850 nafta`)\n"
    "• /corregir <campo> <valor> — corrige el último gasto cargado. "
    f"Campos: {', '.join(CAMPOS_CORREGIBLES)}\n"
    "• /borrar — elimina el último gasto cargado\n"
    "• /help — esta ayuda"
)


def _es_autorizado(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    if chat is None or chat.id != context.bot_data["allowed_chat_id"]:
        logger.warning("Mensaje de chat no autorizado: %s", chat.id if chat else None)
        return False
    return True


def _ahora(tz_name: str) -> str:
    return datetime.now(ZoneInfo(tz_name)).strftime("%Y-%m-%d %H:%M")


def _msg_confirmacion(gasto: Gasto) -> str:
    return (
        f"✅ Cargado: {gasto.monto:g} {gasto.moneda} - {gasto.descripcion}\n"
        f"📁 {gasto.macro_categoria} > {gasto.subcategoria}\n"
        f"💳 {gasto.cuenta_origen}"
    )


async def _extraer_con_validacion(llm: LLMClient, texto: str) -> tuple[dict, str | None]:
    """Extrae el gasto con el LLM. Devuelve (data, error_categoria|None).

    Si la categoría es inválida, reintenta una vez informando el error.
    """
    data = await llm.extraer_gasto(texto)
    macro, sub = (data.get("macro_categoria") or "").strip(), (
        data.get("subcategoria") or ""
    ).strip()
    if es_valida(macro, sub):
        return data, None

    logger.info("Categoría inválida del LLM (%s > %s), reintentando", macro, sub)
    data = await llm.extraer_gasto(texto, error_previo=f"{macro} > {sub}")
    macro, sub = (data.get("macro_categoria") or "").strip(), (
        data.get("subcategoria") or ""
    ).strip()
    if es_valida(macro, sub):
        return data, None
    return data, f"{macro} > {sub}"


async def _guardar_gasto(
    context: ContextTypes.DEFAULT_TYPE, data: dict
) -> Gasto:
    """Construye el Gasto (valida taxonomía y monto) y lo persiste."""
    gasto = Gasto.desde_llm(data)
    sheets: SheetsClient = context.bot_data["sheets"]
    fecha = _ahora(context.bot_data["timezone"])
    await sheets.append_row(gasto.como_fila(fecha))
    return gasto


async def manejar_texto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mensaje de texto libre: nuevo gasto o completado de un gasto pendiente."""
    if not _es_autorizado(update, context):
        return
    if update.message is None or update.message.text is None:
        return

    texto = update.message.text.strip()
    logger.info("Mensaje recibido (%d chars)", len(texto))
    llm: LLMClient = context.bot_data["llm"]

    pendiente = context.user_data.get("pendiente")
    if pendiente:
        await _completar_pendiente(update, context, pendiente, texto)
        return

    try:
        data, error_categoria = await _extraer_con_validacion(llm, texto)
    except LLMError:
        await update.message.reply_text("⚠️ No pude procesar tu mensaje ahora, intentá de nuevo en un rato.")
        return

    if error_categoria:
        # Tras el reintento sigue fallando: queda pendiente de categoría manual
        context.user_data["pendiente"] = {"modo": "categoria", "data": data}
        await update.message.reply_text(
            "🤔 No pude clasificar tu gasto automáticamente. "
            "Respondé con la categoría exacta de esta lista "
            "(formato: Macro-Categoría > Subcategoría):\n\n" + taxonomia_como_texto()
        )
        return

    try:
        gasto = await _guardar_gasto(context, data)
    except ValueError:
        # Monto ausente o inválido: pedir aclaración
        context.user_data["pendiente"] = {"modo": "monto", "data": data}
        await update.message.reply_text(
            "🤔 No pude identificar el monto. Respondé solo con el número "
            "(ej: 850 o -1500.50)."
        )
        return

    await update.message.reply_text(_msg_confirmacion(gasto))


async def _completar_pendiente(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    pendiente: dict,
    texto: str,
) -> None:
    data = pendiente["data"]
    if pendiente["modo"] == "categoria":
        partes = [p.strip() for p in texto.split(">", maxsplit=1)]
        if len(partes) != 2 or not es_valida(partes[0], partes[1]):
            await update.message.reply_text(
                "Esa categoría no es válida. Usá el formato exacto "
                "Macro-Categoría > Subcategoría, de esta lista:\n\n"
                + taxonomia_como_texto()
            )
            return
        data["macro_categoria"], data["subcategoria"] = partes
    elif pendiente["modo"] == "monto":
        try:
            data["monto"] = float(texto.replace(",", "."))
        except ValueError:
            await update.message.reply_text("Eso no es un número válido. Intentá de nuevo (ej: 850 o -1500.50).")
            return

    try:
        gasto = await _guardar_gasto(context, data)
    except ValueError:
        # Sigue faltando el monto tras definir la categoría
        context.user_data["pendiente"] = {"modo": "monto", "data": data}
        await update.message.reply_text(
            "Categoría lista. Ahora indicame el monto (ej: 850 o -1500.50)."
        )
        return
    context.user_data.pop("pendiente", None)
    await update.message.reply_text(_msg_confirmacion(gasto))


async def cmd_corregir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Corrige un campo del último gasto cargado: /corregir <campo> <valor>."""
    if not _es_autorizado(update, context):
        return
    assert update.message is not None

    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "Uso: /corregir <campo> <valor>. "
            f"Campos: {', '.join(CAMPOS_CORREGIBLES)}"
        )
        return

    campo, valor = args[0].lower(), " ".join(args[1:])
    if campo not in CAMPOS_CORREGIBLES:
        await update.message.reply_text(
            f"Campo inválido: {campo}. Válidos: {', '.join(CAMPOS_CORREGIBLES)}"
        )
        return
    if campo == "monto":
        try:
            float(valor)
        except ValueError:
            await update.message.reply_text("El monto debe ser numérico (ej: /corregir monto -900).")
            return
    if campo in ("macro_categoria", "subcategoria"):
        await update.message.reply_text(
            "Recordá que la categoría debe existir en la taxonomía. Revisá /help para el formato."
        )

    sheets: SheetsClient = context.bot_data["sheets"]
    ultima = await sheets.ultima_fila()
    if ultima is None:
        await update.message.reply_text("No hay ningún gasto cargado para corregir.")
        return

    nro_fila, _ = ultima
    await sheets.actualizar_celda(nro_fila, campo, valor)
    await update.message.reply_text(f"✏️ Corregido: {campo} = {valor} (fila {nro_fila}).")


async def cmd_borrar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Elimina el último gasto cargado y confirma qué se borró."""
    if not _es_autorizado(update, context):
        return
    assert update.message is not None

    sheets: SheetsClient = context.bot_data["sheets"]
    ultima = await sheets.ultima_fila()
    if ultima is None:
        await update.message.reply_text("No hay ningún gasto cargado para borrar.")
        return

    nro_fila, valores = ultima
    await sheets.borrar_fila(nro_fila)
    await update.message.reply_text(
        "🗑️ Se borró el último gasto cargado:\n"
        f"{valores[1]} {valores[2]} - {valores[6]}\n"
        f"📁 {valores[3]} > {valores[4]}"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _es_autorizado(update, context):
        return
    assert update.message is not None
    await update.message.reply_text(HELP_TEXTO)


async def manejador_errores(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Loguea la excepción completa y responde un mensaje genérico."""
    logger.exception("Error no controlado procesando update", exc_info=context.error)
    if isinstance(update, Update) and update.message is not None:
        await update.message.reply_text("😵 Algo salió mal, intentá de nuevo.")
