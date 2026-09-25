"""Monitor pasivo de colaboraciones inter-especialista.

Se enchufa al orchestrator del exp_03 vía el hook `on_solve_complete`.
Al recibir un `CrossDomainResult`, lo proyecta a 0..N
`CollaborationRecord` siguiendo esta definición operativa:

  Una colaboración existe cuando el problema se resolvió con éxito
  (success=True) y el iniciador delegó a otro especialista que
  devolvió RESOLVED. Una entrada por par único {initiator, responder}
  por problema (no por delegación: si el mismo par delega varias veces
  en el mismo problema, una sola entrada con la unión de nodos y de
  variables delegadas).

El monitor NO filtra, NO rankea, NO propone síntesis. Sólo memoriza.
"""
from __future__ import annotations

from typing import Iterable

from experiment_01.specialist import Problem, ReasoningStep
from experiment_03.orchestrator import CrossDomainResult

from .record import CollaborationRecord


class CollaborationMonitor:
    def __init__(self) -> None:
        self._records: list[CollaborationRecord] = []

    # -- API pública ---------------------------------------------------

    def observe(
        self,
        problem: Problem,
        result: CrossDomainResult,
        problem_id: str | None = None,
    ) -> list[CollaborationRecord]:
        """Procesa un CrossDomainResult y agrega los records derivados.

        Devuelve la lista de records creados en esta llamada — útil para
        tests y debugging. Si no hay colaboración (problema no resuelto,
        o sin delegaciones RESOLVED), devuelve [].
        """
        if not result.solve_result.success:
            return []

        pid = problem_id or f"anon.{len(self._records)}"

        # Indexamos pasos delegated:* de la traza principal por su
        # responder. La traza principal pertenece al iniciador del
        # problema (result.initiating_domain).
        principal_steps = result.solve_result.trace.steps
        per_responder = self._group_delegations_by_responder(principal_steps)
        if not per_responder:
            return []

        # Nodos usados por el iniciador en la traza principal: pasos
        # cuyo node_id no empiece por 'delegated:' ni 'binding:'.
        initiator_nodes = [
            s.node_id for s in principal_steps
            if not s.node_id.startswith("delegated:")
            and not s.node_id.startswith("binding:")
        ]

        new_records: list[CollaborationRecord] = []
        for responder, delegations in per_responder.items():
            responder_nodes: list[str] = []
            delegated_vars: list[str] = []
            for step in delegations:
                if step.delegated_trace is not None:
                    for sub in step.delegated_trace.steps:
                        if (
                            not sub.node_id.startswith("delegated:")
                            and not sub.node_id.startswith("binding:")
                        ):
                            responder_nodes.append(sub.node_id)
                # Variables delegadas: las claves del 'outputs' del step
                # delegado, que es lo que el responder devolvió al iniciador.
                delegated_vars.extend(step.outputs.keys())

            record = CollaborationRecord(
                problem_id=pid,
                problem_statement=problem.statement,
                problem_initiating_domain=result.initiating_domain,
                initiator=result.initiating_domain,
                responder=responder,
                nodes_used_initiator=initiator_nodes,
                nodes_used_responder=responder_nodes,
                variable_bindings=dict(problem.variable_bindings),
                delegation_hints=dict(problem.delegation_hints),
                delegated_variables=delegated_vars,
            )
            self._records.append(record)
            new_records.append(record)

        return new_records

    # -- consultas -----------------------------------------------------

    def all_records(self) -> list[CollaborationRecord]:
        return list(self._records)

    def records_for_pair(self, a: str, b: str) -> list[CollaborationRecord]:
        target = frozenset({a, b})
        return [
            r for r in self._records
            if frozenset({r.initiator, r.responder}) == target
        ]

    def records_by_signature(self) -> dict[frozenset, list[CollaborationRecord]]:
        """Agrupa records por su signature() — útil para inspección.
        El pattern_detector usará la misma agrupación con su propio
        umbral.
        """
        out: dict[frozenset, list[CollaborationRecord]] = {}
        for r in self._records:
            out.setdefault(r.signature(), []).append(r)
        return out

    # -- helpers internos ---------------------------------------------

    @staticmethod
    def _group_delegations_by_responder(
        steps: Iterable[ReasoningStep],
    ) -> dict[str, list[ReasoningStep]]:
        """Devuelve {responder: [step, ...]} agrupando los pasos
        cuya id sigue el formato 'delegated:<responder>:<vars>'.

        Sólo cuenta delegaciones que produjeron output (son las
        equivalentes a status RESOLVED del response).
        """
        out: dict[str, list[ReasoningStep]] = {}
        for s in steps:
            if not s.node_id.startswith("delegated:"):
                continue
            if not s.outputs:
                continue
            parts = s.node_id.split(":", 2)
            if len(parts) < 2:
                continue
            responder = parts[1]
            out.setdefault(responder, []).append(s)
        return out
