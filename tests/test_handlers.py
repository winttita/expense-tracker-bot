"""Tests de handlers con LLM y Sheets mockeados (nunca pegan a APIs reales)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.handlers import cmd_borrar, cmd_corregir, cmd_help, manejar_texto

ALLOWED = 12345

DATA_OK = {
    "monto": -850,
    "moneda": "ARS",
    "macro_categoria": "Necesidades (50%)",
    "subcategoria": "Transporte y Movilidad",
    "cuenta_origen": "Sin especificar",
    "descripcion": "nafta",
}


def _update(texto: str = "", chat_id: int = ALLOWED) -> SimpleNamespace:
    mensaje = SimpleNamespace(text=texto, reply_text=AsyncMock())
    chat = SimpleNamespace(id=chat_id)
    return SimpleNamespace(message=mensaje, effective_chat=chat)


def _context(**overrides) -> SimpleNamespace:
    bot_data = {
        "allowed_chat_id": ALLOWED,
        "timezone": "America/Argentina/Buenos_Aires",
        "llm": AsyncMock(),
        "sheets": AsyncMock(),
    }
    bot_data.update(overrides.pop("bot_data", {}))
    args = overrides.pop("args", [])
    return SimpleNamespace(bot_data=bot_data, user_data={}, args=args, **overrides)


# --- whitelist ---

async def test_chat_no_autorizado_silencio_total():
    upd = _update("850 nafta", chat_id=999)
    ctx = _context()
    await manejar_texto(upd, ctx)
    upd.message.reply_text.assert_not_called()
    ctx.bot_data["llm"].extraer_gasto.assert_not_called()


async def test_comandos_ignorados_para_no_autorizados():
    upd = _update(chat_id=999)
    ctx = _context(args=["monto", "-900"])
    await cmd_corregir(upd, ctx)
    await cmd_borrar(upd, ctx)
    upd.message.reply_text.assert_not_called()


# --- flujo principal ---

async def test_gasto_ok_guarda_y_confirma():
    upd = _update("850 nafta")
    ctx = _context()
    ctx.bot_data["llm"].extraer_gasto.return_value = dict(DATA_OK)
    await manejar_texto(upd, ctx)
    ctx.bot_data["sheets"].append_row.assert_awaited_once()
    fila = ctx.bot_data["sheets"].append_row.call_args[0][0]
    assert fila[1] == -850 and fila[4] == "Transporte y Movilidad"
    respuesta = upd.message.reply_text.call_args[0][0]
    assert "✅ Cargado" in respuesta and "nafta" in respuesta


async def test_categoria_invalida_dos_veces_queda_pendiente():
    upd = _update("850 nafta")
    ctx = _context()
    malo = dict(DATA_OK, subcategoria="Nafta")
    ctx.bot_data["llm"].extraer_gasto.side_effect = [malo, malo]
    await manejar_texto(upd, ctx)
    ctx.bot_data["sheets"].append_row.assert_not_called()
    respuesta = upd.message.reply_text.call_args[0][0]
    assert "No pude clasificar" in respuesta
    assert ctx.user_data["pendiente"]["modo"] == "categoria"
    # Reintentó una vez informando el error
    assert ctx.bot_data["llm"].extraer_gasto.call_count == 2


async def test_completar_categoria_pendiente():
    pendiente = {"modo": "categoria", "data": dict(DATA_OK)}
    upd = _update("Necesidades (50%) > Transporte y Movilidad")
    ctx = _context()
    ctx.user_data["pendiente"] = pendiente
    await manejar_texto(upd, ctx)
    ctx.bot_data["sheets"].append_row.assert_awaited_once()
    assert "pendiente" not in ctx.user_data
    assert "✅ Cargado" in upd.message.reply_text.call_args[0][0]


async def test_categoria_manual_invalida_no_avanza():
    pendiente = {"modo": "categoria", "data": dict(DATA_OK)}
    upd = _update("cosas varias")
    ctx = _context()
    ctx.user_data["pendiente"] = pendiente
    await manejar_texto(upd, ctx)
    ctx.bot_data["sheets"].append_row.assert_not_called()
    assert "pendiente" in ctx.user_data


async def test_monto_invalido_pide_aclaracion_y_completa():
    sin_monto = dict(DATA_OK, monto=None)
    upd = _update("nafta")
    ctx = _context()
    ctx.bot_data["llm"].extraer_gasto.return_value = sin_monto
    await manejar_texto(upd, ctx)
    ctx.bot_data["sheets"].append_row.assert_not_called()
    assert ctx.user_data["pendiente"]["modo"] == "monto"

    upd2 = _update("-850")
    await manejar_texto(upd2, ctx)
    ctx.bot_data["sheets"].append_row.assert_awaited_once()
    fila = ctx.bot_data["sheets"].append_row.call_args[0][0]
    assert fila[1] == -850


# --- /corregir ---

async def test_corregir_ok():
    upd = _update()
    sheets = AsyncMock()
    sheets.ultima_fila.return_value = (5, ["f", "-850", "ARS", "N", "T", "S", "nafta"])
    ctx = _context(args=["monto", "-900"], bot_data={"sheets": sheets})
    await cmd_corregir(upd, ctx)
    sheets.actualizar_celda.assert_awaited_once_with(5, "monto", "-900")
    assert "Corregido" in upd.message.reply_text.call_args[0][0]


async def test_corregir_campo_invalido():
    upd = _update()
    ctx = _context(args=["color", "rojo"])
    await cmd_corregir(upd, ctx)
    assert "Campo inválido" in upd.message.reply_text.call_args[0][0]


async def test_corregir_sin_filas():
    upd = _update()
    sheets = AsyncMock()
    sheets.ultima_fila.return_value = None
    ctx = _context(args=["monto", "-900"], bot_data={"sheets": sheets})
    await cmd_corregir(upd, ctx)
    assert "No hay ningún gasto" in upd.message.reply_text.call_args[0][0]


async def test_corregir_monto_no_numerico():
    upd = _update()
    ctx = _context(args=["monto", "abc"])
    await cmd_corregir(upd, ctx)
    assert "numérico" in upd.message.reply_text.call_args[0][0]


# --- /borrar ---

async def test_borrar_ok_confirma_contenido():
    upd = _update()
    sheets = AsyncMock()
    sheets.ultima_fila.return_value = (5, ["f", "-850", "ARS", "N", "T", "S", "nafta"])
    ctx = _context(bot_data={"sheets": sheets})
    await cmd_borrar(upd, ctx)
    sheets.borrar_fila.assert_awaited_once_with(5)
    respuesta = upd.message.reply_text.call_args[0][0]
    assert "Se borró" in respuesta and "nafta" in respuesta


async def test_borrar_sin_filas():
    upd = _update()
    sheets = AsyncMock()
    sheets.ultima_fila.return_value = None
    ctx = _context(bot_data={"sheets": sheets})
    await cmd_borrar(upd, ctx)
    sheets.borrar_fila.assert_not_called()
    assert "No hay ningún gasto" in upd.message.reply_text.call_args[0][0]


# --- /help ---

async def test_help_lista_comandos():
    upd = _update()
    await cmd_help(upd, _context())
    respuesta = upd.message.reply_text.call_args[0][0]
    assert "/corregir" in respuesta and "/borrar" in respuesta
