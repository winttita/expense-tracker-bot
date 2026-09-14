"""Taxonomía de finanzas personales (modelo 50/30/20) y validación estricta.

Esta constante es la FUENTE DE VERDAD: el prompt del LLM y la validación
de su respuesta dependen de esta misma estructura.
"""

TAXONOMIA = {
    "Necesidades (50%)": [
        "Vivienda y Servicios",
        "Alimentación Regular",
        "Transporte y Movilidad",
    ],
    "Deseos (30%)": [
        "Ocio y Entretenimiento",
        "Salud, Deporte y Cuidado Personal",
        "Hardware y Tecnología",
    ],
    "Ahorro e Inversión (20%)": [
        "Fondo de Emergencia",
        "Construcción de Patrimonio",
    ],
    "Ingresos": [
        "Trabajo Principal / Proyectos",
        "Rendimientos Financieros",
    ],
}

MACRO_INGRESOS = "Ingresos"


class CategoriaInvalidaError(ValueError):
    """La combinación macro/subcategoría no existe en la taxonomía."""


def es_valida(macro_categoria: str, subcategoria: str) -> bool:
    """True solo si la macro existe y la subcategoría pertenece exactamente a ella."""
    subcategorias = TAXONOMIA.get(macro_categoria)
    return subcategorias is not None and subcategoria in subcategorias


def validar(macro_categoria: str, subcategoria: str) -> None:
    """Lanza CategoriaInvalidaError si la combinación no es válida."""
    if not es_valida(macro_categoria, subcategoria):
        raise CategoriaInvalidaError(
            f"Combinación inválida: {macro_categoria!r} > {subcategoria!r}"
        )


def taxonomia_como_texto() -> str:
    """Representación legible de la taxonomía, para prompts y mensajes al usuario."""
    lineas = []
    for macro, subs in TAXONOMIA.items():
        for sub in subs:
            lineas.append(f"- {macro} > {sub}")
    return "\n".join(lineas)
