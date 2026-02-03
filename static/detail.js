/**
 * Detail Page - Shows full job report with checklist, artifacts, and execution log
 * Uses DaisyUI + Tailwind for professional styling
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
        statusContent.innerHTML = "<div class='alert alert-error'>No job ID provided</div>";
        return;
    }
    
    loadJobData();
    setupEventListeners();
});

function setupEventListeners() {
    deleteBtn.addEventListener("click", () => {
        deleteModal.showModal();
    });
    
    cancelDeleteBtn.addEventListener("click", () => {
        deleteModal.close();
    });
    
    confirmDeleteBtn.addEventListener("click", deleteJob);
}

// ============================================================================
// Load Job Data
// ============================================================================

async function loadJobData() {
    try {
        const response = await fetch(`/api/job/${JOB_ID}/full`);
        
        if (!response.ok) {
            const error = await response.json();
            statusContent.innerHTML = `<div class='alert alert-error'>Error: ${error.error}</div>`;
            return;
        }
        
        currentJob = await response.json();
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
    docMeta.textContent = `${createdDate}${duration}`;
    
    // Status section
    renderStatus();
    
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
        html += `<div class="alert alert-success"><span>✓ Reproducibility Check Passed</span></div>`;
    } else if (status === "completed") {
        html += `<div class="alert alert-info"><span>✓ Analysis Completed</span></div>`;
    } else if (status === "failed") {
        html += `<div class="alert alert-error"><span>✗ Reproducibility Check Failed</span></div>`;
    } else if (status === "processing") {
        html += `<div class="alert alert-warning"><span>⏳ Processing...</span></div>`;
    } else {
        html += `<div class="alert"><span>${status || "Unknown"}</span></div>`;
    }
    
    // Score
    if (report.reproducibility_score !== undefined) {
        const percentage = Math.round(report.reproducibility_score * 100);
        html += `
            <div class="mt-4">
                <div class="flex justify-between mb-2">
                    <span class="text-sm font-semibold">Reproducibility Score</span>
                    <span class="text-sm font-bold">${percentage}%</span>
                </div>
                <progress class="progress progress-primary w-full" value="${percentage}" max="100"></progress>
            </div>
        `;
    }
    
    // Message
    if (report.message) {
        html += `<div class="mt-4 p-4 bg-base-200 rounded-lg text-sm">${escapeHtml(report.message)}</div>`;
    }
    
    // Error
    if (currentJob.error_message) {
        html += `<div class="alert alert-error mt-4"><span><strong>Error:</strong> ${escapeHtml(currentJob.error_message)}</span></div>`;
    }
    
    statusContent.innerHTML = html;
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
        // Group by tier
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

// Theme toggle
function toggleTheme() {
    const html = document.documentElement;
    const isDark = html.getAttribute('data-theme') === 'dark';
    html.setAttribute('data-theme', isDark ? 'light' : 'dark');
    localStorage.setItem('theme', isDark ? 'light' : 'dark');
}
