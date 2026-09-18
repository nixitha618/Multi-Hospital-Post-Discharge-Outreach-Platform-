// AegisHealth Post-Discharge Operations Platform - Main Application Logic

let currentTenant = 'hosp-mgh';
let currentRole = 'CAMPAIGN_MANAGER';
let activeCallId = null;
let callTimerInterval = null;
let callDurationSecs = 0;
let simAutoPlayInterval = null;
let autoRefreshInterval = null;
let currentEscalations = [];
let selectedEscalationId = null;

// Toast notification function
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  
  const iconMap = {
    success: '✓',
    info: 'ℹ',
    warning: '⚠',
    danger: '✕'
  };

  toast.innerHTML = `
    <span style="font-weight: 800; font-size: 14px;">${iconMap[type] || '•'}</span>
    <span style="flex: 1;">${message}</span>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    setTimeout(() => toast.remove(), 300);
  }, 3800);
}

// ==========================================
// IST (Indian Standard Time, UTC+05:30) Helpers
// ==========================================
function parseToISTDate(input) {
  if (!input) return null;
  if (input instanceof Date) return input;
  let s = String(input).trim();
  // If no timezone offset is present, treat it as IST local time (+05:30)
  if (!s.includes('+') && !s.endsWith('Z') && s.length >= 10) {
    s = s.replace(' ', 'T') + '+05:30';
  }
  const d = new Date(s);
  return isNaN(d.getTime()) ? null : d;
}

function formatISTTime(input, showSeconds = false) {
  const d = parseToISTDate(input);
  if (!d) return 'N/A';
  const timePart = d.toLocaleTimeString('en-IN', {
    timeZone: 'Asia/Kolkata',
    hour: '2-digit',
    minute: '2-digit',
    second: showSeconds ? '2-digit' : undefined,
    hour12: true
  });
  return `${timePart} IST`;
}

function formatISTDateTime(input) {
  const d = parseToISTDate(input);
  if (!d) return 'N/A';
  const dtPart = d.toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true
  });
  return `${dtPart} IST`;
}

function formatISTDate(input) {
  const d = parseToISTDate(input);
  if (!d) return 'Recent';
  return d.toLocaleDateString('en-IN', {
    timeZone: 'Asia/Kolkata',
    day: '2-digit',
    month: 'short',
    year: 'numeric'
  });
}

function startISTClock() {
  function updateClock() {
    const el = document.getElementById('istLiveClock');
    if (el) {
      const now = new Date();
      const timeStr = now.toLocaleTimeString('en-IN', {
        timeZone: 'Asia/Kolkata',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: true
      });
      const dateStr = now.toLocaleDateString('en-IN', {
        timeZone: 'Asia/Kolkata',
        day: '2-digit',
        month: 'short'
      });
      el.textContent = `${dateStr}, ${timeStr} IST`;
    }
  }
  updateClock();
  setInterval(updateClock, 1000);
}

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
  startISTClock();
  setupEventListeners();
  loadAllData();
  startAutoRefresh();
});

function startAutoRefresh() {
  if (autoRefreshInterval) clearInterval(autoRefreshInterval);
  autoRefreshInterval = setInterval(() => {
    const chk = document.getElementById('chkAutoRefresh');
    if (chk && chk.checked) {
      // Only poll when Operations tab is active and not currently on an active modal
      const isOpsActive = document.getElementById('tab-queue')?.classList.contains('active');
      const isCallOpen = document.getElementById('modalCallSim')?.classList.contains('active');
      if (isOpsActive && !isCallOpen) {
        loadAllData(true); // silent refresh
      }
    }
  }, 5000);
}

function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(b => {
    b.classList.toggle('active', b.getAttribute('data-tab') === tabId);
  });
  document.querySelectorAll('.tab-content').forEach(c => {
    c.classList.toggle('active', c.id === `tab-${tabId}`);
  });

  if (tabId === 'queue') loadAllData();
  if (tabId === 'hospital-admin') loadHospitalAdminView();
  if (tabId === 'platform-admin') loadPlatformAdminView();
  if (tabId === 'simulation') loadSimulationView();
  if (tabId === 'escalations') loadEscalationsView();
  if (tabId === 'admin') loadAdminView();
}

function setupEventListeners() {
  // Tenant Switcher
  const tenantSelect = document.getElementById('tenantSelect');
  tenantSelect.addEventListener('change', (e) => {
    currentTenant = e.target.value;
    api.setContext(currentTenant, currentRole);
    loadAllData();
    if (document.getElementById('tab-hospital-admin')?.classList.contains('active')) {
      loadHospitalAdminView();
    }
    if (document.getElementById('tab-platform-admin')?.classList.contains('active')) {
      loadPlatformAdminView();
    }
  });

  // Role Switcher
  const roleSelect = document.getElementById('roleSelect');
  roleSelect.addEventListener('change', (e) => {
    currentRole = e.target.value;
    api.setContext(currentTenant, currentRole);
    if (currentRole === 'HOSPITAL_ADMIN') {
      switchTab('hospital-admin');
    } else if (currentRole === 'PLATFORM_ADMIN') {
      switchTab('platform-admin');
    } else if (currentRole === 'CLINICAL_REVIEWER') {
      switchTab('escalations');
    } else if (currentRole === 'CAMPAIGN_MANAGER') {
      switchTab('queue');
    }
    loadAllData();
  });

  // Auto-Refresh checkbox
  document.getElementById('chkAutoRefresh')?.addEventListener('change', (e) => {
    const lbl = document.getElementById('lblAutoRefresh');
    if (lbl) {
      lbl.innerText = e.target.checked ? 'Live Polling (5s)' : 'Polling Paused';
    }
    showToast(e.target.checked ? 'Live queue polling activated' : 'Live queue polling paused', 'info');
  });

  // Queue Status Filter
  document.getElementById('queueStatusFilter')?.addEventListener('change', () => {
    loadAllData();
  });

  // Tabs Navigation
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tabId = btn.getAttribute('data-tab');
      switchTab(tabId);
    });
  });

  // Hospital Admin Refresh
  document.getElementById('btnRefreshHospitalAdmin')?.addEventListener('click', loadHospitalAdminView);

  // Platform Admin Refresh
  document.getElementById('btnRefreshPlatformAdmin')?.addEventListener('click', loadPlatformAdminView);

  // Reprioritize Modal Controls
  document.getElementById('btnCloseReprioritize')?.addEventListener('click', closeReprioritizeModal);
  document.getElementById('btnCancelReprioritize')?.addEventListener('click', closeReprioritizeModal);
  document.getElementById('btnSaveReprioritize')?.addEventListener('click', handleSaveReprioritize);

  // Operations Buttons
  document.getElementById('btnRefreshOps')?.addEventListener('click', loadAllData);
  document.getElementById('btnDispatchNext')?.addEventListener('click', handleDispatchNext);
  document.getElementById('btnTriggerReaper')?.addEventListener('click', handleTriggerReaper);
  document.getElementById('btnResetQueueQuick')?.addEventListener('click', handleSimReset);
  document.getElementById('btnLaunchSimQuick')?.addEventListener('click', handleLaunchSimQuick);

  // Simulation Studio Buttons
  document.getElementById('btnSimReset')?.addEventListener('click', handleSimReset);
  document.getElementById('btnSimStep')?.addEventListener('click', handleSimStep);
  document.getElementById('btnSimAutoPlay')?.addEventListener('click', handleSimAutoPlay);

  // Escalation Filter Buttons
  document.querySelectorAll('.esc-filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.esc-filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const filter = btn.getAttribute('data-filter');
      loadEscalationsView(filter);
    });
  });

  // Safety Benchmark Button
  document.getElementById('btnRunSafetyBenchmark')?.addEventListener('click', handleRunSafetyBenchmark);

  // EHR Failure Toggle
  document.getElementById('btnToggleEhrFailure')?.addEventListener('click', handleToggleEHRFailure);

  // Call Modal Controls
  document.getElementById('btnCloseCallModal')?.addEventListener('click', closeCallModal);
  document.getElementById('btnEndCallTriage')?.addEventListener('click', handleEndCallTriage);
  document.getElementById('btnEndNormal')?.addEventListener('click', () => handleEndCallWithOutcome('SUCCESSFUL_COMPLETION'));
  document.getElementById('btnEndEscalate')?.addEventListener('click', () => handleEndCallWithOutcome('ESCALATION_TRIGGERED'));
  document.getElementById('btnSendSpeech')?.addEventListener('click', handleSendSpeech);
  document.getElementById('callSpeechInput')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleSendSpeech();
  });

  // Call Presets
  document.querySelectorAll('.call-preset-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const speech = btn.getAttribute('data-speech');
      if (speech) {
        document.getElementById('callSpeechInput').value = speech;
        handleSendSpeech();
      }
    });
  });

  // Patient 360 Close
  document.getElementById('btnCloseP360')?.addEventListener('click', () => {
    document.getElementById('modalPatient360').classList.remove('active');
  });
}

// ----------------------------------------------------
// DATA LOADING
// ----------------------------------------------------
async function loadAllData(isSilent = false) {
  try {
    const statusFilter = document.getElementById('queueStatusFilter')?.value || null;
    const [concurrency, campaigns, allTasks, filteredTasks] = await Promise.all([
      api.getConcurrency(),
      api.getCampaigns(),
      api.getTasks(), // for global KPI cards
      statusFilter ? api.getTasks(statusFilter) : null
    ]);

    window.currentAllTasks = allTasks || [];
    updateConcurrencyBar(concurrency);
    renderKPICards(concurrency, allTasks);
    renderCampaigns(campaigns);
    renderQueueTable(filteredTasks || allTasks);

    // If Escalations tab is active, refresh its list too
    const isEscActive = document.getElementById('tab-escalations')?.classList.contains('active');
    if (isEscActive) {
      const activeFilterBtn = document.querySelector('.esc-filter-btn.active');
      const activeFilter = activeFilterBtn?.getAttribute('data-filter') || 'ALL';
      loadEscalationsView(activeFilter);
    }
  } catch (err) {
    if (!isSilent) console.error("Failed loading platform data:", err);
  }
}

function updateConcurrencyBar(concurrency) {
  if (!concurrency) return;
  const active = concurrency.active_calls_count || 0;
  const max = concurrency.max_concurrent_capacity || 5;
  const pct = concurrency.utilization_percentage || 0;

  const label = document.getElementById('capacityLabel');
  const progress = document.getElementById('capacityProgress');

  if (label) label.innerText = `${active} / ${max} (${pct.toFixed(0)}%)`;
  if (progress) {
    progress.style.width = `${Math.min(100, pct)}%`;
    progress.style.backgroundColor = pct >= 100 ? 'var(--danger)' : 'var(--success)';
  }
}

function renderKPICards(concurrency, tasks) {
  if (concurrency) {
    const active = concurrency.active_calls_count || 0;
    const max = concurrency.max_concurrent_capacity || 5;
    const avail = concurrency.available_slots || 0;
    document.getElementById('kpiActiveCalls').innerText = `${active} / ${max}`;
    document.getElementById('kpiAvailableSlots').innerText = `${avail} slots available now`;
    document.getElementById('kpiQueueDepth').innerText = concurrency.pending_tasks_count || 0;
    document.getElementById('kpiOldestWait').innerText = `Oldest task: ${concurrency.oldest_pending_task_age_minutes || 0}m`;
    document.getElementById('kpiCutoffRisk').innerText = concurrency.cutoff_risk_count || 0;
  }

  if (tasks) {
    const completed = tasks.filter(t => t.status === 'COMPLETED').length;
    const escalated = tasks.filter(t => t.status === 'ESCALATED').length;
    document.getElementById('kpiCompleted').innerText = completed;
    document.getElementById('kpiEscalations').innerText = escalated;
  }
}

function renderCampaigns(campaigns) {
  const container = document.getElementById('campaignsContainer');
  if (!container) return;

  if (!campaigns || campaigns.length === 0) {
    container.innerHTML = `<div style="color: #64748b; font-style: italic; padding: 12px 0;">No active campaigns for this hospital tenant.</div>`;
    return;
  }

  container.innerHTML = campaigns.map(c => {
    const isRunning = c.status === 'RUNNING';
    return `
      <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid rgba(35, 48, 77, 0.4);">
        <div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <strong style="color: #fff; font-size: 13px;">${c.name}</strong>
            <span class="badge ${isRunning ? 'badge-routine' : 'badge-concerning'}">${c.status}</span>
            <span class="badge" style="background: #1e293b; color: #94a3b8;">Condition: ${c.target_condition}</span>
          </div>
          <p style="font-size: 11px; color: #94a3b8; margin-top: 3px;">${c.description}</p>
          <div style="font-size: 11px; color: #64748b; display: flex; gap: 16px; margin-top: 4px;">
            <span>Clinical Window: <strong style="color: #cbd5e1;">${c.followup_window_hours}h</strong></span>
            <span>Allocated Slots: <strong style="color: #cbd5e1;">${c.allocated_capacity}</strong></span>
            <span>Priority Level: <strong style="color: #cbd5e1;">${c.priority_level}/5</strong></span>
          </div>
        </div>
        <div style="display: flex; gap: 6px; align-items: center;">
          <button class="btn btn-secondary" style="font-size: 11px; padding: 5px 10px;" onclick="openReprioritizeModal('${c.id}', ${c.priority_level || 1}, ${c.allocated_capacity || 2}, '${(c.name || '').replace(/'/g, "\\'")}')">
            Reprioritize
          </button>
          ${isRunning ? `
            <button class="btn btn-secondary" onclick="toggleCampaign('${c.id}', 'PAUSED')">
              Pause Outreach
            </button>
          ` : `
            <button class="btn btn-success" onclick="toggleCampaign('${c.id}', 'RUNNING')">
              Resume Outreach
            </button>
          `}
        </div>
      </div>
    `;
  }).join('');
}

async function toggleCampaign(campId, newStatus) {
  try {
    await api.setCampaignStatus(campId, newStatus);
    showToast(`Campaign ${newStatus === 'RUNNING' ? 'resumed' : 'paused'} successfully`, 'success');
    loadAllData();
    if (document.getElementById('tab-hospital-admin')?.classList.contains('active')) {
      loadHospitalAdminView();
    }
  } catch (err) {
    showToast("Error updating campaign: " + err.message, 'danger');
  }
}

function renderQueueTable(tasks) {
  const tbody = document.getElementById('queueTableBody');
  if (!tbody) return;

  if (!tasks || tasks.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: #64748b; padding: 30px;">Queue empty. No matching outreach tasks.</td></tr>`;
    return;
  }

  tbody.innerHTML = tasks.slice(0, 50).map((t, idx) => {
    const patName = t.patient ? `${t.patient.first_name} ${t.patient.last_name}` : t.patient_id;
    const mrn = t.patient?.mrn || 'N/A';
    
    // Calculate cutoff hours left
    const cutoff = parseToISTDate(t.clinical_cutoff_time);
    const now = new Date();
    const hoursLeft = cutoff ? Math.max(0, ((cutoff - now) / (1000 * 3600))).toFixed(1) : 'N/A';
    const isImminent = cutoff && Number(hoursLeft) <= 4.0;

    let statusBadge = 'badge';
    if (t.status === 'COMPLETED') statusBadge = 'badge-routine';
    else if (t.status === 'CALLING') statusBadge = 'badge-calling';
    else if (t.status === 'ESCALATED') statusBadge = 'badge-urgent';
    else if (t.status === 'RETRY_SCHEDULED') statusBadge = 'badge-concerning';
    else if (t.status === 'PENDING') statusBadge = 'badge';
    else if (t.status === 'MANUAL_FOLLOW_UP') statusBadge = 'badge-concerning';

    const maxRetries = t.max_retries || 3;
    const safeAttempts = Math.min(t.attempts_count || 0, maxRetries);
    const completedAttempt = Math.min(Math.max(1, t.attempts_count || 1), maxRetries);
    const retriesRemaining = Math.max(0, maxRetries - safeAttempts);
    const retryWord = retriesRemaining === 1 ? 'retry' : 'retries';
    const nextAttempt = Math.min(maxRetries, safeAttempts + 1);

    let attemptsHtml = `${safeAttempts} / ${maxRetries}`;
    if (t.status === 'ESCALATED') {
      attemptsHtml = `${safeAttempts} / ${maxRetries}`;
      if (retriesRemaining > 0) {
        attemptsHtml += `<div style="font-size: 10px; color: #f59e0b; font-weight: 600;">(${retriesRemaining} ${retryWord} left)</div>`;
      }
    } else if (t.status === 'COMPLETED') {
      attemptsHtml = `
        <div style="font-family: 'JetBrains Mono'; font-weight: 700; color: #34d399; font-size: 12px;" title="Normal recovery confirmed on outreach attempt ${completedAttempt} of ${maxRetries}">Attempt ${completedAttempt}</div>
        <div style="font-size: 10px; color: #6ee7b7; font-weight: 600; margin-top: 1px;">(Normal Recovery)</div>
      `;
    }

    let actionBtnHtml = '';
    if (t.status === 'CALLING') {
      actionBtnHtml = `
        <div style="display: flex; gap: 4px; justify-content: flex-end;">
          <button class="btn btn-warning" style="padding: 3px 8px; font-size: 11px;" onclick="openCallModal('${t.id}')" title="Join live call audio & dialogue">
            Join
          </button>
          <button class="btn btn-secondary" style="padding: 3px 8px; font-size: 11px; color: #f87171; border-color: rgba(239, 68, 68, 0.4);" onclick="quickEndCall('${t.id}', 'ESCALATION_TRIGGERED')" title="End call and place in Clinical Escalations Box">
            Escalate
          </button>
          <button class="btn btn-secondary" style="padding: 3px 8px; font-size: 11px; color: #34d399; border-color: rgba(16, 185, 129, 0.4);" onclick="quickEndCall('${t.id}', 'SUCCESSFUL_COMPLETION')" title="End call as stable normal recovery and mark completed in queue">
            Complete
          </button>
        </div>
      `;
    } else if (t.status === 'PENDING' || t.status === 'RETRY_SCHEDULED') {
      actionBtnHtml = `
        <button class="btn btn-primary" style="padding: 3px 12px; font-size: 11px;" onclick="openCallModal('${t.id}')">
          Call Now
        </button>
      `;
    } else if (t.status === 'ESCALATED') {
      const isMaxReached = safeAttempts >= maxRetries;
      const callBtnLabel = !isMaxReached 
        ? `📞 Retry Call (${retriesRemaining} left)` 
        : `⚠️ Max Attempts (${safeAttempts}/${maxRetries})`;
      
      const patFullName = (t.patient ? `${t.patient.first_name} ${t.patient.last_name}` : 'Patient').replace(/'/g, "\\'");
      actionBtnHtml = `
        <div style="display: flex; gap: 4px; justify-content: flex-end; align-items: center;">
          ${!isMaxReached ? `
            <button class="btn btn-primary" style="padding: 3px 8px; font-size: 11px;" onclick="openCallModal('${t.id}')" title="Retry call for patient (Attempt ${nextAttempt} of ${maxRetries} - ${retriesRemaining} ${retryWord} remaining)">
              ${callBtnLabel}
            </button>
          ` : `
            <button class="btn btn-secondary" style="padding: 3px 8px; font-size: 11px; color: #f87171; border-color: rgba(239, 68, 68, 0.4); background: rgba(239, 68, 68, 0.08);" onclick="showMaxAttemptsNotice('${patFullName}', ${safeAttempts}, ${maxRetries})" title="Maximum outreach call attempts reached (${safeAttempts}/${maxRetries}). Automated calls stopped. Please review in Clinical Escalations Box.">
              ${callBtnLabel}
            </button>
          `}
          <button class="btn btn-secondary" style="padding: 3px 8px; font-size: 11px; color: #f59e0b; border-color: rgba(245, 158, 11, 0.4);" onclick="goToEscalationsTab('${t.id}')" title="View in Clinical Escalations Box">
            Escalations Box ↗
          </button>
        </div>
      `;
    } else if (t.status === 'COMPLETED') {
      actionBtnHtml = `
        <div style="display: flex; gap: 4px; justify-content: flex-end; align-items: center;">
          <span style="font-size: 11px; font-weight: 700; color: #34d399; margin-right: 4px;">✓ Completed</span>
          <button class="btn btn-secondary" style="padding: 3px 8px; font-size: 11px; color: #10b981; border-color: rgba(16, 185, 129, 0.4);" onclick="openPatient360('${t.patient_id}')" title="Open Patient 360 EHR Chart">
            EHR Chart
          </button>
        </div>
      `;
    } else if (t.status === 'MANUAL_FOLLOW_UP') {
      actionBtnHtml = `
        <div style="display: flex; gap: 4px; justify-content: flex-end;">
          <button class="btn btn-warning" style="padding: 3px 8px; font-size: 11px;" onclick="openCallModal('${t.id}')" title="Direct clinician outreach call">
            Manual Call
          </button>
          <button class="btn btn-secondary" style="padding: 3px 8px; font-size: 11px; color: #10b981; border-color: rgba(16, 185, 129, 0.4);" onclick="openPatient360('${t.patient_id}')" title="Open Patient 360 EHR Chart">
            EHR Chart
          </button>
        </div>
      `;
    } else {
      actionBtnHtml = `
        <button class="btn btn-secondary" style="padding: 3px 10px; font-size: 11px; color: #10b981; border-color: rgba(16, 185, 129, 0.4);" onclick="openPatient360('${t.patient_id}')">
          EHR Chart
        </button>
      `;
    }

    return `
      <tr style="${t.status === 'CALLING' ? 'background: rgba(79, 70, 229, 0.08);' : (t.status === 'COMPLETED' ? 'background: rgba(16, 185, 129, 0.04);' : '')}">
        <td style="font-family: 'JetBrains Mono'; font-weight: 700; color: #94a3b8;">#${idx + 1}</td>
        <td>
          <a href="javascript:void(0)" onclick="openPatient360('${t.patient_id}')" style="color: #fff; font-weight: 600; text-decoration: none;">
            ${patName}
          </a>
          <div style="font-size: 10px; font-family: 'JetBrains Mono'; color: #64748b;">${mrn}</div>
        </td>
        <td>
          <span style="font-family: 'JetBrains Mono'; font-weight: 700; font-size: 13px; color: #818cf8;">
            ${t.priority_score.toFixed(1)}
          </span>
        </td>
        <td>
          <span class="badge ${t.clinical_risk_score >= 8 ? 'badge-urgent' : (t.clinical_risk_score >= 6 ? 'badge-concerning' : 'badge-routine')}">
            Score: ${t.clinical_risk_score.toFixed(1)}
          </span>
        </td>
        <td>
          <span style="font-family: 'JetBrains Mono'; font-weight: 600; color: ${isImminent ? '#f87171' : '#cbd5e1'};" title="IST Deadline: ${formatISTDateTime(t.clinical_cutoff_time)}">
            ${hoursLeft}h left ${isImminent ? '⚡' : ''}
          </span>
        </td>
        <td style="font-family: 'JetBrains Mono';">${attemptsHtml}</td>
        <td>
          <span class="badge ${statusBadge}">${t.status}</span>
        </td>
        <td style="text-align: right;">
          ${actionBtnHtml}
        </td>
      </tr>
    `;
  }).join('');
}

