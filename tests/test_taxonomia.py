import pytest

from src.taxonomia import (
    CategoriaInvalidaError,
    TAXONOMIA,
    es_valida,
    taxonomia_como_texto,
    validar,
)


def test_combinacion_valida():
    assert es_valida("Necesidades (50%)", "Transporte y Movilidad")
    validar("Ingresos", "Trabajo Principal / Proyectos")  # no lanza


def test_macro_inexistente():
    assert not es_valida("Necesidad", "Transporte y Movilidad")
    with pytest.raises(CategoriaInvalidaError):
        validar("Necesidad", "Transporte y Movilidad")


def test_subcategoria_de_otra_macro():
    # La subcategoría existe, pero en otra macro -> inválida
    assert not es_valida("Deseos (30%)", "Vivienda y Servicios")
    with pytest.raises(CategoriaInvalidaError):
        validar("Deseos (30%)", "Vivienda y Servicios")


def test_subcategoria_inventada():
    assert not es_valida("Necesidades (50%)", "Nafta")
    with pytest.raises(CategoriaInvalidaError):
        validar("Necesidades (50%)", "Nafta")


def test_estructura_taxonomia():
    # Garantiza que la fuente de verdad no se corrompa por accidente
    total = sum(len(subs) for subs in TAXONOMIA.values())
    assert len(TAXONOMIA) == 4
    assert total == 10
    assert "Ingresos" in TAXONOMIA


def test_taxonomia_como_texto_incluye_todo():
    texto = taxonomia_como_texto()
    for macro, subs in TAXONOMIA.items():
        for sub in subs:
            assert f"{macro} > {sub}" in texto
