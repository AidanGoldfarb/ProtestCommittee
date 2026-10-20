"""
Synthetic verification suite -- the oracle is hand-constructed geometry with a
KNOWN-correct answer, never the rules engine. Run with:  pytest -q

Conventions: hdg / wind are compass degrees (0=+y, cw). +y is upwind.
"""
import os, json, math
import pytest
import rrs_geometry as g
import committee as C


# ---- tack -----------------------------------------------------------------
def test_tack_starboard_and_port_beating_upwind():
    # wind from the north (0). Beating upwind: NW heading is starboard, NE is port.
    assert g.tack(315, 0) == "STARBOARD"
    assert g.tack(45, 0) == "PORT"

def test_tack_matches_real_frame_convention():
    # verified frame: wind from ~345, clusters at ~300 (stbd) and ~30 (port)
    assert g.tack(300, 345) == "STARBOARD"
    assert g.tack(30, 345) == "PORT"

def test_head_to_wind():
    assert g.tack(0, 0) == "HEAD_TO_WIND"


# ---- windward / leeward ---------------------------------------------------
def test_windward_is_the_more_upwind_boat():
    # same tack, overlapped abeam; wind from north -> higher y is windward
    A = (0.0, 5.0); B = (0.0, -5.0)
    assert g.overlapped(A, B, 315, 315) is True
    assert g.windward_boat(A, B, 0) == "A"   # A is further upwind (+y)

def test_r11_windward_keeps_clear():
    frame = {0: dict(slot=0, x=0.0, y=5.0, hdg=315, sog=6.0, name="A"),
             1: dict(slot=1, x=0.0, y=-5.0, hdg=315, sog=6.0, name="B")}
    v = C.assess_r11_12(C._boat(frame, 0), C._boat(frame, 1), 0.0, g.DEFAULT_BOAT_LENGTH_M)
    assert v.rule == 11 and v.adjudicable
    assert v.keep_clear_slot == 0 and v.row_slot == 1


# ---- clear astern / Rule 12 ----------------------------------------------
def test_clear_astern_behind_on_same_tack():
    # B ahead at origin, A ~100 m directly astern along heading 350 (starboard)
    u = g.unit(350)
    B = (0.0, 0.0)
    A = (B[0] - 100 * u[0], B[1] - 100 * u[1])
    assert g.clear_astern(A, B, 350) is True
    assert g.overlapped(A, B, 350, 350) is False

def test_r12_astern_boat_keeps_clear():
    u = g.unit(350); B = (0.0, 0.0)
    A = (B[0] - 100 * u[0], B[1] - 100 * u[1])
    frame = {0: dict(slot=0, x=A[0], y=A[1], hdg=350, sog=6.0, name="A"),
             1: dict(slot=1, x=B[0], y=B[1], hdg=350, sog=6.0, name="B")}
    v = C.assess_r11_12(C._boat(frame, 0), C._boat(frame, 1), 0.0, g.DEFAULT_BOAT_LENGTH_M)
    assert v.rule == 12 and v.adjudicable
    assert v.keep_clear_slot == 0 and v.row_slot == 1


# ---- Rule 10 opposite tacks ----------------------------------------------
def test_r10_port_keeps_clear_of_starboard():
    frame = {0: dict(slot=0, x=-20.0, y=0.0, hdg=45, sog=6.0, name="port"),
             1: dict(slot=1, x=20.0, y=0.0, hdg=315, sog=6.0, name="stbd")}
    v = C.assess_r10(C._boat(frame, 0), C._boat(frame, 1), 0.0, g.DEFAULT_BOAT_LENGTH_M)
    assert v.rule == 10 and v.adjudicable
    assert v.keep_clear_slot == 0 and v.row_slot == 1

def test_r10_not_applicable_same_tack():
    frame = {0: dict(slot=0, x=-20.0, y=0.0, hdg=315, sog=6.0),
             1: dict(slot=1, x=20.0, y=0.0, hdg=315, sog=6.0)}
    v = C.assess_r10(C._boat(frame, 0), C._boat(frame, 1), 0.0, g.DEFAULT_BOAT_LENGTH_M)
    assert v.adjudicable is False


# ---- Rule 22 OCS ----------------------------------------------------------
def _start_course():
    return {"startLine": {"a": {"x": -100, "y": -10}, "b": {"x": 100, "y": -10}},
            "marks": [{"id": "WW", "x": 0, "y": 960}]}

def test_ocs_boat_over_early():
    boat = C.BoatState(slot=3, x=0, y=5, hdg=0, sog=0)   # on course side (+y)
    v = C.assess_r22(boat, _start_course(), g.DEFAULT_BOAT_LENGTH_M)
    assert v.adjudicable and v.keep_clear_slot == 3        # flagged OCS

def test_not_ocs_behind_line():
    boat = C.BoatState(slot=3, x=0, y=-50, hdg=0, sog=0)
    v = C.assess_r22(boat, _start_course(), g.DEFAULT_BOAT_LENGTH_M)
    assert v.adjudicable and v.keep_clear_slot is None


# ---- real-data corroboration (skipped if the blob isn't present) ----------
BLOB = os.environ.get("REGATTA_BLOB", os.path.expanduser(
    "/tmp/claude-0/-home-claude/d20a91b1-8c4d-55f6-98e4-cae6d9b028e6/scratchpad/regattatron_replay_cacbaec5.json"))

@pytest.mark.skipif(not os.path.exists(BLOB), reason="replay blob not available")
def test_ocs_bow_model_matches_engine_for_all_boats():
    """Under the bow model, the committee must reproduce the engine's gun-line
    calls for EVERY boat present at the gun -- both the flagged OCS boats and
    the clean ones (no false positives)."""
    blob = json.load(open(BLOB))
    idx, frame = C.frame_at(blob, blob["gunElapsedMs"])
    engine_ocs = {e["boatSlot"] for e in blob["events"] if e["kind"] == "OCS"}
    checked = 0
    for slot in frame:
        v = C.assess_r22(C._boat(frame, slot), blob["course"], g.DEFAULT_BOAT_LENGTH_M)
        if not v.adjudicable:
            continue  # ghost / did-not-start boat, correctly excluded
        checked += 1
        committee_ocs = v.keep_clear_slot == slot
        assert committee_ocs == (slot in engine_ocs), (
            f"slot {slot}: committee OCS={committee_ocs} but engine OCS={slot in engine_ocs}")
    assert checked >= len(engine_ocs)  # every flagged boat was actually evaluated
