from elevator_sim.models import Direction, Elevator, Passenger, Request
from elevator_sim.scheduler import LeastAddedTime, NearestCar, RoundRobin, remaining_cost


def test_least_added_time_counts_delay_to_existing_passengers():
    # Car 1 is at floor 5 heading up to collect someone at floor 6 who wants to go down.
    # A new request at floor 10 is closer to car 1, but serving it first means
    # carrying the new passenger up to 11 and making the floor-6 passenger wait 10 more ticks.
    busy = Elevator(id=1, capacity=8, floor=5, direction=Direction.UP)
    busy.pickups.append(Passenger("waiting", 6, 1, 0, 1))
    idle = Elevator(id=2, capacity=8, floor=1)
    request = Request(0, "new", 10, 11)

    assert remaining_cost(busy, 0) == 6
    assert NearestCar().assign(request, [busy, idle], 0) is busy
    assert LeastAddedTime().assign(request, [busy, idle], 0) is idle


def test_least_added_time_does_not_mutate_real_passengers():
    car = Elevator(id=1, capacity=8)
    waiting = Passenger("w", 1, 4, 0, 1)
    car.pickups.append(waiting)
    LeastAddedTime().assign(Request(0, "new", 2, 3), [car], 0)
    assert waiting.board_time is None and car.pickups == [waiting]


def test_round_robin_cycles():
    cars = [Elevator(id=i, capacity=1) for i in (1, 2, 3)]
    scheduler = RoundRobin()
    picks = [scheduler.assign(Request(0, str(i), 1, 2), cars, 0).id for i in range(4)]
    assert picks == [1, 2, 3, 1]


def test_schedulers_skip_an_express_car_that_cannot_stop_for_the_trip():
    # Car 1 is closer to floor 3, but it only stops at 1 and 10, so it cannot take 3 -> 4.
    express = Elevator(id=1, capacity=8, floor=2, stops=frozenset({1, 10}))
    local = Elevator(id=2, capacity=8, floor=8)
    request = Request(0, "p", 3, 4)
    assert NearestCar().assign(request, [express, local], 0) is local
    assert LeastAddedTime().assign(request, [express, local], 0) is local


def test_round_robin_skips_express_cars_and_keeps_cycling():
    cars = [
        Elevator(id=1, capacity=8, stops=frozenset({1, 5})),
        Elevator(id=2, capacity=8),
        Elevator(id=3, capacity=8),
    ]
    scheduler = RoundRobin()
    picks = [scheduler.assign(Request(0, str(i), 2, 3), cars, 0).id for i in range(4)]
    assert picks == [2, 3, 2, 3]


def test_nearest_car_counts_floors_without_a_floor_zero():
    # Floor 1 is one step from -1 and two steps from 3. A plain abs() would call both distance 2.
    far = Elevator(id=1, capacity=8, floor=3)
    near = Elevator(id=2, capacity=8, floor=-1)
    assert NearestCar().assign(Request(0, "p", 1, 5), [far, near], 0) is near
