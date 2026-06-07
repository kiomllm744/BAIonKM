/* ==========================================================================
 * BAIonKM lightweight i18n (English / Korean)
 *
 * Single source of truth for all UI strings. Static template text is tagged
 * with data-i18n / data-i18n-html / data-i18n-placeholder / data-i18n-title and
 * translated by applyI18n(); dynamic JS text calls window.i18n.t('key', vars).
 *
 * Default language is Korean; the choice is remembered per browser in
 * localStorage. setLang() dispatches a 'langchange' event so already-rendered
 * dynamic content can re-render itself.
 *
 * Proper nouns are intentionally NOT translated: BAIonKM, Open Targets,
 * BATMAN-TCM, KEGG, Reactome, GO, Enrichr, DisGeNET, UMLS, gene symbols,
 * EFO/MONDO IDs, Pinyin herb names.
 * ========================================================================== */
(function (global) {
  'use strict';

  var DEFAULT_LANG = 'ko';
  var SUPPORTED = ['en', 'ko'];
  var STORAGE_KEY = 'baionkm.lang';
  var currentLang = DEFAULT_LANG;

  var I18N = {
    en: {
      /* ---- shared top bar / nav ---- */
      'nav.analysis': 'Analysis',
      'nav.database': 'Database',
      'nav.history': 'History',
      'nav.about': 'About',
      'auth.login': 'Login',
      'auth.logout': 'Logout',
      'stat.diseases': 'Diseases',
      'stat.herbs': 'Herbs',
      'lang.toggleAria': 'Switch language',

      /* ---- index / analysis page ---- */
      'index.heroTitle': 'Disease-Herb Gene Analysis',
      'index.heroSubtitle': 'Discover common genes between diseases and traditional Chinese medicine prescriptions',
      'index.selectDisease': 'Select Disease',
      'index.diseaseLabel': 'Disease(s) / Symptom(s)',
      'index.diseasePlaceholder': 'Type a disease or symptom, then pick to add (up to 3)...',
      'index.diseaseHint': "Add up to 3 diseases/symptoms — they're combined (union of genes; shared genes highlighted). Pick from the suggestions to add each one.",
      'index.prescriptions': 'Herbal Prescriptions',
      'index.addPrescription': 'Add Prescription',
      'index.presets': 'Quick test presets:',
      'index.loadAll': 'Load all 3',
      'index.herbPlaceholder': 'Type herb name or paste list...',
      'index.herbPlaceholderMore': 'Add more herbs...',
      'index.prescriptionsHint': 'You can add up to 3 prescriptions. Type to search or paste a comma-separated list of herbs.',
      'index.enrichmentLibs': 'Enrichment Libraries',
      'index.enrichmentHint': 'Choose which gene-set libraries to enrich the common genes against. Pathway libraries (KEGG, Reactome, GO) reveal mechanism; DisGeNET maps the genes back to diseases.',
      'index.clearAll': 'Clear All',
      'index.runAnalysis': 'Run Analysis',

      /* ---- prescriptions (dynamic) ---- */
      'rx.badge': 'Prescription {n}',
      'rx.removeTitle': 'Remove prescription',

      /* ---- buttons / status (dynamic) ---- */
      'btn.analyzing': 'Analyzing...',

      /* ---- toasts (dynamic) ---- */
      'toast.validatingHerbs': 'Validating herbs...',
      'toast.addedHerbs': 'Added {n} herb(s) successfully',
      'toast.notFound': 'Not found in database: {list}',
      'toast.alreadyAdded': 'Already added: {list}',
      'toast.maxPrescriptions': 'Maximum 3 prescriptions allowed',
      'toast.minPrescription': 'At least one prescription is required',
      'toast.maxDiseases': 'You can add up to {n} diseases/symptoms',
      'toast.needDisease': 'Please add at least one disease/symptom (pick it from the suggestions)',
      'toast.needHerb': 'Please add at least one herb to a prescription',

      /* ---- terminology mapping panel ---- */
      'term.title': 'Terminology Mapping',
      'term.input': 'Input',
      'term.inputHint': 'Type a disease, symptom, or clinical phrase',
      'term.umlsEmpty': 'No concepts loaded',
      'term.otEmpty': 'No candidates loaded',
      'term.status.idle': 'Idle',
      'term.status.waiting': 'Waiting',
      'term.status.mapping': 'Mapping',
      'term.status.live': 'Live',
      'term.status.fallback': 'Fallback',
      'term.status.error': 'Error',
      'term.interpreting': 'Interpreting {q}…',
      'term.understoodAs': 'We understood {q} as {rest}',
      'term.notInOt': 'not in Open Targets (no gene data)',
      'term.standardizedTerm': 'Standardized term',
      'term.searchingUmls': 'Searching UMLS...',
      'term.waitingTerms': 'Waiting for normalized terms',
      'term.searchingOt': 'Searching Open Targets for {q}…',
      'term.umlsKeyMissing': 'UMLS key not configured',
      'term.noUmlsMatch': 'No UMLS concept match',
      'term.notInOtHint': 'Not in Open Targets — no disease-gene data for this term. Pick an Open Targets disease (try a more standard name).',
      'term.umlsFailed': 'UMLS lookup failed',
      'term.usingDirectOt': 'Using direct Open Targets search',
      'term.selectThisDisease': 'Click to select this disease',
      'search.found': 'Found {n} matching results',
      'common.remove': 'Remove',

      /* ---- database page ---- */
      'db.title': 'Database Explorer',
      'db.subtitle': 'Browse diseases and herbs in the database with their associated genes',
      'db.tabDiseases': 'Diseases',
      'db.tabHerbs': 'Herbs',
      'db.searchDiseases': 'Search diseases...',
      'db.searchHerbs': 'Search herbs...',
      'db.colDiseaseName': 'Disease Name',
      'db.colAssociatedGenes': 'Associated Genes',
      'db.colSource': 'Source',
      'db.colHerbName': 'Herb Name',
      'db.colTargetGenes': 'Target Genes',
      'db.colCompounds': 'Compounds',
      'db.loading': 'Loading...',
      'db.loadingGenes': 'Loading genes...',
      'db.noDiseases': 'No diseases found',
      'db.noHerbs': 'No herbs found',
      'db.noCompounds': 'No compounds found',
      'db.noGenes': 'No genes found',
      'db.errorLoading': 'Error loading data',
      'db.errorLoadingGenes': 'Error loading genes',
      'db.showing': 'Showing {start}-{end} of {total}',
      'db.showingMatch': 'Showing {start}-{end} of {total} matching "{q}"',
      'db.genesCount': '{n} genes',
      'db.genesFor': 'Genes for: {name}',
      'db.goto': 'Go to:',
      'db.geneDetails': 'Gene Details',
      'db.go': 'Go',
      'db.compoundsCount': '{n} compounds',
      'db.geneAssociations': '{n} Gene Associations',
      'db.unknown': 'Unknown',
      'db.colGeneSymbol': 'Gene Symbol',
      'db.colGeneId': 'Gene ID',
      'db.colScore': 'Score',
      'db.liveOnline': 'Live online',

      /* ---- login page ---- */
      'login.subtitle': 'Disease-Herb Gene Analysis Platform',
      'login.demoAccess': 'Demo Access',
      'login.demoBlurb': 'Login to view saved analysis results and example cases.',
      'login.username': 'Username',
      'login.usernamePlaceholder': 'Enter your username',
      'login.password': 'Password',
      'login.passwordPlaceholder': 'Enter your password',
      'login.signIn': 'Sign In',
      'login.back': 'Back to Analysis',

      /* ---- result page (Phase 1: key labels only) ---- */
      'result.diseaseSummary': 'Disease Summary',
      'result.prescriptionSummary': 'Prescription Summary',
      'result.sharedTargets': 'Shared Disease Targets Across Prescriptions',
      'result.aiComparative': 'AI Comparative Analysis',
      'result.clinicalQuestions': 'Clinical Interview Questions',
      'result.pathwayEnrichment': 'Pathway Enrichment Analysis',
      'result.geneOverlap': 'Gene Overlap Across Prescriptions',
      'result.newAnalysis': 'New Analysis',
      'result.print': 'Print Results'
    },

    ko: {
      /* ---- shared top bar / nav ---- */
      'nav.analysis': '분석',
      'nav.database': '데이터베이스',
      'nav.history': '히스토리',
      'nav.about': '정보',
      'auth.login': '로그인',
      'auth.logout': '로그아웃',
      'stat.diseases': '질병',
      'stat.herbs': '약재',
      'lang.toggleAria': '언어 전환',

      /* ---- index / analysis page ---- */
      'index.heroTitle': '시스템 생물학 기반 처방추천 인공지능 서비스',
      'index.heroSubtitle': '한약 성분과 질환의 공통 타겟 유전자를 중심으로 핵심이 되는 생물학적 기전을 탐색하여 한의 처방 간의 감별진단 포인트를 생물학적 관점에서 추천합니다.',
      'index.selectDisease': '질병 / 증상 선택',
      'index.diseaseLabel': '질병 / 증상 (영어)',
      'index.diseasePlaceholder': '질병 또는 증상을 입력한 뒤 목록에서 선택하세요 (최대 3개)...',
      'index.diseaseHint': '최대 3개의 질병/증상을 추가할 수 있습니다 — 유전자를 합집합으로 결합하며 공통 유전자를 강조 표시합니다. 추천 목록에서 선택해 추가하세요.',
      'index.prescriptions': '한의 처방 선택',
      'index.addPrescription': '처방 추가',
      'index.presets': '빠른 테스트 예시:',
      'index.loadAll': '3개 모두 불러오기',
      'index.herbPlaceholder': '약재명을 입력하거나 목록을 붙여넣으세요...',
      'index.herbPlaceholderMore': '약재 더 추가...',
      'index.prescriptionsHint': '최대 3개의 처방을 추가할 수 있습니다. 약재를 검색하거나 쉼표로 구분된 목록을 붙여넣으세요.',
      'index.enrichmentLibs': '강화 분석 라이브러리',
      'index.enrichmentHint': '공통 유전자를 강화 분석할 유전자 세트 라이브러리를 선택하세요. 경로 라이브러리(KEGG, Reactome, GO)는 기전을 보여주고, DisGeNET은 유전자를 질병과 연결합니다.',
      'index.clearAll': '모두 지우기',
      'index.runAnalysis': '분석 실행',

      /* ---- prescriptions (dynamic) ---- */
      'rx.badge': '처방 {n}',
      'rx.removeTitle': '처방 제거',

      /* ---- buttons / status (dynamic) ---- */
      'btn.analyzing': '분석 중...',

      /* ---- toasts (dynamic) ---- */
      'toast.validatingHerbs': '약재 확인 중...',
      'toast.addedHerbs': '{n}개 약재를 추가했습니다',
      'toast.notFound': '데이터베이스에 없음: {list}',
      'toast.alreadyAdded': '이미 추가됨: {list}',
      'toast.maxPrescriptions': '처방은 최대 3개까지 가능합니다',
      'toast.minPrescription': '최소 한 개의 처방이 필요합니다',
      'toast.maxDiseases': '최대 {n}개의 질병/증상을 추가할 수 있습니다',
      'toast.needDisease': '질병/증상을 최소 하나 추가하세요 (추천 목록에서 선택)',
      'toast.needHerb': '처방에 약재를 최소 하나 추가하세요',

      /* ---- terminology mapping panel ---- */
      'term.title': '용어 매핑',
      'term.input': '입력',
      'term.inputHint': '질병, 증상 또는 임상 표현을 입력하세요',
      'term.umlsEmpty': '불러온 개념 없음',
      'term.otEmpty': '불러온 후보 없음',
      'term.status.idle': '유휴',
      'term.status.waiting': '대기',
      'term.status.mapping': '매핑 중',
      'term.status.live': '실시간',
      'term.status.fallback': '대체',
      'term.status.error': '오류',
      'term.interpreting': '{q} 해석 중…',
      'term.understoodAs': '{q}을(를) 다음으로 이해했습니다: {rest}',
      'term.notInOt': 'Open Targets에 없음 (유전자 데이터 없음)',
      'term.standardizedTerm': '표준 용어',
      'term.searchingUmls': 'UMLS 검색 중...',
      'term.waitingTerms': '표준화된 용어 대기 중',
      'term.searchingOt': 'Open Targets에서 {q} 검색 중…',
      'term.umlsKeyMissing': 'UMLS 키가 설정되지 않음',
      'term.noUmlsMatch': '일치하는 UMLS 개념 없음',
      'term.notInOtHint': 'Open Targets에 없음 — 이 용어에 대한 질병-유전자 데이터가 없습니다. Open Targets 질병을 선택하세요 (더 표준적인 이름을 사용해 보세요).',
      'term.umlsFailed': 'UMLS 조회 실패',
      'term.usingDirectOt': 'Open Targets 직접 검색 사용',
      'term.selectThisDisease': '이 질병을 선택하려면 클릭하세요',
      'search.found': '{n}개의 결과를 찾았습니다',
      'common.remove': '제거',

      /* ---- database page ---- */
      'db.title': '데이터베이스 탐색',
      'db.subtitle': '데이터베이스의 질병과 약재, 연관 유전자를 탐색합니다',
      'db.tabDiseases': '질병',
      'db.tabHerbs': '약재',
      'db.searchDiseases': '질병 검색...',
      'db.searchHerbs': '약재 검색...',
      'db.colDiseaseName': '질병명',
      'db.colAssociatedGenes': '연관 유전자',
      'db.colSource': '출처',
      'db.colHerbName': '약재명',
      'db.colTargetGenes': '타겟 유전자',
      'db.colCompounds': '성분',
      'db.loading': '불러오는 중...',
      'db.loadingGenes': '유전자 불러오는 중...',
      'db.noDiseases': '질병을 찾을 수 없습니다',
      'db.noHerbs': '약재를 찾을 수 없습니다',
      'db.noCompounds': '성분을 찾을 수 없습니다',
      'db.noGenes': '유전자를 찾을 수 없습니다',
      'db.errorLoading': '데이터를 불러오지 못했습니다',
      'db.errorLoadingGenes': '유전자를 불러오지 못했습니다',
      'db.showing': '{total}개 중 {start}-{end} 표시',
      'db.showingMatch': '"{q}" 검색 결과 {total}개 중 {start}-{end} 표시',
      'db.genesCount': '{n}개 유전자',
      'db.genesFor': '유전자: {name}',
      'db.goto': '이동:',
      'db.geneDetails': '유전자 상세',
      'db.go': '이동',
      'db.compoundsCount': '성분 {n}개',
      'db.geneAssociations': '유전자 연관 {n}개',
      'db.unknown': '알 수 없음',
      'db.colGeneSymbol': '유전자 기호',
      'db.colGeneId': '유전자 ID',
      'db.colScore': '점수',
      'db.liveOnline': '실시간 온라인',

      /* ---- login page ---- */
      'login.subtitle': '질병-약재 유전자 분석 플랫폼',
      'login.demoAccess': '데모 접속',
      'login.demoBlurb': '저장된 분석 결과와 예시를 보려면 로그인하세요.',
      'login.username': '사용자 이름',
      'login.usernamePlaceholder': '사용자 이름을 입력하세요',
      'login.password': '비밀번호',
      'login.passwordPlaceholder': '비밀번호를 입력하세요',
      'login.signIn': '로그인',
      'login.back': '분석 페이지로 돌아가기',

      /* ---- result page (Phase 1: key labels only) ---- */
      'result.diseaseSummary': '질병 요약',
      'result.prescriptionSummary': '처방 요약',
      'result.sharedTargets': '처방 간 공유 질병 타겟',
      'result.aiComparative': 'AI 비교 분석',
      'result.clinicalQuestions': '임상 문진 질문',
      'result.pathwayEnrichment': '경로 강화 분석',
      'result.geneOverlap': '처방 간 유전자 중복',
      'result.newAnalysis': '새 분석',
      'result.print': '결과 인쇄'
    }
  };

  /* ---- core helpers ---- */

  function getLang() { return currentLang; }

  function t(key, vars) {
    var table = I18N[currentLang] || I18N.en;
    var str = (table && table[key] != null)
      ? table[key]
      : (I18N.en[key] != null ? I18N.en[key] : key); // current -> en -> raw key
    if (vars) {
      str = str.replace(/\{(\w+)\}/g, function (m, name) {
        return (vars[name] != null) ? vars[name] : m;
      });
    }
    return str;
  }

  function applyI18n(root) {
    root = root || document;
    root.querySelectorAll('[data-i18n]').forEach(function (el) {
      el.textContent = t(el.getAttribute('data-i18n'));
    });
    root.querySelectorAll('[data-i18n-html]').forEach(function (el) {
      el.innerHTML = t(el.getAttribute('data-i18n-html'));
    });
    root.querySelectorAll('[data-i18n-placeholder]').forEach(function (el) {
      el.setAttribute('placeholder', t(el.getAttribute('data-i18n-placeholder')));
    });
    root.querySelectorAll('[data-i18n-title]').forEach(function (el) {
      el.setAttribute('title', t(el.getAttribute('data-i18n-title')));
    });
  }

  function updateToggleUI() {
    var btn = document.getElementById('lang-toggle');
    if (!btn) return;
    btn.querySelectorAll('[data-lang]').forEach(function (span) {
      span.classList.toggle('active', span.getAttribute('data-lang') === currentLang);
    });
    btn.setAttribute('aria-label', t('lang.toggleAria'));
  }

  function setLang(lang) {
    if (SUPPORTED.indexOf(lang) === -1) lang = DEFAULT_LANG;
    currentLang = lang;
    try { localStorage.setItem(STORAGE_KEY, lang); } catch (e) {}
    document.documentElement.lang = lang;
    applyI18n(document);
    updateToggleUI();
    try {
      document.dispatchEvent(new CustomEvent('langchange', { detail: { lang: lang } }));
    } catch (e) {
      // Older browsers: fall back to a manually-constructed event
      var ev = document.createEvent('CustomEvent');
      ev.initCustomEvent('langchange', false, false, { lang: lang });
      document.dispatchEvent(ev);
    }
  }

  function toggle() { setLang(currentLang === 'ko' ? 'en' : 'ko'); }

  function readSavedLang() {
    try {
      var saved = localStorage.getItem(STORAGE_KEY);
      if (saved && SUPPORTED.indexOf(saved) !== -1) return saved;
    } catch (e) {}
    return DEFAULT_LANG;
  }

  function init() {
    currentLang = readSavedLang();
    document.documentElement.lang = currentLang;
    applyI18n(document);
    var btn = document.getElementById('lang-toggle');
    if (btn) btn.addEventListener('click', toggle);
    updateToggleUI();
    // Reveal the page (the head cloak script hides it until translations apply)
    document.documentElement.classList.remove('i18n-cloak');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Public API (also usable from template inline scripts)
  global.I18N = I18N;
  global.i18n = {
    t: t,
    applyI18n: applyI18n,
    setLang: setLang,
    getLang: getLang,
    toggle: toggle
  };
})(window);
