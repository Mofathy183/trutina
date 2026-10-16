"""Public HTTP request/response contracts for the account feature.

These schemas are the API's own presentation-layer types. They are
structurally similar to `modules/account/dtos.py`'s DTOs and
`AccountViewModel`/`ChartOfAccountsViewModel` by design -- the account
resource has one natural shape -- but are kept as separate classes so
the public HTTP contract can evolve independently of the service
boundary's DTOs, exactly as `Trutina API Feature & Testing Prompt`
Section 2 requires ("Response Schema... Must never expose internal
domain/DTO field names it hasn't deliberately chosen to mirror").

Request schemas perform FastAPI/Pydantic structural validation only.
Business rules (uniqueness, name-format validation) fire later, inside
AccountService and the Account domain model, and are translated to the
standard error envelope by `api/shared/errors/handlers.py`.
"""

from typing import Literal

from pydantic import BaseModel, Field
from trutina.api.shared.response import SuccessResponse
from trutina.core.account.schemas.account import AccountCategory


class CreateAccountRequest(BaseModel):
    """Request body for ``POST /accounts``.

    Field constraints mirror `CreateAccountInput`
    (`modules/account/dtos.py`) so a malformed request fails fast at the
    transport layer (422 via FastAPI's own request validation) before
    ever reaching the service. Deeper business rules -- name-character
    validity, duplicate code/name -- are not (and cannot be) expressed
    here; they fire inside `AccountService.create_account()`.
    """

    code: str = Field(
        min_length=1,
        max_length=20,
        description="Chart of accounts code: 4 to 6 digits, e.g. '1000'.",
    )
    name: str = Field(
        min_length=2,
        max_length=150,
        description="The canonical name of the account.",
    )
    category: AccountCategory = Field(
        description="The classification category of the account.",
    )


class UpdateAccountRequest(BaseModel):
    """Request body for ``PATCH /accounts/{code}``.

    The account code is supplied via the URL path, not the body -- it
    is the immutable lookup key, mirroring `UpdateAccountInput`'s own
    treatment of `code`. Only `name`/`category` are fields a caller can
    submit; both are optional so a caller may update just one.
    Omitted vs. explicitly `null` follows the same DTO-level semantics
    as `UpdateAccountInput` (see `modules/account/dtos.py`): both mean
    "leave the existing value in place," since the mapper always
    forwards the field, and `AccountService.update_account()` treats a
    `None` value as "unchanged" rather than "clear the field" -- there
    is no way to null out `name` or `category` through this endpoint,
    consistent with the domain model requiring both to always be set.
    """

    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=150,
        description="New account name. Omit to keep the current name.",
    )
    category: AccountCategory | None = Field(
        default=None,
        description="New account category. Omit to keep the current category.",
    )


class AccountData(BaseModel):
    """The account resource shape returned by every account endpoint.

    Mirrors `AccountViewModel` (`modules/account/dtos.py`) field for
    field. Kept as a distinct type per this project's API/domain
    boundary rule rather than reusing `AccountViewModel` directly on
    the wire.
    """

    code: str
    name: str
    category: AccountCategory
    normal_balance: Literal["debit", "credit"]


class AccountResponse(SuccessResponse):
    """Response envelope for endpoints returning a single account.

    Used by create, get, and update. ``account`` carries the resource;
    ``success``/``timestamp`` are inherited from ``SuccessResponse``.
    """

    account: AccountData


class ChartOfAccountsResponse(SuccessResponse):
    """Response envelope for ``GET /accounts`` (list all accounts)."""

    accounts: list[AccountData]


class DeleteAccountResponse(SuccessResponse):
    """Response envelope for ``DELETE /accounts/{code}``.

    Carries no resource body -- the account no longer exists -- but
    still returns the standard envelope (`success`/`timestamp`) rather
    than a bare 204, so every account endpoint has one consistent
    response shape to parse. Echoes back the deleted `code` as the only
    useful confirmation data available after deletion.
    """

    code: str
