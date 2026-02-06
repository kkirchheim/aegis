/**
 * Aspects Management - Client-side functionality for aspect CRUD operations
 */

// Load and display aspects
async function loadAspects() {
    try {
        const response = await fetch('/api/aspects', {
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error(`Failed to load aspects: ${response.statusText}`);
        }
        
        const data = await response.json();
        const aspects = data.aspects || [];
        
        // Separate defaults and custom
        const defaults = aspects.filter(a => a.is_default);
        const custom = aspects.filter(a => !a.is_default);
        
        // Render CUSTOM aspects first (appear at top), then defaults
        renderAspects(custom, 'custom-aspects');
        renderAspects(defaults, 'default-aspects');
        
        // Show/hide empty state for custom aspects
        const emptyState = document.getElementById('emptyCustomAspects');
        if (custom.length === 0) {
            emptyState.style.display = 'block';
        } else {
            emptyState.style.display = 'none';
        }
        
        // Show content, hide loading
        document.getElementById('loadingState').style.display = 'none';
        document.getElementById('contentState').style.display = 'block';
        
    } catch (error) {
        console.error('Error loading aspects:', error);
        showError('Failed to load aspects: ' + error.message);
    }
}

// Render aspect cards (compact for 4-column grid)
function renderAspects(aspects, containerId) {
    const container = document.getElementById(containerId);
    
    if (aspects.length === 0) {
        container.innerHTML = '<p class="col-span-full text-center text-base-content/60">No aspects found</p>';
        return;
    }
    
    container.innerHTML = aspects.map(aspect => `
        <div class="card bg-base-100 border border-base-300 shadow-sm hover:shadow-md transition-shadow" data-aspect-id="${aspect.id}">
            <div class="card-body p-4">
                <div class="flex justify-between items-start gap-2 mb-2">
                    <h3 class="card-title text-base leading-snug flex-1">${escapeHtml(aspect.name)}</h3>
                    <span class="badge badge-sm ${aspect.is_default ? 'badge-secondary' : 'badge-primary'} whitespace-nowrap flex-shrink-0">
                        ${aspect.is_default ? 'DEFAULT' : 'CUSTOM'}
                    </span>
                </div>
                
                <p class="text-xs text-base-content/60 mb-3 line-clamp-2">${escapeHtml(aspect.description)}</p>
                
                <div class="flex flex-col gap-2 mt-auto">
                    <label class="label cursor-pointer p-0 gap-2">
                        <input 
                            type="checkbox" 
                            class="checkbox checkbox-sm aspect-toggle" 
                            ${aspect.is_active ? 'checked' : ''}
                            onchange="toggleAspect('${aspect.id}', this.checked)"
                        >
                        <span class="label-text text-xs">${aspect.is_active ? 'Active' : 'Inactive'}</span>
                    </label>
                    
                    ${!aspect.is_default ? `
                        <div class="flex gap-1">
                            <button 
                                class="btn btn-xs btn-ghost flex-1" 
                                onclick="editAspect('${aspect.id}')" 
                                title="Edit"
                            >
                                ✎ Edit
                            </button>
                            <button 
                                class="btn btn-xs btn-ghost text-error" 
                                onclick="deleteAspect('${aspect.id}')" 
                                title="Delete"
                            >
                                🗑
                            </button>
                        </div>
                    ` : ''}
                </div>
            </div>
        </div>
    `).join('');
}

// Toggle aspect active/inactive
async function toggleAspect(aspectId, isActive) {
    try {
        const response = await fetch(`/api/aspects/${aspectId}/activate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ is_active: isActive })
        });
        
        if (!response.ok) {
            throw new Error('Failed to update aspect');
        }
        
        // Reload to reflect changes
        await loadAspects();
        
    } catch (error) {
        console.error('Error toggling aspect:', error);
        showError('Failed to update aspect: ' + error.message);
        // Reload to reset toggle state
        await loadAspects();
    }
}

// Open create modal
function openCreateModal() {
    clearModalError();
    document.getElementById('modal-title').textContent = 'Create Reproducibility Aspect';
    document.getElementById('aspect-form').reset();
    document.getElementById('aspect-form').dataset.mode = 'create';
    delete document.getElementById('aspect-form').dataset.aspectId;
    
    openAspectModal();
    
    // Focus on name field
    setTimeout(() => {
        document.getElementById('aspect-name').focus();
    }, 100);
}

// Open edit modal
async function editAspect(aspectId) {
    try {
        const response = await fetch(`/api/aspects/${aspectId}`, {
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error('Failed to load aspect');
        }
        
        const aspect = await response.json();
        
        document.getElementById('modal-title').textContent = 'Edit Aspect';
        document.getElementById('aspect-name').value = aspect.name || '';
        document.getElementById('aspect-description').value = aspect.description || '';
        document.getElementById('aspect-prompt').value = aspect.prompt_to_use || aspect.custom_prompt || aspect.prompt || '';
        
        const form = document.getElementById('aspect-form');
        form.dataset.mode = 'edit';
        form.dataset.aspectId = aspectId;
        
        clearModalError();
        openAspectModal();
        
    } catch (error) {
        console.error('Error loading aspect:', error);
        showError('Failed to load aspect: ' + error.message);
    }
}

// Submit aspect form
async function submitAspectForm(event) {
    event.preventDefault();
    
    const form = event.target;
    const mode = form.dataset.mode;
    const aspectId = form.dataset.aspectId;
    
    const data = {
        name: document.getElementById('aspect-name').value.trim(),
        description: document.getElementById('aspect-description').value.trim(),
        prompt: document.getElementById('aspect-prompt').value.trim()
    };
    
    // Validation
    if (!data.name || !data.description || !data.prompt) {
        showModalError('All fields are required');
        return;
    }
    
    if (data.name.length > 255) {
        showModalError('Name must be 255 characters or less');
        return;
    }
    
    try {
        let response;
        
        if (mode === 'create') {
            response = await fetch('/api/aspects', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(data)
            });
        } else {
            response = await fetch(`/api/aspects/${aspectId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(data)
            });
        }
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || error.message || 'Failed to save aspect');
        }
        
        closeAspectModal();
        await loadAspects();
        
        // Show success message
        const action = mode === 'create' ? 'created' : 'updated';
        
    } catch (error) {
        console.error('Error saving aspect:', error);
        showModalError(error.message);
    }
}

