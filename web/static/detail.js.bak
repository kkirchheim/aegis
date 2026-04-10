/**
 * Detail Page - Shows full job report with checklist, artifacts, and execution log
 * Uses DaisyUI + Tailwind for professional styling
 */

// State
let currentJob = null;
let pollInterval = null;
let eventSource = null;
let lastStage = null;

// DOM Elements
const statusSection = document.getElementById("statusSection");
const progressSection = document.getElementById("progressSection");
const metadataSection = document.getElementById("metadataSection");
const citationsSection = document.getElementById("citationsSection");
const artifactsSection = document.getElementById("artifactsSection");
const aspectsSection = document.getElementById("aspectsSection");
const logSection = document.getElementById("logSection");
const chatSection = document.getElementById("chatSection");

const statusContent = document.getElementById("statusContent");
const progressFill = document.getElementById("progressFill");
const progressText = document.getElementById("progressText");
const metadataContent = document.getElementById("metadataContent");
const citationsContent = document.getElementById("citationsContent");
const citationCount = document.getElementById("citationCount");
const artifactsContent = document.getElementById("artifactsContent");
const aspectsContent = document.getElementById("aspectsContent");
const eventLog = document.getElementById("eventLog");

const chatHistory = document.getElementById("chatHistory");
const chatInput = document.getElementById("chatInput");
const chatSendBtn = document.getElementById("chatSendBtn");
const chatClearBtn = document.getElementById("chatClearBtn");

const docTitle = document.getElementById("docTitle");
const docMeta = document.getElementById("docMeta");

const deleteBtn = document.getElementById("deleteBtn");
const deleteModal = document.getElementById("deleteModal");
const cancelDeleteBtn = document.getElementById("cancelDeleteBtn");
const confirmDeleteBtn = document.getElementById("confirmDeleteBtn");

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener("DOMContentLoaded", () => {
    console.log(`[init] DOMContentLoaded, JOB_ID=${JOB_ID}`);
    console.log(`[init] eventLog element:`, eventLog);
    console.log(`[init] logSection element:`, logSection);
    
    if (!JOB_ID) {
        statusContent.innerHTML = "<div class='alert alert-error'>No job ID provided</div>";
        return;
    }
    
    loadJobData();
    setupEventListeners();
});

// Cleanup on page unload
window.addEventListener("beforeunload", () => {
    stopProgressPolling();
    if (eventSource) eventSource.close();
});

function setupEventListeners() {
    deleteBtn.addEventListener("click", () => {
        deleteModal.showModal();
    });
    
    cancelDeleteBtn.addEventListener("click", () => {
        deleteModal.close();
    });
    
    confirmDeleteBtn.addEventListener("click", deleteJob);
    
    // Chat listeners
    chatSendBtn.addEventListener("click", sendChatMessage);
    chatClearBtn.addEventListener("click", clearChatHistory);
    chatInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendChatMessage();
        }
    });
}

// ============================================================================
// Load Job Data
// ============================================================================

async function loadJobData() {
    try {
        const response = await fetch(`/api/job/${JOB_ID}/full`);
        
        if (!response.ok) {
            const text = await response.text();
            console.error(`HTTP ${response.status}: ${text}`);
            statusContent.innerHTML = `<div class='alert alert-error'>Error: HTTP ${response.status}</div>`;
            return;
        }
        
        const text = await response.text();
        if (!text) {
            console.error("Empty response from API");
            statusContent.innerHTML = `<div class='alert alert-error'>Empty response from API</div>`;
            return;
        }
        
        currentJob = JSON.parse(text);
        console.log(`Job ${currentJob.id}: status=${currentJob.status}, events=${currentJob.events ? currentJob.events.length : 0}`);
        if (currentJob.events && currentJob.events.length > 0) {
            console.log(`First event: ${currentJob.events[0].step} - ${currentJob.events[0].message}`);
        }
        renderPage();
        
    } catch (error) {
        console.error("Failed to load job:", error);
        statusContent.innerHTML = `<div class='alert alert-error'>Failed to load job: ${error.message}</div>`;
    }
}

// ============================================================================
// Render Page
// ============================================================================

