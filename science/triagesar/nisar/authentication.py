"""NASA Earthdata Login credential handling. Secrets are never logged or printed."""

from __future__ import annotations

import netrc
import os
from dataclasses import dataclass
from pathlib import Path

import requests

URS_HOST = "urs.earthdata.nasa.gov"
TOKEN_ENDPOINT = f"https://{URS_HOST}/api/users/find_or_create_token"
HELP = (
    "Earthdata credentials not found. Create a free account at https://urs.earthdata.nasa.gov/ and then either "
    "set EARTHDATA_TOKEN (Profile > Generate Token), or EARTHDATA_USERNAME and EARTHDATA_PASSWORD, in the "
    "environment or in a .env file, or add a 'machine urs.earthdata.nasa.gov' entry to ~/.netrc."
)


class AuthenticationError(RuntimeError):
    """Earthdata credentials are missing or were rejected."""


@dataclass(frozen=True)
class EarthdataCredentials:
    token: str | None = None
    username: str | None = None
    password: str | None = None
    source: str = "none"

    def __repr__(self) -> str:  # never expose secrets in logs or tracebacks
        kind = "token" if self.token else ("username/password" if self.username else "none")
        return f"EarthdataCredentials(kind={kind!r}, source={self.source!r})"

    @property
    def available(self) -> bool:
        return bool(self.token or (self.username and self.password))


def load_dotenv(path: Path) -> dict[str, str]:
    """Minimal .env parser (KEY=VALUE lines). Values are returned, never logged."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip().removeprefix("export ").strip()] = value.strip().strip("'\"")
    return values


def resolve_credentials(dotenv_path: Path | None = None, netrc_path: Path | None = None) -> EarthdataCredentials:
    """Look for credentials in the environment, then .env, then ~/.netrc."""
    sources: list[tuple[str, dict[str, str]]] = [("environment", dict(os.environ))]
    if dotenv_path is not None:
        sources.append((".env", load_dotenv(dotenv_path)))
    for name, env in sources:
        token = env.get("EARTHDATA_TOKEN", "").strip()
        if token:
            return EarthdataCredentials(token=token, source=name)
        user, password = env.get("EARTHDATA_USERNAME", "").strip(), env.get("EARTHDATA_PASSWORD", "")
        if user and password:
            return EarthdataCredentials(username=user, password=password, source=name)
    try:
        auth = netrc.netrc(str(netrc_path) if netrc_path else None).authenticators(URS_HOST)
    except (FileNotFoundError, netrc.NetrcParseError):
        auth = None
    if auth and auth[0] and auth[2]:
        return EarthdataCredentials(username=auth[0], password=auth[2], source="netrc")
    return EarthdataCredentials()


def bearer_token(creds: EarthdataCredentials, timeout_s: float = 30.0) -> str:
    """Return a bearer token, exchanging username/password for one if necessary."""
    if not creds.available:
        raise AuthenticationError(HELP)
    if creds.token:
        return creds.token
    try:
        resp = requests.post(TOKEN_ENDPOINT, auth=(creds.username or "", creds.password or ""), timeout=timeout_s)
    except requests.RequestException as exc:
        raise AuthenticationError(f"Could not reach Earthdata Login: {type(exc).__name__}") from None
    if resp.status_code in (401, 403):
        raise AuthenticationError("Earthdata Login rejected the username/password.")
    if resp.status_code != 200:
        raise AuthenticationError(f"Earthdata Login returned HTTP {resp.status_code} when requesting a token.")
    token = resp.json().get("access_token")
    if not token:
        raise AuthenticationError("Earthdata Login did not return an access token.")
    return str(token)
