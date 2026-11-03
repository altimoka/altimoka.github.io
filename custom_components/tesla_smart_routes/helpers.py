from __future__ import annotations

import urllib.parse


def waypoint_place_url(waypoint: dict) -> str:
    return (
        "https://www.google.com/maps/search/?api=1"
        f"&query={urllib.parse.quote_plus(waypoint['label'])}"
        f"&query_place_id={waypoint['place_id']}"
    )


def build_maps_url(waypoints: list[dict]) -> str | None:
    if not waypoints:
        return None
    destination = waypoints[-1]
    intermediates = waypoints[:-1]
    url = (
        "https://www.google.com/maps/dir/?api=1"
        "&origin=Current+Location"
        f"&destination={urllib.parse.quote_plus(destination['label'])}"
        f"&destination_place_id={destination['place_id']}"
        "&travelmode=driving"
    )
    if intermediates:
        wp_ids = "|".join(w["place_id"] for w in intermediates)
        url += f"&waypoints={wp_ids}&waypoint_place_ids={wp_ids}"
    return url