function renderPage() {
    // Header with status indicator and paper title
    const paperTitle = currentJob.paper_analysis?.title || currentJob.pdf_filename || `Report ${currentJob.id.substring(0, 8)}`;
    const status = currentJob.report?.status || currentJob.status;
    
    let statusBadge = "";
    let statusClass = "badge-neutral";
    if (status === "success") {
        statusBadge = "✓";
        statusClass = "badge-success";
    } else if (status === "completed") {
        statusBadge = "✓";
        statusClass = "badge-info";
    } else if (status === "failed") {
        statusBadge = "✗";
        statusClass = "badge-error";
    } else if (status === "processing") {
        statusBadge = "⏳";
        statusClass = "badge-warning";
    }
    
    docTitle.innerHTML = `<span class="badge ${statusClass}">${statusBadge}</span> ${paperTitle}`;
    
    const createdDate = new Date(currentJob.created_at).toLocaleString();
    let duration = "";
    if (currentJob.completed_at) {
        const start = new Date(currentJob.created_at);
        const end = new Date(currentJob.completed_at);
        const ms = end - start;
        const seconds = Math.floor(ms / 1000);
        duration = ` • Completed in ${seconds}s`;
    }
    docMeta.textContent = `${createdDate}${duration}`;
    
    // Hide status section (now in header)
    statusSection.style.display = "none";
    
    // Metadata section (Title & Abstract)
    if (currentJob.paper_analysis && (currentJob.paper_analysis.title || currentJob.paper_analysis.abstract)) {
        metadataSection.style.display = "block";
        renderMetadata();
    }
    
    // Citations section
    if (currentJob.paper_analysis && currentJob.paper_analysis.citations && currentJob.paper_analysis.citations.length > 0) {
        citationsSection.style.display = "block";
        renderCitations();
    }
    
    // Checklist section
    if (currentJob.report && currentJob.report.aspect_evaluations && currentJob.report.aspect_evaluations.length > 0) {
        const checklistHtml = renderChecklist();
        const container = document.getElementById("checklistContainer");
        if (container) {
            container.innerHTML = checklistHtml;
        }
    }
    
    // Artifacts section
    if (currentJob.artifacts && currentJob.artifacts.length > 0) {
        artifactsSection.style.display = "block";
        renderArtifacts();
    }
    
    // Reproducibility aspects
    if (currentJob.report && currentJob.report.reproducibility_aspects) {
        aspectsSection.style.display = "block";
        renderAspects();
    }
    
    // Chat section - show for completed analyses
    if (currentJob.status === "completed" || currentJob.status === "success") {
        chatSection.style.display = "block";
        loadChatHistory();
    }
    
    // Progress section - show if processing OR if we have events
    if (currentJob.status === "processing") {
        console.log("Status is processing, showing live log section");
        progressSection.style.display = "block";
        logSection.style.display = "block";  // Show log section for live updates
        
        // Set progress bar from API response (0.0-1.0 converted to 0-100)
        const progressPercentage = Math.round((currentJob.progress || 0) * 100);
        progressFill.value = progressPercentage;
        progressText.textContent = `${progressPercentage}%`;
        
        // First, render historical events if any exist
        if (currentJob.events && currentJob.events.length > 0) {
            renderProgressHistory();
        } else {
            // No historical events, show empty state
            eventLog.innerHTML = "";
        }
        
        // Then connect to SSE for live updates (new events will be appended)
        setupSSEConnection();
    } else if (currentJob.events && currentJob.events.length > 0) {
        // Show progress section with historical events for completed jobs
        console.log("Status is not processing but has events, showing historical log");
        console.log("progressSection before:", progressSection.style.display);
        console.log("logSection before:", logSection.style.display);
        
        progressSection.style.display = "block";
        logSection.style.display = "block";  // Show log section
        
        console.log("progressSection after:", progressSection.style.display);
        console.log("logSection after:", logSection.style.display);
        
        renderProgressHistory();
        
        // For completed jobs, mark all stages as complete
        if (currentJob.status === "completed" || currentJob.status === "success") {
            const stage1Icon = document.getElementById("stage1Icon");
            const stage2Icon = document.getElementById("stage2Icon");
            const stage3Icon = document.getElementById("stage3Icon");
            
            stage1Icon.textContent = "✓";
            stage1Icon.style.color = "#22c55e";
            stage1Icon.className = "text-2xl mb-1";
            
            stage2Icon.textContent = "✓";
            stage2Icon.style.color = "#22c55e";
            stage2Icon.className = "text-2xl mb-1";
            
            stage3Icon.textContent = "✓";
            stage3Icon.style.color = "#22c55e";
            stage3Icon.className = "text-2xl mb-1";
            
            progressFill.value = 100;
            progressText.textContent = "100%";
        }
    }
}

