from dataclasses import dataclass, field, replace
from enum import Enum


class Direction(Enum):
    UP = 1
    DOWN = -1
    IDLE = 0


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
    floor: int = 1
    direction: Direction = Direction.IDLE
    onboard: list[Passenger] = field(default_factory=list)
    pickups: list[Passenger] = field(default_factory=list)  # assigned, not yet boarded

    @property
    def busy(self) -> bool:
        return bool(self.onboard or self.pickups)

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
        self.floor += self.direction.value

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
            ahead(p.source) or (p.source == self.floor and p.direction is direction)
            for p in self.pickups
        )

    def nearest_pickup_direction(self) -> Direction:
        if not self.pickups:
            return Direction.IDLE
        nearest = min(self.pickups, key=lambda p: abs(p.source - self.floor))
        if nearest.source == self.floor:
            return nearest.direction
        return Direction.UP if nearest.source > self.floor else Direction.DOWN

    def board(self, now: int) -> None:
        """Board waiting passengers headed our way, in assignment order, while there is room."""
        for p in list(self.pickups):
            if (
                p.source == self.floor
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
