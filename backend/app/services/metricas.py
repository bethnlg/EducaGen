"""Indicadores de edición y tiempo (HU0025, HU0027, RF-09)."""
from difflib import SequenceMatcher

from .esquemas import contenido_a_texto


def porcentaje_modificado(contenido_ia: dict, contenido_final: dict) -> float:
    """Porcentaje de texto que el docente modificó respecto de la versión de la IA."""
    a = contenido_a_texto(contenido_ia).split()
    b = contenido_a_texto(contenido_final).split()
    if not a and not b:
        return 0.0
    if a == b:
        return 0.0
    similitud = SequenceMatcher(None, a, b, autojunk=False).ratio()
    return round(max(0.0, min(100.0, (1 - similitud) * 100)), 1)
