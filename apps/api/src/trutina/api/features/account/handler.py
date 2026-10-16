"""Input DTO -> AccountService call -> ViewModel for the account feature.

Each handler is exactly one service call, per
`Trutina API Feature & Testing Prompt` Section 2/3: no FastAPI import,
no Mapper/Presenter construction, no exception handling. Any
``AppError``/``ValidationAppError``/``pydantic.ValidationError`` raised
by ``AccountService`` propagates uncaught -- ``api/shared/errors/handlers.py``
is the single translation seam for all of it, exactly as it already is
for a mapper-stage domain-construction failure.

Every function here is a plain ``async def`` callable identically from
a router or directly from a unit test against a ``Fake*Repo``-backed
``AccountService`` -- mirroring the CLI's own ``handler.py`` contract.
Every write passes ``PRE_AUTH_ACTOR`` as the service's keyword-only
``actor``. Requests carry no authenticated identity today, and the actor is
never read from a request body or DTO. Handler signatures take no actor.
"""

from trutina.api.shared.actor import PRE_AUTH_ACTOR
from trutina.core.account.dtos import (
    AccountViewModel,
    ChartOfAccountsViewModel,
    CreateAccountInput,
    UpdateAccountInput,
)
from trutina.core.account.service import AccountService


async def create_account(
    service: AccountService, dto: CreateAccountInput
) -> AccountViewModel:
    """Create a new account.

    Args:
        service: The resolved ``AccountService`` instance.
        dto: Validated account-creation input.

    Returns:
        The view model of the newly created account.

    Raises:
        AppError: DUPLICATE_ACCOUNT_CODE, DUPLICATE_ACCOUNT_NAME.
        ValidationAppError: VALIDATION_ERROR.
    """
    return await service.create_account(dto, actor=PRE_AUTH_ACTOR)


async def update_account(
    service: AccountService, dto: UpdateAccountInput
) -> AccountViewModel:
    """Apply a partial update to an existing account.

    Args:
        service: The resolved ``AccountService`` instance.
        dto: Partial update input; omitted fields keep their current
            persisted values.

    Returns:
        The view model of the updated account.

    Raises:
        AppError: UNKNOWN_ACCOUNT, DUPLICATE_ACCOUNT_NAME.
        ValidationAppError: VALIDATION_ERROR.
    """
    return await service.update_account(dto, actor=PRE_AUTH_ACTOR)


async def get_account(service: AccountService, code: str) -> AccountViewModel:
    """Fetch a single account by its code.

    Args:
        service: The resolved ``AccountService`` instance.
        code: The account code to look up.

    Returns:
        The view model for the matching account.

    Raises:
        AppError: UNKNOWN_ACCOUNT.
    """
    return await service.get_account(code)


async def list_accounts(service: AccountService) -> ChartOfAccountsViewModel:
    """Fetch every persisted account as a single chart view model.

    Args:
        service: The resolved ``AccountService`` instance.

    Returns:
        A ``ChartOfAccountsViewModel`` containing every persisted
        account.
    """
    return await service.list_accounts()


async def delete_account(service: AccountService, code: str) -> None:
    """Remove an account by its code.

    Args:
        service: The resolved ``AccountService`` instance.
        code: The account code to delete.

    Raises:
        AppError: UNKNOWN_ACCOUNT.
    """
    await service.delete_account(code, actor=PRE_AUTH_ACTOR)
