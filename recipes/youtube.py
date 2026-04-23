import re
from dataclasses import dataclass

try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    build = None
    HttpError = Exception


class InvalidVideoError(Exception):
    pass


class APIError(Exception):
    pass


@dataclass
class YouTubeMetadata:
    video_id: str
    title: str
    description: str
    thumbnail_url: str
    transcript: str = ""


class YouTubeService:
    def __init__(self, api_key: str):
        if not api_key:
            raise APIError("YouTube API key not configured")
        self.api_key = api_key
        if build:
            self.youtube = build("youtube", "v3", developerKey=api_key)
        else:
            self.youtube = None

    def extract_video_id(self, url: str) -> str:
        patterns = [
            r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/|youtube\.com/v/)([a-zA-Z0-9_-]{11})",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        raise InvalidVideoError("Invalid YouTube URL format")

    def get_transcript(self, url: str) -> str:
        """Fetch transcript using markitdown if available."""
        try:
            from markitdown import MarkItDown

            md = MarkItDown()
            result = md.convert(url)
            return result.text_content or ""
        except ImportError:
            return ""
        except Exception:
            return ""

    def get_video_metadata(self, video_id: str) -> YouTubeMetadata:
        if not self.youtube:
            raise APIError("YouTube API not configured")

        try:
            request = self.youtube.videos().list(part="snippet", id=video_id)
            response = request.execute()

            if not response.get("items"):
                raise APIError("Video not found")

            snippet = response["items"][0]["snippet"]
            thumbnails = snippet.get("thumbnails", {})

            thumbnail_url = ""
            for quality in ("maxres", "high", "medium", "default"):
                if quality in thumbnails:
                    thumbnail_url = thumbnails[quality]["url"]
                    break

            return YouTubeMetadata(
                video_id=video_id,
                title=snippet.get("title", ""),
                description=snippet.get("description", ""),
                thumbnail_url=thumbnail_url,
            )
        except HttpError as e:
            raise APIError(f"YouTube API error: {e}")
