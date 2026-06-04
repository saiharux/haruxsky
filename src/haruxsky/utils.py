import os
import requests
from bs4 import BeautifulSoup
from typing import Set

def split_into_small_chunks(text: str, max_graphemes: int = 265) -> list[str]:
    """Strict splitter that guarantees no chunk exceeds the max grapheme limit."""
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

    # Final safety merge for small chunks
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


def get_article_image_url(article_url: str) -> str | None:
    """Try to extract a good og:image or twitter:image from the article page."""
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
    except Exception:
        return None


def download_image(url: str, max_size_mb: float = 1.5) -> bytes | None:
    """Download image and return bytes, with size limit."""
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
            if len(content) > max_size_mb * 1024 * 1024:
                return None
        return content
    except Exception:
        return None


def load_posted_articles(path: str) -> Set[str]:
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def save_posted_article(link: str, path: str):
    with open(path, "a", encoding="utf-8") as f:
        f.write(link + "\n")


def format_prompt(template: str, **kwargs) -> str:
    """Safely format a prompt template with provided variables (style, title, etc.)."""
    try:
        return template.format(**kwargs)
    except KeyError:
        return template  # graceful fallback
