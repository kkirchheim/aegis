/**
 * AEGIS - Frontend
 * 
 * Handles:
 * - PDF upload
 * - Redirect to report page
 * - Job history
 */

// State
let currentJobId = null;

// DOM Elements
const pdfInput = document.getElementById("pdfInput");
const analyzeBtn = document.getElementById("analyzeBtn");
const uploadArea = document.querySelector(".upload-area");
const uploadSection = document.getElementById("uploadSection");
const jobsList = document.getElementById("jobsList");
const manualArtifactUrls = document.getElementById("manualArtifactUrls");
const agentInstructions = document.getElementById("agentInstructions");

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
            textEl.textContent = `Selected: ${file.name}`;
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
    formData.append("docker_image", document.getElementById("dockerImageSelect").value);
    formData.append("model", document.getElementById("modelSelect").value);
    formData.append("cpu_limit", document.getElementById("cpuLimit").value);
    formData.append("memory_limit", document.getElementById("memoryLimit").value);
    formData.append("runtime_limit", document.getElementById("runtimeLimit").value);
    formData.append("max_iterations", document.getElementById("maxIterations").value);
    formData.append("storage_limit", document.getElementById("storageLimit").value);
    formData.append("temperature", document.getElementById("temperature").value);
    if (manualArtifactUrls && manualArtifactUrls.value.trim()) {
        formData.append("manual_artifact_urls", manualArtifactUrls.value.trim());
    }
    if (agentInstructions && agentInstructions.value.trim()) {
        formData.append("agent_instructions", agentInstructions.value.trim());
    }
    
    try {
        analyzeBtn.disabled = true;
        
        // Upload PDF
        const response = await fetch("/api/job/upload", {
            method: "POST",
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            alert(`Upload failed: ${error.error}`);
            analyzeBtn.disabled = false;
            return;
        }
        
        const result = await response.json();
        currentJobId = result.job_id;
        
        // Redirect immediately to report page
        window.location.href = `/job/${currentJobId}`;
        
    } catch (error) {
        alert(`Upload error: ${error.message}`);
        analyzeBtn.disabled = false;
    }
}

// ============================================================================
// Jobs History
// ============================================================================

async function loadJobsHistory() {
    // Only load if jobsList element exists (only on history page)
    if (!jobsList) return;
    
    try {
        const response = await fetch("/api/job");
        const data = await response.json();
        const jobs = data.jobs || [];  // Extract jobs array from envelope format
        
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
                                    <i class="fa-solid fa-file-lines" aria-hidden="true"></i>
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
                                    <i class="fa-solid fa-trash" aria-hidden="true"></i>
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
        const response = await fetch(`/api/job/${jobId}`, {
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
    window.location.href = `/job/${jobId}`;
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
// Initialization
// ============================================================================

document.addEventListener("DOMContentLoaded", () => {
    loadJobsHistory();
});
