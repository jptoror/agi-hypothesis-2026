"""Interfaz que cualquier especialista debe implementar para hablar
el protocolo inter-dominio.

Un adapter es la CARA de un especialista frente al orchestrator. El
adapter no razona — delega al especialista real. Su responsabilidad es
traducir un `GapRequest` al lenguaje interno del especialista y
empaquetar la respuesta como `GapResponse`.

Esto permite que el especialista de Geometría del exp_01/02 siga siendo
inmutable: creamos un adapter que lo envuelve y habla el protocolo.

El parámetro `delegate` de `handle` permite que un adapter que está
resolviendo una consulta DELEGE a su vez — p. ej. si la consulta sobre
una variable física desemboca en una sub-consulta geométrica. Los
adapters antiguos que no usan el parámetro siguen funcionando sin
cambios: lo aceptan y lo ignoran.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Optional

from .messages import GapRequest, GapResponse

#: Tipo del callback de delegación que el orchestrator inyecta en cada
#: handle(). Un adapter que no delega puede ignorarlo.
DelegateFn = Callable[[GapRequest], GapResponse]


class SpecialistAdapter(ABC):
    """Interfaz mínima de un adapter.

    El orchestrator sólo interactúa con un adapter a través de tres
    métodos. Eso es el contrato público — nada más.
    """

    #: Nombre único del especialista; aparece en responses y trazas.
    name: str

    #: Variables que este especialista puede PRODUCIR como salida.
    #: El registry lo usa para lookup rápido. Es la única declaración
    #: de capacidades que el orchestrator ve; cualquier detalle fino
    #: vive en `can_handle`.
    output_variables: frozenset[str]

    def can_handle(self, request: GapRequest) -> bool:
        """Predicado opcional más fino que la simple pertenencia a
        `output_variables`. Por defecto: si la variable pedida está en
        mis outputs, puedo intentarlo. Los especialistas concretos
        pueden sobreescribir para rechazar consultas cuyo contexto no
        cuadra con su dominio."""
        return request.target_variable in self.output_variables

    @abstractmethod
    def handle(
        self,
        request: GapRequest,
        delegate: Optional[DelegateFn] = None,
    ) -> GapResponse:
        """Intenta resolver la consulta.

        DEBE devolver un GapResponse con el mismo `request_id` que el
        request. Si no puede resolver, devuelve status=UNRESOLVABLE con
        un KnowledgeGap explicativo en `failure`. NO lanza para fallos
        semánticos — reserva las excepciones para errores estructurales.

        `delegate` (opcional) es un callback que el orchestrator inyecta
        para permitir que este adapter DELEGUE a su vez durante la
        resolución. Los adapters que no necesitan delegar lo ignoran.
        El orchestrator aplica depth/cycle checks sobre todas las
        delegaciones, incluso las que nacen en responders.
        """
        ...
