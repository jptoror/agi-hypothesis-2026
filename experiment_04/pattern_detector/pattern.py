"""Patrón recurrente de colaboración detectado por el PatternDetector.

Un Pattern es una proyección del grupo de records con la misma
`signature()`, deduplicados por `problem_id` — porque el experimento
busca DIVERSIDAD DE PROBLEMAS, no frecuencia de ejecución.

El sintetizador recibirá patrones "ready" y necesita suficiente
información para construir el subdominio sin recalcular nada:
  - la signature (qué FORMA tiene el patrón);
  - los problem_ids (cuántos problemas distintos lo exhibieron);
  - un sample_record para extraer los ids de nodos, bindings y hints
    sin reconstruir la firma.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from experiment_04.collaboration_monitor import CollaborationRecord


@dataclass
class Pattern:
    signature: frozenset
    problem_ids: set[str] = field(default_factory=set)
    sample_record: CollaborationRecord | None = None

    @property
    def count(self) -> int:
        """Número de PROBLEMAS ÚNICOS que exhibieron este patrón."""
        return len(self.problem_ids)

    def render(self) -> str:
        sample = self.sample_record
        lines = [
            f"PATTERN (count={self.count})",
            f"  signature: {self.signature}",
            f"  problem_ids: {sorted(self.problem_ids)}",
        ]
        if sample is not None:
            lines.append(
                f"  sample: {sample.initiator} ↔ {sample.responder} | "
                f"bindings={sample.variable_bindings} | "
                f"hints={sample.delegation_hints}"
            )
            lines.append(f"  nodos {sample.initiator}: {sample.nodes_used_initiator}")
            lines.append(f"  nodos {sample.responder}: {sample.nodes_used_responder}")
        return "\n".join(lines)
