"""Repository health check tests."""

from unittest.mock import MagicMock

from app.repository.health import check_database


def test_check_database_ok() -> None:
    connection = MagicMock()
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    assert check_database(engine) == "ok"
    connection.execute.assert_called_once()


def test_check_database_unavailable() -> None:
    engine = MagicMock()
    engine.connect.side_effect = RuntimeError("db down")
    assert check_database(engine) == "unavailable"
