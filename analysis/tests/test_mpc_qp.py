from __future__ import annotations

import unittest

from mpc_autoscaler_analysis.mpc import (
    clamp_int,
    greedy_replica_action,
    round_replica_action,
    update_backlog,
)
from mpc_autoscaler_analysis.mpc.qp import _normalization_scales


class QPHelperTests(unittest.TestCase):
    def test_clamp_int(self) -> None:
        self.assertEqual(clamp_int(1, 2, 5), 2)
        self.assertEqual(clamp_int(6, 2, 5), 5)
        self.assertEqual(clamp_int(3, 2, 5), 3)

    def test_update_backlog(self) -> None:
        self.assertEqual(update_backlog(0.0, 10.0, 2, 10.0, 0.8, 1.0), 0.0)
        self.assertEqual(update_backlog(5.0, 25.0, 2, 10.0, 0.8, 1.0), 14.0)

    def test_greedy_replica_action_respects_bounds_and_step(self) -> None:
        action, status = greedy_replica_action(
            100.0,
            3,
            min_replicas=1,
            max_replicas=10,
            max_step=2,
            capacity_per_replica=10.0,
            rho_star=0.8,
            status="fallback",
        )

        self.assertEqual(action, 5)
        self.assertEqual(status, "fallback")

    def test_round_replica_action_rounds_halves_up(self) -> None:
        self.assertEqual(round_replica_action(2.5, 1, 10), 3)
        self.assertEqual(round_replica_action(4.5, 1, 10), 5)
        self.assertEqual(round_replica_action(10.5, 1, 10), 10)

    def test_normalization_reference_decouples_ceiling(self) -> None:
        base = _normalization_scales(
            mu_rho=17.5,
            max_replicas=12,
            max_step=2,
            dt_seconds=5,
            normalization_reference_replicas=12,
        )
        higher_ceiling = _normalization_scales(
            mu_rho=17.5,
            max_replicas=70,
            max_step=2,
            dt_seconds=5,
            normalization_reference_replicas=12,
        )
        dynamic = _normalization_scales(
            mu_rho=17.5,
            max_replicas=70,
            max_step=2,
            dt_seconds=5,
            normalization_reference_replicas=0,
        )

        self.assertEqual(base, higher_ceiling)
        self.assertGreater(dynamic[0], base[0])
        self.assertGreater(dynamic[2], base[2])


if __name__ == "__main__":
    unittest.main()
