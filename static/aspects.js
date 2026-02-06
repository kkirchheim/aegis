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
        
        renderAspects(defaults, 'default-aspects');
        renderAspects(custom, 'custom-aspects');
        
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

// Render aspect cards
function renderAspects(aspects, containerId) {
    const container = document.getElementById(containerId);
    
    if (aspects.length === 0) {
        container.innerHTML = '<p class="col-span-full text-center text-base-content/60">No aspects found</p>';
        return;
    }
    
    container.innerHTML = aspects.map(aspect => `
        <div class="card bg-base-200 shadow-md" data-aspect-id="${aspect.id}">
            <div class="card-body">
                <div class="flex justify-between items-start gap-2">
                    <div class="flex-1">
                        <h3 class="card-title text-lg">${escapeHtml(aspect.name)}</h3>
                        <p class="text-sm text-base-content/70 mt-2">${escapeHtml(aspect.description)}</p>
                    </div>
                    <span class="badge ${aspect.is_default ? 'badge-secondary' : 'badge-primary'}">
                        ${aspect.is_default ? 'DEFAULT' : 'CUSTOM'}
                    </span>
                </div>
                
                <div class="card-actions justify-between items-center mt-4">
                    <div class="flex items-center gap-2">
                        <input 
                            type="checkbox" 
                            class="checkbox aspect-toggle" 
                            ${aspect.is_active ? 'checked' : ''}
                            onchange="toggleAspect('${aspect.id}', this.checked)"
                        >
                        <span class="text-sm font-semibold">${aspect.is_active ? 'ENABLED' : 'DISABLED'}</span>
                    </div>
                    
                    ${!aspect.is_default ? `
                        <div class="flex gap-2">
                            <button 
                                class="btn btn-sm btn-ghost" 
                                onclick="editAspect('${aspect.id}')" 
                                title="Edit aspect"
                            >
                                ✎
                            </button>
                            <button 
                                class="btn btn-sm btn-ghost text-error" 
                                onclick="deleteAspect('${aspect.id}')" 
                                title="Delete aspect"
                            >
                                🗑️
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
    
    const modal = document.getElementById('aspect-modal');
    modal.style.display = 'flex';
    
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
        document.getElementById('aspect-prompt').value = aspect.custom_prompt || aspect.prompt || '';
        
        const form = document.getElementById('aspect-form');
        form.dataset.mode = 'edit';
        form.dataset.aspectId = aspectId;
        
        clearModalError();
        const modal = document.getElementById('aspect-modal');
        modal.style.display = 'flex';
        
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
    document.getElementById('aspect-modal').style.display = 'flex';
}

function closeAspectModal() {
    document.getElementById('aspect-modal').style.display = 'none';
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
    if (event.target === modal) {
        closeAspectModal();
    }
});

// Close modal on Escape key
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        closeAspectModal();
    }
});
