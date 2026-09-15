from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from trutina.storage_postgres.shared import Base, Money, TimestampedMixin


class _ConcreteTimestamped(TimestampedMixin, Base):
    """A throwaway table used only to exercise TimestampedMixin's mapping.

    Not registered against a real database -- __tablename__ exists only
    because SQLAlchemy's declarative mapping requires one to configure
    mappers, not because this table is ever created.
    """

    __tablename__ = "_test_timestamped"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)


class _ConcreteMoney(Base):
    """A throwaway table used only to exercise the Money type alias."""

    __tablename__ = "_test_money"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    amount: Mapped[Money]


@pytest.mark.unit
class TestNamingConvention:
    def test_metadata_uses_the_shared_naming_convention(self):
        assert Base.metadata.naming_convention["pk"] == "pk_%(table_name)s"

    def test_every_subclass_shares_one_metadata_registry(self):
        assert _ConcreteTimestamped.metadata is Base.metadata
        assert _ConcreteMoney.metadata is Base.metadata


@pytest.mark.unit
class TestTimestampedMixin:
    def test_created_at_column_exists(self):
        column = _ConcreteTimestamped.__table__.columns["created_at"]
        assert column.type.python_type is datetime

    def test_updated_at_column_exists(self):
        column = _ConcreteTimestamped.__table__.columns["updated_at"]
        assert column.type.python_type is datetime

    def test_created_at_is_not_nullable(self):
        column = _ConcreteTimestamped.__table__.columns["created_at"]
        assert column.nullable is False

    def test_updated_at_is_not_nullable(self):
        column = _ConcreteTimestamped.__table__.columns["updated_at"]
        assert column.nullable is False

    def test_created_at_has_a_server_default(self):
        column = _ConcreteTimestamped.__table__.columns["created_at"]
        assert column.server_default is not None

    def test_updated_at_refreshes_via_onupdate(self):
        column = _ConcreteTimestamped.__table__.columns["updated_at"]
        assert column.onupdate is not None

    def test_created_at_has_no_onupdate(self):
        column = _ConcreteTimestamped.__table__.columns["created_at"]
        assert column.onupdate is None


@pytest.mark.unit
class TestMoney:
    def test_maps_to_numeric_18_2(self):
        column = _ConcreteMoney.__table__.columns["amount"]
        assert column.type.precision == 18  # ty: ignore[unresolved-attribute]
        assert column.type.scale == 2  # ty: ignore[unresolved-attribute]

    def test_python_type_is_decimal(self):
        column = _ConcreteMoney.__table__.columns["amount"]
        assert column.type.python_type is Decimal

    def test_is_not_nullable(self):
        column = _ConcreteMoney.__table__.columns["amount"]
        assert column.nullable is False
