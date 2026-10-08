"""Band arithmetic, CEFR mapping and the XP level system.

All IELTS figures produced by LinguaSI are *AI Estimated* practice indicators, never official results.
"""

from __future__ import annotations

import math

CEFR_LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")


def clamp_band(value: float) -> float:
    return max(0.0, min(9.0, value))


def round_band(value: float) -> float:
    """Round an average to the nearest half band (x.25 -> x.5, x.75 -> x+1), as for the overall band."""
    return clamp_band(math.floor(value * 2 + 0.5) / 2)


def round_band_down(value: float) -> float:
    """Round down to the nearest half band - used for a single Writing/Speaking task average."""
    return clamp_band(math.floor(value * 2 + 1e-9) / 2)


def snap_half(value: float) -> float:
    """Snap an arbitrary number (e.g. an AI criterion score) onto the 0.5 grid."""
    return clamp_band(round(value * 2) / 2)


def band_to_cefr(band: float | None) -> str | None:
    if band is None:
        return None
    if band < 3.0:
        return "A1"
    if band < 4.0:
        return "A2"
    if band < 5.5:
        return "B1"
    if band < 7.0:
        return "B2"
    if band < 8.5:
        return "C1"
    return "C2"


CEFR_MID_BAND = {"A1": 2.5, "A2": 3.5, "B1": 4.5, "B2": 6.0, "C1": 7.5, "C2": 8.5}


def cefr_to_band(cefr: str | None) -> float | None:
    return CEFR_MID_BAND.get((cefr or "").upper())


def score_to_cefr(score: float) -> str:
    if score < 20:
        return "A1"
    if score < 35:
        return "A2"
    if score < 55:
        return "B1"
    if score < 72:
        return "B2"
    if score < 88:
        return "C1"
    return "C2"


def band_to_score(band: float | None) -> float:
    """Normalise a band onto 0-100 so all skills share one scale."""
    if band is None:
        return 0.0
    return round(max(0.0, min(100.0, (band / 9.0) * 100.0)), 1)


def score_to_band(score: float) -> float:
    return snap_half(score / 100.0 * 9.0)


# Approximate raw-score (out of 40) to band conversion used by IELTS-style reading/listening tests.
_RAW40_TO_BAND = [
    (39, 9.0),
    (37, 8.5),
    (35, 8.0),
    (33, 7.5),
    (30, 7.0),
    (27, 6.5),
    (23, 6.0),
    (19, 5.5),
    (15, 5.0),
    (13, 4.5),
    (10, 4.0),
    (8, 3.5),
    (6, 3.0),
    (4, 2.5),
    (0, 2.0),
]
_DIFFICULTY_SHIFT = {1: -1.0, 2: -0.5, 3: 0.0, 4: 0.25, 5: 0.5}
_DIFFICULTY_CAP = {1: 6.0, 2: 7.0, 3: 8.0, 4: 8.5, 5: 9.0}


def accuracy_to_band(accuracy: float, difficulty: int) -> float:
    """Estimate a band from a short practice set's accuracy (0-100) and its difficulty (1-5)."""
    raw = accuracy / 100.0 * 40
    band = 2.0
    for threshold, value in _RAW40_TO_BAND:
        if raw >= threshold - 1e-9:
            band = value
            break
    d = max(1, min(5, int(difficulty)))
    band = band + _DIFFICULTY_SHIFT[d]
    return snap_half(min(band, _DIFFICULTY_CAP[d]))


# --- XP levels --------------------------------------------------------------------------------

LEVEL_TITLES = [
    (1, "Beginner Explorer"),
    (2, "Curious Learner"),
    (3, "Word Collector"),
    (4, "Sentence Crafter"),
    (5, "Language Builder"),
    (6, "Steady Speaker"),
    (7, "Confident Communicator"),
    (8, "Idea Architect"),
    (9, "Skilled Strategist"),
    (10, "Fluent Challenger"),
    (12, "Advanced Analyst"),
    (15, "Band Breaker"),
    (20, "IELTS Warrior"),
    (25, "Language Master"),
    (30, "SI Legend"),
]


def xp_for_level(level: int) -> int:
    """Total XP required to reach `level` (level 1 starts at 0 XP)."""
    return 50 * level * (level - 1)


def level_for_xp(xp: int) -> int:
    level = 1
    while xp_for_level(level + 1) <= xp:
        level += 1
    return level


def level_title(level: int) -> str:
    title = LEVEL_TITLES[0][1]
    for threshold, name in LEVEL_TITLES:
        if level >= threshold:
            title = name
    return title


def level_progress(xp: int) -> dict:
    level = level_for_xp(xp)
    current_floor = xp_for_level(level)
    next_floor = xp_for_level(level + 1)
    span = next_floor - current_floor
    return {
        "level": level,
        "title": level_title(level),
        "xp": xp,
        "level_floor": current_floor,
        "next_level_xp": next_floor,
        "progress": round((xp - current_floor) / span, 4) if span else 1.0,
    }
