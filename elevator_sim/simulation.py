import math
import re
import statistics
from collections import Counter, deque
from dataclasses import dataclass

from elevator_sim.models import GROUND_FLOOR, Elevator, Passenger, Request, floors_between
from elevator_sim.scheduler import MAX_DRAIN_TICKS, LeastAddedTime

MAX_ELEVATORS = 10  # the brief's example range; override per run with max_elevators


@dataclass
class SimulationResult:
    positions: list[list[int]]  # one row per tick: [time, floor of elevator 1, floor of elevator 2, ...]
    passengers: list[Passenger]
    summary: dict


def simulate(
    requests: list[Request],
    elevators: int,
    max_floor: int,
    capacity: int,
    scheduler=None,
    max_ticks: int = MAX_DRAIN_TICKS,  # same "stuck" guard the scheduler uses for its what-if runs
    max_elevators: int = MAX_ELEVATORS,
    min_floor: int = GROUND_FLOOR,
    express: dict[int, frozenset[int]] | None = None,
) -> SimulationResult:
    if not 1 <= elevators <= max_elevators:
        raise ValueError(f"elevators must be between 1 and {max_elevators}")
    if min_floor == 0 or min_floor > GROUND_FLOOR:
        raise ValueError(f"min_floor must be {GROUND_FLOOR} or a negative floor (there is no floor 0)")
    if max_floor < GROUND_FLOOR or floors_between(min_floor, max_floor) < 1 or capacity < 1:
        raise ValueError("need at least 2 floors and capacity of at least 1")

    scheduler = scheduler or LeastAddedTime()
    served = express or {}
    check_express(served, elevators, min_floor, max_floor)
    cars = [
        Elevator(id=i, capacity=capacity, stops=served.get(i))  # start on the ground floor
        for i in range(1, elevators + 1)
    ]
    # Arrival queue. Requests leave it only when their time comes, so nothing later is visible.
    arrivals = deque(sorted(requests, key=lambda r: r.time))
    passengers: list[Passenger] = []
    seen_ids: set[str] = set()
    positions: list[list[int]] = []

    t = 0
    while arrivals or any(car.busy for car in cars):
        if t > max_ticks:
            raise RuntimeError(f"simulation did not finish within {max_ticks} ticks")

        while arrivals and arrivals[0].time <= t:
            request = arrivals.popleft()
            check_request(request, max_floor, seen_ids, min_floor)
            car = scheduler.assign(request, cars, t)
            passenger = Passenger(request.id, request.source, request.dest, request.time, car.id)
            car.pickups.append(passenger)
            passengers.append(passenger)

        for car in cars:
            car.step(t)
        positions.append([t] + [car.floor for car in cars])
        for car in cars:
            car.move()
        t += 1

    return SimulationResult(positions, passengers, summarize(passengers))


def parse_express(spec: str) -> tuple[int, frozenset[int]]:
    """Parse ``1=1,30-50`` into an elevator id and the floors that car stops at.

    A token is one floor (``1``, ``-2``) or a range. Positive ranges use a hyphen (``30-50``).
    Ranges that include a negative floor use ``..`` (``-2..2``). Floor 0 is never a stop.
    """
    if spec.count("=") != 1:
        raise ValueError(f"express spec {spec!r} must look like 1=1,30-50")
    car_text, floors_text = spec.split("=")
    try:
        car_id = int(car_text)
    except ValueError as error:
        raise ValueError(f"express spec {spec!r} must look like 1=1,30-50") from error
    if not floors_text:
        raise ValueError(f"elevator {car_id} stops at no floors")
    stops: set[int] = set()
    for token in floors_text.split(","):
        token = token.strip()
        if ".." in token:
            ends = token.split("..")
            if len(ends) != 2:
                raise ValueError(f"bad floor range {token!r} in {spec!r}")
            lo, hi = int(ends[0]), int(ends[1])
        elif re.fullmatch(r"\d+-\d+", token):
            lo_text, hi_text = token.split("-")
            lo, hi = int(lo_text), int(hi_text)
        elif re.fullmatch(r"-?\d+", token):
            floor = int(token)
            if floor == 0:
                raise ValueError(f"{spec}: there is no floor 0")
            stops.add(floor)
            continue
        else:
            raise ValueError(f"bad floor {token!r} in {spec!r}")
        if lo > hi:
            lo, hi = hi, lo
        stops.update(floor for floor in range(lo, hi + 1) if floor != 0)
    if not stops:
        raise ValueError(f"elevator {car_id} stops at no floors")
    return car_id, frozenset(stops)


def check_express(
    express: dict[int, frozenset[int]], elevators: int, min_floor: int, max_floor: int
) -> None:
    for car_id, stops in express.items():
        if not 1 <= car_id <= elevators:
            raise ValueError(f"express car {car_id} is not one of the {elevators} elevators")
        if not stops:
            raise ValueError(f"elevator {car_id} stops at no floors")
        outside = sorted(floor for floor in stops if floor < min_floor or floor > max_floor)
        if outside:
            raise ValueError(
                f"elevator {car_id} stops at {outside[0]}, outside {min_floor} to {max_floor}"
            )


def check_request(
    request: Request, max_floor: int, seen_ids: set[str], min_floor: int = GROUND_FLOOR
) -> None:
    if request.id in seen_ids:
        raise ValueError(f"duplicate passenger id {request.id}")
    seen_ids.add(request.id)
    if request.time < 0:
        raise ValueError(f"{request.id}: time must be >= 0")
    if request.source == request.dest:
        raise ValueError(f"{request.id}: source and dest are the same floor")
    on_a_real_floor = all(min_floor <= f <= max_floor and f != 0 for f in (request.source, request.dest))
    if not on_a_real_floor:
        note = " (there is no floor 0)" if min_floor < 0 else ""
        raise ValueError(f"{request.id}: floors must be between {min_floor} and {max_floor}{note}")


def summarize(passengers: list[Passenger]) -> dict:
    if not passengers:
        return {"passengers": 0}
    waits = [p.wait_time for p in passengers]
    totals = [p.total_time for p in passengers]
    longest_wait = max(passengers, key=lambda p: p.wait_time)
    return {
        "passengers": len(passengers),
        "wait_min": min(waits),
        "wait_max": max(waits),
        "wait_avg": round(statistics.mean(waits), 2),
        "total_min": min(totals),
        "total_max": max(totals),
        "total_avg": round(statistics.mean(totals), 2),
        "total_median": statistics.median(totals),
        "total_p95": percentile(totals, 95),
        "zero_wait_passengers": waits.count(0),
        "longest_wait": f"{longest_wait.id} ({longest_wait.wait_time} ticks)",
        "passengers_per_elevator": dict(sorted(Counter(p.elevator_id for p in passengers).items())),
    }


def percentile(values: list[int], pct: int) -> int:
    """Nearest-rank percentile."""
    ordered = sorted(values)
    return ordered[math.ceil(pct / 100 * len(ordered)) - 1]
