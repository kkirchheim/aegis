/**
 * Detail Page - Unified Polling Approach
 * Single source of truth: calls /api/job/<id>/full every 200ms
 * Updates all UI components from complete job state
 */

// Module-level JOB_ID initialized from window global
let JOB_ID = null;

let currentJob = null;
let pollInterval = null;
let lastStage = null;
let lastEventCount = 0;  // Track processed events to avoid duplicates

// Chat polling variables
let chatPollingInterval = null;
let lastChatMessageCount = 0;  // Track processed chat messages to avoid duplicates

// DOM Elements - Sections
const statusSection = document.getElementById("statusSection");
const progressSection = document.getElementById("progressSection");
const metadataSection = document.getElementById("metadataSection");
const citationsSection = document.getElementById("citationsSection");
const artifactsSection = document.getElementById("artifactsSection");
const aspectsSection = document.getElementById("aspectsSection");
const logSection = document.getElementById("logSection");
const chatSection = document.getElementById("chatSection");

// DOM Elements - Content Areas
const statusContent = document.getElementById("statusContent");
const progressFill = document.getElementById("progressFill");
const progressText = document.getElementById("progressText");
const eventLog = document.getElementById("eventLog");
const metadataContent = document.getElementById("metadataContent");
const citationsContent = document.getElementById("citationsContent");
const citationCount = document.getElementById("citationCount");
const artifactsContent = document.getElementById("artifactsContent");
const aspectsContent = document.getElementById("aspectsContent");

// DOM Elements - Controls
const deleteBtn = document.getElementById("deleteBtn");
const deleteModal = document.getElementById("deleteModal");
const cancelDeleteBtn = document.getElementById("cancelDeleteBtn");
const confirmDeleteBtn = document.getElementById("confirmDeleteBtn");

// DOM Elements - Header
const docTitle = document.getElementById("docTitle");
const docMeta = document.getElementById("docMeta");

// DOM Elements - Chat
const chatHistory = document.getElementById("chatHistory");
const chatInput = document.getElementById("chatInput");
const chatSendBtn = document.getElementById("chatSendBtn");
const chatClearBtn = document.getElementById("chatClearBtn");

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener("DOMContentLoaded", () => {
    // Initialize JOB_ID from window global (set by HTML template BEFORE detail.js loads)
    JOB_ID = window.JOB_ID;
    
    console.log(`[unified-polling] Starting for JOB_ID=${JOB_ID}`);
    console.log('[chat-polling] Page loaded, jobId:', JOB_ID);
    console.log('[chat-polling] JOB_ID type:', typeof JOB_ID, 'value is truthy:', !!JOB_ID);
    console.log('[chat-polling] window.JOB_ID:', window.JOB_ID);
    
    if (!JOB_ID) {
        console.error('[chat-polling] JOB_ID not set or empty! window.JOB_ID=', window.JOB_ID);
        statusContent.innerHTML = "<div class='alert alert-error'>No job ID provided</div>";
        return;
    }
    
    setupEventListeners();
    startUnifiedPolling();  // Poll every 200ms
});

