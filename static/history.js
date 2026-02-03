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
const sortDate = document.getElementById('sortDate');
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
    
    sortDate.addEventListener('click', () => {
        currentSort = 'date';
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
    sortName.classList.toggle('btn-primary', currentSort === 'name');
    
    sortDate.classList.toggle('btn-outline', currentSort !== 'date');
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
    
    filteredJobs = allJobs.filter(job => {
        // Search filter - search by title, filename, or abstract
        const title = (job.title || '').toLowerCase();
        const filename = (job.pdf_filename || '').toLowerCase();
        const abstract = (job.abstract || '').toLowerCase();
        if (search && !title.includes(search) && !filename.includes(search) && !abstract.includes(search)) {
            return false;
        }
        
        // Status filter
        if (status && job.status !== status) {
            return false;
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
    } else if (currentSort === 'name') {
        filteredJobs.sort((a, b) => {
            const nameA = (a.title || a.pdf_filename || '').toLowerCase();
            const nameB = (b.title || b.pdf_filename || '').toLowerCase();
            return nameA.localeCompare(nameB);
        });
    }
    
    // Render
    renderJobs();
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
        
        const paperTitle = job.title || job.pdf_filename || `Report ${job.id.substring(0, 8)}`;
        const abstract = job.abstract ? `<p class="text-sm text-base-content/70 line-clamp-2 mt-2 mb-2">${escapeHtml(job.abstract)}</p>` : '';
        const createdDate = new Date(job.created_at).toLocaleDateString();
        const createdTime = new Date(job.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        
        html += `
            <div class="card card-compact bg-base-200 hover:shadow-lg transition-shadow cursor-pointer" onclick="viewJob('${job.id}')">
                <div class="card-body p-4">
                    <div class="flex justify-between items-start gap-4">
                        <div class="flex-1">
                            <div class="font-semibold text-base flex items-center gap-2 mb-1">
                                <span class="text-lg">${statusIcon}</span>
                                <span class="truncate">${escapeHtml(paperTitle)}</span>
                                <span class="badge ${statusBadge} badge-sm flex-shrink-0">${status}</span>
                            </div>
                            ${abstract}
                            <div class="text-xs text-base-content/60">
                                ${createdDate} at ${createdTime}
                            </div>
                        </div>
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
    window.location.href = `/results/${jobId}`;
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
