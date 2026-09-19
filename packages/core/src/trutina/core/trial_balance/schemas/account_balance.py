"""
Domain schema for one account's aggregated posting activity.

An account balance entry is a derived, read-only record produced by
aggregating every LedgerPosting recorded against a single account. It
carries no accounting invariants of its own beyond what its source
postings already enforce -- it exists purely to shape one row of a
trial balance.

Unlike a posting, an account balance entry is never single-sided: an
account legitimately accumulates both debit and credit activity over
its history, so both totals are independently non-negative.
"""

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator
from trutina.shared.errors import ErrorCode, pydantic_error
from trutina.shared.rule import clean_account_name


class AccountBalanceEntry(BaseModel):
    """Aggregated debit/credit activity for a single account.

    Represents one row of a trial balance: the sum of every debit
    posted to this account and the sum of every credit posted to it,
    across whatever set of LedgerPosting records the aggregation was
    scoped to (see TrialBalanceRepo.get_account_balances's as_of_date
    parameter).

    Both totals are independently non-negative. This is a deliberate
    departure from LedgerPosting's single-sidedness: a posting records
    one side of one transaction, but an account's lifetime activity
    legitimately includes both debit and credit postings.
    """

    model_config = ConfigDict(frozen=True)

    account: Annotated[
        str,
        Field(
            description="The account this balance was aggregated for.",
            min_length=2,
            max_length=100,
        ),
    ]

    debit_total: Annotated[
        Decimal,
        Field(
            ge=0,
            description="Sum of every debit posting recorded against this account.",
        ),
    ]

    credit_total: Annotated[
        Decimal,
        Field(
            ge=0,
            description="Sum of every credit posting recorded against this account.",
        ),
    ]

    @field_validator("account")
    @classmethod
    def validate_account(cls, value: str) -> str:
        """Validate and normalize the account reference.

        Applies the same normalization LedgerPosting.account enforces.
        The value is expected to already be a normalized account name
        coming out of aggregation -- this is a defensive re-check, not
        a new source of truth for account naming.

        Args:
            value: Raw account name from the aggregation source.

        Returns:
            The normalized account name.

        Raises:
            PydanticCustomError: If the account name is invalid.
        """
        cleaned = clean_account_name(value)
        if cleaned is None:
            raise pydantic_error(ErrorCode.INVALID_ACCOUNT_NAME)
        return cleaned
