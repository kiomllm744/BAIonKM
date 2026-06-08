/**
 * BAIonKM - Main Application JavaScript
 */

// State management
const state = {
    prescriptions: { 1: [], 2: [] },
    prescriptionCount: 2,
    maxPrescriptions: 2,
    activeDropdown: null,
    selectedIndex: -1,
    selectedDiseases: [], // chosen diseases [{name, id}], up to maxDiseases
    maxDiseases: 3,
    diseaseOk: true,      // (legacy) per-input confirmation flag
    diseaseOkFor: ''
};

// DOM Elements
const elements = {
    diseaseInput: document.getElementById('disease'),
    diseaseIdInput: document.getElementById('disease-id-input'),
    diseasesDataInput: document.getElementById('diseases-data-input'),
    diseaseChips: document.getElementById('disease-chips'),
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
    loadProvenance();
    setupDiseaseAutocomplete();
    document.querySelectorAll('.herb-input').forEach(setupHerbAutocomplete);
    setupEventListeners();
    relabelPrescriptions();

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

async function loadProvenance() {
    const bar = document.getElementById('provenance-bar');
    if (!bar) return;
    try {
        const p = await (await fetch('/api/provenance')).json();
        const cat = p.disease_catalogue || {};
        const herbs = (p.herb_db && p.herb_db.herbs) || '—';
        const parts = [
            `<span class="provenance-title">Data</span>`,
            `Open Targets <b>${p.open_targets_live || '—'}</b>`,
            `${cat.count || '—'} diseases`,
            `${p.herb_db ? p.herb_db.name : 'BATMAN-TCM'} <b>${herbs}</b> herbs`,
            `UMLS · Enrichr/${(p.enrichment || '').split('/').pop().trim() || 'DisGeNET'}`
        ];
        if (p.stale) parts.push(`<span class="prov-warn">disease catalogue outdated — rebuild the index</span>`);
        bar.innerHTML = parts.join('<span class="prov-sep">·</span>');
    } catch (e) {
        bar.innerHTML = '';
    }
}

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

// Run is blocked until at least one real disease has been added (picked from
// suggestions). This also stops free text like "abc" from being analysed.
function diseaseSelectionBlocked() {
    return state.selectedDiseases.length === 0;
}

function updateRunButton() {
    if (!elements.runAnalysisBtn) return;
    elements.runAnalysisBtn.classList.toggle('is-disabled', diseaseSelectionBlocked());
}

// --- Selected-disease chips (1..maxDiseases) ---
function syncDiseasesField() {
    if (elements.diseasesDataInput) {
        elements.diseasesDataInput.value = JSON.stringify(state.selectedDiseases);
    }
}

function renderDiseaseChips() {
    const c = elements.diseaseChips;
    if (!c) return;
    c.innerHTML = state.selectedDiseases.map((d, i) => `
        <span class="disease-chip">
            <strong>${escapeHtml(d.name)}</strong>${d.id ? `<small>${escapeHtml(d.id)}</small>` : ''}
            <button type="button" class="disease-chip-remove" data-index="${i}" title="${i18n.t('common.remove')}" aria-label="${i18n.t('common.remove')}">&times;</button>
        </span>
    `).join('');
    c.querySelectorAll('.disease-chip-remove').forEach(btn => {
        btn.addEventListener('click', () => removeDisease(parseInt(btn.dataset.index, 10)));
    });
}

function addDisease(name, id) {
    name = (name || '').trim();
    if (!name) return;
    if (state.selectedDiseases.some(d => d.name.toLowerCase() === name.toLowerCase())) return; // de-dupe
    if (state.selectedDiseases.length >= state.maxDiseases) {
        showToast(i18n.t('toast.maxDiseases', { n: state.maxDiseases }), 'error');
        return;
    }
    state.selectedDiseases.push({ name: name, id: id || '' });
    renderDiseaseChips();
    syncDiseasesField();
    updateRunButton();
}

function removeDisease(index) {
    state.selectedDiseases.splice(index, 1);
    renderDiseaseChips();
    syncDiseasesField();
    updateRunButton();
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
    setTerminologyStatus(query ? i18n.t('term.status.waiting') : i18n.t('term.status.idle'));
    if (elements.terminologySummary) elements.terminologySummary.innerHTML = '';
    elements.terminologyInput.innerHTML = query
        ? `<span class="terminology-chip"><strong>${escapeHtml(query)}</strong></span>`
        : `<span class="terminology-empty">${i18n.t('term.inputHint')}</span>`;
    elements.terminologyUmls.innerHTML = `<span class="terminology-empty">${i18n.t('term.umlsEmpty')}</span>`;
    elements.terminologyOpenTargets.innerHTML = `<span class="terminology-empty">${i18n.t('term.otEmpty')}</span>`;
}

function renderTerminologyLoading(query) {
    if (!elements.terminologyPanel) return;
    setTerminologyStatus(i18n.t('term.status.mapping'), 'loading');
    if (elements.terminologySummary) elements.terminologySummary.innerHTML = i18n.t('term.interpreting', { q: `<strong>&ldquo;${escapeHtml(query)}&rdquo;</strong>` });
    elements.terminologyInput.innerHTML = `<span class="terminology-chip"><strong>${escapeHtml(query)}</strong></span>`;
    elements.terminologyUmls.innerHTML = `<span class="terminology-empty">${i18n.t('term.searchingUmls')}</span>`;
    elements.terminologyOpenTargets.innerHTML = `<span class="terminology-empty">${i18n.t('term.waitingTerms')}</span>`;
}

function renderTerminologyMapping(query, payload, openTargetsSuggestions = []) {
    if (!elements.terminologyPanel) return;
    
    const concepts = Array.isArray(payload?.concepts) ? payload.concepts : [];
    const candidates = Array.isArray(openTargetsSuggestions) ? openTargetsSuggestions : [];
    const hasUmls = concepts.length > 0;

    setTerminologyStatus(hasUmls ? i18n.t('term.status.live') : i18n.t('term.status.fallback'), hasUmls ? 'ready' : 'fallback');
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
        const styledQuery = `<strong>&ldquo;${escapeHtml(query)}&rdquo;</strong>`;
        const understoodRest = `<span class="terminology-understood">${escapeHtml(primaryName)}</span>`
            + (primaryMeta ? ` <small>${escapeHtml(primaryMeta)}</small>` : '')
            + (noOt ? ` <small class="terminology-warn">${i18n.t('term.notInOt')}</small>` : '');
        elements.terminologySummary.innerHTML = primaryName
            ? i18n.t('term.understoodAs', { q: styledQuery, rest: understoodRest })
            : i18n.t('term.searchingOt', { q: styledQuery });
    }

    if (hasUmls) {
        // UMLS chips are read-only CONTEXT (how we interpreted the words). They
        // are NOT selectable, because a UMLS concept may have no Open Targets
        // disease -> no genes. Only Open Targets entries (which resolve to genes)
        // are selectable. Anything analyzable also appears in the Open Targets
        // column, so nothing useful is lost.
        elements.terminologyUmls.innerHTML = concepts.slice(0, 6).map(concept => {
            const name = concept.preferred_name || concept.name || '';
            const icd = concept.icd10 ? `<small>ICD-10 ${escapeHtml(concept.icd10)}</small>` : '';
            const tip = i18n.t('term.standardizedTerm') + (concept.cui ? ' · ' + concept.cui : '');
            return `
                <span class="terminology-chip umls" title="${escapeHtml(tip)}">
                    <strong>${escapeHtml(name)}</strong>${icd}
                </span>
            `;
        }).join('');
    } else if (payload && payload.umls_available === false) {
        elements.terminologyUmls.innerHTML = `<span class="terminology-empty">${i18n.t('term.umlsKeyMissing')}</span>`;
    } else {
        elements.terminologyUmls.innerHTML = `<span class="terminology-empty">${i18n.t('term.noUmlsMatch')}</span>`;
    }

    if (candidates.length > 0) {
        elements.terminologyOpenTargets.innerHTML = candidates.slice(0, 10).map(c => {
            const nm = typeof c === 'string' ? c : (c.name || '');
            const cid = typeof c === 'string' ? '' : (c.id || '');
            return `
                <span class="terminology-chip open-targets selectable" data-disease="${escapeHtml(nm)}" data-id="${escapeHtml(cid)}" title="${escapeHtml(i18n.t('term.selectThisDisease'))}">
                    <strong>${escapeHtml(nm)}</strong>
                </span>
            `;
        }).join('');
    } else {
        elements.terminologyOpenTargets.innerHTML = `<span class="terminology-empty">${i18n.t('term.notInOtHint')}</span>`;
    }
}

