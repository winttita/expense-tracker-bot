"""Persistencia en Google Sheets vía Service Account (gspread)."""

import asyncio
import json
import logging
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

ENCABEZADOS = [
    "Fecha",
    "Monto",
    "Moneda",
    "Macro-Categoría",
    "Subcategoría",
    "Cuenta/Origen",
    "Descripción",
]

# Campos corregibles con /corregir -> índice de columna (1-based)
CAMPOS_CORREGIBLES = {
    "monto": 2,
    "moneda": 3,
    "macro_categoria": 4,
    "subcategoria": 5,
    "cuenta_origen": 6,
    "descripcion": 7,
}


class SheetsError(Exception):
    """Fallo de comunicación con Google Sheets."""


class SheetsClient:
    def __init__(self, service_account: str, sheet_id: str, sheet_name: str) -> None:
        """service_account: contenido JSON del Service Account o ruta al archivo."""
        if Path(service_account).is_file():
            creds = Credentials.from_service_account_file(service_account, scopes=SCOPES)
        else:
            info = json.loads(service_account)
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        gc = gspread.authorize(creds)
        self._ws = gc.open_by_key(sheet_id).worksheet(sheet_name)

    @classmethod
    async def crear(cls, service_account: str, sheet_id: str, sheet_name: str) -> "SheetsClient":
        """Construye el cliente sin bloquear el event loop."""
        return await asyncio.to_thread(cls, service_account, sheet_id, sheet_name)

    def _todas_las_filas(self) -> list[list[str]]:
        return self._ws.get_all_values()

    async def inicializar_encabezados(self) -> None:
        """Escribe los encabezados si la hoja está vacía."""
        def _init() -> None:
            if not self._todas_las_filas():
                self._ws.append_row(ENCABEZADOS)
                logger.info("Hoja vacía: encabezados inicializados")

        await asyncio.to_thread(_init)

    async def append_row(self, fila: list) -> None:
        for intento in range(2):
            try:
                await asyncio.to_thread(self._ws.append_row, fila)
                logger.info("Fila agregada a la sheet")
                return
            except Exception as exc:
                if intento == 1:
                    raise SheetsError(f"No se pudo escribir en la sheet: {exc}") from exc
                logger.warning("Fallo transitorio en Sheets, reintento en 2s")
                await asyncio.sleep(2)

    async def ultima_fila(self) -> tuple[int, list[str]] | None:
        """(número de fila, valores) de la última fila con datos, o None si no hay."""
        filas = await asyncio.to_thread(self._todas_las_filas)
        datos = filas[1:]  # salteo encabezados
        if not datos:
            return None
        return len(filas), datos[-1]

    async def actualizar_celda(self, nro_fila: int, campo: str, valor: str) -> None:
        columna = CAMPOS_CORREGIBLES[campo]
        await asyncio.to_thread(self._ws.update_cell, nro_fila, columna, valor)
        logger.info("Celda (%d, %d) actualizada: %s=%s", nro_fila, columna, campo, valor)

    async def borrar_fila(self, nro_fila: int) -> None:
        await asyncio.to_thread(self._ws.delete_rows, nro_fila)
        logger.info("Fila %d eliminada", nro_fila)
