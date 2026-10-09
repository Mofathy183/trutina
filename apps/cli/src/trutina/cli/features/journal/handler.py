"""Application-level use cases for the Journal CLI feature.

Mirrors cli/features/account/handler.py: a handler accepts an
already-validated DTO (or a plain identifier) and knows nothing about
Typer, Click, or terminal presentation. Every handler here resolves
JournalService lazily from the supplied CliContext the same way
Account's handlers resolve AccountService.
"""

from trutina.cli.composition.actor import PRE_AUTH_ACTOR
from trutina.cli.composition.context import CliContext
from trutina.core.journal import CreateJournalInput, JournalViewModel


async def create_journal_entry_handler(
    ctx: CliContext,
    dto: CreateJournalInput,
) -> JournalViewModel:
    """Create a new journal entry through JournalService.

    The write is attributed to the CLI's fixed pre-auth actor
    (``PRE_AUTH_ACTOR``); the command carries no identity.

    Args:
        ctx: The CliContext for this invocation. Callers must pass
            ``state.context``, not the CliState wrapper itself.
        dto: A structurally valid CreateJournalInput, already resolved
            from CLI flags or interactive prompts by the calling
            command.

    Returns:
        The view model for the newly created journal entry.

    Raises:
        AppError: UNKNOWN_ACCOUNT if any line references an account
            that does not exist in the chart of accounts. Propagates
            unchanged from JournalService.create_journal_entry.
        ValidationAppError: VALIDATION_ERROR if the entry fails domain
            validation (unbalanced totals, future posting date, invalid
            line amounts, etc.).
    """
    service = await ctx.get_journal_service()
    return await service.create_journal_entry(dto, actor=PRE_AUTH_ACTOR)


async def get_journal_entry_handler(
    ctx: CliContext,
    journal_number: int,
) -> JournalViewModel:
    """Look up a single journal entry by its journal number.

    Args:
        ctx: The CliContext for this invocation.
        journal_number: The journal number to look up, as typed or
            prompted.

    Returns:
        The view model for the matching journal entry.

    Raises:
        AppError: UNKNOWN_JOURNAL_ENTRY if no entry has that number.
    """
    service = await ctx.get_journal_service()
    return await service.get_journal_entry(journal_number)


async def list_journal_entries_handler(ctx: CliContext) -> list[JournalViewModel]:
    """List every journal entry.

    Args:
        ctx: The CliContext for this invocation.

    Returns:
        All journal entries as view models, ordered ascending by
        journal number. Empty if none have been created.
    """
    service = await ctx.get_journal_service()
    return await service.list_journal_entries()
