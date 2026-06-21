from datetime import datetime, timezone
from lilwman.domain.feed_entities import FeedSubscription, FeedPost


def test_feed_subscription_fields():
    now = datetime.now(timezone.utc)
    sub = FeedSubscription(
        id=1,
        channel_id="111222333",
        platform="instagram",
        account_name="testuser",
        rss_url="http://localhost:3000/?action=display&bridge=Instagram&username=testuser&format=Atom",
        created_at=now,
    )
    assert sub.id == 1
    assert sub.platform == "instagram"
    assert sub.account_name == "testuser"
    assert sub.rss_url.startswith("http://localhost:3000")


def test_feed_post_defaults():
    now = datetime.now(timezone.utc)
    post = FeedPost(
        guid="abc123",
        title="Test Post",
        url="https://instagram.com/p/abc123",
        description="A test post",
        author="testuser",
        published_at=now,
    )
    assert post.images == []
    assert post.video_url is None


def test_feed_post_with_images():
    now = datetime.now(timezone.utc)
    post = FeedPost(
        guid="abc123",
        title="Carousel",
        url="https://instagram.com/p/abc123",
        description="Multiple images",
        author="testuser",
        published_at=now,
        images=["https://example.com/img1.jpg", "https://example.com/img2.jpg"],
    )
    assert len(post.images) == 2
    assert post.video_url is None


def test_feed_post_with_video():
    now = datetime.now(timezone.utc)
    post = FeedPost(
        guid="v1",
        title="Reel",
        url="https://instagram.com/reel/v1",
        description="A reel",
        author="testuser",
        published_at=now,
        video_url="https://cdn.example.com/video.mp4",
    )
    assert post.video_url == "https://cdn.example.com/video.mp4"
    assert post.images == []