// ============================================================================
// Render Status
// ============================================================================

function renderStatus() {
    const report = currentJob.report || {};
    const status = report.status || currentJob.status;
    
    let html = "";
    
    // Status badge (minimal)
    let badgeClass = "badge-neutral";
    let statusText = status || "Unknown";
    
    if (status === "success") {
        badgeClass = "badge-success";
        statusText = "✓ Passed";
    } else if (status === "completed") {
        badgeClass = "badge-info";
        statusText = "✓ Completed";
    } else if (status === "failed") {
        badgeClass = "badge-error";
        statusText = "✗ Failed";
    } else if (status === "processing") {
        badgeClass = "badge-warning";
        statusText = "⏳ Processing";
    }
    
    html += `<div class="badge ${badgeClass} badge-lg gap-2 mb-4">${statusText}</div>`;
    
    // Score
    if (report.reproducibility_score !== undefined) {
        const percentage = Math.round(report.reproducibility_score * 100);
        html += `
            <div class="mt-3">
                <div class="flex justify-between mb-2">
                    <span class="text-xs opacity-70">Score</span>
                    <span class="text-xs font-semibold">${percentage}%</span>
                </div>
                <progress class="progress progress-sm w-full" value="${percentage}" max="100"></progress>
            </div>
        `;
    }
    
    // Error only (if present)
    if (currentJob.error_message) {
        html += `<div class="alert alert-error mt-3 py-2"><span class="text-xs"><strong>Error:</strong> ${escapeHtml(currentJob.error_message)}</span></div>`;
    }
    
    statusContent.innerHTML = html;
}

// ============================================================================
// Render Metadata (Title & Abstract)
// ============================================================================

function renderMetadata() {
    const paperAnalysis = currentJob.paper_analysis || {};
    const abstract = paperAnalysis.abstract || "";
    
    let html = "";
    
    if (abstract) {
        html += `<div class="prose prose-sm max-w-none"><p>${abstract}</p></div>`;
    }
    
    metadataContent.innerHTML = html || "<p class='text-base-content/60'>No abstract available</p>";
}

// ============================================================================
// Render Citations
// ============================================================================

function renderCitations() {
    const paperAnalysis = currentJob.paper_analysis || {};
    const citations = paperAnalysis.citations || [];
    
    citationCount.textContent = citations.length;
    
    let html = "";
    
    for (const citation of citations) {
        const authors = citation.authors || "Unknown";
        const year = citation.year || "n.d.";
        const title = citation.title || "Unknown title";
        const url = citation.url;
        
        let citationHtml = `
            <div class="p-3 bg-base-100 rounded-lg border border-base-300">
                <div class="font-semibold text-sm">${escapeHtml(title)}</div>
                <div class="text-sm text-base-content/70 mt-1">${escapeHtml(authors)} (${year})</div>
        `;
        
        if (url) {
            citationHtml += `<div class="mt-2"><a href="${escapeHtml(url)}" target="_blank" class="link link-primary text-xs">${escapeHtml(url)}</a></div>`;
        }
        
        citationHtml += `</div>`;
        html += citationHtml;
    }
    
    citationsContent.innerHTML = html;
}

// ============================================================================
// Render Reproducibility Checklist
// ============================================================================

