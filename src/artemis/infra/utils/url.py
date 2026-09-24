"""URL helpers shared across infra and API layers."""


def normalize_nav_url(raw: str) -> str:
    """``baidu.com`` → ``https://baidu.com``; empty input → ``\"\"``."""
    t = raw.strip()
    if not t:
        return ""
    lower = t.lower()
    if "://" in lower:
        if lower.startswith(("http://", "https://")):
            return t
        return ""
    return f"https://{t}"
