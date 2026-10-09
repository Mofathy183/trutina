"""Actor passed to journal and posting writes in tests.

Core requires a non-blank, caller-supplied actor on write methods. Tests
use this one constant instead of repeating a literal.
"""

TEST_ACTOR = "system:test"
