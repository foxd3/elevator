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


def read_positions(path: str | Path) -> tuple[list[str], list[list[int]]]:
    """Read a position log written by `write_positions`. Returns elevator names and rows."""
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    names = rows[0][1:] if rows and rows[0] else []
    bad_header = (
        len(rows) < 2
        or not rows[0]
        or rows[0][0] != "time"
        or not names
        or any(not name.startswith("elevator_") for name in names)
    )
    if bad_header:
        raise ValueError(f"{path} is not a position log (expected header time,elevator_1,...)")
    width = len(rows[0])
    parsed: list[list[int]] = []
    for line_no, row in enumerate(rows[1:], start=2):
        if len(row) != width:
            raise ValueError(f"{path}:{line_no}: expected {width} columns")
        try:
            parsed.append([int(cell) for cell in row])
        except ValueError as error:
            raise ValueError(f"{path}:{line_no}: expected integers") from error
    return rows[0][1:], parsed


def write_positions(path: str | Path, positions: list[list[int]]) -> None:
    elevator_count = len(positions[0]) - 1 if positions else 0
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time"] + [f"elevator_{i}" for i in range(1, elevator_count + 1)])
        writer.writerows(positions)


def format_summary(summary: dict) -> str:
    return "\n".join(f"{key}: {value}" for key, value in summary.items())
