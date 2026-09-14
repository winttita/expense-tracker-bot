import pytest

from src.models import Gasto


def test_desde_llm_ok():
    data = {
        "monto": -850,
        "moneda": "ars",
        "macro_categoria": "Necesidades (50%)",
        "subcategoria": "Transporte y Movilidad",
        "cuenta_origen": "Billetera Virtual",
        "descripcion": "nafta",
    }
    gasto = Gasto.desde_llm(data)
    assert gasto.monto == -850
    assert gasto.moneda == "ARS"
    assert gasto.descripcion == "nafta"


def test_desde_llm_defaults():
    data = {
        "monto": "-1200.5",
        "macro_categoria": "Deseos (30%)",
        "subcategoria": "Ocio y Entretenimiento",
        "descripcion": "cine",
    }
    gasto = Gasto.desde_llm(data)
    assert gasto.monto == -1200.5
    assert gasto.moneda == "ARS"
    assert gasto.cuenta_origen == "Sin especificar"


def test_desde_llm_monto_invalido():
    with pytest.raises(ValueError):
        Gasto.desde_llm({"monto": "abc", "descripcion": "x"})
    with pytest.raises(ValueError):
        Gasto.desde_llm({"descripcion": "sin monto"})


def test_categoria_invalida_rechazada():
    with pytest.raises(ValueError):
        Gasto(
            monto=-10,
            macro_categoria="Necesidades (50%)",
            subcategoria="No existe",
            descripcion="x",
        )


def test_como_fila_orden_columnas():
    gasto = Gasto(
        monto=-850,
        macro_categoria="Necesidades (50%)",
        subcategoria="Transporte y Movilidad",
        descripcion="nafta",
    )
    fila = gasto.como_fila("2026-09-13 22:30")
    assert fila == [
        "2026-09-13 22:30",
        -850,
        "ARS",
        "Necesidades (50%)",
        "Transporte y Movilidad",
        "Sin especificar",
        "nafta",
    ]
