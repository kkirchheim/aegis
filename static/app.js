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

pdfInput.addEventListener("change", updateUploadUI);
uploadArea.addEventListener("dragover", handleDragOver);
uploadArea.addEventListener("dragleave", handleDragLeave);
uploadArea.addEventListener("drop", handleDrop);
analyzeBtn.addEventListener("click", handleAnalyzeClick);

function updateUploadUI() {
    const file = pdfInput.files[0];
    if (file) {
        analyzeBtn.disabled = false;
        uploadArea.querySelector("span:last-child").textContent = `Selected: ${file.name}`;
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
    
    try {
        analyzeBtn.disabled = true;
        progressSection.style.display = "block";
        reportSection.style.display = "none";
        progressLog.innerHTML = "";
        progressFill.style.width = "0%";
        progressText.textContent = "Uploading...";
        
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
// Server-Sent Events (SSE)
// ============================================================================

function connectToEventStream(jobId) {
    addLog("Connecting to live stream...");
    
    eventSource = new EventSource(`/events/${jobId}`);
    
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleProgressEvent(data);
    };
    
    eventSource.onerror = (error) => {
        console.error("SSE connection error:", error);
        eventSource.close();
        logError("Connection lost");
    };
}

function handleProgressEvent(event) {
    const { step, message, progress, error, report, artifacts, status } = event;
    
    // Update progress bar
    if (progress !== undefined) {
        progressFill.style.width = progress + "%";
        progressText.textContent = `${Math.round(progress)}%`;
    }
    
    // Add to log
    if (error) {
        logError(`[${step}] ${message}`);
    } else {
        addLog(`[${step}] ${message}`);
    }
    
    // Handle completion
    if (step === "complete") {
        // Include status in report if present
        if (status && report) {
            report.status = status;
        }
        handleAnalysisComplete(report || { status, message });
        eventSource.close();
        analyzeBtn.disabled = false;
    } else if (step === "error") {
        eventSource.close();
        analyzeBtn.disabled = false;
    }
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
    
    displayReport(report);
    loadJobsHistory();
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
    try {
        const response = await fetch("/jobs");
        const jobs = await response.json();
        
        if (jobs.length === 0) {
            jobsList.innerHTML = '<p class="empty-state">No previous analyses yet</p>';
            return;
        }
        
        let html = "";
        for (const job of jobs) {
            const createdDate = new Date(job.created_at).toLocaleString();
            html += `
                <div class="job-item">
                    <div class="job-content" onclick="viewJob('${job.id}')">
                        <div class="job-filename">📄 ${escapeHtml(job.pdf_filename)}</div>
                        <div class="job-meta">Job ID: ${job.id.substring(0, 8)}...</div>
                        <div class="job-meta">Created: ${createdDate}</div>
                    </div>
                    <div class="job-actions">
                        <span class="job-status ${job.status}">${job.status.toUpperCase()}</span>
                        <button class="btn-delete" onclick="deleteJobFromList('${job.id}', event)" title="Delete">🗑️</button>
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
