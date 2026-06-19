"""Tests for the online control-loop helpers."""

from __future__ import annotations

import unittest

from mpc_autoscaler_analysis.online.control_loop import (
    MPCConfig,
    escape_promql_label,
    validate_promql_duration,
)


def _make_config(**overrides: object) -> MPCConfig:
    defaults: dict[str, object] = dict(
        horizon=4,
        alpha=1.0,
        beta=0.1,
        gamma=0.01,
        rho_star=0.8,
        capacity_per_replica=10.0,
        normalization_reference_replicas=12.0,
        min_replicas=1,
        max_replicas=10,
        max_step=2,
        dt_seconds=15,
        normalized_objective=True,
        constraint_tolerance=1e-3,
    )
    defaults.update(overrides)
    return MPCConfig(**defaults)  # type: ignore[arg-type]


class PromQLEscapeTests(unittest.TestCase):
    def test_escape_passes_simple_value(self) -> None:
        self.assertEqual(escape_promql_label("toy-load"), "toy-load")

    def test_escape_handles_quote_and_backslash(self) -> None:
        self.assertEqual(escape_promql_label('a"b\\c'), 'a\\"b\\\\c')

    def test_escape_newline(self) -> None:
        self.assertEqual(escape_promql_label("a\nb"), "a\\nb")

    def test_validate_duration_accepts_units(self) -> None:
        for value in ("30s", "1m", "2h", "500ms", "7d", "1w", "1y"):
            self.assertEqual(validate_promql_duration(value, name="x"), value)

    def test_validate_duration_rejects_bad(self) -> None:
        for value in ("", "abc", "1", "-1s", "1.5s", "1m30s", "1minute", '1m"'):
            with self.assertRaises(ValueError):
                validate_promql_duration(value, name="x")


class MPCConfigValidationTests(unittest.TestCase):
    def test_defaults_construct(self) -> None:
        cfg = _make_config()
        self.assertEqual(cfg.horizon, 4)

    def test_horizon_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            _make_config(horizon=0)

    def test_weights_must_be_nonnegative(self) -> None:
        with self.assertRaises(ValueError):
            _make_config(alpha=-0.1)
        with self.assertRaises(ValueError):
            _make_config(beta=-0.1)
        with self.assertRaises(ValueError):
            _make_config(gamma=-0.1)

    def test_rho_star_in_unit_interval(self) -> None:
        with self.assertRaises(ValueError):
            _make_config(rho_star=0.0)
        with self.assertRaises(ValueError):
            _make_config(rho_star=1.5)

    def test_max_replicas_at_least_min(self) -> None:
        with self.assertRaises(ValueError):
            _make_config(min_replicas=5, max_replicas=4)

    def test_capacity_and_step_positive(self) -> None:
        with self.assertRaises(ValueError):
            _make_config(capacity_per_replica=0.0)
        with self.assertRaises(ValueError):
            _make_config(max_step=0)
        with self.assertRaises(ValueError):
            _make_config(dt_seconds=0)


if __name__ == "__main__":
    unittest.main()