window.addEventListener("beforeunload", () => {
    stopPolling();
    stopChatPolling();
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

// ============================================================================
// Independent Chat Polling (500ms) - Separate from Job Polling
// ============================================================================

function startChatPolling() {
    if (!JOB_ID) {
        console.error('[chat-polling] jobId not set, cannot start polling. JOB_ID=', JOB_ID);
        return;
    }
    
    console.log('[chat-polling] Starting polling for jobId:', JOB_ID);
    
    // Clear existing interval if any
    if (chatPollingInterval) {
        clearInterval(chatPollingInterval);
    }
    
    // Poll every 500ms (faster than job polling since it's just fetching history)
    chatPollingInterval = setInterval(async () => {
        if (!JOB_ID) {
            console.warn('[chat-polling] jobId became undefined, stopping polling');
            stopChatPolling();
            return;
        }
        
        const chatSection = document.getElementById('chatSection');
        // Only poll if chat section is visible
        if (!chatSection || chatSection.style.display === 'none') {
            return;
        }
        
        try {
            const url = `/api/job/${JOB_ID}/chat/history`;
            console.log('[chat-polling] Fetching from:', url);
            
            const response = await fetch(url, {
                credentials: 'include'
            });
            
            console.log('[chat-polling] Response status:', response.status);
            
            if (!response.ok) {
                console.warn('[chat-polling] Response not ok. Status:', response.status);
                return;
            }
            
            const data = await response.json();
            const messages = data.messages || [];  // Extract messages array from envelope format
            console.log('[chat-polling] Received', messages.length, 'messages');
            updateChatMessages(messages);
        } catch (error) {
            console.error('[chat-polling] Fetch failed. JobId:', JOB_ID, 'Error:', error);
        }
    }, 500); // Poll every 500ms
}

function stopChatPolling() {
    if (chatPollingInterval) {
        clearInterval(chatPollingInterval);
        chatPollingInterval = null;
        console.log(`[chat-polling] Stopped`);
    }
}

function updateChatMessages(messages) {
    const chatMessages = document.getElementById('chatHistory');
    if (!chatMessages) {
        console.warn('[chat-polling] chatHistory element not found');
        return;
    }
    
    const currentMessages = chatMessages.querySelectorAll('.chat-message');
    
    // Only update if new messages arrived
    if (messages.length > currentMessages.length) {
        console.log(`[chat-polling] Found ${messages.length - currentMessages.length} new messages`);
        const newMessages = messages.slice(currentMessages.length);
        newMessages.forEach(msg => {
            addChatMessage(msg.role, msg.content);
        });
        lastChatMessageCount = messages.length;
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
        
        // Show/hide sections based on job status and data
        showRelevantSections(job);
        
        // Update all UI components - each in its own try-catch so failures don't stop others
        try { updateProgressBar(job); } catch (e) { console.error(`[update] progressBar failed:`, e); }
        try { updateStages(job); } catch (e) { console.error(`[update] stages failed:`, e); }
        try { updateStatus(job); } catch (e) { console.error(`[update] status failed:`, e); }
        try { updateEventLog(job); } catch (e) { console.error(`[update] eventLog failed:`, e); }
        try { updateMetadata(job); } catch (e) { console.error(`[update] metadata failed:`, e); }
        try { updateCitations(job); } catch (e) { console.error(`[update] citations failed:`, e); }
        try { updateArtifacts(job); } catch (e) { console.error(`[update] artifacts failed:`, e); }
        try { updateAspects(job); } catch (e) { console.error(`[update] aspects failed:`, e); }
        try { updateAssessment(job); } catch (e) { console.error(`[update] assessment failed:`, e); }
        
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

function showRelevantSections(job) {
    console.log(`[sections] Showing relevant sections for status=${job.status}`);
    
    // Always show progress section - shows 100% when completed
    if (progressSection) {
        progressSection.style.display = "block";
        console.log(`[sections] progressSection: shown (status=${job.status})`);
    }
    
    // Show analysis sections if we have data
    if (metadataSection) {
        const show = !!job.paper_analysis;
        metadataSection.style.display = show ? "block" : "none";
        console.log(`[sections] metadataSection: ${show ? "shown" : "hidden"} (has data=${show})`);
    }
    
    if (citationsSection) {
        const show = job.paper_analysis && Array.isArray(job.paper_analysis.citations) && job.paper_analysis.citations.length > 0;
        citationsSection.style.display = show ? "block" : "none";
        console.log(`[sections] citationsSection: ${show ? "shown" : "hidden"} (count=${job.paper_analysis?.citations?.length || 0})`);
    }
    
    if (artifactsSection) {
        const show = Array.isArray(job.artifacts) && job.artifacts.length > 0;
        artifactsSection.style.display = show ? "block" : "none";
        console.log(`[sections] artifactsSection: ${show ? "shown" : "hidden"} (count=${job.artifacts?.length || 0})`);
    }
    
    if (aspectsSection) {
        const show = job.report && Array.isArray(job.report.aspect_evaluations) && job.report.aspect_evaluations.length > 0;
        aspectsSection.style.display = show ? "block" : "none";
        console.log(`[sections] aspectsSection: ${show ? "shown" : "hidden"} (count=${job.report?.aspect_evaluations?.length || 0})`);
    }
    
    // Show assessment section if we have evaluation results
    const assessmentSection = document.getElementById('assessmentSection');
    if (assessmentSection) {
        const show = job.evaluation_results && Object.keys(job.evaluation_results).length > 0;
        assessmentSection.style.display = show ? "block" : "none";
        console.log(`[sections] assessmentSection: ${show ? "shown" : "hidden"} (count=${Object.keys(job.evaluation_results || {}).length})`);
    }
    
    // Show log if we have events
    if (logSection) {
        const show = Array.isArray(job.events) && job.events.length > 0;
        logSection.style.display = show ? "block" : "none";
        console.log(`[sections] logSection: ${show ? "shown" : "hidden"} (count=${job.events?.length || 0})`);
    }
    
    // Show chat for completed jobs
    if (chatSection) {
        const show = job.status === "completed";
        chatSection.style.display = show ? "block" : "none";
        console.log(`[sections] chatSection: ${show ? "shown" : "hidden"} (status=${job.status})`);
        
        // Load chat history and start polling when chat section is shown
        if (show) {
            console.log('[chat-polling] Showing chat section, jobId:', JOB_ID);
            loadChatHistory();
            console.log('[chat-polling] Chat history loaded, starting polling...');
            startChatPolling();  // Start independent chat polling
        } else {
            console.log('[chat-polling] Hiding chat section, stopping polling...');
            stopChatPolling();  // Stop polling when chat is hidden
        }
    }
}

function updateProgressBar(job) {
    console.log(`[update] progressBar: progressFill=${!!progressFill}, progressText=${!!progressText}, progress=${job.progress}`);
    if (!progressFill || !progressText) {
        console.warn(`[update] progressBar skipped - missing DOM elements`);
        return;
    }
    
    const percent = Math.round((job.progress || 0) * 100);
    progressFill.value = percent;
    
    // Show stage info along with percentage
    const stage = job.current_stage || "pending";
    const stageLabel = {
        'paper_analysis': 'Analyzing Paper',
        'code_execution': 'Executing Code',
        'evaluation': 'Evaluating Results',
        'completed': 'Completed',
        'failed': 'Failed'
    }[stage] || stage;
    
    progressText.textContent = `${stageLabel} (${percent}%)`;
    console.log(`[update] progressBar: Set to ${percent}% - ${stageLabel}`);
}

function updateStages(job) {
    const stage = job.current_stage || "pending";
    const events = job.events || [];
    
    const stageMap = {
        'paper_analysis': 'stage1',
        'code_execution': 'stage2',
        'evaluation': 'stage3'
    };
    
    const stageEventMap = {
        'stage1': 'paper_analysis',
        'stage2': 'code_execution',
        'stage3': 'evaluation'
    };
    
    // Find timestamps for each stage's start event
    const stageTimestamps = {};
    events.forEach(event => {
        if (event.step && Object.values(stageEventMap).includes(event.step)) {
            const stageId = Object.keys(stageEventMap).find(k => stageEventMap[k] === event.step);
            if (stageId && !stageTimestamps[stageId]) {
                stageTimestamps[stageId] = event.timestamp;
            }
        }
    });
    
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
        const timeEl = document.getElementById(`${s}Time`);
        
        if (icon) {
            if (i < currentIndex) {
                icon.textContent = "✓";
                icon.style.color = "#22c55e";
                icon.className = "text-2xl mb-1";
            } else if (i === currentIndex && currentIndex !== 999) {
                icon.textContent = "▶";
                icon.style.color = "#ffa500";
                icon.className = "text-2xl mb-1 animate-pulse";
            } else if (currentIndex === 999) {
                icon.textContent = "✓";
                icon.style.color = "#22c55e";
                icon.className = "text-2xl mb-1";
            } else {
                icon.textContent = "○";
                icon.style.color = "rgba(0,0,0,0.3)";
                icon.className = "text-2xl mb-1";
            }
        }
        
        // Update timestamp display
        if (timeEl && stageTimestamps[s]) {
            const time = new Date(stageTimestamps[s]).toLocaleTimeString();
            timeEl.textContent = time;
        } else if (timeEl) {
            timeEl.textContent = "";
        }
    });
}

function updateStatus(job) {
    // Update status badge in the progress section header
    const statusBadge = document.getElementById("statusBadge");
    
    if (!statusBadge) {
        console.warn(`[update] status: missing statusBadge element`);
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
    
    statusBadge.className = `badge ${statusClass}`;
    statusBadge.textContent = statusText;
    
    console.log(`[update] status: Updated statusBadge to "${statusText}" with class ${statusClass}`);
}

function updateEventLog(job) {
    console.log(`[update] eventLog: eventLog=${!!eventLog}, events=${job.events?.length || 0}, lastEventCount=${lastEventCount}`);
    if (!eventLog) {
        console.warn(`[update] eventLog skipped - missing eventLog element`);
        return;
    }
    
    // Initialize event log on first call
    if (lastEventCount === 0 && (!job.events || job.events.length === 0)) {
        eventLog.innerHTML = "<div class='text-base-content/50'>No events yet</div>";
        return;
    }
    
    // Check if this is the first population or if we have new events
    const currentEventCount = job.events ? job.events.length : 0;
    
    // If first time with events, clear the "No events yet" message
    if (lastEventCount === 0 && currentEventCount > 0) {
        eventLog.innerHTML = "";
    }
    
    // Only append new events (events after lastEventCount)
    if (currentEventCount > lastEventCount && job.events) {
        const newEventsCount = currentEventCount - lastEventCount;
        job.events.slice(lastEventCount).forEach(event => {
            // Handle chat events separately
            if (event.step && (event.step.startsWith('chat_') || event.step === 'chat_error')) {
                if (event.step === 'chat_response' || event.step === 'chat_complete') {
                    // Add assistant response to chat
                    if (event.message) {
                        addChatMessage('assistant', event.message);
                    }
                } else if (event.step === 'chat_error') {
                    // Add error message to chat
                    addChatMessage('assistant', `Error: ${event.message || 'Failed to process message'}`);
                }
                return;  // Don't add chat events to event log
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
        
        lastEventCount = currentEventCount;
        console.log(`[update] eventLog: Appended ${newEventsCount} new events`);
    }
    
    // Auto-scroll to bottom only if user isn't scrolled up reading history
    const logContainer = logSection?.querySelector('.max-h-96');
    if (logContainer) {
        const isAtBottom = logContainer.scrollHeight - logContainer.scrollTop <= logContainer.clientHeight + 5;
        if (isAtBottom) {
            logContainer.scrollTop = logContainer.scrollHeight;
        }
    }
}

function updateMetadata(job) {
    console.log(`[update] metadata: metadataContent=${!!metadataContent}`);
    if (!metadataContent) {
        console.warn(`[update] metadata skipped - missing metadataContent`);
        return;
    }
    
    const paper = job.paper_analysis || {};
    const abstract = paper.abstract || "No abstract available";
    
    metadataContent.innerHTML = `
        <div class="space-y-4">
            <div>
                <p class="text-sm text-base-content/60 font-semibold mb-2">Abstract</p>
                <p class="text-sm leading-relaxed">${abstract}</p>
            </div>
        </div>
    `;
    
    // Update page header with paper title if available
    const title = paper.title || job.pdf_filename;
    docTitle.textContent = title;
    console.log(`[update] metadata: Set page title to "${title}"`);
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
        .map(c => {
            const authors = c.authors ? `<strong>${c.authors}</strong>` : "(Unknown authors)";
            const year = c.year ? ` (${c.year})` : "";
            const title = c.title ? `${c.title}` : "";
            const url = c.url ? ` <a href="${c.url}" target="_blank" class="link link-primary text-xs">🔗</a>` : "";
            return `<div class="text-sm mb-2">${authors}${year}: ${title}${url}</div>`;
        })
        .join("");
}

function updateArtifacts(job) {
    if (!artifactsContent) return;
    
    const artifacts = job.artifacts || [];
    
    if (artifacts.length === 0) {
        artifactsContent.innerHTML = "<p class='text-base-content/50'>No artifacts found</p>";
        return;
    }
    
    artifactsContent.innerHTML = artifacts
        .map(a => {
            const type = a.artifact_type ? `<span class="badge badge-sm badge-outline mr-2">${a.artifact_type}</span>` : "";
            const description = a.description ? `<p class="text-xs text-base-content/70 mt-1">${a.description}</p>` : "";
            const link = a.url ? `<a href="${a.url}" target="_blank" class="link link-primary text-sm">View Artifact →</a>` : "";
            return `<div class="mb-4 p-3 bg-base-200 rounded-lg">${type}<div class="text-sm font-semibold">${a.description || a.url || "Artifact"}</div>${description}${link}</div>`;
        })
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
        .map((a, index) => {
            const statusIcon = a.status === "pass" ? "✓" : a.status === "fail" ? "✗" : "?";
            const statusColor = a.status === "pass" ? "text-success" : a.status === "fail" ? "text-error" : "text-warning";
            const statusLabel = a.status === "pass" ? "Pass" : a.status === "fail" ? "Fail" : "Unknown";
            
            const conclusion = a.conclusion ? `<p class="mt-2"><strong>Conclusion:</strong> ${a.conclusion}</p>` : "";
            const evidence = a.evidence ? `<p class="mt-2"><strong>Evidence:</strong> ${a.evidence}</p>` : "";
            const codeSupports = a.code_supports !== undefined ? `<p class="mt-2"><strong>Code Supports:</strong> ${a.code_supports ? "Yes ✓" : "No ✗"}</p>` : "";
            const paperSupports = a.paper_supports !== undefined ? `<p class="mt-2"><strong>Paper Supports:</strong> ${a.paper_supports ? "Yes ✓" : "No ✗"}</p>` : "";
            
            const hasDetails = conclusion || evidence || codeSupports || paperSupports;
            
            return `
                <div class="collapse collapse-arrow bg-base-200 mb-2">
                    <input type="checkbox" />
                    <div class="collapse-title font-semibold flex items-center gap-2">
                        <span class="${statusColor} text-lg">${statusIcon}</span>
                        <span>${a.name}</span>
                        <span class="text-xs badge badge-${a.status === "pass" ? "success" : a.status === "fail" ? "error" : "warning"}">${statusLabel}</span>
                    </div>
                    <div class="collapse-content text-sm">
                        ${hasDetails ? `${conclusion}${evidence}${codeSupports}${paperSupports}` : '<p class="text-base-content/50">No additional details available</p>'}
                    </div>
                </div>
            `;
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

// ============================================================================
// Chat Helper Functions
// ============================================================================

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function addChatMessage(role, content) {
    if (!chatHistory) {
        console.error('Chat history element not found');
        return;
    }
    
    // Clear initial placeholder if this is first message
    if (chatHistory.innerHTML.trim().includes("Ask questions about the paper's reproducibility")) {
        chatHistory.innerHTML = '';
    }
    
    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-message ${role}-message`;
    msgDiv.innerHTML = `<div class="message-content">${escapeHtml(content)}</div>`;
    
    chatHistory.appendChild(msgDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

async function loadChatHistory() {
    if (!JOB_ID) {
        console.error('[chat-polling] loadChatHistory: jobId not set');
        return;
    }
    
    if (!chatHistory) {
        console.error('[chat-polling] Chat history element not found');
        return;
    }
    
    try {
        const url = `/api/job/${JOB_ID}/chat/history`;
        console.log('[chat-polling] Loading initial chat history from:', url);
        
        const response = await fetch(url, {
            credentials: 'include'
        });
        
        console.log('[chat-polling] Initial load response status:', response.status);
        
        if (!response.ok) {
            console.error('[chat-polling] Failed to load chat history. Status:', response.status);
            return;
        }
        
        const data = await response.json();
        const messages = data.messages || [];  // Handle both array and {messages: [...]} response
        console.log('[chat-polling] Loaded', messages.length, 'historical messages');
        
        // Clear existing messages
        chatHistory.innerHTML = '';
        
        // Add each historical message
        if (Array.isArray(messages)) {
            messages.forEach(msg => {
                addChatMessage(msg.role, msg.content);
            });
        } else {
            console.error('[chat-polling] Messages is not an array:', messages);
        }
        
        // Track how many messages we've rendered so polling knows what's new
        lastChatMessageCount = messages.length;
        console.log('[chat-polling] Synced lastChatMessageCount to', lastChatMessageCount);
        
        // Scroll to bottom
        chatHistory.scrollTop = chatHistory.scrollHeight;
    } catch (error) {
        console.error('[chat-polling] Error loading chat history. JobId:', JOB_ID, 'Error:', error);
    }
}

async function sendChat() {
    const message = chatInput?.value.trim();
    if (!message) {
        alert('Message cannot be empty');
        return;
    }
    
    if (!JOB_ID) {
        console.error('Job ID not set for chat');
        return;
    }
    
    if (!chatHistory) {
        console.error('Chat history element not found');
        return;
    }
    
    try {
        // Add user message to display immediately
        addChatMessage('user', message);
        
        // Clear input
        chatInput.value = '';
        
        // Send to API
        const response = await fetch(`/api/job/${JOB_ID}/chat`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            credentials: 'include',
            body: JSON.stringify({message: message})
        });
        
        if (!response.ok) {
            const error = await response.json();
            addChatMessage('assistant', `Error: ${error.error || 'Failed to send message'}`);
            return;
        }
        
        // Backend returns success, but don't add message here.
        // The polling loop will fetch the response from the database
        // within 500ms. This avoids duplicate messages and race conditions.
        console.log('[chat] Message sent, waiting for polling to fetch response from DB');
        
    } catch (error) {
        console.error('Chat error:', error);
        addChatMessage('assistant', 'Failed to send message: ' + error.message);
    }
}

async function clearChat() {
    if (!confirm('Clear all chat history?')) return;
    
    if (!JOB_ID) {
        console.error('Job ID not set for chat');
        return;
    }
    
    try {
        const response = await fetch(`/api/job/${JOB_ID}/chat/history`, {
            method: 'DELETE',
            credentials: 'include'
        });
        
        if (response.ok) {
            if (chatHistory) {
                chatHistory.innerHTML = '<div class="text-center text-base-content/60 text-sm">Ask questions about the paper\'s reproducibility...</div>';
            }
            console.log('Chat history cleared');
        } else {
            alert('Failed to clear chat history');
        }
    } catch (error) {
        console.error('Error clearing chat:', error);
        alert('Failed to clear chat history');
    }
}

// ============================================================================
// Assessment/Evaluation Results Rendering
// ============================================================================

function updateAssessment(job) {
    const assessmentSection = document.getElementById('assessmentSection');
    if (!assessmentSection) {
        console.warn('[update] assessmentSection not found');
        return;
    }
    
    // Check if we have evaluation_results
    if (!job.evaluation_results || Object.keys(job.evaluation_results).length === 0) {
        assessmentSection.style.display = 'none';
        return;
    }
    
    // Show assessment section
    assessmentSection.style.display = 'block';
    
    // Render expandable aspect list
    renderAspectsList(job.evaluation_results);
}

function renderAspectsList(evaluationResults) {
    const list = document.getElementById('assessment-list');
    if (!list) {
        console.warn('[assessment] assessment-list not found');
        return;
    }
    
    const aspects = Object.entries(evaluationResults).map(([aspectId, result]) => {
        const status = result.status || 'UNKNOWN';
        const statusIcon = {
            'PASS': '✅',
            'FAIL': '❌',
            'UNCLEAR': '⚠️'
        }[status] || '❓';
        
        const statusBadgeClass = {
            'PASS': 'badge-success',
            'FAIL': 'badge-error',
            'UNCLEAR': 'badge-warning'
        }[status] || 'badge-secondary';
        
        const description = result.aspect_description ? `<p class="text-xs text-base-content/60 mb-2">${escapeHtml(result.aspect_description)}</p>` : '';
        
        return `
            <div class="collapse collapse-arrow border border-base-300 bg-base-100">
                <input type="checkbox" />
                <div class="collapse-title flex items-center gap-3 font-semibold cursor-pointer py-3">
                    <span class="text-lg">${statusIcon}</span>
                    <span class="flex-1">${escapeHtml(result.aspect_name || 'Aspect')}</span>
                    <span class="badge ${statusBadgeClass} text-xs">${escapeHtml(status)}</span>
                </div>
                <div class="collapse-content">
                    ${description}
                    <p class="text-sm leading-relaxed">${escapeHtml(result.reasoning || 'No reasoning provided')}</p>
                </div>
            </div>
        `;
    }).join('');
    
    list.innerHTML = aspects;
}

function escapeHtml(text) {
    if (!text) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}
