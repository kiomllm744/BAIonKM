/**
 * GeneRx Portal - Main Application JavaScript
 */

// State management
const state = {
    prescriptions: { 1: [] },
    prescriptionCount: 1,
    maxPrescriptions: 3,
    activeDropdown: null,
    selectedIndex: -1
};

// DOM Elements
const elements = {
    diseaseInput: document.getElementById('disease'),
    diseaseSuggestions: document.getElementById('disease-suggestions'),
    prescriptionsContainer: document.getElementById('prescriptions-container'),
    addPrescriptionBtn: document.getElementById('add-prescription-btn'),
    clearBtn: document.getElementById('clear-btn'),
    form: document.getElementById('analysis-form'),
    herbsDataInput: document.getElementById('herbs-data-input'),
    diseaseCount: document.getElementById('disease-count'),
    herbCount: document.getElementById('herb-count')
};

// ==========================================
// Initialization
// ==========================================

document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

function initializeApp() {
    loadStats();
    setupDiseaseAutocomplete();
    document.querySelectorAll('.herb-input').forEach(setupHerbAutocomplete);
    setupEventListeners();
    
    // Click on container focuses the input
    document.querySelectorAll('.tags-input-container').forEach(container => {
        container.addEventListener('click', () => {
            container.querySelector('.tags-input')?.focus();
        });
    });
}

// ==========================================
// Stats Loading
// ==========================================

async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        const stats = await response.json();
        
        if (elements.diseaseCount) {
            elements.diseaseCount.textContent = formatNumber(stats.diseases);
        }
        if (elements.herbCount) {
            elements.herbCount.textContent = formatNumber(stats.herbs);
        }
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

function formatNumber(num) {
    if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

// ==========================================
// Disease Autocomplete with Keyboard Navigation
// ==========================================

function setupDiseaseAutocomplete() {
    let debounceTimer;
    const input = elements.diseaseInput;
    const dropdown = elements.diseaseSuggestions;
    
    input.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        const query = this.value.trim();
        state.selectedIndex = -1;
        
        if (query.length < 1) {
            hideSuggestions(dropdown);
            return;
        }
        
        debounceTimer = setTimeout(async () => {
            const suggestions = await fetchSuggestions('/api/diseases', query);
            state.activeDropdown = dropdown;
            showSuggestionsWithKeyboard(dropdown, suggestions, query, (value) => {
                input.value = value;
                hideSuggestions(dropdown);
            });
        }, 150);
    });
    
    input.addEventListener('keydown', function(e) {
        handleKeyboardNavigation(e, dropdown, (value) => {
            input.value = value;
            hideSuggestions(dropdown);
        });
    });
    
    input.addEventListener('focus', function() {
        if (this.value.length >= 1) {
            this.dispatchEvent(new Event('input'));
        }
    });
}

// ==========================================
// Herb Autocomplete with Tags in Same Input
// ==========================================

