import math
import statistics
from collections import Counter, deque
from dataclasses import dataclass

from elevator_sim.models import Elevator, Passenger, Request
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
    floors: int,
    capacity: int,
    scheduler=None,
    max_ticks: int = MAX_DRAIN_TICKS,  # same "stuck" guard the scheduler uses for its what-if runs
    max_elevators: int = MAX_ELEVATORS,
) -> SimulationResult:
    if not 1 <= elevators <= max_elevators:
        raise ValueError(f"elevators must be between 1 and {max_elevators}")
    if floors < 2 or capacity < 1:
        raise ValueError("need at least 2 floors and capacity of at least 1")

    scheduler = scheduler or LeastAddedTime()
    cars = [Elevator(id=i, capacity=capacity) for i in range(1, elevators + 1)]
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
            check_request(request, floors, seen_ids)
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


def check_request(request: Request, floors: int, seen_ids: set[str]) -> None:
    if request.id in seen_ids:
        raise ValueError(f"duplicate passenger id {request.id}")
    seen_ids.add(request.id)
    if request.time < 0:
        raise ValueError(f"{request.id}: time must be >= 0")
    if request.source == request.dest:
        raise ValueError(f"{request.id}: source and dest are the same floor")
    if not (1 <= request.source <= floors and 1 <= request.dest <= floors):
        raise ValueError(f"{request.id}: floors must be between 1 and {floors}")


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
