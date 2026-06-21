from urllib.parse import urlparse

from lilwman.domain.feed_entities import FeedSubscription
from lilwman.domain.feed_ports import FeedRepository

_BRIDGES: dict[str, str] = {
    "instagram":  "Instagram&username={account}",
    "tiktok":     "TikTok&username={account}",
    "twitter":    "Twitter&u={account}",
    "reddit":     "Reddit&r={account}",
    "youtube":    "YouTube&channel={account}",
    "twitch":     "Twitch&channel={account}",
    "hackernews": "HackerNews&category={account}",
}

SUPPORTED_PLATFORMS: set[str] = set(_BRIDGES.keys())


def build_rss_url(rss_bridge_host: str, platform: str, account: str) -> str:
    bridge_params = _BRIDGES[platform].format(account=account)
    return f"{rss_bridge_host}/?action=display&bridge={bridge_params}&format=Atom"


class AddFeedUseCase:
    def __init__(self, repo: FeedRepository, rss_bridge_url: str) -> None:
        self._repo = repo
        self._rss_bridge_url = rss_bridge_url

    async def execute(
        self, channel_id: str, platform: str, account_name: str
    ) -> FeedSubscription | None:
        rss_url = build_rss_url(self._rss_bridge_url, platform, account_name)
        return await self._repo.save(channel_id, platform, account_name, rss_url)

    async def execute_custom_url(
        self, channel_id: str, rss_url: str
    ) -> FeedSubscription | None:
        account_name = urlparse(rss_url).netloc or rss_url
        return await self._repo.save(channel_id, "custom", account_name, rss_url)
