"""QP helpers shared by offline and online MPC tools."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable

DEFAULT_NORMALIZATION_REFERENCE_REPLICAS = 12.0


def clamp_int(value: int, low: int, high: int) -> int:
    """Clamp an integer to the inclusive range."""
    return max(low, min(high, value))


def round_replica_action(value: float, low: int, high: int) -> int:
    """Round relaxed replica count with halves rounded up."""
    return clamp_int(int(math.floor(value + 0.5)), low, high)


def update_backlog(
    b0: float,
    lambda_obs: float,
    r_prev: int,
    mu: float,
    rho_star: float,
    dt: float,
) -> float:
    """Update the surrogate backlog state for one control interval."""
    return max(0.0, b0 + dt * (lambda_obs - mu * rho_star * r_prev))


def greedy_replica_action(
    forecast_first: float,
    r_current: int,
    *,
    min_replicas: int,
    max_replicas: int,
    max_step: int,
    capacity_per_replica: float,
    rho_star: float,
    status: str,
) -> tuple[int, str]:
    """Scale toward the first forecast point within step limits."""
    denom = max(capacity_per_replica * rho_star, 1e-9)
    desired = int(math.ceil(max(forecast_first, 0.0) / denom))
    desired = clamp_int(desired, min_replicas, max_replicas)
    delta = max(-max_step, min(max_step, desired - r_current))
    action = clamp_int(r_current + delta, min_replicas, max_replicas)
    return action, status


def _normalization_scales(
    *,
    mu_rho: float,
    max_replicas: int,
    max_step: int,
    dt_seconds: float,
    normalization_reference_replicas: float,
) -> tuple[float, float, float]:
    reference_replicas = (
        float(normalization_reference_replicas)
        if normalization_reference_replicas > 0
        else float(max_replicas)
    )
    return (
        max(mu_rho * reference_replicas * float(dt_seconds), 1e-9),
        max(float(max_step), 1e-9),
        max(reference_replicas, 1e-9),
    )


def _constraint_violation(
    x_values: object,
    b_values: object,
    forecast: object,
    b0: float,
    r_current: int,
    *,
    capacity_per_replica: float,
    rho_star: float,
    min_replicas: int,
    max_replicas: int,
    max_step: int,
    dt_seconds: float,
    tolerance: float,
) -> str | None:
    import numpy as np

    if x_values.shape != forecast.shape or b_values.shape != forecast.shape:
        return "shape"
    if not np.all(np.isfinite(x_values)) or not np.all(np.isfinite(b_values)):
        return "non_finite"

    lower_gap = float(np.min(x_values) - min_replicas)
    if lower_gap < -tolerance:
        return f"replica_lower_bound:{lower_gap:.6g}"
    upper_gap = float(max_replicas - np.max(x_values))
    if upper_gap < -tolerance:
        return f"replica_upper_bound:{upper_gap:.6g}"
    backlog_min = float(np.min(b_values))
    if backlog_min < -tolerance:
        return f"backlog_nonnegative:{backlog_min:.6g}"

    prev_x = np.concatenate(([float(r_current)], x_values[:-1]))
    step_excess = float(np.max(np.abs(x_values - prev_x)) - max_step)
    if step_excess > tolerance:
        return f"step_bound:{step_excess:.6g}"

    mu_rho = capacity_per_replica * rho_star
    prev_b = np.concatenate(([float(b0)], b_values[:-1]))
    backlog_rhs = prev_b + float(dt_seconds) * (forecast - mu_rho * x_values)
    backlog_gap = float(np.min(b_values - backlog_rhs))
    if backlog_gap < -tolerance:
        return f"backlog_dynamics:{backlog_gap:.6g}"

    return None


def solve_backlog_mpc(
    forecast: object,
    b0: float,
    r_current: int,
    *,
    alpha: float,
    beta: float,
    gamma: float,
    capacity_per_replica: float,
    rho_star: float,
    min_replicas: int,
    max_replicas: int,
    max_step: int,
    dt_seconds: float,
    fallback: Callable[[float, int], tuple[int, str]] | None = None,
    accepted_statuses: Iterable[str] | None = None,
    constraint_tolerance: float = 1e-3,
    normalized_objective: bool = False,
    normalization_reference_replicas: float = DEFAULT_NORMALIZATION_REFERENCE_REPLICAS,
) -> tuple[int, str]:
    """Solve the relaxed backlog-state MPC problem for the next replica count."""
    try:
        import numpy as np
    except ImportError:
        values = list(forecast) if isinstance(forecast, Iterable) else []
        if values and fallback is not None:
            return fallback(float(values[0]), r_current)
        return r_current, "solver_unavailable"

    forecast_arr = np.asarray(forecast, dtype=float)
    if forecast_arr.size == 0:
        return r_current, "empty_forecast"

    accepted = set(accepted_statuses) if accepted_statuses is not None else None

    try:
        import cvxpy as cp
    except ImportError:
        if fallback is not None:
            return fallback(float(forecast_arr[0]), r_current)
        return r_current, "solver_unavailable"

    n = int(forecast_arr.size)
    mu_rho = capacity_per_replica * rho_star
    x = cp.Variable(n)
    b = cp.Variable(n)

    constraints: list = [
        x >= min_replicas,
        x <= max_replicas,
        b >= 0.0,
    ]

    for k in range(n):
        x_prev = r_current if k == 0 else x[k - 1]
        constraints.append(x[k] - x_prev <= max_step)
        constraints.append(x_prev - x[k] <= max_step)

    for k in range(n):
        b_prev = b0 if k == 0 else b[k - 1]
        constraints.append(
            b[k] >= b_prev + float(dt_seconds) * (float(forecast_arr[k]) - mu_rho * x[k])
        )

    smooth = cp.square(x[0] - r_current)
    for k in range(1, n):
        smooth = smooth + cp.square(x[k] - x[k - 1])

    if normalized_objective:
        backlog_scale, step_scale, replica_scale = _normalization_scales(
            mu_rho=mu_rho,
            max_replicas=max_replicas,
            max_step=max_step,
            dt_seconds=dt_seconds,
            normalization_reference_replicas=normalization_reference_replicas,
        )
        objective = (
            alpha * cp.sum_squares(b / backlog_scale)
            + beta * smooth / (step_scale * step_scale)
            + gamma * cp.sum(x / replica_scale)
        )
    else:
        objective = alpha * cp.sum_squares(b) + beta * smooth + gamma * cp.sum(x)
    problem = cp.Problem(cp.Minimize(objective), constraints)

    try:
        problem.solve(
            solver=cp.OSQP,
            warm_start=True,
            verbose=False,
            max_iter=20000,
            eps_abs=1e-4,
            eps_rel=1e-4,
            polish=True,
        )
    except Exception as exc:  # noqa: BLE001
        if fallback is not None:
            return fallback(float(forecast_arr[0]), r_current)
        return r_current, f"solver_exception:{type(exc).__name__}"

    status = str(problem.status or "unknown")
    if x.value is None or b.value is None:
        if fallback is not None:
            return fallback(float(forecast_arr[0]), r_current)
        return r_current, "no_solution"

    if accepted is not None and status not in accepted:
        if fallback is not None:
            return fallback(float(forecast_arr[0]), r_current)
        return r_current, status

    x_values = np.asarray(x.value, dtype=float).reshape(-1)
    b_values = np.asarray(b.value, dtype=float).reshape(-1)
    violation = _constraint_violation(
        x_values,
        b_values,
        forecast_arr,
        b0,
        r_current,
        capacity_per_replica=capacity_per_replica,
        rho_star=rho_star,
        min_replicas=min_replicas,
        max_replicas=max_replicas,
        max_step=max_step,
        dt_seconds=dt_seconds,
        tolerance=constraint_tolerance,
    )
    if violation is not None:
        status = f"{status}|post_solve_violation:{violation}"
        if fallback is not None:
            action, fallback_status = fallback(float(forecast_arr[0]), r_current)
            return action, f"{status}|fallback:{fallback_status}"
        return r_current, status

    lower = max(min_replicas, r_current - max_step)
    upper = min(max_replicas, r_current + max_step)
    action = round_replica_action(float(x_values[0]), lower, upper)
    return action, status
