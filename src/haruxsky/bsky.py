from atproto import Client as BskyClient
from atproto import models
from .config import Config


class BskyClientWrapper:
    def __init__(self, config: Config):
        self.client = BskyClient()
        handle = config.bluesky["handle"]
        app_password = config.bluesky["app_password"]
        self.client.login(handle, app_password)
        print(f"✅ Logged into Bluesky as @{handle}")

    def send_post(self, text: str, reply_to: dict | None = None):
        if reply_to:
            return self.client.send_post(text=text, reply_to=reply_to)
        return self.client.send_post(text=text)

    def send_image(self, text: str, image: bytes, image_alt: str = "", reply_to: dict | None = None):
        # atproto expects upload first? Simplified: use send_image if available
        # For robustness we'll use the basic send_post with image for now.
        # The original used send_image.
        try:
            return self.client.send_image(
                text=text,
                image=image,
                image_alt=image_alt,
                reply_to=reply_to,
            )
        except Exception:
            # Fallback: post text only if image fails
            print("  Warning: image upload failed, posting text only")
            return self.send_post(text=text, reply_to=reply_to)

    def search_posts(self, query: str, limit: int = 100):
        params = models.AppBskyFeedSearchPosts.Params(q=query, limit=limit)
        results = self.client.app.bsky.feed.search_posts(params)
        return results.posts
