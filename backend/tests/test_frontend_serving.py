import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app

@pytest.mark.asyncio
async def test_frontend_serving():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/")
        assert res.status_code == 200
        assert "AegisHealth Operations Platform" in res.text
        assert "html" in res.headers.get("content-type", "")

        # Check static css
        css_res = await ac.get("/static/css/styles.css")
        assert css_res.status_code == 200
        assert "Clinical Operations Styling" in css_res.text

        # Check static js
        js_res = await ac.get("/static/js/api.js")
        assert js_res.status_code == 200
        assert "ApiClient" in js_res.text
