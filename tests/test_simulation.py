import random
from pathlib import Path

import pytest

from elevator_sim.__main__ import main
from elevator_sim.io import read_requests
from elevator_sim.models import Request
from elevator_sim.scheduler import SCHEDULERS
from elevator_sim.simulation import simulate

SCENARIOS = Path(__file__).resolve().parents[1] / "scenarios"


def run(requests, elevators=1, floors=10, capacity=8, scheduler=None):
    result = simulate(requests, elevators, floors, capacity, scheduler)
    return result, {p.id: p for p in result.passengers}


def test_single_passenger():
    result, people = run([Request(0, "a", 1, 3)])
    assert result.positions == [[0, 1], [1, 2], [2, 3]]
    assert (people["a"].wait_time, people["a"].travel_time, people["a"].total_time) == (0, 2, 2)


def test_ticks_through_gaps_with_no_requests():
    result, people = run([Request(10, "late", 1, 2)])
    assert [row[0] for row in result.positions] == list(range(12))
    assert [row[1] for row in result.positions] == [1] * 11 + [2]
    assert people["late"].wait_time == 0


def test_scheduler_only_sees_requests_that_have_arrived():
    seen = []

    class Recorder:
        def assign(self, request, elevators, now):
            assert request.time <= now
            seen.append((request.id, now))
            return elevators[0]

    run([Request(10, "late", 1, 3), Request(0, "early", 1, 2)], scheduler=Recorder())
    assert seen == [("early", 0), ("late", 10)]


def test_car_finishes_its_direction_before_picking_up_counterflow():
    # One car going up passes floor 20 at t=19, but the passenger there wants to go down.
    _, people = run(read_requests(SCENARIOS / "direction.csv"), floors=51)
    assert people["to37"].alight_time == 36
    assert people["to51"].alight_time == 50
    assert people["to1"].board_time == 81  # after reaching 51 and coming back down
    assert people["to1"].alight_time == 100


def test_sample_sends_counterflow_request_to_the_idle_car():
    # At t=10 car 1 is 9 floors from floor 20 but committed upward; car 2 is idle at floor 1.
    result, people = run(read_requests(SCENARIOS / "sample.csv"), elevators=2, floors=51)
    assert people["passenger1"].elevator_id == people["passenger2"].elevator_id == 1
    assert people["passenger3"].elevator_id == 2
    assert (people["passenger3"].wait_time, people["passenger3"].travel_time) == (19, 19)
    assert result.positions[10] == [10, 11, 1]
    s = result.summary
    assert (s["wait_min"], s["wait_max"], s["wait_avg"]) == (0, 19, 6.33)
    assert (s["total_min"], s["total_max"], s["total_avg"]) == (36, 50, 41.33)


def test_capacity_spreads_passengers_across_cars():
    requests = [Request(0, "a", 1, 3), Request(0, "b", 1, 3)]
    _, people = run(requests, elevators=2, capacity=1)
    assert people["a"].elevator_id != people["b"].elevator_id
    assert people["a"].wait_time == people["b"].wait_time == 0


def test_full_car_comes_back_for_the_second_passenger():
    _, people = run([Request(0, "a", 1, 3), Request(0, "b", 1, 3)], capacity=1)
    assert (people["a"].board_time, people["a"].alight_time) == (0, 2)
    assert (people["b"].board_time, people["b"].alight_time) == (4, 6)


def test_full_car_drops_off_and_picks_up_on_the_same_tick():
    _, people = run([Request(0, "a", 1, 2), Request(0, "b", 2, 3)], capacity=1)
    assert people["a"].alight_time == 1
    assert people["b"].board_time == 1


@pytest.mark.parametrize("name", SCHEDULERS)
def test_every_scheduler_serves_everyone_within_the_rules(name):
    rng = random.Random(7)
    floors, requests, t = 12, [], 0
    for i in range(60):
        source, dest = rng.sample(range(1, floors + 1), 2)
        requests.append(Request(t, f"p{i}", source, dest))
        t += rng.randint(0, 3)
    result, _ = run(requests, elevators=3, floors=floors, capacity=3, scheduler=SCHEDULERS[name]())
    assert [row[0] for row in result.positions] == list(range(len(result.positions)))
    assert all(1 <= floor <= floors for row in result.positions for floor in row[1:])
    for p in result.passengers:
        assert p.alight_time is not None
        assert p.wait_time >= 0
        assert p.travel_time >= abs(p.dest - p.source)


@pytest.mark.parametrize(
    "request_, message",
    [
        (Request(0, "a", 3, 3), "same floor"),
        (Request(0, "a", 1, 99), "between 1 and 10"),
        (Request(-1, "a", 1, 2), "time must be"),
    ],
)
def test_rejects_invalid_requests(request_, message):
    with pytest.raises(ValueError, match=message):
        run([request_])


def test_elevator_limit_defaults_to_ten_and_can_be_raised():
    with pytest.raises(ValueError, match="between 1 and 10"):
        simulate([Request(0, "a", 1, 2)], elevators=11, floors=5, capacity=1)
    result = simulate([Request(0, "a", 1, 2)], elevators=11, floors=5, capacity=1, max_elevators=20)
    assert len(result.positions[0]) == 12


def test_cli_max_elevators_flag(tmp_path):
    positions = tmp_path / "positions.csv"
    args = [str(SCENARIOS / "sample.csv"), "--elevators", "12", "--positions", str(positions)]
    assert main(args) == 2
    assert main(args + ["--max-elevators", "12"]) == 0
    assert positions.read_text().splitlines()[0].endswith("elevator_12")


def test_rejects_duplicate_ids():
    with pytest.raises(ValueError, match="duplicate"):
        run([Request(0, "a", 1, 2), Request(1, "a", 2, 3)])


def test_cli_writes_positions_and_prints_summary(tmp_path, capsys):
    positions = tmp_path / "positions.csv"
    code = main([str(SCENARIOS / "sample.csv"), "--elevators", "2", "--positions", str(positions)])
    assert code == 0
    lines = positions.read_text().splitlines()
    assert lines[:2] == ["time,elevator_1,elevator_2", "0,1,1"]
    assert "wait_max: 19" in capsys.readouterr().out


def test_cli_reports_bad_input_without_writing_positions(tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text("time,id,source,dest\n0,a,1,1\n")
    positions = tmp_path / "positions.csv"
    assert main([str(bad), "--positions", str(positions)]) == 2
    assert not positions.exists()
    assert "same floor" in capsys.readouterr().err


def test_cli_rejects_empty_input(tmp_path, capsys):
    empty = tmp_path / "empty.csv"
    empty.write_text("time,id,source,dest\n")
    assert main([str(empty), "--compare"]) == 2
    assert "no requests" in capsys.readouterr().err