function setupHerbAutocomplete(input) {
    const container = input.closest('.autocomplete-wrapper');
    const dropdown = container.querySelector('.herb-suggestions');
    const tagsContainer = input.closest('.tags-input-container');
    const prescriptionIndex = parseInt(input.dataset.index);
    let debounceTimer;
    
    // Handle paste event for bulk adding herbs
    input.addEventListener('paste', async function(e) {
        e.preventDefault();
        const pastedText = (e.clipboardData || window.clipboardData).getData('text');
        
        // Check if it contains commas (bulk paste)
        if (pastedText.includes(',')) {
            const herbs = pastedText.split(',').map(h => h.trim()).filter(h => h.length > 0);
            await addBulkHerbs(prescriptionIndex, herbs, tagsContainer, input);
        } else {
            // Single word paste, just insert normally
            const start = this.selectionStart;
            const end = this.selectionEnd;
            const text = this.value;
            this.value = text.substring(0, start) + pastedText + text.substring(end);
            this.selectionStart = this.selectionEnd = start + pastedText.length;
            this.dispatchEvent(new Event('input'));
        }
    });
    
    input.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        const query = this.value.trim();
        state.selectedIndex = -1;
        
        if (query.length < 1) {
            hideSuggestions(dropdown);
            return;
        }
        
        debounceTimer = setTimeout(async () => {
            let suggestions = await fetchSuggestions('/api/herbs', query);
            
            // Filter out already selected herbs
            const selectedHerbs = state.prescriptions[prescriptionIndex] || [];
            suggestions = suggestions.filter(s => !selectedHerbs.includes(s));
            
            state.activeDropdown = dropdown;
            showSuggestionsWithKeyboard(dropdown, suggestions, query, (value) => {
                addHerbTagInline(prescriptionIndex, value, tagsContainer, input);
                input.value = '';
                hideSuggestions(dropdown);
                input.focus();
            });
        }, 100);
    });
    
    input.addEventListener('keydown', function(e) {
        // Handle backspace to remove last tag
        if (e.key === 'Backspace' && this.value === '') {
            const herbs = state.prescriptions[prescriptionIndex];
            if (herbs && herbs.length > 0) {
                const lastHerb = herbs[herbs.length - 1];
                removeHerbTagInline(prescriptionIndex, lastHerb, tagsContainer);
            }
            return;
        }
        
        handleKeyboardNavigation(e, dropdown, (value) => {
            addHerbTagInline(prescriptionIndex, value, tagsContainer, input);
            input.value = '';
            hideSuggestions(dropdown);
            input.focus();
        });
    });
}

// ==========================================
// Keyboard Navigation Handler
// ==========================================

function handleKeyboardNavigation(e, dropdown, onSelect) {
    const items = dropdown.querySelectorAll('.suggestion-item');
    
    if (items.length === 0) return;
    
    if (e.key === 'ArrowDown') {
        e.preventDefault();
        state.selectedIndex = Math.min(state.selectedIndex + 1, items.length - 1);
        updateSelectedItem(items);
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        state.selectedIndex = Math.max(state.selectedIndex - 1, 0);
        updateSelectedItem(items);
    } else if (e.key === 'Enter') {
        e.preventDefault();
        if (state.selectedIndex >= 0 && items[state.selectedIndex]) {
            onSelect(items[state.selectedIndex].dataset.value);
            state.selectedIndex = -1;
        }
    } else if (e.key === 'Escape') {
        hideSuggestions(dropdown);
        state.selectedIndex = -1;
    }
}

function updateSelectedItem(items) {
    items.forEach((item, index) => {
        if (index === state.selectedIndex) {
            item.classList.add('active');
            item.scrollIntoView({ block: 'nearest' });
        } else {
            item.classList.remove('active');
        }
    });
}

// ==========================================
// Suggestions Display
// ==========================================

async function fetchSuggestions(endpoint, query) {
    try {
        const response = await fetch(`${endpoint}?q=${encodeURIComponent(query)}`);
        return await response.json();
    } catch (error) {
        console.error('Failed to fetch suggestions:', error);
        return [];
    }
}

function showSuggestionsWithKeyboard(container, suggestions, query, onSelect) {
    if (suggestions.length === 0) {
        hideSuggestions(container);
        return;
    }
    
    state.selectedIndex = 0; // Auto-select first item
    
    // Add count header for better UX
    const countHeader = `<div class="suggestions-count"><i class="fas fa-search"></i> Found ${suggestions.length} matching result${suggestions.length !== 1 ? 's' : ''}</div>`;
    
    container.innerHTML = countHeader + suggestions.map((s, i) => 
        `<div class="suggestion-item${i === 0 ? ' active' : ''}" data-value="${escapeHtml(s)}">${highlightMatch(s, query)}</div>`
    ).join('');
    
    container.style.display = 'block';
    
    // Add click and hover handlers
    container.querySelectorAll('.suggestion-item').forEach((item, index) => {
        item.addEventListener('click', () => {
            onSelect(item.dataset.value);
        });
        
        item.addEventListener('mouseenter', () => {
            state.selectedIndex = index;
            updateSelectedItem(container.querySelectorAll('.suggestion-item'));
        });
    });
}

