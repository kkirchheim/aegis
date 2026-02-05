/**
 * Detail Page - Unified Polling Approach
 * Single source of truth: calls /api/job/<id>/full every 200ms
 * Updates all UI components from complete job state
 */

let currentJob = null;
let pollInterval = null;
let lastStage = null;

// DOM Elements
const statusContent = document.getElementById("statusContent");
const progressFill = document.getElementById("progressFill");
const progressText = document.getElementById("progressText");
const eventLog = document.getElementById("eventLog");
const logSection = document.getElementById("logSection");
const progressSection = document.getElementById("progressSection");
const metadataContent = document.getElementById("metadataContent");
const citationsContent = document.getElementById("citationsContent");
const citationCount = document.getElementById("citationCount");
const artifactsContent = document.getElementById("artifactsContent");
const aspectsContent = document.getElementById("aspectsContent");
const chatSection = document.getElementById("chatSection");

const deleteBtn = document.getElementById("deleteBtn");
const deleteModal = document.getElementById("deleteModal");
const cancelDeleteBtn = document.getElementById("cancelDeleteBtn");
const confirmDeleteBtn = document.getElementById("confirmDeleteBtn");

const docTitle = document.getElementById("docTitle");
const docMeta = document.getElementById("docMeta");

const chatHistory = document.getElementById("chatHistory");
const chatInput = document.getElementById("chatInput");
const chatSendBtn = document.getElementById("chatSendBtn");
const chatClearBtn = document.getElementById("chatClearBtn");

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener("DOMContentLoaded", () => {
    console.log(`[unified-polling] Starting for JOB_ID=${JOB_ID}`);
    
    if (!JOB_ID) {
        statusContent.innerHTML = "<div class='alert alert-error'>No job ID provided</div>";
        return;
    }
    
    setupEventListeners();
    startUnifiedPolling();  // Poll every 200ms
});

window.addEventListener("beforeunload", () => {
    stopPolling();
});

// ============================================================================
// Unified Polling (200ms)
// ============================================================================

function startUnifiedPolling() {
    console.log(`[polling] Starting unified polling every 200ms`);
    pollOnce();  // Immediate first poll
    pollInterval = setInterval(pollOnce, 200);
}

function stopPolling() {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
        console.log(`[polling] Stopped`);
    }
}

async function pollOnce() {
    try {
        const response = await fetch(`/api/job/${JOB_ID}/full`, {
            credentials: 'include'
        });
        
        if (!response.ok) {
            console.warn(`[polling] Failed: HTTP ${response.status}`);
            return;
        }
        
        const job = await response.json();
        currentJob = job;
        
        console.log(`[polling] Received: status=${job.status}, progress=${job.progress}, stage=${job.current_stage}, events=${job.events.length}`);
        
        // Update all UI components - each in its own try-catch so failures don't stop others
        try { updateProgressBar(job); } catch (e) { console.error(`[update] progressBar failed:`, e); }
        try { updateStages(job); } catch (e) { console.error(`[update] stages failed:`, e); }
        try { updateStatus(job); } catch (e) { console.error(`[update] status failed:`, e); }
        try { updateEventLog(job); } catch (e) { console.error(`[update] eventLog failed:`, e); }
        try { updateMetadata(job); } catch (e) { console.error(`[update] metadata failed:`, e); }
        try { updateCitations(job); } catch (e) { console.error(`[update] citations failed:`, e); }
        try { updateArtifacts(job); } catch (e) { console.error(`[update] artifacts failed:`, e); }
        try { updateAspects(job); } catch (e) { console.error(`[update] aspects failed:`, e); }
        
        // Stop polling when complete
        if (job.status === "completed" || job.status === "failed") {
            stopPolling();
        }
        
    } catch (error) {
        console.error(`[polling] Fetch error:`, error);
    }
}

// ============================================================================
// UI Update Functions
// ============================================================================

