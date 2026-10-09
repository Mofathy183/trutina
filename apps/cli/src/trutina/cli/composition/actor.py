"""Pre-authentication actor for the CLI's write commands.

Journal and posting writes require a caller-supplied actor. CLI commands
carry no authenticated identity, so every write is attributed to this
fixed constant. The ``system:`` prefix marks a non-user writer and the
suffix records the writing application, so rows attributed to this value
can be told apart from rows written elsewhere. Core checks only that the
actor is non-blank.
"""

PRE_AUTH_ACTOR = "system:pre-auth:cli"
