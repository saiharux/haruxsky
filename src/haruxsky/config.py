import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    provider: str = "xai"
    api_key: str
    model: str = "grok-3"
    base_url: str | None = None  # for xai or custom


class PostingConfig(BaseModel):
    enabled: bool = True
    feeds: list[str] = Field(default_factory=list)
    max_posts_per_run: int = 1
    generate_images: bool = False
    max_graphemes: int = 265


class EngagementConfig(BaseModel):
    enabled: bool = True
    replies_per_run: int = 30
    min_likes_for_reply: int = 0
    min_followers: int = 0
    skip_political: bool = True


class SafetyConfig(BaseModel):
    banned_keywords: list[str] = Field(default_factory=list)


class PostPromptConfig(BaseModel):
    prompt: str = Field(..., description="Template for generating posts from articles. Use {title}, {summary}, {style}")


class ReplyPromptConfig(BaseModel):
    prompt: str = Field(..., description="Template for generating replies. Use {post_text}, {author_handle}, {style}")


class PromptsConfig(BaseModel):
    style: str = "thoughtful and engaging with a bit of personality"
    post: PostPromptConfig
    reply: ReplyPromptConfig


class Config(BaseModel):
    bluesky: dict[str, str]  # handle, app_password
    llm: LLMConfig
    posting: PostingConfig = Field(default_factory=PostingConfig)
    engagement: EngagementConfig = Field(default_factory=EngagementConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    prompts: PromptsConfig
    posted_file: str = "posted_articles.txt"
    logging_level: str = "INFO"


DEFAULT_POST_PROMPT = """Write a good, thoughtful post for Bluesky based on this story.

Aim for 160–220 words if making a thread. Make it well-structured with paragraphs and real substance.
Write in a natural, engaging tone.
Do not mention the original source or link to it.

Title: {title}
Summary: {summary}

Return only the full post text."""

DEFAULT_REPLY_PROMPT = """Write a very short, casual, natural, and COMPLETELY NEUTRAL reply (1-2 short sentences max, no emojis) that directly responds to the actual topic or content of this Bluesky post.

Strict rules (must follow):
- Stay 100% apolitical, non-partisan, and safe.
- Make a specific, light observation or brief comment that actually references the topic.
- Vary your reply style.

Post by @{author_handle}: {post_text}

Reply:"""


def load_config(path: str = "config.yaml") -> Config:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}. Run 'haruxsky init' first.")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    # Inject defaults for prompts if not fully provided
    prompts_data = raw.get("prompts", {})
    if "post" not in prompts_data or "prompt" not in prompts_data.get("post", {}):
        prompts_data.setdefault("post", {})["prompt"] = DEFAULT_POST_PROMPT
    if "reply" not in prompts_data or "prompt" not in prompts_data.get("reply", {}):
        prompts_data.setdefault("reply", {})["prompt"] = DEFAULT_REPLY_PROMPT

    raw["prompts"] = prompts_data

    # Handle LLM base_url for xai
    llm_data = raw.get("llm", {})
    if llm_data.get("provider") == "xai" and not llm_data.get("base_url"):
        llm_data["base_url"] = "https://api.x.ai/v1"

    raw["llm"] = llm_data

    # Map logging
    if "logging" in raw:
        raw["logging_level"] = raw["logging"].get("level", "INFO")

    config = Config.model_validate(raw)

    # Load secrets from env if not in config (for api keys etc.)
    if not config.llm.api_key or config.llm.api_key.startswith("your-"):
        env_key = os.getenv("XAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        if env_key:
            config.llm.api_key = env_key

    if not config.bluesky.get("app_password") or config.bluesky["app_password"].startswith("xxxx"):
        env_pass = os.getenv("BSKY_APP_PASSWORD")
        if env_pass:
            config.bluesky["app_password"] = env_pass

    return config
