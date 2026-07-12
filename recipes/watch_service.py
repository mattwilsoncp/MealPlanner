"""Video watch pipeline for recipes.

This service mirrors the Droid ``watch`` skill's core workflow: download the
recipe's video, pull a timestamped transcript, and extract a frame at the
start of each transcript segment so the web UI can show screenshots next to
the spoken instructions.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage

from instructions.models import Instruction
from recipes.models import Recipe, RecipeWatchSegment, RecipeWatchSession
from recipes.youtube import InvalidVideoError, YouTubeService


def extract_video_id(url: str) -> str:
    """Return the 11-character YouTube video id from *url*."""
    service = YouTubeService(api_key="placeholder")
    return service.extract_video_id(url)


def _find_binary(name: str) -> str | None:
    return shutil.which(name)


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        **kwargs,
    )


def _fetch_transcript_items(video_id: str) -> list[dict[str, Any]]:
    """Fetch caption items with start/duration/text from YouTube.

    Tries the same paths the rest of the project uses so the behaviour is
    consistent regardless of the installed ``youtube-transcript-api`` version.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError as exc:
        raise RuntimeError(
            "youtube-transcript-api is not installed"
        ) from exc

    errors = []
    transcript_items = None

    try:
        transcript_items = YouTubeTranscriptApi.get_transcript(
            video_id, languages=["en", "en-US", "en-GB"]
        )
    except Exception as exc:
        errors.append(f"get_transcript failed: {exc}")

    if transcript_items is None:
        try:
            api = YouTubeTranscriptApi()
            transcript_items = api.fetch(
                video_id, languages=["en", "en-US", "en-GB"]
            )
        except TypeError:
            try:
                transcript_items = api.fetch(video_id)
            except Exception as exc:
                errors.append(f"fetch failed: {exc}")
        except Exception as exc:
            errors.append(f"fetch failed: {exc}")

    if transcript_items is None:
        try:
            api = YouTubeTranscriptApi()
            transcript_list = api.list(video_id)
            preferred_languages = ["en", "en-US", "en-GB"]
            selected_transcript = None
            for language_code in preferred_languages:
                try:
                    selected_transcript = transcript_list.find_transcript(
                        [language_code]
                    )
                    break
                except Exception:
                    continue
            if selected_transcript is None:
                try:
                    selected_transcript = (
                        transcript_list.find_generated_transcript(
                            preferred_languages
                        )
                    )
                except Exception:
                    selected_transcript = None
            if selected_transcript is not None:
                transcript_items = selected_transcript.fetch()
        except Exception as exc:
            errors.append(f"list/fetch transcript track failed: {exc}")

    if transcript_items:
        normalized = []
        for item in transcript_items:
            if isinstance(item, dict):
                start = item.get("start", 0)
                duration = item.get("duration", 0)
                text = str(item.get("text", "") or "").strip()
            else:
                start = getattr(item, "start", 0)
                duration = getattr(item, "duration", 0)
                text = str(getattr(item, "text", "") or "").strip()
            if text:
                normalized.append(
                    {
                        "start": Decimal(str(start)),
                        "duration": Decimal(str(duration)),
                        "text": text,
                    }
                )
        return normalized

    error_message = "; ".join(errors) if errors else "No transcript items returned"
    raise RuntimeError(f"Could not fetch YouTube captions: {error_message}")


def _group_items_into_segments(
    items: list[dict[str, Any]],
    *,
    target_duration: Decimal = Decimal("10"),
    target_text_length: int = 200,
) -> list[dict[str, Any]]:
    """Group consecutive caption items into coarse segments for frame extraction.

    A new segment is started when the accumulated caption time reaches
    ``target_duration`` or the accumulated text length reaches
    ``target_text_length``.
    """
    if not items:
        return []

    segments = []
    current_texts: list[str] = []
    current_start: Decimal | None = None
    current_end: Decimal = Decimal("0")
    accumulated_duration = Decimal("0")

    def flush_segment():
        if not current_texts:
            return
        segments.append(
            {
                "start": current_start,
                "end": current_end,
                "text": " ".join(current_texts).strip(),
            }
        )
        current_texts.clear()

    for item in items:
        text = item.get("text", "").strip()
        if not text:
            continue

        start = Decimal(str(item.get("start", 0)))
        duration = Decimal(str(item.get("duration", 0)))
        end = start + duration

        if current_start is None:
            current_start = start

        should_flush = (
            accumulated_duration >= target_duration
            or sum(len(t) for t in current_texts) >= target_text_length
        )

        if should_flush and current_texts:
            flush_segment()
            current_start = start
            accumulated_duration = Decimal("0")

        current_texts.append(text)
        current_end = end
        accumulated_duration += duration

    flush_segment()
    return segments


