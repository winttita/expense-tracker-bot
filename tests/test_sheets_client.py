from unittest.mock import MagicMock

import pytest

from src.sheets_client import CAMPOS_CORREGIBLES, ENCABEZADOS, SheetsClient


def _client_con_ws_mock(filas: list[list[str]]) -> tuple[SheetsClient, MagicMock]:
    """Construye un SheetsClient sin tocar Google, con la worksheet mockeada."""
    client = SheetsClient.__new__(SheetsClient)
    ws = MagicMock()
    ws.get_all_values.return_value = filas
    client._ws = ws
    return client, ws


async def test_inicializar_encabezados_hoja_vacia():
    client, ws = _client_con_ws_mock([])
    await client.inicializar_encabezados()
    ws.append_row.assert_called_once_with(ENCABEZADOS)


async def test_inicializar_encabezados_hoja_con_datos_no_toca():
    client, ws = _client_con_ws_mock([ENCABEZADOS, ["a", 1]])
    await client.inicializar_encabezados()
    ws.append_row.assert_not_called()


async def test_append_row():
    client, ws = _client_con_ws_mock([ENCABEZADOS])
    fila = ["2026-09-13 22:30", -850, "ARS", "Necesidades (50%)",
            "Transporte y Movilidad", "Sin especificar", "nafta"]
    await client.append_row(fila)
    ws.append_row.assert_called_once_with(fila)


async def test_ultima_fila_sin_datos():
    client, _ = _client_con_ws_mock([ENCABEZADOS])
    assert await client.ultima_fila() is None


async def test_ultima_fila_con_datos():
    filas = [ENCABEZADOS, ["fila2"], ["fila3"]]
    client, _ = _client_con_ws_mock(filas)
    nro, valores = await client.ultima_fila()
    assert nro == 3
    assert valores == ["fila3"]


async def test_actualizar_celda():
    client, ws = _client_con_ws_mock([ENCABEZADOS, ["fila2"]])
    await client.actualizar_celda(2, "monto", "-900")
    ws.update_cell.assert_called_once_with(2, 2, "-900")


def test_campos_corregibles_mapean_columnas_correctas():
    assert CAMPOS_CORREGIBLES == {
        "monto": 2,
        "moneda": 3,
        "macro_categoria": 4,
        "subcategoria": 5,
        "cuenta_origen": 6,
        "descripcion": 7,
    }


async def test_borrar_fila():
    client, ws = _client_con_ws_mock([ENCABEZADOS, ["fila2"]])
    await client.borrar_fila(2)
    ws.delete_rows.assert_called_once_with(2)
