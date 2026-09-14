"""Cliente del LLM (NVIDIA NIM) para extracción y categorización de gastos."""

import asyncio
import json
import logging
import re

import httpx

from .taxonomia import taxonomia_como_texto

logger = logging.getLogger(__name__)

NIM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)

SYSTEM_PROMPT = f"""Sos un extractor de datos de gastos personales. Dado un mensaje en español, \
devolvés ÚNICAMENTE un JSON con esta forma exacta (sin texto adicional, sin markdown):

{{"monto": numero, "moneda": "ARS", "macro_categoria": "...", "subcategoria": "...", \
"cuenta_origen": "...", "descripcion": "..."}}

Reglas:
- El monto es SIEMPRE negativo (es un gasto), salvo que el mensaje indique explícitamente \
que es un ingreso (en ese caso macro_categoria = "Ingresos" y el monto es positivo).
- Si no se menciona moneda, usar "ARS".
- Si no se menciona cuenta/origen, usar "Sin especificar".
- macro_categoria y subcategoria deben elegirse EXACTAMENTE de esta lista, sin inventar \
variantes ni cambiar mayúsculas/tildes:

{taxonomia_como_texto()}

- "descripcion" es un resumen breve del gasto en palabras del usuario.
"""


class LLMError(Exception):
    """Fallo de comunicación con el LLM o respuesta no parseable."""


def extraer_json(texto: str) -> dict:
    """Extrae el primer bloque {...} de una respuesta posiblemente 'sucia' del LLM.

    Los modelos open-weight a veces agregan texto alrededor del JSON; no asumimos
    que la respuesta completa es JSON puro.
    """
    match = JSON_BLOCK_RE.search(texto)
    if not match:
        raise LLMError(f"No se encontró un bloque JSON en la respuesta: {texto!r}")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise LLMError(f"JSON inválido en la respuesta del LLM: {exc}") from exc
    if not isinstance(data, dict):
        raise LLMError(f"El JSON extraído no es un objeto: {data!r}")
    return data


class LLMClient:
    def __init__(self, api_key: str, model: str, base_url: str = NIM_URL) -> None:
        self._model = model
        self._url = base_url
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def _completar(self, mensajes: list[dict]) -> str:
        payload = {
            "model": self._model,
            "messages": mensajes,
            "temperature": 0.2,
            "max_tokens": 300,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            for intento in range(2):
                try:
                    resp = await client.post(
                        self._url, headers=self._headers, json=payload
                    )
                    resp.raise_for_status()
                    return resp.json()["choices"][0]["message"]["content"]
                except (httpx.HTTPError, KeyError, IndexError) as exc:
                    if intento == 1:
                        raise LLMError(f"Error al llamar al LLM: {exc}") from exc
                    logger.warning("Fallo transitorio al llamar al LLM, reintento en 2s")
                    await asyncio.sleep(2)
        raise LLMError("Error inesperado al llamar al LLM")  # pragma: no cover

    async def extraer_gasto(
        self, mensaje_usuario: str, error_previo: str | None = None
    ) -> dict:
        """Extrae los datos del gasto del mensaje del usuario.

        Si error_previo está presente, es un reintento: se le informa al LLM qué
        categoría inválida devolvió antes y se le recuerda la lista válida.
        """
        mensajes = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": mensaje_usuario},
        ]
        if error_previo:
            mensajes.append(
                {
                    "role": "user",
                    "content": (
                        f"ATENCIÓN: en tu respuesta anterior devolviste una categoría "
                        f"inválida: {error_previo}. Debés elegir macro_categoria y "
                        f"subcategoria EXACTAMENTE de esta lista, sin variantes:\n"
                        f"{taxonomia_como_texto()}"
                    ),
                }
            )
        logger.info("Llamando al LLM (modelo=%s, reintento=%s)", self._model, bool(error_previo))
        respuesta = await self._completar(mensajes)
        return extraer_json(respuesta)
