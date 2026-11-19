from urllib.parse import urlsplit


def media_url(value: object, hosts: set[str]) -> str | None:
    if isinstance(value, str) and len(value) <= 1000:
        try:
            url = urlsplit(value)
            if url.scheme == "https" and url.netloc in hosts:
                return value
        except ValueError:
            pass
    return None


def driver_headshot(headshots: object, car_number: str) -> str | None:
    if not isinstance(headshots, dict):
        return None
    return media_url(
        headshots.get(car_number),
        {"www.formula1.com", "media.formula1.com", "formula1.com"},
    )
