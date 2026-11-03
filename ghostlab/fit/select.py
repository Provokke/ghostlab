"""Run every motion model; say when another model fits much better than the chosen one."""
from __future__ import annotations

import numpy as np

from ghostlab.core import FitError, FitResult, Track
from ghostlab.fit import bounce, pendulum, projectile, ramp

MODULES = {m.MOTION: m for m in (projectile, bounce, pendulum, ramp)}
MUCH_BETTER = 0.5  # another model must halve the RMSE to be suggested
FREE_PARAMETERS = {"projectile": 5, "bounce": 8, "pendulum": 8, "ramp": 7}  # fitted numbers per model


def _adjusted_rmse(r: FitResult) -> float:
    """In-sample RMSE corrected for degrees of freedom, so an 8-parameter model does not win by flexibility alone.

    Still a heuristic (the held-out check decides trust); it only picks a model to suggest."""
    dof = r.n_points - FREE_PARAMETERS.get(r.motion, 0)
    return r.rmse * (r.n_points / dof) ** 0.5 if dof > 0 else float("inf")


def fit_all(track: Track, pivot: tuple[float, float] | None = None) -> dict[str, FitResult | str]:
    """Fit every model; a model that cannot fit maps to the reason (a string) instead of a result."""
    results: dict[str, FitResult | str] = {}
    for name, module in MODULES.items():
        try:
            results[name] = module.fit(track, pivot=pivot) if name == "pendulum" else module.fit(track)
        except (FitError, np.linalg.LinAlgError) as exc:
            results[name] = str(exc)
    return results


def better_alternative(chosen: str, results: dict[str, FitResult | str]) -> str | None:
    fitted = {k: v for k, v in results.items() if isinstance(v, FitResult)}
    if not fitted:
        return None
    best = min(fitted.values(), key=_adjusted_rmse)
    if best.motion == chosen:
        return None
    mine = fitted.get(chosen)
    if mine is None or _adjusted_rmse(best) < MUCH_BETTER * _adjusted_rmse(mine):
        return best.motion
    return None
