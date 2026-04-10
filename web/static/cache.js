/**
 * Cache Management Functions
 * Shared across all pages via navbar
 */

async function openCacheModal() {
    const modal = document.getElementById('cacheModal');
    if (modal) {
        modal.showModal();
        await loadCacheStats();
    }
}

async function loadCacheStats() {
    try {
        const response = await fetch('/api/cache/stats');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const stats = await response.json();
        
        console.log('Cache stats loaded:', stats);
        
        const paperEl = document.getElementById('cacheStatPaper');
        const codeEl = document.getElementById('cacheStatCode');
        const evalEl = document.getElementById('cacheStatEval');
        const totalEl = document.getElementById('cacheStatTotal');
        const emptyNoteEl = document.getElementById('cacheEmptyNote');
        
        const paper = Number(stats.paper_analysis || 0);
        const code = Number(stats.code_execution || 0);
        const eval_count = Number(stats.evaluation || 0);
        const total = Number(stats.total || 0);
        
        if (paperEl) paperEl.textContent = paper;
        if (codeEl) codeEl.textContent = code;
        if (evalEl) evalEl.textContent = eval_count;
        if (totalEl) totalEl.textContent = total;
        
        // Show/hide empty message
        if (emptyNoteEl) {
            emptyNoteEl.style.display = total === 0 ? 'block' : 'none';
        }
    } catch (error) {
        console.error('Failed to load cache stats:', error);
        // Set fallback values
        if (document.getElementById('cacheStatPaper')) {
            document.getElementById('cacheStatPaper').textContent = '?';
            document.getElementById('cacheStatCode').textContent = '?';
            document.getElementById('cacheStatEval').textContent = '?';
            document.getElementById('cacheStatTotal').textContent = '?';
        }
    }
}

async function clearCache() {
    if (!confirm('Clear all cache? This will free up storage but slow down future analyses.')) {
        return;
    }
    
    try {
        const response = await fetch('/api/cache/clear', { method: 'DELETE' });
        const result = await response.json();
        
        if (response.ok) {
            alert('Cache cleared successfully');
            await loadCacheStats();
        } else {
            alert('Failed to clear cache: ' + result.error);
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}
