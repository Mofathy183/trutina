"""
Data transfer objects for the account feature.

Input DTOs carry raw caller input into the service layer.
ViewModels carry service results back to the CLI or API.

Formatters and routes depend only on the ViewModels defined here,
never on Account or ChartOfAccounts internals.
"""

from pydantic import BaseModel, Field

from .schemas.account import AccountCategory, NormalBalance

# Input DTOs — data coming IN to the service


class CreateAccountInput(BaseModel):
    """Input DTO for account creation.

    Carries raw user-supplied values into the service.
    Field-level validation and normalization are enforced by the
    Account domain model constructed by the service. This DTO only
    captures caller-supplied values for the creation workflow.
    Cross-account uniqueness checks (duplicate code, duplicate
    name) happen in the service via targeted existence queries — not
    here.
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


class UpdateAccountInput(BaseModel):
    """Input DTO for partial account updates.

    Only the fields explicitly provided are applied; omitted fields
    retain their current persisted values. The code field identifies
    which account to update and is immutable — it is never changed by
    an update operation.

    Cross-account uniqueness checks for any changed name are the
    service's responsibility. This DTO performs no uniqueness checks
    of its own.
    """

    code: str = Field(
        min_length=1,
        max_length=20,
        description=(
            "Code of the account to update. "
            "Used as the lookup key and cannot be changed."
        ),
    )
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=150,
        description="New account name. Omit to keep the current name.",
    )
    category: AccountCategory | None = Field(
        default=None,
        description=(
            "New account category. "
            "Omit to keep the current category. "
            "Changing the category also changes the derived normal balance."
        ),
    )


# ViewModels — data coming OUT of the service


class AccountViewModel(BaseModel):
    """Read-only view of a single account.

    Provides the service layer's public representation of an account.
    Callers consume this model instead of the underlying Account domain
    model so presentation concerns can evolve independently of domain
    implementation details.
    """

    code: str
    name: str
    category: AccountCategory
    normal_balance: NormalBalance


class ChartOfAccountsViewModel(BaseModel):
    """Read-only view of a chart of accounts.

    Provides callers with a stable collection of account view models
    without exposing ChartOfAccounts internals.
    """

    accounts: list[AccountViewModel]
