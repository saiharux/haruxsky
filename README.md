# HaruxSky — Real Desktop Program for Bluesky (Post + Engage)

**A dead-simple standalone Windows app (HaruxSky.exe) that posts thoughtful article threads from your RSS feeds and naturally replies to random people on Bluesky — with full live visibility of everything it does.**

Double-click the .exe, enter your Bluesky handle + app password + LLM API key, and the program "loads up" into a clean GUI. Edit your article sources, choose exactly how many articles to post and how many replies to make, hit Run, and watch the detailed live log as it does the real work (fetching, LLM thinking, posting threads, etc.).

No hidden magic. Everything is transparent. Prompts are high-quality internal defaults tuned for safe, thoughtful, non-political content. 

Built for creators who want leverage without babysitting or risking their account. Open source (MIT).

## What it actually does (the real program)

- **Article posting phase**: You give it RSS feeds (Technology Review, Ars Technica, Wikipedia Random, your own blogs, etc.). It fetches them, uses the LLM to classify (skips political/low-quality), generates a natural multi-part thread from a good article using strong internal prompts, optionally grabs the article's main image, and posts it to Bluesky. You choose exactly how many articles per run (1, 2, 3...).
- **Reply engagement phase**: Then it does broad searches across Bluesky ("the", "and", "why", "today" etc.) to simulate natural discovery, filters (followers, likes, skips political via LLM), generates short natural neutral replies with the LLM, and posts them to random recent posts by other people.
- **Zero auto-reply to your own posts**: After posting an article it moves straight to replying to *other people*.
- **Full live visibility**: Big "Current activity" label + scrolling Live Activity Log that shows every single step in real time (fetching exact URL you typed, "Considering article: ...", full LLM classification output, "Generating post with LLM using your custom prompt...", preview of generated text, "✅ Posted a 6-part thread", "Replied to @someone", etc.). The background worker thread is actually running the real code.
- **Dry run mode**: Preview everything without posting.
- **Image attachment**: Free, scrapes og:image / twitter:image or first good image from the article page.
- **True LOG OUT**: The "Log Out / Reconfigure" button completely resets the app back to the initial login screen (no manual delete files or restart needed).
- **Persistent settings**: Everything saved in %LOCALAPPDATA%\HaruxSky\config.yaml (you can edit the feeds list by hand too).

The prompts themselves are now high-quality baked-in defaults (thoughtful, neutral, substance-focused, strictly apolitical guardrails). The old editable prompt boxes were removed to keep the UI clean and focused ("just the center stuff").

Strong safety: political skip on both posting and replies, duplicate protection, rate limiting, etc.

## The Real Program (HaruxSky.exe) — Recommended

This is the main deliverable: a single ~38 MB Windows executable. No Python install, no terminal.

1. Download `HaruxSky.exe` (from Releases once published, or build it yourself — see below).
2. Double-click it.
3. On first run: enter your Bluesky handle (e.g. yourname.bsky.social), an App Password (create at bsky.app/settings/app-passwords), and your LLM API key (xAI/Grok recommended — get at console.x.ai).
4. It shows a loading/spinner screen, then "loads up further" into the full GUI.
5. **Customize**:
   - Article Sources (RSS feeds) — one URL per line. Supports any RSS (tech, blogs, Wikipedia Special:Random, etc.).
   - Check "Post articles" and/or "Send replies".
   - Set **Articles to post:** (e.g. 1 or 2 or 3) and **Replies to send:** (e.g. 5–20).
   - Dry Run (recommended first) or real posting.
   - "Attach image from article if available".
6. Hit **▶ Run Now**.
7. Watch the live log fill with every detail as the background thread does the actual work.
8. When done it says "Run finished successfully." Your settings are auto-saved.

The **LOG OUT / Reconfigure Account** button in the header fully resets everything back to the login screen.

### Building the .exe yourself (for transparency / updates)

```bash
git clone https://github.com/saiharux/haruxsky
cd haruxsky
pip install -e ".[build]"
python build_exe.py
```

The exe lands in `dist/HaruxSky.exe`. Close any running copy of the program before building (the exe file gets locked while open).

The CLI (`haruxsky` and `haruxsky-gui` commands) still exists in the source for power users who want to script or run on non-Windows.

See [examples/config.example.yaml](examples/config.example.yaml) for the full config schema (the GUI only exposes the most useful parts).

## Requirements

- Python 3.10+
- Bluesky account + App Password (never use your main password)
- LLM API key (xAI/Grok recommended for best results and currently best supported; OpenAI, Claude, etc. will be supported)

## Why HaruxSky?

Most Bluesky automation feels fake or risky. HaruxSky is built for people who want a real, visible, safe presence:

- You see **everything** happening in the log (no "it says running but nothing is happening").
- You control the exact volume (number of articles + replies).
- Strong built-in safety (political filtering on both posting and replies, no self-reply loops).
- Real multi-part threads with optional article images.
- Natural random discovery for replies (broad queries + filters) instead of spamming the same people.
- True standalone .exe that feels like a proper desktop program.

The prompts are intentionally not user-editable in the GUI anymore — they are carefully tuned good defaults so the output stays thoughtful, neutral, and high-signal.

## Monetization / Support

This is open source under MIT. Ways to support:

- ⭐ Star the repo
- Sponsor on GitHub: https://github.com/sponsors/saiharux
- (Future) Pro hosted version, extra personas, priority support, etc. (TBA)

## Roadmap (rough)

- [x] Real visible GUI + live logging + true LOG OUT reset
- [x] User-chosen article count + reply count
- [ ] Releases with pre-built .exe attached
- [ ] Better image handling / more sources
- [ ] Scheduling helper (Task Scheduler / simple GUI timer)
- [ ] Optional self-hosted web version
- [ ] More LLM providers

## Contributing

Ideas, bug reports, and PRs welcome. Open an issue first for bigger changes.

## License

MIT License — see LICENSE file.

## Disclaimer

Use responsibly and follow Bluesky's rules. You are responsible for what your account posts and replies. The built-in filters help a lot but are not 100% foolproof.

---

Made for creators who want real leverage on Bluesky without losing their voice or their account.

Bluesky: @saiharux.bsky.social (and the tool account once set up)
