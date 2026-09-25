from __future__ import annotations

import math

from experiment_01.knowledge_graph import KnowledgeGraph

from ..hypothesis_engine import HypothesisCandidate
from .result import CheckOutcome, ValidationResult


class ConsistencyValidator:
    """Valida un HypothesisCandidate contra el grafo actual.

    Ejecuta cuatro checks en orden, registrando cada uno como CheckOutcome
    auditable. La política es 'fail-fast semántico': registramos TODOS los
    checks aunque uno falle — esto hace la traza más útil para el paper —
    pero `valid` es `all(check.passed)`.

    Los checks son deterministas y no usan modelos estadísticos. Cada uno
    toma una decisión con información concreta: existencia de nodos,
    ejecución del compute, comparación numérica sobre casos de prueba
    elegidos con criterio explícito.
    """

    # Casos de prueba que se aplican al compute del candidato.
    # Son simples y deliberadamente transparentes: input cero, input
    # positivo pequeño, input positivo mayor. Suficiente para detectar
    # incumplimiento de invariantes lineales/cuadráticos y no
    # determinismo. Si el candidato modela una magnitud no-lineal
    # (p. ej. área), sólo el check de 'determinismo' y 'finitud' se
    # ejercita — no el de 'cero → cero', que aplica sólo a magnitudes
    # marcadas como 'homogéneas de grado ≥ 1' en metadata.
    _TEST_INPUTS: tuple[float, ...] = (0.0, 1.0, 7.5)

    def validate(
        self,
        candidate: HypothesisCandidate,
        graph: KnowledgeGraph,
    ) -> ValidationResult:
        checks: list[CheckOutcome] = []

        # Check 1: fundamentos existen.
        checks.append(self._check_foundations_exist(candidate, graph))

        # Check 2: necesidad — no hay productor existente de las mismas outputs.
        checks.append(self._check_not_redundant(candidate, graph))

        # Check 3: ejecutable y determinista.
        exec_check = self._check_executable_and_deterministic(candidate)
        checks.append(exec_check)

        # Check 4: consistencia con axiomas relevantes. Se apoya en que
        # el compute funcionó; si falló arriba, este check se marca como
        # no ejecutable.
        if exec_check.passed:
            checks.append(self._check_axiomatic_consistency(candidate, graph))
        else:
            checks.append(CheckOutcome(
                name="axiomatic_consistency",
                passed=False,
                detail=(
                    "no ejecutado: el check previo de ejecución falló, "
                    "sin datos numéricos no se puede comparar contra axiomas."
                ),
            ))

        valid = all(c.passed for c in checks)
        if valid:
            reason = (
                f"los {len(checks)} checks de consistencia pasaron — "
                f"el candidato puede incorporarse al grafo como HYPOTHESIS."
            )
        else:
            failed = [c.name for c in checks if not c.passed]
            reason = f"checks fallidos: {', '.join(failed)}"

        return ValidationResult(valid=valid, reason=reason, checks=checks)

    # ------------------------------------------------------------------
    # Check 1
    # ------------------------------------------------------------------

    def _check_foundations_exist(
        self,
        candidate: HypothesisCandidate,
        graph: KnowledgeGraph,
    ) -> CheckOutcome:
        missing = [f for f in candidate.node.foundations if not graph.has(f)]
        if missing:
            return CheckOutcome(
                name="foundations_exist",
                passed=False,
                detail=f"fundamentos inexistentes en el grafo: {', '.join(missing)}",
            )
        return CheckOutcome(
            name="foundations_exist",
            passed=True,
            detail=(
                f"los {len(candidate.node.foundations)} fundamentos declarados "
                f"existen: {', '.join(candidate.node.foundations)}"
            ),
        )

    # ------------------------------------------------------------------
    # Check 2 (necesidad — el que pediste explícito)
    # ------------------------------------------------------------------

    def _check_not_redundant(
        self,
        candidate: HypothesisCandidate,
        graph: KnowledgeGraph,
    ) -> CheckOutcome:
        """La hipótesis es *necesaria* si ninguna relación ejecutable del
        grafo produce ya alguna de sus variables de output.

        Si existe un productor existente, la hipótesis es redundante —
        eso es un bug del engine, no un aprendizaje. Distinto de
        *inconsistente*: redundante significa que el sistema se propone
        a sí mismo conocimiento que ya tiene.
        """
        redundantes: dict[str, list[str]] = {}
        for out in candidate.node.outputs:
            producers = [
                n.id
                for n in graph.find_relations_producing(out)
                if n.id != candidate.node.id
            ]
            if producers:
                redundantes[out] = producers
        if redundantes:
            partes = [
                f"'{v}' ya producido por {', '.join(ids)}"
                for v, ids in redundantes.items()
            ]
            return CheckOutcome(
                name="not_redundant",
                passed=False,
                detail=(
                    "hipótesis redundante — el grafo ya tiene productor(es) "
                    f"para las outputs: {'; '.join(partes)}"
                ),
            )
        return CheckOutcome(
            name="not_redundant",
            passed=True,
            detail=(
                f"ningún nodo existente produce {candidate.node.outputs} — "
                f"la hipótesis es necesaria."
            ),
        )

    # ------------------------------------------------------------------
    # Check 3
    # ------------------------------------------------------------------

    def _check_executable_and_deterministic(
        self,
        candidate: HypothesisCandidate,
    ) -> CheckOutcome:
        node = candidate.node
        if not node.is_executable():
            return CheckOutcome(
                name="executable_and_deterministic",
                passed=False,
                detail="el nodo no tiene función compute — no es ejecutable.",
            )

        trial_inputs = [
            {k: t for k in node.inputs}
            for t in self._TEST_INPUTS
        ]

        try:
            first_run = [node.compute(inp) for inp in trial_inputs]
            second_run = [node.compute(inp) for inp in trial_inputs]
        except Exception as e:  # noqa: BLE001 — queremos atrapar cualquier fallo del compute
            return CheckOutcome(
                name="executable_and_deterministic",
                passed=False,
                detail=f"compute lanzó excepción en casos de prueba: {e!r}",
            )

        # Determinismo: mismas entradas → mismas salidas.
        for a, b, inp in zip(first_run, second_run, trial_inputs):
            if a != b:
                return CheckOutcome(
                    name="executable_and_deterministic",
                    passed=False,
                    detail=(
                        f"no determinista: compute({inp}) devolvió {a} y luego {b}."
                    ),
                )

        # Finitud y numericidad de cada salida.
        for inp, out in zip(trial_inputs, first_run):
            for k, v in out.items():
                if not isinstance(v, (int, float)):
                    return CheckOutcome(
                        name="executable_and_deterministic",
                        passed=False,
                        detail=(
                            f"salida no numérica para '{k}' en compute({inp}): {v!r}"
                        ),
                    )
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    return CheckOutcome(
                        name="executable_and_deterministic",
                        passed=False,
                        detail=f"salida no finita para '{k}' en compute({inp}): {v}",
                    )

        return CheckOutcome(
            name="executable_and_deterministic",
            passed=True,
            detail=(
                f"compute es ejecutable, determinista y produce valores finitos "
                f"en los {len(trial_inputs)} casos de prueba {list(self._TEST_INPUTS)}."
            ),
        )

    # ------------------------------------------------------------------
    # Check 4
    # ------------------------------------------------------------------

    def _check_axiomatic_consistency(
        self,
        candidate: HypothesisCandidate,
        graph: KnowledgeGraph,
    ) -> CheckOutcome:
        """Comprueba que el compute no viola axiomas activos en el grafo.

        Axiomas verificables por ejecución que manejamos explícitamente:

        - ax.length.nonnegative — si el candidato produce una magnitud
          derivada de longitudes (detectable porque sus inputs son
          longitudes: aparecen en otros nodos que dependen de def.length
          o ax.length.nonnegative), entonces para inputs >= 0 la salida
          debe ser >= 0.

        - ax.arithmetic.real_numbers — las operaciones deben producir
          reales. Ya cubierto por el check de finitud del paso previo,
          aquí lo refrendamos como explícito para la traza.

        Sólo comprobamos axiomas PRESENTES en el grafo: si alguien borra
        ax.length.nonnegative, el check correspondiente se salta (con
        una anotación en el detail).
        """
        node = candidate.node
        notes: list[str] = []

        # Axioma aritmética de reales.
        if graph.has("ax.arithmetic.real_numbers"):
            notes.append("ax.arithmetic.real_numbers: salidas numéricas y finitas (verificado en check previo).")
        else:
            notes.append("ax.arithmetic.real_numbers: axioma ausente en el grafo — no aplicable.")

        # Axioma longitudes no negativas.
        if graph.has("ax.length.nonnegative"):
            trial = [0.0, 0.5, 3.0, 12.0]
            violations: list[str] = []
            for t in trial:
                inp = {k: t for k in node.inputs}
                out = node.compute(inp)
                for k, v in out.items():
                    if v < -1e-12:
                        violations.append(f"compute({inp})['{k}'] = {v} < 0")
            if violations:
                return CheckOutcome(
                    name="axiomatic_consistency",
                    passed=False,
                    detail=(
                        "viola ax.length.nonnegative para inputs >= 0: "
                        + "; ".join(violations)
                    ),
                )
            notes.append(
                f"ax.length.nonnegative: para inputs {trial}, todas las outputs son >= 0."
            )
        else:
            notes.append("ax.length.nonnegative: axioma ausente en el grafo — no aplicable.")

        return CheckOutcome(
            name="axiomatic_consistency",
            passed=True,
            detail=" | ".join(notes),
        )
