import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.llm_client import LLMClient, LLMError, extraer_json


# --- extraer_json: parseo de respuestas "sucias" ---

def test_json_puro():
    assert extraer_json('{"monto": -850}') == {"monto": -850}


def test_json_con_texto_alrededor():
    sucio = 'Claro, acá va:\n{"monto": -850, "moneda": "ARS"}\nEspero que sirva.'
    assert extraer_json(sucio) == {"monto": -850, "moneda": "ARS"}


def test_json_en_bloque_markdown():
    md = '```json\n{"monto": -100, "descripcion": "cine"}\n```'
    assert extraer_json(md) == {"monto": -100, "descripcion": "cine"}


def test_sin_json_lanza():
    with pytest.raises(LLMError):
        extraer_json("no hay ningún json acá")


def test_json_malformado_lanza():
    with pytest.raises(LLMError):
        extraer_json('{"monto": -850, sin cerrar')


def test_json_no_objeto_lanza():
    with pytest.raises(LLMError):
        extraer_json("[]")


# --- LLMClient ---

def _mock_response(data: dict) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": json.dumps(data)}}]},
        request=httpx.Request("POST", "http://test"),
    )


async def test_extraer_gasto_ok():
    client = LLMClient(api_key="k", model="m")
    esperado = {"monto": -850, "macro_categoria": "Necesidades (50%)"}
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _mock_response(esperado)
        result = await client.extraer_gasto("850 nafta")
    assert result == esperado
    # Verifica parámetros de la llamada
    payload = mock_post.call_args.kwargs["json"]
    assert payload["temperature"] == 0.2
    assert payload["max_tokens"] == 300


async def test_extraer_gasto_reintenta_tras_fallo_de_red():
    client = LLMClient(api_key="k", model="m")
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post, patch(
        "asyncio.sleep", new_callable=AsyncMock
    ):
        mock_post.side_effect = [
            httpx.ConnectError("boom", request=httpx.Request("POST", "http://t")),
            _mock_response({"monto": -1}),
        ]
        result = await client.extraer_gasto("x")
    assert result == {"monto": -1}
    assert mock_post.call_count == 2


async def test_extraer_gasto_falla_dos_veces_lanza():
    client = LLMClient(api_key="k", model="m")
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post, patch(
        "asyncio.sleep", new_callable=AsyncMock
    ):
        mock_post.side_effect = httpx.ConnectError(
            "boom", request=httpx.Request("POST", "http://t")
        )
        with pytest.raises(LLMError):
            await client.extraer_gasto("x")


async def test_reintento_por_categoria_incluye_error_en_prompt():
    client = LLMClient(api_key="k", model="m")
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _mock_response({"monto": -1})
        await client.extraer_gasto("850 nafta", error_previo="Necesidades (50%) > Nafta")
    mensajes = mock_post.call_args.kwargs["json"]["messages"]
    assert any("Necesidades (50%) > Nafta" in m["content"] for m in mensajes)
