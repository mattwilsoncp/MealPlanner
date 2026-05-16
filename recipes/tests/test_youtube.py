import pytest
from unittest.mock import MagicMock, patch

from recipes.youtube import (
    YouTubeService,
    YouTubeMetadata,
    InvalidVideoError,
    APIError,
)


class TestYouTubeServiceInit:
    def test_init_empty_api_key_raises_error(self):
        with pytest.raises(APIError) as exc_info:
            YouTubeService("")
        assert "YouTube API key not configured" in str(exc_info.value)

    def test_init_none_api_key_raises_error(self):
        with pytest.raises(APIError) as exc_info:
            YouTubeService(None)
        assert "YouTube API key not configured" in str(exc_info.value)

    @patch("recipes.youtube.build")
    def test_init_valid_api_key_creates_youtube_client(self, mock_build):
        mock_youtube = MagicMock()
        mock_build.return_value = mock_youtube
        
        service = YouTubeService("test-api-key")
        
        assert service.api_key == "test-api-key"
        assert service.youtube == mock_youtube
        mock_build.assert_called_once_with("youtube", "v3", developerKey="test-api-key")

    def test_init_build_not_available_sets_youtube_to_none(self):
        import recipes.youtube as yt_module
        original_build = yt_module.build
        yt_module.build = None
        
        try:
            service = YouTubeService("test-api-key")
            assert service.youtube is None
        finally:
            yt_module.build = original_build


