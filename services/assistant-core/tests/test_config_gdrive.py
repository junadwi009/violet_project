from __future__ import annotations

import os

from violet_assistant.config import load_settings


def test_gdrive_settings_read_from_env(tmp_path):
    env = {
        "KNOWLEDGE_SOURCES": "local,gdrive",
        "GDRIVE_FOLDER_ID": "FID",
        "GDRIVE_SHARED_DRIVE_ID": "SD1",
    }
    for k, v in env.items():
        os.environ[k] = v
    try:
        s = load_settings(tmp_path)
        assert s.knowledge_sources == "local,gdrive"
        assert s.gdrive_folder_id == "FID"
        assert s.gdrive_shared_drive_id == "SD1"
        assert s.gdrive_token_path.endswith("gdrive_token.json")
    finally:
        for k in env:
            os.environ.pop(k, None)
