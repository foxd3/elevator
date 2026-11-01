from dataclasses import dataclass, field, replace
from enum import Enum


class Direction(Enum):
    UP = 1
    DOWN = -1
    IDLE = 0


# The ground floor. Cars start here, and it is the default bottom of the building.
GROUND_FLOOR = 1


# There is no floor 0: the floors run ..., -2, -1, 1, 2, ... so going down from the ground floor
# reaches -1 in one tick. Floor numbers keep their order, so comparisons (<, >) work as written.
# Anything that counts steps between floors goes through floor_index, which has no gap.
def floor_index(floor: int) -> int:
    """Position on a gapless number line: ... -2 -> -1, -1 -> 0, 1 -> 1, 2 -> 2 ..."""
    return floor if floor > 0 else floor + 1


def floor_from_index(index: int) -> int:
    return index if index > 0 else index - 1


def floors_between(a: int, b: int) -> int:
    """Number of one-tick steps between two floors."""
    return abs(floor_index(a) - floor_index(b))


@dataclass(frozen=True)
class Request:
    time: int
    id: str
    source: int
    dest: int


@dataclass
class Passenger:
    id: str
    source: int
    dest: int
    request_time: int
    elevator_id: int
    board_time: int | None = None
    alight_time: int | None = None

    @property
    def direction(self) -> Direction:
        return Direction.UP if self.dest > self.source else Direction.DOWN

    @property
    def wait_time(self) -> int:
        return self.board_time - self.request_time

    @property
    def travel_time(self) -> int:
        return self.alight_time - self.board_time

    @property
    def total_time(self) -> int:
        return self.wait_time + self.travel_time


@dataclass
class Elevator:
    id: int
    capacity: int
    floor: int = GROUND_FLOOR
    direction: Direction = Direction.IDLE
    onboard: list[Passenger] = field(default_factory=list)
    pickups: list[Passenger] = field(default_factory=list)  # assigned, not yet boarded
    stops: frozenset[int] | None = None  # None means every floor; an express car lists the floors it stops at

    @property
    def busy(self) -> bool:
        return bool(self.onboard or self.pickups)

    def serves(self, floor: int) -> bool:
        """True if this car stops at floor. An express car skips every floor not in stops."""
        return self.stops is None or floor in self.stops

    def step(self, now: int) -> list[Passenger]:
        """Run one tick at the current floor. Returns the passengers who got off."""
        alighted = [p for p in self.onboard if p.dest == self.floor]
        for p in alighted:
            p.alight_time = now
        self.onboard = [p for p in self.onboard if p.dest != self.floor]
        self.choose_direction()
        self.board(now)
        return alighted

    def move(self) -> None:
        self.floor = floor_from_index(floor_index(self.floor) + self.direction.value)

    def choose_direction(self) -> None:
        """Keep going while there is work ahead, reverse when there isn't, idle when there's nothing."""
        if self.direction is Direction.IDLE:
            self.direction = self.nearest_pickup_direction()
        elif not self.has_stop(self.direction):
            reverse = Direction(-self.direction.value)
            self.direction = reverse if self.has_stop(reverse) else Direction.IDLE

    def has_stop(self, direction: Direction) -> bool:
        def ahead(floor: int) -> bool:
            return (floor - self.floor) * direction.value > 0

        return any(ahead(p.dest) for p in self.onboard) or any(
            self.serves(p.source)
            and self.serves(p.dest)
            and (ahead(p.source) or (p.source == self.floor and p.direction is direction))
            for p in self.pickups
        )

    def nearest_pickup_direction(self) -> Direction:
        if not self.pickups:
            return Direction.IDLE
        nearest = min(self.pickups, key=lambda p: floors_between(p.source, self.floor))
        if nearest.source == self.floor:
            return nearest.direction
        return Direction.UP if nearest.source > self.floor else Direction.DOWN

    def board(self, now: int) -> None:
        """Board waiting passengers headed our way, in assignment order, while there is room."""
        for p in list(self.pickups):
            if (
                p.source == self.floor
                and self.serves(p.dest)
                and p.direction is self.direction
                and len(self.onboard) < self.capacity
            ):
                p.board_time = now
                self.onboard.append(p)
                self.pickups.remove(p)

    def copy(self) -> "Elevator":
        """Independent copy for what-if runs, so the scheduler never mutates real passengers."""
        return replace(
            self,
            onboard=[replace(p) for p in self.onboard],
            pickups=[replace(p) for p in self.pickups],
        )
