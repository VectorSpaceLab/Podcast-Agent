"""Project-level exceptions."""


class PodcastAgentError(Exception):
    """Base exception for Podcast-Agent failures."""


class UnsupportedSourceError(PodcastAgentError):
    """Raised when a URL does not match a supported source."""


class InvalidSourceUrlError(PodcastAgentError):
    """Raised when a supported source URL cannot be resolved."""


class YtDlpError(PodcastAgentError):
    """Raised when yt-dlp fails."""


class ElementFetchError(PodcastAgentError):
    """Base exception for base element fetching failures."""


class MetadataFetchError(ElementFetchError):
    """Raised when video metadata cannot be fetched or normalized."""


class TranscriptFetchError(ElementFetchError):
    """Raised when transcript acquisition fails."""


class AudioTranscriptionError(ElementFetchError):
    """Raised when audio transcription fallback fails."""


class EvidenceExtractionError(PodcastAgentError):
    """Raised when evidence extraction fails."""
