"""Shared response envelope primitives for the Trutina API.

BaseResponse defines the two fields every JSON body carries regardless
of outcome. SuccessResponse and the error envelopes in
`api/shared/errors/schemas.py` both build on top of it, so a client can
always branch on `success` without inferring outcome from the HTTP
status code alone.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class BaseResponse(BaseModel):
    """Common envelope shared by every API response, success or error.

    Attributes:
        success: True for a successful response, False for any
            ErrorResponse (fixed there via Literal[False]). Lets clients
            branch on outcome directly from the body, without inferring
            it from the HTTP status code or transport-level detail.
        timestamp: UTC time this response instance was constructed.
            Freshly generated per response via a default factory -- for
            client-side logging and correlation, not a persisted domain
            value, and not the time the underlying operation occurred.
    """

    success: bool
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SuccessResponse(BaseResponse):
    """Base envelope for every successful response.

    Feature presenters build their own response models on top of this
    (e.g. `AccountResponse(SuccessResponse)`) instead of `BaseResponse`
    directly, so `success` is fixed to `True` and never has to be set
    explicitly at each call site -- mirroring how `ErrorResponse` fixes
    `success` to `Literal[False]`.
    """

    success: bool = True
