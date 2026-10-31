"""Replay a position log as a self-contained HTML animation.

python3 -m elevator_sim.plot positions.csv
"""

import argparse
import json
import sys
from pathlib import Path

from elevator_sim.io import read_positions

# One color per car, reused if there are more cars than colors.
CAR_COLORS = [
    "#4cc9f0",
    "#f72585",
    "#c8f542",
    "#ffd166",
    "#c77dff",
    "#ff9f1c",
    "#80ed99",
    "#f4a261",
    "#90e0ef",
    "#e9c46a",
]
CAR_HEIGHT_PX = 22

_PAGE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<style>
  :root { color-scheme: dark; }
  body { margin: 0; font-family: ui-sans-serif, system-ui, sans-serif; background: #141414; color: #eee; }
  header { display: flex; gap: 16px; align-items: center; padding: 12px 16px; background: #1c1c1c; }
  h1 { font-size: 16px; font-weight: 650; margin: 0; white-space: nowrap; flex: none; }
  button { background: #eee; color: #111; border: 0; border-radius: 6px; padding: 6px 14px; font: inherit; }
  label { font-size: 13px; color: #bbb; }
  input[type=range] { vertical-align: middle; }
  #clock { font-variant-numeric: tabular-nums; min-width: 7em; }
  .stage { display: flex; justify-content: center; gap: 10px; height: calc(100vh - 58px);
           padding: 12px 16px 28px; box-sizing: border-box; }
  .ruler-column { width: 36px; }
  .ruler { position: relative; flex: 1; }
  .mark { position: absolute; right: 0; font-size: 11px; color: #888; transform: translateY(50%); }
  .bank { display: flex; gap: 14px; }
  .column { display: flex; flex-direction: column; width: 72px; height: 100%; }
  .shaft { position: relative; flex: 1; background: #222; border: 1px solid #3a3a3a; border-radius: 8px; }
  .car { position: absolute; left: 8px; right: 8px; border-radius: 4px; text-align: center;
         font-size: 12px; font-weight: 700; color: #111; line-height: __CAR_HEIGHT__px; }
  .name { text-align: center; font-size: 12px; color: #aaa; padding-top: 6px; }
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <button id="play" type="button">Play</button>
  <label>Speed <input id="speed" type="range" min="1" max="40" value="12"></label>
  <label>Time <input id="scrub" type="range" min="0" value="0"></label>
  <span id="clock"></span>
</header>
<div class="stage">
  <div class="column ruler-column">
    <div id="ruler" class="ruler"></div>
    <div class="name">&nbsp;</div>
  </div>
  <div id="bank" class="bank"></div>
</div>
<script>
const frames = __FRAMES__;
const names = __NAMES__;
const colors = __COLORS__;
const maxFloor = __MAX_FLOOR__;
const carHeight = __CAR_HEIGHT__;

const bank = document.getElementById("bank");
const ruler = document.getElementById("ruler");
const clock = document.getElementById("clock");
const scrub = document.getElementById("scrub");
const playButton = document.getElementById("play");
const speed = document.getElementById("speed");
scrub.max = String(frames.length - 1);

const cars = names.map((name, i) => {
  const column = document.createElement("div");
  column.className = "column";
  const shaft = document.createElement("div");
  shaft.className = "shaft";
  const car = document.createElement("div");
  car.className = "car";
  car.style.background = colors[i % colors.length];
  car.style.height = carHeight + "px";
  shaft.append(car);
  const label = document.createElement("div");
  label.className = "name";
  label.textContent = name.replace(/^elevator_/, "");
  column.append(shaft, label);
  bank.append(column);
  return car;
});

const labelStep = maxFloor > 30 ? 10 : maxFloor > 16 ? 5 : 1;
for (let floor = 1; floor <= maxFloor; floor++) {
  const onStep = floor % labelStep === 0;
  const crowded = floor !== maxFloor && maxFloor - floor < labelStep;
  if (floor !== 1 && floor !== maxFloor && (!onStep || crowded)) continue;
  const mark = document.createElement("div");
  mark.className = "mark";
  mark.textContent = String(floor);
  const frac = (floor - 1) / (maxFloor - 1);
  mark.style.bottom = `calc(${frac * 100}% - ${frac * 14}px)`;
  ruler.append(mark);
}

let index = 0;
let timer = null;

function show(i) {
  const row = frames[i];
  clock.textContent = "t = " + row[0];
  scrub.value = String(i);
  cars.forEach((car, c) => {
    const floor = row[c + 1];
    const frac = (floor - 1) / (maxFloor - 1);
    car.style.bottom = `calc(${frac * 100}% - ${frac * carHeight}px)`;
    car.textContent = String(floor);
  });
}

function pause() {
  clearInterval(timer);
  timer = null;
  playButton.textContent = "Play";
}

function play() {
  if (index >= frames.length - 1) index = 0;
  clearInterval(timer);
  timer = setInterval(() => {
    index = Math.min(index + 1, frames.length - 1);
    show(index);
    if (index >= frames.length - 1) pause();
  }, 1000 / Number(speed.value));
  playButton.textContent = "Pause";
}

playButton.addEventListener("click", () => (timer ? pause() : play()));
speed.addEventListener("input", () => { if (timer) play(); });
scrub.addEventListener("input", () => { index = Number(scrub.value); show(index); });
document.addEventListener("keydown", (event) => {
  if (event.key === " " && event.target === document.body) {
    event.preventDefault();
    timer ? pause() : play();
  }
});
show(0);
</script>
</body>
</html>
"""


def render_animation(names: list[str], positions: list[list[int]], title: str = "Elevator positions") -> str:
    """Return a self-contained HTML page that replays `positions`."""
    highest = max(floor for row in positions for floor in row[1:])
    payload = {
        "__TITLE__": title,
        "__FRAMES__": _json(positions),
        "__NAMES__": _json(names),
        "__COLORS__": _json(CAR_COLORS),
        "__MAX_FLOOR__": str(max(highest, 2)),
        "__CAR_HEIGHT__": str(CAR_HEIGHT_PX),
    }
    page = _PAGE
    for key, value in payload.items():
        page = page.replace(key, value)
    return page


def _json(value: object) -> str:
    return json.dumps(value).replace("<", "\\u003c")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Animate an elevator position log in a browser")
    parser.add_argument("positions", help="CSV written by the simulation (time,elevator_1,...)")
    parser.add_argument("-o", "--output", help="HTML file to write (default: the CSV name with .html)")
    args = parser.parse_args(argv)

    source = Path(args.positions)
    output = Path(args.output) if args.output else source.with_suffix(".html")
    try:
        names, positions = read_positions(source)
        output.write_text(render_animation(names, positions))
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(f"wrote {output} ({len(positions)} ticks). Open it in a browser.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
