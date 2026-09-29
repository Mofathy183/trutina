"""
Service layer for the journal feature.

JournalService coordinates journal-entry workflows and serves as the
only entry point for creating, retrieving, and listing journal entries.

Responsibilities:

- Validate account references against the chart of accounts.
- Assign journal numbers via the repository.
- Construct domain JournalLine and JournalEntry models from service DTOs.
- Coordinate persistence through JournalRepo.
- Translate domain validation failures into ValidationAppError.
- Return stable ViewModels to callers.
- Log "journal.created" through the standard library's logging module
    once a new entry is persisted -- never on a read, never on a path
    that raises AppError/ValidationAppError. This module imports
    nothing from trutina.observability or structlog.

CLI commands and API routes depend only on this service and the
DTO contracts defined in dtos.py. They never interact directly with
JournalLine, JournalEntry, JournalRepo, or AccountService.
"""

import logging

from pydantic import ValidationError
from trutina.core.account.service import AccountService
from trutina.shared.errors import (
    AppError,
    ErrorCode,
    ValidationAppError,
)

from .dtos import (
    CreateJournalInput,
    JournalLineInput,
    JournalLineViewModel,
    JournalViewModel,
)
from .repo import JournalRepo
from .schemas.journal import JournalEntry
from .schemas.line import JournalLine

logger = logging.getLogger(__name__)


class JournalService:
    """Coordinates journal-entry workflows.

    JournalService is responsible for enforcing cross-aggregate business
    rules that involve more than the journal domain alone, including
    account-existence validation before entry construction. Persistence
    is delegated to the configured JournalRepo implementation, and
    account resolution is delegated to AccountService.

    Attributes:
        _repo: The persistence boundary for journal entries.
        _account_service: Used to resolve account references against the
            current chart of accounts.
    """

    def __init__(
        self,
        repo: JournalRepo,
        account_service: AccountService,
    ) -> None:
        """Initialize the service with injected dependencies.

        Args:
            repo: Repository implementation used for journal persistence.
            account_service: Used to resolve account references against
                the chart of accounts. Called once per create operation
                to obtain a consistent chart snapshot.
        """
        self._repo = repo
        self._account_service = account_service

    async def create_journal_entry(
        self,
        input: CreateJournalInput,
    ) -> JournalViewModel:
        """Validate and persist a new journal entry.

        Resolves all account references against a single chart snapshot,
        assigns the next journal number, constructs the domain entry
        (which validates its own accounting invariants), and persists it.
        Logs "journal.created" only after the repository write succeeds.

        Args:
            input: Raw journal entry creation input.

        Returns:
            The view model of the newly created journal entry.

        Raises:
            AppError: UNKNOWN_ACCOUNT if any line references an account
                that does not exist in the chart of accounts.
            ValidationAppError: If the journal entry fields are
                structurally invalid (unbalanced totals, future date,
                invalid line amounts, etc.).
        """
        await self._validate_accounts(input.lines)

        journal_number = await self._repo.next_journal_number()

        try:
            lines = self._build_lines(input.lines)
            entry = JournalEntry(
                journal_number=journal_number,
                posting_date=input.posting_date,
                lines=lines,
                description=input.description,
            )
        except ValidationError as exc:
            raise ValidationAppError.validation(exc) from exc

        await self._repo.save(entry)

        logger.info(
            "journal.created",
            extra={
                "context": {
                    "journal_number": entry.journal_number,
                    "line_count": len(entry.lines),
                }
            },
        )

        return self._to_entry_view(entry)

    async def get_journal_entry(
        self,
        journal_number: int,
    ) -> JournalViewModel:
        """Fetch a single journal entry by its journal number.

        Read-only -- never logs a state-change event.

        Args:
            journal_number: The journal number to look up.

        Returns:
            The view model for the matching journal entry.

        Raises:
            AppError: UNKNOWN_JOURNAL_ENTRY if no entry has that number.
        """
        entry = await self._repo.get_by_number(journal_number)

        if entry is None:
            raise AppError.not_found(
                code=ErrorCode.UNKNOWN_JOURNAL_ENTRY,
                resource="journal_entry",
                identifier=str(journal_number),
            )

        return self._to_entry_view(entry)

    async def list_journal_entries(self) -> list[JournalViewModel]:
        """Fetch all journal entries as a list of view models.

        Returns an empty list when no entries have been persisted.
        Read-only -- never logs a state-change event.

        Returns:
            All persisted journal entries ordered ascending by journal
            number.
        """
        entries = await self._repo.list_entries()

        return [self._to_entry_view(entry) for entry in entries]

    async def _validate_accounts(
        self,
        lines: list[JournalLineInput],
    ) -> None:
        """Verify that every line references a known account.

        Loads the chart of accounts once and resolves all account
        references against the same snapshot. Fails fast on the first
        unresolved reference.

        The chart is loaded once rather than resolving each reference
        individually to avoid multiple round-trips to the repository and
        to guarantee that all references are validated against a
        consistent view of the chart.

        Args:
            lines: The journal line inputs whose account references
                should be validated.

        Raises:
            AppError: UNKNOWN_ACCOUNT if any account reference does not
                resolve to a known account in the chart.
        """
        chart = await self._account_service.get_chart()

        for line in lines:
            if chart.get_by_name(line.account) is None:
                raise AppError.not_found(
                    code=ErrorCode.UNKNOWN_ACCOUNT,
                    resource="account",
                    identifier=line.account,
                )

    def _build_lines(
        self,
        lines: list[JournalLineInput],
    ) -> list[JournalLine]:
        """Map journal line input DTOs to domain JournalLine objects.

        Constructs one JournalLine per input. Domain validators fire
        during construction and any resulting ValidationError is allowed
        to propagate to the caller for translation.

        Args:
            lines: The line inputs to map.

        Returns:
            A list of validated JournalLine domain objects.
        """
        return [
            JournalLine(
                account=line.account,
                debit_amount=line.debit_amount,
                credit_amount=line.credit_amount,
            )
            for line in lines
        ]

    def _to_line_view(self, line: JournalLine) -> JournalLineViewModel:
        """Build a JournalLineViewModel from a domain JournalLine.

        Args:
            line: The validated domain JournalLine.

        Returns:
            The read-only view model for this line.
        """
        return JournalLineViewModel(
            account=line.account,
            debit_amount=line.debit_amount,
            credit_amount=line.credit_amount,
        )

    def _to_entry_view(self, entry: JournalEntry) -> JournalViewModel:
        """Build a JournalViewModel from a domain JournalEntry.

        Args:
            entry: The validated domain JournalEntry.

        Returns:
            The read-only view model for this entry.
        """
        return JournalViewModel(
            journal_number=entry.journal_number,
            posting_date=entry.posting_date,
            description=entry.description,
            lines=[self._to_line_view(line) for line in entry.lines],
            total_debits=entry.total_debits,
            total_credits=entry.total_credits,
            is_balanced=entry.is_balanced,
        )
