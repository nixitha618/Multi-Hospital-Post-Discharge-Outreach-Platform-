import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from backend.app.main import app

@pytest.mark.asyncio
async def test_tenant_isolation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Request with Metro General Hospital tenant header
        res_mgh = await ac.get("/api/campaigns", headers={"X-Tenant-ID": "hosp-mgh"})
        assert res_mgh.status_code == 200
        mgh_campaigns = res_mgh.json()
        assert len(mgh_campaigns) > 0
        for c in mgh_campaigns:
            assert c["hospital_id"] == "hosp-mgh"

        # Request with St. Jude Memorial Health tenant header
        res_sjm = await ac.get("/api/campaigns", headers={"X-Tenant-ID": "hosp-sjm"})
        assert res_sjm.status_code == 200
        sjm_campaigns = res_sjm.json()
        for c in sjm_campaigns:
            assert c["hospital_id"] == "hosp-sjm"

        # Verify patients isolated
        res_pats_mgh = await ac.get("/api/patients", headers={"X-Tenant-ID": "hosp-mgh"})
        assert res_pats_mgh.status_code == 200
        for p in res_pats_mgh.json():
            assert p["hospital_id"] == "hosp-mgh"
