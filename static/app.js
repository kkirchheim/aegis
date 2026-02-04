/**
 * Paper Reproducibility Checker - Frontend
 * 
 * Handles:
 * - PDF upload
 * - SSE connection for live progress
 * - Report display
 * - Job history
 */

// State
let currentJobId = null;
let eventSource = null;
let pollInterval = null;
let lastStage = null;
let stages = {
  paper_analysis: { name: '📄 Paper Analysis', status: 'pending', start: null, duration: null },
  code_execution: { name: '⚙️ Code Execution', status: 'pending', start: null, duration: null },
  reproducibility_evaluation: { name: '📊 Evaluation', status: 'pending', start: null, duration: null }
};

// DOM Elements
const pdfInput = document.getElementById("pdfInput");
const analyzeBtn = document.getElementById("analyzeBtn");
const uploadArea = document.querySelector(".upload-area");
const uploadSection = document.getElementById("uploadSection");
const progressSection = document.getElementById("progressSection");
const reportSection = document.getElementById("reportSection");
const progressLog = document.getElementById("progressLog");
const progressFill = document.getElementById("progressFill");
const progressText = document.getElementById("progressText");
const reportContent = document.getElementById("reportContent");
const jobsList = document.getElementById("jobsList");

// ============================================================================
// Upload Handling
// ============================================================================

// Only set up upload handlers if elements exist (only on index.html)
if (pdfInput) pdfInput.addEventListener("change", updateUploadUI);
if (uploadArea) {
    uploadArea.addEventListener("dragover", handleDragOver);
    uploadArea.addEventListener("dragleave", handleDragLeave);
    uploadArea.addEventListener("drop", handleDrop);
}
if (analyzeBtn) analyzeBtn.addEventListener("click", handleAnalyzeClick);

function updateUploadUI() {
    if (!pdfInput) return;
    const file = pdfInput.files[0];
    if (file) {
        analyzeBtn.disabled = false;
        const textEl = uploadArea?.querySelector(".text-lg");
        if (textEl) {
            textEl.textContent = `✓ Selected: ${file.name}`;
        }
    }
}

function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    uploadArea.classList.add("dragover");
}

function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    uploadArea.classList.remove("dragover");
}

function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    uploadArea.classList.remove("dragover");
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        pdfInput.files = files;
        updateUploadUI();
    }
}

// ============================================================================
// Analysis Flow
// ============================================================================

async function handleAnalyzeClick() {
    const file = pdfInput.files[0];
    if (!file) return;
    
    // Prepare form data
    const formData = new FormData();
    formData.append("pdf", file);
    
    // Add configuration options
    formData.append("container", document.getElementById("containerSelect").value);
    formData.append("model", document.getElementById("modelSelect").value);
    formData.append("cpu_limit", document.getElementById("cpuLimit").value);
    formData.append("memory_limit", document.getElementById("memoryLimit").value);
    formData.append("runtime_limit", document.getElementById("runtimeLimit").value);
    formData.append("max_iterations", document.getElementById("maxIterations").value);
    formData.append("storage_limit", document.getElementById("storageLimit").value);
    
    try {
        analyzeBtn.disabled = true;
        progressSection.style.display = "block";
        reportSection.style.display = "none";
        progressLog.innerHTML = "";
        progressFill.value = 0;
        progressText.textContent = "Uploading...";
        
        // Reset stages
        Object.keys(stages).forEach(key => {
            stages[key] = { name: stages[key].name, status: 'pending', start: null, duration: null };
        });
        updateStagesUI();
        
        // Upload PDF
        const response = await fetch("/upload", {
            method: "POST",
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            logError(`Upload failed: ${error.error}`);
            analyzeBtn.disabled = false;
            return;
        }
        
        const result = await response.json();
        currentJobId = result.job_id;
        
        addLog(`Job started: ${currentJobId.substring(0, 8)}...`);
        
        // Connect to SSE stream
        connectToEventStream(currentJobId);
        
    } catch (error) {
        logError(`Upload error: ${error.message}`);
        analyzeBtn.disabled = false;
    }
}

// ============================================================================
// Polling + SSE Architecture
// ============================================================================

function connectToEventStream(jobId) {
    addLog("Starting analysis...");
    
    // Start polling job progress (1-2 second intervals)
    startProgressPolling(jobId);
    
    // Connect to SSE for logs only
    eventSource = new EventSource(`/events/${jobId}`);
    
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleLogEvent(data);
    };
    
    eventSource.onerror = (error) => {
        console.error("SSE connection error:", error);
        // Don't log this every time - just close silently
        eventSource.close();
    };
}

