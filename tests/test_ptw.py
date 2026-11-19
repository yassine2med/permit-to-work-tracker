from datetime import datetime

import pytest

from ptw.__main__ import main
from ptw.core import Permit, check, format_report, load_permits

NOW = datetime(2026, 3, 10, 12, 0)


def mk(pid="X1", kind="hot work", loc="Building A", issued="2026-03-10T08:00", expires="2026-03-10T12:00",
       closed=None, gas=True, fire=True):
    return Permit(pid, kind, loc, datetime.fromisoformat(issued), datetime.fromisoformat(expires),
                  datetime.fromisoformat(closed) if closed else None, gas, fire)


def rules(ps):
    return {f.rule for f in check(ps, NOW)}


def test_clean_permit_has_no_findings():
    assert check([mk()], NOW) == []


def test_hot_work_over_eight_hours():
    assert "too-long" in rules([mk(expires="2026-03-10T17:00")])


def test_confined_space_allows_longer_window():
    p = mk(kind="confined space", expires="2026-03-10T19:00")
    assert "too-long" not in rules([p])


def test_confined_space_needs_gas_test():
    assert "no-gas-test" in rules([mk(kind="confined space", gas=False)])


def test_hot_work_needs_fire_watch():
    assert "no-fire-watch" in rules([mk(fire=False)])


def test_expired_open_permit():
    assert "not-closed" in rules([mk(expires="2026-03-10T09:00")])


def test_open_permit_not_expired_is_fine():
    assert "not-closed" not in rules([mk(expires="2026-03-10T14:00")])


def test_closed_late():
    assert "closed-late" in rules([mk(expires="2026-03-10T09:00", closed="2026-03-10T11:00")])


def test_bad_window():
    assert "bad-window" in rules([mk(expires="2026-03-10T07:00")])


def test_conflict_same_location():
    hw = mk("H1")
    cs = mk("C1", kind="confined space", loc="Building A")
    assert "conflict" in rules([hw, cs])


def test_no_conflict_other_location():
    hw = mk("H1")
    cs = mk("C1", kind="confined space", loc="Building B")
    assert "conflict" not in rules([hw, cs])


def test_load_sample_and_report():
    permits = load_permits("data/permits.csv")
    assert len(permits) == 6
    text = format_report(permits, check(permits, NOW))
    assert "Permits checked: 6" in text


def test_load_missing_column(tmp_path):
    f = tmp_path / "a.csv"
    f.write_text("permit_id,kind\n1,hot work\n")
    with pytest.raises(ValueError, match="missing columns"):
        load_permits(f)


def test_load_unknown_kind(tmp_path):
    f = tmp_path / "a.csv"
    f.write_text("permit_id,kind,location,issued,expires,closed,gas_test,fire_watch\n"
                 "1,welding,A,2026-03-10T08:00,2026-03-10T09:00,,y,y\n")
    with pytest.raises(ValueError, match="line 2"):
        load_permits(f)


def test_cli_missing_file_returns_2():
    assert main(["report", "nope.csv"]) == 2


def test_cli_findings_exit_code():
    assert main(["report", "data/permits.csv", "--now", "2026-03-10T12:00"]) == 1
