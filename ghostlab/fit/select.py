"""Run every motion model; say when another model fits much better than the chosen one."""
from __future__ import annotations

from ghostlab.core import FitError, FitResult, Track
from ghostlab.fit import bounce, pendulum, projectile, ramp

MODULES = {m.MOTION: m for m in (projectile, bounce, pendulum, ramp)}
MUCH_BETTER = 0.5  # another model must halve the RMSE to be suggested


def fit_all(track: Track, pivot: tuple[float, float] | None = None) -> dict[str, FitResult | str]:
    results: dict[str, FitResult | str] = {}
    for name, module in MODULES.items():
        try:
            results[name] = module.fit(track, pivot=pivot) if name == "pendulum" else module.fit(track)
        except FitError as exc:
            results[name] = str(exc)
    return results


def better_alternative(chosen: str, results: dict[str, FitResult | str]) -> str | None:
    fitted = {k: v for k, v in results.items() if isinstance(v, FitResult)}
    if not fitted:
        return None
    best = min(fitted.values(), key=lambda r: r.rmse)
    if best.motion == chosen:
        return None
    mine = fitted.get(chosen)
    if mine is None or best.rmse < MUCH_BETTER * mine.rmse:
        return best.motion
    return None
