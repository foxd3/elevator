import csv
from pathlib import Path

from elevator_sim.models import Request


def read_requests(path: str | Path) -> list[Request]:
    """Read a CSV with a header row: time,id,source,dest."""
    with open(path, newline="") as f:
        return [
            Request(int(row["time"]), row["id"], int(row["source"]), int(row["dest"]))
            for row in csv.DictReader(f, skipinitialspace=True)
        ]


def write_positions(path: str | Path, positions: list[list[int]]) -> None:
    elevator_count = len(positions[0]) - 1 if positions else 0
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time"] + [f"elevator_{i}" for i in range(1, elevator_count + 1)])
        writer.writerows(positions)


def format_summary(summary: dict) -> str:
    return "\n".join(f"{key}: {value}" for key, value in summary.items())
