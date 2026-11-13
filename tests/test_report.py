import pytest

from scbot.report import format_table, summarise_blocks


def episode(number: int, result: str, ret: float, decisions: int, no_ops: int) -> dict[str, str]:
    return {
        "episode": str(number),
        "result": result,
        "return": str(ret),
        "decisions": str(decisions),
        "game_minutes": "10.0",
        "action_NO_OP": str(no_ops),
        "marines_trained": "20",
        "epsilon": str(1.0 - number / 10),
    }


ROWS = [
    episode(1, "Victory", 2.0, 100, 50),
    episode(2, "Defeat", -1.0, 300, 250),
    episode(3, "Tie", 0.5, 200, 20),
]


def test_blocks_count_results_and_average_the_rest():
    first, second = summarise_blocks(ROWS, block=2)

    assert (first["first"], first["last"], first["games"]) == (1, 2, 2)
    assert (first["wins"], first["losses"], first["ties"]) == (1, 1, 0)
    assert first["win_rate"] == pytest.approx(0.5)
    assert first["mean_return"] == pytest.approx(0.5)
    assert first["mean_decisions"] == pytest.approx(200)
    assert first["no_op_share"] == pytest.approx(300 / 400)  # weighted by decisions
    assert first["epsilon"] == pytest.approx(0.8)  # epsilon of the block's last game

    assert (second["first"], second["last"], second["games"]) == (3, 3, 1)
    assert (second["wins"], second["losses"], second["ties"]) == (0, 0, 1)


def test_table_has_one_line_per_block_plus_a_header():
    table = format_table(summarise_blocks(ROWS, block=2))

    lines = table.splitlines()
    assert len(lines) == 3
    assert "win%" in lines[0]
    assert lines[1].split()[0] == "1-2"
    assert lines[2].split()[0] == "3-3"
