"""Modelo de datos de un gasto/movimiento."""

from dataclasses import dataclass, field
from datetime import datetime

from .taxonomia import validar


@dataclass
class Gasto:
    """Un movimiento financiero listo para persistir.

    Reglas de negocio:
    - monto negativo para gastos, positivo solo si es Ingresos.
    - moneda por defecto ARS.
    - cuenta_origen "Sin especificar" si el usuario no la menciona.
    - fecha la genera el backend, no el LLM.
    """

    monto: float
    macro_categoria: str
    subcategoria: str
    descripcion: str
    moneda: str = "ARS"
    cuenta_origen: str = "Sin especificar"
    fecha: datetime | None = field(default=None)

    def __post_init__(self) -> None:
        if self.monto is None:
            raise ValueError("El monto es obligatorio")
        validar(self.macro_categoria, self.subcategoria)

    @classmethod
    def desde_llm(cls, data: dict) -> "Gasto":
        """Construye un Gasto desde el JSON extraído del LLM.

        Lanza ValueError si faltan campos o el monto no es numérico.
        """
        try:
            monto = float(data["monto"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Monto inválido o ausente: {data.get('monto')!r}") from exc

        return cls(
            monto=monto,
            moneda=(data.get("moneda") or "ARS").strip().upper(),
            macro_categoria=(data.get("macro_categoria") or "").strip(),
            subcategoria=(data.get("subcategoria") or "").strip(),
            cuenta_origen=(data.get("cuenta_origen") or "Sin especificar").strip()
            or "Sin especificar",
            descripcion=(data.get("descripcion") or "").strip(),
        )

    def como_fila(self, fecha_str: str) -> list[str | float]:
        """Fila en el orden exacto de columnas de la Google Sheet."""
        return [
            fecha_str,
            self.monto,
            self.moneda,
            self.macro_categoria,
            self.subcategoria,
            self.cuenta_origen,
            self.descripcion,
        ]