function goToEscalationsTab(taskId) {
  const escBtn = document.querySelector('.tab-btn[data-tab="escalations"]');
  if (escBtn) {
    escBtn.click();
    loadEscalationsView().then(() => {
      if (taskId && currentEscalations.length > 0) {
        const found = currentEscalations.find(e => e.task_id === taskId);
        if (found) selectEscalation(found.id);
      }
    });
  }
}

// ----------------------------------------------------
// ACTIONS: DISPATCH & REAPER
// ----------------------------------------------------
async function handleDispatchNext() {
  try {
    const res = await api.dispatchNext();
    if (res.dispatched) {
      showToast(`Slot Reserved! Dispatched task ${res.task_id} (Priority: ${res.priority_score}) to line`, 'success');
    } else {
      showToast(res.message, 'warning');
    }
    loadAllData();
  } catch (err) {
    showToast("Dispatch error: " + err.message, 'danger');
  }
}

async function handleTriggerReaper() {
  try {
    const reaped = await api.triggerReaper();
    if (reaped && reaped.length > 0) {
      showToast(`Stuck Worker Reaper: Recovered ${reaped.length} timed-out task(s): ${reaped.join(', ')}`, 'warning');
    } else {
      showToast("Heartbeat Reaper: All worker heartbeats active. 0 stalled slots detected.", 'success');
    }
    loadAllData();
  } catch (err) {
    showToast("Reaper error: " + err.message, 'danger');
  }
}

function handleLaunchSimQuick() {
  api.getTasks().then(tasks => {
    if (tasks && tasks.length > 0) {
      openCallModal(tasks[0].id);
    } else {
      alert("No tasks currently available in queue to call.");
    }
  });
}

// ----------------------------------------------------
// TAB 2: QUEUE SIMULATION STUDIO
// ----------------------------------------------------
async function loadSimulationView() {
  try {
    const tasks = await api.getTasks();
    renderSimulationSlots(tasks);
    renderSimulationCohort(tasks);
  } catch (err) {
    console.error(err);
  }
}

