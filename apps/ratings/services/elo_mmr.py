"""Elo-MMR rating engine.

The constants and update equations follow the Elo-MMR formulation used by
DMOJ's AGPL-licensed ratings reference, adapted to plain Python for JudgeLoom.
"""

from __future__ import annotations

from math import pi, sqrt, tanh

BETA2 = 328.33**2
MEAN_INIT = 1500.0
RATING_INIT = 1200
VAR_INIT = 350**2 * (BETA2 / 212**2)
SD_INIT = sqrt(VAR_INIT)
VALID_RANGE = (MEAN_INIT - 20 * SD_INIT, MEAN_INIT + 20 * SD_INIT)
VAR_PER_CONTEST = 1219.047619 * (BETA2 / 212**2)
VAR_LIM = (sqrt(VAR_PER_CONTEST**2 + 4 * BETA2 * VAR_PER_CONTEST) - VAR_PER_CONTEST) / 2
SD_LIM = sqrt(VAR_LIM)
TANH_C = sqrt(3) / pi

_VAR_CACHE: list[float] = [VAR_INIT]


def variance_for(times_ranked: int) -> float:
    """Return the prior variance for a participant with N rated contests."""

    while times_ranked >= len(_VAR_CACHE):
        previous = _VAR_CACHE[-1]
        _VAR_CACHE.append(1.0 / (1.0 / (previous + VAR_PER_CONTEST) + 1.0 / BETA2))
    return _VAR_CACHE[times_ranked]


def _eval_tanhs(terms: list[tuple[float, float, float]], x: float) -> float:
    return sum((weight / sd) * tanh((x - mean) / (2 * sd)) for mean, sd, weight in terms)


def _solve(
    terms: list[tuple[float, float, float]],
    target: float,
    linear_factor: float = 0.0,
    bounds: tuple[float, float] = VALID_RANGE,
) -> float:
    left, right = bounds
    left_y = right_y = None

    while right - left > 2:
        middle = (left + right) / 2
        value = linear_factor * middle + _eval_tanhs(terms, middle)
        if value > target:
            right, right_y = middle, value
        elif value < target:
            left, left_y = middle, value
        else:
            return middle

    if left_y is None:
        left_y = linear_factor * left + _eval_tanhs(terms, left)
    if target <= left_y:
        return left
    if right_y is None:
        right_y = linear_factor * right + _eval_tanhs(terms, right)
    if target >= right_y:
        return right

    ratio = (target - left_y) / (right_y - left_y)
    return left * (1 - ratio) + right * ratio


def recalculate(
    ranks: list[float],
    old_mean: list[float],
    times_ranked: list[int],
    historical_performance: list[list[float]],
    performance_ceiling: float | None = None,
) -> tuple[list[int], list[float], list[float]]:
    """Return displayed rating, mean, and performance for one contest."""

    count = len(ranks)
    if count == 0:
        return [], [], []

    bounds = list(VALID_RANGE)
    if performance_ceiling is not None:
        bounds[1] = min(bounds[1], performance_ceiling)
    updated_bounds = (bounds[0], bounds[1])

    delta = [
        TANH_C * sqrt(variance_for(times) + VAR_PER_CONTEST + BETA2)
        for times in times_ranked
    ]
    prior_terms = [(mean, width, 1.0) for mean, width in zip(old_mean, delta, strict=True)]
    new_performance = [0.0] * count
    new_mean = [0.0] * count

    def solve_index(index: int, search_bounds: tuple[float, float]) -> None:
        rank = ranks[index]
        target = 0.0
        for opponent_rank, width in zip(ranks, delta, strict=True):
            if opponent_rank > rank:
                target += 1.0 / width
            elif opponent_rank < rank:
                target -= 1.0 / width
        new_performance[index] = _solve(prior_terms, target, bounds=search_bounds)

    def fill(left: int, right: int) -> None:
        if right - left > 1:
            middle = (left + right) // 2
            solve_index(middle, (new_performance[right], new_performance[left]))
            fill(left, middle)
            fill(middle, right)

    if count < 2:
        new_performance = list(old_mean)
        new_mean = list(old_mean)
    else:
        solve_index(0, updated_bounds)
        solve_index(count - 1, updated_bounds)
        fill(0, count - 1)

        for index in range(count):
            terms: list[tuple[float, float, float]] = []
            previous_weight = 1.0
            weight_sum = 0.0
            history = [new_performance[index], *historical_performance[index]]
            for history_index, performance in enumerate(history):
                gamma2 = VAR_PER_CONTEST if history_index > 0 else 0.0
                history_variance = variance_for(times_ranked[index] + 1 - history_index)
                factor = history_variance / (history_variance + gamma2)
                weight = previous_weight * factor**2
                terms.append((performance, sqrt(BETA2) * TANH_C, weight))
                previous_weight = weight
                weight_sum += weight / BETA2

            initial_weight = 1.0 / variance_for(times_ranked[index] + 1) - weight_sum
            initial_performance = (
                _eval_tanhs(terms[1:], old_mean[index]) / initial_weight + old_mean[index]
            )
            new_mean[index] = _solve(
                terms,
                initial_weight * initial_performance,
                linear_factor=initial_weight,
                bounds=updated_bounds,
            )

    displayed = [
        max(1, round(mean - (sqrt(variance_for(times + 1)) - SD_LIM)))
        for mean, times in zip(new_mean, times_ranked, strict=True)
    ]
    return displayed, new_mean, new_performance
