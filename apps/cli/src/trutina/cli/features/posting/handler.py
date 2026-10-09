"""Application-level use cases for the Posting CLI feature.

Mirrors cli/features/account/handler.py and cli/features/journal/handler.py:
a handler accepts an already-validated value (here, a plain int or str
rather than a DTO, per parser.py's module docstring) and knows nothing
about Typer, Click, or terminal presentation. Every handler resolves
PostingService lazily from the supplied CliContext.
"""

from trutina.cli.composition.actor import PRE_AUTH_ACTOR
from trutina.cli.composition.context import CliContext
from trutina.core.posting import PostingViewModel


async def post_journal_entry_handler(
    ctx: CliContext,
    journal_number: int,
) -> list[PostingViewModel]:
    """Post a validated journal entry, deriving its ledger postings.

    The write is attributed to the CLI's fixed pre-auth actor
    (``PRE_AUTH_ACTOR``); the command carries no identity.

    Args:
        ctx: The CliContext for this invocation. Callers must pass
            ``state.context``, not the CliState wrapper itself.
        journal_number: The journal number of the entry to post, as
            typed or prompted.

    Returns:
        The view models of the newly created postings, in the same
        order as the entry's lines.

    Raises:
        AppError: UNKNOWN_JOURNAL_ENTRY if no entry has that number.
            JOURNAL_ALREADY_POSTED if postings already exist for this
            journal entry. Both propagate unchanged from
            PostingService.post_journal_entry.
    """
    service = await ctx.get_posting_service()
    return await service.post_journal_entry(journal_number, actor=PRE_AUTH_ACTOR)


async def get_postings_by_account_handler(
    ctx: CliContext,
    account: str,
) -> list[PostingViewModel]:
    """Retrieve all postings recorded against a given account.

    Args:
        ctx: The CliContext for this invocation.
        account: The account name to look up, as typed or prompted.
            Matching is case-insensitive, per PostingService.

    Returns:
        All postings for that account. Empty if none exist — this is
        not treated as an error, since an account may simply have no
        postings yet.
    """
    service = await ctx.get_posting_service()
    return await service.get_postings_by_account(account)


async def get_postings_by_journal_number_handler(
    ctx: CliContext,
    journal_number: int,
) -> list[PostingViewModel]:
    """Retrieve all postings derived from a specific journal entry.

    Args:
        ctx: The CliContext for this invocation.
        journal_number: The journal number to look up, as typed or
            prompted.

    Returns:
        All postings derived from that journal entry. Empty if the
        journal entry hasn't been posted yet — this is not treated as
        an error by PostingService, so this handler doesn't treat it
        as one either.
    """
    service = await ctx.get_posting_service()
    return await service.get_postings_by_journal_number(journal_number)
