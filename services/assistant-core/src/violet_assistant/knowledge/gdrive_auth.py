from __future__ import annotations

from pathlib import Path

from violet_assistant.config import Settings

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def token_path(settings: Settings) -> Path:
    return Path(settings.gdrive_token_path)


def is_authorized(settings: Settings) -> bool:
    return token_path(settings).exists()


def load_credentials(settings: Settings):
    """Return valid google Credentials (refreshing if needed) or None.

    Returns None WITHOUT importing google libs when no token file exists yet,
    so core Violet needs neither the libraries nor Drive config to run.
    """
    path = token_path(settings)
    if not path.exists():
        return None
    from google.oauth2.credentials import Credentials  # lazy
    from google.auth.transport.requests import Request  # lazy

    creds = Credentials.from_authorized_user_file(str(path), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        path.write_text(creds.to_json(), encoding="utf-8")
    return creds if creds and creds.valid else None


def authorize(settings: Settings):
    """Interactive one-time consent (opens the local browser). Not unit-tested."""
    if not settings.google_oauth_client_secrets:
        raise ValueError("GOOGLE_OAUTH_CLIENT_SECRETS is not set.")
    from google_auth_oauthlib.flow import InstalledAppFlow  # lazy

    flow = InstalledAppFlow.from_client_secrets_file(
        settings.google_oauth_client_secrets, SCOPES
    )
    creds = flow.run_local_server(port=0)
    path = token_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def revoke(settings: Settings) -> bool:
    path = token_path(settings)
    if path.exists():
        path.unlink()
        return True
    return False


if __name__ == "__main__":  # CLI: python -m violet_assistant.knowledge.gdrive_auth
    from violet_assistant.config import load_settings

    authorize(load_settings())
    print("Google Drive authorized.")
