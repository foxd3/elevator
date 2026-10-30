"""Generate a seeded morning-rush workload.

python scenarios/generate.py --passengers 300 --floors 51 --duration 600 > scenarios/morning_rush.csv
"""

import argparse
import random


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--passengers", type=int, default=300)
    parser.add_argument("--floors", type=int, default=51)
    parser.add_argument("--duration", type=int, default=600, help="requests arrive in [0, duration)")
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    rng = random.Random(args.seed)

    rows = []
    for i in range(args.passengers):
        roll = rng.random()
        if roll < 0.7:  # lobby to an upper floor
            source, dest = 1, rng.randint(2, args.floors)
        elif roll < 0.85:  # upper floor back down to the lobby
            source, dest = rng.randint(2, args.floors), 1
        else:  # between two upper floors
            source, dest = rng.sample(range(2, args.floors + 1), 2)
        rows.append((rng.randrange(args.duration), f"p{i}", source, dest))

    print("time,id,source,dest")
    for row in sorted(rows):
        print(",".join(map(str, row)))


if __name__ == "__main__":
    main()
