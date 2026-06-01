/**
 * GeneRx Portal - Main Application JavaScript
 */

// State management
const state = {
    prescriptions: { 1: [] },
    prescriptionCount: 1,
    maxPrescriptions: 3,
    activeDropdown: null,
    selectedIndex: -1,
    diseaseOk: true,      // does the current disease resolve in Open Targets?
    diseaseOkFor: ''      // the exact input text the diseaseOk flag applies to
};

// DOM Elements
const elements = {
    diseaseInput: document.getElementById('disease'),
    diseaseIdInput: document.getElementById('disease-id-input'),
    diseaseSuggestions: document.getElementById('disease-suggestions'),
    prescriptionsContainer: document.getElementById('prescriptions-container'),
    addPrescriptionBtn: document.getElementById('add-prescription-btn'),
    clearBtn: document.getElementById('clear-btn'),
    runAnalysisBtn: document.getElementById('run-analysis-btn'),
    form: document.getElementById('analysis-form'),
    herbsDataInput: document.getElementById('herbs-data-input'),
    diseaseCount: document.getElementById('disease-count'),
    herbCount: document.getElementById('herb-count'),
    terminologyPanel: document.getElementById('terminology-panel'),
    terminologyStatus: document.getElementById('terminology-status'),
    terminologySummary: document.getElementById('terminology-summary'),
    terminologyInput: document.getElementById('terminology-input'),
    terminologyUmls: document.getElementById('terminology-umls'),
    terminologyOpenTargets: document.getElementById('terminology-opentargets')
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
// Live UMLS -> Open Targets Mapping
// ==========================================

let terminologyRequestId = 0;

// Block unless the current disease text is a CONFIRMED real disease: either
// picked from suggestions (exact ID) or an exact name match. Stops free text
// like "abc" from analyzing a surprise disease via fuzzy search.
function diseaseSelectionBlocked() {
    if (!elements.diseaseInput) return false;
    const val = elements.diseaseInput.value.trim();
    if (!val) return false;                                              // empty handled separately
    if (elements.diseaseIdInput && elements.diseaseIdInput.value) return false; // exact pick -> ok
    return !(state.diseaseOk && state.diseaseOkFor === val);            // ok only if confirmed for THIS text
}

function updateRunButton() {
    if (!elements.runAnalysisBtn) return;
    elements.runAnalysisBtn.classList.toggle('is-disabled', diseaseSelectionBlocked());
}

function setTerminologyStatus(label, className = '') {
    if (!elements.terminologyStatus) return;
    elements.terminologyStatus.textContent = label;
    elements.terminologyStatus.className = `terminology-status ${className}`.trim();
}

function renderTerminologyEmpty(query = '') {
    if (!elements.terminologyPanel) return;
    state.diseaseOk = true;          // no disease yet -> don't block the button
    state.diseaseOkFor = '';
    updateRunButton();
    setTerminologyStatus(query ? 'Waiting' : 'Idle');
    if (elements.terminologySummary) elements.terminologySummary.innerHTML = '';
    elements.terminologyInput.innerHTML = query
        ? `<span class="terminology-chip"><strong>${escapeHtml(query)}</strong></span>`
        : '<span class="terminology-empty">Type a disease, symptom, or clinical phrase</span>';
    elements.terminologyUmls.innerHTML = '<span class="terminology-empty">No concepts loaded</span>';
    elements.terminologyOpenTargets.innerHTML = '<span class="terminology-empty">No candidates loaded</span>';
}

function renderTerminologyLoading(query) {
    if (!elements.terminologyPanel) return;
    setTerminologyStatus('Mapping', 'loading');
    if (elements.terminologySummary) elements.terminologySummary.innerHTML = `Interpreting <strong>&ldquo;${escapeHtml(query)}&rdquo;</strong>&hellip;`;
    elements.terminologyInput.innerHTML = `<span class="terminology-chip"><strong>${escapeHtml(query)}</strong></span>`;
    elements.terminologyUmls.innerHTML = '<span class="terminology-empty">Searching UMLS...</span>';
    elements.terminologyOpenTargets.innerHTML = '<span class="terminology-empty">Waiting for normalized terms</span>';
}

function renderTerminologyMapping(query, payload, openTargetsSuggestions = []) {
    if (!elements.terminologyPanel) return;
    
    const concepts = Array.isArray(payload?.concepts) ? payload.concepts : [];
    const candidates = Array.isArray(openTargetsSuggestions) ? openTargetsSuggestions : [];
    const hasUmls = concepts.length > 0;

    setTerminologyStatus(hasUmls ? 'Live' : 'Fallback', hasUmls ? 'ready' : 'fallback');
    elements.terminologyInput.innerHTML = `<span class="terminology-chip"><strong>${escapeHtml(query)}</strong></span>`;

    // Plain-language summary: "We understood "<input>" as <Disease> (ICD-10 ...)"
    let primaryName = '';
    let primaryMeta = '';
    if (hasUmls) {
        const top = concepts[0];
        primaryName = top.preferred_name || top.name || '';
        const bits = [];
        if (top.icd10) bits.push('ICD-10 ' + top.icd10);
        if (top.root_source) bits.push(top.root_source);
        primaryMeta = bits.join(' · ');
    } else if (candidates.length) {
        const c0 = candidates[0];
        primaryName = typeof c0 === 'string' ? c0 : (c0.name || '');
    }
    if (elements.terminologySummary) {
        const noOt = candidates.length === 0;
        elements.terminologySummary.innerHTML = primaryName
            ? `We understood <strong>&ldquo;${escapeHtml(query)}&rdquo;</strong> as `
              + `<span class="terminology-understood">${escapeHtml(primaryName)}</span>`
              + (primaryMeta ? ` <small>${escapeHtml(primaryMeta)}</small>` : '')
              + (noOt ? ` <small class="terminology-warn">not in Open Targets (no gene data)</small>` : '')
            : `Searching Open Targets for <strong>&ldquo;${escapeHtml(query)}&rdquo;</strong>&hellip;`;
    }

    if (hasUmls) {
        // UMLS chips are read-only CONTEXT (how we interpreted the words). They
        // are NOT selectable, because a UMLS concept may have no Open Targets
        // disease -> no genes. Only Open Targets entries (which resolve to genes)
        // are selectable. Anything analyzable also appears in the Open Targets
        // column, so nothing useful is lost.
        elements.terminologyUmls.innerHTML = concepts.slice(0, 4).map(concept => {
            const name = concept.preferred_name || concept.name || '';
            const icd = concept.icd10 ? `<small>ICD-10 ${escapeHtml(concept.icd10)}</small>` : '';
            const tip = `Standardized term${concept.cui ? ' · ' + concept.cui : ''}`;
            return `
                <span class="terminology-chip umls" title="${escapeHtml(tip)}">
                    <strong>${escapeHtml(name)}</strong>${icd}
                </span>
            `;
        }).join('');
    } else if (payload && payload.umls_available === false) {
        elements.terminologyUmls.innerHTML = '<span class="terminology-empty">UMLS key not configured</span>';
    } else {
        elements.terminologyUmls.innerHTML = '<span class="terminology-empty">No UMLS concept match</span>';
    }

    if (candidates.length > 0) {
        elements.terminologyOpenTargets.innerHTML = candidates.slice(0, 5).map(c => {
            const nm = typeof c === 'string' ? c : (c.name || '');
            const cid = typeof c === 'string' ? '' : (c.id || '');
            return `
                <span class="terminology-chip open-targets selectable" data-disease="${escapeHtml(nm)}" data-id="${escapeHtml(cid)}" title="Click to select this disease">
                    <strong>${escapeHtml(nm)}</strong>
                </span>
            `;
        }).join('');
    } else {
        elements.terminologyOpenTargets.innerHTML = '<span class="terminology-empty">Not in Open Targets &mdash; no disease-gene data for this term. Pick an Open Targets disease (try a more standard name).</span>';
    }
}

function renderTerminologyError(query) {
    if (!elements.terminologyPanel) return;
    setTerminologyStatus('Error', 'fallback');
    if (elements.terminologySummary) elements.terminologySummary.innerHTML = '';
    elements.terminologyInput.innerHTML = `<span class="terminology-chip"><strong>${escapeHtml(query)}</strong></span>`;
    elements.terminologyUmls.innerHTML = '<span class="terminology-empty">UMLS lookup failed</span>';
    elements.terminologyOpenTargets.innerHTML = '<span class="terminology-empty">Using direct Open Targets search</span>';
}

async function fetchTerminologyMapping(query, openTargetsPromise) {
    const requestId = ++terminologyRequestId;
    renderTerminologyLoading(query);
    
    try {
        const [payload, openTargetsSuggestions] = await Promise.all([
            fetch(`/api/translate-symptoms?q=${encodeURIComponent(query)}`).then(r => r.json()),
            openTargetsPromise
        ]);
        
        if (requestId !== terminologyRequestId) return;
        renderTerminologyMapping(query, payload, openTargetsSuggestions);
    } catch (error) {
        console.error('Failed to fetch terminology mapping:', error);
        if (requestId !== terminologyRequestId) return;
        renderTerminologyError(query);
    }
}

// ==========================================
// Disease Autocomplete with Keyboard Navigation
// ==========================================

function setupDiseaseAutocomplete() {
    let debounceTimer;
    let justSelected = false; // Flag to prevent reopening after selection
    const input = elements.diseaseInput;
    const dropdown = elements.diseaseSuggestions;
    renderTerminologyEmpty();
    
    // Helper to handle selection. `id` is the exact Open Targets ID when the
    // pick came from the catalogue; stored so analysis skips name re-resolution.
    function selectDisease(value, id) {
        justSelected = true;
        input.value = value;
        if (elements.diseaseIdInput) elements.diseaseIdInput.value = id || '';
        state.diseaseOk = true;          // picked from Open Targets -> analyzable
        state.diseaseOkFor = value;
        updateRunButton();
        fetchTerminologyMapping(value, fetchSuggestions('/api/diseases', value));
        hideSuggestions(dropdown);
        // Move focus to first herb input after disease selection
        setTimeout(() => {
            const firstHerbInput = document.querySelector('.herb-input');
            if (firstHerbInput) {
                firstHerbInput.focus();
            }
        }, 50);
    }
    
    input.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        justSelected = false; // Reset flag on new input
        if (elements.diseaseIdInput) elements.diseaseIdInput.value = ''; // typing => no exact ID yet
        const query = this.value.trim();
        state.selectedIndex = -1;

        if (query.length < 1) {
            hideSuggestions(dropdown);
            renderTerminologyEmpty();   // resets diseaseOk + button
            return;
        }

        // Unconfirmed until the user picks a suggestion OR the text exactly
        // matches one. Prevents free text like "abc" from analyzing a surprise
        // disease via Open Targets' fuzzy search.
        state.diseaseOk = false;
        state.diseaseOkFor = query;
        updateRunButton();

        debounceTimer = setTimeout(async () => {
            const suggestionsPromise = fetchSuggestions('/api/diseases', query);
            fetchTerminologyMapping(query, suggestionsPromise);
            const suggestions = await suggestionsPromise;
            state.activeDropdown = dropdown;
            showSuggestionsWithKeyboard(dropdown, suggestions, query, selectDisease);

            // Auto-confirm if the typed text is an exact disease name.
            if (input.value.trim() === query) {
                const exact = suggestions.find(s => {
                    const n = (s && typeof s === 'object') ? s.name : s;
                    return (n || '').toLowerCase() === query.toLowerCase();
                });
                if (exact) {
                    state.diseaseOk = true;
                    state.diseaseOkFor = query;
                    if (elements.diseaseIdInput) {
                        elements.diseaseIdInput.value = (exact && typeof exact === 'object') ? (exact.id || '') : '';
                    }
                    updateRunButton();
                }
            }
        }, 150);
    });
    
    input.addEventListener('keydown', function(e) {
        handleKeyboardNavigation(e, dropdown, selectDisease);
    });
    
    input.addEventListener('focus', function() {
        // Don't reopen if we just selected something
        if (justSelected) {
            justSelected = false;
            return;
        }
        if (this.value.length >= 1 && dropdown.style.display !== 'block') {
            this.dispatchEvent(new Event('input'));
        }
    });
    
    // Click a UMLS / Open Targets chip in the Terminology panel to use it as the disease
    if (elements.terminologyPanel) {
        elements.terminologyPanel.addEventListener('click', function(e) {
            const chip = e.target.closest('.terminology-chip.selectable[data-disease]');
            if (chip && chip.dataset.disease) {
                selectDisease(chip.dataset.disease, chip.dataset.id || '');
            }
        });
    }

    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
        if (!input.contains(e.target) && !dropdown.contains(e.target)) {
            hideSuggestions(dropdown);
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
            
            // Filter out already selected herbs (check english name)
            const selectedHerbs = state.prescriptions[prescriptionIndex] || [];
            suggestions = suggestions.filter(s => {
                const englishName = typeof s === 'object' ? s.english : s;
                return !selectedHerbs.includes(englishName);
            });
            
            state.activeDropdown = dropdown;
            showSuggestionsWithKeyboard(dropdown, suggestions, query, (value, koreanName) => {
                // Cache the Korean name from the suggestion
                const suggestionItem = dropdown.querySelector(`[data-value="${value}"]`);
                const korean = suggestionItem ? suggestionItem.dataset.korean : null;
                if (korean) herbKoreanCache[value] = korean;
                
                addHerbTagInline(prescriptionIndex, value, tagsContainer, input, korean);
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
            // Get Korean name from the selected item
            const items = dropdown.querySelectorAll('.suggestion-item');
            const selectedItem = items[state.selectedIndex];
            const korean = selectedItem ? selectedItem.dataset.korean : null;
            if (korean) herbKoreanCache[value] = korean;
            
            addHerbTagInline(prescriptionIndex, value, tagsContainer, input, korean);
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
            const chosen = items[state.selectedIndex];
            onSelect(chosen.dataset.value, chosen.dataset.id || '');
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
    
    // Detect suggestion shape: herb objects {english/korean}, disease objects
    // {name,id}, or legacy plain strings.
    const first = suggestions[0];
    const isHerbSuggestion = typeof first === 'object' && first && first.english;
    const isDiseaseObject = typeof first === 'object' && first && !first.english && 'name' in first;

    // Add count header for better UX
    const countHeader = `<div class="suggestions-count"><i class="fas fa-search"></i> Found ${suggestions.length} matching result${suggestions.length !== 1 ? 's' : ''}</div>`;

    let itemsHtml;
    if (isHerbSuggestion) {
        // Bilingual herb display: Korean (English)
        itemsHtml = suggestions.map((s, i) => {
            const displayText = s.korean ? `${s.korean} (${s.english})` : s.english;
            const highlightedText = s.korean ?
                `${highlightMatch(s.korean, query)} <span class="herb-english">(${highlightMatch(s.english, query)})</span>` :
                highlightMatch(s.english, query);
            return `<div class="suggestion-item${i === 0 ? ' active' : ''}" data-value="${escapeHtml(s.english)}" data-korean="${escapeHtml(s.korean || '')}">${highlightedText}</div>`;
        }).join('');
    } else if (isDiseaseObject) {
        // Disease suggestions: name + Open Targets ID badge
        itemsHtml = suggestions.map((s, i) => {
            const idBadge = s.id ? `<span class="suggestion-id">${escapeHtml(s.id)}</span>` : '';
            return `<div class="suggestion-item${i === 0 ? ' active' : ''}" data-value="${escapeHtml(s.name)}" data-id="${escapeHtml(s.id || '')}">${highlightMatch(s.name, query)}${idBadge}</div>`;
        }).join('');
    } else {
        // Legacy plain-string suggestions
        itemsHtml = suggestions.map((s, i) =>
            `<div class="suggestion-item${i === 0 ? ' active' : ''}" data-value="${escapeHtml(s)}">${highlightMatch(s, query)}</div>`
        ).join('');
    }

    container.innerHTML = countHeader + itemsHtml;
    container.style.display = 'block';

    // Add click and hover handlers
    container.querySelectorAll('.suggestion-item').forEach((item, index) => {
        item.addEventListener('click', () => {
            onSelect(item.dataset.value, item.dataset.id || '');
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
// Herb Name Cache for Korean Display
// ==========================================

// Cache Korean names to avoid repeated API calls
const herbKoreanCache = {};

async function getKoreanName(englishName) {
    if (herbKoreanCache[englishName] !== undefined) {
        return herbKoreanCache[englishName];
    }
    try {
        const response = await fetch(`/api/herbs/validate?name=${encodeURIComponent(englishName)}`);
        const data = await response.json();
        herbKoreanCache[englishName] = data.korean || '';
        return herbKoreanCache[englishName];
    } catch {
        return '';
    }
}

// ==========================================
// Inline Herb Tags Management
// ==========================================

async function addHerbTagInline(prescriptionIndex, herbName, tagsContainer, input, koreanName = null) {
    if (!state.prescriptions[prescriptionIndex]) {
        state.prescriptions[prescriptionIndex] = [];
    }
    
    if (state.prescriptions[prescriptionIndex].includes(herbName)) {
        return;
    }
    
    state.prescriptions[prescriptionIndex].push(herbName);
    
    // Get Korean name if not provided
    if (koreanName === null) {
        koreanName = await getKoreanName(herbName);
    }
    
    const tag = document.createElement('span');
    tag.className = 'herb-tag';
    tag.dataset.herb = herbName;
    
    // Display Korean name with English in parentheses, or just English if no Korean
    const displayName = koreanName ? `${koreanName} (${herbName})` : herbName;
    tag.innerHTML = `
        ${escapeHtml(displayName)}
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
// Bulk Herb Adding (Paste Support with Korean)
// ==========================================

async function addBulkHerbs(prescriptionIndex, herbs, tagsContainer, input) {
    const validHerbs = [];
    const invalidHerbs = [];
    const duplicateHerbs = [];
    
    // Show loading toast
    showToast('Validating herbs...', 'info');
    
    for (const herb of herbs) {
        // Validate against database (works for both Korean and English input)
        const validated = await validateHerb(herb);
        
        if (validated) {
            // Check if already added (by English name)
            if (state.prescriptions[prescriptionIndex]?.includes(validated.english)) {
                duplicateHerbs.push(herb);
                continue;
            }
            validHerbs.push(validated);
        } else {
            invalidHerbs.push(herb);
        }
    }
    
    // Add valid herbs as tags (with Korean names from validation)
    for (const herbData of validHerbs) {
        const englishName = typeof herbData === 'object' ? herbData.english : herbData;
        const koreanName = typeof herbData === 'object' ? herbData.korean : null;
        await addHerbTagInline(prescriptionIndex, englishName, tagsContainer, input, koreanName);
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
        if (data.valid) {
            // Cache the Korean name
            if (data.korean) herbKoreanCache[data.english || data.name] = data.korean;
            // Return object with both names
            return { english: data.english || data.name, korean: data.korean || '' };
        }
        return null;
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

    if (diseaseSelectionBlocked()) {
        showToast(`Please pick a disease from the suggestions list so we analyze the exact one you mean. Free text like "${elements.diseaseInput.value.trim()}" isn't a confirmed disease.`, 'error', 6000);
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