def _download_video(url: str, work_dir: Path) -> Path:
    """Download *url* into *work_dir* and return the local file path."""
    yt_dlp = _find_binary("yt-dlp")
    if yt_dlp is None:
        raise RuntimeError("yt-dlp is not installed or not on PATH")

    # Download a single video file; cap at 720p to keep downloads fast and
    # frame extraction light.  We use a stable filename and let yt-dlp write
    # whatever extension it chooses, then return the actual file.
    template = str(work_dir / "video.%(ext)s")
    _run(
        [
            yt_dlp,
            "-f",
            "best[height<=720]/best",
            "-o",
            template,
            "--no-playlist",
            "--newline",
            url,
        ]
    )

    candidates = sorted(work_dir.glob("video.*"))
    for candidate in candidates:
        if candidate.suffix.lower() in {".mp4", ".webm", ".mkv", ".mov"}:
            return candidate

    raise RuntimeError("yt-dlp did not produce a recognizable video file")


def _extract_frame(video_path: Path, timestamp: Decimal, output_path: Path) -> None:
    """Extract one JPEG frame at *timestamp* seconds from *video_path*."""
    ffmpeg = _find_binary("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is not installed or not on PATH")

    _run(
        [
            ffmpeg,
            "-y",
            "-ss",
            str(float(timestamp)),
            "-i",
            str(video_path),
            "-vframes",
            "1",
            "-q:v",
            "2",
            "-vf",
            "scale=640:-1",
            str(output_path),
        ]
    )


def _best_matching_step(segment_text: str, instructions: list[Instruction]) -> int | None:
    """Return the step number of the instruction that best overlaps with
    *segment_text*, or ``None`` if there is no clear candidate.
    """
    if not instructions or not segment_text:
        return None

    segment_words = set(_normalize_words(segment_text))
    if not segment_words:
        return None

    best_step = None
    best_score = 0.0
    for instruction in instructions:
        instruction_words = set(_normalize_words(instruction.text))
        if not instruction_words:
            continue
        overlap = len(segment_words & instruction_words)
        score = overlap / max(len(instruction_words), 1)
        if score > best_score and score > 0.2:
            best_score = score
            best_step = instruction.step_number

    return best_step


def _normalize_words(text: str) -> list[str]:
    """Return lowercased words from *text* with common stop words removed."""
    stop_words = {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "to",
        "of",
        "in",
        "on",
        "at",
        "for",
        "with",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "then",
        "so",
        "if",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "you",
        "your",
        "i",
        "we",
        "they",
        "them",
        "he",
        "she",
        "his",
        "her",
    }
    return [
        word
        for word in re.findall(r"[a-zA-Z']+", text.lower())
        if word and word not in stop_words and len(word) > 2
    ]


def process_recipe_watch(
    recipe: Recipe,
    *,
    max_segments: int = 30,
    keep_video: bool = False,
) -> RecipeWatchSession:
    """Download *recipe*'s video, extract frames, and build watch segments.

    Existing segments and images for this recipe are replaced.  The function
    returns the updated ``RecipeWatchSession``.
    """
    session, _ = RecipeWatchSession.objects.get_or_create(
        recipe=recipe,
        defaults={"status": RecipeWatchSession.Status.PENDING},
    )
    session.status = RecipeWatchSession.Status.PENDING
    session.error_message = ""
    session.save()

    # Delete old segments (and their images via Django's file delete hook).
    session.segments.all().delete()

    try:
        if not recipe.video_url:
            raise ValueError("Recipe has no video URL")

        video_id = extract_video_id(recipe.video_url)
        items = _fetch_transcript_items(video_id)

        if not items:
            raise ValueError(
                "No captions were returned for this video. "
                "The video may not have captions available, or the captions are empty."
            )

        first_start = min(item["start"] for item in items)
        last_end = max(item["start"] + item["duration"] for item in items)
        total_duration = last_end - first_start
        if total_duration > 0:
            target_duration = max(
                total_duration / Decimal(max_segments), Decimal("5")
            )
        else:
            target_duration = Decimal("10")

        segments = _group_items_into_segments(
            items,
            target_duration=target_duration,
            target_text_length=200,
        )
        if not segments:
            raise ValueError("No transcript content available to segment")

        instructions = list(
            Instruction.objects.filter(recipe=recipe).order_by("step_number")
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = Path(tmp_dir)
            video_path = _download_video(recipe.video_url, work_dir)

            for index, segment in enumerate(segments, start=1):
                start = segment["start"]
                end = segment["end"]
                text = segment["text"]

                frame_path = work_dir / f"frame_{index:04d}.jpg"
                _extract_frame(video_path, start, frame_path)

                step_number = _best_matching_step(text, instructions)
                segment = RecipeWatchSegment.objects.create(
                    session=session,
                    start_time=start,
                    end_time=end,
                    text=text,
                    step_number=step_number,
                )
                with open(frame_path, "rb") as fh:
                    segment.image.save(
                        f"frame_{index:04d}.jpg", File(fh), save=True
                    )

        session.status = RecipeWatchSession.Status.READY
        session.save()

    except Exception as exc:
        session.status = RecipeWatchSession.Status.ERROR
        session.error_message = str(exc)
        session.save()
        raise

    return session
