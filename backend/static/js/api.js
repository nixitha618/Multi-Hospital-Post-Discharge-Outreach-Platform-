// Vanilla JavaScript API Client for Multi-Hospital Post-Discharge Platform
class ApiClient {
  constructor() {
    this.tenantId = 'hosp-mgh';
    this.userRole = 'CAMPAIGN_MANAGER';
    this.userId = 'usr-demo';
    this.baseUrl = '/api';
  }

  setContext(tenantId, role, userId) {
    this.tenantId = tenantId;
    this.userRole = role;
    this.userId = userId || `usr-${role.toLowerCase()}`;
  }

  getHeaders() {
    return {
      'Content-Type': 'application/json',
      'X-Tenant-ID': this.tenantId,
      'X-User-Role': this.userRole,
      'X-User-Id': this.userId
    };
  }

  async getHospitals() {
    const res = await fetch(`${this.baseUrl}/hospitals`, { headers: this.getHeaders() });
    return res.json();
  }

  async getCampaigns() {
    const res = await fetch(`${this.baseUrl}/campaigns`, { headers: this.getHeaders() });
    return res.json();
  }

  async setCampaignStatus(campaignId, status) {
    const res = await fetch(`${this.baseUrl}/campaigns/${campaignId}/status?new_status=${status}`, {
      method: 'POST',
      headers: this.getHeaders()
    });
    return res.json();
  }

  async getConcurrency() {
    const res = await fetch(`${this.baseUrl}/queue/concurrency`, { headers: this.getHeaders() });
    return res.json();
  }

  async getTasks(statusFilter, campaignId) {
    let url = `${this.baseUrl}/queue/tasks?limit=50`;
    if (statusFilter) url += `&status_filter=${statusFilter}`;
    if (campaignId) url += `&campaign_id=${campaignId}`;
    const res = await fetch(url, { headers: this.getHeaders() });
    return res.json();
  }

  async dispatchNext() {
    const res = await fetch(`${this.baseUrl}/queue/dispatch-next`, {
      method: 'POST',
      headers: this.getHeaders()
    });
    return res.json();
  }

  async triggerReaper() {
    const res = await fetch(`${this.baseUrl}/queue/reap`, {
      method: 'POST',
      headers: this.getHeaders()
    });
    return res.json();
  }

  async startCall(taskId) {
    const res = await fetch(`${this.baseUrl}/calls/start`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ task_id: taskId, worker_id: 'browser-evaluator' })
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Failed to initiate call (HTTP ${res.status})`);
    }
    return res.json();
  }

  async sendCallTurn(callId, speech) {
    const res = await fetch(`${this.baseUrl}/calls/turn`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ call_id: callId, patient_speech: speech })
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Failed to send speech (HTTP ${res.status})`);
    }
    return res.json();
  }

  async finishCall(callId, outcome) {
    let url = `${this.baseUrl}/calls/${callId}/finish`;
    if (outcome) url += `?simulated_outcome=${outcome}`;
    const res = await fetch(url, {
      method: 'POST',
      headers: this.getHeaders()
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Failed to finish call (HTTP ${res.status})`);
    }
    return res.json();
  }

  async finishCallByTask(taskId, outcome) {
    let url = `${this.baseUrl}/calls/task/${taskId}/finish`;
    if (outcome) url += `?simulated_outcome=${outcome}`;
    const res = await fetch(url, {
      method: 'POST',
      headers: this.getHeaders()
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Failed to finish call (HTTP ${res.status})`);
    }
    return res.json();
  }

  async getEscalations(statusFilter) {
    let url = `${this.baseUrl}/escalations`;
    if (statusFilter && statusFilter !== 'ALL') url += `?status_filter=${statusFilter}`;
    const res = await fetch(url, { headers: this.getHeaders() });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Failed to fetch escalations (HTTP ${res.status})`);
    }
    return res.json();
  }

  async assignEscalation(id, reviewerId, reviewerName) {
    const res = await fetch(`${this.baseUrl}/escalations/${id}/assign`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ reviewer_id: reviewerId, reviewer_name: reviewerName })
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Failed to assign escalation (HTTP ${res.status})`);
    }
    return res.json();
  }

  async resolveEscalation(id, notes, action, reviewerName) {
    const res = await fetch(`${this.baseUrl}/escalations/${id}/resolve`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ resolution_notes: notes, resolution_action: action, reviewer_name: reviewerName })
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Failed to resolve escalation (HTTP ${res.status})`);
    }
    return res.json();
  }

  async initSimulation() {
    const res = await fetch(`${this.baseUrl}/simulation/init`, {
      method: 'POST',
      headers: this.getHeaders()
    });
    return res.json();
  }

  async stepSimulation() {
    const res = await fetch(`${this.baseUrl}/simulation/step`, {
      method: 'POST',
      headers: this.getHeaders()
    });
    return res.json();
  }

  async runSafetyBenchmark() {
    const res = await fetch(`${this.baseUrl}/safety/benchmark`, { headers: this.getHeaders() });
    return res.json();
  }

  async getHealth() {
    const res = await fetch(`${this.baseUrl}/health`, { headers: this.getHeaders() });
    return res.json();
  }

  async getEhrRecords() {
    const res = await fetch(`${this.baseUrl}/ehr/records`, { headers: this.getHeaders() });
    return res.json();
  }

  async toggleEhrFailure(enable) {
    const res = await fetch(`${this.baseUrl}/ehr/simulate-failure?enable=${enable}`, {
      method: 'POST',
      headers: this.getHeaders()
    });
    return res.json();
  }

  async getAuditLogs() {
    const res = await fetch(`${this.baseUrl}/audit`, { headers: this.getHeaders() });
    return res.json();
  }

  async getPatientTimeline(patientId) {
    const res = await fetch(`${this.baseUrl}/patients/${patientId}/timeline`, { headers: this.getHeaders() });
    return res.json();
  }

  async getPatientOperationalView(patientId) {
    const res = await fetch(`${this.baseUrl}/patients/${patientId}/operational-view`, { headers: this.getHeaders() });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Failed to load patient operational view`);
    }
    return res.json();
  }

  async getHospitalAnalytics() {
    const res = await fetch(`${this.baseUrl}/analytics/hospital`, { headers: this.getHeaders() });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Failed to load hospital analytics`);
    }
    return res.json();
  }

  async getPlatformAnalytics() {
    const res = await fetch(`${this.baseUrl}/analytics/platform`, { headers: this.getHeaders() });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Failed to load platform analytics`);
    }
    return res.json();
  }

  async reprioritizeCampaign(campaignId, priorityLevel, allocatedCapacity) {
    const res = await fetch(`${this.baseUrl}/campaigns/${campaignId}/reprioritize`, {
      method: 'PATCH',
      headers: this.getHeaders(),
      body: JSON.stringify({ priority_level: priorityLevel, allocated_capacity: allocatedCapacity })
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Failed to reprioritize campaign`);
    }
    return res.json();
  }

  async getProtocols() {
    const res = await fetch(`${this.baseUrl}/protocols`, { headers: this.getHeaders() });
    if (!res.ok) return [];
    return res.json();
  }
}

const api = new ApiClient();
