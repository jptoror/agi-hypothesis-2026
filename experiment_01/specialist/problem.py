from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DomainContext:
    """Contexto estructurado del problema, agnóstico al dominio.

    `kind` identifica el tipo de objeto del problema (p. ej. "square",
    "physics.object", "linear_equation") — debe coincidir con algún
    término reconocido por el especialista que va a resolver, ya sea
    definido en su grafo o declarado como `domain_terms` del propio
    especialista.

    Conceptualmente reemplaza al antiguo `Figure`: el sistema modela
    problemas en cualquier dominio (geometría, física, álgebra, etc.)
    y "figura" era un término demasiado geometricocéntrico.
    """

    kind: str
    known: dict[str, float] = field(default_factory=dict)

    def describe(self) -> str:
        if not self.known:
            return f"contexto de tipo '{self.kind}' sin datos numéricos"
        datos = ", ".join(f"{k}={v}" for k, v in self.known.items())
        return f"contexto de tipo '{self.kind}' con {datos}"


@dataclass
class Problem:
    """Un problema de un dominio cualquiera.

    `target` es el nombre de la variable que se quiere resolver (p. ej. "A"
    para área, "x" para incógnita). `context` aporta el contexto y los
    valores conocidos. `statement` es el enunciado en lenguaje natural,
    sólo para trazabilidad.

    `variable_bindings` declara equivalencias ontológicas del enunciado
    entre variables de dominios distintos. Ejemplo: {"v": "l"} para un
    problema que dice 'la velocidad es igual al lado del cuadrado'. Es
    conocimiento del ENUNCIADO, no de ningún especialista. El orchestrator
    inter-dominio las honra de forma explícita y auditable (genera un
    paso 'binding:...' en la traza).
    """

    statement: str
    target: str
    context: DomainContext
    variable_bindings: dict[str, str] = field(default_factory=dict)
    # Pistas del enunciado para especialistas consultados vía delegación.
    # Típicamente contiene claves como `figure_kind`/`object_kind` que el
    # responder necesita y que no viven en el `context` del requester. Es
    # información ontológica del enunciado — no razonamiento.
    delegation_hints: dict = field(default_factory=dict)
