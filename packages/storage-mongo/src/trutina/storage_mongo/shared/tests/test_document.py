from datetime import UTC

import pytest
from trutina.infrastructure.mongo.shared import TimestampedDocument


class _ConcreteTimestamped(TimestampedDocument):
    pass


@pytest.mark.unit
class TestTimestampedDocumentDefaults:
    def test_created_at_defaults_to_none(self):
        doc = _ConcreteTimestamped.model_construct()
        assert doc.created_at is None

    def test_updated_at_defaults_to_none(self):
        doc = _ConcreteTimestamped.model_construct()
        assert doc.updated_at is None


@pytest.mark.unit
class TestInitializeTimestamps:
    def test_sets_created_at(self):
        doc = _ConcreteTimestamped.model_construct()
        doc.initialize_timestamps()
        assert doc.created_at is not None

    def test_sets_updated_at(self):
        doc = _ConcreteTimestamped.model_construct()
        doc.initialize_timestamps()
        assert doc.updated_at is not None

    def test_created_at_and_updated_at_are_equal_at_initialization(self):
        doc = _ConcreteTimestamped.model_construct()
        doc.initialize_timestamps()
        assert doc.created_at == doc.updated_at

    def test_created_at_is_timezone_aware(self):
        doc = _ConcreteTimestamped.model_construct()
        doc.initialize_timestamps()
        assert doc.created_at.tzinfo is UTC

    def test_updated_at_is_timezone_aware(self):
        doc = _ConcreteTimestamped.model_construct()
        doc.initialize_timestamps()
        assert doc.updated_at.tzinfo is UTC