function renderTerminologyError(query) {
    if (!elements.terminologyPanel) return;
    setTerminologyStatus(i18n.t('term.status.error'), 'fallback');
    if (elements.terminologySummary) elements.terminologySummary.innerHTML = '';
    elements.terminologyInput.innerHTML = `<span class="terminology-chip"><strong>${escapeHtml(query)}</strong></span>`;
    elements.terminologyUmls.innerHTML = `<span class="terminology-empty">${i18n.t('term.umlsFailed')}</span>`;
    elements.terminologyOpenTargets.innerHTML = `<span class="terminology-empty">${i18n.t('term.usingDirectOt')}</span>`;
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
    
    // Picking a suggestion ADDS it as a disease chip (up to maxDiseases), so the
    // user can combine several. `id` is the exact Open Targets ID when available.
    function selectDisease(value, id) {
        justSelected = true;
        addDisease(value, id || '');
        input.value = '';
        if (elements.diseaseIdInput) elements.diseaseIdInput.value = '';
        hideSuggestions(dropdown);
        renderTerminologyEmpty();
        setTimeout(() => input.focus(), 30);   // ready to add another
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
    const countHeader = `<div class="suggestions-count"><i class="fas fa-search"></i> ${i18n.t('search.found', { n: suggestions.length })}</div>`;

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
        <span class="remove-tag" title="${i18n.t('common.remove')}">&times;</span>
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
    input.placeholder = herbs.length > 0 ? i18n.t('index.herbPlaceholderMore') : i18n.t('index.herbPlaceholder');
}

// ==========================================
// Bulk Herb Adding (Paste Support with Korean)
// ==========================================

async function addBulkHerbs(prescriptionIndex, herbs, tagsContainer, input) {
    const validHerbs = [];
    const invalidHerbs = [];
    const duplicateHerbs = [];
    
    // Show loading toast
    showToast(i18n.t('toast.validatingHerbs'), 'info');
    
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
        showToast(i18n.t('toast.addedHerbs', { n: validHerbs.length }), 'success');
    }
    
    if (invalidHerbs.length > 0) {
        showToast(i18n.t('toast.notFound', { list: invalidHerbs.join(', ') }), 'error', 5000);
    }
    
    if (duplicateHerbs.length > 0) {
        showToast(i18n.t('toast.alreadyAdded', { list: duplicateHerbs.join(', ') }), 'warning');
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

// Preset herb formulas for quick testing. Each maps to its prescription slot.
const PRESCRIPTION_PRESETS = {
    1: ['Shu di huang', 'Shan yao', 'Shan zhu yu', 'Ze xie', 'Mu dan pi', 'Fu ling'],
    2: ['Huang lian', 'Huang bai', 'Huang qin', 'Zhi zi']
};

// Fill a single prescription slot with its preset (creates the slot if needed).
async function fillPresetSlot(slot) {
    if (slot > state.maxPrescriptions) return;   // 2 fixed slots; no dynamic add
    const tagsContainer = document.getElementById(`tags-container-${slot}`);
    if (!tagsContainer) return;
    const input = tagsContainer.querySelector('.herb-input');
    // clear anything already in this slot so re-clicking is idempotent
    tagsContainer.querySelectorAll('.herb-tag').forEach(tag => tag.remove());
    state.prescriptions[slot] = [];
    await addBulkHerbs(slot, PRESCRIPTION_PRESETS[slot], tagsContainer, input);
}

// Handle a preset button click ("1" | "2" | "3" | "all").
async function loadPreset(which) {
    if (which === 'all') {
        for (const slot of [1, 2]) {
            await fillPresetSlot(slot);
        }
        return;
    }
    await fillPresetSlot(parseInt(which, 10));
}

function addPrescription() {
    if (state.prescriptionCount >= state.maxPrescriptions) {
        showToast(i18n.t('toast.maxPrescriptions'), 'warning');
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
            <span class="prescription-badge">${i18n.t('rx.badge', { n: index })}</span>
            <button type="button" class="btn-icon remove-prescription" title="${i18n.t('rx.removeTitle')}" data-i18n-title="rx.removeTitle">
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
                        placeholder="${i18n.t('index.herbPlaceholder')}"
                        data-i18n-placeholder="index.herbPlaceholder"
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
        showToast(i18n.t('toast.minPrescription'), 'warning');
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
        card.querySelector('.prescription-badge').textContent = i18n.t('rx.badge', { n: newIndex });
        card.querySelector('.herb-input').dataset.index = newIndex;
        card.querySelector('.tags-input-container').id = `tags-container-${newIndex}`;
    });
    
    state.prescriptions = newPrescriptions;
    state.prescriptionCount = cards.length;
}

// Re-apply the localized "Prescription N" badges (on load and on language change).
function relabelPrescriptions() {
    elements.prescriptionsContainer.querySelectorAll('.prescription-card').forEach((card, i) => {
        const badge = card.querySelector('.prescription-badge');
        if (badge) badge.textContent = i18n.t('rx.badge', { n: i + 1 });
    });
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
    state.selectedDiseases = [];
    renderDiseaseChips();
    syncDiseasesField();
    updateRunButton();

    // Clear all herbs from the (two fixed) prescription slots
    Object.keys(state.prescriptions).forEach(index => {
        const tagsContainer = document.getElementById(`tags-container-${index}`);
        if (tagsContainer) {
            tagsContainer.querySelectorAll('.herb-tag').forEach(tag => tag.remove());
        }
        state.prescriptions[index] = [];
    });

    // Reset placeholders on both inputs
    document.querySelectorAll('.herb-input').forEach(inp => {
        inp.placeholder = i18n.t('index.herbPlaceholder');
    });

    elements.diseaseInput.focus();
}

function handleFormSubmit(e) {
    e.preventDefault();
    
    if (state.selectedDiseases.length === 0) {
        showToast(i18n.t('toast.needDisease'), 'error');
        elements.diseaseInput.focus();
        return;
    }
    syncDiseasesField();

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
        showToast(i18n.t('toast.needHerb'), 'error');
        return;
    }
    
    elements.herbsDataInput.value = JSON.stringify(herbsData);
    
    const submitBtn = elements.form.querySelector('button[type="submit"]');
    submitBtn.innerHTML = '<span class="spinner"></span> ' + i18n.t('btn.analyzing');
    submitBtn.disabled = true;

    elements.form.submit();
}

