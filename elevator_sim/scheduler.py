from elevator_sim.models import Elevator, Passenger, Request, floors_between

# A scheduler is any object with:
#     assign(request, elevators, now) -> Elevator
# It is called once per request, on the tick the request arrives, and only sees current state.

# Safety limit for remaining_cost: a car that takes longer than this to empty is assumed stuck.
# Far above any realistic drain time; it exists only to turn an infinite loop into an error.
MAX_DRAIN_TICKS = 100_000


def eligible(request: Request, elevators: list[Elevator]) -> list[Elevator]:
    """Cars that stop at both ends of this trip. An express car skips the floors it does not serve."""
    cars = [car for car in elevators if car.serves(request.source) and car.serves(request.dest)]
    if not cars:
        raise ValueError(
            f"{request.id}: no elevator serves both floor {request.source} and floor {request.dest}"
        )
    return cars


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

        return min(eligible(request, elevators), key=lambda car: (added_time(car), car.id))


class NearestCar:
    """Baseline: the car physically closest to the pickup floor, ignoring direction and load."""

    def assign(self, request: Request, elevators: list[Elevator], now: int) -> Elevator:
        cars = eligible(request, elevators)
        return min(cars, key=lambda car: (floors_between(car.floor, request.source), car.id))


class RoundRobin:
    """Baseline: cycle through the cars in order, ignoring state."""

    def __init__(self) -> None:
        self.next_index = 0

    def assign(self, request: Request, elevators: list[Elevator], now: int) -> Elevator:
        count = len(elevators)
        for offset in range(count):
            index = (self.next_index + offset) % count
            car = elevators[index]
            if car.serves(request.source) and car.serves(request.dest):
                self.next_index = index + 1
                return car
        raise ValueError(
            f"{request.id}: no elevator serves both floor {request.source} and floor {request.dest}"
        )


SCHEDULERS = {
    "least_added_time": LeastAddedTime,
    "nearest": NearestCar,
    "round_robin": RoundRobin,
}
