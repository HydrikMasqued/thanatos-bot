// Forum Management JavaScript
let categories = [];
let threads = [];
let currentMappings = {};
let originalMappings = {};
let hasChanges = false;

// Initialize the page
document.addEventListener('DOMContentLoaded', function() {
    loadForumData();
});

// Load all forum data
async function loadForumData() {
    showLoading(true);
    hideAlerts();
    
    try {
        // Load categories
        const categoriesResponse = await fetch('/api/categories');
        if (!categoriesResponse.ok) {
            throw new Error(`Failed to load categories: ${categoriesResponse.status}`);
        }
        categories = await categoriesResponse.json();
        
        // Load threads
        const threadsResponse = await fetch('/api/forum_threads');
        if (!threadsResponse.ok) {
            throw new Error(`Failed to load threads: ${threadsResponse.status}`);
        }
        threads = await threadsResponse.json();
        
        // Load current mappings
        const mappingsResponse = await fetch('/api/thread_mappings');
        if (!mappingsResponse.ok) {
            throw new Error(`Failed to load mappings: ${mappingsResponse.status}`);
        }
        currentMappings = await mappingsResponse.json();
        originalMappings = JSON.parse(JSON.stringify(currentMappings)); // Deep copy
        
        // Render the UI
        renderForumInfo();
        renderCategoryMappings();
        renderUnmappedCategories();
        renderThreadsTable();
        
        showLoading(false);
        showForumContent(true);
        
    } catch (error) {
        showLoading(false);
        showError(`Failed to load forum data: ${error.message}`);
        console.error('Error loading forum data:', error);
    }
}

// Show/hide loading indicator
function showLoading(show) {
    const loading = document.getElementById('loading');
    if (show) {
        loading.classList.remove('d-none');
    } else {
        loading.classList.add('d-none');
    }
}

// Show/hide forum content
function showForumContent(show) {
    const content = document.getElementById('forumContent');
    if (show) {
        content.classList.remove('d-none');
    } else {
        content.classList.add('d-none');
    }
}

// Show error alert
function showError(message) {
    const errorAlert = document.getElementById('errorAlert');
    const errorMessage = document.getElementById('errorMessage');
    errorMessage.textContent = message;
    errorAlert.classList.remove('d-none');
    
    // Auto-hide after 10 seconds
    setTimeout(() => {
        errorAlert.classList.add('d-none');
    }, 10000);
}

// Show success alert
function showSuccess(message) {
    const successAlert = document.getElementById('successAlert');
    const successMessage = document.getElementById('successMessage');
    successMessage.textContent = message;
    successAlert.classList.remove('d-none');
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        successAlert.classList.add('d-none');
    }, 5000);
}

// Hide all alerts
function hideAlerts() {
    document.getElementById('errorAlert').classList.add('d-none');
    document.getElementById('successAlert').classList.add('d-none');
}

// Render forum channel information
function renderForumInfo() {
    if (threads.length > 0) {
        // Get forum channel name from first thread (they should all be from same channel)
        const forumName = threads[0].parent_name || 'Unknown Forum';
        document.getElementById('forumChannelName').textContent = forumName;
    }
    
    document.getElementById('totalThreads').textContent = threads.length;
    document.getElementById('mappedCategories').textContent = Object.keys(currentMappings).length;
}

// Render category thread mappings
function renderCategoryMappings() {
    const container = document.getElementById('categoryMappings');
    container.innerHTML = '';
    
    if (categories.length === 0) {
        container.innerHTML = '<p class="text-muted">No categories found.</p>';
        return;
    }
    
    // Create a row for each category
    categories.forEach(category => {
        const row = document.createElement('div');
        row.className = 'row mb-3 align-items-center';
        
        const currentThreadId = currentMappings[category] || '';
        const currentThread = threads.find(t => t.id === currentThreadId);
        
        row.innerHTML = `
            <div class="col-md-3">
                <label class="form-label fw-bold">${escapeHtml(category)}</label>
            </div>
            <div class="col-md-6">
                <select class="form-select thread-select" data-category="${escapeHtml(category)}" onchange="onMappingChange('${escapeHtml(category)}', this.value)">
                    <option value="">Select a thread...</option>
                    ${threads.map(thread => `
                        <option value="${thread.id}" ${thread.id === currentThreadId ? 'selected' : ''}>
                            ${escapeHtml(thread.name)} (${thread.id})
                        </option>
                    `).join('')}
                </select>
            </div>
            <div class="col-md-3">
                <div class="d-flex align-items-center">
                    ${currentThread ? `
                        <span class="badge bg-success me-2">Mapped</span>
                        <small class="text-muted">${escapeHtml(currentThread.name)}</small>
                    ` : `
                        <span class="badge bg-warning">Unmapped</span>
                    `}
                </div>
            </div>
        `;
        
        container.appendChild(row);
    });
}

// Handle mapping change
function onMappingChange(category, threadId) {
    if (threadId === '') {
        delete currentMappings[category];
    } else {
        currentMappings[category] = threadId;
    }
    
    // Check if there are changes
    checkForChanges();
    
    // Update UI elements that depend on mappings
    updateMappingStatus();
    renderUnmappedCategories();
    renderThreadsTable();
}

