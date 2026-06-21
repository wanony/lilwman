from typing import Callable

_FIX_URLS: dict[str, Callable[[str], str]] = {
    "twitter":   lambda u: u.replace("twitter.com", "vxtwitter.com").replace("x.com", "vxtwitter.com"),
    "instagram": lambda u: u.replace("instagram.com", "ddinstagram.com"),
    "tiktok":    lambda u: u.replace("tiktok.com", "vxtiktok.com"),
}

_COLOURS: dict[str, int] = {
    "instagram":  0xE1306C,
    "tiktok":     0x010101,
    "twitter":    0x1DA1F2,
    "reddit":     0xFF4500,
    "youtube":    0xFF0000,
    "twitch":     0x9146FF,
    "hackernews": 0xFF6600,
    "custom":     0x5865F2,
}


def get_fix_url(platform: str, url: str) -> str | None:
    transform = _FIX_URLS.get(platform)
    return transform(url) if transform else None


def get_platform_colour(platform: str) -> int:
    return _COLOURS.get(platform, 0x5865F2)
