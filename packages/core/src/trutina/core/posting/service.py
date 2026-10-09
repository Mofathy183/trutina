"""
Service layer for the posting feature.

PostingService derives ledger postings from an already-validated
JournalEntry and persists them through PostingRepo. It is the only
entry point for converting a journal entry into its posted ledger
effect.

Responsibilities:

- Require a non-blank, caller-supplied actor before any other work.
- Retrieve the journal entry by number via JournalService.
- Enforce the one-posting-per-journal-entry invariant.
- Derive one LedgerPosting per journal line on the entry.
- Persist the derived postings through PostingRepo.
- Return stable PostingViewModels to callers.
- Log "posting.created" through the standard library's logging module
    once a batch of postings is persisted -- one line per
    post_journal_entry() call, never per individual posting, never on
    a read, and never on a path that raises AppError. This module
    imports nothing from trutina.observability or structlog.

PostingService does not validate account references (enforced upstream
by JournalService via AccountService) and does not construct
JournalEntry instances. It trusts that any entry returned by
JournalService is fully validated.
"""

import logging

from trutina.core.journal.service import JournalService
from trutina.shared.errors import AppError, ErrorCode, ValidationAppError
from trutina.shared.rule import is_non_blank_actor

from .dtos import PostingViewModel
from .repo import PostingRepo
from .schemas.ledger_posting import LedgerPosting

logger = logging.getLogger(__name__)


class PostingService:
    """Coordinates posting-derivation workflows.

    PostingService turns a balanced JournalEntry into its individual
    ledger postings and persists them. Account validation and journal
    construction both happen upstream, before a JournalEntry ever
    reaches this service via JournalService.

    Attributes:
        _repo: The persistence boundary for ledger postings.
        _journal_service: Used to retrieve journal entries by number.
    """

    def __init__(
        self,
        repo: PostingRepo,
        journal_service: JournalService,
    ) -> None:
        """Initialize the service with injected dependencies.

        Args:
            repo: Repository implementation used for posting persistence.
            journal_service: Used to retrieve journal entries by number.
        """
        self._repo = repo
        self._journal_service = journal_service

    async def post_journal_entry(
        self,
        journal_number: int,
        *,
        actor: str,
    ) -> list[PostingViewModel]:
        """Derive and persist postings for a validated journal entry.

        Rejects a blank actor first, so a rejected call reads nothing from
        the journal or the posting repository. Then retrieves the journal
        entry by number, verifies it has not already been posted, builds one
        LedgerPosting per line, persists the batch in a single repository
        call, and returns PostingViewModels. Logs "posting.created" once,
        for the whole batch, only after the repository write succeeds.
        The repository's transaction guarantees, if any, are adapter-specific.

        Args:
            journal_number: The journal number of the entry to post.
            actor: Opaque identifier of the caller performing the write. It
                must contain at least one non-whitespace character; its
                format is not inspected here. It is checked for presence
                only: it is not persisted or logged.

        Returns:
            The view models of the newly created postings, in the same
            order as the entry's lines.

        Raises:
            ValidationAppError: REQUIRED_FIELD on ``actor`` if it is blank.
            AppError: UNKNOWN_JOURNAL_ENTRY if no entry has that number.
            AppError: JOURNAL_ALREADY_POSTED if postings already exist
                for this journal entry.
        """
        if not is_non_blank_actor(actor):
            raise ValidationAppError.required_field("actor", actor)

        entry = await self._journal_service.get_journal_entry(journal_number)

        existing = await self._repo.get_by_journal_number(journal_number)
        if existing:
            raise AppError.conflict(
                code=ErrorCode.JOURNAL_ALREADY_POSTED,
                resource="journal_entry",
                field_name="journal_number",
                value=str(journal_number),
            )

        postings = self._derive_postings(entry)

        await self._repo.save_many(postings)

        logger.info(
            "posting.created",
            extra={
                "context": {
                    "journal_number": journal_number,
                    "line_count": len(postings),
                }
            },
        )

        return [self._to_view_model(posting) for posting in postings]

    async def get_postings_by_account(
        self,
        account: str,
    ) -> list[PostingViewModel]:
        """Retrieve all postings for a given account.

        Read-only -- never logs a state-change event.

        Args:
            account: The account name to look up. Matching is
                case-insensitive and follows the chart's canonical
                lookup rules.

        Returns:
            All postings recorded against that account.
        """
        postings = await self._repo.get_by_account(account)
        return [self._to_view_model(p) for p in postings]

    async def get_postings_by_journal_number(
        self,
        journal_number: int,
    ) -> list[PostingViewModel]:
        """Retrieve all postings derived from a specific journal entry.

        Read-only -- never logs a state-change event.

        Args:
            journal_number: The journal number to look up.

        Returns:
            All postings derived from that journal entry, in the order
            they were originally saved.
        """
        postings = await self._repo.get_by_journal_number(journal_number)
        return [self._to_view_model(p) for p in postings]

    def _derive_postings(self, entry) -> list[LedgerPosting]:
        """Map each journal line on the entry to a domain LedgerPosting.

        Each posting inherits journal_number and posting_date from the
        entry itself, since a posting is the ledger-side effect of a
        single journal line within that entry.

        Args:
            entry: The JournalViewModel whose lines should be posted.

        Returns:
            One LedgerPosting per line on the entry, in line order.
        """
        return [
            LedgerPosting(
                account=line.account,
                debit_amount=line.debit_amount,
                credit_amount=line.credit_amount,
                journal_number=entry.journal_number,
                posting_date=entry.posting_date,
            )
            for line in entry.lines
        ]

    @staticmethod
    def _to_view_model(posting: LedgerPosting) -> PostingViewModel:
        """Build a PostingViewModel from a domain LedgerPosting.

        Debit postings carry a non-None debit_amount and a None
        credit_amount. Credit postings carry a non-None credit_amount
        and a None debit_amount. ``is_debit`` is derived automatically
        by PostingViewModel from the amount fields.

        Args:
            posting: The validated domain LedgerPosting.

        Returns:
            The read-only view model for this posting.
        """
        return PostingViewModel(
            account=posting.account,
            debit_amount=posting.debit_amount if posting.is_debit else None,
            credit_amount=posting.credit_amount if not posting.is_debit else None,
            journal_number=posting.journal_number,
            posting_date=posting.posting_date,
        )
