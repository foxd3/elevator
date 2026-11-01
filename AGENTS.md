# Agent guide

Discrete-time destination-dispatch elevator simulation. Standard library only. Read `README.md` first for behavior, assumptions, and trade-offs.

## Commands

```bash
python3 -m pip install pytest ruff                      # one-time setup
python3 -m pytest                                       # tests, must pass
ruff check .                                            # lint, must pass
python3 -m elevator_sim scenarios/sample.csv --elevators 2
python3 -m elevator_sim scenarios/morning_rush.csv --compare
```

## Layout

- `elevator_sim/models.py`: `Request`, `Passenger`, `Elevator`. All per-car movement rules live in `Elevator.step`.
- `elevator_sim/scheduler.py`: assignment strategies. A scheduler is any object with `assign(request, elevators, now) -> Elevator`.
- `elevator_sim/simulation.py`: tick loop, request validation, summary stats.
- `elevator_sim/io.py`, `elevator_sim/__main__.py`: CSV in and out, CLI.
- `scenarios/`: input CSVs and a seeded workload generator.
- `tests/`: pytest. Sample timings are asserted exactly, so behavior changes show up here.

## Invariants (do not break)

- **No peeking ahead.** Requests leave the arrival queue only on their tick. Schedulers must never see future requests.
- **Assignment is final.** Once a passenger is assigned to a car, it never changes.
- **One tick = one floor.** Order inside a tick is: arrivals, `step` for each car, log positions, `move` for each car.
- **Floor 1 is the ground floor, and there is no floor 0.** Basements are -1, -2, ... Never subtract floor numbers to count steps. Use `floors_between` and `floor_index` from `models.py`. `sample.csv` comes from the brief, so its timings must not change.
- **What-if runs reuse `Elevator.step`** via `Elevator.copy()`. Never mutate real passengers or cars inside a scheduler.

## Conventions

- Python 3.10+, type hints on public functions, no third-party runtime dependencies.
- Keep magic numbers named (for example `MAX_DRAIN_TICKS`, `MAX_ELEVATORS`).
- Invalid input raises `ValueError`. The CLI reports it on stderr and exits 2.
- A behavior change needs a test, and a README update if it changes assumptions or the results table.
- If you change scheduling or movement, re-run `--compare` and update the README results table.

## Writing tests

- Plain pytest functions and `@pytest.mark.parametrize`. No classes or fixtures unless needed.
- Build input with `Request(...)` and the `run()` helper in `tests/test_simulation.py`. Use `tmp_path` for files.
- Assert exact tick numbers (board, alight, wait) for small scenarios, and comment the expected number when it isn't obvious.

## Not in scope

Express cars, door dwell time, and reassignment are deliberately not implemented. See "What I'd do with more time" in the README.
