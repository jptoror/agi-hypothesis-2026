"""Tests del ActiveContext (exp_19).

Cubre:
  - Acumulación y caducidad de domain_hints (FIFO con max_hints).
  - Registro y resolución de bindings por categoría declarada.
  - Tick avanza turnos y expira bindings sin uso.
  - Resolución ambigua devuelve la lista de candidatos.
  - Reset por user_request y por idle_timeout.
"""
from __future__ import annotations

import unittest

from experiment_19.conversation.active_context import (
    ActiveContext,
    ContextResetReason,
)


class DomainHintsTest(unittest.TestCase):
    def test_push_appends_to_end(self) -> None:
        ctx = ActiveContext(max_hints=3)
        ctx.push_domain_hint("algorithms")
        ctx.push_domain_hint("geometry")
        self.assertEqual(ctx.domain_hints, ["algorithms", "geometry"])

    def test_max_hints_caps_size(self) -> None:
        ctx = ActiveContext(max_hints=2)
        for h in ["a", "b", "c", "d"]:
            ctx.push_domain_hint(h)
        self.assertEqual(ctx.domain_hints, ["c", "d"])

    def test_empty_hint_ignored(self) -> None:
        ctx = ActiveContext()
        ctx.push_domain_hint("")
        self.assertEqual(ctx.domain_hints, [])

    def test_duplicates_preserved(self) -> None:
        # Tres turnos seguidos de algorithms → el hint pesa más
        # (lo refleja la repetición). El caller decide cómo usarlo.
        ctx = ActiveContext()
        for _ in range(3):
            ctx.push_domain_hint("algorithms")
        self.assertEqual(ctx.domain_hints, ["algorithms"] * 3)


class BindingsTest(unittest.TestCase):
    def test_register_and_resolve_single(self) -> None:
        ctx = ActiveContext()
        ctx.register_binding("grafo_actual", "spec_a::node_3")
        node_id, candidates = ctx.resolve_anaphora("grafo")
        self.assertEqual(node_id, "spec_a::node_3")
        self.assertEqual(candidates, [])

    def test_resolve_returns_none_when_no_binding(self) -> None:
        ctx = ActiveContext()
        node_id, candidates = ctx.resolve_anaphora("grafo")
        self.assertIsNone(node_id)
        self.assertEqual(candidates, [])

    def test_ambiguous_returns_all_candidates(self) -> None:
        ctx = ActiveContext()
        ctx.register_binding("grafo_a", "spec::A")
        ctx.register_binding("grafo_b", "spec::B")
        node_id, candidates = ctx.resolve_anaphora("grafo")
        self.assertIsNone(node_id)
        self.assertEqual(sorted(candidates), ["grafo_a", "grafo_b"])

    def test_register_overwrites_same_name(self) -> None:
        ctx = ActiveContext()
        ctx.register_binding("grafo_actual", "spec::A")
        ctx.register_binding("grafo_actual", "spec::B")
        self.assertEqual(
            ctx.active_bindings["grafo_actual"], "spec::B",
        )

    def test_use_binding_resets_idle_counter(self) -> None:
        ctx = ActiveContext(binding_timeout=2)
        ctx.register_binding("x", "spec::1")
        ctx.tick()
        self.assertEqual(ctx.idle_turns_per_binding["x"], 1)
        ctx.use_binding("x")
        self.assertEqual(ctx.idle_turns_per_binding["x"], 0)


class TickAndTimeoutTest(unittest.TestCase):
    def test_tick_increments_all_counters(self) -> None:
        ctx = ActiveContext()
        ctx.register_binding("a", "X")
        ctx.register_binding("b", "Y")
        ctx.tick()
        self.assertEqual(ctx.idle_turns_per_binding["a"], 1)
        self.assertEqual(ctx.idle_turns_per_binding["b"], 1)

    def test_binding_expires_after_timeout(self) -> None:
        ctx = ActiveContext(binding_timeout=2)
        ctx.register_binding("a", "X")
        # Turno 1 sin uso.
        expired = ctx.tick()
        self.assertEqual(expired, [])
        # Turno 2 sin uso → 2 idle ticks, llega al timeout.
        expired = ctx.tick()
        self.assertEqual(expired, ["a"])
        self.assertNotIn("a", ctx.active_bindings)

    def test_binding_survives_when_used(self) -> None:
        ctx = ActiveContext(binding_timeout=2)
        ctx.register_binding("a", "X")
        ctx.tick()
        ctx.use_binding("a")
        # El uso reseteó el contador; un tick más no expira.
        ctx.tick()
        self.assertIn("a", ctx.active_bindings)


class ResetTest(unittest.TestCase):
    def test_user_request_clears_bindings_and_hints(self) -> None:
        ctx = ActiveContext()
        ctx.register_binding("a", "X")
        ctx.push_domain_hint("h")
        ctx.last_specialist_id = "specA"
        ctx.reset(ContextResetReason.USER_REQUEST)
        self.assertEqual(ctx.active_bindings, {})
        self.assertEqual(ctx.domain_hints, [])
        # Pero last_specialist_id se preserva — útil para el
        # próximo turno.
        self.assertEqual(ctx.last_specialist_id, "specA")

    def test_idle_timeout_reset_is_equivalent(self) -> None:
        ctx = ActiveContext()
        ctx.register_binding("a", "X")
        ctx.reset(ContextResetReason.IDLE_TIMEOUT)
        self.assertEqual(ctx.active_bindings, {})


class RoundTripTest(unittest.TestCase):
    def test_to_dict_from_dict_roundtrip(self) -> None:
        ctx = ActiveContext(
            last_specialist_id="spec_a",
            active_bindings={"x": "X", "y": "Y"},
            domain_hints=["a", "b"],
            idle_turns_per_binding={"x": 1, "y": 0},
            max_hints=7,
            binding_timeout=10,
        )
        d = ctx.to_dict()
        ctx2 = ActiveContext.from_dict(d)
        self.assertEqual(ctx2.last_specialist_id, "spec_a")
        self.assertEqual(ctx2.active_bindings, {"x": "X", "y": "Y"})
        self.assertEqual(ctx2.domain_hints, ["a", "b"])
        self.assertEqual(ctx2.idle_turns_per_binding, {"x": 1, "y": 0})
        self.assertEqual(ctx2.max_hints, 7)
        self.assertEqual(ctx2.binding_timeout, 10)


if __name__ == "__main__":
    unittest.main()