function hideSuggestions(container) {
    container.style.display = 'none';
    container.innerHTML = '';
    state.selectedIndex = -1;
}

// ==========================================
// Inline Herb Tags Management
// ==========================================

function addHerbTagInline(prescriptionIndex, herbName, tagsContainer, input) {
    if (!state.prescriptions[prescriptionIndex]) {
        state.prescriptions[prescriptionIndex] = [];
    }
    
    if (state.prescriptions[prescriptionIndex].includes(herbName)) {
        return;
    }
    
    state.prescriptions[prescriptionIndex].push(herbName);
    
    const tag = document.createElement('span');
    tag.className = 'herb-tag';
    tag.dataset.herb = herbName;
    tag.innerHTML = `
        ${escapeHtml(herbName)}
        <span class="remove-tag" title="Remove">&times;</span>
    `;
    
    tag.querySelector('.remove-tag').addEventListener('click', (e) => {
        e.stopPropagation();
        removeHerbTagInline(prescriptionIndex, herbName, tagsContainer);
    });
    
    // Insert tag before the input
    tagsContainer.insertBefore(tag, input);
    
    // Update placeholder
    updatePlaceholder(prescriptionIndex, input);
}

function removeHerbTagInline(prescriptionIndex, herbName, tagsContainer) {
    state.prescriptions[prescriptionIndex] = state.prescriptions[prescriptionIndex].filter(h => h !== herbName);
    
    const tag = tagsContainer.querySelector(`.herb-tag[data-herb="${herbName}"]`);
    if (tag) {
        tag.remove();
    }
    
    // Update placeholder
    const input = tagsContainer.querySelector('.tags-input');
    updatePlaceholder(prescriptionIndex, input);
}

function updatePlaceholder(prescriptionIndex, input) {
    const herbs = state.prescriptions[prescriptionIndex] || [];
    input.placeholder = herbs.length > 0 ? 'Add more herbs...' : 'Type herb name or paste list...';
}

// ==========================================
// Bulk Herb Adding (Paste Support)
// ==========================================

async function addBulkHerbs(prescriptionIndex, herbs, tagsContainer, input) {
    const validHerbs = [];
    const invalidHerbs = [];
    const duplicateHerbs = [];
    
    // Show loading toast
    showToast('Validating herbs...', 'info');
    
    for (const herb of herbs) {
        // Check if already added
        if (state.prescriptions[prescriptionIndex]?.includes(herb)) {
            duplicateHerbs.push(herb);
            continue;
        }
        
        // Validate against database
        const isValid = await validateHerb(herb);
        if (isValid) {
            validHerbs.push(isValid); // Use the exact name from database
        } else {
            invalidHerbs.push(herb);
        }
    }
    
    // Add valid herbs as tags
    for (const herb of validHerbs) {
        addHerbTagInline(prescriptionIndex, herb, tagsContainer, input);
    }
    
    // Show results
    if (validHerbs.length > 0) {
        showToast(`Added ${validHerbs.length} herb${validHerbs.length > 1 ? 's' : ''} successfully`, 'success');
    }
    
    if (invalidHerbs.length > 0) {
        showToast(`Not found in database: ${invalidHerbs.join(', ')}`, 'error', 5000);
    }
    
    if (duplicateHerbs.length > 0) {
        showToast(`Already added: ${duplicateHerbs.join(', ')}`, 'warning');
    }
    
    input.value = '';
    input.focus();
}

async function validateHerb(herbName) {
    try {
        const response = await fetch(`/api/herbs/validate?name=${encodeURIComponent(herbName)}`);
        const data = await response.json();
        return data.valid ? data.name : null;
    } catch (error) {
        console.error('Error validating herb:', error);
        return null;
    }
}

// ==========================================
// Prescription Management
// ==========================================

