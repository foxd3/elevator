# Elevator simulation

A discrete-time simulation of a destination-dispatch elevator bank. Each passenger gives an origin and a destination when they request. The controller assigns them to one elevator straight away, and that assignment never changes.

## How to run

Python 3.10 or newer. The simulation uses only the standard library. Dependencies for development (`pytest` and `ruff`) are managed with [Poetry](https://python-poetry.org/).

```bash
poetry install            # creates .venv and installs pytest and ruff from poetry.lock
poetry run pytest         # tests
poetry run ruff check .   # lint
poetry run elevator-sim scenarios/sample.csv --elevators 2   # same as python3 -m elevator_sim
```

Without Poetry, `python3 -m elevator_sim ...` still works from the repo root, because the simulation needs nothing installed. The examples below use that form.

```bash
# The sample from the brief
python3 -m elevator_sim scenarios/sample.csv --elevators 2 --max-floor 51 --capacity 8

# A 300-passenger morning rush, comparing all three schedulers
python3 -m elevator_sim scenarios/morning_rush.csv --elevators 3 --compare

# Tests
python3 -m pytest
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--elevators` | 3 | Number of cars, from 1 to `--max-elevators` |
| `--max-elevators` | 10 | Upper limit on cars. 10 is the brief's example; raise it for bigger banks |
| `--max-floor` | 51 | Top floor. 51 is the default because the brief's sample sends `passenger1` to floor 51 |
| `--min-floor` | 1 | Bottom floor, also the ground floor. Use a negative number to add basements, for example `-2`. There is no floor 0 |
| `--capacity` | 8 | Maximum passengers per car |
| `--scheduler` | `least_added_time` | Also `nearest` or `round_robin` |
| `--positions` | `positions.csv` | Where the position log is written |
| `--compare` | off | Run every scheduler and print a table |

The position log has one row per tick, starting at 0: `time,elevator_1,elevator_2,...`. The summary prints min, max, and average wait and total time. It also prints the median and 95th-percentile total time, how many passengers waited 0, the passenger who waited longest, and how many passengers each car carried.

To make a new workload, run `python3 scenarios/generate.py --passengers 500 --seed 2 > my.csv`.

From Python:

```python
from elevator_sim.models import Request
from elevator_sim.simulation import simulate

result = simulate([Request(0, "p1", 1, 51), Request(10, "p3", 20, 1)], elevators=2, max_floor=51, capacity=8)
print(result.summary)
```

## Code layout

- `elevator_sim/models.py`: `Request`, `Passenger`, and `Elevator`. Each car's movement rules live in `Elevator`.
- `elevator_sim/scheduler.py`: the three assignment strategies.
- `elevator_sim/simulation.py`: the tick loop, input checks, and summary stats.
- `elevator_sim/io.py` and `elevator_sim/__main__.py`: CSV input and output, and the CLI.
- `AGENTS.md`: commands, layout, invariants, and conventions for AI coding agents working in this repo.

## How a tick works

Every tick `t` does the following, in this order:

1. **Arrivals.** Pop requests with `time <= t` off a time-sorted queue. Hand each one to the scheduler, which picks a car. The passenger joins that car's `pickups`. The scheduler only ever sees the current request and the current cars, never later rows.
2. **Each car takes one step** (`Elevator.step`):
   - Passengers whose destination is this floor get off.
   - The car chooses a direction. It keeps going while there is a stop ahead. With nothing ahead, it reverses if there is work behind it. Otherwise it goes idle. An idle car heads toward its nearest waiting passenger.
   - Waiting passengers on this floor who are going the car's direction get on, while there is room.
3. **Log** every car's floor for time `t`.
4. **Move** every car one floor in its direction, or keep it in place if idle.

The run ends when no requests remain and every car is empty.

These rules guarantee the elevator constraints and that everyone is served eventually:

- **Direction.** A car never picks up someone going the opposite way, and it never turns around while it still has a stop ahead. This is the classic elevator, or SCAN, sweep. Each sweep ends at the farthest committed stop, so every assigned passenger is reached.
- **Capacity.** Boarding stops when the car is full. A passenger who can't fit waits for the car's next pass.
- **Same-tick handoff.** People get off before others board, so a full car can drop one passenger and pick up another on the same tick.

## The scheduler: least added time

The objective is to minimize total time per passenger. For each car, the scheduler runs a copy of that car forward until it is empty, twice: once without the new passenger and once with them. The car that gets the request is the one where it adds the fewest total passenger-ticks. That count includes the new passenger's own wait and travel time, plus any delay it causes passengers already assigned to that car. Ties go to the lowest elevator id.

The what-if runs reuse the same `Elevator.step` as the real simulation. That keeps the cost estimate consistent with direction and capacity rules automatically.

Two examples:

- In the sample, at t=10 car 1 is 9 floors from `passenger3` but is busy carrying people up to 37 and 51. Assigning `passenger3` to it would cost 90 ticks, because they'd be picked up on the way back down. Idle car 2 costs 38 ticks, 19 waiting and 19 riding, so car 2 wins.
- `tests/test_scheduler.py` covers a case where picking the car with the earliest pickup would be wrong. The closer car would have to detour upward and delay someone it's already committed to.

The baselines, `nearest` (closest car, ignoring direction and load) and `round_robin`, are there for comparison.

## Results

Morning rush: 300 passengers over 600 ticks, floors 1 to 51 (`--max-floor 51`, the default, which the brief's sample requires; the workload didn't need a tower this tall), capacity 8. Floor 1 is the lobby. 70% start there going up, 15% go back down to it, and 15% travel between upper floors.

| Elevators | Scheduler | Avg wait | Max wait | Avg total | p95 total | Max total |
| --- | --- | --- | --- | --- | --- | --- |
| 3 | least_added_time | 78.7 | 229 | 102.0 | 224 | 266 |
| 3 | nearest | 129.4 | 374 | 152.6 | 330 | 422 |
| 3 | round_robin | 108.3 | 314 | 131.5 | 252 | 339 |
| 6 | least_added_time | 14.6 | 47 | 37.8 | 71 | 96 |
| 6 | nearest | 47.6 | 197 | 70.8 | 143 | 240 |
| 6 | round_robin | 43.4 | 97 | 66.6 | 114 | 140 |

What this shows:

- Three cars are overloaded for this demand. Waits grow throughout the run. Doubling to six cars cuts the average wait by about 80%.
- `nearest` does worst. It sends cars to passengers going the other way, and they then wait a whole sweep.
- Minimizing *total* added time also gave the best *worst-case* wait here. That isn't guaranteed: the objective is efficiency, not fairness.

## Assumptions and simplifications

- All cars start idle at floor 1, the ground floor. The building runs from `min_floor` (default 1) to `max_floor`, both inclusive. Both are floor numbers, not counts, so with `min_floor=-2` and `max_floor=50` the floors are `-2, -1, 1 ... 50`, which is 52 floors.
- Basements are optional (`--min-floor -2`, or `min_floor=` in `simulate`). There is no floor 0, as in a real building: the floors run `-2, -1, 1, 2, ...`, so going from floor 1 to -1 is one tick, not two. `Elevator.move` and every distance calculation go through `floor_index` and `floors_between` in `models.py`, which close that gap. Comparing floors with `<` and `>` still works, because the numbering keeps its order.
- One tick is one floor of travel, as the brief defines it. The brief says nothing about time spent at a stop, so I treat stops as free: doors open and close instantly, and every passenger who can get off or on does so on the same tick, however many there are. This is a large simplification of real elevators, where each stop costs time (doors, plus people walking in and out) and a busy stop costs more than a quiet one. See the trade-offs below.
- Wait is `board_time - request_time`. Travel is `alight_time - board_time`. Total time is wait plus travel. Someone picked up on the tick they asked has a wait of 0.
- Requests on the same tick are assigned in file order.
- One request is one passenger, and riders behave as declared: everyone submits their own request, boards the car they were assigned, and gets off at their stated floor. Capacity counts requests, so two people travelling together on one request would exceed the real car capacity without the model noticing. Real systems guard against this by weighing the car and by asking for a party size.
- Assignment is final, as the brief requires. A car won't hand a passenger to another car even if things change.
- Invalid requests are rejected with an error: unknown floor, same origin and destination, negative time, or duplicate id. The CLI also rejects an input file with no requests. Each request is checked when it arrives, so validation never looks ahead.
- All cars serve every floor. There are no express cars or zones.
- The elevator count defaults to a limit of 10, matching the brief's example range. Pass `max_elevators=` to `simulate`, or `--max-elevators` on the CLI, to allow more. The limit is only a sanity check; nothing else depends on it.

## Trade-offs

- **Efficiency versus fairness.** Least added time minimizes the sum of passenger-ticks. A strict sum can let one awkward passenger, for example someone far from every car's route, wait longer than a fairness-first rule would. Under capacity pressure, with assignment locked in, that passenger isn't strictly guaranteed to be served. The `max_ticks` guard in `simulate` exists to catch that rather than hang. To trade efficiency for fairness, add a penalty on long existing waits in `added_time`.
- **Cost of the what-if runs.** Each assignment simulates every car to empty. That is fine at this scale: 300 passengers take under half a second. A real controller would use an analytic estimate.
- **Free stops.** With zero dwell time, an extra stop costs nothing and loading 8 people costs the same as driving past. A real stop typically costs several times as long as passing a floor, so real controllers work hard to avoid unnecessary stops, such as grouping passengers who share a destination. My model can't see that benefit, because stopping is never penalized. It flatters schedulers that add stops, and it is why the cost only shows up as detours. It probably also understates how much a good scheduler gains over `nearest` and `round_robin`, since they make more stops. Destination dispatch exists so the controller can group people by destination and avoid stops, and this model cannot show that saving.

## What I'd do with more time

- Realistic stop cost: a fixed door time per stop, plus a per-passenger load and unload time, so that a crowded stop takes longer than an empty one. It would go in `Elevator.step` and `move`, and the scheduler would account for it automatically because `remaining_cost` reuses `step`. This is the biggest gap between the model and a real elevator, and it would make grouping by destination valuable, which is the point of destination dispatch.
- Express or zoned cars. An `Elevator.serves(floor)` check would gate `board`, `has_stop`, and the scheduler.
- A `party_size` on each request, so capacity counts people instead of requests, and a no-show or wrong-car rider to show how the model fails.
- A fairness knob in the cost function, and a sweep showing the trade-off between average and maximum wait.
- An animated plot of `positions.csv` for the walkthrough.

## Time spent

3 to 4 hours. I was presented with a version of this problem in an earlier live interview, so the overall design was already clear.
