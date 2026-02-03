/**
 * Detail Page - Shows full job report with events, artifacts, and aspects
 * 
 * Extensible architecture:
 * - Reproducibility aspects are rendered dynamically from report data
 * - New aspects can be added to report without UI code changes
 * - Event log supports any step type
 */

// State
let currentJob = null;

// DOM Elements
const statusSection = document.getElementById("statusSection");
const artifactsSection = document.getElementById("artifactsSection");
const aspectsSection = document.getElementById("aspectsSection");
const logSection = document.getElementById("logSection");

const statusContent = document.getElementById("statusContent");
const artifactsContent = document.getElementById("artifactsContent");
const aspectsContent = document.getElementById("aspectsContent");
const eventLog = document.getElementById("eventLog");

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
    if (!JOB_ID) {
        statusContent.innerHTML = "<p class='error'>No job ID provided</p>";
        return;
    }
    
    loadJobData();
    setupEventListeners();
});

function setupEventListeners() {
    deleteBtn.addEventListener("click", () => {
        deleteModal.style.display = "flex";
    });
    
    cancelDeleteBtn.addEventListener("click", () => {
        deleteModal.style.display = "none";
    });
    
    confirmDeleteBtn.addEventListener("click", deleteJob);
    
    // Close modal on outside click
    deleteModal.addEventListener("click", (e) => {
        if (e.target === deleteModal) {
            deleteModal.style.display = "none";
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
            const error = await response.json();
            statusContent.innerHTML = `<p class="error">Error: ${error.error}</p>`;
            return;
        }
        
        currentJob = await response.json();
        renderPage();
        
    } catch (error) {
        console.error("Failed to load job:", error);
        statusContent.innerHTML = `<p class="error">Failed to load job: ${error.message}</p>`;
    }
}

// ============================================================================
// Render Page
// ============================================================================

function renderPage() {
    // Header
    docTitle.textContent = currentJob.pdf_filename || `Report ${currentJob.id.substring(0, 8)}`;
    const createdDate = new Date(currentJob.created_at).toLocaleString();
    let duration = "";
    if (currentJob.completed_at) {
        const start = new Date(currentJob.created_at);
        const end = new Date(currentJob.completed_at);
        const ms = end - start;
        const seconds = Math.floor(ms / 1000);
        duration = ` • Completed in ${seconds}s`;
    }
    docMeta.textContent = `Created: ${createdDate}${duration}`;
    
    // Status section
    renderStatus();
    
    // Artifacts section
    if (currentJob.artifacts && currentJob.artifacts.length > 0) {
        artifactsSection.style.display = "block";
        renderArtifacts();
    }
    
    // Reproducibility evaluations (with evidence from all sources)
    if (currentJob.report && currentJob.report.aspect_evaluations && currentJob.report.aspect_evaluations.length > 0) {
        let checklistHtml = "<div id='checklistSection' class='section' style='order: -1;'>";
        checklistHtml += "<h2>✓ Reproducibility Checklist</h2>";
        checklistHtml += renderChecklist();
        checklistHtml += "</div>";
        
        // Insert before status section
        statusSection.insertAdjacentHTML("beforebegin", checklistHtml);
    }
    
    // Reproducibility aspects (extensible)
    if (currentJob.report && currentJob.report.reproducibility_aspects) {
        aspectsSection.style.display = "block";
        renderAspects();
    }
    
    // Event log
    if (currentJob.events && currentJob.events.length > 0) {
        logSection.style.display = "block";
        renderEventLog();
    }
}

// ============================================================================
// Render Status
// ============================================================================

function renderStatus() {
    const report = currentJob.report || {};
    const status = report.status || currentJob.status;
    
    let html = "";
    
    // Status badge
    if (status === "success") {
        html += `<div class="status-badge success">✓ Reproducibility Check Passed</div>`;
    } else if (status === "completed") {
        html += `<div class="status-badge success">✓ Analysis Completed</div>`;
    } else if (status === "failed") {
        html += `<div class="status-badge error">✗ Reproducibility Check Failed</div>`;
    } else if (status === "processing") {
        html += `<div class="status-badge warning">⏳ Processing...</div>`;
    } else {
        html += `<div class="status-badge">${status || "Unknown"}</div>`;
    }
    
    // Score
    if (report.reproducibility_score !== undefined) {
        const percentage = Math.round(report.reproducibility_score * 100);
        const scoreClass = percentage >= 80 ? "success" : percentage >= 50 ? "warning" : "error";
        html += `
            <div class="score-card">
                <div class="score-label">Reproducibility Score</div>
                <div class="score-value ${scoreClass}">${percentage}%</div>
            </div>
        `;
    }
    
    // Message
    if (report.message) {
        html += `
            <div class="message-box">
                <p>${escapeHtml(report.message)}</p>
            </div>
        `;
    }
    
    // Error (if failed)
    if (currentJob.error_message) {
        html += `
            <div class="error-box">
                <p><strong>Error:</strong> ${escapeHtml(currentJob.error_message)}</p>
            </div>
        `;
    }
    
    statusContent.innerHTML = html;
}

// ============================================================================
// Render Artifacts
// ============================================================================

function renderArtifacts() {
    let html = `<div class="artifact-list">`;
    
    if (currentJob.artifacts.length === 0) {
        html += "<p>No artifacts found</p>";
    } else {
        html += `<p>${currentJob.artifacts.length} artifact(s) identified:</p>`;
        
        for (const artifact of currentJob.artifacts) {
            const emoji = getArtifactEmoji(artifact.artifact_type);
            html += `
                <div class="artifact-item">
                    <span class="artifact-icon">${emoji}</span>
                    <div class="artifact-details">
                        <div class="artifact-url"><a href="${escapeHtml(artifact.url)}" target="_blank">${escapeHtml(artifact.url)}</a></div>
                        <div class="artifact-type">${escapeHtml(artifact.artifact_type || "unknown")}</div>
                        ${artifact.description ? `<div class="artifact-description">${escapeHtml(artifact.description)}</div>` : ""}
                    </div>
                </div>
            `;
        }
    }
    
    html += `</div>`;
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
// Render Reproducibility Aspects (EXTENSIBLE)
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
        html += `<div class="aspect-category">`;
        html += `<h4 class="category-name">${categoryLabel(category)}</h4>`;
        html += `<div class="aspect-items">`;
        
        for (const aspect of items) {
            const statusClass = getStatusClass(aspect.status);
            const icon = getStatusIcon(aspect.status);
            
            html += `
                <div class="aspect-item ${statusClass}">
                    <div class="aspect-header">
                        <span class="aspect-icon">${aspect.emoji || icon}</span>
                        <div class="aspect-title">
                            <div class="aspect-name">${escapeHtml(aspect.name)}</div>
                            <div class="aspect-status">${escapeHtml(aspect.status)}</div>
                        </div>
                        <span class="severity-badge severity-${aspect.severity || 'medium'}">
                            ${aspect.severity || 'medium'}
                        </span>
                    </div>
                    ${aspect.value ? `<div class="aspect-value">${escapeHtml(aspect.value)}</div>` : ""}
                </div>
            `;
        }
        
        html += `</div></div>`;
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
    if (["partial", "limited", "partial-available"].includes(lower)) return "warning";
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
// Render Reproducibility Checklist (with multi-source evidence)
// ============================================================================

function renderChecklist() {
    let html = `<div class="checklist">`;
    
    const evaluations = currentJob.report.aspect_evaluations || [];
    
    if (evaluations.length === 0) {
        html += "<p>No evaluations available</p>";
    } else {
        // Group by tier (infer from aspect_id)
        const tierMap = {
            "dependencies_pinned": 1,
            "results_reproducible": 1,
            "hyperparameters_documented": 1,
            "dataset_available": 2,
            "environment_documented": 2,
            "test_suite_present": 2,
            "config_file_present": 2,
            "documentation_quality": 2,
            "randomness_controlled": 3,
            "license_specified": 3,
            "continuous_integration": 3,
            "data_versioning": 3,
            "computational_requirements": 3,
            "output_format_documented": 3,
            "python_version_compatibility": 3
        };
        
        const tiers = { 1: [], 2: [], 3: [] };
        
        for (const eval_item of evaluations) {
            const tier = tierMap[eval_item.aspect_id] || 3;
            tiers[tier].push(eval_item);
        }
        
        // Render by tier
        const tierLabels = {
            1: "🔴 CRITICAL - Must Have",
            2: "🟠 HIGH VALUE - Recommended",
            3: "🟡 NICE-TO-HAVE - Optional"
        };
        
        for (const [tier, items] of Object.entries(tiers)) {
            if (items.length === 0) continue;
            
            html += `<div class="tier-group">`;
            html += `<h3 class="tier-label">${tierLabels[tier]}</h3>`;
            
            for (const eval_item of items) {
                const status = eval_item.status || "unknown";
                const statusClass = getChecklistStatusClass(status);
                const icon = getChecklistIcon(status);
                
                html += `
                    <div class="checklist-item ${statusClass}">
                        <div class="checklist-header">
                            <span class="check-icon">${icon}</span>
                            <div class="check-info">
                                <div class="check-label">${escapeHtml(eval_item.name)}</div>
                                <div class="check-status">${escapeHtml(status)}</div>
                            </div>
                        </div>
                        
                        <div class="check-evidence">
                            <details>
                                <summary>View Evidence</summary>
                                <div class="evidence-detail">
                                    <p><strong>Finding:</strong> ${escapeHtml(eval_item.evidence)}</p>
                                    <p><strong>Paper supports:</strong> ${eval_item.paper_supports ? "✓ Yes" : "✗ No"}</p>
                                    <p><strong>Code supports:</strong> ${eval_item.code_supports ? "✓ Yes" : "✗ No"}</p>
                                    <p><strong>Conclusion:</strong> ${escapeHtml(eval_item.conclusion)}</p>
                                </div>
                            </details>
                        </div>
                    </div>
                `;
            }
            
            html += `</div>`;
        }
    }
    
    html += `</div>`;
    return html;
}

function getChecklistStatusClass(status) {
    if (!status) return "unknown";
    const lower = status.toLowerCase();
    if (lower === "pass") return "pass";
    if (lower === "partial") return "partial";
    return "fail";
}

function getChecklistIcon(status) {
    if (!status) return "❓";
    const lower = status.toLowerCase();
    if (lower === "pass") return "✓";
    if (lower === "partial") return "⚠";
    return "✗";
}

// ============================================================================
// Render Event Log
// ============================================================================

function renderEventLog() {
    eventLog.innerHTML = "";
    
    if (!currentJob.events || currentJob.events.length === 0) {
        const entry = document.createElement("div");
        entry.className = "log-entry";
        entry.textContent = "No events recorded";
        eventLog.appendChild(entry);
        return;
    }
    
    for (const event of currentJob.events) {
        const entry = document.createElement("div");
        entry.className = `log-entry ${event.severity || "info"}`;
        
        const time = new Date(event.timestamp).toLocaleTimeString();
        const step = event.step ? `[${event.step}]` : "";
        const message = event.message || "";
        
        entry.textContent = `${time} ${step} ${message}`;
        eventLog.appendChild(entry);
    }
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
