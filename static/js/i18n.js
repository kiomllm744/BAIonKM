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
      'nav.libraries': 'Libraries',
      'lib.title': 'Enrichment libraries',
      'lib.hint': 'Sent to Enrichr. If none are selected, DisGeNET is used.',
      'nav.aiModel': 'AI Model',
      'ai.modelTitle': 'AI model',
      'ai.modelHint': 'Which AI writes the analysis. Set the matching API key on the server.',
      'auth.login': 'Login',
      'auth.logout': 'Logout',
      'stat.diseases': 'Diseases',
      'stat.herbs': 'Herbs',
      'lang.toggleAria': 'Switch language',

      /* ---- index / analysis page ---- */
      'index.heroTitle': 'Disease-Herb Gene Analysis',
      'index.heroSubtitle': 'Discover common genes between diseases and traditional Chinese medicine prescriptions',
      'index.selectDisease': 'Select Disease',
      'index.diseaseLabel': 'Disease / symptom name',
      'index.diseasePlaceholder': 'Type a disease or symptom name, then pick to add (up to 3)...',
      'index.diseaseHint': "Add up to 3 diseases — they're combined (union of genes; shared genes highlighted). Pick from the suggestions to add each one.",
      'index.prescriptions': 'Herbal Prescriptions',
      'index.addPrescription': 'Add Prescription',
      'index.presets': 'Examples:',
      'index.preset1': 'Yukmijihwangtang',
      'index.preset2': 'Hwangnyeonhaedoktang',
      'index.loadAll': 'Load both',
      'index.diseasePresets': 'Add examples:',
      'index.addBothDiseases': 'Add both',
      'index.herbPlaceholder': 'Type herb name or paste list...',
      'index.herbPlaceholderMore': 'Add more herbs...',
      'index.prescriptionsHint': 'Fill one or both prescriptions. Type to search or paste a comma-separated list of herbs.',
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
      'toast.maxPrescriptions': 'Maximum 2 prescriptions allowed',
      'toast.minPrescription': 'At least one prescription is required',
      'toast.maxDiseases': 'You can add up to {n} diseases',
      'toast.needDisease': 'Please add at least one disease (pick it from the suggestions)',
      'toast.needHerb': 'Please add at least one herb to a prescription',

      /* ---- terminology mapping panel ---- */
      'term.title': 'Terminology Mapping',
      'term.input': 'Input',
      'term.inputHint': '',
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
      'result.diseaseSummary': 'Disease / Symptom – Gene Correlation',
      'result.prescriptionSummary': 'Prescription Summary',
      'result.sharedTargets': 'Shared Disease Targets Across Prescriptions',
      'result.aiComparative': 'AI Comparative Analysis',
      'result.clinicalQuestions': 'Clinical Interview Questions',
      'result.pathwayEnrichment': 'Pathway Enrichment Analysis',
      'result.geneOverlap': 'Gene Overlap Across Prescriptions',
      'result.newAnalysis': 'New Analysis',
      'result.print': 'Print Results',

      /* ---- about page (Phase 2) ---- */
      'about.heroBlurb': 'A computational platform for discovering shared genetic pathways between diseases and traditional Chinese medicine prescriptions through advanced bioinformatics analysis.',
      'about.systemArchitecture': 'System Architecture',
      'about.coreAlgorithm': 'Core Algorithm',
      'about.dataSources': 'Data Sources',
      'about.howItWorks': 'How It Works',
      'about.techStack': 'Technology Stack',
      'about.archDisease': 'Disease Name',
      'about.archDiseaseEg': "e.g., Alzheimer's Disease",
      'about.archRx': 'Herbal Prescriptions',
      'about.archRxSub': 'Up to 3 formulas',
      'about.archOtSub': 'Disease-Gene Associations',
      'about.archBatmanSub': 'Herb-Compound-Gene Data',
      'about.archIntersection': 'Gene Set Intersection',
      'about.archIntersectionSub': 'Find common genes between disease & herbs',
      'about.commonGenes': 'Common Genes',
      'about.keggPathways': 'KEGG Pathways',
      'about.goTerms': 'GO Terms',
      'about.archEnrichrSub': 'Pathway Enrichment Analysis',
      'about.setIntersectionLogic': 'Set Intersection Logic',
      'about.diseaseGenes': 'Disease Genes',
      'about.fromOpenTargets': 'from Open Targets',
      'about.herbTargets': 'Herb Targets',
      'about.fromBatman': 'from BATMAN-TCM',
      'about.therapeuticTargets': 'Therapeutic Targets',
      'about.algoDesc': 'The intersection reveals genes that are both associated with the disease AND targeted by the herbal compounds, suggesting potential therapeutic mechanisms of traditional medicine.',
      'about.otDesc': 'An open platform that integrates human genetics, genomics, transcriptomics, drugs, animal models, and the literature to score and rank gene–disease associations. Disease genes and their association scores are fetched live from the Open Targets GraphQL API.',
      'about.statTargets': 'Targets',
      'about.batmanDesc': 'Bioinformatics Analysis Tool for Molecular mechANism of Traditional Chinese Medicine. Maps herbal compounds to their gene targets using molecular similarity and network-based predictions.',
      'about.statCompounds': 'Compounds',
      'about.enrichrDesc': 'A comprehensive gene set enrichment analysis web server. Provides access to hundreds of gene-set libraries for pathway analysis including KEGG, GO, and the <strong>DisGeNET</strong> disease gene-set library used here for enrichment.',
      'about.statLibraries': 'Libraries',
      'about.statGeneSets': 'Gene Sets',
      'about.step1Title': 'Select Disease & Input Prescriptions',
      'about.step1Desc': 'Enter a disease name using the autocomplete search and add up to 3 herbal prescriptions. Each prescription can contain multiple herbs separated by commas. The system validates herb names against the BATMAN-TCM database.',
      'about.step2Title': 'Retrieve Gene Associations',
      'about.step2Desc': 'The system queries Open Targets for disease-associated genes (with association scores) and BATMAN-TCM for compound-gene targets of each herb. These sources provide curated, high-quality associations from multiple lines of evidence.',
      'about.step3Title': 'Compute Gene Intersection',
      'about.step3Desc': 'Using set theory, the system finds genes that appear in BOTH the disease gene set AND the combined herb target gene set. This intersection represents potential therapeutic targets.',
      'about.step4Title': 'Pathway Enrichment Analysis',
      'about.step4Desc': 'The common genes are submitted to Enrichr for enrichment analysis. The system retrieves significantly enriched KEGG pathways, GO biological processes, and molecular functions to understand the biological context.',
      'about.step5Title': 'Results & Visualization',
      'about.step5Desc': 'Results are presented with interactive visualizations including gene lists, pathway charts, and statistical significance scores. All results are saved to history for future reference.',
      'about.step6Title': 'AI Comparative Analysis',
      'about.step6Desc': 'The enriched pathways for each prescription are sent to a generative AI model (Gemini), which compares the prescriptions, derives each one\'s core biological mechanism against the disease, and generates key differential clinical questions. The analysis follows the UI language — English or Korean.',
      'about.archAiModule': 'AI Integrated Analysis Module',
      'about.archAiModuleSub': 'Comparative pathway & mechanism analysis (Gemini)',
      'about.archAiOut1': 'Unique mechanism per prescription',
      'about.archAiOut2': 'Core mechanism per prescription',
      'about.archAiOut3': 'Key differential clinical questions',
      'about.footerDesc': 'Bridging traditional medicine and modern genomics through computational analysis. This platform aims to help researchers understand the potential molecular mechanisms underlying traditional Chinese medicine treatments.',

      /* ---- history page (Phase 2) ---- */
      'hist.title': 'Analysis History',
      'hist.subtitle': 'View and revisit your previous disease-herb gene analysis results',
      'hist.savedResults': 'Saved Results',
      'hist.loadingResults': 'Loading results...',
      'hist.resultsCount': '{n} results',
      'hist.emptyTitle': 'No Analysis Results Yet',
      'hist.emptyDesc': 'Run your first disease-herb gene analysis to see results here.',
      'hist.startNew': 'Start New Analysis',
      'hist.rxCount': '{n} prescriptions',
      'hist.herbsCount': '{n} herbs',
      'hist.viewResult': 'View Result',
      'hist.delete': 'Delete',
      'hist.errorTitle': 'Error Loading Results',
      'hist.errorDesc': 'Failed to load analysis history. Please try again.',
      'hist.retry': 'Retry',
      'hist.confirmDelete': 'Are you sure you want to delete this result?',
      'hist.deleteSuccess': 'Result deleted successfully',
      'hist.deleteFailed': 'Failed to delete result',
      'hist.deleteError': 'Error deleting result',

      /* ---- results page deep body + AI (Phase 2) ---- */
      'result.genesUnit': 'genes',
      'result.diseaseGeneUnit': ' genes',
      'result.showMoreGenes': '+{n} more',
      'result.showLessGenes': 'Show less',
      'result.totalAssocGenes': 'Total associated genes:',
      'result.usedInAnalysis': 'used in analysis',
      'result.notResolved': 'not resolved',
      'result.vennNote1': 'Each number = genes shared by exactly that region · center = shared by all diseases',
      'result.diagramToggle': 'Diagram',
      'result.tabIntersection': 'Intersection',
      'result.tabUnion': 'Union',
      'result.emptyIntersectionTitle': 'No shared genes',
      'result.emptyIntersectionBody': 'The selected diseases have no genes in common, so the intersection analysis is empty. Try the Union analysis instead.',
      'choose.title': 'How should we combine the disease genes?',
      'choose.subtitle': 'You entered more than one disease. Choose whether to analyze: 1. genes associated with all diseases (intersection), 2. all genes associated with at least one disease (union), or 3. both.',
      'choose.diseaseOverlap': 'Disease gene overlap',
      'choose.unionCount': 'genes in any disease (union)',
      'choose.intersectionCount': 'genes shared by all (intersection)',
      'choose.intersectionLabel': 'Intersection',
      'choose.intersectionDesc': 'Analyse only the genes shared by every selected disease — the common core.',
      'choose.unionLabel': 'Union',
      'choose.unionDesc': 'Analyse every gene linked to any of the selected diseases.',
      'choose.bothLabel': 'Both',
      'choose.bothDesc': 'Run both analyses and compare them side by side in two tabs.',
      'choose.bothCount': 'intersection + union',
      'choose.genesWord': 'genes',
      'choose.intersectionEmptyWarn': 'The selected diseases share no common genes, so only the Union analysis is available.',
      'choose.hlHint': 'Hover an option below to preview which genes it analyses.',
      'choose.hlIntersection': 'Intersection → only the shared center of the diagram.',
      'choose.hlUnion': 'Union → the whole diagram (all genes).',
      'choose.hlBoth': 'Both → runs the whole diagram and the shared center.',
      'result.kpiDiseasesCombined': 'Diseases / symptoms',
      'result.kpiTotalGenes': 'Total genes used (union)',
      'result.kpiTotalGenesIntersection': 'Total genes used (intersection)',
      'result.kpiSharedAll': 'Shared by all diseases',
      'result.kpiDiseaseGenesHit': 'Disease genes hit (any prescription)',
      'result.aiFeature': 'Feature',
      'result.aiFinding': 'Finding',
      'result.aiRowDriver': 'Primary Driver',
      'result.aiRowTissue': 'Key Tissue',
      'result.aiRowConsequence': 'Main Consequence',
      'result.warnings': 'Warnings:',
      'result.rxLabel': 'Prescription',
      'result.kpiHerbGenes': 'Herb genes (total)',
      'result.kpiCommonGenes': 'Common genes',
      'result.intersectingTargets': 'Intersecting Gene Targets',
      'result.legendClinGenThis': 'ClinGen-validated (this disease)',
      'result.legendClinGenOther': 'ClinGen (other disease)',
      'result.legendOther': 'other',
      'result.legendSharedAll': 'shared by all diseases',
      'result.hoverEvidence': 'hover a gene for evidence',
      'result.noIntersecting': 'No intersecting targets found',
      'result.vennNote2': 'Each number = disease-associated genes hit by exactly that set of prescriptions · center = hit by all',
      'result.vennDiseaseGenes': 'Disease genes',
      'result.vennHerbGenes': 'herb genes',
      'result.vennOverlapNote': 'Overlap = disease-associated genes this prescription targets',
      'result.kpiSharedAllRx': 'Shared by all prescriptions',
      'result.aiLoading': 'Analyzing pathways with AI...',
      'result.viewDetailed': 'View Detailed Analysis',
      'result.hideDetailed': 'Hide Detailed Analysis',
      'result.showRationale': 'Show Rationale',
      'result.hideRationale': 'Hide Rationale',
      'result.analysisFailed': 'Analysis Failed',
      'result.errorOccurred': 'An error occurred',
      'result.retry': 'Retry',
      'result.apiKeyRequired': 'API Key Required',
      'result.setGeminiKey': 'Set your Gemini API key to enable AI analysis:',
      'result.getFreeKey': 'Get a free key at',
      'result.diagnosticSupport': 'Diagnostic Support',
      'result.generatingQuestions': 'Generating clinical questions...',
      'result.clinicalUnavailable': 'Clinical questions will be generated after pathway analysis completes.',
      'result.suspectedDriver': 'Suspected Driver:',
      'result.group': 'Group {n}',
      'result.analysisPending': 'Analysis pending',
      'result.noComparisonData': 'No comparison table data available.',
      'result.noAnalysisResults': 'No analysis results available',
      'result.noEnrichmentData': 'No enrichment data available. The prescription may not have significant gene-disease associations.',
      'result.aiAnalysisFailed': 'AI analysis failed',
      'result.noSummaryData': 'No summary data available',
      'result.failedInitAi': 'Failed to initialize AI',
      'result.resultsCount': '{n} results',
      'result.colTerm': 'Term',
      'result.colPvalue': 'P-value',
      'result.colScoreEnr': 'Score',
      'result.noSignificant': 'No significant enrichment results',
      'result.overlapIntro': "Enrichment above is computed on each prescription's disease-relevant (“common”) genes. This panel shows how those targets overlap — the core hit by every formula vs. the targets distinctive to a single one.",
      'result.coreTargets': 'Core targets — shared by every prescription',
      'result.noSingleCore': 'No single target is shared by all prescriptions.',
      'result.distinctiveTargets': 'Distinctive targets — hit by only one prescription',
      'result.distinctiveCount': '{n} distinctive',
      'result.noneOverlaps': '— none (fully overlaps the other prescriptions)',

      /* ---- error pages (Phase 2) ---- */
      'error.t404': 'Page not found',
      'error.m404': "That page doesn't exist or has moved.",
      'error.t500': 'Something went wrong',
      'error.m500': 'An unexpected error occurred.'
    },

    ko: {
      /* ---- shared top bar / nav ---- */
      'nav.analysis': '분석',
      'nav.database': '데이터베이스',
      'nav.history': '히스토리',
      'nav.about': '정보',
      'nav.libraries': '라이브러리',
      'lib.title': '강화 분석 라이브러리',
      'lib.hint': 'Enrichr로 전송됩니다. 선택하지 않으면 DisGeNET이 사용됩니다.',
      'nav.aiModel': 'AI 모델',
      'ai.modelTitle': 'AI 모델 선택',
      'ai.modelHint': 'AI 분석을 작성할 모델입니다. 서버에 해당 API 키를 설정하세요.',
      'auth.login': '로그인',
      'auth.logout': '로그아웃',
      'stat.diseases': '질병',
      'stat.herbs': '약재',
      'lang.toggleAria': '언어 전환',

      /* ---- index / analysis page ---- */
      'index.heroTitle': '시스템 생물학 기반 처방추천 인공지능 서비스',
      'index.heroSubtitle': '한약 성분과 질환의 공통 타겟 유전자를 중심으로 핵심이 되는 생물학적 기전을 탐색하여 한의 처방 간의 감별진단 포인트를 생물학적 관점에서 추천합니다.',
      'index.selectDisease': '질병 선택',
      'index.diseaseLabel': '질병/증상명',
      'index.diseasePlaceholder': '질병/증상명을 입력한 뒤...',
      'index.diseaseHint': '최대 3개의 질병을 추가할 수 있습니다 — 유전자를 합집합으로 결합하며 공통 유전자를 강조 표시합니다. 추천 목록에서 선택해 추가하세요.',
      'index.prescriptions': '한의 처방 선택',
      'index.addPrescription': '처방 추가',
      'index.presets': '예시:',
      'index.preset1': '육미 지황탕',
      'index.preset2': '황련해독탕',
      'index.loadAll': '둘 다 불러오기',
      'index.diseasePresets': '예시 추가:',
      'index.addBothDiseases': '둘 다 추가',
      'index.herbPlaceholder': '약재명을 입력하거나 목록을 붙여넣으세요...',
      'index.herbPlaceholderMore': '약재 더 추가...',
      'index.prescriptionsHint': '두 처방 중 하나 또는 둘 다 입력하세요. 약재를 검색하거나 쉼표로 구분된 목록을 붙여넣으세요.',
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
      'toast.maxPrescriptions': '처방은 최대 2개까지 가능합니다',
      'toast.minPrescription': '최소 한 개의 처방이 필요합니다',
      'toast.maxDiseases': '최대 {n}개의 질병을 추가할 수 있습니다',
      'toast.needDisease': '질병을 최소 하나 추가하세요 (추천 목록에서 선택)',
      'toast.needHerb': '처방에 약재를 최소 하나 추가하세요',

      /* ---- terminology mapping panel ---- */
      'term.title': '용어 매핑',
      'term.input': '입력',
      'term.inputHint': '',
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
      'result.diseaseSummary': '질환/증상 - 유전자 상관성',
      'result.prescriptionSummary': '처방 요약',
      'result.sharedTargets': '처방 간 공유 질병 타겟',
      'result.aiComparative': 'AI 비교 분석',
      'result.clinicalQuestions': '임상 문진 질문',
      'result.pathwayEnrichment': '경로 강화 분석',
      'result.geneOverlap': '처방 간 유전자 중복',
      'result.newAnalysis': '새 분석',
      'result.print': '결과 인쇄',

      /* ---- about page (Phase 2) ---- */
      'about.heroBlurb': '질병과 한약 처방 간의 공통 유전적 경로를 고급 생물정보학 분석으로 탐색하는 컴퓨팅 플랫폼입니다.',
      'about.systemArchitecture': '시스템 아키텍처',
      'about.coreAlgorithm': '핵심 알고리즘',
      'about.dataSources': '데이터 출처',
      'about.howItWorks': '작동 방식',
      'about.techStack': '기술 스택',
      'about.archDisease': '질병명',
      'about.archDiseaseEg': "예: Alzheimer's Disease",
      'about.archRx': '한방 처방',
      'about.archRxSub': '최대 3개 처방',
      'about.archOtSub': '질병-유전자 연관성',
      'about.archBatmanSub': '약재-성분-유전자 데이터',
      'about.archIntersection': '유전자 세트 교집합',
      'about.archIntersectionSub': '질병과 약재 간의 공통 유전자 찾기',
      'about.commonGenes': '공통 유전자',
      'about.keggPathways': 'KEGG 경로',
      'about.goTerms': 'GO 용어',
      'about.archEnrichrSub': '경로 강화 분석',
      'about.setIntersectionLogic': '집합 교집합 논리',
      'about.diseaseGenes': '질병 유전자',
      'about.fromOpenTargets': 'Open Targets 기반',
      'about.herbTargets': '약재 타겟',
      'about.fromBatman': 'BATMAN-TCM 기반',
      'about.therapeuticTargets': '치료 타겟',
      'about.algoDesc': '교집합은 질병과 연관되면서 동시에 한약 성분이 표적하는 유전자를 보여주며, 전통 의학의 잠재적 치료 기전을 시사합니다.',
      'about.otDesc': '인간 유전학, 유전체학, 전사체학, 약물, 동물 모델, 문헌을 통합하여 유전자–질병 연관성을 점수화하고 순위를 매기는 공개 플랫폼입니다. 질병 유전자와 연관성 점수는 Open Targets GraphQL API에서 실시간으로 가져옵니다.',
      'about.statTargets': '타겟',
      'about.batmanDesc': '전통 한의학의 분자 기전 분석을 위한 생물정보학 도구입니다. 분자 유사성과 네트워크 기반 예측을 사용해 한약 성분을 유전자 타겟에 매핑합니다.',
      'about.statCompounds': '성분',
      'about.enrichrDesc': '포괄적인 유전자 세트 강화 분석 웹 서버입니다. KEGG, GO를 포함한 수백 개의 유전자 세트 라이브러리와 여기서 강화 분석에 사용하는 <strong>DisGeNET</strong> 질병 유전자 세트 라이브러리에 접근할 수 있습니다.',
      'about.statLibraries': '라이브러리',
      'about.statGeneSets': '유전자 세트',
      'about.step1Title': '질병 선택 및 처방 입력',
      'about.step1Desc': '자동완성 검색으로 질병명을 입력하고 최대 3개의 한방 처방을 추가합니다. 각 처방은 쉼표로 구분된 여러 약재를 포함할 수 있습니다. 시스템은 약재명을 BATMAN-TCM 데이터베이스와 대조해 검증합니다.',
      'about.step2Title': '유전자 연관성 조회',
      'about.step2Desc': '시스템은 Open Targets에서 질병 연관 유전자(연관성 점수 포함)를, BATMAN-TCM에서 각 약재의 성분-유전자 타겟을 조회합니다. 이 출처들은 여러 근거에 기반한 정제된 고품질 연관성을 제공합니다.',
      'about.step3Title': '유전자 교집합 계산',
      'about.step3Desc': '집합 이론을 사용해 질병 유전자 집합과 약재 타겟 유전자 집합 모두에 나타나는 유전자를 찾습니다. 이 교집합이 잠재적 치료 타겟을 나타냅니다.',
      'about.step4Title': '경로 강화 분석',
      'about.step4Desc': '공통 유전자를 Enrichr에 제출해 강화 분석을 수행합니다. 시스템은 유의하게 강화된 KEGG 경로, GO 생물학적 과정 및 분자 기능을 조회해 생물학적 맥락을 파악합니다.',
      'about.step5Title': '결과 및 시각화',
      'about.step5Desc': '결과는 유전자 목록, 경로 차트, 통계적 유의성 점수를 포함한 대화형 시각화로 제공됩니다. 모든 결과는 향후 참조를 위해 히스토리에 저장됩니다.',
      'about.step6Title': 'AI 비교 분석',
      'about.step6Desc': '각 처방의 강화된 경로를 생성형 AI 모델(Gemini)에 전달하여 처방들을 비교하고, 각 처방의 질병 대비 핵심 생물학적 기전을 도출하며, 주요 감별 임상 질문을 생성합니다. 분석은 UI 언어(영어 또는 한국어)를 따릅니다.',
      'about.archAiModule': 'AI 통합 분석 모듈',
      'about.archAiModuleSub': '생물학적 경로 및 기전 비교 분석 (Gemini)',
      'about.archAiOut1': '처방 별 고유 생물학적 기전 비교',
      'about.archAiOut2': '처방 별 핵심 생물학적 기전 도출',
      'about.archAiOut3': '핵심 기전 중심 주요 감별 질문 생성',
      'about.footerDesc': '컴퓨팅 분석을 통해 전통 의학과 현대 유전체학을 연결합니다. 이 플랫폼은 연구자가 전통 한의학 치료의 잠재적 분자 기전을 이해하도록 돕는 것을 목표로 합니다.',

      /* ---- history page (Phase 2) ---- */
      'hist.title': '분석 히스토리',
      'hist.subtitle': '이전 질병-약재 유전자 분석 결과를 확인하고 다시 볼 수 있습니다',
      'hist.savedResults': '저장된 결과',
      'hist.loadingResults': '결과를 불러오는 중...',
      'hist.resultsCount': '{n}개 결과',
      'hist.emptyTitle': '아직 분석 결과가 없습니다',
      'hist.emptyDesc': '첫 질병-약재 유전자 분석을 실행하면 여기에 결과가 표시됩니다.',
      'hist.startNew': '새 분석 시작',
      'hist.rxCount': '처방 {n}개',
      'hist.herbsCount': '약재 {n}개',
      'hist.viewResult': '결과 보기',
      'hist.delete': '삭제',
      'hist.errorTitle': '결과를 불러오지 못했습니다',
      'hist.errorDesc': '분석 히스토리를 불러오지 못했습니다. 다시 시도하세요.',
      'hist.retry': '다시 시도',
      'hist.confirmDelete': '이 결과를 삭제하시겠습니까?',
      'hist.deleteSuccess': '결과를 삭제했습니다',
      'hist.deleteFailed': '결과 삭제에 실패했습니다',
      'hist.deleteError': '결과 삭제 중 오류가 발생했습니다',

      /* ---- results page deep body + AI (Phase 2) ---- */
      'result.genesUnit': '유전자',
      'result.diseaseGeneUnit': '종 유전자',
      'result.showMoreGenes': '+{n}개 더보기',
      'result.showLessGenes': '접기',
      'result.totalAssocGenes': '전체 연관 유전자:',
      'result.usedInAnalysis': '분석에 사용',
      'result.notResolved': '미해결',
      'result.vennNote1': '각 숫자 = 해당 영역에만 공유되는 유전자 · 중앙 = 모든 질병이 공유',
      'result.diagramToggle': '다이어그램',
      'result.tabIntersection': '교집합',
      'result.tabUnion': '합집합',
      'result.emptyIntersectionTitle': '공유 유전자 없음',
      'result.emptyIntersectionBody': '선택한 질병들이 공통 유전자를 가지고 있지 않아 교집합 분석이 비어 있습니다. 대신 합집합 분석을 사용해 보세요.',
      'choose.title': '질병 유전자를 어떻게 결합할까요?',
      'choose.subtitle': '두 개 이상의 질병을 입력하였습니다. 1. 모든 질병과의 연관성을 갖는 유전자군(교집합)과, 2. 최소 하나의 질병과의 연관성을 갖는 모든 유전자군(합집합), 3. 두가지 모두를 분석할지 선택하세요.',
      'choose.diseaseOverlap': '질병 유전자 중첩',
      'choose.unionCount': '어느 질병이든 포함된 유전자 (합집합)',
      'choose.intersectionCount': '모든 질병이 공유하는 유전자 (교집합)',
      'choose.intersectionLabel': '교집합',
      'choose.intersectionDesc': '선택한 모든 질병이 공유하는 유전자(질환 공통 유발요인)만 분석합니다.',
      'choose.unionLabel': '합집합',
      'choose.unionDesc': '선택한 질병 중 하나라도 연관된 모든 유전자를 분석합니다.',
      'choose.bothLabel': '둘 다',
      'choose.bothDesc': '두 분석을 모두 실행하여 두 개의 탭에서 나란히 비교합니다.',
      'choose.bothCount': '교집합 + 합집합',
      'choose.genesWord': '유전자',
      'choose.intersectionEmptyWarn': '선택한 질병들이 공유하는 공통 유전자가 없어 합집합 분석만 가능합니다.',
      'choose.hlHint': '아래 옵션에 마우스를 올리면 어떤 유전자를 분석할지 미리 볼 수 있습니다.',
      'choose.hlIntersection': '교집합 → 다이어그램의 공유 중심 부분만 분석합니다.',
      'choose.hlUnion': '합집합 → 다이어그램 전체(모든 유전자)를 분석합니다.',
      'choose.hlBoth': '둘 다 → 전체와 공유 중심을 모두 분석합니다.',
      'result.kpiDiseasesCombined': '질환/증상 수',
      'result.kpiTotalGenes': '사용된 전체 유전자 (합집합)',
      'result.kpiTotalGenesIntersection': '사용된 전체 유전자 (교집합)',
      'result.kpiSharedAll': '모든 질병 공유',
      'result.kpiDiseaseGenesHit': '어느 처방이든 적중한 질병 유전자',
      'result.aiFeature': '항목',
      'result.aiFinding': '분석 결과',
      'result.aiRowDriver': '주요 원인',
      'result.aiRowTissue': '주요 조직',
      'result.aiRowConsequence': '주요 결과',
      'result.warnings': '경고:',
      'result.rxLabel': '처방',
      'result.kpiHerbGenes': '약재 유전자 (전체)',
      'result.kpiCommonGenes': '공통 유전자',
      'result.intersectingTargets': '교차 유전자 타겟',
      'result.legendClinGenThis': 'ClinGen 검증 (이 질병)',
      'result.legendClinGenOther': 'ClinGen (다른 질병)',
      'result.legendOther': '기타',
      'result.legendSharedAll': '모든 질병 공유',
      'result.hoverEvidence': '유전자에 마우스를 올리면 근거 표시',
      'result.noIntersecting': '교차 타겟을 찾을 수 없습니다',
      'result.vennNote2': '각 숫자 = 해당 처방 조합에만 해당하는 질병 연관 유전자 · 중앙 = 모든 처방이 적중',
      'result.vennDiseaseGenes': '질병 유전자',
      'result.vennHerbGenes': '약재 유전자',
      'result.vennOverlapNote': '겹침 = 이 처방이 표적으로 하는 질병 연관 유전자',
      'result.kpiSharedAllRx': '모든 처방 공유',
      'result.aiLoading': 'AI로 경로 분석 중...',
      'result.viewDetailed': '상세 분석 보기',
      'result.hideDetailed': '상세 분석 숨기기',
      'result.showRationale': '근거 보기',
      'result.hideRationale': '근거 숨기기',
      'result.analysisFailed': '분석 실패',
      'result.errorOccurred': '오류가 발생했습니다',
      'result.retry': '다시 시도',
      'result.apiKeyRequired': 'API 키 필요',
      'result.setGeminiKey': 'AI 분석을 사용하려면 Gemini API 키를 설정하세요:',
      'result.getFreeKey': '무료 키 받기:',
      'result.diagnosticSupport': '진단 지원',
      'result.generatingQuestions': '임상 질문 생성 중...',
      'result.clinicalUnavailable': '경로 분석이 완료되면 임상 질문이 생성됩니다.',
      'result.suspectedDriver': '추정 동인:',
      'result.group': '그룹 {n}',
      'result.analysisPending': '분석 대기 중',
      'result.noComparisonData': '비교 표 데이터가 없습니다.',
      'result.noAnalysisResults': '분석 결과가 없습니다',
      'result.noEnrichmentData': '강화 분석 데이터가 없습니다. 이 처방은 유의한 유전자-질병 연관성이 없을 수 있습니다.',
      'result.aiAnalysisFailed': 'AI 분석에 실패했습니다',
      'result.noSummaryData': '요약 데이터가 없습니다',
      'result.failedInitAi': 'AI 초기화에 실패했습니다',
      'result.resultsCount': '{n}개 결과',
      'result.colTerm': '용어',
      'result.colPvalue': 'P-값',
      'result.colScoreEnr': '점수',
      'result.noSignificant': '유의한 강화 결과가 없습니다',
      'result.overlapIntro': '위 강화 분석은 각 처방의 질병 관련("공통") 유전자를 기준으로 계산됩니다. 이 패널은 해당 타겟들이 어떻게 겹치는지 — 모든 처방이 공유하는 핵심 타겟과 단일 처방에만 해당하는 타겟 — 을 보여줍니다.',
      'result.coreTargets': '핵심 타겟 — 모든 처방이 공유',
      'result.noSingleCore': '모든 처방이 공유하는 단일 타겟이 없습니다.',
      'result.distinctiveTargets': '구별되는 타겟 — 단일 처방에만 해당',
      'result.distinctiveCount': '{n}개 구별',
      'result.noneOverlaps': '— 없음 (다른 처방과 완전히 겹침)',

      /* ---- error pages (Phase 2) ---- */
      'error.t404': '페이지를 찾을 수 없습니다',
      'error.m404': '해당 페이지가 존재하지 않거나 이동되었습니다.',
      'error.t500': '문제가 발생했습니다',
      'error.m500': '예상치 못한 오류가 발생했습니다.'
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
