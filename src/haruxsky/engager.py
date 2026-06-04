import random
import time

from .config import Config
from .llm import LLMClient
from .bsky import BskyClientWrapper
from .utils import format_prompt


def is_political_post(text: str, llm: LLMClient, config: Config, log_func=print) -> bool:
    """Use LLM to classify if a post is primarily political."""
    if not text or len(text.strip()) < 8:
        return False

    # We can make this prompt customizable too in future, for now use strong default
    prompt = f"""Respond with exactly one word: YES or NO.

Is this post primarily about politics, elections, politicians, political parties, government policy, partisan issues, or current political events?

Post: {text[:600]}

Answer:"""

    try:
        answer = llm.classify(prompt).strip().upper()
        return "YES" in answer
    except Exception as e:
        log_func(f"    Political check error (skipping post to be safe): {e}")
        return True  # safer to skip on error


def generate_reply(post_text: str, author_handle: str, llm: LLMClient, config: Config, log_func=print) -> str | None:
    """Generate a reply using the user-customizable prompt."""
    prompt = format_prompt(
        config.prompts.reply.prompt,
        post_text=post_text[:450],
        author_handle=author_handle,
        style=config.prompts.style,
    )

    try:
        reply = llm.generate(prompt, max_tokens=60, temperature=0.85)
        reply = reply.strip().strip('"\'')
        return reply if len(reply) > 3 else None
    except Exception as e:
        log_func(f"    Error generating reply: {e}")
        return None


def find_posts_to_reply(bsky: BskyClientWrapper, config: Config, log_func=print) -> list:
    """Broad search for candidate posts to reply to."""
    queries = [
        "the", "this", "that", "and", "but", "just", "now",
        "today", "people", "think", "good", "bad", "love",
        "wow", "lol", "why", "how", "what", "is", "are"
    ]
    random.shuffle(queries)

    all_posts = []
    log_func(f"    Searching very broadly for reply candidates...")

    for query in queries[:8]:
        try:
            posts = bsky.search_posts(query, limit=100)
            all_posts.extend(posts)
            log_func(f"      Query '{query}': got {len(posts)} raw posts")
            time.sleep(0.4)
        except Exception as e:
            log_func(f"    Search error for '{query}': {e}")
            continue

    log_func(f"    Total raw posts before filtering: {len(all_posts)}")

    seen = set()
    filtered = []
    for post in all_posts:
        if post.uri in seen:
            continue
        seen.add(post.uri)

        if getattr(post.author, 'followers_count', 0) < config.engagement.min_followers:
            continue
        if getattr(post, 'like_count', 0) < config.engagement.min_likes_for_reply:
            continue

        # text extraction
        post_text = ""
        if hasattr(post, 'record') and hasattr(post.record, 'text'):
            post_text = post.record.text or ""
        elif hasattr(post, 'text'):
            post_text = post.text or ""

        if not post_text.strip():
            continue

        # loose language filter
        non_ascii = sum(1 for c in post_text if ord(c) > 127)
        if non_ascii > len(post_text) * 0.95:
            continue

        filtered.append(post)

    log_func(f"    Final candidates for replies after filters: {len(filtered)}")
    random.shuffle(filtered)
    return filtered


def run_engagement(config: Config, llm: LLMClient, bsky: BskyClientWrapper, dry_run: bool = False, stop_event=None, log_func=print) -> int:
    """Run reply engagement using customizable prompts."""
    log_func("REPLIES PHASE: Starting to search for recent posts on Bluesky (using broad queries to find 'random' ones) and generate natural replies using your custom prompts.")
    if not config.engagement.enabled:
        log_func("  Engagement is disabled in config.")
        return 0

    num_replies = config.engagement.replies_per_run
    if num_replies <= 0:
        return 0

    log_func(f"  → Doing up to {num_replies} replies...")

    log_func("    Searching for random recent posts on Bluesky to reply to (using broad queries to simulate natural discovery)...")
    candidates = find_posts_to_reply(bsky, config, log_func)
    replied_accounts = set()
    replies_made = 0

    for post in candidates:
        if replies_made >= num_replies:
            break
        if stop_event and stop_event.is_set():
            log_func("  Stop requested, exiting engagement phase.")
            break

        author_handle = post.author.handle
        if author_handle in replied_accounts:
            continue

        post_text = ""
        if hasattr(post, 'record') and hasattr(post.record, 'text'):
            post_text = post.record.text or ""
        elif hasattr(post, 'text'):
            post_text = post.text or ""

        if config.engagement.skip_political and is_political_post(post_text, llm, config, log_func):
            log_func(f"    Skipping political post from @{author_handle}")
            continue

        log_func(f"    Generating natural reply for post by @{author_handle} using your custom prompt...")
        reply_text = generate_reply(post_text, author_handle, llm, config, log_func)
        if not reply_text or len(reply_text) < 5:
            log_func(f"    -> LLM returned empty/short reply, skipping.")
            continue

        if dry_run:
            log_func(f"[DRY RUN] Would reply to @{author_handle}: {reply_text[:80]}...")
            replied_accounts.add(author_handle)
            replies_made += 1
            if stop_event and stop_event.is_set():
                log_func("  Stop requested.")
            continue
        else:
            log_func(f"    Posting reply to @{author_handle}...")

        try:
            bsky.send_post(
                text=reply_text,
                reply_to={
                    "root": {"uri": post.uri, "cid": post.cid},
                    "parent": {"uri": post.uri, "cid": post.cid}
                }
            )
            replied_accounts.add(author_handle)
            replies_made += 1
            log_func(f"    Replied to @{author_handle}")
            time.sleep(random.uniform(8, 20))
        except Exception as e:
            log_func(f"    Failed to reply to @{author_handle}: {e}")
            time.sleep(2)

    log_func(f"  → Done with replies. Made {replies_made} replies.\n")
    return replies_made
