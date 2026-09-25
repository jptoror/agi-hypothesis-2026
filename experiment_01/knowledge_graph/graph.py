from __future__ import annotations

from typing import Iterable, Iterator, Optional

from .node import KnowledgeNode, EpistemicStatus, NodeKind


class KnowledgeGraph:
    """Grafo dirigido de nodos de conocimiento.

    Los arcos van de un nodo a sus *fundamentos* (los nodos de los que
    depende su verdad). El grafo es la base sobre la que el especialista
    razona: busca nodos, comprueba fundamentos y ejecuta derivaciones.

    OPTIMIZACIONES (exp_12):
      - `_output_index` — dict {variable → list[node_id]} mantenido
        en `add`/`remove`. Convierte `find_relations_producing` de
        O(N) a O(1) amortizado.
      - `_foundations_cache` — dict {node_id → list[KnowledgeNode]}
        que memoriza el resultado de `transitive_foundations`.
        Invalidado al añadir o eliminar nodos.
      - `transitive_foundations` — implementación ITERATIVA con
        stack explícito. Resuelve PROB-08 (RecursionError con
        cadenas > sys.setrecursionlimit) y permite la memoización
        sin recursión profunda.

    El orden de visita (DFS post-order) y el orden de iteración
    (orden de inserción de Python 3.7+) se preservan exactamente —
    ningún cambio observable en la semántica.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, KnowledgeNode] = {}
        # Índice {variable → list[node_id]} para find_relations_producing.
        # Sólo nodos ejecutables entran al índice.
        self._output_index: dict[str, list[str]] = {}
        # Cache {node_id → list[KnowledgeNode]} de cierres
        # transitivos. Se invalida al mutar el grafo.
        self._foundations_cache: dict[str, list[KnowledgeNode]] = {}

    # -- construcción ---------------------------------------------------

    def add(self, node: KnowledgeNode) -> KnowledgeNode:
        if node.id in self._nodes:
            raise ValueError(f"nodo duplicado: {node.id}")
        for dep in node.foundations:
            if dep not in self._nodes:
                raise ValueError(
                    f"fundamento inexistente '{dep}' para el nodo '{node.id}'. "
                    "Los fundamentos deben añadirse antes que los nodos que los usan."
                )
        self._nodes[node.id] = node
        # Actualizar índice de outputs si el nodo es ejecutable.
        if node.is_executable():
            for out in node.outputs:
                self._output_index.setdefault(out, []).append(node.id)
        # Cualquier mutación invalida el cache de fundamentos.
        # Los nuevos nodos no afectan a los cierres ya calculados
        # (sólo los descendientes, que aún no existen), pero los
        # `add` posteriores podrían referenciar ids ya cacheados —
        # invalidar es más seguro que rastrear dependencias.
        if self._foundations_cache:
            self._foundations_cache.clear()
        return node

    # -- acceso ---------------------------------------------------------

    def get(self, node_id: str) -> KnowledgeNode:
        if node_id not in self._nodes:
            raise KeyError(f"nodo no encontrado: {node_id}")
        return self._nodes[node_id]

    def has(self, node_id: str) -> bool:
        return node_id in self._nodes

    def __iter__(self) -> Iterator[KnowledgeNode]:
        return iter(self._nodes.values())

    def __len__(self) -> int:
        return len(self._nodes)

    # -- búsqueda -------------------------------------------------------

    def find_by_concept(self, concept: str) -> list[KnowledgeNode]:
        """Devuelve nodos cuyo id o enunciado menciona el concepto.

        Búsqueda simple por substring — suficiente para un grafo pequeño
        y auditable. No es un embedding ni un matcher estadístico.
        """
        needle = concept.lower()
        return [
            n
            for n in self._nodes.values()
            if needle in n.id.lower() or needle in n.statement.lower()
        ]

    def find_relations_producing(self, variable: str) -> list[KnowledgeNode]:
        """Nodos ejecutables que producen la variable solicitada.

        OPTIMIZADO (exp_12): consulta el índice _output_index en
        O(1) amortizado en lugar de iterar el grafo. Preserva el
        orden de inserción (los node_ids se añaden al índice en el
        mismo orden en que sus nodos llegan vía add()).
        """
        ids = self._output_index.get(variable)
        if not ids:
            return []
        return [self._nodes[nid] for nid in ids]

    def by_status(self, status: EpistemicStatus) -> list[KnowledgeNode]:
        return [n for n in self._nodes.values() if n.status == status]

    def by_kind(self, kind: NodeKind) -> list[KnowledgeNode]:
        return [n for n in self._nodes.values() if n.kind == kind]

    # -- recorrido ------------------------------------------------------

    def foundations_of(self, node_id: str) -> list[KnowledgeNode]:
        """Fundamentos directos de un nodo."""
        return [self._nodes[dep] for dep in self._nodes[node_id].foundations]

    def transitive_foundations(self, node_id: str) -> list[KnowledgeNode]:
        """Cierre transitivo de fundamentos.

        OPTIMIZADO (exp_12):
          - ITERATIVO con stack explícito → resuelve PROB-08
            (RecursionError con cadenas > sys.recursionlimit).
          - MEMOIZADO en self._foundations_cache → resuelve PROB-09
            (recalcular en cada llamada cuesta O(N) por llamada;
            memoizar reduce a O(1) las llamadas repetidas).

        El orden producido es el mismo que la versión recursiva
        original (DFS post-order: cada nodo aparece DESPUÉS de
        todos sus fundamentos transitivos).
        """
        # Cache hit: devolvemos copia para que el caller no mute
        # el cache. La copia es O(K) donde K = tamaño del resultado;
        # sigue siendo mucho más barato que recalcular.
        cached = self._foundations_cache.get(node_id)
        if cached is not None:
            return list(cached)

        seen: set[str] = set()
        order: list[str] = []

        # Stack de (nid, iterator_de_fundamentos_pendientes).
        # Emulamos la recursión DFS post-order: visitamos los
        # fundamentos antes de añadir el padre al `order`.
        # Sentinel `_root` indica que el nodo raíz se procesa pero
        # NO se incluye en el resultado (la versión recursiva sólo
        # añadía DEPS al `order`, no el propio node_id).
        if node_id not in self._nodes:
            return []

        # Estructura del stack: list de [nid, iterator, is_root_marker]
        # Procesamos como una cola DFS manual.
        stack: list[tuple[str, Iterator[str], bool]] = [
            (node_id, iter(self._nodes[node_id].foundations), True),
        ]

        while stack:
            nid, deps_iter, is_root = stack[-1]
            try:
                next_dep = next(deps_iter)
            except StopIteration:
                # Todos los fundamentos del frame actual procesados.
                # Si el nodo no es la raíz, lo añadimos al order
                # (post-order). La raíz nunca se añade — coincide con
                # el comportamiento de la versión recursiva.
                stack.pop()
                if not is_root:
                    order.append(nid)
                continue
            if next_dep in seen or next_dep not in self._nodes:
                continue
            seen.add(next_dep)
            stack.append(
                (next_dep, iter(self._nodes[next_dep].foundations), False)
            )

        result = [self._nodes[nid] for nid in order]
        self._foundations_cache[node_id] = list(result)
        return result

    # -- mutación segura ------------------------------------------------

    def remove(self, node_id: str) -> KnowledgeNode:
        """Elimina un nodo. Falla si algún otro nodo lo referencia como
        fundamento — preserva la integridad del grafo.
        """
        if node_id not in self._nodes:
            raise KeyError(f"nodo no encontrado: {node_id}")
        referers = [
            n.id for n in self._nodes.values()
            if node_id in n.foundations and n.id != node_id
        ]
        if referers:
            raise ValueError(
                f"no se puede eliminar '{node_id}': lo referencian como "
                f"fundamento {referers}"
            )
        node = self._nodes.pop(node_id)
        # Limpiar índice de outputs.
        if node.is_executable():
            for out in node.outputs:
                bucket = self._output_index.get(out)
                if bucket is not None and node_id in bucket:
                    bucket.remove(node_id)
                    if not bucket:
                        del self._output_index[out]
        # Invalidar cache (los cierres pueden referenciar este nodo).
        if self._foundations_cache:
            self._foundations_cache.clear()
        return node

    # -- integridad -----------------------------------------------------

    def validate(self) -> list[str]:
        """Comprobaciones básicas de integridad epistemológica
        (sólo errores; para warnings ver validate_with_warnings):

        - Cada referencia a fundamento debe existir en el grafo.
        - Un TEOREMA debe declarar al menos un fundamento (sin
          fundamentos no es derivable).
        - Un AXIOMA NO debe declarar fundamentos (un axioma se
          acepta sin demostración; tener fundamentos contradice su
          naturaleza). Caso PROB-10 — añadido en experiment_13.
        - Un ALGORITHM debe tener `properties["inputs"]` y
          `properties["outputs"]` declarados como listas no vacías.
          Caso PROB-11 — añadido en experiment_14.
        """
        errors, _warnings = self._collect_validation_messages()
        return errors

    def validate_with_warnings(self) -> tuple[list[str], list[str]]:
        """Variante de validate() que devuelve (errors, warnings).

        Las warnings NO bloquean el grafo (BuildReport.is_valid sigue
        leyendo sólo errors). Permiten advertir condiciones laxas:

        - Un ALGORITHM sin foundations NI inputs declarados:
          warning. La regla intencional es que un algoritmo PUEDE no
          tener fundamentos, pero si tampoco declara entradas el
          nodo es operativamente inerte — vale la pena avisar.
        """
        return self._collect_validation_messages()

    def _collect_validation_messages(self) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        for node in self._nodes.values():
            for dep in node.foundations:
                if dep not in self._nodes:
                    errors.append(f"{node.id} referencia fundamento inexistente {dep}")
            if node.status == EpistemicStatus.THEOREM and not node.foundations:
                errors.append(f"{node.id} es TEOREMA pero no declara fundamentos")
            if node.status == EpistemicStatus.AXIOM and node.foundations:
                errors.append(
                    f"{node.id} es AXIOMA pero declara fundamentos "
                    f"{node.foundations} — un axioma se acepta sin demostración."
                )
            if node.status == EpistemicStatus.ALGORITHM:
                props = node.properties or {}
                p_inputs = props.get("inputs")
                p_outputs = props.get("outputs")
                if not isinstance(p_inputs, list) or not p_inputs:
                    errors.append(
                        f"{node.id} es ALGORITHM pero no declara "
                        f"properties['inputs'] como lista no vacía."
                    )
                if not isinstance(p_outputs, list) or not p_outputs:
                    errors.append(
                        f"{node.id} es ALGORITHM pero no declara "
                        f"properties['outputs'] como lista no vacía."
                    )
                # Warning: ALGORITHM sin foundations declarados.
                # No es error — un algoritmo puede ser autónomo —
                # pero es señal de un nodo posiblemente desconectado
                # del resto del conocimiento.
                if not node.foundations:
                    warnings.append(
                        f"{node.id} es ALGORITHM sin foundations declarados "
                        f"— no es error, pero el nodo queda epistémicamente "
                        f"aislado del resto del grafo."
                    )
        return errors, warnings

    # -- extensión ------------------------------------------------------

    def extend(self, nodes: Iterable[KnowledgeNode]) -> None:
        for node in nodes:
            self.add(node)
