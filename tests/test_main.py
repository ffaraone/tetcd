from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from tetcd.main import app

runner = CliRunner()


def test_version_flag() -> None:
    """``tetcd --version`` prints the version and exits cleanly."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "tetcd" in result.stdout


def test_default_invocation_uses_v3() -> None:
    """``tetcd`` (no args) launches the TUI with the v3 client."""
    with (
        patch("tetcd.main.TetcdApp") as mock_app_cls,
        patch("tetcd.main.EtcdV3Client") as mock_v3,
        patch("tetcd.main.EtcdV2Client") as mock_v2,
    ):
        mock_app_cls.return_value.run = MagicMock()
        result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert mock_v3.called
    assert not mock_v2.called
    mock_app_cls.return_value.run.assert_called_once()


def test_api_v2_flag_uses_v2_client() -> None:
    """``--api v2`` swaps in the v2 client instead of v3."""
    with (
        patch("tetcd.main.TetcdApp") as mock_app_cls,
        patch("tetcd.main.EtcdV2Client") as mock_v2,
        patch("tetcd.main.EtcdV3Client") as mock_v3,
    ):
        mock_app_cls.return_value.run = MagicMock()
        result = runner.invoke(app, ["--api", "v2"])
    assert result.exit_code == 0
    assert mock_v2.called
    assert not mock_v3.called


def test_host_and_port_overrides() -> None:
    """``--host`` / ``--port`` flags reach the etcd client constructor."""
    with (
        patch("tetcd.main.TetcdApp") as mock_app_cls,
        patch("tetcd.main.EtcdV3Client") as mock_v3,
    ):
        mock_app_cls.return_value.run = MagicMock()
        result = runner.invoke(app, ["--host", "etcd.test", "--port", "12345"])
    assert result.exit_code == 0
    mock_v3.assert_called_once_with(host="etcd.test", port=12345)
