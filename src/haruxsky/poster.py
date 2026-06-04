import feedparser
from bs4 import BeautifulSoup
import time
import random

from .config import Config
from .llm import LLMClient
from .bsky import BskyClientWrapper
from .utils import (
    split_into_small_chunks,
    get_article_image_url,
    download_image,
    load_posted_articles,
    save_posted_article,
    format_prompt,
)


def run_posting(config: Config, llm: LLMClient, bsky: BskyClientWrapper, dry_run: bool = False, stop_event=None, log_func=print, max_posts: int = 1) -> int:
    """Run the article posting logic using customizable prompts. Posts up to max_posts good articles."""
    log_func("POSTING PHASE: Starting to search the provided RSS feeds for articles and generate posts using your custom prompts.")
    if not config.posting.enabled:
        log_func("  Posting is disabled in config.")
        return 0

    posted_file = config.posted_file
    posted_articles = load_posted_articles(posted_file)
    posted_count = 0

    feeds = config.posting.feeds or [
        # sensible defaults if none provided
        "https://www.technologyreview.com/feed/",
        "https://feeds.arstechnica.com/arstechnica/index",
    ]

    log_func("Looking for good articles...\n")
    random.shuffle(feeds)
    log_func(f"  Will check {len(feeds)} RSS feeds for new articles (target: up to {max_posts}).")

    for rss_url in feeds:
        if posted_count >= max_posts:
            break
        if stop_event and stop_event.is_set():
            log_func("  Stop requested, exiting posting phase.")
            break

        log_func(f"  Fetching and parsing RSS feed: {rss_url}")
        feed = feedparser.parse(rss_url)
        log_func(f"    Found {len(feed.entries)} entries in feed.")

        for entry in feed.entries:
            if posted_count >= max_posts:
                break
            article_link = entry.get("link", "")
            if article_link and article_link in posted_articles:
                continue

            title = entry.title
            raw_summary = entry.get("summary", entry.get("description", ""))
            soup = BeautifulSoup(raw_summary, "html.parser")
            clean_summary = soup.get_text(separator=" ", strip=True)

            log_func(f"    Considering article: {title[:80]}...")

            # --- Classification (can be made fully custom later) ---
            classification_prompt = f"""You are a content curator for a Bluesky bot.

Respond in exactly this format:
Political: Yes or No
Category: Science / Tech / Health / Environment / Weird / Culture / None
Good for bot: Yes or No
Reason: One short sentence

Title: {title}
Summary: {clean_summary[:700]}
"""
            classification = llm.classify(classification_prompt)
            log_func(f"    LLM classification: {classification.strip()[:100]}...")

            if "Good for bot: Yes" not in classification:
                log_func("    -> Rejected by classification filter.")
                continue
            if stop_event and stop_event.is_set():
                log_func("  Stop requested, exiting posting phase.")
                break

            log_func("    -> Article passed filters. Generating post with LLM using your custom prompt...")

            # --- Custom post generation ---
            post_prompt = format_prompt(
                config.prompts.post.prompt,
                title=title,
                summary=clean_summary,
                style=config.prompts.style,
            )

            full_text = llm.generate(
                post_prompt,
                max_tokens=750,
                temperature=0.7,
            )

            if not full_text:
                log_func("    -> LLM returned empty post text.")
                continue

            log_func(f"    Generated post text (preview): {full_text[:150]}...")

            chunks = split_into_small_chunks(full_text, config.posting.max_graphemes)

            # Image
            image_bytes = None
            if config.posting.generate_images and article_link:
                image_url = get_article_image_url(article_link)
                if image_url:
                    image_bytes = download_image(image_url)
                    if image_bytes:
                        log_func("  → Found and downloaded article image")

            if dry_run:
                log_func(f"[DRY RUN] Would post {len(chunks)}-part thread about: {title[:60]}...")
                log_func(f"First chunk preview: {chunks[0][:150]}...")
                posted_count += 1
                if stop_event and stop_event.is_set():
                    log_func("  Stop requested.")
                if posted_count >= max_posts:
                    break
                continue
            else:
                log_func("    Actually posting the thread to Bluesky...")

            try:
                first_text = f"1/{len(chunks)}\n\n{chunks[0]}"

                if image_bytes:
                    root = bsky.send_image(
                        text=first_text,
                        image=image_bytes,
                        image_alt=title[:100]
                    )
                else:
                    root = bsky.send_post(text=first_text)

                root_ref = {"uri": root.uri, "cid": root.cid}
                parent_ref = root_ref

                for i, chunk in enumerate(chunks[1:], start=2):
                    reply = bsky.send_post(
                        text=f"{i}/{len(chunks)}\n\n{chunk}",
                        reply_to={"root": root_ref, "parent": parent_ref}
                    )
                    parent_ref = {"uri": reply.uri, "cid": reply.cid}
                    time.sleep(random.uniform(2, 5))

                if article_link:
                    save_posted_article(article_link, posted_file)

                log_func(f"✅ Posted a {len(chunks)}-part thread to Bluesky!\n")
                posted_count += 1
                if posted_count >= max_posts:
                    break

            except Exception as e:
                log_func(f"❌ Failed to post thread: {e}\n")
                break

    log_func(f"  → Done with posting. Made {posted_count} post(s).")
    return posted_count