class TestExtractVideoId:
    def setup_method(self):
        with patch("recipes.youtube.build"):
            self.service = YouTubeService("test-key")

    def test_extract_from_standard_watch_url(self):
        video_id = self.service.extract_video_id(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_from_short_url(self):
        video_id = self.service.extract_video_id(
            "https://youtu.be/dQw4w9WgXcQ"
        )
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_from_short_with_params(self):
        video_id = self.service.extract_video_id(
            "https://youtu.be/dQw4w9WgXcQ?t=42"
        )
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_from_shorts_url(self):
        video_id = self.service.extract_video_id(
            "https://youtube.com/shorts/dQw4w9WgXcQ"
        )
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_from_embed_url(self):
        video_id = self.service.extract_video_id(
            "https://youtube.com/v/dQw4w9WgXcQ"
        )
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_from_url_with_additional_params(self):
        video_id = self.service.extract_video_id(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
        )
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_invalid_url_raises_error(self):
        with pytest.raises(InvalidVideoError) as exc_info:
            self.service.extract_video_id("https://example.com/video")
        assert "Invalid YouTube URL format" in str(exc_info.value)

    def test_extract_empty_url_raises_error(self):
        with pytest.raises(InvalidVideoError):
            self.service.extract_video_id("")


class TestGetTranscript:
    def setup_method(self):
        with patch("recipes.youtube.build"):
            self.service = YouTubeService("test-key")

    @patch("markitdown.MarkItDown")
    def test_get_transcript_success(self, mock_markitdown_cls):
        mock_result = MagicMock()
        mock_result.text_content = "This is the transcript content."
        mock_markitdown = MagicMock()
        mock_markitdown.convert.return_value = mock_result
        mock_markitdown_cls.return_value = mock_markitdown

        transcript = self.service.get_transcript("https://youtube.com/watch?v=abc123")
        
        assert transcript == "This is the transcript content."
        mock_markitdown.convert.assert_called_once_with("https://youtube.com/watch?v=abc123")

    @patch("markitdown.MarkItDown")
    def test_get_transcript_empty_content_returns_empty_string(self, mock_markitdown_cls):
        mock_result = MagicMock()
        mock_result.text_content = None
        mock_markitdown = MagicMock()
        mock_markitdown.convert.return_value = mock_result
        mock_markitdown_cls.return_value = mock_markitdown

        transcript = self.service.get_transcript("https://youtube.com/watch?v=abc123")
        
        assert transcript == ""

    @patch("markitdown.MarkItDown")
    def test_get_transcript_import_error_returns_empty(self, mock_markitdown_cls):
        mock_markitdown_cls.side_effect = ImportError("markitdown not installed")

        transcript = self.service.get_transcript("https://youtube.com/watch?v=abc123")
        
        assert transcript == ""

    @patch("markitdown.MarkItDown")
    def test_get_transcript_other_error_returns_empty(self, mock_markitdown_cls):
        mock_markitdown_cls.side_effect = RuntimeError("Some error")

        transcript = self.service.get_transcript("https://youtube.com/watch?v=abc123")
        
        assert transcript == ""


class TestGetVideoMetadata:
    def test_get_video_metadata_youtube_not_configured_raises_error(self):
        import recipes.youtube as yt_module
        original_build = yt_module.build
        yt_module.build = None
        
        try:
            service = YouTubeService("test-api-key")
            assert service.youtube is None
            
            with pytest.raises(APIError) as exc_info:
                service.get_video_metadata("test-video-id")
            assert "YouTube API not configured" in str(exc_info.value)
        finally:
            yt_module.build = original_build

    @patch("recipes.youtube.build")
    def test_get_video_metadata_video_not_found_raises_error(self, mock_build):
        mock_youtube = MagicMock()
        mock_response = {"items": []}
        mock_youtube.videos.return_value.list.return_value.execute.return_value = mock_response
        mock_build.return_value = mock_youtube
        
        service = YouTubeService("test-api-key")
        
        with pytest.raises(APIError) as exc_info:
            service.get_video_metadata("nonexistent-video-id")
        assert "Video not found" in str(exc_info.value)

    @patch("recipes.youtube.build")
    def test_get_video_metadata_http_error_raises_api_error(self, mock_build):
        mock_youtube = MagicMock()
        from googleapiclient.errors import HttpError
        
        # Create a mock response object with 'reason' attribute
        mock_resp = MagicMock()
        mock_resp.reason = "Bad Request"
        
        mock_request = MagicMock()
        mock_request.execute.side_effect = HttpError(mock_resp, b'Error')
        mock_youtube.videos.return_value.list.return_value = mock_request
        mock_build.return_value = mock_youtube
        
        service = YouTubeService("test-api-key")
        
        with pytest.raises(APIError) as exc_info:
            service.get_video_metadata("test-video-id")
        assert "YouTube API error" in str(exc_info.value)

    @patch("recipes.youtube.build")
    def test_get_video_metadata_maxres_thumbnail(self, mock_build):
        mock_youtube = MagicMock()
        mock_response = {
            "items": [{
                "snippet": {
                    "title": "Test Video",
                    "description": "Test description",
                    "thumbnails": {
                        "maxres": {"url": "https://maxres.url/thumb.jpg"}
                    }
                }
            }]
        }
        mock_youtube.videos.return_value.list.return_value.execute.return_value = mock_response
        mock_build.return_value = mock_youtube
        
        service = YouTubeService("test-api-key")
        metadata = service.get_video_metadata("test-video-id")
        
        assert isinstance(metadata, YouTubeMetadata)
        assert metadata.video_id == "test-video-id"
        assert metadata.title == "Test Video"
        assert metadata.description == "Test description"
        assert metadata.thumbnail_url == "https://maxres.url/thumb.jpg"
        assert metadata.transcript == ""

    @patch("recipes.youtube.build")
    def test_get_video_metadata_high_thumbnail(self, mock_build):
        mock_youtube = MagicMock()
        mock_response = {
            "items": [{
                "snippet": {
                    "title": "Test Video",
                    "description": "Test description",
                    "thumbnails": {
                        "high": {"url": "https://high.url/thumb.jpg"}
                    }
                }
            }]
        }
        mock_youtube.videos.return_value.list.return_value.execute.return_value = mock_response
        mock_build.return_value = mock_youtube
        
        service = YouTubeService("test-api-key")
        metadata = service.get_video_metadata("test-video-id")
        
        assert metadata.thumbnail_url == "https://high.url/thumb.jpg"

    @patch("recipes.youtube.build")
    def test_get_video_metadata_medium_thumbnail(self, mock_build):
        mock_youtube = MagicMock()
        mock_response = {
            "items": [{
                "snippet": {
                    "title": "Test Video",
                    "description": "Test description",
                    "thumbnails": {
                        "medium": {"url": "https://medium.url/thumb.jpg"}
                    }
                }
            }]
        }
        mock_youtube.videos.return_value.list.return_value.execute.return_value = mock_response
        mock_build.return_value = mock_youtube
        
        service = YouTubeService("test-api-key")
        metadata = service.get_video_metadata("test-video-id")
        
        assert metadata.thumbnail_url == "https://medium.url/thumb.jpg"

    @patch("recipes.youtube.build")
    def test_get_video_metadata_default_thumbnail(self, mock_build):
        mock_youtube = MagicMock()
        mock_response = {
            "items": [{
                "snippet": {
                    "title": "Test Video",
                    "description": "Test description",
                    "thumbnails": {
                        "default": {"url": "https://default.url/thumb.jpg"}
                    }
                }
            }]
        }
        mock_youtube.videos.return_value.list.return_value.execute.return_value = mock_response
        mock_build.return_value = mock_youtube
        
        service = YouTubeService("test-api-key")
        metadata = service.get_video_metadata("test-video-id")
        
        assert metadata.thumbnail_url == "https://default.url/thumb.jpg"

    @patch("recipes.youtube.build")
    def test_get_video_metadata_no_thumbnail_returns_empty_url(self, mock_build):
        mock_youtube = MagicMock()
        mock_response = {
            "items": [{
                "snippet": {
                    "title": "Test Video",
                    "description": "Test description",
                    "thumbnails": {}
                }
            }]
        }
        mock_youtube.videos.return_value.list.return_value.execute.return_value = mock_response
        mock_build.return_value = mock_youtube
        
        service = YouTubeService("test-api-key")
        metadata = service.get_video_metadata("test-video-id")
        
        assert metadata.thumbnail_url == ""

    @patch("recipes.youtube.build")
    def test_get_video_metadata_missing_title_and_description(self, mock_build):
        mock_youtube = MagicMock()
        mock_response = {
            "items": [{
                "snippet": {
                    "thumbnails": {}
                }
            }]
        }
        mock_youtube.videos.return_value.list.return_value.execute.return_value = mock_response
        mock_build.return_value = mock_youtube
        
        service = YouTubeService("test-api-key")
        metadata = service.get_video_metadata("test-video-id")
        
        assert metadata.title == ""
        assert metadata.description == ""


class TestYouTubeMetadata:
    def test_youtube_metadata_default_transcript(self):
        metadata = YouTubeMetadata(
            video_id="test123",
            title="Test Title",
            description="Test Description",
            thumbnail_url="https://example.com/thumb.jpg"
        )
        assert metadata.transcript == ""

    def test_youtube_metadata_with_transcript(self):
        metadata = YouTubeMetadata(
            video_id="test123",
            title="Test Title",
            description="Test Description",
            thumbnail_url="https://example.com/thumb.jpg",
            transcript="This is a transcript"
        )
        assert metadata.transcript == "This is a transcript"