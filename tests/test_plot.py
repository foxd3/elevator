import pytest

from elevator_sim.io import read_positions, write_positions
from elevator_sim.plot import main, render_animation


def test_read_positions_round_trip(tmp_path):
    path = tmp_path / "positions.csv"
    write_positions(path, [[0, 1, 1], [1, 2, 1]])
    names, rows = read_positions(path)
    assert names == ["elevator_1", "elevator_2"]
    assert rows == [[0, 1, 1], [1, 2, 1]]


def test_read_positions_rejects_a_request_csv(tmp_path):
    path = tmp_path / "requests.csv"
    path.write_text("time,id,source,dest\n0,a,1,2\n")
    with pytest.raises(ValueError, match="position log"):
        read_positions(path)


def test_render_animation_embeds_the_log():
    html = render_animation(["elevator_1"], [[0, 1], [1, 4]])
    assert "[[0, 1], [1, 4]]" in html
    assert "function floorIndex" in html
    assert "elevator_1" in html


def test_render_animation_puts_the_basement_next_to_the_ground_floor():
    # Floor -1 is one step below floor 1. The page must not treat floor 0 as a real stop.
    html = render_animation(["elevator_1"], [[0, -1], [1, 1]])
    assert "[[0, -1], [1, 1]]" in html
    assert "(floor - 1)" not in html


def test_plot_cli_writes_html_next_to_the_csv(tmp_path, capsys):
    source = tmp_path / "positions.csv"
    write_positions(source, [[0, 1], [1, 3], [2, 2]])
    assert main([str(source)]) == 0
    written = (tmp_path / "positions.html").read_text()
    assert "[[0, 1], [1, 3], [2, 2]]" in written
    assert "Open it in a browser" in capsys.readouterr().out


def test_plot_cli_reports_bad_input(tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text("time,elevator_1\n0,nope\n")
    assert main([str(bad), "-o", str(tmp_path / "out.html")]) == 2
    assert not (tmp_path / "out.html").exists()
    assert "expected integers" in capsys.readouterr().err
