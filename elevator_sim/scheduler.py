from elevator_sim.models import Elevator, Passenger, Request, floors_between

# A scheduler is any object with:
#     assign(request, elevators, now) -> Elevator
# It is called once per request, on the tick the request arrives, and only sees current state.

# Safety limit for remaining_cost: a car that takes longer than this to empty is assumed stuck.
# Far above any realistic drain time; it exists only to turn an infinite loop into an error.
MAX_DRAIN_TICKS = 100_000


def remaining_cost(car: Elevator, now: int) -> int:
    """Run a copy of the car until it is empty. Sum the ticks until each passenger gets off."""
    car = car.copy()
    t, total = now, 0
    while car.busy:
        total += sum(t - now for _ in car.step(t))
        car.move()
        t += 1
        if t - now > MAX_DRAIN_TICKS:
            raise RuntimeError(f"elevator {car.id} never empties")
    return total


class LeastAddedTime:
    """Pick the car where this request adds the fewest passenger-ticks.

    That is the new passenger's own wait and travel time, plus any delay it causes
    passengers already assigned to that car. Ties go to the lowest elevator id.
    """

    def assign(self, request: Request, elevators: list[Elevator], now: int) -> Elevator:
        def added_time(car: Elevator) -> int:
            with_request = car.copy()
            with_request.pickups.append(
                Passenger(request.id, request.source, request.dest, request.time, car.id)
            )
            return remaining_cost(with_request, now) - remaining_cost(car, now)

        return min(elevators, key=lambda car: (added_time(car), car.id))


class NearestCar:
    """Baseline: the car physically closest to the pickup floor, ignoring direction and load."""

    def assign(self, request: Request, elevators: list[Elevator], now: int) -> Elevator:
        return min(elevators, key=lambda car: (floors_between(car.floor, request.source), car.id))


class RoundRobin:
    """Baseline: cycle through the cars in order, ignoring state."""

    def __init__(self) -> None:
        self.next_index = 0

    def assign(self, request: Request, elevators: list[Elevator], now: int) -> Elevator:
        car = elevators[self.next_index % len(elevators)]
        self.next_index += 1
        return car


SCHEDULERS = {
    "least_added_time": LeastAddedTime,
    "nearest": NearestCar,
    "round_robin": RoundRobin,
}
