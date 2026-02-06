/**
 * Scripts Management Page
 * Load, create, activate, and delete execution scripts
 */

let allScripts = [];

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
    scriptNameInput.value = '';
    scriptDescriptionInput.value = '';
    scriptTextInput.value = '#!/bin/bash\n';
    scriptModal.style.display = 'flex';
    scriptModal.classList.add('modal-open');
}

function closeCreateModal() {
    scriptModal.style.display = 'none';
    scriptModal.classList.remove('modal-open');
}

function handleCreateScript(event) {
    event.preventDefault();
    createScript();
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
        customScriptsContainer.innerHTML = customScripts.map(renderScriptCard).join('');
    }
    
    // Render default scripts
    defaultScriptsContainer.innerHTML = defaultScripts.length > 0 
        ? defaultScripts.map(renderScriptCard).join('')
        : '<p class="text-base-content/50">No default scripts available</p>';
}

function renderScriptCard(script) {
    const statusBadge = script.is_active 
        ? '<span class="badge badge-success badge-sm">Active</span>'
        : '<span class="badge badge-outline badge-sm">Inactive</span>';
    
    const actionButtons = renderScriptActions(script);
    
    const createdDate = new Date(script.created_at).toLocaleDateString();
    
    return `
        <div class="card bg-base-200 shadow-md hover:shadow-lg transition-shadow">
            <div class="card-body p-4">
                <div class="flex items-start justify-between gap-3 mb-2">
                    <h3 class="card-title text-base flex-1">${escapeHtml(script.name)}</h3>
                    ${statusBadge}
                </div>
                
                ${script.description ? `<p class="text-sm text-base-content/70 mb-3">${escapeHtml(script.description)}</p>` : ''}
                
                <div class="text-xs text-base-content/50 mb-4 space-y-1">
                    <div>By: <strong>${escapeHtml(script.created_by)}</strong></div>
                    <div>Created: ${createdDate}</div>
                    <div>Hash: <code class="text-xs bg-black/20 px-1 rounded">${script.script_hash.substring(0, 8)}</code></div>
                </div>
                
                <div class="card-actions justify-end gap-2">
                    ${actionButtons}
                </div>
            </div>
        </div>
    `;
}

function renderScriptActions(script) {
    if (script.is_default) {
        // Default scripts: only enable/disable
        if (script.is_active) {
            return `<button class="btn btn-sm btn-outline" onclick="deactivateScript('${script.script_hash}')">Disable</button>`;
        } else {
            return `<button class="btn btn-sm btn-primary" onclick="activateScript('${script.script_hash}')">Enable</button>`;
        }
    } else {
        // User scripts: enable/disable + delete
        const toggleBtn = script.is_active
            ? `<button class="btn btn-sm btn-outline" onclick="deactivateScript('${script.script_hash}')">Disable</button>`
            : `<button class="btn btn-sm btn-primary" onclick="activateScript('${script.script_hash}')">Enable</button>`;
        
        return `
            ${toggleBtn}
            <button class="btn btn-sm btn-error" onclick="deleteScript('${script.script_hash}')">Delete</button>
        `;
    }
}

// ============================================================================
// Script Actions
// ============================================================================

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
