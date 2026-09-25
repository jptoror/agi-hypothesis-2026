"""Detector de patrones recurrentes sobre la memoria del monitor.

Convierte la lista plana de CollaborationRecord del monitor en una
proyección útil para el sintetizador:

  - Agrupa records por `signature()`.
  - Dedup por `problem_id` (el mismo problema ejecutado dos veces
    no cuenta dos veces — no es evidencia de patrón).
  - Separa patrones 'ready' (count >= min_count) de 'emerging'
    (0 < count < min_count).

La separación ready/emerging es metacognición sobre la propia
historia: el sistema no sólo reacciona cuando un patrón supera el
umbral, sabe qué patrones están creciendo.
"""
from __future__ import annotations

from experiment_04.collaboration_monitor import CollaborationMonitor

from .pattern import Pattern


class PatternDetector:
    def __init__(
        self,
        monitor: CollaborationMonitor,
        min_count: int = 3,
    ) -> None:
        if min_count < 1:
            raise ValueError("min_count debe ser >= 1")
        self.monitor = monitor
        self.min_count = min_count

    # -- computación -----------------------------------------------------

    def all_patterns(self) -> list[Pattern]:
        """Todos los patrones presentes en la memoria del monitor,
        rankeados por count descendente. Orden estable ante empates
        (por repr(signature)) — determinismo auditable.
        """
        groups: dict[frozenset, Pattern] = {}
        for rec in self.monitor.all_records():
            sig = rec.signature()
            pat = groups.get(sig)
            if pat is None:
                pat = Pattern(signature=sig, sample_record=rec)
                groups[sig] = pat
            pat.problem_ids.add(rec.problem_id)
        patterns = list(groups.values())
        patterns.sort(key=lambda p: (-p.count, repr(p.signature)))
        return patterns

    def detect_ready(self) -> list[Pattern]:
        """Patrones con count >= min_count.

        Estos son los patrones que el sintetizador debe procesar ahora:
        han aparecido en suficientes problemas distintos como para ser
        considerados estructuralmente estables.
        """
        return [p for p in self.all_patterns() if p.count >= self.min_count]

    def detect_emerging(self) -> list[Pattern]:
        """Patrones con 0 < count < min_count.

        Son los que están creciendo pero no han alcanzado el umbral.
        El sistema los "sabe" — es metacognición explícita sobre su
        historia de colaboraciones — sin actuar sobre ellos todavía.
        """
        return [p for p in self.all_patterns() if 0 < p.count < self.min_count]

    # -- render auxiliar --------------------------------------------------

    def render(self) -> str:
        ready = self.detect_ready()
        emerging = self.detect_emerging()
        lines = [
            "=" * 60,
            f"PATTERN DETECTOR (umbral N={self.min_count})",
            "=" * 60,
            f"Patrones READY: {len(ready)}",
        ]
        for p in ready:
            lines.append(p.render())
            lines.append("")
        lines.append(f"Patrones EMERGING: {len(emerging)}")
        for p in emerging:
            lines.append(p.render())
            lines.append("")
        return "\n".join(lines)
