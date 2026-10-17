"""Application-level use case for creating an account.

Handlers are the seam between CLI-specific input resolution (parsing,
interactive prompts) and the service layer. A handler accepts an
already-validated DTO and knows nothing about Typer, Click, or
terminal presentation -- it must remain callable identically regardless
of where the DTO came from.
"""

from trutina.cli.composition.actor import PRE_AUTH_ACTOR
from trutina.cli.composition.context import CliContext
from trutina.core.account import (
    AccountViewModel,
    ChartOfAccountsViewModel,
    CreateAccountInput,
    UpdateAccountInput,
)
from trutina.shared.errors import AppError, ErrorCode


async def create_account_handler(
    ctx: CliContext,
    dto: CreateAccountInput,
) -> AccountViewModel:
    """Create a new account through ``AccountService``.

    Resolves ``AccountService`` from the supplied ``CliContext` and delegates account creation
    to it.

    Args:
        ctx: The ``CliContext`` for this invocation. Callers must pass
            ``state.context``, not the ``CliState`` wrapper itself.
        dto: A structurally valid ``CreateAccountInput``, already
            resolved from CLI flags or interactive prompts by the
            calling command.

    Returns:
        The view model for the newly created account.

    Raises:
        AppError: DUPLICATE_ACCOUNT_CODE or DUPLICATE_ACCOUNT_NAME if the
            account conflicts with an existing one. Propagates unchanged
            from ``AccountService.create_account`` for the command to
            catch and render.
        ValidationAppError: VALIDATION_ERROR if the account fields fail
            domain validation.
    """
    service = await ctx.get_account_service()
    return await service.create_account(dto, actor=PRE_AUTH_ACTOR)


async def get_account_handler(ctx: CliContext, identifier: str) -> AccountViewModel:
    """Look up a single account by code, falling back to name.

    Accounts are naturally identified two ways in this codebase --
    ``AccountService.get_account(code)`` and
    ``AccountService.resolve_account(name)``. The CLI exposes a single
    ``identifier`` argument (per ``prompts.prompt_account_identifier()``),
    so this handler tries the code lookup first and only falls back to
    name resolution if the code lookup reports UNKNOWN_ACCOUNT. Any other
    AppError propagates immediately -- it isn't this handler's place to
    guess whether a non-lookup failure might resolve differently by name.

    Args:
        ctx: The CliContext for this invocation.
        identifier: An account code or account name, as typed or prompted.

    Returns:
        The view model for the matching account.

    Raises:
        AppError: UNKNOWN_ACCOUNT if identifier matches neither a code
            nor a name.
    """
    service = await ctx.get_account_service()
    try:
        return await service.get_account(code=identifier)
    except AppError as exc:
        if exc.code != ErrorCode.UNKNOWN_ACCOUNT:
            raise
    return await service.resolve_account(reference=identifier)


async def list_accounts_handler(ctx: CliContext) -> ChartOfAccountsViewModel:
    """List every account in the chart of accounts.

    Args:
        ctx: The CliContext for this invocation.

    Returns:
        The chart-of-accounts view model, possibly empty.
    """
    service = await ctx.get_account_service()
    return await service.list_accounts()


async def update_account_handler(
    ctx: CliContext,
    dto: UpdateAccountInput,
) -> AccountViewModel:
    """Apply a partial update to an existing account through AccountService.

    Args:
        ctx: The CliContext for this invocation.
        dto: A structurally valid UpdateAccountInput, already resolved
            from CLI flags or interactive prompts.

    Returns:
        The view model for the updated account.

    Raises:
        AppError: UNKNOWN_ACCOUNT if dto.code does not exist.
            DUPLICATE_ACCOUNT_NAME if the new name collides with another
            account.
        ValidationAppError: VALIDATION_ERROR if the merged field values
            fail domain validation.
    """
    service = await ctx.get_account_service()
    return await service.update_account(dto, actor=PRE_AUTH_ACTOR)


async def delete_account_handler(ctx: CliContext, code: str) -> None:
    """Delete an account by code through AccountService.

    Args:
        ctx: The CliContext for this invocation.
        code: The account code to delete.

    Raises:
        AppError: UNKNOWN_ACCOUNT if no account with that code exists.
    """
    service = await ctx.get_account_service()
    await service.delete_account(code, actor=PRE_AUTH_ACTOR)
