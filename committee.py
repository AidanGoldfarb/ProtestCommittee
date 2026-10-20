"""
Protest committee: independently re-assigns right-of-way under the Racing Rules
of Sailing (2025-2028) for a flagged incident, and compares the result to the
rules engine's own call.

SCOPE OF v1 (honest):
  What it checks  : "Did the engine charge the correct boat under the cited
                    rule?" -- i.e. the right-of-way ASSIGNMENT, which is fully
                    determined by the kinematic state.
  What it does NOT yet check: whether an infringement actually occurred
                    (keep-clear breach + contact). That needs a contact model
                    and hull dimensions, which the replay does not carry.

Rules implemented: 10 (opposite tacks), 11 (windward/leeward), 12 (same tack,
clear astern), 22 (OCS at the start). Rules 13/14/15/16/17/18/31 are declared
but return adjudicable=False with a reason, so coverage is explicit.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional
import rrs_geometry as g


@dataclass
class BoatState:
    slot: int
    x: float
    y: float
    hdg: float
    sog: float
    name: str = ""

    @property
    def pos(self):
        return (self.x, self.y)


@dataclass
class Verdict:
    rule: int
    adjudicable: bool
    # who the committee says had to keep clear (the burdened boat), by slot
    keep_clear_slot: Optional[int] = None
    row_slot: Optional[int] = None           # right-of-way boat
    basis: dict = field(default_factory=dict)
    reason: str = ""


def _boat(frame_boats, slot) -> BoatState:
    b = frame_boats[slot]
    return BoatState(**b)


# --- individual rule assessors -------------------------------------------
# Each returns a Verdict describing the ROW assignment at the incident instant.

def assess_r10(a: BoatState, b: BoatState, w: float, boat_len: float) -> Verdict:
    """Rule 10: on opposite tacks, the port-tack boat keeps clear of starboard."""
    ta, tb = g.tack(a.hdg, w), g.tack(b.hdg, w)
    basis = {"windDir": round(w, 2), "tack": {a.slot: ta, b.slot: tb}}
    if ta == tb:
        return Verdict(10, False, basis=basis,
                       reason=f"Both on {ta} tack; Rule 10 does not apply (same tack).")
    if "HEAD_TO_WIND" in (ta, tb):
        return Verdict(10, False, basis=basis,
                       reason="A boat is head to wind; tack undefined this instant.")
    port = a.slot if ta == "PORT" else b.slot
    stbd = b.slot if port == a.slot else a.slot
    return Verdict(10, True, keep_clear_slot=port, row_slot=stbd, basis=basis,
                   reason=f"Opposite tacks: slot {port} (port) must keep clear of slot {stbd} (starboard).")


def assess_r11_12(a: BoatState, b: BoatState, w: float, boat_len: float) -> Verdict:
    """Rules 11 and 12: same tack.
    11 (overlapped): windward keeps clear of leeward.
    12 (not overlapped): the boat clear astern keeps clear of the boat ahead."""
    ta, tb = g.tack(a.hdg, w), g.tack(b.hdg, w)
    basis = {"windDir": round(w, 2), "tack": {a.slot: ta, b.slot: tb}}
    if ta != tb or "HEAD_TO_WIND" in (ta, tb):
        return Verdict(11, False, basis=basis,
                       reason="Boats not clearly on the same tack; Rules 11/12 N/A.")
    ov = g.overlapped(a.pos, b.pos, a.hdg, b.hdg, boat_len)
    basis["overlapped"] = ov
    basis["boat_len_assumed"] = boat_len
    if ov:
        wb = g.windward_boat(a.pos, b.pos, w)
        windward = a.slot if wb == "A" else b.slot
        leeward = b.slot if windward == a.slot else a.slot
        basis["windward"] = windward
        return Verdict(11, True, keep_clear_slot=windward, row_slot=leeward, basis=basis,
                       reason=f"Same tack, overlapped: windward slot {windward} keeps clear of leeward slot {leeward}.")
    # not overlapped -> Rule 12
    a_astern = g.clear_astern(a.pos, b.pos, b.hdg, boat_len)
    astern = a.slot if a_astern else b.slot
    ahead = b.slot if astern == a.slot else a.slot
    return Verdict(12, True, keep_clear_slot=astern, row_slot=ahead, basis=basis,
                   reason=f"Same tack, not overlapped: boat clear astern (slot {astern}) keeps clear of slot {ahead}.")


def assess_r22(boat: BoatState, course: dict, boat_len: float) -> Verdict:
    """Rule 22 (OCS): on the course side of the start line at the start signal.

    The replay (x,y) is the hull CENTROID; the start line is judged at the BOW,
    modelled as centroid + (boat_len/2) along heading. This bow model was
    cross-checked against race cacbaec5: it reproduces all four gun-line calls
    (slots 1,2 OCS; slots 0,3 clean) that the centroid alone gets wrong.
    """
    sl = course["startLine"]
    la, lb = (sl["a"]["x"], sl["a"]["y"]), (sl["b"]["x"], sl["b"]["y"])
    ww = next((m for m in course["marks"] if m["id"] == "WW"), None)
    if ww is None:
        return Verdict(22, False, reason="No windward mark to orient the line.")
    # OCS only concerns boats actually at the start. Ghost / did-not-start
    # boats sit far up-course (e.g. a DSQ no-show ~54 km away in cacbaec5);
    # exclude anything beyond a few line-lengths of the line.
    line_len = g.dist(la, lb)
    mid = ((la[0] + lb[0]) / 2.0, (la[1] + lb[1]) / 2.0)
    if g.dist(boat.pos, mid) > 3.0 * line_len:
        return Verdict(22, False,
                       basis={"dist_to_line_mid": round(g.dist(boat.pos, mid), 1)},
                       reason="Boat not in the start area (likely did not start / DSQ); Rule 22 N/A.")
    bow = g.reference_point(boat.pos, boat.hdg, boat_len / 2.0)
    ocs = g.on_course_side(bow, la, lb, (ww["x"], ww["y"]))
    return Verdict(22, True, keep_clear_slot=(boat.slot if ocs else None),
                   basis={"on_course_side": ocs, "bow": tuple(round(c, 1) for c in bow),
                          "centroid": boat.pos, "bow_offset_m": boat_len / 2.0},
                   reason=("Bow on the course side at the gun -> OCS." if ocs
                           else "Bow behind the line at the gun -> not OCS."))


_NOT_YET = {
    13: "While tacking: needs head-to-wind crossing detection over a window.",
    14: "Avoid contact: needs a contact model + hull dimensions (absent).",
    15: "Acquiring ROW: needs the transition sequence, not one instant.",
    16: "Changing course: needs heading-change detection over a window.",
    17: "Proper course: needs a proper-course estimate over a window.",
    18: "Mark-room: zone radius is known, but overlap-at-zone-entry needs boat length and a time window.",
    31: "Touching a mark: needs a contact model + hull dimensions (absent).",
}


# --- audit orchestration -------------------------------------------------

@dataclass
class IncidentAudit:
    event_tMs: int
    sample_idx: int
    engine_kind: str
    engine_rule: Optional[int]
    engine_offender_slot: int
    engine_offender: str
    engine_counterparty_slot: Optional[int]
    engine_counterparty: Optional[str]
    verdict: Verdict
    agreement: str      # AGREE | DISAGREE | UNDETERMINED | N/A
    note: str = ""


def _names(blob):
    return {b["slot"]: b["displayName"] for b in blob["boats"]}


def frame_at(blob, tMs):
    """Return {slot: {...}} for the sample whose tMs matches (== tMs/1000 idx)."""
    interval = blob.get("sampleIntervalSimMs", 1000)
    idx = round(tMs / interval)
    idx = max(0, min(idx, len(blob["samples"]) - 1))
    s = blob["samples"][idx]
    if s["tMs"] != tMs:  # fall back to nearest by scan if the index guess is off
        best = min(range(len(blob["samples"])),
                   key=lambda i: abs(blob["samples"][i]["tMs"] - tMs))
        idx, s = best, blob["samples"][best]
    names = _names(blob)
    frame = {b["slot"]: {**b, "name": names.get(b["slot"], "")} for b in s["boats"]}
    return idx, frame


def audit_event(blob, event, boat_len=g.DEFAULT_BOAT_LENGTH_M) -> IncidentAudit:
    names = _names(blob)
    tMs = event["tMs"]
    idx, frame = frame_at(blob, tMs)
    w = frame[next(iter(frame))]  # any boat, to read wind? wind is per-sample
    wind = blob["samples"][idx]["w"]
    off = event["boatSlot"]
    cp = event.get("counterpartySlot")
    rule = event.get("rule")

    base = dict(event_tMs=tMs, sample_idx=idx, engine_kind=event["kind"],
                engine_rule=rule, engine_offender_slot=off,
                engine_offender=names.get(off, str(off)),
                engine_counterparty_slot=cp,
                engine_counterparty=(names.get(cp) if cp is not None else None))

    # Route to the right assessor.
    if rule == 10 and cp is not None:
        v = assess_r10(_boat(frame, off), _boat(frame, cp), wind, boat_len)
    elif rule == 11 and cp is not None:
        v = assess_r11_12(_boat(frame, off), _boat(frame, cp), wind, boat_len)
    elif rule == 22:
        v = assess_r22(_boat(frame, off), blob["course"], boat_len)
    elif rule in _NOT_YET:
        v = Verdict(rule, False, reason=_NOT_YET[rule])
    elif rule == 11 and cp is None:
        v = Verdict(11, False, reason="Rule 11 event without a counterparty slot; cannot place the pair.")
    else:
        v = Verdict(rule or -1, False, reason="No assessor for this rule/event.")

    # Decide agreement for the ROW-assignment check.
    if not v.adjudicable:
        agreement, note = "UNDETERMINED", v.reason
    elif rule == 22:
        agreement = "AGREE" if v.keep_clear_slot == off else "DISAGREE"
        note = v.reason
    elif v.keep_clear_slot is None:
        agreement, note = "UNDETERMINED", v.reason
    else:
        agreement = "AGREE" if v.keep_clear_slot == off else "DISAGREE"
        note = v.reason
    return IncidentAudit(**base, verdict=v, agreement=agreement, note=note)


def audit_blob(blob, boat_len=g.DEFAULT_BOAT_LENGTH_M):
    kinds = {"INFRACTION", "OCS", "MARK_TOUCH"}
    out = []
    for e in blob["events"]:
        if e["kind"] in kinds:
            out.append(audit_event(blob, e, boat_len))
    return out
