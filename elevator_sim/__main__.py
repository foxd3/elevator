import argparse
import sys

from elevator_sim.io import format_summary, read_requests, write_positions
from elevator_sim.models import GROUND_FLOOR
from elevator_sim.scheduler import SCHEDULERS
from elevator_sim.simulation import MAX_ELEVATORS, parse_express, simulate

COMPARE_COLUMNS = ["wait_avg", "wait_max", "total_avg", "total_median", "total_p95", "total_max"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Destination-dispatch elevator simulation")
    parser.add_argument("input", help="CSV of time,id,source,dest")
    parser.add_argument("--elevators", type=int, default=3)
    parser.add_argument("--max-elevators", type=int, default=MAX_ELEVATORS, help="upper limit on --elevators")
    parser.add_argument("--max-floor", type=int, default=51, help="top floor")
    parser.add_argument(
        "--min-floor", type=int, default=GROUND_FLOOR, help="bottom floor; negative adds basements (no 0)"
    )
    parser.add_argument("--capacity", type=int, default=8)
    parser.add_argument("--scheduler", choices=SCHEDULERS, default="least_added_time")
    parser.add_argument(
        "--express",
        action="append",
        default=[],
        metavar="CAR=FLOORS",
        help="floors this car stops at, for example 1=1,30-50. Repeat for each express car",
    )
    parser.add_argument("--positions", default="positions.csv", help="where to write the position log")
    parser.add_argument("--compare", action="store_true", help="run every scheduler and print a table")
    args = parser.parse_args(argv)

    def run(scheduler):
        return simulate(
            requests, args.elevators, args.max_floor, args.capacity, scheduler,
            max_elevators=args.max_elevators, min_floor=args.min_floor, express=express or None,
        )

    try:
        requests = read_requests(args.input)
        if not requests:
            raise ValueError(f"no requests in {args.input}")
        express: dict[int, frozenset[int]] = {}
        for spec in args.express:
            car_id, stops = parse_express(spec)
            if car_id in express:
                raise ValueError(f"elevator {car_id} listed twice in --express")
            express[car_id] = stops
        if args.compare:
            print(f"{'scheduler':<18}" + "".join(f"{c:>14}" for c in COMPARE_COLUMNS))
            for name, scheduler_class in SCHEDULERS.items():
                result = run(scheduler_class())
                print(f"{name:<18}" + "".join(f"{result.summary[c]:>14}" for c in COMPARE_COLUMNS))
            return 0
        result = run(SCHEDULERS[args.scheduler]())
    except (ValueError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    write_positions(args.positions, result.positions)
    print(format_summary(result.summary))
    print(f"positions written to {args.positions} ({len(result.positions)} ticks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
