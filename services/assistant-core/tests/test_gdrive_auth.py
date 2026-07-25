from __future__ import annotations

from violet_assistant.config import load_settings
from violet_assistant.knowledge import gdrive_auth


def test_not_authorized_when_no_token(tmp_path):
    settings = load_settings(tmp_path)
    assert gdrive_auth.is_authorized(settings) is False
    assert gdrive_auth.load_credentials(settings) is None


def test_revoke_deletes_token_file(tmp_path):
    settings = load_settings(tmp_path)
    path = gdrive_auth.token_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    assert gdrive_auth.is_authorized(settings) is True
    assert gdrive_auth.revoke(settings) is True
    assert gdrive_auth.is_authorized(settings) is False
    assert gdrive_auth.revoke(settings) is False  # already gone
