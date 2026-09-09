"""Shared MongoDB base document with automatic timestamp management.

TimestampedDocument provides the common persistence fields shared by all
MongoDB documents in the infrastructure layer. Its insert hook initializes
timestamps for single-document inserts, while batch-write paths must set
timestamps explicitly when their Beanie operation does not invoke hooks.

Timestamp lifecycle
-------------------
- created_at is assigned by the insert hook immediately before a
    single-document insert; batch writers set it themselves where needed.
- updated_at is initialized to the same value on insert and is expected
    to be refreshed by repository write operations on subsequent updates.
- Both timestamps are stored in UTC to provide a consistent time
    reference across environments.

Architectural responsibility
----------------------------
This class belongs entirely to the infrastructure layer. It provides
persistence metadata only and intentionally contains no business rules,
domain validation, or accounting logic.
"""

from datetime import UTC, datetime

from beanie import Document, Insert, before_event


class TimestampedDocument(Document):
    """Base Beanie document providing common audit timestamps.

    All MongoDB persistence models inherit these creation and modification
    fields. The insert hook initializes them for a Beanie ``insert()``;
    batch persistence must initialize them explicitly. The timestamps are
    infrastructure-managed metadata, not domain-model business invariants.

    Attributes:
        created_at: UTC timestamp recorded when the document is first
            inserted into MongoDB.
        updated_at: UTC timestamp representing the most recent write to
            the document.
    """

    created_at: datetime | None = None
    updated_at: datetime | None = None

    @before_event(Insert)
    def initialize_timestamps(self) -> None:
        """Initialize persistence timestamps before the first insert.

        Beanie invokes this hook immediately before a single-document
        insert. Both timestamps receive the same UTC value so newly created
        documents begin with identical creation and modification times.
        Batch persistence paths do not invoke this hook and initialize the
        fields themselves. Repository update operations are responsible for
        advancing ``updated_at`` on subsequent writes.
        """
        now = datetime.now(UTC)
        self.created_at = now
        self.updated_at = now