function renderChecklist() {
    let html = `
        <div class="card bg-base-100 shadow-lg mb-8">
            <div class="card-body">
                <h2 class="card-title flex items-center gap-2">
                    <span>✓</span>
                    <span>Reproducibility Checklist</span>
                </h2>
    `;
    
    const evaluations = currentJob.report.aspect_evaluations || [];
    
    if (evaluations.length === 0) {
        html += "<p>No evaluations available</p>";
    } else {
        // Group by tier (5-4-6 split)
        // TIER 1 (CRITICAL - 5 aspects): Must have for reproducibility
        // TIER 2 (HIGH VALUE - 4 aspects): Strongly recommended
        // TIER 3 (NICE-TO-HAVE - 6+ aspects): Additional best practices
        const tierMap = {
            // TIER 1 (CRITICAL) - 5 aspects
            "dependencies_pinned": 1,
            // Results Reproducible (all variants)
            "results_reproducible": 1,
            "result_reproducibility": 1,
            "reproducible_results": 1,
            "execution_reproducibility": 1,
            "results_verification": 1,
            // Hyperparameters Documented (all variants)
            "hyperparameters_documented": 1,
            "hyperparameter_specification": 1,
            "parameter_documentation": 1,
            // Dataset Available (all variants)
            "dataset_available": 1,
            "dataset_availability": 1,
            "dataset_specification": 1,
            // Environment Documented (all variants)
            "environment_documented": 1,
            "environment_specification": 1,
            
            // TIER 2 (HIGH VALUE) - 4 aspects
            // Test Suite Present (all variants)
            "test_suite_present": 2,
            "test_suite_presence": 2,
            // Config File Present
            "config_file_present": 2,
            // Documentation Quality (all variants)
            "documentation_quality": 2,
            "documentation_completeness": 2,
            "execution_instructions": 2,
            // Randomness Controlled (all variants)
            "randomness_controlled": 2,
            "random_seed_control": 2,
            
            // TIER 3 (NICE-TO-HAVE) - 6+ aspects
            // License Specified
            "license_specified": 3,
            // Continuous Integration
            "continuous_integration": 3,
            // Data Versioning (all variants)
            "data_versioning": 3,
            "data_preprocessing_documentation": 3,
            // Computational Requirements
            "computational_requirements": 3,
            // Output Format Documented
            "output_format_documented": 3,
            // Python Version Compatibility
            "python_version_compatibility": 3,
            
            // EXTRA ASPECTS (not in core 15 but in database)
            "code_availability": 3,
            "code_clarity": 3,
            "code_quality_and_clarity": 3,
            "version_control": 3,
            "statistical_significance": 3,
            "hyperparameter_justification": 3,
            "methodology_clarity": 3,
            "train_test_split_specification": 3,
            "evaluation_metrics": 3,
            "result_consistency": 3
        };
        
        const tiers = { 1: [], 2: [], 3: [] };
        
        for (const eval_item of evaluations) {
            const tier = tierMap[eval_item.aspect_id] || 3;
            tiers[tier].push(eval_item);
        }
        
        // Render by tier
        const tierLabels = {
            1: { emoji: "🔴", label: "CRITICAL - Must Have", color: "error" },
            2: { emoji: "🟠", label: "HIGH VALUE - Recommended", color: "warning" },
            3: { emoji: "🟡", label: "NICE-TO-HAVE - Optional", color: "info" }
        };
        
        for (const [tier, items] of Object.entries(tiers)) {
            if (items.length === 0) continue;
            
            const tierInfo = tierLabels[tier];
            html += `
                <div class="mt-4">
                    <h3 class="text-sm font-semibold flex items-center gap-2 mb-2">
                        <span>${tierInfo.emoji}</span>
                        <span>${tierInfo.label}</span>
                    </h3>
                    <div class="space-y-1">
            `;
            
            for (const eval_item of items) {
                const status = eval_item.status || "unknown";
                const icon = getChecklistIcon(status);
                const badgeColor = status === "pass" ? "badge-success" : status === "partial" ? "badge-warning" : "badge-error";
                
                html += `
                    <div class="collapse bg-base-200 border border-base-300">
                        <input type="checkbox" class="peer" />
                        <div class="collapse-title flex items-center gap-2 py-2 px-3 pr-12 cursor-pointer peer-checked:bg-base-300">
                            <span class="text-lg flex-shrink-0">${icon}</span>
                            <span class="font-medium text-sm flex-1 truncate">${escapeHtml(eval_item.name)}</span>
                            <div class="badge ${badgeColor} badge-xs flex-shrink-0">
                                ${escapeHtml(status)}
                            </div>
                            <span class="text-lg flex-shrink-0 transition-transform peer-checked:rotate-180">▼</span>
                        </div>
                        <div class="collapse-content px-3 py-2 space-y-1 text-xs bg-base-100 hidden peer-checked:block">
                            <p><strong>Evidence:</strong> ${escapeHtml(eval_item.evidence)}</p>
                            <p><strong>Paper:</strong> ${eval_item.paper_supports ? "✓" : "✗"} | <strong>Code:</strong> ${eval_item.code_supports ? "✓" : "✗"}</p>
                            <p><strong>Conclusion:</strong> ${escapeHtml(eval_item.conclusion)}</p>
                        </div>
                    </div>
                `;
            }
            
            html += `
                    </div>
                </div>
            `;
        }
    }
    
    html += `
            </div>
        </div>
    `;
    return html;
}

