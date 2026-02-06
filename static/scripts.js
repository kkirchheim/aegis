/**
 * Scripts Management Page
 * Load, create, activate, and delete execution scripts
 */

let allScripts = [];

// DOM Elements
const scriptsList = document.getElementById('scriptsList');
const scriptCount = document.getElementById('scriptCount');
const createScriptBtn = document.getElementById('createScriptBtn');
const createScriptModal = document.getElementById('createScriptModal');
const confirmCreateBtn = document.getElementById('confirmCreateBtn');
const scriptNameInput = document.getElementById('scriptName');
const scriptDescriptionInput = document.getElementById('scriptDescription');
const scriptTextInput = document.getElementById('scriptText');

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('[scripts] Page loaded');
    loadScripts();
    setupEventListeners();
});

// ============================================================================
// Event Listeners
// ============================================================================

function setupEventListeners() {
    createScriptBtn.addEventListener('click', () => {
        scriptNameInput.value = '';
        scriptDescriptionInput.value = '';
        scriptTextInput.value = '#!/bin/bash\n';
        createScriptModal.showModal();
    });

    confirmCreateBtn.addEventListener('click', async () => {
        const name = scriptNameInput.value.trim();
        const description = scriptDescriptionInput.value.trim();
        const script_text = scriptTextInput.value.trim();

        if (!name || !script_text) {
            alert('Please fill in script name and code');
            return;
        }

        confirmCreateBtn.disabled = true;
        confirmCreateBtn.textContent = 'Creating...';

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

            if (response.ok) {
                alert('Script created successfully!');
                createScriptModal.close();
                await loadScripts();
            } else {
                const err = await response.json();
                alert(`Error: ${err.error || 'Failed to create script'}`);
            }
        } catch (error) {
            console.error('[scripts] Error creating script:', error);
            alert('Failed to create script');
        } finally {
            confirmCreateBtn.disabled = false;
            confirmCreateBtn.textContent = 'Create Script';
        }
    });
}

// ============================================================================
// Load and Render Scripts
// ============================================================================

async function loadScripts() {
    try {
        const response = await fetch('/api/user/scripts', {
            credentials: 'include'
        });

        if (!response.ok) {
            console.error('[scripts] Failed to load scripts:', response.status);
            scriptsList.innerHTML = '<p class="text-error">Failed to load scripts</p>';
            return;
        }

        const data = await response.json();
        allScripts = data.scripts || [];

        scriptCount.textContent = allScripts.length;

        if (allScripts.length === 0) {
            scriptsList.innerHTML = '<p class="text-base-content/50">No scripts available</p>';
            return;
        }

        renderScripts();
    } catch (error) {
        console.error('[scripts] Error loading scripts:', error);
        scriptsList.innerHTML = '<p class="text-error">Error loading scripts</p>';
    }
}

function renderScripts() {
    // Separate default and user scripts
    const defaultScripts = allScripts.filter(s => s.is_default);
    const userScripts = allScripts.filter(s => !s.is_default);

    let html = '';

    // Default Scripts Section
    if (defaultScripts.length > 0) {
        html += '<div class="mb-6">';
        html += '<h3 class="font-semibold text-base mb-3 flex items-center gap-2"><span>📦</span> Default Scripts</h3>';
        html += defaultScripts.map(s => renderScriptCard(s)).join('');
        html += '</div>';
    }

    // User Scripts Section
    if (userScripts.length > 0) {
        html += '<div>';
        html += '<h3 class="font-semibold text-base mb-3 flex items-center gap-2"><span>👤</span> Your Scripts</h3>';
        html += userScripts.map(s => renderScriptCard(s)).join('');
        html += '</div>';
    }

    scriptsList.innerHTML = html;
}

function renderScriptCard(script) {
    const statusBadge = script.is_active 
        ? '<span class="badge badge-success">✓ Active</span>' 
        : '<span class="badge badge-outline">○ Inactive</span>';
    
    const actionBtns = script.is_default 
        ? renderDefaultScriptActions(script)
        : renderUserScriptActions(script);

    return `
        <div class="card bg-base-200 mb-3">
            <div class="card-body p-4">
                <div class="flex items-start justify-between gap-4">
                    <div class="flex-1">
                        <h4 class="font-semibold text-base flex items-center gap-2">
                            <span>${script.name}</span>
                            ${statusBadge}
                        </h4>
                        ${script.description ? `<p class="text-sm text-base-content/70 mt-1">${escapeHtml(script.description)}</p>` : ''}
                        <p class="text-xs text-base-content/50 mt-2">
                            By: <strong>${escapeHtml(script.created_by)}</strong> | 
                            Created: ${new Date(script.created_at).toLocaleDateString()}
                        </p>
                    </div>
                    <div class="flex gap-2">
                        ${actionBtns}
                    </div>
                </div>
            </div>
        </div>
    `;
}

function renderDefaultScriptActions(script) {
    if (script.is_active) {
        return `<button class="btn btn-sm btn-outline" onclick="deactivateScript('${script.script_hash}')">Disable</button>`;
    } else {
        return `<button class="btn btn-sm btn-primary" onclick="activateScript('${script.script_hash}')">Enable</button>`;
    }
}

function renderUserScriptActions(script) {
    const toggleBtn = script.is_active
        ? `<button class="btn btn-sm btn-outline" onclick="deactivateScript('${script.script_hash}')">Disable</button>`
        : `<button class="btn btn-sm btn-primary" onclick="activateScript('${script.script_hash}')">Enable</button>`;

    return `
        ${toggleBtn}
        <button class="btn btn-sm btn-error" onclick="deleteScript('${script.script_hash}')">Delete</button>
    `;
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
            alert('Failed to activate script');
        }
    } catch (error) {
        console.error('[scripts] Error activating script:', error);
        alert('Error activating script');
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
            alert('Failed to deactivate script');
        }
    } catch (error) {
        console.error('[scripts] Error deactivating script:', error);
        alert('Error deactivating script');
    }
}

async function deleteScript(scriptHash) {
    if (!confirm('Delete this script? This action cannot be undone.')) {
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
            alert('Failed to delete script');
        }
    } catch (error) {
        console.error('[scripts] Error deleting script:', error);
        alert('Error deleting script');
    }
}

// ============================================================================
// Utilities
// ============================================================================

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
