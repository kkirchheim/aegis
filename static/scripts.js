/**
 * Scripts Management Page
 * Load, create, activate, and delete execution scripts
 */

let allScripts = [];
let editingScriptHash = null; // Track which script is being edited

// DOM elements will be initialized after DOMContentLoaded
let loadingState;
let contentState;
let errorAlert;
let errorMessage;
let customScriptsContainer;
let defaultScriptsContainer;
let scriptModal;
let scriptNameInput;
let scriptDescriptionInput;
let scriptTextInput;
let emptyCustomScripts;

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('[scripts] Page loaded, initializing DOM elements...');
    
    // Initialize DOM element references
    loadingState = document.getElementById('loadingState');
    contentState = document.getElementById('contentState');
    errorAlert = document.getElementById('errorAlert');
    errorMessage = document.getElementById('errorMessage');
    customScriptsContainer = document.getElementById('custom-scripts');
    defaultScriptsContainer = document.getElementById('default-scripts');
    scriptModal = document.getElementById('script-modal');
    scriptNameInput = document.getElementById('scriptName');
    scriptDescriptionInput = document.getElementById('scriptDescription');
    scriptTextInput = document.getElementById('scriptText');
    emptyCustomScripts = document.getElementById('emptyCustomScripts');
    
    console.log('[scripts] DOM elements initialized, loading scripts...');
    loadScripts();
});

// ============================================================================
// Event Listeners
// ============================================================================

function openCreateModal() {
    editingScriptHash = null;
    document.getElementById('modalTitle').textContent = 'Create Execution Script';
    scriptNameInput.value = '';
    scriptDescriptionInput.value = '';
    scriptTextInput.value = '#!/bin/bash\n';
    scriptModal.style.display = 'flex';
    scriptModal.classList.add('modal-open');
}

function openEditModal(scriptHash) {
    const script = allScripts.find(s => s.script_hash === scriptHash);
    if (!script) {
        showError('Script not found');
        return;
    }
    
    editingScriptHash = scriptHash;
    document.getElementById('modalTitle').textContent = 'Edit Execution Script';
    scriptNameInput.value = script.name;
    scriptDescriptionInput.value = script.description || '';
    scriptTextInput.value = script.script_text_preview || '';
    scriptModal.style.display = 'flex';
    scriptModal.classList.add('modal-open');
}

function closeCreateModal() {
    scriptModal.style.display = 'none';
    scriptModal.classList.remove('modal-open');
}

function handleCreateScript(event) {
    event.preventDefault();
    if (editingScriptHash) {
        updateScript();
    } else {
        createScript();
    }
}

// ============================================================================
// Load and Render Scripts
// ============================================================================

