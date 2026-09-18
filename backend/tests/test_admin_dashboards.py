import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app

@pytest.mark.asyncio
async def test_hospital_admin_operational_metrics():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = {
            "X-Tenant-ID": "hosp-mgh",
            "X-User-Role": "HOSPITAL_ADMIN",
            "X-User-Id": "usr-admin-mgh"
        }
        res = await ac.get("/api/analytics/hospital", headers=headers)
        assert res.status_code == 200
        data = res.json()
        
        # Verify required hospital-wide KPI visibility
        assert data["hospital_id"] == "hosp-mgh"
        assert "hospital_name" in data
        assert "total_tasks" in data
        assert "contact_rate_pct" in data
        assert "escalation_rate_pct" in data
        assert "ehr_status" in data
        assert "ehr_synced_count" in data
        assert "active_slots" in data
        assert "max_slots" in data
        
        # Verify campaigns breakdown
        assert "campaigns" in data
        assert isinstance(data["campaigns"], list)
        if len(data["campaigns"]) > 0:
            c = data["campaigns"][0]
            assert "id" in c
            assert "priority_level" in c
            assert "progress_percentage" in c

        # Verify contact outcomes and retry progression
        assert "outcomes" in data
        out = data["outcomes"]
        assert "completed" in out
        assert "escalated" in out
        assert "retry_distribution" in data or "retries" in data
        rd = data.get("retries") or data.get("retry_distribution")
        assert "attempt_1" in rd
        assert "attempt_2" in rd
        assert "attempt_3" in rd
        assert "exhausted_max" in rd

        # Verify staff activity audit trail
        assert "recent_staff_activity" in data
        assert isinstance(data["recent_staff_activity"], list)

@pytest.mark.asyncio
async def test_hospital_admin_multi_tenant_isolation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        for tenant in ["hosp-mgh", "hosp-sjm", "hosp-pcm"]:
            res = await ac.get(
                "/api/analytics/hospital",
                headers={"X-Tenant-ID": tenant, "X-User-Role": "HOSPITAL_ADMIN"}
            )
            assert res.status_code == 200
            data = res.json()
            assert data["hospital_id"] == tenant

@pytest.mark.asyncio
async def test_platform_admin_fleet_dashboard():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = {
            "X-Tenant-ID": "hosp-mgh",
            "X-User-Role": "PLATFORM_ADMIN",
            "X-User-Id": "usr-platform-super"
        }
        res = await ac.get("/api/analytics/platform", headers=headers)
        assert res.status_code == 200
        data = res.json()

        # Verify aggregate cross-hospital fleet visibility
        assert data["total_hospitals"] == 3
        assert data["total_campaigns"] >= 2
        assert "fleet_active_calls" in data
        assert "fleet_max_capacity" in data
        assert "fleet_capacity_utilization_pct" in data
        assert "total_pending_queue" in data
        assert "total_completed_outreach" in data
        assert "total_platform_escalations" in data

        # Verify AI Observability
        assert "ai_usage" in data
        ai = data["ai_usage"]
        assert "consensus_agreement_rate_pct" in ai
        assert "average_latency_ms" in ai
        assert "total_tokens_consumed" in ai
        assert "estimated_cost_usd" in ai

        # Verify multi-hospital comparison table items
        assert "hospitals" in data
        assert len(data["hospitals"]) == 3
        hosp_ids = [h["hospital_id"] for h in data["hospitals"]]
        assert "hosp-mgh" in hosp_ids
        assert "hosp-sjm" in hosp_ids
        assert "hosp-pcm" in hosp_ids

        # Ensure no cross-hospital PHI leak in platform fleet response
        content_str = res.text.lower()
        assert "steven lopez" not in content_str
        assert "dorothy" not in content_str

@pytest.mark.asyncio
async def test_campaign_reprioritization_control():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = {
            "X-Tenant-ID": "hosp-mgh",
            "X-User-Role": "CAMPAIGN_MANAGER",
            "X-User-Id": "usr-cm-01"
        }
        
        # Fetch existing campaigns
        camps_res = await ac.get("/api/campaigns", headers=headers)
        assert camps_res.status_code == 200
        camps = camps_res.json()
        assert len(camps) > 0
        target_camp = camps[0]
        camp_id = target_camp["id"]

        # Reprioritize campaign to priority 5 and capacity 4
        patch_res = await ac.patch(
            f"/api/campaigns/{camp_id}/reprioritize",
            json={"priority_level": 5, "allocated_capacity": 4},
            headers=headers
        )
        assert patch_res.status_code == 200
        updated = patch_res.json()
        assert updated["priority_level"] == 5
        assert updated["allocated_capacity"] == 4

        # Verify audit log recorded the reprioritization action
        audit_res = await ac.get("/api/audit", headers=headers)
        assert audit_res.status_code == 200
        audits = audit_res.json()
        reprioritize_actions = [a for a in audits if a["action"] == "CAMPAIGN_REPRIORITIZED"]
        assert len(reprioritize_actions) > 0
        assert reprioritize_actions[0]["target_id"] == camp_id
        assert reprioritize_actions[0]["target_entity"] == "OutreachCampaign"

@pytest.mark.asyncio
async def test_patient_operational_view_360():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = {
            "X-Tenant-ID": "hosp-mgh",
            "X-User-Role": "CLINICAL_REVIEWER",
            "X-User-Id": "usr-nurse-01"
        }
        
        # Get tasks to find an MGH patient
        tasks_res = await ac.get("/api/queue/tasks", headers=headers)
        assert tasks_res.status_code == 200
        tasks = tasks_res.json()
        assert len(tasks) > 0
        patient_id = tasks[0]["patient_id"]

        # Query Patient 360 Operational View
        op_res = await ac.get(f"/api/patients/{patient_id}/operational-view", headers=headers)
        assert op_res.status_code == 200
        p360 = op_res.json()

        assert p360["patient_id"] == patient_id
        assert "mrn" in p360
        assert "full_name" in p360
        assert "encounter" in p360
        enc = p360["encounter"]
        assert "primary_diagnosis" in enc
        assert "discharge_summary" in enc
        assert "calls" in p360
        assert "escalations" in p360
