"""Application handlers for the posting API.

Each handler coordinates a single posting workflow by delegating to
``PostingService``. Handlers define the boundary between the API layer
and the application layer, leaving request mapping, response
presentation, and error translation to their respective components.
"""

from trutina.api.shared.actor import PRE_AUTH_ACTOR
from trutina.core.posting.dtos import PostingViewModel
from trutina.core.posting.service import PostingService


async def post_journal_entry_handler(
    service: PostingService,
    journal_number: int,
) -> list[PostingViewModel]:
    """Post a journal entry and return the derived ledger postings.

    Posting converts a balanced journal entry into the immutable ledger
    history by creating one posting for each journal line. The write is
    attributed to the API's fixed pre-auth actor (``PRE_AUTH_ACTOR``);
    the request carries no identity.

    Args:
        service: The posting service coordinating the workflow.
        journal_number: The journal entry to post.

    Returns:
        The postings derived from the journal entry.

    Raises:
        AppError: If the journal entry does not exist or has already
            been posted.
    """
    return await service.post_journal_entry(journal_number, actor=PRE_AUTH_ACTOR)


async def get_postings_by_account_handler(
    service: PostingService,
    account: str,
) -> list[PostingViewModel]:
    """Retrieve the ledger postings recorded against an account.

    Args:
        service: The posting service coordinating the workflow.
        account: The account whose posting history should be retrieved.

    Returns:
        The postings recorded against the requested account.
    """
    return await service.get_postings_by_account(account)


async def get_postings_by_journal_number_handler(
    service: PostingService,
    journal_number: int,
) -> list[PostingViewModel]:
    """Retrieve the postings derived from a journal entry.

    Args:
        service: The posting service coordinating the workflow.
        journal_number: The journal entry whose postings should be retrieved.

    Returns:
        The postings derived from the requested journal entry.
    """
    return await service.get_postings_by_journal_number(journal_number)
