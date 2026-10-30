# Elevator simulation

A discrete-time simulation of a destination-dispatch elevator bank. Each passenger gives an origin and a destination when they request. The controller assigns them to one elevator straight away, and that assignment never changes.

## How to run

Python 3.10 or newer. The simulation uses only the standard library. Tests need `pytest`.

```bash
# The sample from the brief
python3 -m elevator_sim scenarios/sample.csv --elevators 2 --floors 51 --capacity 8

# A 300-passenger morning rush, comparing all three schedulers
python3 -m elevator_sim scenarios/morning_rush.csv --elevators 3 --compare

# Tests (pytest is the only extra dependency)
python3 -m pip install pytest
python3 -m pytest
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--elevators` | 3 | Number of cars, from 1 to `--max-elevators` |
| `--max-elevators` | 10 | Upper limit on cars. 10 is the brief's example; raise it for bigger banks |
| `--floors` | 51 | Floors are numbered from 1 to N |
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

result = simulate([Request(0, "p1", 1, 51), Request(10, "p3", 20, 1)], elevators=2, floors=51, capacity=8)
print(result.summary)
```

## Code layout

- `elevator_sim/models.py`: `Request`, `Passenger`, and `Elevator`. Each car's movement rules live in `Elevator`.
- `elevator_sim/scheduler.py`: the three assignment strategies.
- `elevator_sim/simulation.py`: the tick loop, input checks, and summary stats.
- `elevator_sim/io.py` and `elevator_sim/__main__.py`: CSV input and output, and the CLI.

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

Morning rush: 300 passengers over 600 ticks, 51 floors, capacity 8. 70% start at the lobby going up, 15% go back down to the lobby, and 15% travel between upper floors.

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

- All cars start idle at floor 1. Floors are numbered from 1 to N.
- One tick is one floor of travel. Doors open and close instantly: boarding and getting off take no extra ticks.
- Wait is `board_time - request_time`. Travel is `alight_time - board_time`. Total time is wait plus travel. Someone picked up on the tick they asked has a wait of 0.
- Requests on the same tick are assigned in file order.
- Assignment is final, as the brief requires. A car won't hand a passenger to another car even if things change.
- Invalid requests are rejected with an error: unknown floor, same origin and destination, negative time, or duplicate id. The CLI also rejects an input file with no requests. Each request is checked when it arrives, so validation never looks ahead.
- All cars serve every floor. There are no express cars or zones.
- The elevator count defaults to a limit of 10, matching the brief's example range. Pass `max_elevators=` to `simulate`, or `--max-elevators` on the CLI, to allow more. The limit is only a sanity check; nothing else depends on it.

## Trade-offs

- **Efficiency versus fairness.** Least added time minimizes the sum of passenger-ticks. A strict sum can let one awkward passenger, for example someone far from every car's route, wait longer than a fairness-first rule would. Under capacity pressure, with assignment locked in, that passenger isn't strictly guaranteed to be served. The `max_ticks` guard in `simulate` exists to catch that rather than hang. To trade efficiency for fairness, add a penalty on long existing waits in `added_time`.
- **Cost of the what-if runs.** Each assignment simulates every car to empty. That is fine at this scale: 300 passengers take under half a second. A real controller would use an analytic estimate.
- **Instant doors.** With zero dwell time, an extra stop costs nothing. That flatters schedulers that add stops, and it is why the cost only shows up as detours.

## What I'd do with more time

- Door dwell time, for example 1 tick per stop. It would go in `Elevator.step`, and the scheduler would account for it automatically.
- Express or zoned cars. An `Elevator.serves(floor)` check would gate `board`, `has_stop`, and the scheduler.
- A fairness knob in the cost function, and a sweep showing the trade-off between average and maximum wait.
- An animated plot of `positions.csv` for the walkthrough.

## Time spent

3 to 4 hours. I was presented with a version of this problem in an earlier live interview, so the overall design was already clear.
