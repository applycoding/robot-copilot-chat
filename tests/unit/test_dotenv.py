import pytest

from robot_copilot.settings import SettingsError, read_dotenv


def test_dotenv_grammar(tmp_path):
    p = tmp_path / ".env"
    p.write_text("# comment\n\nFOO=bar\nexport BAD=1\n")
    with pytest.raises(SettingsError):
        read_dotenv(p)


def test_quotes(tmp_path):
    p = tmp_path / ".env"
    p.write_text('A="x y"\n')
    assert read_dotenv(p)["A"] == "x y"
