/**
 * Plugins Management - Client-side functionality for plugin CRUD operations
 */

// Load and display plugins
async function loadPlugins() {
    try {
        const response = await fetch('/api/plugins', {
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error(`Failed to load plugins: ${response.statusText}`);
        }
        
        const data = await response.json();
        const plugins = data.plugins || [];
        
        // Separate defaults and custom
        const defaults = plugins.filter(a => a.is_default);
        const custom = plugins.filter(a => !a.is_default);
        
        // Render CUSTOM plugins first (appear at top), then defaults
        renderPlugins(custom, 'custom-plugins');
        renderPlugins(defaults, 'default-plugins');
        
        // Show/hide empty state for custom plugins
        const emptyState = document.getElementById('emptyCustomPlugins');
        if (custom.length === 0) {
            emptyState.style.display = 'block';
        } else {
            emptyState.style.display = 'none';
        }
        
        // Show content, hide loading
        document.getElementById('loadingState').style.display = 'none';
        document.getElementById('contentState').style.display = 'block';
        
    } catch (error) {
        console.error('Error loading plugins:', error);
        showError('Failed to load plugins: ' + error.message);
    }
}

// Render plugin cards (compact for 4-column grid)
function renderPlugins(plugins, containerId) {
    const container = document.getElementById(containerId);
    
    if (plugins.length === 0) {
        container.innerHTML = '<p class="col-span-full text-center text-base-content/60">No plugins found</p>';
        return;
    }
    
    container.innerHTML = plugins.map(plugin => `
        <div class="card bg-base-100 border border-base-300 shadow-sm hover:shadow-md transition-shadow" data-plugin-id="${plugin.id}">
            <div class="card-body p-4">
                <div class="flex justify-between items-start gap-2 mb-2">
                    <h3 class="card-title text-base leading-snug flex-1">${escapeHtml(plugin.name)}</h3>
                    <span class="badge badge-sm ${plugin.is_default ? 'badge-secondary' : 'badge-primary'} whitespace-nowrap flex-shrink-0">
                        ${plugin.is_default ? 'DEFAULT' : 'CUSTOM'}
                    </span>
                </div>
                
                <p class="text-xs text-base-content/60 mb-3 line-clamp-2">${escapeHtml(plugin.description)}</p>
                
                <div class="flex flex-col gap-2 mt-auto">
                    <label class="label cursor-pointer p-0 gap-2">
                        <input 
                            type="checkbox" 
                            class="checkbox checkbox-sm plugin-toggle" 
                            ${plugin.is_active ? 'checked' : ''}
                            onchange="togglePlugin('${plugin.id}', this.checked)"
                        >
                        <span class="label-text text-xs">${plugin.is_active ? 'Active' : 'Inactive'}</span>
                    </label>
                    
                    ${!plugin.is_default ? `
                        <div class="flex gap-1">
                            <button 
                                class="btn btn-xs btn-ghost flex-1" 
                                onclick="editPlugin('${plugin.id}')" 
                                title="Edit"
                            >
                                ✎ Edit
                            </button>
                            <button 
                                class="btn btn-xs btn-ghost text-error" 
                                onclick="deletePlugin('${plugin.id}')" 
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

// Toggle plugin active/inactive
async function togglePlugin(pluginId, isActive) {
    try {
        const response = await fetch(`/api/plugins/${pluginId}/activate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ is_active: isActive })
        });
        
        if (!response.ok) {
            throw new Error('Failed to update plugin');
        }
        
        // Reload to reflect changes
        await loadPlugins();
        
    } catch (error) {
        console.error('Error toggling plugin:', error);
        showError('Failed to update plugin: ' + error.message);
        // Reload to reset toggle state
        await loadPlugins();
    }
}

// Open create modal
function openCreateModal() {
    clearModalError();
    document.getElementById('modal-title').textContent = 'Create Evaluation Plugin';
    document.getElementById('plugin-form').reset();
    document.getElementById('plugin-form').dataset.mode = 'create';
    delete document.getElementById('plugin-form').dataset.pluginId;
    
    openPluginModal();
    
    // Focus on name field
    setTimeout(() => {
        document.getElementById('plugin-name').focus();
    }, 100);
}

// Open edit modal
async function editPlugin(pluginId) {
    try {
        const response = await fetch(`/api/plugins/${pluginId}`, {
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error('Failed to load plugin');
        }
        
        const plugin = await response.json();
        
        document.getElementById('modal-title').textContent = 'Edit Plugin';
        document.getElementById('plugin-name').value = plugin.name || '';
        document.getElementById('plugin-description').value = plugin.description || '';
        document.getElementById('plugin-prompt').value = plugin.prompt_to_use || plugin.custom_prompt || plugin.prompt || '';
        
        const form = document.getElementById('plugin-form');
        form.dataset.mode = 'edit';
        form.dataset.pluginId = pluginId;
        
        clearModalError();
        openPluginModal();
        
    } catch (error) {
        console.error('Error loading plugin:', error);
        showError('Failed to load plugin: ' + error.message);
    }
}

// Submit plugin form
async function submitPluginForm(event) {
    event.preventDefault();
    
    const form = event.target;
    const mode = form.dataset.mode;
    const pluginId = form.dataset.pluginId;
    
    const data = {
        name: document.getElementById('plugin-name').value.trim(),
        description: document.getElementById('plugin-description').value.trim(),
        prompt: document.getElementById('plugin-prompt').value.trim()
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
            response = await fetch('/api/plugins', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(data)
            });
        } else {
            response = await fetch(`/api/plugins/${pluginId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(data)
            });
        }
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || error.message || 'Failed to save plugin');
        }
        
        closePluginModal();
        await loadPlugins();
        
        // Show success message
        const action = mode === 'create' ? 'created' : 'updated';
        
    } catch (error) {
        console.error('Error saving plugin:', error);
        showModalError(error.message);
    }
}

// Delete plugin
async function deletePlugin(pluginId) {
    if (!confirm('Delete this plugin? This action cannot be undone.')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/plugins/${pluginId}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to delete plugin');
        }
        
        await loadPlugins();
        
    } catch (error) {
        console.error('Error deleting plugin:', error);
        showError('Failed to delete plugin: ' + error.message);
    }
}

// Modal helpers
function openPluginModal() {
    const modal = document.getElementById('plugin-modal');
    modal.classList.add('modal-open');
    modal.style.display = 'flex';
}

function closePluginModal() {
    const modal = document.getElementById('plugin-modal');
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
    const modal = document.getElementById('plugin-modal');
    // Close on backdrop click or on the form button backdrop
    if (event.target === modal || (event.target.tagName === 'FORM' && event.target.className.includes('modal-backdrop'))) {
        closePluginModal();
    }
});

// Close modal on Escape key
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        closePluginModal();
    }
});
