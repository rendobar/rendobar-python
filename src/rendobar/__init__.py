"""Rendobar Python SDK: media processing and AI generation API for Python.

    from rendobar import Rendobar
    rb = Rendobar()  # reads RENDOBAR_API_KEY
    job = rb.jobs.run(type="ffprobe", params={"command": "https://example.com/a.mp4"})
"""
from ._async_client import AsyncRendobar
from ._client import DeprecationNotice, Page, Rendobar, UnknownJob, generate_idempotency_key
from ._errors import (
    AuthenticationError,
    BadRequestError,
    ConflictError,
    InsufficientCreditsError,
    InternalServerError,
    JobFailedError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    RendobarError,
    WaitTimeoutError,
)
from ._version import __version__

__all__ = [
    "Rendobar", "AsyncRendobar", "Page", "UnknownJob", "DeprecationNotice", "generate_idempotency_key",
    "RendobarError", "BadRequestError", "AuthenticationError", "InsufficientCreditsError",
    "PermissionDeniedError", "NotFoundError", "ConflictError", "RateLimitError", "InternalServerError",
    "JobFailedError", "WaitTimeoutError", "__version__",
]
