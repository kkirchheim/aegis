/**
 * Checks Management Page
 * Load, create, activate, and delete execution checks
 */

let allChecks = [];
let editingCheckHash = null; // Track which check is being edited

// DOM elements will be initialized after DOMContentLoaded
let loadingState;
let contentState;
let errorAlert;
let errorMessage;
let customChecksContainer;
let defaultChecksContainer;
let checkModal;
let checkNameInput;
let checkDescriptionInput;
let checkTextInput;
let emptyCustomChecks;

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('[checks] Page loaded, initializing DOM elements...');

    // Initialize DOM element references
    loadingState = document.getElementById('loadingState');
    contentState = document.getElementById('contentState');
    errorAlert = document.getElementById('errorAlert');
    errorMessage = document.getElementById('errorMessage');
    customChecksContainer = document.getElementById('custom-checks');
    defaultChecksContainer = document.getElementById('default-checks');
    checkModal = document.getElementById('check-modal');
    checkNameInput = document.getElementById('checkName');
    checkDescriptionInput = document.getElementById('checkDescription');
    checkTextInput = document.getElementById('checkText');
    emptyCustomChecks = document.getElementById('emptyCustomChecks');

    console.log('[checks] DOM elements initialized, loading checks...');
    loadChecks();
});

// ============================================================================
// Event Listeners
// ============================================================================

function openCreateModal() {
    editingCheckHash = null;
    document.getElementById('modalTitle').textContent = 'Create Execution Check';
    checkNameInput.value = '';
    checkDescriptionInput.value = '';
    checkTextInput.value = '#!/bin/bash\n';
    checkModal.style.display = 'flex';
    checkModal.classList.add('modal-open');
}

function openEditModal(scriptHash) {
    const check = allChecks.find(s => s.script_hash === scriptHash);
    if (!check) {
        showError('Check not found');
        return;
    }

    editingCheckHash = scriptHash;
    document.getElementById('modalTitle').textContent = 'Edit Execution Check';
    checkNameInput.value = check.name;
    checkDescriptionInput.value = check.description || '';
    checkTextInput.value = check.script_text_preview || '';
    checkModal.style.display = 'flex';
    checkModal.classList.add('modal-open');
}

function closeCreateModal() {
    checkModal.style.display = 'none';
    checkModal.classList.remove('modal-open');
}

function handleCreateCheck(event) {
    event.preventDefault();
    if (editingCheckHash) {
        updateCheck();
    } else {
        createCheck();
    }
}

// ============================================================================
// Load and Render Checks
// ============================================================================