// Restore the Run Analysis button to its normal, clickable state. Needed after
// a back/forward-cache restore (e.g. Chrome Back from a result page), where the
// button would otherwise stay frozen in the "Analyzing..." disabled state.
function resetRunButton() {
    const btn = elements.runAnalysisBtn;
    if (!btn) return;
    btn.disabled = false;
    btn.innerHTML = '<i class="fas fa-flask"></i> <span data-i18n="index.runAnalysis">' + i18n.t('index.runAnalysis') + '</span>';
    updateRunButton(); // re-apply is-disabled based on current disease selection
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

    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', () => loadPreset(btn.dataset.preset));
    });

    // Quick-add default diseases (mirrors the prescription presets). "Add both"
    // adds every named preset button's disease; individual buttons add their own.
    document.querySelectorAll('.disease-preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            if (btn.dataset.diseaseAddBoth) {
                document.querySelectorAll('.disease-preset-btn[data-disease-id]').forEach(b => {
                    addDisease(b.dataset.diseaseName, b.dataset.diseaseId);
                });
            } else {
                addDisease(btn.dataset.diseaseName, btn.dataset.diseaseId);
            }
        });
    });

    if (elements.form) {
        elements.form.addEventListener('submit', handleFormSubmit);
    }

    // pageshow fires on first load AND on back/forward-cache restores (unlike
    // DOMContentLoaded). Reset the submit button so it isn't stuck "Analyzing...".
    window.addEventListener('pageshow', resetRunButton);

    // Re-localize dynamic content when the language changes.
    document.addEventListener('langchange', () => {
        relabelPrescriptions();
        renderDiseaseChips();
        document.querySelectorAll('.herb-input').forEach((inp) => {
            updatePlaceholder(parseInt(inp.dataset.index, 10), inp);
        });
        if (elements.diseaseInput && !elements.diseaseInput.value.trim()) {
            renderTerminologyEmpty();
        }
    });

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