function getChecklistIcon(status) {
    if (!status) return "❓";
    const lower = status.toLowerCase();
    if (lower === "pass") return "✓";
    if (lower === "partial") return "⚠";
    return "✗";
}

// ============================================================================
// Render Artifacts
// ============================================================================

function renderArtifacts() {
    let html = "";
    
    if (currentJob.artifacts.length === 0) {
        html += "<p>No artifacts found</p>";
    } else {
        html += "<div class='space-y-2'>";
        
        for (const artifact of currentJob.artifacts) {
            const emoji = getArtifactEmoji(artifact.artifact_type);
            html += `
                <div class="card bg-base-200">
                    <div class="card-body p-4">
                        <div class="flex gap-3">
                            <span class="text-2xl">${emoji}</span>
                            <div class="flex-1">
                                <a href="${escapeHtml(artifact.url)}" target="_blank" class="link link-primary font-semibold">
                                    ${escapeHtml(artifact.url)}
                                </a>
                                <p class="text-xs text-base-content/60 mt-1">${escapeHtml(artifact.artifact_type || "unknown")}</p>
                                ${artifact.description ? `<p class="text-sm mt-2 italic">${escapeHtml(artifact.description)}</p>` : ""}
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }
        
        html += "</div>";
    }
    
    artifactsContent.innerHTML = html;
}

function getArtifactEmoji(type) {
    const map = {
        "repository": "📦",
        "github": "🐙",
        "dataset": "📊",
        "paper": "📄",
        "code": "💻",
        "docker": "🐳"
    };
    return map[type?.toLowerCase()] || "🔗";
}

// ============================================================================
// Render Reproducibility Aspects
// ============================================================================

function renderAspects() {
    const aspects = currentJob.report.reproducibility_aspects;
    
    if (!aspects || !Array.isArray(aspects.aspects)) {
        aspectsContent.innerHTML = "<p>No aspects data available</p>";
        return;
    }
    
    // Group by category
    const grouped = {};
    for (const aspect of aspects.aspects) {
        const category = aspect.category || "other";
        if (!grouped[category]) grouped[category] = [];
        grouped[category].push(aspect);
    }
    
    // Render by category
    let html = "";
    
    for (const [category, items] of Object.entries(grouped)) {
        html += `
            <div class="card bg-base-200 mb-3">
                <div class="card-body p-4">
                    <h4 class="font-semibold text-primary mb-3">${categoryLabel(category)}</h4>
                    <div class="space-y-2">
        `;
        
        for (const aspect of items) {
            const statusClass = getStatusClass(aspect.status);
            const icon = getStatusIcon(aspect.status);
            
            html += `
                <div class="p-2 bg-base-100 rounded">
                    <div class="flex gap-2 items-start">
                        <span class="text-lg">${aspect.emoji || icon}</span>
                        <div class="flex-1">
                            <div class="font-semibold text-sm">${escapeHtml(aspect.name)}</div>
                            <div class="badge badge-sm mt-1">${aspect.status}</div>
                        </div>
                    </div>
                    ${aspect.value ? `<div class="text-xs text-base-content/60 mt-2">${escapeHtml(aspect.value)}</div>` : ""}
                </div>
            `;
        }
        
        html += `
                    </div>
                </div>
            </div>
        `;
    }
    
    aspectsContent.innerHTML = html;
}

function categoryLabel(cat) {
    const labels = {
        "documentation": "📝 Documentation",
        "data": "📊 Data",
        "environment": "🔧 Environment",
        "code": "💻 Code",
        "testing": "✓ Testing",
        "other": "📌 Other"
    };
    return labels[cat] || cat;
}

function getStatusClass(status) {
    if (!status) return "unknown";
    const lower = status.toLowerCase();
    if (["documented", "available", "sufficient", "present", "found", "yes"].includes(lower)) return "success";
    if (["partial", "limited"].includes(lower)) return "warning";
    return "error";
}

function getStatusIcon(status) {
    if (!status) return "❓";
    const lower = status.toLowerCase();
    if (["documented", "available", "sufficient", "present", "found", "yes"].includes(lower)) return "✓";
    if (["partial", "limited"].includes(lower)) return "⚠";
    return "✗";
}

// ============================================================================
// Render Event Log
// ============================================================================

function renderEventLog() {
    if (!currentJob.events || currentJob.events.length === 0) {
        eventLog.innerHTML = '<div class="text-base-content/50">No events recorded</div>';
        return;
    }
    
    let html = "";
    for (const event of currentJob.events) {
        const time = new Date(event.timestamp).toLocaleTimeString();
        const step = event.step ? `[${event.step}]` : "";
        const message = event.message || "";
        const colorClass = event.severity === 'error' ? 'text-error' : event.severity === 'success' ? 'text-success' : event.severity === 'warning' ? 'text-warning' : 'text-base-content/70';
        
        html += `<div class="${colorClass}">${time} ${step} ${escapeHtml(message)}</div>`;
    }
    eventLog.innerHTML = html;
}

// ============================================================================
// Server-Sent Events (Live Progress)
// ============================================================================

function setupSSEConnection() {
    // Use polling for both progress AND events
    // Much simpler and more reliable than SSE with race conditions
    startEventPolling();
}

// Track the last timestamp we fetched events from
let lastEventTimestamp = null;

function startEventPolling() {
    // Poll every 500ms for new events
    console.log(`[Polling] Starting event polling for ${JOB_ID}`);
    pollInterval = setInterval(pollForEvents, 500);
    // Also poll immediately to avoid initial delay
    pollForEvents();
}

async function pollForEvents() {
    try {
        // Build URL with 'since' parameter if we have a last timestamp
        let url = `/api/job/${JOB_ID}/events`;
        if (lastEventTimestamp) {
            url += `?since=${encodeURIComponent(lastEventTimestamp)}`;
        }
        
        const response = await fetch(url, {
            credentials: 'include'
        });
        
        if (!response.ok) {
            console.warn(`[Polling] Failed to fetch events: HTTP ${response.status}`);
            return;
        }
        
        const data = await response.json();
        
        // Update job completion status
        if (data.completed) {
            stopProgressPolling();
        }
        
        // Update progress from job status
        if (data.job_status) {
            const job = await fetch(`/api/job/${JOB_ID}/full`, { credentials: 'include' })
                .then(r => r.json());
            currentJob = job;
            
            const progressPercentage = Math.round((job.progress || 0) * 100);
            progressFill.value = progressPercentage;
            progressText.textContent = `${progressPercentage}%`;
            
            if (job.current_stage && job.current_stage !== lastStage) {
                lastStage = job.current_stage;
                updateStagesFromStage(job.current_stage);
            }
        }
        
        // Process all new events
        if (data.events && data.events.length > 0) {
            console.log(`[Polling] Received ${data.events.length} new events`);
            data.events.forEach(event => {
                handleLogEvent(event);
                // Update last timestamp to this event's timestamp
                lastEventTimestamp = event.timestamp;
            });
        }
        
    } catch (error) {
        console.error(`[Polling] Error fetching events:`, error);
    }
}

function startProgressPolling() {
    // DEPRECATED: Polling now handled by startEventPolling() which calls pollForEvents()
    // This function kept for backward compatibility but does nothing
}

function stopProgressPolling() {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}

function updateStagesFromStage(currentStage) {
    // Map backend stage names to UI stage elements
    const stageMap = {
        'paper_analysis': 'stage1',
        'code_execution': 'stage2',
        'evaluation': 'stage3'
    };
    
    const stages = ['stage1', 'stage2', 'stage3'];
    const stageKey = stageMap[currentStage];
    let currentIndex = -1;
    
    // If job is completed/failed, mark all stages as complete
    if (currentStage === 'completed' || currentStage === 'failed') {
        currentIndex = 999;
    } else {
        currentIndex = stages.indexOf(stageKey);
    }
    
    // Update the stage icons - mark all previous as complete, current as active
    stages.forEach((stage, index) => {
        const icon = document.getElementById(`${stage}Icon`);
        if (icon) {
            if (index < currentIndex) {
                icon.textContent = "✓";
                icon.style.color = "#22c55e";
                icon.className = "text-2xl mb-1";
            } else if (index === currentIndex && currentIndex !== 999) {
                icon.textContent = "▶";
                icon.style.color = "#ffa500";
                icon.className = "text-2xl mb-1 animate-pulse";
            } else if (currentIndex === 999) {
                // All complete
                icon.textContent = "✓";
                icon.style.color = "#22c55e";
                icon.className = "text-2xl mb-1";
            }
        }
    });
}

function handleLogEvent(event) {
    const { step, message, severity, stage_duration_ms } = event;
    
    console.log(`[handleLogEvent] Processing: step=${step}, message=${message}`);
    
    // Skip chat events (handled separately) and error events (logged below)
    if (step && (step.startsWith('chat_') || step === 'chat_error')) {
        console.log(`[handleLogEvent] Skipping chat event: ${step}`);
        return;
    }
    
    // Add ALL events to the execution log
    const time = new Date().toLocaleTimeString();
    const stepLabel = step ? `[${step}]` : "";
    const severityClass = severity === 'error' ? 'text-error' : severity === 'success' ? 'text-success' : severity === 'warning' ? 'text-warning' : 'text-base-content/70';
    const logEntry = `<div class="${severityClass}">${time} ${stepLabel} ${escapeHtml(message)}</div>`;
    
    console.log(`[handleLogEvent] Adding to log, current children: ${eventLog.children.length}`);
    eventLog.innerHTML += logEntry;
    console.log(`[handleLogEvent] After add, children: ${eventLog.children.length}`);
    eventLog.scrollTop = eventLog.scrollHeight;
    
    // Capture stage durations for UI update
    if (step && step.includes('stage_') && step.includes('complete')) {
        if (stage_duration_ms) {
            // Update stage time display
            if (step.includes('stage_1')) {
                const el = document.getElementById('stage1Time');
                if (el) el.textContent = `${(stage_duration_ms / 1000).toFixed(1)}s`;
            } else if (step.includes('stage_2')) {
                const el = document.getElementById('stage2Time');
                if (el) el.textContent = `${(stage_duration_ms / 1000).toFixed(1)}s`;
            } else if (step.includes('stage_3')) {
                const el = document.getElementById('stage3Time');
                if (el) el.textContent = `${(stage_duration_ms / 1000).toFixed(1)}s`;
            }
        }
    }
}

function renderProgressHistory() {
    // Show historical events for completed jobs (all events except chat)
    const events = currentJob.events || [];
    console.log(`renderProgressHistory called with ${events.length} events`);
    
    let html = "";
    
    for (const event of events) {
        // Skip chat-related events
        if (event.step && (event.step.startsWith('chat_') || event.step === 'chat_error')) {
            continue;
        }
        
        // Include ALL other events (stage, error, progress, etc.)
        const time = new Date(event.timestamp).toLocaleTimeString();
        const stepLabel = event.step ? `[${event.step}]` : "";
        const severityClass = event.severity === 'error' ? 'text-error' : event.severity === 'success' ? 'text-success' : event.severity === 'warning' ? 'text-warning' : 'text-base-content/70';
        const logEntry = `<div class="${severityClass}">${time} ${stepLabel} ${escapeHtml(event.message)}</div>`;
        html += logEntry;
    }
    
    console.log(`renderProgressHistory generated ${html.length} chars of HTML`);
    console.log(`eventLog element:`, eventLog);
    
    if (eventLog) {
        eventLog.innerHTML = html;
        console.log(`Set eventLog.innerHTML, now has ${eventLog.children.length} children`);
        
        // Scroll the log section into view
        if (logSection && logSection.style.display === "block") {
            logSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            console.log("Scrolled logSection into view");
        }
    } else {
        console.error("eventLog element not found!");
    }
    
    progressFill.value = 100;
    progressText.textContent = "100%";
}

// ============================================================================
// Delete Job
// ============================================================================

async function deleteJob() {
    try {
        const response = await fetch(`/job/${JOB_ID}`, {
            method: "DELETE"
        });
        
        if (!response.ok) {
            const error = await response.json();
            alert(`Delete failed: ${error.error}`);
            return;
        }
        
        // Redirect to home
        window.location.href = "/";
        
    } catch (error) {
        console.error("Failed to delete job:", error);
        alert(`Delete error: ${error.message}`);
    }
}

// ============================================================================
// Utilities
// ============================================================================

function escapeHtml(text) {
    if (!text) return "";
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// ============================================================================
// Chat Functions
// ============================================================================

async function loadChatHistory() {
    try {
        const response = await fetch(`/api/job/${JOB_ID}/chat/history`);
        if (!response.ok) return;
        
        const messages = await response.json();
        chatHistory.innerHTML = '';
        
        messages.forEach(msg => {
            addChatMessageToUI(msg.role, msg.content);
        });
    } catch (error) {
        console.error("Failed to load chat history:", error);
    }
}

async function clearChatHistory() {
    if (!confirm("Clear all chat messages? This cannot be undone.")) {
        return;
    }
    
    try {
        const response = await fetch(`/api/job/${JOB_ID}/chat/history`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }
        
        // Clear UI
        chatHistory.innerHTML = `
            <div class="text-center text-base-content/60 text-sm">
                Chat history cleared. Ask a new question...
            </div>
        `;
    } catch (error) {
        console.error("Failed to clear chat history:", error);
        alert(`Error: ${error.message}`);
    }
}

async function sendChatMessage() {
    const message = chatInput.value.trim();
    if (!message) return;
    
    // Add user message to display immediately
    addChatMessageToUI('user', message);
    chatInput.value = '';
    chatSendBtn.disabled = true;
    
    try {
        // Send message to backend
        const response = await fetch(`/api/job/${JOB_ID}/chat`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message})
        });
        
        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }
        
        // Stream response via SSE
        streamChatResponse();
        
    } catch (error) {
        console.error("Chat error:", error);
        addChatMessageToUI('error', `Error: ${error.message}`);
    } finally {
        chatSendBtn.disabled = false;
    }
}

function streamChatResponse() {
    // Listen for chat response events from server
    const eventSource = new EventSource(`/events/${JOB_ID}`, { withCredentials: true });
    let assistantMessage = '';
    let messageDiv = null;
    
    eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            
            if (data.step === 'chat_response') {
                // Streaming content
                assistantMessage += data.content;
                
                // Create or update message div
                if (!messageDiv) {
                    messageDiv = document.createElement('div');
                    messageDiv.className = 'mb-3';
                    chatHistory.appendChild(messageDiv);
                }
                
                // Update message with latest content (trim whitespace, preserve internal newlines)
                messageDiv.innerHTML = `<div class="flex gap-2"><div class="font-semibold text-sm text-primary">Assistant:</div><div class="text-sm flex-1 bg-base-200 rounded" style="padding: 4px 8px !important; white-space: pre-wrap;">${escapeHtml(assistantMessage.trim())}</div></div>`;
                
                // Auto-scroll to bottom
                chatHistory.scrollTop = chatHistory.scrollHeight;
                
            } else if (data.step === 'chat_complete') {
                // Response finished
                eventSource.close();
            } else if (data.step === 'chat_error') {
                // Error occurred
                addChatMessageToUI('error', data.message);
                eventSource.close();
            }
        } catch (e) {
            console.error("Error parsing SSE message:", e);
        }
    };
    
    eventSource.onerror = () => {
        console.error("SSE connection error");
        eventSource.close();
    };
}

function addChatMessageToUI(role, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'mb-3';
    
    if (role === 'user') {
        messageDiv.innerHTML = `<div class="flex gap-2 justify-end"><div class="text-sm flex-1 max-w-md bg-primary text-primary-content rounded" style="padding: 4px 8px !important; white-space: pre-wrap;">${escapeHtml(content.trim())}</div><div class="font-semibold text-sm">You:</div></div>`;
    } else if (role === 'error') {
        messageDiv.innerHTML = `
            <div class="alert alert-error text-sm py-2">
                ${escapeHtml(content)}
            </div>
        `;
    } else {
        messageDiv.innerHTML = `<div class="flex gap-2"><div class="font-semibold text-sm text-primary">Assistant:</div><div class="text-sm flex-1 bg-base-200 rounded" style="padding: 4px 8px !important; white-space: pre-wrap;">${escapeHtml(content.trim())}</div></div>`;
    }
    
    chatHistory.appendChild(messageDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

// Theme toggle
function toggleTheme() {
    const html = document.documentElement;
    const isDark = html.getAttribute('data-theme') === 'dark';
    html.setAttribute('data-theme', isDark ? 'light' : 'dark');
    localStorage.setItem('theme', isDark ? 'light' : 'dark');
}
