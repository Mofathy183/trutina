"""Identity primitives shared by every authentication contract.

Defines the authenticated-caller identity and the per-write access
state. Part of ``trutina-authentication``; must not import from
``trutina.core``, storage packages or presentation frameworks.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Identity:
    """The authenticated principal a request or command acts as.

    Carries only the stable subject id: no email and no roles, so an
    identity never goes stale when a profile changes. Roles arrive with
    authorization in a later milestone. Callers turn it into the opaque
    ``actor`` string handed to core write services; core never sees this
    type.

    Attributes:
        subject_id: Stable identifier of the user.
    """

    subject_id: UUID


@dataclass(frozen=True, slots=True)
class AccessState:
    """What is checked about a user on every write.

    A small object rather than a bare boolean so that adding a role later
    extends the same per-write query instead of changing every write path.

    Attributes:
        is_active: Whether the user may currently perform writes.
    """

    is_active: bool