function addPrescription() {
    if (state.prescriptionCount >= state.maxPrescriptions) {
        showToast('Maximum 3 prescriptions allowed', 'warning');
        return;
    }
    
    state.prescriptionCount++;
    const index = state.prescriptionCount;
    state.prescriptions[index] = [];
    
    const prescriptionCard = document.createElement('div');
    prescriptionCard.className = 'prescription-card';
    prescriptionCard.dataset.index = index;
    prescriptionCard.innerHTML = `
        <div class="prescription-header">
            <span class="prescription-badge">Rx ${index}</span>
            <button type="button" class="btn-icon remove-prescription" title="Remove prescription">
                <i class="fas fa-times"></i>
            </button>
        </div>
        <div class="prescription-body">
            <div class="autocomplete-wrapper">
                <div class="tags-input-container" id="tags-container-${index}">
                    <input 
                        type="text" 
                        class="tags-input herb-input" 
                        data-index="${index}"
                        placeholder="Type herb name..." 
                        autocomplete="off"
                    >
                </div>
                <div class="suggestions-dropdown herb-suggestions"></div>
            </div>
        </div>
    `;
    
    elements.prescriptionsContainer.appendChild(prescriptionCard);
    
    // Setup autocomplete for new input
    const newInput = prescriptionCard.querySelector('.herb-input');
    setupHerbAutocomplete(newInput);
    
    // Click on container focuses input
    const tagsContainer = prescriptionCard.querySelector('.tags-input-container');
    tagsContainer.addEventListener('click', () => newInput.focus());
    
    // Setup remove button
    prescriptionCard.querySelector('.remove-prescription').addEventListener('click', () => {
        removePrescription(index, prescriptionCard);
    });
    
    updateRemoveButtonsVisibility();
    newInput.focus();
}

function removePrescription(index, element) {
    if (state.prescriptionCount <= 1) {
        showToast('At least one prescription is required', 'warning');
        return;
    }
    
    delete state.prescriptions[index];
    element.remove();
    state.prescriptionCount--;
    
    renumberPrescriptions();
    updateRemoveButtonsVisibility();
}

function renumberPrescriptions() {
    const cards = elements.prescriptionsContainer.querySelectorAll('.prescription-card');
    const newPrescriptions = {};
    
    cards.forEach((card, i) => {
        const newIndex = i + 1;
        const oldIndex = parseInt(card.dataset.index);
        
        newPrescriptions[newIndex] = state.prescriptions[oldIndex] || [];
        
        card.dataset.index = newIndex;
        card.querySelector('.prescription-badge').textContent = `Rx ${newIndex}`;
        card.querySelector('.herb-input').dataset.index = newIndex;
        card.querySelector('.tags-input-container').id = `tags-container-${newIndex}`;
    });
    
    state.prescriptions = newPrescriptions;
    state.prescriptionCount = cards.length;
}

function updateRemoveButtonsVisibility() {
    const cards = elements.prescriptionsContainer.querySelectorAll('.prescription-card');
    cards.forEach(card => {
        const removeBtn = card.querySelector('.remove-prescription');
        if (removeBtn) {
            removeBtn.style.display = cards.length > 1 ? 'flex' : 'none';
        }
    });
}

// ==========================================
// Form Handling
// ==========================================

function clearForm() {
    elements.diseaseInput.value = '';
    
    // Clear all herbs
    Object.keys(state.prescriptions).forEach(index => {
        const tagsContainer = document.getElementById(`tags-container-${index}`);
        if (tagsContainer) {
            tagsContainer.querySelectorAll('.herb-tag').forEach(tag => tag.remove());
        }
        state.prescriptions[index] = [];
    });
    
    // Remove extra prescriptions
    while (state.prescriptionCount > 1) {
        const lastCard = elements.prescriptionsContainer.lastElementChild;
        delete state.prescriptions[state.prescriptionCount];
        lastCard.remove();
        state.prescriptionCount--;
    }
    
    // Reset placeholder
    const firstInput = document.querySelector('.herb-input[data-index="1"]');
    if (firstInput) {
        firstInput.placeholder = 'Type herb name...';
    }
    
    updateRemoveButtonsVisibility();
    elements.diseaseInput.focus();
}

