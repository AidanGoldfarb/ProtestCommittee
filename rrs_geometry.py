"""
RRS geometry + right-of-way predicates for Regattatron replay state.

Conventions (verified against replay data, race cacbaec5):
  - Positions (x, y) in metres. +y points toward the windward mark ("north").
  - Headings `hdg` and wind direction `w` are COMPASS degrees:
        0 deg = +y, 90 deg = +x, clockwise.
    So a heading's unit vector is (sin h, cos h).
  - `w` is the direction the wind blows FROM (verified: at a frame with w=345,
    the close-hauled fleet split into heading clusters ~300 and ~30, i.e. +-45
    around the wind axis).

All functions here are pure and deterministic. They take plain numbers so the
synthetic test suite can construct incidents without any replay file.
"""
from __future__ import annotations
import math
from dataclasses import dataclass

# Boat length used for overlap / clear-astern. The replay carries no hull
# dimensions; this is inferred from course.zoneRadiusM / 3 (RRS zone = 3 hull
# lengths) and should be confirmed with the game's author.
DEFAULT_BOAT_LENGTH_M = 33.6


def norm180(a: float) -> float:
    """Normalize degrees to (-180, 180]."""
    a = (a + 180.0) % 360.0 - 180.0
    return a + 360.0 if a <= -180.0 else a


def unit(hdg_deg: float) -> tuple[float, float]:
    r = math.radians(hdg_deg)
    return (math.sin(r), math.cos(r))


def wind_from_vec(w_deg: float) -> tuple[float, float]:
    """Unit vector pointing toward where the wind comes FROM."""
    return unit(w_deg)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def dist(a, b):
    d = sub(a, b)
    return math.hypot(d[0], d[1])


# --- tack / point of sail -------------------------------------------------

def tack(hdg_deg: float, w_deg: float) -> str:
    """STARBOARD if the wind is on the boat's starboard side, else PORT.

    rel = wind_from - heading, normalized. rel>0 => wind comes from the
    clockwise (starboard) side of the bow => starboard tack.
    """
    rel = norm180(w_deg - hdg_deg)
    if rel > 0:
        return "STARBOARD"
    if rel < 0:
        return "PORT"
    return "HEAD_TO_WIND"


def wind_angle(hdg_deg: float, w_deg: float) -> float:
    """Absolute angle between heading and the wind axis, 0..180.
    ~45 close-hauled, ~90 reach, ~180 dead downwind."""
    return abs(norm180(w_deg - hdg_deg))


# --- overlap / clear astern ----------------------------------------------

def along_separation(pos_a, pos_b, hdg_b_deg: float) -> float:
    """Signed distance of A relative to B measured along B's heading axis.
    Negative => A is behind B (astern); positive => A is ahead of B."""
    return dot(sub(pos_a, pos_b), unit(hdg_b_deg))


def clear_astern(pos_a, pos_b, hdg_b_deg: float,
                 boat_len: float = DEFAULT_BOAT_LENGTH_M) -> bool:
    """A is clear astern of B: A's hull is behind the line abeam from B's
    aftmost point (RRS Definition, approximated with a single hull length)."""
    return along_separation(pos_a, pos_b, hdg_b_deg) < -boat_len


def overlapped(pos_a, pos_b, hdg_a_deg: float, hdg_b_deg: float,
               boat_len: float = DEFAULT_BOAT_LENGTH_M) -> bool:
    """Overlap = neither boat is clear astern of the other (RRS Definition
    Clear Astern/Ahead; Overlap)."""
    a_ca_b = clear_astern(pos_a, pos_b, hdg_b_deg, boat_len)
    b_ca_a = clear_astern(pos_b, pos_a, hdg_a_deg, boat_len)
    return not (a_ca_b or b_ca_a)


def windward_boat(pos_a, pos_b, w_deg: float) -> str:
    """Of two overlapped same-tack boats, which is to windward.
    Windward = toward the side the wind comes from => positive projection of
    (posA - posB) onto the wind-from vector. Returns 'A' or 'B'."""
    s = dot(sub(pos_a, pos_b), wind_from_vec(w_deg))
    return "A" if s > 0 else "B"


# --- line geometry (start line / gates) ----------------------------------

def reference_point(pos, hdg_deg: float, offset_m: float) -> tuple[float, float]:
    """A point `offset_m` ahead of `pos` along the heading (bow if offset>0)."""
    u = unit(hdg_deg)
    return (pos[0] + offset_m * u[0], pos[1] + offset_m * u[1])


def side_of_line(p, a, b) -> float:
    """Signed area (z of cross product) of point p relative to directed line
    a->b. >0 left of a->b, <0 right. Sign only is meaningful."""
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def on_course_side(p, line_a, line_b, toward_point) -> bool:
    """True if point p is on the course side of a start/finish line, i.e. the
    same side as `toward_point` (the first mark)."""
    s_p = side_of_line(p, line_a, line_b)
    s_mark = side_of_line(toward_point, line_a, line_b)
    if s_mark == 0:
        raise ValueError("reference mark is on the line; cannot orient")
    return (s_p > 0) == (s_mark > 0) and s_p != 0
