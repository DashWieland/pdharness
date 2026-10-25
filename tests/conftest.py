"""Shared fixtures: no test touches the account's real pdverify config."""

import pytest


@pytest.fixture(autouse=True)
def isolated_pdverify_config(tmp_path_factory, monkeypatch):
    """doctor remembers a passing Pd in pdverify's per-user config; keep that in a temp dir."""
    monkeypatch.setenv("PDVERIFY_CONFIG_DIR", str(tmp_path_factory.mktemp("pdverify_config")))