function updateProgressBar(job) {
    console.log(`[update] progressBar: progressFill=${!!progressFill}, progressText=${!!progressText}`);
    if (!progressFill || !progressText) {
        console.warn(`[update] progressBar skipped - missing DOM elements`);
        return;
    }
    
    const percent = Math.round((job.progress || 0) * 100);
    progressFill.value = percent;
    progressText.textContent = `${percent}%`;
    console.log(`[update] progressBar: Set to ${percent}%`);
}

function updateStages(job) {
    const stage = job.current_stage || "pending";
    
    if (stage !== lastStage) {
        lastStage = stage;
        
        const stageMap = {
            'paper_analysis': 'stage1',
            'code_execution': 'stage2',
            'evaluation': 'stage3'
        };
        
        const stages = ['stage1', 'stage2', 'stage3'];
        const stageKey = stageMap[stage];
        let currentIndex = -1;
        
        if (stage === 'completed' || stage === 'failed') {
            currentIndex = 999;
        } else {
            currentIndex = stages.indexOf(stageKey);
        }
        
        stages.forEach((s, i) => {
            const icon = document.getElementById(`${s}Icon`);
            if (icon) {
                if (i < currentIndex) {
                    icon.textContent = "✓";
                    icon.style.color = "#22c55e";
                } else if (i === currentIndex && currentIndex !== 999) {
                    icon.textContent = "▶";
                    icon.style.color = "#ffa500";
                    icon.className = "text-2xl mb-1 animate-pulse";
                } else if (currentIndex === 999) {
                    icon.textContent = "✓";
                    icon.style.color = "#22c55e";
                } else {
                    icon.textContent = "○";
                    icon.style.color = "rgba(0,0,0,0.3)";
                }
            }
        });
    }
}

function updateStatus(job) {
    console.log(`[update] status: statusContent=${!!statusContent}`);
    if (!statusContent) {
        console.warn(`[update] status skipped - missing statusContent`);
        return;
    }
    
    const statusText = {
        'pending': 'Pending',
        'processing': 'Processing',
        'completed': 'Completed',
        'failed': 'Failed',
        'error': 'Error'
    }[job.status] || job.status;
    
    const statusClass = {
        'pending': 'badge-warning',
        'processing': 'badge-info',
        'completed': 'badge-success',
        'failed': 'badge-error',
        'error': 'badge-error'
    }[job.status] || 'badge-gray';
    
    statusContent.innerHTML = `<div class="badge ${statusClass}">${statusText}</div>`;
    
    if (job.error_message) {
        statusContent.innerHTML += `<div class="alert alert-error mt-2"><p>${job.error_message}</p></div>`;
    }
    
    console.log(`[update] status: Rendered as "${statusText}"`);
}

function updateEventLog(job) {
    console.log(`[update] eventLog: eventLog=${!!eventLog}, events=${job.events?.length || 0}`);
    if (!eventLog) {
        console.warn(`[update] eventLog skipped - missing eventLog element`);
        return;
    }
    
    // Clear and rebuild entire log from scratch
    eventLog.innerHTML = "";
    
    if (!job.events || job.events.length === 0) {
        eventLog.innerHTML = "<div class='text-base-content/50'>No events yet</div>";
        return;
    }
    
    // Show all events in chronological order
    job.events.forEach(event => {
        if (event.step && (event.step.startsWith('chat_') || event.step === 'chat_error')) {
            return;  // Skip chat events
        }
        
        const time = new Date(event.timestamp).toLocaleTimeString();
        const stepLabel = event.step ? `[${event.step}]` : "";
        const severityClass = {
            'error': 'text-error',
            'success': 'text-success',
            'warning': 'text-warning',
            'info': 'text-base-content/70'
        }[event.severity] || 'text-base-content/70';
        
        const entry = document.createElement('div');
        entry.className = severityClass;
        entry.textContent = `${time} ${stepLabel} ${event.message || ""}`;
        eventLog.appendChild(entry);
    });
    
    if (logSection) logSection.scrollTop = logSection.scrollHeight;
    console.log(`[update] eventLog: Rendered ${job.events.length} events`);
}

