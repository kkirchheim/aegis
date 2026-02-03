/**
 * History Page - Browse past analyses with search and filtering
 */

// State
let allJobs = [];
let filteredJobs = [];
let currentSort = 'date'; // date, score, name

// DOM Elements
const searchInput = document.getElementById('searchInput');
const statusFilter = document.getElementById('statusFilter');
const scoreFilter = document.getElementById('scoreFilter');
const sortDate = document.getElementById('sortDate');
const sortScore = document.getElementById('sortScore');
const sortName = document.getElementById('sortName');
const jobsList = document.getElementById('jobsList');
const emptyState = document.getElementById('emptyState');
const resultCount = document.getElementById('resultCount');

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    loadJobs();
    setupEventListeners();
});

function setupEventListeners() {
    searchInput.addEventListener('input', filterJobs);
    statusFilter.addEventListener('change', filterJobs);
    scoreFilter.addEventListener('change', filterJobs);
    
    sortDate.addEventListener('click', () => {
        currentSort = 'date';
        updateSortButtons();
        sortAndRender();
    });
    sortScore.addEventListener('click', () => {
        currentSort = 'score';
        updateSortButtons();
        sortAndRender();
    });
    sortName.addEventListener('click', () => {
        currentSort = 'name';
        updateSortButtons();
        sortAndRender();
    });
}

function updateSortButtons() {
    sortDate.classList.toggle('btn-primary', currentSort === 'date');
    sortScore.classList.toggle('btn-primary', currentSort === 'score');
    sortName.classList.toggle('btn-primary', currentSort === 'name');
    
    sortDate.classList.toggle('btn-outline', currentSort !== 'date');
    sortScore.classList.toggle('btn-outline', currentSort !== 'score');
    sortName.classList.toggle('btn-outline', currentSort !== 'name');
}

// ============================================================================
// Load Jobs
// ============================================================================

async function loadJobs() {
    try {
        const response = await fetch('/jobs');
        
        if (!response.ok) {
            jobsList.innerHTML = '<div class="alert alert-error">Failed to load jobs</div>';
            return;
        }
        
        allJobs = await response.json();
        
        // Sort by date (newest first) by default
        allJobs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        
        filterJobs();
        
    } catch (error) {
        console.error('Failed to load jobs:', error);
        jobsList.innerHTML = '<div class="alert alert-error">Error loading jobs</div>';
    }
}

// ============================================================================
// Filter Jobs
// ============================================================================

function filterJobs() {
    const search = searchInput.value.toLowerCase();
    const status = statusFilter.value;
    const minScore = scoreFilter.value ? parseInt(scoreFilter.value) : 0;
    
    filteredJobs = allJobs.filter(job => {
        // Search filter
        const filename = (job.pdf_filename || '').toLowerCase();
        if (search && !filename.includes(search)) {
            return false;
        }
        
        // Status filter
        if (status && job.status !== status) {
            return false;
        }
        
        // Score filter
        if (minScore > 0 && job.report) {
            try {
                const report = typeof job.report === 'string' ? JSON.parse(job.report) : job.report;
                const score = report.reproducibility_score || report.status;
                if (score && typeof score === 'number') {
                    if (score * 100 < minScore) {
                        return false;
                    }
                }
            } catch (e) {
                // If can't parse, include it
            }
        }
        
        return true;
    });
    
    sortAndRender();
}

// ============================================================================
// Sort and Render
// ============================================================================

function sortAndRender() {
    // Sort
    if (currentSort === 'date') {
        filteredJobs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    } else if (currentSort === 'score') {
        filteredJobs.sort((a, b) => {
            const scoreA = getScore(a);
            const scoreB = getScore(b);
            return scoreB - scoreA;
        });
    } else if (currentSort === 'name') {
        filteredJobs.sort((a, b) => {
            const nameA = (a.pdf_filename || '').toLowerCase();
            const nameB = (b.pdf_filename || '').toLowerCase();
            return nameA.localeCompare(nameB);
        });
    }
    
    // Render
    renderJobs();
}

function getScore(job) {
    try {
        const report = typeof job.report === 'string' ? JSON.parse(job.report) : job.report;
        if (report && typeof report.reproducibility_score === 'number') {
            return report.reproducibility_score * 100;
        }
    } catch (e) {
        // Ignore parse errors
    }
    return 0;
}

// ============================================================================
// Render Jobs
// ============================================================================

function renderJobs() {
    // Update result count
    resultCount.textContent = `${filteredJobs.length} Result${filteredJobs.length !== 1 ? 's' : ''}`;
    
    if (filteredJobs.length === 0) {
        jobsList.style.display = 'none';
        emptyState.style.display = 'block';
        return;
    }
    
    jobsList.style.display = 'block';
    emptyState.style.display = 'none';
    
    let html = '';
    
    for (const job of filteredJobs) {
        const status = job.status;
        const statusIcon = status === 'completed' ? '✓' : status === 'failed' ? '✗' : '⏳';
        const statusBadge = status === 'completed' ? 'badge-success' : status === 'failed' ? 'badge-error' : 'badge-warning';
        
        const filename = job.pdf_filename || `Report ${job.id.substring(0, 8)}`;
        const createdDate = new Date(job.created_at).toLocaleDateString();
        const createdTime = new Date(job.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        
        let scoreHtml = '';
        let score = getScore(job);
        if (score > 0) {
            const scoreColor = score >= 80 ? 'text-success' : score >= 60 ? 'text-warning' : 'text-error';
            scoreHtml = `<div class="text-right">
                <div class="${scoreColor} font-bold">${Math.round(score)}%</div>
                <div class="text-xs text-base-content/50">Reproducibility</div>
            </div>`;
        }
        
        html += `
            <div class="card card-compact bg-base-200 hover:shadow-lg transition-shadow cursor-pointer" onclick="viewJob('${job.id}')">
                <div class="card-body p-4">
                    <div class="flex justify-between items-start gap-4">
                        <div class="flex-1">
                            <div class="font-semibold text-base flex items-center gap-2">
                                <span class="text-lg">${statusIcon}</span>
                                <span class="truncate">${escapeHtml(filename)}</span>
                                <span class="badge ${statusBadge} badge-sm flex-shrink-0">${status}</span>
                            </div>
                            <div class="text-xs text-base-content/60 mt-1">
                                ${createdDate} at ${createdTime}
                            </div>
                        </div>
                        ${scoreHtml}
                    </div>
                </div>
            </div>
        `;
    }
    
    jobsList.innerHTML = html;
}

// ============================================================================
// Navigation
// ============================================================================

function viewJob(jobId) {
    window.location.href = `/reports/${jobId}`;
}

// ============================================================================
// Utilities
// ============================================================================

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================================
// Theme Toggle
// ============================================================================

function toggleTheme() {
    const html = document.documentElement;
    const isDark = html.getAttribute('data-theme') === 'dark';
    html.setAttribute('data-theme', isDark ? 'light' : 'dark');
    document.getElementById('themeIcon').textContent = isDark ? '🌙' : '☀️';
    localStorage.setItem('theme', isDark ? 'light' : 'dark');
}
