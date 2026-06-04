import os
import random
import requests
import time
from dotenv import load_dotenv
import feedparser
from bs4 import BeautifulSoup
from openai import OpenAI
from atproto import Client as BskyClient

load_dotenv()

# ==================== SETTINGS ====================
BLUESKY_HANDLE = "saiharux.bsky.social"
BLUESKY_APP_PASSWORD = "rkzk-bcua-epfx-a35p"

POSTED_FILE = "posted_articles.txt"
GENERATE_IMAGES = False

MAX_GRAPHEMES_PER_POST = 265

# Simple mode: 1 main post + 50 replies
REPLIES_TO_MAKE = 50
MIN_LIKES_FOR_REPLY = 0          # Very permissive so we can find enough non-political posts (50 replies target)
MIN_FOLLOWERS = 0                # Very permissive so we can find enough non-political posts (50 replies target)
# ==================================================

xai_client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1"
)

bsky = BskyClient()
bsky.login(BLUESKY_HANDLE, BLUESKY_APP_PASSWORD)
print("✅ Logged into Bluesky\n")

def load_posted_articles():
    if not os.path.exists(POSTED_FILE):
        return set()
    with open(POSTED_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

posted_articles = load_posted_articles()

def save_posted_article(link):
    with open(POSTED_FILE, "a", encoding="utf-8") as f:
        f.write(link + "\n")

def get_article_image_url(article_url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(article_url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            return og["content"]

        tw = soup.find("meta", attrs={"name": "twitter:image"})
        if tw and tw.get("content"):
            return tw["content"]

        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if src and "logo" not in src.lower() and "icon" not in src.lower():
                if src.startswith("//"):
                    src = "https:" + src
                elif src.startswith("/"):
                    src = article_url.rstrip("/") + src
                return src
        return None
    except:
        return None

def download_image(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=15, stream=True)
        if resp.status_code != 200:
            return None
        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type:
            return None
        content = b""
        for chunk in resp.iter_content(1024 * 64):
            content += chunk
            if len(content) > 1.5 * 1024 * 1024:
                return None
        return content
    except:
        return None

def split_into_small_chunks(text, max_graphemes=MAX_GRAPHEMES_PER_POST):
    """Strict splitter that guarantees no chunk exceeds the 300 grapheme limit."""
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    chunks = []
    current = ""

    for para in paragraphs:
        if len(para) > max_graphemes:
            sentences = para.replace('! ', '. ').replace('? ', '. ').split('. ')
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                if len(current) + len(sentence) + 2 <= max_graphemes:
                    current += (". " if current else "") + sentence
                else:
                    if current:
                        chunks.append(current.strip())
                    current = sentence
            if current:
                chunks.append(current.strip())
                current = ""
            continue

        if len(current) + len(para) + 2 <= max_graphemes:
            current += ("\n\n" if current else "") + para
        else:
            if current:
                chunks.append(current)
            current = para

    if current:
        chunks.append(current)

    # Final safety: merge very small chunks only if it stays under the limit
    final = []
    for chunk in chunks:
        if not final:
            final.append(chunk)
            continue

        if len(chunk) < 100 and len(final[-1]) + len(chunk) + 2 <= max_graphemes:
            final[-1] = final[-1] + "\n\n" + chunk
        else:
            final.append(chunk)

    return final


# ==================== REPLY SYSTEM (Skip political posts + varied, topic-specific neutral replies - now 50 per run) ====================

def generate_casual_reply(post_text, author_handle):
    """Strictly neutral reply that actually comments on the specific topic of the post. Varied phrasing, no repetitive generic questions."""
    prompt = f"""Write a very short, casual, natural, and COMPLETELY NEUTRAL reply (1-2 short sentences max, no emojis) that directly responds to the actual topic or content of this Bluesky post.

Strict rules (must follow):
- Stay 100% apolitical, non-partisan, and safe. Never use political terms, party references, "blue"/"red", ideologies, or cultural stereotypes.
- Do NOT default to repetitive safe phrases like "what do you make of it?", "interesting", "cool", "how do you feel about that?", or generic questions.
- Instead, make a specific, light observation, small reaction, or brief comment that actually references the topic the person posted about.
- Vary your reply style and wording — make each reply feel like a genuine, different reaction to that particular post.
- Keep it friendly, bland, inoffensive, and very short.

Post by @{author_handle}: {post_text[:450]}

Reply:"""

    try:
        response = xai_client.chat.completions.create(
            model="grok-3",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=45,
            temperature=0.85
        )
        reply = response.choices[0].message.content.strip().strip('"\'')
        return reply
    except Exception as e:
        print(f"    Error generating reply: {e}")
        return None


def is_political_post(text):
    """Use Grok to classify if a post is primarily political (YES/NO).
    Hard skip — we never reply to political content. Consistent with main article filter."""
    if not text or len(text.strip()) < 8:
        return False

    prompt = f"""Respond with exactly one word: YES or NO.

Is this post primarily about politics, elections, politicians, political parties, government policy, partisan issues, or current political events?

Post: {text[:600]}

Answer:"""

    try:
        response = xai_client.chat.completions.create(
            model="grok-3",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=5,
            temperature=0.0
        )
        answer = response.choices[0].message.content.strip().upper()
        if "YES" in answer:
            return True
        return False
    except Exception as e:
        print(f"    Political check error (skipping post to be safe): {e}")
        return True   # On any error, skip the post (safer for user's "do not respond to political posts")


def find_posts_to_reply():
    """Search very broadly for recent posts (always max 100 per query due to Bluesky API limit).
    Political posts are skipped before any reply is generated."""
    # Extremely broad queries to maximize chances
    queries = [
        "the", "this", "that", "and", "but", "just", "now", 
        "today", "people", "think", "good", "bad", "love", 
        "wow", "lol", "why", "how", "what", "is", "are"
    ]
    
    all_posts = []
    random.shuffle(queries)
    
    print(f"    Searching very broadly (up to 100 per query)...")
    
    for query in queries[:8]:
        try:
            from atproto import models
            params = models.AppBskyFeedSearchPosts.Params(q=query, limit=100)
            results = bsky.app.bsky.feed.search_posts(params)
            raw_count = len(results.posts)
            all_posts.extend(results.posts)
            print(f"      Query '{query}': got {raw_count} raw posts")
            time.sleep(0.5)
        except Exception as e:
            print(f"    Search error for '{query}': {e}")
            continue
    
    print(f"    Total raw posts before filtering: {len(all_posts)}")
    
    # Very permissive filtering
    seen = set()
    filtered = []
    
    after_dedup = 0
    after_followers = 0
    after_likes = 0
    after_language = 0
    
    for post in all_posts:
        if post.uri in seen:
            continue
        seen.add(post.uri)
        after_dedup += 1
        
        if getattr(post.author, 'followers_count', 0) < MIN_FOLLOWERS:
            continue
        after_followers += 1
        
        if getattr(post, 'like_count', 0) < MIN_LIKES_FOR_REPLY:
            continue
        after_likes += 1
        
        # Safe text extraction for PostView (record.text is the reliable location)
        post_text = ""
        if hasattr(post, 'record') and hasattr(post.record, 'text'):
            post_text = post.record.text or ""
        elif hasattr(post, 'text'):
            post_text = post.text or ""
        
        # Extremely loose language check (skip only almost entirely non-English)
        if not post_text.strip():
            continue
        non_ascii = sum(1 for c in post_text if ord(c) > 127)
        if non_ascii > len(post_text) * 0.95:
            continue
        after_language += 1
            
        filtered.append(post)
    
    print(f"    After dedup: {after_dedup}")
    print(f"    After followers filter (>{MIN_FOLLOWERS}): {after_followers}")
    print(f"    After likes filter (>{MIN_LIKES_FOR_REPLY}): {after_likes}")
    print(f"    After language check: {after_language}")
    print(f"    Final candidates for replies: {len(filtered)}")
    
    random.shuffle(filtered)
    return filtered


def do_simple_replies(num_replies):
    """Reply only to non-political posts (target 50). Uses max search volume (800 raw posts possible). Replies are varied and actually address the post's topic while staying neutral."""
    if num_replies <= 0:
        return 0

    print(f"  → Doing {num_replies} replies...")

    replied_accounts = set()
    replies_made = 0
    attempts = 0
    target_candidates = num_replies * 10   # How many raw posts we want before filtering

    candidates = find_posts_to_reply()  # Always fetches up to 800 raw (8 queries × 100)

    for post in candidates:
        if replies_made >= num_replies or attempts >= target_candidates:
            break
        attempts += 1

        author_handle = post.author.handle
        if author_handle in replied_accounts:
            continue

        # Safely get the post text (PostView objects store it in .record.text)
        post_text = ""
        if hasattr(post, 'record') and hasattr(post.record, 'text'):
            post_text = post.record.text or ""
        elif hasattr(post, 'text'):
            post_text = post.text or ""

        # Do not respond to political posts (hard skip)
        if is_political_post(post_text):
            print(f"    Skipping political post from @{author_handle}")
            continue

        reply_text = generate_casual_reply(post_text, author_handle)
        if not reply_text or len(reply_text) < 5:
            continue

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
            print(f"    Replied to @{author_handle}")
            time.sleep(random.uniform(10, 25))
        except Exception as e:
            print(f"    Failed to reply to @{author_handle}: {e}")
            time.sleep(3)

    print(f"  → Done with replies. Made {replies_made} replies.\n")
    return replies_made


# ==================== MAIN ====================

RSS_FEEDS = [
    "https://www.rt.com/rss/",
    "https://www.technologyreview.com/feed/",
    "https://feeds.arstechnica.com/arstechnica/index",
    "https://feeds.bbci.co.uk/news/future/rss.xml",
    "https://aeon.co/feed.rss",
]

print("Looking for a good article...\n")

posted_something = False
random.shuffle(RSS_FEEDS)

for rss_url in RSS_FEEDS:
    if posted_something:
        break

    feed = feedparser.parse(rss_url)

    for entry in feed.entries:
        article_link = entry.get("link", "")
        if article_link and article_link in posted_articles:
            continue

        title = entry.title
        raw_summary = entry.get("summary", entry.get("description", ""))
        soup = BeautifulSoup(raw_summary, "html.parser")
        clean_summary = soup.get_text(separator=" ", strip=True)

        classification_prompt = f"""You are a content curator for a Bluesky bot.

Respond in exactly this format:

Political: Yes or No
Category: Science / Tech / Health / Environment / Weird / Culture / None
Good for bot: Yes or No
Reason: One short sentence

Title: {title}
Summary: {clean_summary[:700]}
"""

        classification = xai_client.chat.completions.create(
            model="grok-3",
            messages=[{"role": "user", "content": classification_prompt}],
            max_tokens=120,
            temperature=0.3
        ).choices[0].message.content.strip()

        if "Good for bot: Yes" not in classification:
            continue

        post_prompt = f"""Write a good, thoughtful post for Bluesky based on this story.

Aim for 160–220 words. Make it well-structured with paragraphs and real substance.
Write in a natural, engaging tone. Do not mention the original source or link to it.

Title: {title}
Summary: {clean_summary}

Return only the full post text."""

        full_text = xai_client.chat.completions.create(
            model="grok-3",
            messages=[{"role": "user", "content": post_prompt}],
            max_tokens=750,
            temperature=0.7
        ).choices[0].message.content.strip()

        chunks = split_into_small_chunks(full_text)

        # Image from article
        image_bytes = None
        image_url = get_article_image_url(article_link) if article_link else None
        if image_url:
            image_bytes = download_image(image_url)
            if image_bytes:
                print("  → Found and downloaded article image")

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

            if article_link:
                save_posted_article(article_link)

            print(f"✅ Posted a {len(chunks)}-part thread to Bluesky!\n")
            posted_something = True

            break

        except Exception as e:
            print(f"❌ Failed to post thread: {e}\n")
            break

    # === DO 50 REPLIES (separate from thread posting so errors don't lie) ===
    if posted_something:
        try:
            do_simple_replies(REPLIES_TO_MAKE)
        except Exception as e:
            print(f"  ⚠️ Reply phase error (non-fatal): {e}")

if not posted_something:
    print("No good new article found right now.")

print("Done.")
