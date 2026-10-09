"""Input DTO -> JournalService call -> ViewModel for the journal feature.

Each handler is exactly one service call, per
`Trutina API Feature & Testing Prompt` Section 2/3: no FastAPI import,
no Mapper/Presenter construction, no exception handling. Any
``AppError``/``ValidationAppError`` raised by ``JournalService``
propagates uncaught -- ``api/shared/errors/handlers.py`` is the single
translation seam for all of it.

Every function here is a plain ``async def`` callable identically from
a router or directly from a unit test against a fake-repo-backed
``JournalService`` -- mirroring the CLI's own ``handler.py`` contract
and the account feature's API handler.
"""

from trutina.api.shared.actor import PRE_AUTH_ACTOR
from trutina.core.journal.dtos import CreateJournalInput, JournalViewModel
from trutina.core.journal.service import JournalService


async def create_journal_entry(
    service: JournalService, dto: CreateJournalInput
) -> JournalViewModel:
    """Create a new journal entry.

    The write is attributed to the API's fixed pre-auth actor
    (``PRE_AUTH_ACTOR``); the request carries no identity.

    Args:
        service: The resolved ``JournalService`` instance.
        dto: Validated journal-entry creation input.

    Returns:
        The view model of the newly created journal entry.

    Raises:
        AppError: UNKNOWN_ACCOUNT if any line references an account
            that does not exist in the chart of accounts.
        ValidationAppError: VALIDATION_ERROR if the entry fields are
            structurally invalid (unbalanced totals, future date,
            invalid line amounts, etc.).
    """
    return await service.create_journal_entry(dto, actor=PRE_AUTH_ACTOR)


async def get_journal_entry(
    service: JournalService, journal_number: int
) -> JournalViewModel:
    """Fetch a single journal entry by its journal number.

    Args:
        service: The resolved ``JournalService`` instance.
        journal_number: The journal number to look up.

    Returns:
        The view model for the matching journal entry.

    Raises:
        AppError: UNKNOWN_JOURNAL_ENTRY if no entry has that number.
    """
    return await service.get_journal_entry(journal_number)


async def list_journal_entries(service: JournalService) -> list[JournalViewModel]:
    """Fetch every persisted journal entry.

    Args:
        service: The resolved ``JournalService`` instance.

    Returns:
        All persisted journal entries ordered ascending by journal
        number. Empty list when none exist.
    """
    return await service.list_journal_entries()
