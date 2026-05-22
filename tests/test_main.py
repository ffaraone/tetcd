from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from tetcd.main import _resolve_servers, app

runner = CliRunner()


def test_version_flag() -> None:
    """``tetcd --version`` prints the version and exits cleanly."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "tetcd" in result.stdout


def test_default_invocation_uses_v3() -> None:
    """``tetcd`` (no args) launches the TUI with at least one v3 server."""
    with (
        patch("tetcd.main.TetcdApp") as mock_app_cls,
        patch("tetcd.main.EtcdV3Client") as mock_v3,
    ):
        mock_app_cls.return_value.run = MagicMock()
        result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert mock_v3.called
    mock_app_cls.return_value.run.assert_called_once()


def test_cli_host_builds_single_adhoc_server_overriding_config() -> None:
    """``--host`` builds one ad-hoc server and ignores any configured list."""
    with (
        patch("tetcd.main.settings") as mock_settings,
        patch("tetcd.main.EtcdV3Client") as mock_v3,
    ):
        mock_settings.get.return_value = [
            {"label": "Configured", "host": "x", "port": 9, "api": "v3"}
        ]
        servers = _resolve_servers(host="etcd.test", port=12345, api_version=None, label=None)
    assert len(servers) == 1
    assert servers[0].config.host == "etcd.test"
    assert servers[0].config.port == 12345
    assert servers[0].config.api == "v3"
    mock_v3.assert_called_once_with(host="etcd.test", port=12345)


def test_cli_label_overrides_default_label() -> None:
    """``--label`` sets the display label on the ad-hoc server."""
    with patch("tetcd.main.EtcdV3Client"):
        servers = _resolve_servers(host="foo", port=None, api_version=None, label="Quick")
    assert servers[0].config.label == "Quick"


def test_cli_api_v2_uses_v2_client() -> None:
    """``--api v2`` swaps in the v2 client for the ad-hoc server."""
    with patch("tetcd.main.EtcdV2Client") as mock_v2, patch("tetcd.main.EtcdV3Client"):
        servers = _resolve_servers(host="foo", port=None, api_version="v2", label=None)
    assert servers[0].config.api == "v2"
    mock_v2.assert_called_once()


def test_configured_servers_are_resolved_from_settings() -> None:
    """When CLI flags are absent the server list comes from settings."""
    with (
        patch("tetcd.main.settings") as mock_settings,
        patch("tetcd.main.EtcdV3Client") as mock_v3,
        patch("tetcd.main.EtcdV2Client") as mock_v2,
    ):
        mock_settings.get.return_value = [
            {"label": "Prod", "api": "v3", "host": "prod", "port": 2379},
            {"label": "Stage", "api": "v2", "host": "stage", "port": 2380},
        ]
        servers = _resolve_servers(host=None, port=None, api_version=None, label=None)
    labels = [s.config.label for s in servers]
    assert labels == ["Prod", "Stage"]
    assert mock_v3.call_count == 1
    assert mock_v2.call_count == 1


def test_configured_servers_accept_non_dict_entries() -> None:
    """Dynaconf-style attribute objects in the ``servers`` list are coerced."""
    from types import SimpleNamespace

    entry = SimpleNamespace(label="Attr", api="v3", host="h", port=42)
    with (
        patch("tetcd.main.settings") as mock_settings,
        patch("tetcd.main.EtcdV3Client"),
    ):
        mock_settings.get.return_value = [entry]
        servers = _resolve_servers(host=None, port=None, api_version=None, label=None)
    assert servers[0].config.label == "Attr"
    assert servers[0].config.port == 42


def test_empty_configured_servers_falls_back_to_local() -> None:
    """An empty configured list still yields one default local server."""
    with (
        patch("tetcd.main.settings") as mock_settings,
        patch("tetcd.main.EtcdV3Client"),
    ):
        mock_settings.get.return_value = []
        servers = _resolve_servers(host=None, port=None, api_version=None, label=None)
    assert len(servers) == 1
    assert servers[0].config.label == "Local"