function updateMetadata(job) {
    console.log(`[update] metadata: metadataContent=${!!metadataContent}`);
    if (!metadataContent) {
        console.warn(`[update] metadata skipped - missing metadataContent`);
        return;
    }
    
    const createdDate = new Date(job.created_at).toLocaleDateString();
    const completedDate = job.completed_at ? new Date(job.completed_at).toLocaleDateString() : "—";
    
    metadataContent.innerHTML = `
        <div class="grid grid-cols-2 gap-4">
            <div>
                <p class="text-sm text-base-content/60">Filename</p>
                <p class="font-mono text-sm">${job.pdf_filename}</p>
            </div>
            <div>
                <p class="text-sm text-base-content/60">Created</p>
                <p class="text-sm">${createdDate}</p>
            </div>
            <div>
                <p class="text-sm text-base-content/60">Completed</p>
                <p class="text-sm">${completedDate}</p>
            </div>
            <div>
                <p class="text-sm text-base-content/60">Status</p>
                <p class="text-sm"><span class="badge badge-sm">${job.status}</span></p>
            </div>
        </div>
    `;
    
    docTitle.textContent = job.pdf_filename;
}

function updateCitations(job) {
    if (!citationsContent || !citationCount) return;
    
    const paper = job.paper_analysis || {};
    
    // Handle both JSON string and already-parsed array
    let citations = [];
    if (paper.citations) {
        if (typeof paper.citations === 'string') {
            citations = JSON.parse(paper.citations);
        } else {
            citations = paper.citations;
        }
    }
    
    citationCount.textContent = citations.length;
    
    if (citations.length === 0) {
        citationsContent.innerHTML = "<p class='text-base-content/50'>No citations found</p>";
        return;
    }
    
    citationsContent.innerHTML = citations
        .slice(0, 10)
        .map(c => `<div class="text-sm"><strong>${c.authors}</strong> (${c.year}): ${c.title}</div>`)
        .join("");
}

function updateArtifacts(job) {
    if (!artifactsContent) return;
    
    const artifacts = job.artifacts || [];
    
    if (artifacts.length === 0) {
        artifactsContent.innerHTML = "<p class='text-base-content/50'>No artifacts</p>";
        return;
    }
    
    artifactsContent.innerHTML = artifacts
        .map(a => `<div class="text-sm"><a href="${a.path}" class="link">${a.name}</a></div>`)
        .join("");
}

function updateAspects(job) {
    if (!aspectsContent) return;
    
    const report = job.report || {};
    
    // Handle both old field name (aspects) and new (aspect_evaluations)
    let aspects = report.aspect_evaluations || report.aspects || [];
    
    if (aspects.length === 0) {
        aspectsContent.innerHTML = "<p class='text-base-content/50'>No evaluation aspects</p>";
        return;
    }
    
    aspectsContent.innerHTML = aspects
        .map(a => {
            const icon = a.status === "pass" ? "✓" : a.status === "fail" ? "✗" : "?";
            const color = a.status === "pass" ? "text-success" : a.status === "fail" ? "text-error" : "text-warning";
            return `<div class="text-sm"><span class="${color}">${icon}</span> ${a.name}</div>`;
        })
        .join("");
}

// ============================================================================
// Event Listeners
// ============================================================================

function setupEventListeners() {
    if (deleteBtn) deleteBtn.addEventListener("click", () => deleteModal?.showModal());
    if (cancelDeleteBtn) cancelDeleteBtn.addEventListener("click", () => deleteModal?.close());
    if (confirmDeleteBtn) confirmDeleteBtn.addEventListener("click", deleteJob);
    
    if (chatSendBtn) chatSendBtn.addEventListener("click", sendChat);
    if (chatInput) chatInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendChat();
        }
    });
    if (chatClearBtn) chatClearBtn.addEventListener("click", clearChat);
}

function deleteJob() {
    fetch(`/api/job/${JOB_ID}`, { method: "DELETE", credentials: "include" })
        .then(() => window.location.href = "/history")
        .catch(err => alert("Delete failed: " + err.message));
}

function sendChat() {
    const message = chatInput?.value.trim();
    if (!message) return;
    
    // TODO: Implement chat
    console.log("Chat not yet implemented");
}

function clearChat() {
    if (chatHistory) chatHistory.innerHTML = "";
}
