"""
HaruxSky CLI
Main entry point for the Bluesky automation tool.
"""

import os
import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich import print as rprint

from .config import load_config
from .llm import LLMClient
from .bsky import BskyClientWrapper
from .poster import run_posting
from .engager import run_engagement

app = typer.Typer(
    name="haruxsky",
    help="Customizable AI Bluesky automation. Make it sound like you.",
    add_completion=False,
)
console = Console()


@app.command()
def init():
    """Create a starter config.yaml with powerful customization options."""
    target = Path("config.yaml")

    if target.exists():
        rprint("[yellow]config.yaml already exists. Not overwriting.[/yellow]")
        rprint("You can still edit it. The [prompts] section is where the magic happens.")
        return

    # Self-contained good default (so it works even when installed via pip)
    default_config = '''# HaruxSky config - customize the prompts section to match your voice!

bluesky:
  handle: "yourhandle.bsky.social"
  app_password: "your-app-password-here"   # from https://bsky.app/settings/app-passwords

llm:
  provider: "xai"          # xai | openai
  api_key: "your-api-key"
  model: "grok-3"

posting:
  enabled: true
  feeds:
    - "https://www.technologyreview.com/feed/"
    - "https://feeds.arstechnica.com/arstechnica/index"
  max_posts_per_run: 1
  generate_images: false
  max_graphemes: 265

engagement:
  enabled: true
  replies_per_run: 20
  min_likes_for_reply: 1
  skip_political: true

prompts:
  style: "thoughtful, curious, and slightly witty like a well-read friend"

  post:
    prompt: |
      Write a good, thoughtful Bluesky post (or short thread) based on this story.
      Style: {style}
      Keep it natural and engaging. Use paragraphs. Do not mention the source.
      Title: {title}
      Summary: {summary}
      Return only the post text.

  reply:
    prompt: |
      Write a short, natural, on-topic reply (1-2 sentences).
      Style: {style}
      Be specific to the post content. Stay safe and apolitical.
      Post by @{author_handle}: {post_text}
      Reply:
'''

    target.write_text(default_config, encoding="utf-8")
    rprint("[green]Created config.yaml with built-in customization examples.[/green]")
    rprint("Edit the [prompts] section (especially 'style' and the prompt templates) to make it sound like you.")
    rprint("Then: [bold]haruxsky run --mode post,engage --dry-run[/bold]")


@app.command()
def run(
    mode: str = typer.Option("post,engage", help="Comma separated: post,engage, or both"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Don't actually post or reply"),
    config_path: str = typer.Option("config.yaml", "--config", "-c", help="Path to config file"),
):
    """Run the automation (posting and/or engagement) using your custom prompts."""
    try:
        cfg = load_config(config_path)
    except Exception as e:
        rprint(f"[red]Failed to load config: {e}[/red]")
        raise typer.Exit(1)

    rprint(f"[yellow]Running in mode: {mode} (dry_run={dry_run})[/yellow]")

    # Setup clients
    llm = LLMClient(cfg.llm)
    bsky = BskyClientWrapper(cfg)

    modes = [m.strip().lower() for m in mode.split(",")]

    posted = False
    if "post" in modes or "posting" in modes:
        posted = run_posting(cfg, llm, bsky, dry_run=dry_run)

    if "engage" in modes or "replies" in modes or "engagement" in modes:
        if posted:
            # small pause between phases like original
            import time
            time.sleep(3)
        run_engagement(cfg, llm, bsky, dry_run=dry_run)

    rprint("[green]Done.[/green]")


@app.command()
def version():
    """Show version."""
    from . import __version__
    rprint(f"HaruxSky v{__version__}")


@app.command()
def gui():
    """Launch the graphical interface (the real program experience)."""
    try:
        from .gui import main as gui_main
        gui_main()
    except ImportError as e:
        rprint(f"[red]GUI dependencies not installed. Run: pip install 'haruxsky[gui]' or install customtkinter.[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()

