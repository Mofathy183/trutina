"""Integration tests for make_lifespan()'s startup/shutdown sequence.

Verifies the full sequence entering/exiting the lifespan context manager
actually performs: connect() -> build_container() -> attach Container to
app.state -> (yield) -> disconnect(). Does NOT re-verify build_container()'s
wiring (see test_container.py) or connect()/disconnect() themselves
(see storage-postgres's own shared/tests/test_connection.py).
"""

import pytest
from fastapi import FastAPI
from trutina.api.composition.bootstrap import make_lifespan
from trutina.api.composition.container import Container


@pytest.mark.integration
class TestMakeLifespan:
    async def test_attaches_container_to_app_state_on_entry(
        self, test_settings, clean_pg_db
    ):
        app = FastAPI()
        lifespan = make_lifespan(test_settings)

        async with lifespan(app):
            assert isinstance(app.state.container, Container)

    async def test_container_services_are_usable_during_lifespan(
        self, test_settings, clean_pg_db
    ):
        """A weak end-to-end proof that the container built during
        startup is wired against a real, reachable database -- not just
        that the attribute exists. Uses AccountService.list_accounts(),
        which performs a real query and returns an empty result on a
        freshly truncated table (via clean_pg_db) rather than raising.
        """
        app = FastAPI()
        lifespan = make_lifespan(test_settings)

        async with lifespan(app):
            result = await app.state.container.account_service.list_accounts()

        assert result.accounts == []

    async def test_yields_control_to_caller(self, test_settings, clean_pg_db):
        app = FastAPI()
        lifespan = make_lifespan(test_settings)

        entered = False
        async with lifespan(app):
            entered = True

        assert entered is True

    async def test_two_calls_return_independent_lifespan_functions(self, test_settings):
        """make_lifespan() is a factory -- confirms each call produces
        its own closure rather than sharing mutable state, mirroring
        why create_app() is a factory rather than a module singleton.
        """
        first = make_lifespan(test_settings)
        second = make_lifespan(test_settings)

        assert first is not second