async function loadChecks() {
    try {
        console.log('[checks] Loading checks...');
        const response = await fetch('/api/user/checks', {
            credentials: 'include'
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        allChecks = data.checks || [];

        console.log(`[checks] Loaded ${allChecks.length} checks`);
        renderChecks();
        showContent();
    } catch (error) {
        console.error('[checks] Error loading checks:', error);
        showError(`Failed to load checks: ${error.message}`);
    }
}

function renderChecks() {
    const customChecks = allChecks.filter(s => !s.is_default);
    const defaultChecks = allChecks.filter(s => s.is_default);

    // Render custom checks
    if (customChecks.length === 0) {
        customChecksContainer.style.display = 'none';
        emptyCustomChecks.style.display = 'block';
    } else {
        customChecksContainer.style.display = 'grid';
        emptyCustomChecks.style.display = 'none';
        customChecksContainer.className = 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3';
        customChecksContainer.innerHTML = customChecks.map(renderCheckCard).join('');
    }

    // Render default checks
    defaultChecksContainer.className = 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3';
    defaultChecksContainer.innerHTML = defaultChecks.length > 0
        ? defaultChecks.map(renderCheckCard).join('')
        : '<p class="text-base-content/50 text-center py-8">No default checks available</p>';
}

function renderCheckCard(check) {
    const createdDate = new Date(check.created_at).toLocaleDateString();
    const customBadge = !check.is_default ? '<span class="badge badge-sm badge-primary whitespace-nowrap flex-shrink-0">CUSTOM</span>' : '';
    const actionButtons = renderCheckActions(check);

    return `
        <div class="card bg-base-100 border border-base-300 shadow-sm hover:shadow-md transition-shadow">
            <div class="card-body p-4">
                <!-- Header: Name + Badge -->
                <div class="flex justify-between items-start gap-2 mb-2">
                    <h3 class="card-title text-base leading-snug flex-1">${escapeHtml(check.name)}</h3>
                    ${customBadge}
                </div>

                <!-- Description -->
                <p class="text-xs text-base-content/60 mb-3 line-clamp-2">
                    ${check.description ? escapeHtml(check.description) : '<span class="text-base-content/50">No description</span>'}
                </p>

                <!-- Controls -->
                <div class="flex flex-col gap-2 mt-auto">
                    <label class="label cursor-pointer p-0 gap-2">
                        <input type="checkbox" class="checkbox checkbox-sm check-toggle" ${check.is_active ? 'checked' : ''} onchange="toggleCheck('${check.script_hash}', this.checked)">
                        <span class="label-text text-xs">Active</span>
                    </label>

                    ${actionButtons}
                </div>
            </div>
        </div>
    `;
}

function renderCheckActions(check) {
    if (check.is_default) {
        return '';
    } else {
        return `
            <div class="flex gap-1">
                <button class="btn btn-xs btn-ghost flex-1" onclick="openEditModal('${check.script_hash}')" title="Edit">
                    ✎ Edit
                </button>
                <button class="btn btn-xs btn-ghost text-error" onclick="deleteCheck('${check.script_hash}')" title="Delete">
                    🗑
                </button>
            </div>
        `;
    }
}

// ============================================================================
// Check Actions
// ============================================================================

function toggleCheck(scriptHash, isChecked) {
    if (isChecked) {
        activateCheck(scriptHash);
    } else {
        deactivateCheck(scriptHash);
    }
}

async function activateCheck(scriptHash) {
    try {
        const response = await fetch(`/api/user/checks/${scriptHash}/activate`, {
            method: 'POST',
            credentials: 'include'
        });

        if (response.ok) {
            await loadChecks();
        } else {
            showError('Failed to activate check');
        }
    } catch (error) {
        console.error('[checks] Error activating check:', error);
        showError('Error activating check');
    }
}

async function deactivateCheck(scriptHash) {
    try {
        const response = await fetch(`/api/user/checks/${scriptHash}/deactivate`, {
            method: 'POST',
            credentials: 'include'
        });

        if (response.ok) {
            await loadChecks();
        } else {
            showError('Failed to deactivate check');
        }
    } catch (error) {
        console.error('[checks] Error deactivating check:', error);
        showError('Error deactivating check');
    }
}

async function deleteCheck(scriptHash) {
    if (!confirm('Delete this check? This cannot be undone.')) {
        return;
    }

    try {
        const response = await fetch(`/api/user/checks/${scriptHash}`, {
            method: 'DELETE',
            credentials: 'include'
        });

        if (response.ok || response.status === 204) {
            await loadChecks();
        } else {
            showError('Failed to delete check');
        }
    } catch (error) {
        console.error('[checks] Error deleting check:', error);
        showError('Error deleting check');
    }
}

async function createCheck() {
    const name = checkNameInput.value.trim();
    const description = checkDescriptionInput.value.trim();
    const script_text = checkTextInput.value.trim();

    if (!name || !script_text) {
        showError('Check name and code are required');
        return;
    }

    try {
        const response = await fetch('/api/user/checks', {
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
            await loadChecks();
        } else if (response.status === 400) {
            const err = await response.json();
            showError(err.error || 'Invalid check');
        } else {
            showError('Failed to create check');
        }
    } catch (error) {
        console.error('[checks] Error creating check:', error);
        showError('Error creating check');
    }
}

async function updateCheck() {
    const name = checkNameInput.value.trim();
    const description = checkDescriptionInput.value.trim();
    const script_text = checkTextInput.value.trim();

    if (!name || !script_text) {
        showError('Check name and code are required');
        return;
    }

    try {
        const response = await fetch(`/api/user/checks/${editingCheckHash}`, {
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
            await loadChecks();
        } else if (response.status === 400) {
            const err = await response.json();
            showError(err.error || 'Invalid check');
        } else if (response.status === 404) {
            showError('Check not found');
        } else {
            showError('Failed to update check');
        }
    } catch (error) {
        console.error('[checks] Error updating check:', error);
        showError('Error updating check');
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
    console.error('[checks]', message);
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
