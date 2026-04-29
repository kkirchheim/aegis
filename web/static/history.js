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
        const response = await fetch('/api/job');
        
        if (!response.ok) {
            jobsList.innerHTML = '<div class="alert alert-error">Failed to load jobs</div>';
            return;
        }
        
        const data = await response.json();
        const jobs = data.jobs || [];  // Extract jobs array from envelope format
        
        // Fetch full data for each job to get paper_analysis
        allJobs = await Promise.all(jobs.map(async (job) => {
            try {
                const fullResponse = await fetch(`/api/job/${job.id}/full`);
                if (fullResponse.ok) {
                    const fullData = await fullResponse.json();
                    // Merge full data with basic job info
                    return {
                        ...job,
                        paper_analysis: fullData.paper_analysis,
                        // Extract paper title and abstract from paper_analysis
                        paper_title: fullData.paper_analysis?.title || job.pdf_filename,
                        paper_abstract: fullData.paper_analysis?.abstract || ''
                    };
                }
            } catch (error) {
                console.warn(`Failed to fetch full data for job ${job.id}:`, error);
            }
            // Return basic job data if full fetch fails
            return {
                ...job,
                paper_title: job.pdf_filename,
                paper_abstract: ''
            };
        }));
        
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
        // Search filter - search by paper title or abstract
        const paperTitle = (job.paper_title || '').toLowerCase();
        const paperAbstract = (job.paper_abstract || '').toLowerCase();
        if (search && !paperTitle.includes(search) && !paperAbstract.includes(search)) {
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
            const nameA = (a.paper_title || '').toLowerCase();
            const nameB = (b.paper_title || '').toLowerCase();
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
        const statusIcon = status === 'completed'
            ? '<i class="fa-solid fa-circle-check text-success" aria-hidden="true"></i>'
            : status === 'failed'
                ? '<i class="fa-solid fa-circle-xmark text-error" aria-hidden="true"></i>'
                : '<i class="fa-solid fa-hourglass-half text-warning" aria-hidden="true"></i>';
        const statusBadge = status === 'completed' ? 'badge-success' : status === 'failed' ? 'badge-error' : 'badge-warning';
        
        // Display paper title from paper_analysis
        const paperTitle = job.paper_title || `Report ${job.id.substring(0, 8)}`;
        // Display abstract from paper_analysis
        const abstract = job.paper_abstract ? `<p class="text-sm text-base-content/70 line-clamp-3 mt-2 mb-2">${escapeHtml(job.paper_abstract)}</p>` : '';
        const createdDate = new Date(job.created_at).toLocaleDateString();
        const createdTime = new Date(job.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        const pageCount = job.num_pages ? `<i class="fa-solid fa-file-lines" aria-hidden="true"></i> ${job.num_pages} page${job.num_pages !== 1 ? 's' : ''}` : '';
        
        // Build thumbnail HTML
        let thumbnailHtml = '';
        if (job.thumbnail_path) {
            thumbnailHtml = `
                <div class="flex-shrink-0 hidden sm:block">
                    <img src="/${job.thumbnail_path}" alt="PDF thumbnail" class="w-24 h-32 object-cover rounded shadow-md" onerror="this.style.display='none'">
                </div>
            `;
        }
        
        // Fallback placeholder icon if no thumbnail
        if (!job.thumbnail_path) {
            thumbnailHtml = `
                <div class="flex-shrink-0 hidden sm:flex items-center justify-center w-24 h-32 bg-base-300 rounded shadow-md text-2xl">
                    <i class="fa-solid fa-file-lines" aria-hidden="true"></i>
                </div>
            `;
        }
        
        html += `
            <div class="card card-compact bg-base-200 hover:shadow-lg transition-shadow cursor-pointer" onclick="viewJob('${job.id}')">
                <div class="card-body p-4">
                    <div class="flex justify-between items-start gap-4">
                        ${thumbnailHtml}
                        <div class="flex-1">
                            <div class="flex items-start gap-2 mb-2">
                                <span class="text-lg flex-shrink-0">${statusIcon}</span>
                                <div class="flex-1 min-w-0">
                                    <h3 class="font-semibold text-base leading-tight mb-1 break-words">${escapeHtml(paperTitle)}</h3>
                                </div>
                                <span class="badge ${statusBadge} badge-sm flex-shrink-0">${status}</span>
                            </div>
                            ${abstract}
                            <div class="text-xs text-base-content/60 flex items-center gap-3 flex-wrap mt-2">
                                <span>${createdDate} at ${createdTime}</span>
                                ${pageCount ? `<span class="text-base-content/70">${pageCount}</span>` : ''}
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
    window.location.href = `/job/${jobId}`;
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
    const theme = isDark ? 'light' : 'dark';
    html.setAttribute('data-theme', theme);
    const icon = document.getElementById('themeIcon');
    if (icon) {
        icon.className = theme === 'dark' ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
    }
    localStorage.setItem('theme', theme);
}