function startProgressPolling(jobId) {
    // Poll every 1.5 seconds for job progress
    pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/job/${jobId}/full`);
            if (!response.ok) {
                console.error(`Poll failed: HTTP ${response.status}`);
                return;
            }
            
            const job = await response.json();
            updateProgressFromJob(job);
            
            // Stop polling if job is complete
            if (job.status === "completed" || job.status === "failed") {
                stopProgressPolling();
                handleJobComplete(job);
            }
        } catch (error) {
            console.error("Polling error:", error);
        }
    }, 1500);
}

function stopProgressPolling() {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}

function updateProgressFromJob(job) {
    // Update progress bar from backend field
    const progressPercentage = Math.round((job.progress || 0) * 100);
    if (progressFill && progressText) {
        progressFill.value = progressPercentage;
        progressText.textContent = `${progressPercentage}%`;
    }
    
    // Update stages based on current_stage field
    if (job.current_stage && job.current_stage !== lastStage) {
        lastStage = job.current_stage;
        updateStagesFromStage(job.current_stage);
    }
}

function handleLogEvent(event) {
    // SSE now only handles logs/events, not progress
    const { step, message, error } = event;
    
    // Skip stage events (progress is handled by polling)
    if (step && step.includes('stage_')) {
        return;
    }
    
    // Add to log
    if (error) {
        logError(`[${step}] ${message}`);
    } else if (step && message) {
        addLog(`[${step}] ${message}`);
    }
}

function updateStagesFromStage(currentStage) {
    // Map backend stage names to our internal stage keys
    const stageMap = {
        'paper_analysis': 'paper_analysis',
        'code_execution': 'code_execution',
        'evaluation': 'reproducibility_evaluation',
        'completed': null  // All stages complete
    };
    
    const stageKey = stageMap[currentStage];
    
    // Mark all stages based on current position
    const stageKeys = Object.keys(stages);
    const stageOrder = ['paper_analysis', 'code_execution', 'reproducibility_evaluation'];
    const currentIndex = stageOrder.indexOf(stageKey);
    
    stageOrder.forEach((key, index) => {
        if (index < currentIndex) {
            stages[key].status = 'complete';
        } else if (index === currentIndex) {
            stages[key].status = 'active';
            stages[key].start = Date.now();
        } else {
            stages[key].status = 'pending';
        }
    });
    
    updateStagesUI();
}

function handleJobComplete(job) {
    // Stop polling and SSE
    stopProgressPolling();
    if (eventSource) {
        eventSource.close();
    }
    
    // Mark all stages as complete
    Object.keys(stages).forEach(key => {
        stages[key].status = 'complete';
    });
    updateStagesUI();
    
    // Show completion UI
    handleAnalysisComplete(job.report || { status: job.status, message: "Analysis complete" });
    analyzeBtn.disabled = false;
}

function updateStagesUI() {
    const stageMap = {
        paper_analysis: { id: 'stage1', icon: 'stage1Icon', time: 'stage1Time' },
        code_execution: { id: 'stage2', icon: 'stage2Icon', time: 'stage2Time' },
        reproducibility_evaluation: { id: 'stage3', icon: 'stage3Icon', time: 'stage3Time' }
    };
    
    Object.entries(stages).forEach(([key, stage]) => {
        const map = stageMap[key];
        const iconEl = document.getElementById(map.icon);
        const timeEl = document.getElementById(map.time);
        
        if (stage.status === 'complete') {
            iconEl.textContent = '✓';
            iconEl.className = 'text-2xl mb-1 text-green-500';
            const seconds = (stage.duration / 1000).toFixed(1);
            timeEl.textContent = `${seconds}s`;
        } else if (stage.status === 'active') {
            iconEl.textContent = '▶';
            iconEl.className = 'text-2xl mb-1 text-orange-500 animate-pulse';
            timeEl.textContent = 'running...';
        } else {
            iconEl.textContent = '○';
            iconEl.className = 'text-2xl mb-1';
            timeEl.textContent = 'pending';
        }
    });
}

function addLog(message) {
    const entry = document.createElement("div");
    entry.className = "log-entry";
    entry.textContent = message;
    progressLog.appendChild(entry);
    progressLog.scrollTop = progressLog.scrollHeight;
}

function logError(message) {
    const entry = document.createElement("div");
    entry.className = "log-entry error";
    entry.textContent = `❌ ${message}`;
    progressLog.appendChild(entry);
    progressLog.scrollTop = progressLog.scrollHeight;
}

// ============================================================================
// Report Display
// ============================================================================

function handleAnalysisComplete(report) {
    progressSection.style.display = "block";
    reportSection.style.display = "block";
    
    if (!report) {
        reportContent.innerHTML = "<p>No report data available</p>";
        return;
    }
    
    // Add completion card with "View Full Results" button
    let html = `
        <div class="card bg-success text-success-content shadow-lg mb-6">
            <div class="card-body">
                <div class="flex items-center justify-between">
                    <div>
                        <h3 class="card-title">✓ Analysis Complete</h3>
                        <p>Your reproducibility analysis is ready</p>
                    </div>
                    <button class="btn btn-success-content gap-2" onclick="window.location.href='/results/${currentJobId}'">
                        <span>→</span>
                        <span>View Full Results</span>
                    </button>
                </div>
            </div>
        </div>
    `;
    
    // Get existing report HTML
    const reportHtml = getReportHtml(report);
    
    reportContent.innerHTML = html + reportHtml;
    loadJobsHistory();
}

function getReportHtml(report) {
    let html = "";
    
    // Status Badge (for agent completion)
    if (report.status) {
        const statusClass = report.status === "success" ? "success" : "error";
        const statusEmoji = report.status === "success" ? "✓" : "✗";
        const statusText = report.status === "success" ? "Reproducibility Check Passed" : "Reproducibility Check Failed";
        html += `
            <div class="status-badge ${statusClass}">
                ${statusEmoji} ${statusText}
            </div>
        `;
        
        // Add completion message
        if (report.message) {
            html += `
                <div class="report-section">
                    <h4>Analysis Result</h4>
                    <p style="line-height: 1.6; color: #555;">${escapeHtml(report.message)}</p>
                </div>
            `;
        }
        
        // Add reproducibility score if available
        if (report.reproducibility_score !== undefined) {
            const percentage = Math.round(report.reproducibility_score * 100);
            const scoreClass = percentage >= 80 ? "success" : percentage >= 50 ? "warning" : "error";
            html += `
                <div class="report-section">
                    <h4>Reproducibility Score</h4>
                    <div class="reproducibility-check">
                        <span class="check-label">Score</span>
                        <span class="check-value ${scoreClass}">${percentage}%</span>
                    </div>
                </div>
            `;
        }
    }
    
    // Code Found Badge (for paper analysis)
    if (report.code_found !== undefined) {
        const codeStatus = report.code_found ? "found" : "not-found";
        const codeEmoji = report.code_found ? "✓" : "✗";
        html += `
            <div class="status-badge ${codeStatus}">
                ${codeEmoji} Code Artifacts: ${report.code_found ? "Found" : "Not Found"}
            </div>
        `;
    }
    
    // Artifacts Section
    if (report.artifacts && report.artifacts.length > 0) {
        html += `
            <div class="report-section">
                <h4>Code Artifacts Found</h4>
                <ul class="artifact-list">
        `;
        
        for (const artifact of report.artifacts) {
            html += `
                <li class="artifact-item">
                    <div class="artifact-url">🔗 ${escapeHtml(artifact.url)}</div>
                    <div class="artifact-type">${escapeHtml(artifact.type || "unknown")}</div>
                    ${artifact.description ? `<div class="artifact-description">${escapeHtml(artifact.description)}</div>` : ""}
                </li>
            `;
        }
        
        html += `
                </ul>
            </div>
        `;
    }
    
    // Summary
    if (report.summary) {
        html += `
            <div class="report-section">
                <h4>Summary</h4>
                <p style="line-height: 1.6; color: #555;">${escapeHtml(report.summary)}</p>
            </div>
        `;
    }
    
    return html;
}

function displayReport(report) {
    let html = "";
    
    // Status Badge (for agent completion)
    if (report.status) {
        const statusClass = report.status === "success" ? "success" : "error";
        const statusEmoji = report.status === "success" ? "✓" : "✗";
        const statusText = report.status === "success" ? "Reproducibility Check Passed" : "Reproducibility Check Failed";
        html += `
            <div class="status-badge ${statusClass}">
                ${statusEmoji} ${statusText}
            </div>
        `;
        
        // Add completion message
        if (report.message) {
            html += `
                <div class="report-section">
                    <h4>Analysis Result</h4>
                    <p style="line-height: 1.6; color: #555;">${escapeHtml(report.message)}</p>
                </div>
            `;
        }
        
        // Add reproducibility score if available
        if (report.reproducibility_score !== undefined) {
            const percentage = Math.round(report.reproducibility_score * 100);
            const scoreClass = percentage >= 80 ? "success" : percentage >= 50 ? "warning" : "error";
            html += `
                <div class="report-section">
                    <h4>Reproducibility Score</h4>
                    <div class="reproducibility-check">
                        <span class="check-label">Score</span>
                        <span class="check-value ${scoreClass}">${percentage}%</span>
                    </div>
                </div>
            `;
        }
    }
    
    // Code Found Badge (for paper analysis)
    if (report.code_found !== undefined) {
        const codeStatus = report.code_found ? "found" : "not-found";
        const codeEmoji = report.code_found ? "✓" : "✗";
        html += `
            <div class="status-badge ${codeStatus}">
                ${codeEmoji} Code Artifacts: ${report.code_found ? "Found" : "Not Found"}
            </div>
        `;
    }
    
    // Artifacts Section
    if (report.artifacts && report.artifacts.length > 0) {
        html += `
            <div class="report-section">
                <h4>Code Artifacts Found</h4>
                <ul class="artifact-list">
        `;
        
        for (const artifact of report.artifacts) {
            html += `
                <li class="artifact-item">
                    <div class="artifact-url">🔗 ${escapeHtml(artifact.url)}</div>
                    <div class="artifact-type">${escapeHtml(artifact.type || "unknown")}</div>
                    ${artifact.description ? `<div class="artifact-description">${escapeHtml(artifact.description)}</div>` : ""}
                </li>
            `;
        }
        
        html += `
                </ul>
            </div>
        `;
    }
    
    // Reproducibility Aspects
    if (report.reproducibility_aspects) {
        const aspects = report.reproducibility_aspects;
        html += `
            <div class="report-section">
                <h4>Reproducibility Aspects</h4>
        `;
        
        if (aspects.hyperparameters_documented !== undefined) {
            const check = aspects.hyperparameters_documented ? "✓" : "✗";
            const checkClass = aspects.hyperparameters_documented ? "success" : "error";
            html += `
                <div class="reproducibility-check">
                    <span class="check-icon ${checkClass}">${check}</span>
                    <span class="check-label">Hyperparameters Documented</span>
                    <span class="check-value">${aspects.hyperparameters_documented ? "Yes" : "No"}</span>
                </div>
            `;
        }
        
        if (aspects.implementation_details) {
            const statusClass = aspects.implementation_details === "sufficient" ? "success" : aspects.implementation_details === "partial" ? "warning" : "error";
            html += `
                <div class="reproducibility-check">
                    <span class="check-icon">${aspects.implementation_details === "sufficient" ? "✓" : "⚠"}</span>
                    <span class="check-label">Implementation Details</span>
                    <span class="check-value">${aspects.implementation_details}</span>
                </div>
            `;
        }
        
        if (aspects.dataset_description) {
            html += `
                <div class="reproducibility-check">
                    <span class="check-icon">📊</span>
                    <span class="check-label">Dataset</span>
                    <span class="check-value">${escapeHtml(aspects.dataset_description)}</span>
                </div>
            `;
        }
        
        if (aspects.environment_requirements) {
            html += `
                <div class="reproducibility-check">
                    <span class="check-icon">⚙️</span>
                    <span class="check-label">Environment Requirements</span>
                    <span class="check-value">${escapeHtml(aspects.environment_requirements)}</span>
                </div>
            `;
        }
        
        html += `</div>`;
    }
    
    // Summary
    if (report.summary) {
        html += `
            <div class="report-section">
                <h4>Summary</h4>
                <p style="line-height: 1.6; color: #555;">${escapeHtml(report.summary)}</p>
            </div>
        `;
    }
    
    reportContent.innerHTML = html;
}

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
// Jobs History
// ============================================================================

async function loadJobsHistory() {
    // Only load if jobsList element exists (only on history page)
    if (!jobsList) return;
    
    try {
        const response = await fetch("/jobs");
        const jobs = await response.json();
        
        if (jobs.length === 0) {
            jobsList.innerHTML = '<div class="text-center py-8 text-base-content/60"><p>No previous analyses yet</p></div>';
            return;
        }
        
        let html = "";
        for (const job of jobs) {
            const createdDate = new Date(job.created_at).toLocaleString();
            const statusColor = job.status === 'completed' ? 'badge-success' : job.status === 'failed' ? 'badge-error' : 'badge-warning';
            const paperTitle = job.title || job.pdf_filename || 'Unknown';
            const abstract = job.abstract ? `<p class="text-sm text-base-content/70 line-clamp-2 mb-2">${escapeHtml(job.abstract)}</p>` : '';
            
            html += `
                <div class="card bg-base-200 cursor-pointer hover:shadow-md transition-shadow" onclick="viewJob('${job.id}')">
                    <div class="card-body p-4">
                        <div class="flex justify-between items-start gap-4">
                            <div class="flex-1">
                                <h3 class="card-title text-base gap-2 mb-2">
                                    <span>📄</span>
                                    ${escapeHtml(paperTitle)}
                                </h3>
                                ${abstract}
                                <p class="text-xs text-base-content/60">
                                    Created: ${createdDate}
                                </p>
                            </div>
                            <div class="flex gap-2 items-center">
                                <div class="badge ${statusColor}">
                                    ${job.status.toUpperCase()}
                                </div>
                                <button class="btn btn-ghost btn-sm" onclick="deleteJobFromList('${job.id}', event)" title="Delete">
                                    🗑️
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }
        
        jobsList.innerHTML = html;
    } catch (error) {
        console.error("Failed to load jobs history:", error);
    }
}

async function deleteJobFromList(jobId, event) {
    // Prevent triggering viewJob
    event.stopPropagation();
    
    if (!confirm("Delete this analysis? This action cannot be undone.")) {
        return;
    }
    
    try {
        const response = await fetch(`/job/${jobId}`, {
            method: "DELETE"
        });
        
        if (!response.ok) {
            const error = await response.json();
            alert(`Delete failed: ${error.error}`);
            return;
        }
        
        // Reload list
        loadJobsHistory();
    } catch (error) {
        console.error("Failed to delete job:", error);
        alert(`Delete error: ${error.message}`);
    }
}

async function viewJob(jobId) {
    // Navigate to detail page
    window.location.href = `/reports/${jobId}`;
}

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener("DOMContentLoaded", () => {
    loadJobsHistory();
});

// Cleanup on page unload
window.addEventListener("beforeunload", () => {
    stopProgressPolling();
    if (eventSource) eventSource.close();
});
