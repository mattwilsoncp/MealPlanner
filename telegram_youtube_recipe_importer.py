#!/usr/bin/env python3
import argparse
import os
import re
import sys
import time
from pathlib import Path
from typing import Iterable

import requests

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "meal_planner.settings")

import django

django.setup()

from youtube_importer import (
    DEFAULT_MODEL,
    extract_video_id,
    get_household,
    get_openrouter_client,
    get_video_metadata,
    parse_recipe_with_llm,
    transcribe_youtube,
    upsert_recipe,
    write_transcript_log,
)

YOUTUBE_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com/watch\?v=[^\s&]+(?:[^\s]*)?|youtu\.be/[^\s?&]+(?:[^\s]*)?|youtube\.com/shorts/[^\s?&]+(?:[^\s]*)?)",
    re.IGNORECASE,
)


class TelegramRecipeImporter:
    def __init__(
        self,
        bot_token: str,
        household_id: int | None,
        default_model: str,
        allowed_chat_names: set[str] | None,
        poll_interval: float,
    ):
        self.bot_token = bot_token.strip()
        if not self.bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is required for Telegram mode")
        self.household_id = household_id
        self.default_model = default_model
        self.allowed_chat_names = {name.strip() for name in (allowed_chat_names or set()) if name.strip()}
        self.poll_interval = poll_interval
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.offset = None

    def run(self) -> int:
        print("Telegram importer started")
        while True:
            try:
                updates = self._get_updates()
                for update in updates:
                    self._handle_update(update)
            except KeyboardInterrupt:
                print("Stopping Telegram importer")
                return 0
            except Exception as exc:
                print(f"Telegram polling error: {exc}", file=sys.stderr)
                time.sleep(max(self.poll_interval, 2.0))

    def _get_updates(self) -> list[dict]:
        params = {"timeout": 30}
        if self.offset is not None:
            params["offset"] = self.offset
        response = requests.get(f"{self.base_url}/getUpdates", params=params, timeout=45)
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram getUpdates failed: {payload}")
        return payload.get("result", [])

    def _handle_update(self, update: dict) -> None:
        update_id = update.get("update_id")
        if isinstance(update_id, int):
            self.offset = update_id + 1

        message = update.get("message") or update.get("channel_post") or {}
        if not message:
            return

        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        chat_title = str(chat.get("title") or chat.get("username") or "").strip()
        if self.allowed_chat_names and chat_title not in self.allowed_chat_names:
            return

        text = self._extract_message_text(message)
        if not text:
            return

        urls = list(self._extract_youtube_urls(text))
        if not urls:
            return

        requested_model = self._extract_model_override(text) or self.default_model
        title_override = self._extract_title_override(text)

        for url in urls:
            try:
                recipe = import_recipe_from_url(
                    url=url,
                    model=requested_model,
                    household_id=self.household_id,
                    title_override=title_override,
                )
                self._send_message(
                    chat_id,
                    f"Imported recipe #{recipe.pk}: {recipe.title}",
                    reply_to_message_id=message.get("message_id"),
                )
            except Exception as exc:
                self._send_message(
                    chat_id,
                    f"Import failed for {url}: {exc}",
                    reply_to_message_id=message.get("message_id"),
                )

    def _extract_message_text(self, message: dict) -> str:
        text_parts = []
        for key in ("text", "caption"):
            value = message.get(key)
            if isinstance(value, str) and value.strip():
                text_parts.append(value.strip())
        return "\n".join(text_parts).strip()

    def _extract_youtube_urls(self, text: str) -> Iterable[str]:
        for match in YOUTUBE_URL_PATTERN.finditer(text):
            yield match.group(0)

    def _extract_model_override(self, text: str) -> str | None:
        match = re.search(r"(?:^|\s)model\s*[:=]\s*([^\s]+)", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def _extract_title_override(self, text: str) -> str:
        match = re.search(r"(?:^|\s)title\s*[:=]\s*(.+)$", text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
        return ""

    def _send_message(self, chat_id: int | str | None, text: str, reply_to_message_id: int | None = None) -> None:
        if chat_id is None:
            return
        payload = {"chat_id": chat_id, "text": text}
        if isinstance(reply_to_message_id, int):
            payload["reply_to_message_id"] = reply_to_message_id
        response = requests.post(f"{self.base_url}/sendMessage", json=payload, timeout=30)
        response.raise_for_status()
        body = response.json()
        if not body.get("ok"):
            raise RuntimeError(f"Telegram sendMessage failed: {body}")


def import_recipe_from_url(
    url: str,
    model: str,
    household_id: int | None,
    title_override: str = "",
):
    household = get_household(household_id)
    client = get_openrouter_client()
    video_id = extract_video_id(url)
    metadata = get_video_metadata(url, video_id)
    transcript = transcribe_youtube(url)
    transcript_log = write_transcript_log(metadata, transcript)
    parsed = parse_recipe_with_llm(client, model, metadata, transcript)
    if title_override.strip():
        parsed["title"] = title_override.strip()
    recipe = upsert_recipe(parsed, household, url, transcript_log, video_id)
    print(f"Transcript saved to {transcript_log}")
    print(f"Recipe marked for review: {recipe.needs_review}")
    return recipe


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import YouTube recipes directly or from a Telegram group into MealPlanner"
    )
    parser.add_argument("url", nargs="?", help="Single YouTube URL to import")
    parser.add_argument(
        "--model",
        default=os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL),
        help="OpenRouter model to use for recipe extraction",
    )
    parser.add_argument(
        "--household-id",
        type=int,
        default=None,
        help="Household ID to associate with the imported recipe",
    )
    parser.add_argument(
        "--title",
        default="",
        help="Optional recipe title override",
    )
    parser.add_argument(
        "--telegram",
        action="store_true",
        help="Poll Telegram for YouTube URLs instead of importing a single URL",
    )
    parser.add_argument(
        "--telegram-bot-token",
        default=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        help="Telegram bot token for polling updates",
    )
    parser.add_argument(
        "--telegram-chat-name",
        action="append",
        default=[],
        help="Allowed Telegram chat title or username. Repeat to allow multiple chats.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Delay between Telegram polling retries after errors",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.telegram:
            allowed_chat_names = set(args.telegram_chat_name)
            importer = TelegramRecipeImporter(
                bot_token=args.telegram_bot_token,
                household_id=args.household_id,
                default_model=args.model,
                allowed_chat_names=allowed_chat_names,
                poll_interval=args.poll_interval,
            )
            return importer.run()

        if not args.url:
            parser.error("a YouTube URL is required unless --telegram is used")

        import_recipe_from_url(
            url=args.url,
            model=args.model,
            household_id=args.household_id,
            title_override=args.title,
        )
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