// Delete aspect
async function deleteAspect(aspectId) {
    if (!confirm('Delete this aspect? This action cannot be undone.')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/aspects/${aspectId}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to delete aspect');
        }
        
        await loadAspects();
        
    } catch (error) {
        console.error('Error deleting aspect:', error);
        showError('Failed to delete aspect: ' + error.message);
    }
}

// Modal helpers
function openAspectModal() {
    const modal = document.getElementById('aspect-modal');
    modal.classList.add('modal-open');
    modal.style.display = 'flex';
}

function closeAspectModal() {
    const modal = document.getElementById('aspect-modal');
    modal.classList.remove('modal-open');
    modal.style.display = 'none';
    clearModalError();
}

function clearModalError() {
    const errorDiv = document.getElementById('modal-error');
    errorDiv.style.display = 'none';
    document.getElementById('modal-error-message').textContent = '';
}

function showModalError(message) {
    const errorDiv = document.getElementById('modal-error');
    document.getElementById('modal-error-message').textContent = message;
    errorDiv.style.display = 'flex';
    
    // Scroll to error
    errorDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function showError(message) {
    const alert = document.getElementById('errorAlert');
    document.getElementById('errorMessage').textContent = message;
    alert.style.display = 'flex';
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        alert.style.display = 'none';
    }, 5000);
}

// Utility function to escape HTML
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

// Close modal on backdrop click
document.addEventListener('click', function(event) {
    const modal = document.getElementById('aspect-modal');
    // Close on backdrop click or on the form button backdrop
    if (event.target === modal || (event.target.tagName === 'FORM' && event.target.className.includes('modal-backdrop'))) {
        closeAspectModal();
    }
});

// Close modal on Escape key
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        closeAspectModal();
    }
});
