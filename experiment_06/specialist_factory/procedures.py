"""Biblioteca de procedimientos ejecutables disponibles.

Los documentos referencian procedimientos por nombre vía el marcador
**Procedimiento:** <name>. El graph_builder los resuelve consultando
este diccionario y verifica que la firma declarada en el documento
coincide con la firma registrada aquí.

Esta biblioteca es CONOCIMIENTO DEL SISTEMA, no del documento. Es la
pieza honesta que evita la evaluación de strings: el documento dice
'qué procedimiento aplicar', el sistema provee 'cómo se ejecuta'.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ProcedureSpec:
    inputs: list[str]
    outputs: list[str]
    fn: Callable[[dict], dict]
    description: str = ""


PROCEDURES: dict[str, ProcedureSpec] = {
    "linear_equation_solver": ProcedureSpec(
        inputs=["a", "b"],
        outputs=["x"],
        fn=lambda v: {"x": -v["b"] / v["a"]},
        description="Resuelve ax + b = 0 → x = -b/a",
    ),
}