function handleFormSubmit(e) {
    e.preventDefault();
    
    if (!elements.diseaseInput.value.trim()) {
        showToast('Please enter a disease name', 'error');
        elements.diseaseInput.focus();
        return;
    }
    
    const herbsData = [];
    let hasHerbs = false;
    
    for (let i = 1; i <= state.prescriptionCount; i++) {
        const herbs = state.prescriptions[i] || [];
        if (herbs.length > 0) {
            hasHerbs = true;
            herbsData.push(herbs.join(', '));
        }
    }
    
    if (!hasHerbs) {
        showToast('Please add at least one herb to a prescription', 'error');
        return;
    }
    
    elements.herbsDataInput.value = JSON.stringify(herbsData);
    
    const submitBtn = elements.form.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<span class="spinner"></span> Analyzing...';
    submitBtn.disabled = true;
    
    elements.form.submit();
}

// ==========================================
// Event Listeners Setup
// ==========================================

function setupEventListeners() {
    if (elements.addPrescriptionBtn) {
        elements.addPrescriptionBtn.addEventListener('click', addPrescription);
    }
    
    if (elements.clearBtn) {
        elements.clearBtn.addEventListener('click', clearForm);
    }
    
    if (elements.form) {
        elements.form.addEventListener('submit', handleFormSubmit);
    }
    
    // Hide suggestions on outside click
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.autocomplete-wrapper')) {
            document.querySelectorAll('.suggestions-dropdown').forEach(dropdown => {
                hideSuggestions(dropdown);
            });
        }
    });
}

// ==========================================
// Utility Functions
// ==========================================

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function highlightMatch(text, query) {
    if (!query) return escapeHtml(text);
    
    // Escape special regex characters in query
    const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`(${escapedQuery})`, 'gi');
    
    // Split by matches and rebuild with highlights
    const parts = text.split(regex);
    
    return parts.map(part => {
        if (part.toLowerCase() === query.toLowerCase()) {
            return `<mark class="highlight">${escapeHtml(part)}</mark>`;
        }
        return escapeHtml(part);
    }).join('');
}

function showToast(message, type = 'info', duration = 3000) {
    // Remove existing toasts of same type to avoid stacking
    document.querySelectorAll(`.toast.toast-${type}`).forEach(t => t.remove());
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    const icons = {
        error: 'exclamation-circle',
        warning: 'exclamation-triangle',
        success: 'check-circle',
        info: 'info-circle'
    };
    
    toast.innerHTML = `
        <i class="fas fa-${icons[type] || 'info-circle'}"></i>
        <span>${escapeHtml(message)}</span>
        <button class="toast-close">&times;</button>
    `;
    
    if (!document.querySelector('#toast-styles')) {
        const style = document.createElement('style');
        style.id = 'toast-styles';
        style.textContent = `
            .toast {
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 16px 24px;
                background: white;
                border-radius: 10px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                display: flex;
                align-items: center;
                gap: 12px;
                z-index: 9999;
                animation: slideIn 0.3s ease;
                max-width: 400px;
            }
            .toast-error { border-left: 4px solid #ef4444; }
            .toast-warning { border-left: 4px solid #f59e0b; }
            .toast-success { border-left: 4px solid #10b981; }
            .toast-info { border-left: 4px solid #6366f1; }
            .toast i { font-size: 1.25rem; flex-shrink: 0; }
            .toast-error i { color: #ef4444; }
            .toast-warning i { color: #f59e0b; }
            .toast-success i { color: #10b981; }
            .toast-info i { color: #6366f1; }
            .toast span { flex: 1; word-break: break-word; }
            .toast-close {
                background: none;
                border: none;
                font-size: 1.25rem;
                cursor: pointer;
                color: #999;
                padding: 0;
                margin-left: 8px;
            }
            .toast-close:hover { color: #333; }
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
        `;
        document.head.appendChild(style);
    }
    
    document.body.appendChild(toast);
    
    // Close button handler
    toast.querySelector('.toast-close').addEventListener('click', () => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    });
    
    // Auto remove after duration
    setTimeout(() => {
        if (toast.parentNode) {
            toast.style.animation = 'slideIn 0.3s ease reverse';
            setTimeout(() => toast.remove(), 300);
        }
    }, duration);
}