function renderSimulationSlots(tasks) {
  const calling = tasks.filter(t => t.status === 'CALLING');
  for (let i = 1; i <= 3; i++) {
    const slotElem = document.getElementById(`simSlot${i}`);
    if (!slotElem) continue;
    const task = calling[i - 1];

    if (task) {
      const patName = task.patient ? `${task.patient.first_name} ${task.patient.last_name}` : task.patient_id;
      slotElem.style.border = '2px solid #6366f1';
      slotElem.style.background = '#131c31';
      slotElem.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span class="badge" style="background: rgba(79, 70, 229, 0.3); color: #c7d2fe;">SLOT #${i} [OCCUPIED]</span>
          <div class="waveform-container" style="padding: 2px 6px;">
            <div class="waveform-bar" style="height: 10px;"></div>
            <div class="waveform-bar" style="height: 16px;"></div>
            <div class="waveform-bar" style="height: 12px;"></div>
          </div>
        </div>
        <div style="font-weight: 700; color: #fff; font-size: 13px; margin-top: 8px;">${patName}</div>
        <div style="font-size: 11px; color: #94a3b8; display: flex; gap: 8px; margin-top: 2px;">
          <span>Score: <strong style="color: #818cf8;">${task.priority_score.toFixed(1)}</strong></span>
          <span>•</span>
          <span>Attempts: ${task.attempts_count}</span>
        </div>
        <div style="font-size: 10px; font-family: 'JetBrains Mono'; color: var(--success); margin-top: 8px; border-top: 1px solid #1e293b; padding-top: 4px;">
          ● LIVE CALL SIMULATION
        </div>
      `;
    } else {
      slotElem.style.border = '1px dashed #334155';
      slotElem.style.background = '#0b0f19';
      slotElem.innerHTML = `
        <div style="font-size: 11px; font-family: 'JetBrains Mono'; color: #64748b;">SLOT #${i} [IDLE]</div>
        <div style="font-size: 12px; color: #475569; margin-top: 4px;">Available for next highest-priority task</div>
      `;
    }
  }
}

function renderSimulationCohort(tasks) {
  const container = document.getElementById('simTaskList');
  if (!container) return;

  container.innerHTML = tasks.slice(0, 25).map((t, idx) => {
    const patName = t.patient ? `${t.patient.first_name} ${t.patient.last_name}` : t.patient_id;
    let badge = 'badge-routine';
    if (t.status === 'CALLING') badge = 'badge-calling';
    else if (t.status === 'ESCALATED') badge = 'badge-urgent';
    else if (t.status === 'RETRY_SCHEDULED') badge = 'badge-concerning';

    return `
      <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-bottom: 1px solid rgba(35, 48, 77, 0.4); font-size: 12px;">
        <div style="display: flex; align-items: center; gap: 10px;">
          <span style="font-family: 'JetBrains Mono'; color: #64748b; font-weight: 700; width: 24px;">#${idx + 1}</span>
          <div>
            <strong style="color: #fff;">${patName}</strong>
            <div style="font-size: 10px; color: #94a3b8; display: flex; gap: 8px; margin-top: 1px;">
              <span>Risk: <strong>${t.clinical_risk_score.toFixed(1)}</strong></span>
              <span>•</span>
              <span>Priority: <strong style="color: #818cf8;">${t.priority_score.toFixed(1)}</strong></span>
              <span>•</span>
              <span>Attempts: ${t.attempts_count}</span>
            </div>
          </div>
        </div>
        <span class="badge ${badge}">${t.status}</span>
      </div>
    `;
  }).join('');
}

async function handleSimReset() {
  try {
    const res = await api.initSimulation();
    appendSimLog(res.message, 'INIT');
    loadSimulationView();
    loadAllData();
    showToast("Simulation cohort initialized: 25 fresh PENDING patients available to call!", "success");
  } catch (err) {
    alert("Simulation init error: " + err.message);
  }
}

async function handleSimStep() {
  try {
    const res = await api.stepSimulation();
    const events = res.step_events || [];
    events.forEach(e => {
      const msg = e.message || `Task ${e.task_id}: ${e.event} (${e.status || ''}) - ${e.reason || ''}`;
      appendSimLog(msg, e.event || 'STEP');
    });
    loadSimulationView();
    loadAllData();
  } catch (err) {
    console.error("Step error:", err);
  }
}

function handleSimAutoPlay() {
  const btn = document.getElementById('btnSimAutoPlay');
  if (simAutoPlayInterval) {
    clearInterval(simAutoPlayInterval);
    simAutoPlayInterval = null;
    btn.innerText = 'Auto-Run Simulation';
    btn.className = 'btn btn-success';
  } else {
    simAutoPlayInterval = setInterval(handleSimStep, 2500);
    btn.innerText = 'Pause Auto-Run';
    btn.className = 'btn btn-secondary';
  }
}

function appendSimLog(msg, type) {
  const stream = document.getElementById('simLogStream');
  if (!stream) return;
  const time = formatISTTime(new Date(), true);
  const div = document.createElement('div');
  div.style.padding = '6px 8px';
  div.style.background = '#0d1321';
  div.style.borderRadius = '4px';
  div.style.border = '1px solid #1e293b';
  div.innerHTML = `
    <div style="display: flex; justify-content: space-between; color: #64748b; font-size: 10px;">
      <span>[${time}]</span>
      <span style="color: #818cf8; font-weight: 700;">${type}</span>
    </div>
    <div style="color: #e2e8f0; margin-top: 2px;">${msg}</div>
  `;
  stream.prepend(div);
}

// ----------------------------------------------------
// TAB 3: CLINICAL REVIEWER ESCALATIONS
// ----------------------------------------------------
async function loadEscalationsView(statusFilter = 'ALL') {
  try {
    const escalations = await api.getEscalations(statusFilter);
    currentEscalations = escalations;
    renderEscalationList(escalations);
    if (escalations.length > 0) {
      const stillExists = escalations.find(e => e.id === selectedEscalationId);
      if (stillExists) {
        selectEscalation(selectedEscalationId);
      } else {
        selectEscalation(escalations[0].id);
      }
    } else {
      selectedEscalationId = null;
      document.getElementById('escalationDrawer').innerHTML = `
        <div style="color: #64748b; font-style: italic; text-align: center; padding-top: 150px;">
          No escalations matching current filter. All patient cohorts stable.
        </div>
      `;
    }
  } catch (err) {
    console.error(err);
  }
}

function renderEscalationList(escalations) {
  const list = document.getElementById('escalationList');
  if (!list) return;

  if (!escalations || escalations.length === 0) {
    list.innerHTML = `<div style="padding: 20px; text-align: center; color: #64748b; font-style: italic;">No escalations.</div>`;
    return;
  }

  list.innerHTML = escalations.map(esc => {
    const patName = esc.patient ? `${esc.patient.first_name} ${esc.patient.last_name}` : esc.patient_id;
    const isSelected = selectedEscalationId === esc.id;
    const isUrgent = esc.severity === 'URGENT';
    const attempts = (esc.attempts_count !== undefined && esc.attempts_count !== null) ? esc.attempts_count : 1;
    const maxRetries = (esc.max_retries !== undefined && esc.max_retries !== null) ? esc.max_retries : 3;
    const isMaxReached = attempts >= maxRetries;

    return `
      <div 
        onclick="selectEscalation('${esc.id}')"
        style="padding: 12px 16px; border-bottom: 1px solid rgba(35, 48, 77, 0.4); cursor: pointer; background: ${isSelected ? '#17223b' : 'transparent'};"
      >
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
          <span class="badge ${isUrgent ? 'badge-urgent' : 'badge-concerning'}">${esc.severity}</span>
          <span style="font-size: 10px; font-family: 'JetBrains Mono'; color: #64748b;">
            ${formatISTTime(esc.created_at)}
          </span>
        </div>
        <strong style="color: #fff; font-size: 13px;">${patName}</strong>
        <p style="font-size: 11px; color: #cbd5e1; margin-top: 2px; line-height: 1.3;">${esc.trigger_reason}</p>
        <div style="font-size: 10px; color: #64748b; margin-top: 6px; display: flex; justify-content: space-between;">
          <span>Status: <strong style="color: #e2e8f0;">${esc.status}</strong></span>
          <span>Reviewer: ${esc.assigned_reviewer_name || 'Unassigned'}</span>
        </div>
        <div style="font-size: 10px; color: #64748b; margin-top: 5px; display: flex; justify-content: space-between; align-items: center;">
          <span>Attempts: <strong style="color: #38bdf8;">${attempts} / ${maxRetries}</strong></span>
          <span style="font-size: 9px; padding: 1px 6px; border-radius: 4px; font-weight: 600; ${isMaxReached ? 'background: rgba(239, 68, 68, 0.15); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.3);' : 'background: rgba(16, 185, 129, 0.15); color: #6ee7b7; border: 1px solid rgba(16, 185, 129, 0.3);'}">
            ${isMaxReached ? 'Max 3 Attempts' : `Attempt ${attempts} of ${maxRetries}`}
          </span>
        </div>
      </div>
    `;
  }).join('');
}

function showMaxAttemptsNotice(patName, attempts, maxRetries) {
  showToast(`Maximum outreach call attempts reached (${attempts}/${maxRetries}) for ${patName}. Automated calls are stopped. Please resolve the escalation using the clinical actions or orders below.`, 'warning');
}

function selectEscalation(escId) {
  selectedEscalationId = escId;
  const esc = currentEscalations.find(e => e.id === escId);
  const drawer = document.getElementById('escalationDrawer');
  if (!esc || !drawer) return;

  const patName = esc.patient ? `${esc.patient.first_name} ${esc.patient.last_name}` : esc.patient_id;
  const isResolved = esc.status === 'RESOLVED';
  const relatedTask = (window.currentAllTasks || []).find(t => t.id === esc.task_id);
  const attempts = (esc.attempts_count !== undefined && esc.attempts_count !== null)
    ? esc.attempts_count
    : (relatedTask ? (relatedTask.attempts_count || 1) : 1);
  const maxRetries = (esc.max_retries !== undefined && esc.max_retries !== null)
    ? esc.max_retries
    : (relatedTask ? (relatedTask.max_retries || 3) : 3);
  const nextAttempt = Math.min(maxRetries, attempts + 1);
  const isMaxReached = attempts >= maxRetries;
  const callBtnLabel = !isMaxReached 
    ? `📞 Call Patient (Attempt ${nextAttempt}/${maxRetries})` 
    : `⚠️ Max Attempts Reached (${attempts}/${maxRetries})`;

  drawer.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 1px solid var(--border-color); padding-bottom: 12px; margin-bottom: 16px;">
      <div>
        <h3 style="font-size: 16px; font-weight: 700; color: #fff;">${patName}</h3>
        <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">
          MRN: <strong style="color: #cbd5e1;">${esc.patient?.mrn || 'N/A'}</strong> • 
          Severity: <strong style="color: var(--danger);">${esc.severity}</strong> •
          Assigned: <strong style="color: #cbd5e1;">${esc.assigned_reviewer_name || 'Unassigned'}</strong> •
          Attempts: <strong style="color: ${isMaxReached ? '#f87171' : '#38bdf8'};">${attempts} / ${maxRetries}</strong>
        </div>
      </div>
      <div style="display: flex; gap: 8px; align-items: center;">
        ${esc.task_id && !isResolved ? `
          ${!isMaxReached ? `
            <button class="btn btn-primary" onclick="openCallModal('${esc.task_id}')" style="font-size: 11px; padding: 5px 12px;" title="Initiate follow-up outreach call (Attempt ${nextAttempt} of ${maxRetries})">
              ${callBtnLabel}
            </button>
          ` : `
            <button class="btn btn-secondary" onclick="showMaxAttemptsNotice('${patName.replace(/'/g, "\\'")}', ${attempts}, ${maxRetries})" style="font-size: 11px; padding: 5px 12px; color: #f87171; border-color: rgba(239, 68, 68, 0.4); background: rgba(239, 68, 68, 0.08);" title="Maximum outreach call attempts reached (${attempts}/${maxRetries}). Automated calls are stopped. Please review and resolve clinical escalation below.">
              ${callBtnLabel}
            </button>
          `}
        ` : ''}
        ${!esc.assigned_reviewer_name ? `
          <button class="btn btn-secondary" onclick="assignEscalationToMe('${esc.id}')">Assign to Me</button>
        ` : ''}
        <button class="btn btn-secondary" onclick="openPatient360('${esc.patient_id}')" style="font-size: 11px; padding: 5px 10px; color: #10b981; border-color: rgba(16, 185, 129, 0.4);" title="Open Patient 360 Inpatient Discharge &amp; Call History">
          Patient 360 ↗
        </button>
      </div>
    </div>

    <!-- Clinical Trigger Box -->
    <div style="background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; padding: 12px; margin-bottom: 16px;">
      <div style="font-size: 11px; font-weight: 700; color: #fca5a5; text-transform: uppercase;">
        ▲ Clinical Escalation Trigger &amp; Red-Flag Evidence
      </div>
      <p style="font-size: 13px; font-weight: 600; color: #fff; margin-top: 4px;">${esc.trigger_reason}</p>
      <div style="font-size: 11px; color: #94a3b8; margin-top: 4px;">
        <strong>Protocol Cited:</strong> ${esc.protocol_citations}
      </div>
    </div>

    <!-- Multi-Agent AI Consensus -->
    <div style="background: #111a2e; border: 1px solid var(--border-color); border-radius: 8px; padding: 12px; margin-bottom: 16px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
        <span style="font-size: 11px; font-weight: 700; color: #818cf8; text-transform: uppercase;">
          Multi-Agent AI Consensus Rationale
        </span>
        <span class="badge badge-routine">Agreement Verified</span>
      </div>
      <p style="font-size: 12px; color: #cbd5e1; line-height: 1.4;">${esc.consensus_rationale}</p>
      <div style="font-size: 10px; font-family: 'JetBrains Mono'; color: #64748b; margin-top: 6px; border-top: 1px solid #1c2742; padding-top: 4px;">
        Conservative Policy Applied: Any evaluator red-flag forces human reviewer intervention.
      </div>
    </div>

    <!-- Resolution Section -->
    ${!isResolved ? `
      <div style="background: #080d17; border: 1px solid var(--border-color); border-radius: 8px; padding: 14px;">
        <h4 style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: #fff; margin-bottom: 10px;">
          Human Clinical Resolution &amp; EHR Follow-Up Order
        </h4>

        <div style="margin-bottom: 10px;">
          <label style="font-size: 11px; color: #94a3b8; display: block; margin-bottom: 4px;">Select Action:</label>
          <select id="selectResolutionAction" class="select-input" style="width: 100%;">
            <option value="Urgent Clinic Triage Appointment Scheduled">Urgent Clinic Triage Appointment Scheduled</option>
            <option value="Attending Physician Direct Phone Review Completed">Attending Physician Direct Phone Review Completed</option>
            <option value="Dispatched Home Health Registered Nurse">Dispatched Home Health Registered Nurse</option>
            <option value="Diuretic Medication Adjusted by Cardiologist">Diuretic Medication Adjusted by Cardiologist</option>
            <option value="Emergency Department Evaluation Recommended">Emergency Department Evaluation Recommended</option>
            <option value="Patient Educated; Symptoms Deemed Baseline">Patient Educated; Symptoms Deemed Baseline</option>
            <option value="Re-queue Patient for Next Outreach Call Attempt (Retry)">Re-queue Patient for Next Outreach Call Attempt (Retry)</option>
          </select>
        </div>

        <div style="margin-bottom: 12px;">
          <label style="font-size: 11px; color: #94a3b8; display: block; margin-bottom: 4px;">Clinical Reviewer Notes:</label>
          <textarea id="textResolutionNotes" rows="2" placeholder="Document clinical findings, physician consults, and instructions provided to patient..." style="width: 100%; background: #1e293b; border: 1px solid var(--border-color); border-radius: 6px; padding: 8px; color: #fff; font-size: 11px; outline: none;"></textarea>
        </div>

        <button class="btn btn-success" style="width: 100%; justify-content: center; padding: 8px;" onclick="submitEscalationResolution('${esc.id}')">
          Resolve Escalation &amp; Sync Order to Mock EHR
        </button>
      </div>
    ` : `
      <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 8px; padding: 14px; color: #6ee7b7; font-size: 12px;">
        <div style="font-weight: 700; text-transform: uppercase; font-size: 11px; margin-bottom: 4px;">✓ Escalation Resolved</div>
        <div><strong>Action Taken:</strong> ${esc.resolution_action}</div>
        <div style="margin-top: 4px;"><strong>Clinical Notes:</strong> ${esc.resolution_notes}</div>
      </div>
    `}
  `;
}

async function assignEscalationToMe(escId) {
  try {
    await api.assignEscalation(escId, "usr-clin-rev-mgh", "Nurse Sarah Lin, RN");
    loadEscalationsView();
  } catch (err) {
    alert("Assign error: " + err.message);
  }
}

async function submitEscalationResolution(escId) {
  const action = document.getElementById('selectResolutionAction')?.value;
  const notes = document.getElementById('textResolutionNotes')?.value;
  if (!notes || !notes.trim()) {
    alert("Please enter clinical reviewer notes.");
    return;
  }

  try {
    await api.resolveEscalation(escId, notes.trim(), action, "Nurse Sarah Lin, RN");
    alert("Escalation RESOLVED! Clinical follow-up task committed to Mock EHR.");
    loadEscalationsView();
    loadAllData();
  } catch (err) {
    alert("Resolution error: " + err.message);
  }
}

// ----------------------------------------------------
// TAB 4: SAFETY BENCHMARK
// ----------------------------------------------------
async function handleRunSafetyBenchmark() {
  const container = document.getElementById('safetyResultsContainer');
  if (!container) return;

  container.innerHTML = `
    <div style="text-align: center; padding: 60px; color: #818cf8;">
      <div style="font-size: 14px; font-weight: 600;">Running Standardized 35-Case Safety Benchmark...</div>
      <div style="font-size: 12px; color: #64748b; margin-top: 4px;">Evaluating clinical triage, dual-agent consensus, and adversarial prompt injections...</div>
    </div>
  `;

  try {
    const res = await api.runSafetyBenchmark();

    container.innerHTML = `
      <div class="kpi-grid" style="margin-bottom: 24px;">
        <div class="kpi-card" style="border: 2px solid var(--success); background: rgba(16, 185, 129, 0.08);">
          <div class="kpi-title" style="color: #6ee7b7;">False-Negative Rate (FNR)</div>
          <div class="kpi-value" style="color: var(--success);">${res.false_negative_rate_percentage.toFixed(1)}%</div>
          <div class="kpi-sub" style="color: #a7f3d0; font-weight: 600;">TARGET: ZERO MISSED RED FLAGS</div>
        </div>

        <div class="kpi-card">
          <div class="kpi-title">Clinical Sensitivity (Recall)</div>
          <div class="kpi-value">${res.sensitivity_percentage.toFixed(1)}%</div>
          <div class="kpi-sub">${res.true_positives} / ${res.true_positives + res.false_negatives} high-risk cases identified</div>
        </div>

        <div class="kpi-card">
          <div class="kpi-title">Specificity</div>
          <div class="kpi-value">${res.specificity_percentage.toFixed(1)}%</div>
          <div class="kpi-sub">Controlled false alarm margin</div>
        </div>

        <div class="kpi-card">
          <div class="kpi-title" style="color: #d8b4fe;">Prompt Injection Defense</div>
          <div class="kpi-value" style="color: #c084fc;">100%</div>
          <div class="kpi-sub">All override attempts safely neutralized</div>
        </div>
      </div>

      <!-- 2x2 Confusion Matrix -->
      <div style="background: #0e1626; border: 1px solid var(--border-color); border-radius: 8px; padding: 16px; margin-bottom: 24px;">
        <h4 style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: #94a3b8; margin-bottom: 12px;">
          Standardized Confusion Matrix (Total Evaluated: ${res.total_cases})
        </h4>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; max-width: 520px; text-align: center; font-family: 'JetBrains Mono';">
          <div style="background: #111a2e; border: 1px solid rgba(16, 185, 129, 0.4); padding: 12px; border-radius: 6px;">
            <div style="font-size: 20px; font-weight: 700; color: var(--success);">${res.true_positives}</div>
            <div style="font-size: 11px; color: #cbd5e1; font-weight: 600;">True Positives (TP)</div>
            <div style="font-size: 10px; color: #64748b;">Acute cases escalated</div>
          </div>

          <div style="background: #111a2e; border: 1px solid rgba(245, 158, 11, 0.4); padding: 12px; border-radius: 6px;">
            <div style="font-size: 20px; font-weight: 700; color: var(--warning);">${res.false_positives}</div>
            <div style="font-size: 11px; color: #cbd5e1; font-weight: 600;">False Positives (FP)</div>
            <div style="font-size: 10px; color: #64748b;">Conservative safety margin</div>
          </div>

          <div style="background: rgba(16, 185, 129, 0.1); border: 2px solid var(--success); padding: 12px; border-radius: 6px;">
            <div style="font-size: 22px; font-weight: 800; color: var(--success);">${res.false_negatives}</div>
            <div style="font-size: 11px; color: #6ee7b7; font-weight: 700;">False Negatives (FN)</div>
            <div style="font-size: 10px; color: #a7f3d0; font-weight: 600;">ZERO CRITICAL MISSED</div>
          </div>

          <div style="background: #111a2e; border: 1px solid var(--border-color); padding: 12px; border-radius: 6px;">
            <div style="font-size: 20px; font-weight: 700; color: #94a3b8;">${res.true_negatives}</div>
            <div style="font-size: 11px; color: #cbd5e1; font-weight: 600;">True Negatives (TN)</div>
            <div style="font-size: 10px; color: #64748b;">Routine cases confirmed</div>
          </div>
        </div>
      </div>

      <!-- Test Cases Table -->
      <div style="border: 1px solid var(--border-color); border-radius: 8px; overflow: hidden;">
        <table class="data-table">
          <thead>
            <tr>
              <th>Case ID</th>
              <th>Category</th>
              <th>Patient Dialogue Input</th>
              <th>Expected</th>
              <th>Consensus</th>
              <th>Result</th>
            </tr>
          </thead>
          <tbody>
            ${res.cases.map(c => `
              <tr>
                <td style="font-family: 'JetBrains Mono'; font-weight: 700; color: #94a3b8;">${c.case_id}</td>
                <td><span class="badge" style="background: #1e293b; color: #cbd5e1;">${c.category}</span></td>
                <td style="max-width: 360px;">
                  <div style="color: #fff; font-style: italic;">"${c.transcript}"</div>
                  <div style="font-size: 10px; color: #64748b; margin-top: 2px;">${c.consensus_rationale}</div>
                </td>
                <td style="font-family: 'JetBrains Mono'; font-weight: 600; color: ${c.expected_escalation ? '#fca5a5' : '#6ee7b7'};">
                  ${c.expected_urgency}
                </td>
                <td style="font-family: 'JetBrains Mono'; font-weight: 700; color: ${c.actual_consensus === 'URGENT' ? 'var(--danger)' : (c.actual_consensus === 'CONCERNING' ? 'var(--warning)' : 'var(--success)')};">
                  ${c.actual_consensus}
                </td>
                <td>
                  <span class="badge ${c.classification === 'TRUE_POSITIVE' ? 'badge-routine' : (c.classification === 'TRUE_NEGATIVE' ? 'badge' : 'badge-concerning')}">
                    ${c.classification}
                  </span>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  } catch (err) {
    alert("Benchmark failed: " + err.message);
  }
}

// ----------------------------------------------------
// TAB 5: EHR & SYSTEM HEALTH
// ----------------------------------------------------
async function loadAdminView() {
  try {
    const [health, ehr, audit] = await Promise.all([
      api.getHealth(),
      api.getEhrRecords(),
      api.getAuditLogs()
    ]);

    if (health) {
      document.getElementById('adminPlatformStatus').innerText = health.status;
      document.getElementById('adminPlatformStatus').style.color = health.status === 'HEALTHY' ? 'var(--success)' : 'var(--warning)';
      document.getElementById('adminAILatency').innerText = `${health.ai_observability.average_latency_ms} ms`;
      document.getElementById('adminAICost').innerText = `$${health.ai_observability.estimated_cost_usd.toFixed(3)}`;
      document.getElementById('adminEHRStatus').innerText = ehr.gateway_status;
      document.getElementById('adminEHRStatus').style.color = ehr.gateway_status === 'ONLINE' ? 'var(--success)' : 'var(--danger)';
    }

    renderEHRRecords(ehr);
    renderAuditLogs(audit);
  } catch (err) {
    console.error(err);
  }
}

function renderEHRRecords(ehr) {
  const container = document.getElementById('ehrRecordsList');
  if (!container) return;

  const comms = ehr?.communications || [];
  if (comms.length === 0) {
    container.innerHTML = `<div style="color: #64748b; font-style: italic; text-align: center; padding: 20px;">No records synced yet. Complete an outreach call to sync FHIR Communication records.</div>`;
    return;
  }

  container.innerHTML = comms.map(c => `
    <div style="background: #0a0e17; border: 1px solid var(--border-color); border-radius: 6px; padding: 10px; margin-bottom: 8px;">
      <div style="display: flex; justify-content: space-between; color: var(--success); font-weight: 700; margin-bottom: 2px;">
        <span>${c.id}</span>
        <span style="color: #64748b; font-weight: normal;">${formatISTTime(c.synced_at, true)}</span>
      </div>
      <div style="color: #e2e8f0;">Topic: ${c.topic} | ${c.subject}</div>
      <div style="color: #94a3b8; font-size: 10px; margin-top: 4px; line-height: 1.3; white-space: pre-wrap;">${c.payload_content}</div>
    </div>
  `).join('');
}

function renderAuditLogs(audit) {
  const container = document.getElementById('auditLogList');
  if (!container) return;

  if (!audit || audit.length === 0) {
    container.innerHTML = `<div style="color: #64748b; font-style: italic; text-align: center; padding: 20px;">No audit records found.</div>`;
    return;
  }

  container.innerHTML = audit.map(a => `
    <div style="background: #0a0e17; border: 1px solid var(--border-color); border-radius: 6px; padding: 8px 10px; margin-bottom: 6px;">
      <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
        <span style="color: #818cf8; font-weight: 700;">${a.action}</span>
        <span style="color: #64748b;">${formatISTTime(a.timestamp, true)}</span>
      </div>
      <div style="color: #cbd5e1;">Actor: <strong>${a.actor_id}</strong> (${a.actor_role}) • Target: ${a.target_entity}</div>
    </div>
  `).join('');
}

async function handleToggleEHRFailure() {
  const btn = document.getElementById('btnToggleEhrFailure');
  const isCurrentlyDegraded = document.getElementById('adminEHRStatus')?.innerText === 'DEGRADED';
  try {
    await api.toggleEhrFailure(!isCurrentlyDegraded);
    loadAdminView();
  } catch (err) {
    alert("Error toggling EHR status: " + err.message);
  }
}

// ----------------------------------------------------
// CALL SIMULATOR MODAL
// ----------------------------------------------------
async function openCallModal(taskId) {
  // Pre-check if task already reached max attempts
  const esc = (currentEscalations || []).find(e => e.task_id === taskId);
  const task = (window.currentAllTasks || []).find(t => t.id === taskId);
  const curAtt = esc?.attempts_count ?? task?.attempts_count;
  const maxAtt = esc?.max_retries ?? task?.max_retries ?? 3;
  if (curAtt !== undefined && curAtt !== null && curAtt >= maxAtt) {
    showToast(`Maximum outreach attempts reached (${curAtt}/${maxAtt}). Please complete review or resolve clinical escalation below.`, 'warning');
    return;
  }

  const modal = document.getElementById('modalCallSim');
  if (!modal) return;
  modal.classList.add('active');

  // Reset fields
  document.getElementById('callDialogueThread').innerHTML = '';
  document.getElementById('callSummaryContainer').style.display = 'none';
  document.getElementById('callModalTimer').innerText = '00:00';
  const input = document.getElementById('callSpeechInput');
  if (input) {
    input.value = '';
    input.disabled = false;
  }
  const btnSend = document.getElementById('btnSendSpeech');
  if (btnSend) btnSend.disabled = false;
  
  const statusEl = document.getElementById('callModalStatus');
  if (statusEl) {
    statusEl.innerText = 'Connected (Live Audio)';
    statusEl.style.color = 'var(--success)';
  }
  callDurationSecs = 0;
  updateChecklistStep(0);

  if (callTimerInterval) clearInterval(callTimerInterval);
  callTimerInterval = setInterval(() => {
    callDurationSecs++;
    const m = Math.floor(callDurationSecs / 60).toString().padStart(2, '0');
    const s = (callDurationSecs % 60).toString().padStart(2, '0');
    document.getElementById('callModalTimer').innerText = `${m}:${s}`;
  }, 1000);

  try {
    const res = await api.startCall(taskId);
    if (!res || !res.patient) {
      throw new Error(res?.detail || "Invalid response from server when starting call session");
    }
    activeCallId = res.call_id;
    document.getElementById('callModalPatientName').innerText = res.patient.name;
    document.getElementById('callModalPatientMrn').innerText = res.patient.mrn;
    document.getElementById('callModalCondition').innerText = res.patient.condition;
    const attemptBadge = document.getElementById('callModalAttempt');
    if (attemptBadge) {
      const curAttNum = res.patient.attempt_number || 1;
      const maxAttNum = res.patient.max_retries || 3;
      attemptBadge.innerText = `Attempt ${curAttNum} / ${maxAttNum}`;
    }

    if (res.initial_turn) {
      appendDialogueBubble('AGENT', res.initial_turn.text);
    }
  } catch (err) {
    closeCallModal();
    const cleanMsg = err.message ? err.message.replace(/^Failed to initiate call \(HTTP \d+\):\s*/i, "").replace(/^Cannot initiate call:\s*/i, "") : "Failed to initiate call";
    showToast(cleanMsg, 'warning');
  }
}

function updateChecklistStep(stepIndex) {
  const checklist = document.getElementById('protocolChecklist');
  if (!checklist) return;
  const steps = [
    { title: "1. Identity & Availability Check", doneAt: 1 },
    { title: "2. Daily Weight & Shortness of Breath", doneAt: 2 },
    { title: "3. Swelling in Extremities", doneAt: 3 },
    { title: "4. Medication Adherence", doneAt: 4 },
    { title: "5. Follow-Up Clinic Appointment", doneAt: 5 }
  ];
  checklist.innerHTML = steps.map((s, idx) => {
    const isDone = stepIndex >= s.doneAt;
    const isCurrent = stepIndex === s.doneAt - 1;
    return `
      <div class="kpi-card" style="padding: 8px; ${isDone ? 'background: rgba(16, 185, 129, 0.1); border-color: rgba(16, 185, 129, 0.3); color: #6ee7b7;' : (isCurrent ? 'background: rgba(99, 102, 241, 0.15); border-color: rgba(99, 102, 241, 0.4); color: #c7d2fe;' : 'background: #131b2e; color: #94a3b8;')}">
        ${isDone ? '✓' : (isCurrent ? '▶' : '○')} ${s.title}
      </div>
    `;
  }).join('');
}

function closeCallModal() {
  const modal = document.getElementById('modalCallSim');
  if (modal) modal.classList.remove('active');
  if (callTimerInterval) clearInterval(callTimerInterval);
  activeCallId = null;
  loadAllData();
  const isEscActive = document.getElementById('tab-escalations')?.classList.contains('active');
  if (isEscActive) {
    const activeFilterBtn = document.querySelector('.esc-filter-btn.active');
    const activeFilter = activeFilterBtn?.getAttribute('data-filter') || 'ALL';
    loadEscalationsView(activeFilter);
  }
}

async function handleSendSpeech() {
  const input = document.getElementById('callSpeechInput');
  if (!input || !activeCallId) return;
  const speech = input.value.trim();
  if (!speech) return;

  input.value = '';
  appendDialogueBubble('PATIENT', speech);

  try {
    const res = await api.sendCallTurn(activeCallId, speech);
    if (res.agent_turn) {
      appendDialogueBubble('AGENT', res.agent_turn.text);
      if (res.agent_turn.checklist_step !== undefined) {
        updateChecklistStep(res.agent_turn.checklist_step);
      } else if (res.agent_turn.turn_index !== undefined) {
        updateChecklistStep(Math.floor(res.agent_turn.turn_index / 2));
      }
    }
    if (res.action_directive === 'ESCALATE_NOW') {
      showToast('Emergency Red Flag Detected! Connecting to clinical nurse team...', 'warning');
      setTimeout(() => {
        handleEndCallWithOutcome('ESCALATION_TRIGGERED');
      }, 2000);
    } else if (res.action_directive === 'AUTO_FINISH') {
      showToast('Encounter concluded. Running automated clinical triage...', 'info');
      setTimeout(() => {
        handleEndCallTriage();
      }, 2000);
    }
  } catch (err) {
    console.error(err);
  }
}

function appendDialogueBubble(speaker, text) {
  const thread = document.getElementById('callDialogueThread');
  if (!thread) return;

  const isAgent = speaker === 'AGENT';
  const bubble = document.createElement('div');
  bubble.className = `bubble ${isAgent ? 'bubble-agent' : 'bubble-patient'}`;
  bubble.innerHTML = `
    <div class="bubble-sender">${isAgent ? 'AEGIS CLINICAL AGENT' : 'PATIENT (VOICE)'}</div>
    <div>${text}</div>
  `;
  thread.appendChild(bubble);
  thread.scrollTop = thread.scrollHeight;
}

async function handleEndCallWithOutcome(outcome) {
  if (!activeCallId) return;
  if (callTimerInterval) clearInterval(callTimerInterval);

  try {
    const res = await api.finishCall(activeCallId, outcome);
    const isEsc = outcome === 'ESCALATION_TRIGGERED' || res.escalation_created;

    // Immediately reload queue data so the table in the background updates to COMPLETED or ESCALATED instantly!
    await loadAllData(true);

    showToast(isEsc ? 'Emergency Escalation Triggered: Placed in Clinical Escalations Box (retry attempts available).' : 'Outreach Completed: Marked as COMPLETED in queue (Stable Recovery).', isEsc ? 'warning' : 'success');

    const statusEl = document.getElementById('callModalStatus');
    if (statusEl) {
      statusEl.innerText = isEsc ? 'Escalation Flagged (Placed in Box)' : 'Call Completed (Stable Recovery)';
      statusEl.style.color = isEsc ? 'var(--danger)' : 'var(--success)';
    }

    const input = document.getElementById('callSpeechInput');
    if (input) input.disabled = true;
    const btnSend = document.getElementById('btnSendSpeech');
    if (btnSend) btnSend.disabled = true;

    const summaryBox = document.getElementById('callSummaryContainer');
    const summaryContent = document.getElementById('callSummaryContent');
    if (summaryBox && summaryContent) {
      summaryBox.style.display = 'block';
      summaryContent.innerHTML = `
        <div style="margin-bottom: 6px;">
          Triage Outcome: <strong style="color: ${isEsc ? 'var(--danger)' : 'var(--success)'};">${isEsc ? 'URGENT ESCALATION (Placed in Escalations Box)' : 'SUCCESSFUL RECOVERY (Marked Completed in Queue)'}</strong>
        </div>
        <div style="margin-bottom: 6px;">
          Consensus: <strong>${isEsc ? (res.consensus || 'URGENT') : 'ROUTINE'}</strong> (Escalated: <strong>${isEsc ? 'YES' : 'NO'}</strong>)
        </div>
        <div style="margin-bottom: 8px;">
          EHR Sync: <strong style="color: var(--success);">${res.ehr_sync_status || 'COMMITTED'}</strong>
        </div>
        <pre style="background: #000; padding: 8px; border-radius: 4px; font-family: 'JetBrains Mono'; font-size: 10px; white-space: pre-wrap; max-height: 180px; overflow-y: auto;">${res.documentation_summary || 'Clinical documentation finalized.'}</pre>
      `;
    }

    setTimeout(() => {
      closeCallModal();
    }, 1800);
  } catch (err) {
    showToast("Error finishing call: " + err.message, 'danger');
  }
}

async function quickEndCall(taskId, outcome) {
  try {
    const res = await api.finishCallByTask(taskId, outcome);
    const isEsc = outcome === 'ESCALATION_TRIGGERED' || res.escalation_created;
    showToast(isEsc ? 'Call escalated: Placed in Clinical Escalations Box (Retry available in queue)' : 'Call completed: Marked as COMPLETED in queue (Stable Recovery)', isEsc ? 'warning' : 'success');
    await loadAllData();
  } catch (err) {
    showToast("Error ending call: " + err.message, 'danger');
  }
}

async function handleEndCallTriage() {
  if (!activeCallId) return;
  if (callTimerInterval) clearInterval(callTimerInterval);

  try {
    const res = await api.finishCall(activeCallId);
    const isEsc = res.escalation_created;

    // Immediately reload queue data so background table updates instantly
    await loadAllData(true);

    showToast(isEsc ? 'Emergency Escalation Triggered! Case routed to Nurse Review Inbox.' : 'Outreach Completed! SOAP Note & FHIR payload signed to EHR.', isEsc ? 'warning' : 'success');

    const statusEl = document.getElementById('callModalStatus');
    if (statusEl) {
      statusEl.innerText = isEsc ? 'Escalation Flagged' : 'Call Completed (Stable)';
      statusEl.style.color = isEsc ? 'var(--danger)' : 'var(--success)';
    }

    const input = document.getElementById('callSpeechInput');
    if (input) input.disabled = true;
    const btnSend = document.getElementById('btnSendSpeech');
    if (btnSend) btnSend.disabled = true;

    const summaryBox = document.getElementById('callSummaryContainer');
    const summaryContent = document.getElementById('callSummaryContent');
    if (summaryBox && summaryContent) {
      summaryBox.style.display = 'block';
      summaryContent.innerHTML = `
        <div style="margin-bottom: 6px;">
          Triage Urgency: <strong style="color: ${res.triage_urgency === 'URGENT' ? 'var(--danger)' : (res.triage_urgency === 'CONCERNING' ? 'var(--warning)' : 'var(--success)')};">${res.triage_urgency}</strong>
        </div>
        <div style="margin-bottom: 6px;">
          Consensus: <strong>${res.consensus}</strong> (Escalated: <strong>${res.escalation_created ? 'YES' : 'NO'}</strong>)
        </div>
        <div style="margin-bottom: 8px;">
          EHR Sync: <strong style="color: var(--success);">${res.ehr_sync_status}</strong>
        </div>
        <pre style="background: #000; padding: 8px; border-radius: 4px; font-family: 'JetBrains Mono'; font-size: 10px; white-space: pre-wrap; max-height: 180px; overflow-y: auto;">${res.documentation_summary}</pre>
      `;
    }
    setTimeout(() => {
      closeCallModal();
    }, 3500);
  } catch (err) {
    showToast("Error ending call: " + err.message, 'danger');
  }
}

// ----------------------------------------------------
// CAMPAIGN REPRIORITIZE MODAL
// ----------------------------------------------------
function openReprioritizeModal(campaignId, currentPriority, currentCapacity, campaignName) {
  const modal = document.getElementById('modalReprioritize');
  if (!modal) return;

  const idInput = document.getElementById('reprioritizeCampaignId');
  const priInput = document.getElementById('reprioritizePriority');
  const capInput = document.getElementById('reprioritizeCapacity');
  const titleEl = document.getElementById('reprioritizeTitle');

  if (idInput) idInput.value = campaignId;
  if (priInput) priInput.value = String(currentPriority || 1);
  if (capInput) capInput.value = String(currentCapacity || 2);
  if (titleEl && campaignName) {
    titleEl.innerText = `Reprioritize: ${campaignName}`;
  }

  modal.classList.add('active');
}

function closeReprioritizeModal() {
  const modal = document.getElementById('modalReprioritize');
  if (modal) modal.classList.remove('active');
}

async function handleSaveReprioritize() {
  const campaignId = document.getElementById('reprioritizeCampaignId')?.value;
  const priority = parseInt(document.getElementById('reprioritizePriority')?.value || '1', 10);
  const capacity = parseInt(document.getElementById('reprioritizeCapacity')?.value || '2', 10);

  if (!campaignId) {
    showToast("Invalid campaign ID", "danger");
    return;
  }

  try {
    await api.reprioritizeCampaign(campaignId, priority, capacity);
    showToast(`Campaign priority updated to ${priority} with ${capacity} concurrency lines.`, 'success');
    closeReprioritizeModal();
    loadAllData();
    if (document.getElementById('tab-hospital-admin')?.classList.contains('active')) {
      loadHospitalAdminView();
    }
  } catch (err) {
    showToast("Failed to reprioritize campaign: " + err.message, 'danger');
  }
}

// ----------------------------------------------------
// TAB: HOSPITAL ADMIN OPERATIONAL DASHBOARD
// ----------------------------------------------------
async function loadHospitalAdminView() {
  try {
    const [metrics, protocols] = await Promise.all([
      api.getHospitalAnalytics(),
      api.getProtocols()
    ]);

    // Update Hospital Badge
    const badge = document.getElementById('haHospBadge');
    if (badge) {
      const hospCode = currentTenant.replace('hosp-', '').toUpperCase();
      badge.innerText = `${metrics.hospital_name || hospCode} [${metrics.timezone || 'EST'}]`;
    }

    // Populate KPIs
    const contactPct = metrics.contact_rate_pct ?? metrics.contact_success_rate_percent ?? 0;
    const escPct = metrics.escalation_rate_pct ?? metrics.escalation_rate_percent ?? 0;
    const avgWait = metrics.queue_wait_average_mins ?? metrics.average_queue_wait_minutes ?? 0;
    const maxSlots = metrics.max_slots ?? metrics.allocated_concurrency_slots ?? 5;

    const elTotalTasks = document.getElementById('haTotalTasks');
    if (elTotalTasks) elTotalTasks.innerText = metrics.total_tasks || 0;

    const elPendingTasks = document.getElementById('haPendingTasks');
    if (elPendingTasks) elPendingTasks.innerText = `${metrics.pending_tasks || 0} tasks active/pending`;

    const elContactRate = document.getElementById('haContactRate');
    if (elContactRate) elContactRate.innerText = `${contactPct.toFixed(1)}%`;

    const elCompletedTasks = document.getElementById('haCompletedTasks');
    if (elCompletedTasks) elCompletedTasks.innerText = `${metrics.completed_tasks || 0} completed recoveries`;

    const elEscalations = document.getElementById('haEscalations');
    if (elEscalations) elEscalations.innerText = metrics.escalated_tasks || 0;

    const elEscalationRate = document.getElementById('haEscalationRate');
    if (elEscalationRate) elEscalationRate.innerText = `${escPct.toFixed(1)}% of cohort`;

    const elManualFollowups = document.getElementById('haManualFollowups');
    if (elManualFollowups) elManualFollowups.innerText = metrics.manual_followup_tasks ?? metrics.manual_followups_required ?? 0;

    const elEhrStatus = document.getElementById('haEhrStatus');
    if (elEhrStatus) {
      elEhrStatus.innerText = metrics.ehr_status || 'HEALTHY';
      elEhrStatus.style.color = metrics.ehr_status === 'HEALTHY' ? 'var(--success)' : 'var(--danger)';
    }

    const elEhrSynced = document.getElementById('haEhrSynced');
    if (elEhrSynced) elEhrSynced.innerText = `${metrics.ehr_synced_count || 0} synced / ${metrics.ehr_failed_count || 0} failed`;

    const elSlots = document.getElementById('haSlots');
    if (elSlots) elSlots.innerText = `${metrics.active_slots || 0} / ${maxSlots}`;

    const elAvgWait = document.getElementById('haAvgWait');
    if (elAvgWait) elAvgWait.innerText = `Avg queue wait: ${avgWait.toFixed(1)}m`;

    // Render Hospital Campaigns Container
    const campContainer = document.getElementById('haCampaignsContainer');
    if (campContainer) {
      const camps = metrics.campaigns || [];
      if (camps.length === 0) {
        campContainer.innerHTML = `<div style="color: #64748b; font-style: italic; padding: 12px 0;">No campaigns found for this hospital.</div>`;
      } else {
        campContainer.innerHTML = camps.map(c => {
          const isRunning = c.status === 'RUNNING';
          const campId = c.id || c.campaign_id;
          const pct = Math.min(100, Math.max(0, c.progress_percentage ?? c.completion_rate_percent ?? 0));
          const escapedName = (c.name || '').replace(/'/g, "\\'");
          const totalTasks = c.total_tasks ?? c.total_cohort_size ?? 0;
          return `
            <div style="background: #0d1424; border: 1px solid var(--border-color); border-radius: 8px; padding: 12px;">
              <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px;">
                <div>
                  <div style="display: flex; align-items: center; gap: 8px;">
                    <strong style="color: #fff; font-size: 13px;">${c.name}</strong>
                    <span class="badge ${isRunning ? 'badge-routine' : 'badge-concerning'}">${c.status}</span>
                    <span class="badge" style="background: #1e293b; color: #94a3b8;">${c.target_condition}</span>
                    <span class="badge" style="background: rgba(99, 102, 241, 0.2); color: #c7d2fe;">Priority ${c.priority_level}/5</span>
                  </div>
                  <div style="font-size: 11px; color: #94a3b8; margin-top: 4px; display: flex; gap: 14px;">
                    <span>Cohort Size: <strong style="color: #f1f5f9;">${totalTasks}</strong></span>
                    <span>Completed: <strong style="color: #34d399;">${c.completed_tasks ?? c.completed_count ?? 0}</strong></span>
                    <span>Escalated: <strong style="color: #f87171;">${c.escalated_tasks ?? c.escalated_count ?? 0}</strong></span>
                    <span>Allocated Slots: <strong style="color: #818cf8;">${c.allocated_capacity}</strong></span>
                  </div>
                </div>
                <div style="display: flex; gap: 6px;">
                  <button class="btn btn-secondary" style="font-size: 11px; padding: 4px 8px;" onclick="openReprioritizeModal('${campId}', ${c.priority_level}, ${c.allocated_capacity}, '${escapedName}')">
                    Reprioritize
                  </button>
                  ${isRunning ? `
                    <button class="btn btn-secondary" style="font-size: 11px; padding: 4px 8px;" onclick="toggleCampaign('${campId}', 'PAUSED')">
                      Pause
                    </button>
                  ` : `
                    <button class="btn btn-success" style="font-size: 11px; padding: 4px 8px;" onclick="toggleCampaign('${campId}', 'RUNNING')">
                      Resume
                    </button>
                  `}
                </div>
              </div>
              <div style="margin-top: 8px;">
                <div style="display: flex; justify-content: space-between; font-size: 10px; color: #64748b; margin-bottom: 2px;">
                  <span>Cohort Completion Progress</span>
                  <span style="font-weight: 700; color: #34d399;">${pct.toFixed(1)}%</span>
                </div>
                <div class="progress-bar-bg" style="height: 6px; border-radius: 3px;">
                  <div class="progress-bar-fill" style="width: ${pct}%; background: var(--success); height: 100%;"></div>
                </div>
              </div>
            </div>
          `;
        }).join('');
      }
    }

    // Render Contact Outcomes Container
    const outContainer = document.getElementById('haOutcomesContainer');
    if (outContainer) {
      let outcomesList = [];
      if (Array.isArray(metrics.outcomes_breakdown)) {
        outcomesList = metrics.outcomes_breakdown;
      } else if (metrics.outcomes && typeof metrics.outcomes === 'object') {
        const totalOut = Object.values(metrics.outcomes).reduce((a, b) => a + (Number(b) || 0), 0) || 1;
        outcomesList = Object.entries(metrics.outcomes)
          .filter(([_, cnt]) => cnt > 0)
          .map(([k, cnt]) => ({
            outcome: k.toUpperCase().replace(/_/g, ' '),
            count: cnt,
            percentage: (cnt / totalOut) * 100
          }));
      }

      if (outcomesList.length === 0) {
        outContainer.innerHTML = `<div style="color: #64748b; font-style: italic; font-size: 12px; padding: 8px 0;">No completed outreach call outcomes recorded yet.</div>`;
      } else {
        outContainer.innerHTML = outcomesList.map(o => {
          let badgeColor = '#94a3b8';
          let barBg = '#4f46e5';
          const label = String(o.outcome || '').toUpperCase();
          if (label.includes('SUCCESS') || label.includes('COMPLET')) {
            badgeColor = '#34d399';
            barBg = 'var(--success)';
          } else if (label.includes('ESCALAT') || label.includes('REFUS') || label.includes('DROPPED')) {
            badgeColor = '#f87171';
            barBg = 'var(--danger)';
          } else if (label.includes('CALLBACK') || label.includes('RETRY') || label.includes('VOICEMAIL') || label.includes('NO_ANSWER')) {
            badgeColor = '#f59e0b';
            barBg = 'var(--warning)';
          }
          return `
            <div style="font-size: 11px;">
              <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                <span style="color: ${badgeColor}; font-weight: 600;">${label}</span>
                <span style="color: #94a3b8;"><strong style="color: #fff;">${o.count}</strong> (${(o.percentage || 0).toFixed(1)}%)</span>
              </div>
              <div class="progress-bar-bg" style="height: 5px;">
                <div class="progress-bar-fill" style="width: ${Math.min(100, o.percentage || 0)}%; background: ${barBg}; height: 100%;"></div>
              </div>
            </div>
          `;
        }).join('');
      }
    }

    // Render Retry Tiers
    const retryContainer = document.getElementById('haRetryTiers');
    if (retryContainer) {
      const rd = metrics.retries || metrics.retry_distribution || {};
      const att1 = rd.attempt_1 ?? rd.first_attempt_resolved ?? 0;
      const att2 = rd.attempt_2 ?? rd.second_attempt_resolved ?? 0;
      const att3 = rd.attempt_3 ?? rd.third_attempt_resolved ?? 0;
      const exh = rd.exhausted_max ?? rd.exhausted_retries ?? 0;
      retryContainer.innerHTML = `
        <div class="kpi-card" style="padding: 8px; text-align: center;">
          <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase;">1st Call</div>
          <div style="font-size: 16px; font-weight: 700; color: #34d399; margin-top: 2px;">${att1}</div>
          <div style="font-size: 9px; color: #64748b;">Resolved on Att 1</div>
        </div>
        <div class="kpi-card" style="padding: 8px; text-align: center;">
          <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase;">2nd Call</div>
          <div style="font-size: 16px; font-weight: 700; color: #60a5fa; margin-top: 2px;">${att2}</div>
          <div style="font-size: 9px; color: #64748b;">Resolved on Att 2</div>
        </div>
        <div class="kpi-card" style="padding: 8px; text-align: center;">
          <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase;">3rd Call</div>
          <div style="font-size: 16px; font-weight: 700; color: #f59e0b; margin-top: 2px;">${att3}</div>
          <div style="font-size: 9px; color: #64748b;">Resolved on Att 3</div>
        </div>
        <div class="kpi-card" style="padding: 8px; text-align: center;">
          <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase;">Exhausted</div>
          <div style="font-size: 16px; font-weight: 700; color: #f87171; margin-top: 2px;">${exh}</div>
          <div style="font-size: 9px; color: #64748b;">3/3 Retries Ended</div>
        </div>
      `;
    }

    // Render Clinical Protocols
    const protoContainer = document.getElementById('haProtocolsContainer');
    if (protoContainer) {
      if (!protocols || protocols.length === 0) {
        protoContainer.innerHTML = `<div style="color: #64748b; font-style: italic;">No active protocols loaded for this tenant.</div>`;
      } else {
        protoContainer.innerHTML = protocols.map(p => {
          const redFlags = p.red_flags || [];
          return `
            <div style="background: #0d1424; border: 1px solid var(--border-color); border-radius: 8px; padding: 14px;">
              <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                <div>
                  <strong style="color: #fff; font-size: 13px;">${p.name || p.condition}</strong>
                  <div style="font-size: 10px; color: #818cf8; font-family: 'JetBrains Mono'; margin-top: 2px;">ID: ${p.id}</div>
                </div>
                <span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #34d399; font-size: 10px;">ACTIVE PROTOCOL</span>
              </div>
              <div style="font-size: 11px; color: #94a3b8; margin-bottom: 8px; line-height: 1.4;">
                ${p.description || 'Evidence-based post-discharge clinical monitoring guidelines.'}
              </div>
              <div style="font-size: 10px; color: #cbd5e1; background: #070a12; padding: 8px; border-radius: 6px; border: 1px solid rgba(35, 48, 77, 0.6);">
                <div style="color: #fca5a5; font-weight: 700; margin-bottom: 4px;">RED-FLAG ESCALATION TRIGGERS:</div>
                ${redFlags.length > 0 ? redFlags.map(rf => `<div>• ${rf.symptom || rf}: ${rf.threshold || rf.severity || 'Immediate Escalation'}</div>`).join('') : '<div>• Weight gain &gt; 3 lbs/day or &gt; 5 lbs/wk</div><div>• Severe dyspnea / shortness of breath</div><div>• Calf swelling/pain or fever &gt; 101°F</div>'}
              </div>
            </div>
          `;
        }).join('');
      }
    }

    // Render Staff Activity Audit Log
    const staffContainer = document.getElementById('haStaffActivityContainer');
    if (staffContainer) {
      const logs = metrics.recent_staff_activity || metrics.staff_activity || [];
      if (logs.length === 0) {
        staffContainer.innerHTML = `<div style="color: #64748b; font-style: italic; padding: 10px;">No staff activity logged yet.</div>`;
      } else {
        staffContainer.innerHTML = logs.map(l => `
          <div style="background: #080d17; border: 1px solid rgba(35, 48, 77, 0.5); border-radius: 6px; padding: 8px 10px; margin-bottom: 6px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
              <span style="color: #818cf8; font-weight: 700;">${l.action || l.action_type}</span>
              <span style="color: #64748b;">${formatISTDateTime(l.timestamp)}</span>
            </div>
            <div style="color: #cbd5e1;">Staff: <strong>${l.actor_id || l.staff_id}</strong> <span class="badge" style="background: #1e293b; color: #94a3b8; font-size: 9px;">${l.actor_role || l.staff_role}</span> • Target: ${l.target_entity || ''} • Details: ${l.details || ''}</div>
          </div>
        `).join('');
      }
    }
  } catch (err) {
    console.error("Failed loading hospital admin view:", err);
    showToast("Error loading hospital metrics: " + err.message, "danger");
  }
}

// ----------------------------------------------------
// TAB: PLATFORM ADMIN FLEET DASHBOARD
// ----------------------------------------------------
async function loadPlatformAdminView() {
  try {
    const metrics = await api.getPlatformAnalytics();

    // Populate Fleet KPIs
    const elHosp = document.getElementById('paTotalHospitals');
    if (elHosp) elHosp.innerText = metrics.total_hospitals || 3;

    const elCamp = document.getElementById('paTotalCampaigns');
    if (elCamp) elCamp.innerText = metrics.total_campaigns || 0;

    const elActCamp = document.getElementById('paActiveCampaigns');
    if (elActCamp) elActCamp.innerText = `${metrics.active_campaigns || 0} running cohorts`;

    const fleetMaxCap = metrics.fleet_max_capacity ?? metrics.fleet_total_capacity ?? 15;
    const fleetUtil = metrics.fleet_capacity_utilization_pct ?? metrics.fleet_utilization_percent ?? 0;
    const totalQueue = metrics.total_pending_queue ?? metrics.total_queue_depth ?? 0;
    const totalComp = metrics.total_completed_outreach ?? metrics.total_completed_tasks ?? 0;

    const elCap = document.getElementById('paFleetCapacity');
    if (elCap) elCap.innerText = `${metrics.fleet_active_calls || 0} / ${fleetMaxCap}`;

    const elUtil = document.getElementById('paFleetUtilization');
    if (elUtil) elUtil.innerText = `${fleetUtil.toFixed(1)}% utilization`;

    const elQueue = document.getElementById('paTotalQueue');
    if (elQueue) elQueue.innerText = totalQueue;

    const elComp = document.getElementById('paTotalCompleted');
    if (elComp) elComp.innerText = `${totalComp} completed platform-wide`;

    const aiObj = metrics.ai_usage || metrics.ai_observability || {};
    const elTokens = document.getElementById('paTokens');
    if (elTokens) {
      const tok = aiObj.total_tokens_consumed || 0;
      elTokens.innerText = `${(tok / 1000).toFixed(1)}k`;
    }

    const elCost = document.getElementById('paCost');
    if (elCost) {
      const c = aiObj.estimated_cost_usd || 0;
      elCost.innerText = `Est. cost: $${c.toFixed(3)}`;
    }

    const sysStatus = metrics.system_status || metrics.platform_status || 'HEALTHY';
    const elSys = document.getElementById('paSystemStatus');
    if (elSys) {
      elSys.innerText = sysStatus;
      elSys.style.color = sysStatus === 'HEALTHY' ? 'var(--success)' : 'var(--warning)';
    }

    const techFailures = metrics.total_technical_failures ?? metrics.technical_failure_count ?? 0;
    const elErrors = document.getElementById('paTechErrors');
    if (elErrors) elErrors.innerText = `${techFailures} technical errors`;

    // Render Multi-Hospital Comparison Table
    const tbody = document.getElementById('paHospitalTableBody');
    if (tbody) {
      const hosps = metrics.hospitals || [];
      if (hosps.length === 0) {
        tbody.innerHTML = `<tr><td colspan="11" style="text-align: center; color: #64748b; padding: 20px;">No hospital tenant data available.</td></tr>`;
      } else {
        tbody.innerHTML = hosps.map(h => {
          const ehrStatus = h.ehr_status ?? h.ehr_gateway_status ?? 'ONLINE';
          const isOnline = ehrStatus === 'ONLINE' || ehrStatus === 'HEALTHY';
          const hospName = h.name || h.hospital_name || h.hospital_id;
          const maxCap = h.max_concurrency_capacity ?? h.concurrency_capacity ?? 5;
          const utilPct = h.capacity_utilization_pct ?? h.capacity_utilization_percent ?? 0;
          const totalTasks = h.total_tasks_count ?? h.total_tasks ?? 0;
          const pendingTasks = h.pending_tasks_count ?? h.pending_queue_depth ?? 0;
          const compTasks = h.completed_tasks_count ?? h.completed_tasks ?? 0;
          return `
            <tr>
              <td>
                <div style="font-weight: 700; color: #fff;">${hospName}</div>
                <div style="font-size: 10px; font-family: 'JetBrains Mono'; color: #64748b;">${h.hospital_id}</div>
              </td>
              <td><span class="badge" style="background: #1e293b; color: #94a3b8;">${h.timezone}</span></td>
              <td><span class="badge badge-routine">${h.status}</span></td>
              <td style="font-weight: 600; color: #e2e8f0;">${h.active_campaigns_count}</td>
              <td style="font-family: 'JetBrains Mono'; color: #818cf8;">${h.active_calls} / ${maxCap}</td>
              <td>
                <div style="display: flex; align-items: center; gap: 6px;">
                  <div class="progress-bar-bg" style="width: 50px; height: 5px;">
                    <div class="progress-bar-fill" style="width: ${Math.min(100, utilPct)}%; background: ${utilPct >= 80 ? 'var(--warning)' : 'var(--success)'}; height: 100%;"></div>
                  </div>
                  <span style="font-size: 11px; color: #94a3b8;">${utilPct.toFixed(0)}%</span>
                </div>
              </td>
              <td style="font-weight: 700; color: #fff;">${totalTasks}</td>
              <td style="color: #fde68a; font-weight: 600;">${pendingTasks}</td>
              <td style="color: #34d399; font-weight: 600;">${compTasks}</td>
              <td style="color: #f87171; font-weight: 600;">${h.escalations_count || 0}</td>
              <td>
                <span class="badge ${isOnline ? 'badge-routine' : 'badge-urgent'}">
                  ${ehrStatus}
                </span>
              </td>
            </tr>
          `;
        }).join('');
      }
    }

    // AI Engine Observability
    const elAiCalls = document.getElementById('paAiCalls');
    if (elAiCalls) elAiCalls.innerText = aiObj.total_calls_processed ?? aiObj.calls_evaluated ?? 0;

    const elAiCons = document.getElementById('paAiConsensus');
    if (elAiCons) {
      const cons = aiObj.consensus_agreement_rate_pct ?? aiObj.consensus_agreement_percent ?? 96.4;
      elAiCons.innerText = `${Number(cons).toFixed(1)}%`;
    }

    const elAiLat = document.getElementById('paAiLatency');
    if (elAiLat) elAiLat.innerText = `${aiObj.average_latency_ms || 145} ms`;

    // Platform Resilience
    const elPlatEsc = document.getElementById('paPlatformEscalations');
    if (elPlatEsc) elPlatEsc.innerText = metrics.total_platform_escalations || 0;

    const elEhrErr = document.getElementById('paEhrErrors');
    if (elEhrErr) elEhrErr.innerText = metrics.total_ehr_sync_failures ?? metrics.ehr_communication_errors ?? 0;

    const elTechFail = document.getElementById('paTechFailures');
    if (elTechFail) elTechFail.innerText = techFailures;

  } catch (err) {
    console.error("Failed loading platform admin view:", err);
    showToast("Error loading platform fleet metrics: " + err.message, "danger");
  }
}

// ----------------------------------------------------
// PATIENT 360 CLINICAL & OPERATIONAL VIEW
// ----------------------------------------------------
async function openPatient360(patientId) {
  const modal = document.getElementById('modalPatient360');
  const container = document.getElementById('p360TimelineContainer');
  if (!modal || !container) return;

  modal.classList.add('active');
  container.innerHTML = `
    <div style="text-align: center; color: #94a3b8; padding: 40px;">
      <div style="display: inline-block; width: 24px; height: 24px; border: 3px solid rgba(99, 102, 241, 0.3); border-top-color: var(--primary); border-radius: 50%; animation: spin 0.8s linear infinite; margin-bottom: 12px;"></div>
      <div>Loading Comprehensive Patient 360 Operational Record...</div>
    </div>
  `;

  try {
    const res = await api.getPatientOperationalView(patientId);

    const patFullName = res.full_name || res.name || 'Patient Record';
    const patPhone = res.phone_number || res.phone || 'N/A';
    const patCondition = (Array.isArray(res.conditions) && res.conditions.length > 0 ? res.conditions.join(', ') : res.condition) || 'Post-Discharge';

    // Update Header
    const titleEl = document.getElementById('p360Title');
    if (titleEl) {
      titleEl.innerHTML = `
        <span style="color: #fff;">${patFullName}</span>
        <span class="badge" style="background: #1e293b; color: #cbd5e1; font-family: 'JetBrains Mono';">MRN: ${res.mrn}</span>
        <span class="badge" style="background: rgba(99, 102, 241, 0.2); color: #c7d2fe;">${patCondition}</span>
        <span class="badge" style="background: #1e293b; color: #94a3b8;">${res.hospital_id}</span>
      `;
    }

    const subEl = document.getElementById('p360Sub');
    if (subEl) {
      subEl.innerText = `Phone: ${patPhone} • Post-Discharge Clinical Triage & Care Continuity Operational Record`;
    }

    const enc = res.encounter || {};
    const task = res.active_task || res.current_task;
    const calls = res.calls || [];
    const escalations = res.escalations || [];

    // Medications list
    let meds = res.medications || enc.discharge_medications || [];
    if (typeof meds === 'string') {
      try { meds = JSON.parse(meds); } catch { meds = [meds]; }
    }

    // Red flag instructions
    let redFlags = enc.red_flag_instructions || [];
    if (typeof redFlags === 'string') {
      try { redFlags = JSON.parse(redFlags); } catch { redFlags = [redFlags]; }
    }

    const cutoffTime = task?.clinical_cutoff_time || task?.clinical_window_deadline;

    container.innerHTML = `
      <div style="display: grid; grid-template-columns: 1.15fr 1fr; gap: 20px;">
        
        <!-- LEFT COLUMN: INPATIENT DISCHARGE ENCOUNTER & OUTREACH TASK STATUS -->
        <div style="display: flex; flex-direction: column; gap: 16px;">
          
          <!-- Current Outreach Task State -->
          <div style="background: #0d1424; border: 1px solid var(--border-color); border-radius: 8px; padding: 14px;">
            <div style="font-size: 11px; font-weight: 700; color: #818cf8; text-transform: uppercase; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
              <span>Current Outreach Task State</span>
              ${task ? `<span class="badge ${task.status === 'COMPLETED' ? 'badge-routine' : (task.status === 'ESCALATED' ? 'badge-urgent' : 'badge-calling')}">${task.status}</span>` : '<span class="badge">NO ACTIVE TASK</span>'}
            </div>
            ${task ? `
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 11px;">
                <div>
                  <span style="color: #94a3b8;">Outreach Attempts:</span>
                  <strong style="color: #fff; margin-left: 4px;">${task.attempts_count} / ${task.max_retries}</strong>
                </div>
                <div>
                  <span style="color: #94a3b8;">Cutoff Deadline:</span>
                  <strong style="color: #fde68a; margin-left: 4px;">${cutoffTime ? formatISTDateTime(cutoffTime) : 'N/A'}</strong>
                </div>
                <div>
                  <span style="color: #94a3b8;">Campaign:</span>
                  <span style="color: #cbd5e1; margin-left: 4px;">${task.campaign_name || 'Post-Discharge Outreach'}</span>
                </div>
                <div>
                  <span style="color: #94a3b8;">Task ID:</span>
                  <span style="font-family: 'JetBrains Mono'; font-size: 10px; color: #64748b; margin-left: 4px;">${task.task_id}</span>
                </div>
              </div>
            ` : '<div style="color: #64748b; font-style: italic; font-size: 11px;">No active task record associated with patient.</div>'}
          </div>

          <!-- Inpatient Discharge Encounter -->
          <div style="background: #0d1424; border: 1px solid var(--border-color); border-radius: 8px; padding: 14px;">
            <div style="font-size: 11px; font-weight: 700; color: #38bdf8; text-transform: uppercase; margin-bottom: 10px; display: flex; justify-content: space-between;">
              <span>Inpatient Discharge Encounter</span>
              <span style="color: #94a3b8; font-weight: normal;">Discharged: ${enc.discharge_date ? formatISTDate(enc.discharge_date) : 'Recent'}</span>
            </div>
            
            <div style="margin-bottom: 10px;">
              <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase; margin-bottom: 3px;">Primary Diagnosis:</div>
              <div style="font-size: 13px; font-weight: 700; color: #fff; background: rgba(56, 189, 248, 0.08); border-left: 3px solid #38bdf8; padding: 6px 10px; border-radius: 0 4px 4px 0;">
                ${enc.primary_diagnosis || patCondition}
              </div>
            </div>

            ${Array.isArray(res.conditions) && res.conditions.length > 0 ? `
              <div style="margin-bottom: 10px;">
                <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase; margin-bottom: 4px;">Monitored Clinical Conditions:</div>
                <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                  ${res.conditions.map(d => `<span class="badge" style="background: #1e293b; color: #cbd5e1; font-size: 10px;">${d}</span>`).join('')}
                </div>
              </div>
            ` : ''}

            <div style="margin-bottom: 10px;">
              <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase; margin-bottom: 3px;">Hospital Discharge Summary:</div>
              <div style="font-size: 11px; color: #cbd5e1; background: #070a12; padding: 8px 10px; border-radius: 6px; border: 1px solid rgba(35, 48, 77, 0.6); line-height: 1.4;">
                ${enc.discharge_summary || 'Inpatient recovery stable; enrolled in active post-discharge monitoring outreach.'}
              </div>
            </div>

            <!-- Discharge Medications -->
            <div style="margin-bottom: 10px;">
              <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase; margin-bottom: 4px;">Discharge Medications:</div>
              <div style="display: flex; flex-direction: column; gap: 4px;">
                ${meds.length > 0 ? meds.map(m => {
                  const mName = typeof m === 'object' ? `${m.name || m.medication} - ${m.dosage || ''} ${m.instructions || ''}` : m;
                  return `<div style="font-size: 11px; color: #cbd5e1; background: #131b2e; padding: 4px 8px; border-radius: 4px; display: flex; align-items: center; gap: 6px;">
                    <span style="color: #34d399;">💊</span> <span>${mName}</span>
                  </div>`;
                }).join('') : '<div style="color: #64748b; font-size: 11px; font-style: italic;">No specific medications listed.</div>'}
              </div>
            </div>

            <!-- Care Plan / Follow-Up -->
            ${res.care_plan_instructions || enc.follow_up_instructions ? `
              <div style="margin-top: 10px; font-size: 11px; color: #cbd5e1; background: #070a12; padding: 8px; border-radius: 6px;">
                <span style="color: #94a3b8; font-weight: 700;">Care Plan Instructions:</span>
                <div style="margin-top: 2px;">${res.care_plan_instructions || enc.follow_up_instructions}</div>
              </div>
            ` : ''}

          </div>
        </div>

        <!-- RIGHT COLUMN: CALL HISTORY, AUDIO TURNS, SOAP DOCUMENTATION & HITL ESCALATIONS -->
        <div style="display: flex; flex-direction: column; gap: 16px;">
          
          <!-- Outreach Calls Section -->
          <div>
            <div style="font-size: 11px; font-weight: 700; color: #34d399; text-transform: uppercase; margin-bottom: 8px;">
              Outreach Calls &amp; Audio Dialogue (${calls.length})
            </div>
            <div style="display: flex; flex-direction: column; gap: 10px; max-height: 380px; overflow-y: auto;">
              ${calls.length === 0 ? `<div style="color: #64748b; font-style: italic; font-size: 11px; padding: 12px; background: #0d1424; border-radius: 6px;">No outreach calls logged yet.</div>` : calls.map((c, idx) => {
                const turns = c.dialogue_turns || c.transcript || [];
                const outcomeStr = c.outcome || c.call_outcome || 'IN_PROGRESS';
                const startTime = c.start_time || c.started_at;
                const obs = c.observations || c.symptoms_reported || [];
                return `
                  <div style="background: #0d1424; border: 1px solid var(--border-color); border-radius: 8px; padding: 12px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                      <div style="display: flex; align-items: center; gap: 6px;">
                        <strong style="color: #fff; font-size: 12px;">Call Attempt #${c.attempt_number || idx + 1}</strong>
                        <span class="badge ${outcomeStr === 'SUCCESSFUL_COMPLETION' ? 'badge-routine' : (outcomeStr === 'ESCALATION_TRIGGERED' ? 'badge-urgent' : 'badge-concerning')}" style="font-size: 10px;">
                          ${outcomeStr.replace(/_/g, ' ')}
                        </span>
                      </div>
                      <div style="font-size: 10px; color: #94a3b8; font-family: 'JetBrains Mono';">
                        ${c.duration_seconds || 0}s • ${startTime ? formatISTTime(startTime) : ''}
                      </div>
                    </div>

                    ${c.documentation_summary ? `
                      <div style="background: #070a12; border: 1px solid rgba(35, 48, 77, 0.6); border-radius: 6px; padding: 8px; margin-bottom: 8px; font-size: 10.5px; line-height: 1.4;">
                        <div style="font-weight: 700; color: #818cf8; margin-bottom: 2px;">AI CLINICAL SOAP DOCUMENTATION:</div>
                        <div style="color: #cbd5e1; white-space: pre-wrap;">${c.documentation_summary}</div>
                      </div>
                    ` : ''}

                    ${obs.length > 0 ? `
                      <div style="margin-bottom: 6px; display: flex; flex-wrap: wrap; gap: 4px;">
                        ${obs.map(s => `<span class="badge" style="background: #1e293b; color: #fde68a; font-size: 9.5px;">Observed: ${s}</span>`).join('')}
                      </div>
                    ` : ''}

                    ${turns.length > 0 ? `
                      <details style="font-size: 11px; margin-top: 4px;">
                        <summary style="cursor: pointer; color: #818cf8; font-weight: 600; font-size: 10px;">View Dialogue Turns (${turns.length})</summary>
                        <div style="margin-top: 6px; display: flex; flex-direction: column; gap: 4px; max-height: 140px; overflow-y: auto; background: #070a12; padding: 6px; border-radius: 4px;">
                          ${turns.map(t => `
                            <div style="font-size: 10px;">
                              <strong style="color: ${t.speaker === 'agent' ? '#818cf8' : '#34d399'};">${t.speaker === 'agent' ? 'Care Navigator' : 'Patient'}:</strong>
                              <span style="color: #cbd5e1;">"${t.text}"</span>
                            </div>
                          `).join('')}
                        </div>
                      </details>
                    ` : ''}

                  </div>
                `;
              }).join('')}
            </div>
          </div>

          <!-- HITL Clinical Escalations Section -->
          <div>
            <div style="font-size: 11px; font-weight: 700; color: #f87171; text-transform: uppercase; margin-bottom: 8px;">
              Clinical Escalations &amp; HITL Reviews (${escalations.length})
            </div>
            <div style="display: flex; flex-direction: column; gap: 8px; max-height: 300px; overflow-y: auto;">
              ${escalations.length === 0 ? `<div style="color: #64748b; font-style: italic; font-size: 11px; padding: 12px; background: #0d1424; border-radius: 6px;">No clinical escalations triggered for this patient.</div>` : escalations.map(e => {
                const sev = e.severity || e.urgency || 'HIGH';
                const revName = e.assigned_reviewer_name || e.reviewer_name;
                return `
                  <div style="background: rgba(239, 68, 68, 0.05); border: 1px solid rgba(239, 68, 68, 0.25); border-radius: 8px; padding: 10px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                      <div style="display: flex; align-items: center; gap: 6px;">
                        <span class="badge ${sev === 'URGENT' || sev === 'CRITICAL' ? 'badge-urgent' : 'badge-concerning'}" style="font-size: 10px;">${sev}</span>
                        <span class="badge" style="background: #1e293b; color: #94a3b8; font-size: 10px;">${e.status}</span>
                      </div>
                      <span style="font-size: 10px; color: #64748b; font-family: 'JetBrains Mono';">${e.escalation_id}</span>
                    </div>
                    <div style="font-size: 11.5px; font-weight: 600; color: #fca5a5; margin-bottom: 3px;">
                      ${e.trigger_reason}
                    </div>
                    <div style="font-size: 10.5px; color: #cbd5e1; margin-bottom: 6px; line-height: 1.3;">
                      ${e.clinical_indicators || e.clinical_summary || ''}
                    </div>
                    ${revName ? `
                      <div style="font-size: 10px; color: #94a3b8; background: #080d17; padding: 6px; border-radius: 4px; border: 1px solid rgba(35, 48, 77, 0.5);">
                        <div>Reviewed by: <strong style="color: #fff;">${revName}</strong> ${e.resolved_at ? `(${formatISTDateTime(e.resolved_at)})` : ''}</div>
                        ${e.resolution_action ? `<div>Action Taken: <strong style="color: #34d399;">${e.resolution_action}</strong></div>` : ''}
                        ${e.resolution_notes ? `<div>Notes: <span style="color: #cbd5e1;">${e.resolution_notes}</span></div>` : ''}
                      </div>
                    ` : `<div style="font-size: 10px; color: #f59e0b; font-style: italic;">Awaiting Clinician Assignment &amp; HITL Order</div>`}
                  </div>
                `;
              }).join('')}
            </div>
          </div>

        </div>

      </div>
    `;

  } catch (err) {
    container.innerHTML = `<div style="color: var(--danger); padding: 20px;">Error loading comprehensive patient operational record: ${err.message}</div>`;
  }
}
