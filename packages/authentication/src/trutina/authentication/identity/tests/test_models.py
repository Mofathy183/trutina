import dataclasses
from uuid import uuid4

import pytest
from trutina.authentication import AccessState, Identity


@pytest.mark.unit
class TestIdentity:
    def test_is_frozen(self):
        identity = Identity(subject_id=uuid4())

        with pytest.raises(dataclasses.FrozenInstanceError):
            identity.subject_id = uuid4()  # ty: ignore[invalid-assignment]

    def test_equal_when_subject_matches(self):
        subject = uuid4()

        assert Identity(subject) == Identity(subject)

    def test_carries_only_the_subject_id(self):
        assert [f.name for f in dataclasses.fields(Identity)] == ["subject_id"]


@pytest.mark.unit
class TestAccessState:
    def test_is_frozen(self):
        state = AccessState(is_active=True)

        with pytest.raises(dataclasses.FrozenInstanceError):
            state.is_active = False  # ty: ignore[invalid-assignment]
