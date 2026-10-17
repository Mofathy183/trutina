import pytest


@pytest.mark.integration
class TestCreateAppServesRequests:
    async def test_served_request_smoke_test(self, real_api_client):
        """Proves the full lifespan sequence -- connect,
        attach container -- actually results in an app that can serve a
        request, not just construct without error.

        No feature routers exist yet (create_app() only attaches the
        lifespan; there is no app.include_router() call anywhere in
        source), so this hits FastAPI's own built-in OpenAPI docs route
        rather than an application route, purely to prove the ASGI app
        is servable end to end. Once a real route exists,
        prefer hitting that instead.
        """
        response = await real_api_client.get("/docs")

        assert response.status_code == 200

    async def test_container_is_attached_after_startup(self, real_api_app):
        from trutina.api.composition.container import Container

        assert isinstance(real_api_app.state.container, Container)