// Check if there are unsaved changes
function checkForChanges() {
    hasChanges = JSON.stringify(currentMappings) !== JSON.stringify(originalMappings);
    
    // Update save button state
    const saveButton = document.querySelector('button[onclick="saveAllMappings()"]');
    if (hasChanges) {
        saveButton.classList.remove('btn-success');
        saveButton.classList.add('btn-warning');
        saveButton.innerHTML = '<i class="fas fa-save me-1"></i>Save Changes (*)';
    } else {
        saveButton.classList.remove('btn-warning');
        saveButton.classList.add('btn-success');
        saveButton.innerHTML = '<i class="fas fa-save me-1"></i>Save All Changes';
    }
}

// Update mapping status indicators
function updateMappingStatus() {
    document.getElementById('mappedCategories').textContent = Object.keys(currentMappings).length;
    
    // Update individual status badges
    categories.forEach(category => {
        const select = document.querySelector(`select[data-category="${category}"]`);
        if (select) {
            const row = select.closest('.row');
            const statusContainer = row.querySelector('.col-md-3:last-child');
            const currentThreadId = currentMappings[category] || '';
            const currentThread = threads.find(t => t.id === currentThreadId);
            
            if (currentThread) {
                statusContainer.innerHTML = `
                    <div class="d-flex align-items-center">
                        <span class="badge bg-success me-2">Mapped</span>
                        <small class="text-muted">${escapeHtml(currentThread.name)}</small>
                    </div>
                `;
            } else {
                statusContainer.innerHTML = `
                    <div class="d-flex align-items-center">
                        <span class="badge bg-warning">Unmapped</span>
                    </div>
                `;
            }
        }
    });
}

// Render unmapped categories
function renderUnmappedCategories() {
    const container = document.getElementById('unmappedCategories');
    const unmapped = categories.filter(category => !currentMappings[category]);
    
    if (unmapped.length === 0) {
        container.innerHTML = '<span class="text-success"><i class="fas fa-check me-2"></i>All categories are properly mapped.</span>';
    } else {
        container.innerHTML = `
            <div class="alert alert-warning mb-0">
                <strong>The following categories need thread assignments:</strong>
                <ul class="mb-0 mt-2">
                    ${unmapped.map(category => `<li>${escapeHtml(category)}</li>`).join('')}
                </ul>
            </div>
        `;
    }
}

// Render threads table
function renderThreadsTable() {
    const tbody = document.getElementById('threadsTable');
    tbody.innerHTML = '';
    
    if (threads.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">No threads found in the forum channel.</td></tr>';
        return;
    }
    
    threads.forEach(thread => {
        const assignedCategories = Object.entries(currentMappings)
            .filter(([category, threadId]) => threadId === thread.id)
            .map(([category, threadId]) => category);
        
        const isUsed = assignedCategories.length > 0;
        
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>
                <strong>${escapeHtml(thread.name)}</strong>
                ${thread.archived ? '<span class="badge bg-secondary ms-2">Archived</span>' : ''}
            </td>
            <td><code>${thread.id}</code></td>
            <td>
                ${isUsed ? 
                    '<span class="badge bg-success">In Use</span>' : 
                    '<span class="badge bg-light text-dark">Available</span>'
                }
            </td>
            <td>
                ${assignedCategories.length > 0 ? 
                    assignedCategories.map(cat => `<span class="badge bg-primary me-1">${escapeHtml(cat)}</span>`).join('') :
                    '<span class="text-muted">None</span>'
                }
            </td>
        `;
        
        tbody.appendChild(row);
    });
}

// Save all mappings
async function saveAllMappings() {
    if (!hasChanges) {
        showSuccess('No changes to save.');
        return;
    }
    
    hideAlerts();
    
    try {
        const response = await fetch('/api/thread_mappings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(currentMappings)
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || `Server error: ${response.status}`);
        }
        
        // Update original mappings to reflect saved state
        originalMappings = JSON.parse(JSON.stringify(currentMappings));
        hasChanges = false;
        checkForChanges();
        
        showSuccess('Thread mappings saved successfully! The bot will use these new assignments.');
        
    } catch (error) {
        showError(`Failed to save mappings: ${error.message}`);
        console.error('Error saving mappings:', error);
    }
}

// Reset all mappings to original state
function resetAllMappings() {
    if (!hasChanges) {
        showSuccess('No changes to reset.');
        return;
    }
    
    if (confirm('Are you sure you want to reset all changes? This will revert to the last saved state.')) {
        currentMappings = JSON.parse(JSON.stringify(originalMappings));
        hasChanges = false;
        
        // Re-render the UI
        renderCategoryMappings();
        renderUnmappedCategories();
        renderThreadsTable();
        checkForChanges();
        
        showSuccess('Changes have been reset to the last saved state.');
    }
}

// Refresh all data
async function refreshData() {
    showSuccess('Refreshing forum data...');
    await loadForumData();
    showSuccess('Forum data refreshed successfully.');
}

// Utility function to escape HTML
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, function(m) { return map[m]; });
}

// Add CSS for change indicators
const style = document.createElement('style');
style.textContent = `
    .thread-select.changed {
        border-color: #ffc107;
        box-shadow: 0 0 0 0.2rem rgba(255, 193, 7, 0.25);
    }
    
    .btn-warning {
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% {
            box-shadow: 0 0 0 0 rgba(255, 193, 7, 0.7);
        }
        70% {
            box-shadow: 0 0 0 10px rgba(255, 193, 7, 0);
        }
        100% {
            box-shadow: 0 0 0 0 rgba(255, 193, 7, 0);
        }
    }
`;
document.head.appendChild(style);