async function loadScripts() {
    try {
        console.log('[scripts] Loading scripts...');
        const response = await fetch('/api/user/scripts', {
            credentials: 'include'
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        allScripts = data.scripts || [];
        
        console.log(`[scripts] Loaded ${allScripts.length} scripts`);
        renderScripts();
        showContent();
    } catch (error) {
        console.error('[scripts] Error loading scripts:', error);
        showError(`Failed to load scripts: ${error.message}`);
    }
}

function renderScripts() {
    const customScripts = allScripts.filter(s => !s.is_default);
    const defaultScripts = allScripts.filter(s => s.is_default);
    
    // Render custom scripts
    if (customScripts.length === 0) {
        customScriptsContainer.style.display = 'none';
        emptyCustomScripts.style.display = 'block';
    } else {
        customScriptsContainer.style.display = 'grid';
        emptyCustomScripts.style.display = 'none';
        customScriptsContainer.className = 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3';
        customScriptsContainer.innerHTML = customScripts.map(renderScriptCard).join('');
    }
    
    // Render default scripts
    defaultScriptsContainer.className = 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3';
    defaultScriptsContainer.innerHTML = defaultScripts.length > 0 
        ? defaultScripts.map(renderScriptCard).join('')
        : '<p class="text-base-content/50 text-center py-8">No default scripts available</p>';
}

function renderScriptCard(script) {
    const createdDate = new Date(script.created_at).toLocaleDateString();
    const customBadge = !script.is_default ? '<span class="badge badge-sm badge-primary whitespace-nowrap flex-shrink-0">CUSTOM</span>' : '';
    const actionButtons = renderScriptActions(script);
    
    return `
        <div class="card bg-base-100 border border-base-300 shadow-sm hover:shadow-md transition-shadow">
            <div class="card-body p-4">
                <!-- Header: Name + Badge -->
                <div class="flex justify-between items-start gap-2 mb-2">
                    <h3 class="card-title text-base leading-snug flex-1">${escapeHtml(script.name)}</h3>
                    ${customBadge}
                </div>
                
                <!-- Description -->
                <p class="text-xs text-base-content/60 mb-3 line-clamp-2">
                    ${script.description ? escapeHtml(script.description) : '<span class="text-base-content/50">No description</span>'}
                </p>
                
                <!-- Controls -->
                <div class="flex flex-col gap-2 mt-auto">
                    <label class="label cursor-pointer p-0 gap-2">
                        <input type="checkbox" class="checkbox checkbox-sm script-toggle" ${script.is_active ? 'checked' : ''} onchange="toggleScript('${script.script_hash}', this.checked)">
                        <span class="label-text text-xs">Active</span>
                    </label>
                    
                    ${actionButtons}
                </div>
            </div>
        </div>
    `;
}

function renderScriptActions(script) {
    if (script.is_default) {
        // Default scripts: no edit/delete
        return '';
    } else {
        // User scripts: edit + delete buttons
        return `
            <div class="flex gap-1">
                <button class="btn btn-xs btn-ghost flex-1" onclick="openEditModal('${script.script_hash}')" title="Edit">
                    ✎ Edit
                </button>
                <button class="btn btn-xs btn-ghost text-error" onclick="deleteScript('${script.script_hash}')" title="Delete">
                    🗑
                </button>
            </div>
        `;
    }
}

// ============================================================================
// Script Actions
// ============================================================================

function toggleScript(scriptHash, isChecked) {
    if (isChecked) {
        activateScript(scriptHash);
    } else {
        deactivateScript(scriptHash);
    }
}

async function activateScript(scriptHash) {
    try {
        const response = await fetch(`/api/user/scripts/${scriptHash}/activate`, {
            method: 'POST',
            credentials: 'include'
        });

        if (response.ok) {
            await loadScripts();
        } else {
            showError('Failed to activate script');
        }
    } catch (error) {
        console.error('[scripts] Error activating script:', error);
        showError('Error activating script');
    }
}

async function deactivateScript(scriptHash) {
    try {
        const response = await fetch(`/api/user/scripts/${scriptHash}/deactivate`, {
            method: 'POST',
            credentials: 'include'
        });

        if (response.ok) {
            await loadScripts();
        } else {
            showError('Failed to deactivate script');
        }
    } catch (error) {
        console.error('[scripts] Error deactivating script:', error);
        showError('Error deactivating script');
    }
}

async function deleteScript(scriptHash) {
    if (!confirm('Delete this script? This cannot be undone.')) {
        return;
    }

    try {
        const response = await fetch(`/api/user/scripts/${scriptHash}`, {
            method: 'DELETE',
            credentials: 'include'
        });

        if (response.ok || response.status === 204) {
            await loadScripts();
        } else {
            showError('Failed to delete script');
        }
    } catch (error) {
        console.error('[scripts] Error deleting script:', error);
        showError('Error deleting script');
    }
}

async function createScript() {
    const name = scriptNameInput.value.trim();
    const description = scriptDescriptionInput.value.trim();
    const script_text = scriptTextInput.value.trim();

    if (!name || !script_text) {
        showError('Script name and code are required');
        return;
    }

    try {
        const response = await fetch('/api/user/scripts', {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name,
                description,
                script_text
            })
        });

        if (response.status === 201) {
            closeCreateModal();
            await loadScripts();
        } else if (response.status === 400) {
            const err = await response.json();
            showError(err.error || 'Invalid script');
        } else {
            showError('Failed to create script');
        }
    } catch (error) {
        console.error('[scripts] Error creating script:', error);
        showError('Error creating script');
    }
}

async function updateScript() {
    const name = scriptNameInput.value.trim();
    const description = scriptDescriptionInput.value.trim();
    const script_text = scriptTextInput.value.trim();

    if (!name || !script_text) {
        showError('Script name and code are required');
        return;
    }

    try {
        const response = await fetch(`/api/user/scripts/${editingScriptHash}`, {
            method: 'PATCH',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name,
                description,
                script_text
            })
        });

        if (response.ok) {
            closeCreateModal();
            await loadScripts();
        } else if (response.status === 400) {
            const err = await response.json();
            showError(err.error || 'Invalid script');
        } else if (response.status === 404) {
            showError('Script not found');
        } else {
            showError('Failed to update script');
        }
    } catch (error) {
        console.error('[scripts] Error updating script:', error);
        showError('Error updating script');
    }
}

// ============================================================================
// UI Helpers
// ============================================================================

function showContent() {
    loadingState.style.display = 'none';
    contentState.style.display = 'block';
    hideError();
}

function showError(message) {
    errorMessage.textContent = message;
    errorAlert.style.display = 'flex';
    console.error('[scripts]', message);
}

function hideError() {
    errorAlert.style.display = 'none';
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}
