"""Validation for navigation requests and acknowledgements; no network access."""

from __future__ import annotations

import re
from collections.abc import Mapping
from urllib.parse import urlsplit


class RouteValidationError(ValueError):
    """A route or its acknowledgement cannot be accepted."""


def normalize_proxy_settings(url: str, fingerprint: str) -> tuple[str, str]:
    """Require HTTPS and an explicit SHA-256 certificate pin."""
    try:
        parts = urlsplit(url.strip())
        _ = parts.port
    except (ValueError, AttributeError) as err:
        raise RouteValidationError("A helyi szolgáltatás címe nem érvényes.") from err
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.path not in ("", "/")
        or parts.query
        or parts.fragment
    ):
        raise RouteValidationError("A helyi szolgáltatás címe HTTPS-alapcím legyen.")
    pin = fingerprint.replace(":", "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{64}", pin) is None:
        raise RouteValidationError("Érvényes SHA-256 tanúsítványazonosító szükséges.")
    return url.strip().rstrip("/"), pin


def build_waypoints_payload(vin: str, waypoints: list[dict]) -> dict[str, str]:
    """Validate all destinations before any command can be sent."""
    if not isinstance(vin, str) or re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", vin) is None:
        raise RouteValidationError("A járműazonosító nem érvényes.")
    if not isinstance(waypoints, list) or not waypoints:
        raise RouteValidationError("Az útvonalhoz legalább egy megálló szükséges.")
    values = []
    for waypoint in waypoints:
        place_id = waypoint.get("place_id") if isinstance(waypoint, Mapping) else None
        if not isinstance(place_id, str) or re.fullmatch(r"[A-Za-z0-9_-]+", place_id) is None:
            raise RouteValidationError("Az útvonal egyik helyazonosítója nem érvényes.")
        values.append(f"refId:{place_id}")
    return {"waypoints": ",".join(values)}


def require_command_acknowledgement(status: int, body: object) -> None:
    """A transport success alone never confirms the navigation command."""
    if status != 200:
        raise RouteValidationError(f"A Tesla nem fogadta el a parancsot: HTTP {status}.")
    if not isinstance(body, Mapping) or body.get("error"):
        raise RouteValidationError("A Tesla hibás vagy elutasító választ adott.")
    response = body.get("response", body)
    if not isinstance(response, Mapping) or response.get("error") or response.get("result") is not True:
        raise RouteValidationError("A Tesla nem igazolta vissza az útvonal átvételét.")
