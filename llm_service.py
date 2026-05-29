"""
LLM Service for AI-powered pathway analysis using Google Gemini API.
Returns structured JSON with summary_table, detailed_analysis, and clinical_questions.
"""
import requests
import json
import re
import traceback
from config import Config


def get_gemini_response(prompt: str) -> str:
    """
    Send a prompt to Google Gemini API and get a response.
    """
    api_key = Config.GEMINI_API_KEY
    
    if not api_key:
        print("[LLM] Error: No Gemini API key configured")
        return None
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={api_key}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    data = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 4096
        }
    }
    
    try:
        print(f"[LLM] Sending request to Gemini API (prompt length: {len(prompt)} chars)...")
        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=90,
            verify=Config.EXTERNAL_API_VERIFY_SSL
        )
        
        if not response.ok:
            print(f"[LLM] API Error: Status {response.status_code}")
            print(f"[LLM] Response: {response.text[:500]}")
            return None
        
        result = response.json()
        
        if "candidates" in result and len(result["candidates"]) > 0:
            candidate = result["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                parts = candidate["content"]["parts"]
                if len(parts) > 0 and "text" in parts[0]:
                    text = parts[0]["text"]
                    print(f"[LLM] Received response (length: {len(text)} chars)")
                    return text
        
        # Check for blocked content or safety issues
        if "candidates" in result and len(result["candidates"]) > 0:
            candidate = result["candidates"][0]
            if "finishReason" in candidate and candidate["finishReason"] != "STOP":
                print(f"[LLM] Finish reason: {candidate['finishReason']}")
        
        print(f"[LLM] Unexpected response structure: {str(result)[:500]}")
        return None
        
    except requests.exceptions.Timeout:
        print("[LLM] API request timed out (90s)")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[LLM] API Request Error: {str(e)}")
        return None
    except Exception as e:
        print(f"[LLM] Unexpected Error: {str(e)}")
        traceback.print_exc()
        return None


def extract_json_from_response(text: str) -> dict:
    """
    Extract JSON object from LLM response text.
    Handles cases where JSON is wrapped in markdown code blocks.
    Also cleans control characters that can break JSON parsing.
    """
    if not text:
        return None
    
    # Try to find JSON in code blocks first
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to find raw JSON object
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            json_str = json_match.group(0)
        else:
            return None
    
    # Clean control characters that break JSON parsing
    # Replace actual newlines/tabs inside strings with escaped versions
    # First, we need to handle the JSON more carefully
    def clean_json_string(s):
        # Remove or replace problematic control characters
        # Keep \n, \r, \t as they're valid in JSON when escaped
        cleaned = s
        # Replace unescaped control characters (ASCII 0-31 except \t \n \r)
        for i in range(32):
            if i not in (9, 10, 13):  # tab, newline, carriage return
                cleaned = cleaned.replace(chr(i), '')
        return cleaned
    
    json_str = clean_json_string(json_str)
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        # Try a more aggressive cleanup: replace all control chars in string values
        try:
            # Try to fix common issues: unescaped newlines in strings
            # Replace literal newlines that might be inside JSON strings
            fixed = re.sub(r'(?<!\\)\n', '\\n', json_str)
            fixed = re.sub(r'(?<!\\)\r', '\\r', fixed)
            fixed = re.sub(r'(?<!\\)\t', '\\t', fixed)
            return json.loads(fixed)
        except json.JSONDecodeError as e2:
            print(f"JSON parse error after cleanup: {e2}")
            # Last resort: try to extract just the structure
            try:
                # Remove all newlines and extra whitespace
                compact = ' '.join(json_str.split())
                return json.loads(compact)
            except:
                print(f"[LLM] Could not parse JSON even after cleanup")
                return None


def format_enrichment_data_for_llm(enrichment_results: list, top_n: int = 10) -> str:
    """
    Format enrichment results into a readable format for LLM analysis.
    """
    if not enrichment_results:
        return "No enrichment data available."
    
    lines = []
    for i, result in enumerate(enrichment_results[:top_n], 1):
        term = result.get('term', 'Unknown')
        p_value = result.get('adjusted_p_value', result.get('p_value', 'N/A'))
        score = result.get('combined_score', 'N/A')
        
        if isinstance(p_value, (int, float)):
            p_value = f"{p_value:.2e}"
        if isinstance(score, (int, float)):
            score = f"{score:.1f}"
            
        lines.append(f"{i}. {term} (p-value: {p_value}, score: {score})")
    
    return "\n".join(lines)


def format_clingen_data_for_llm(prescriptions: list) -> str:
    """
    Format official ClinGen validity data and clearly labeled local fallback buckets.
    """
    if not prescriptions:
        return "No official ClinGen validity data available."
    
    lines = []
    official_count = 0
    fallback_count = 0
    for rx in prescriptions:
        rx_idx = rx.get('index', '?')
        herbs = ", ".join(rx.get('herbs', []))
        lines.append(f"### Prescription {rx_idx} (Herbs: {herbs})")
        
        validity_map = rx.get('common_genes_validity', {})
        if not validity_map:
            lines.append("  No common genes or validity data found.")
            continue
        
        official_by_level = {}
        fallback_genes = []
        
        for gene, info in validity_map.items():
            clingen = info.get('clingen', {})
            level = clingen.get('level', 'Limited')
            score = info.get('score', 0.0)
            if clingen.get('source') == 'clingen':
                official_by_level.setdefault(level, []).append((gene, score, clingen))
                official_count += 1
            else:
                fallback_genes.append((gene, score, level))
                fallback_count += 1
        
        has_official_genes = False
        for level in ['Definitive', 'Strong', 'Moderate', 'Limited']:
            genes = official_by_level.get(level, [])
            if genes:
                has_official_genes = True
                genes.sort(key=lambda x: x[1], reverse=True)
                genes_str = ", ".join([
                    f"{gene} (ClinGen: {clingen.get('classification', level)}, DisGeNET score: {score})"
                    for gene, score, clingen in genes
                ])
                lines.append(f"  * **Official ClinGen {level} targets**: {genes_str}")
        
        if fallback_genes:
            fallback_genes.sort(key=lambda x: x[1], reverse=True)
            fallback_str = ", ".join([
                f"{gene} ({level} DisGeNET score bucket, score: {score})"
                for gene, score, level in fallback_genes[:12]
            ])
            lines.append(f"  * **Not ClinGen - local fallback only**: {fallback_str}")
        
        if not has_official_genes and not fallback_genes:
            lines.append("  No common genes or validity data found.")
    
    if official_count == 0:
        lines.insert(
            0,
            "No official ClinGen validity matches were found. Any listed fallback buckets are local DisGeNET score buckets, not ClinGen evidence."
        )
    else:
        lines.insert(
            0,
            f"Official ClinGen matches found: {official_count}. Local fallback-only genes: {fallback_count}."
        )
                
    return "\n".join(lines)


def generate_comparative_analysis(disease_name: str, prescription_data: dict, clingen_context: str = None) -> dict:
    """
    Generate comparative analysis with summary table and detailed analysis.
    Uses the exact prompt format specified.
    """
    # Format each group's data
    groups_text = []
    num_groups = len(prescription_data)
    
    for i, (label, data) in enumerate(prescription_data.items(), 1):
        formatted = format_enrichment_data_for_llm(data)
        groups_text.append(f"**Group {i} ({label}):**\n{formatted}")
    
    all_groups = "\n\n".join(groups_text)
    
    # Build dynamic column names
    group_columns = ", ".join([f'"Group {i}"' for i in range(1, num_groups + 1)])
    
    clingen_section = ""
    if clingen_context and "Official ClinGen matches found" in clingen_context:
        clingen_section = f"""
### CLINICAL GENE VALIDITY EVIDENCE (CLINGEN)
The following official ClinGen Gene-Disease Validity data has been matched to common target genes. Items labeled "Not ClinGen" are local DisGeNET score buckets only and must be treated as low-confidence fallback context:

{clingen_context}

CRITICAL MOA REASONING RULES:
1. **Prioritize Official ClinGen Targets**: Base primary therapeutic mechanism hypotheses on official ClinGen 'Definitive' and 'Strong' targets only.
2. **Exercise Skepticism on Weak or Fallback Targets**: Treat 'Limited', 'Moderate', and all "Not ClinGen" DisGeNET score buckets as speculative or low-confidence associations only.
3. **Clinical Integration**: Explain how the high-confidence targets interact with standard pathological pathways of {disease_name}.
"""
    
    prompt = f"""You are an expert Research Scientist in pathology and bioinformatics. Your task is to perform a comparative analysis of multiple disease clusters provided by the user.

The user is studying **{disease_name}** with the following enrichment analysis results:

{all_groups}
{clingen_section}

You must return your response in a strict JSON format with exactly two keys: "summary_table" and "detailed_analysis".

1. "summary_table":
   - An array of objects representing the rows of a comparison table.
   - Each object must have the keys: "Feature", {group_columns}.
   - Include rows for: "Primary Driver", "Key Tissue", "Main Consequence", and "Cancer Risk".
   - Keep the values in this table concise (under 10 words).

2. "detailed_analysis":
   - A single string containing a comprehensive, Markdown-formatted report.
   - This report must include:
     - "1. The High-Level Comparison": A brief summary of the fundamental differences.
     - "2. Deep Dive into Pathways": A detailed breakdown of the mechanism for each group (Group 1, Group 2, Group 3).
     - Use bolding and bullet points for readability.

Do not include any text outside the JSON object."""

    response_text = get_gemini_response(prompt)
    
    if not response_text:
        return None
    
    parsed = extract_json_from_response(response_text)
    
    if parsed and 'summary_table' in parsed and 'detailed_analysis' in parsed:
        return parsed
    
    # Fallback if parsing failed
    return {
        'summary_table': [],
        'detailed_analysis': response_text if response_text else "Analysis could not be generated.",
        'parse_error': True
    }


def generate_clinical_questions(disease_name: str, prescription_data: dict, clingen_context: str = None) -> list:
    """
    Generate clinical interview questions for diagnosis.
    Returns a structured JSON array with group cards.
    """
    # Format the analysis summary for context
    groups_text = []
    num_groups = len(prescription_data)
    
    for i, (label, data) in enumerate(prescription_data.items(), 1):
        formatted = format_enrichment_data_for_llm(data, top_n=5)
        groups_text.append(f"**Group {i} ({label}):**\n{formatted}")
    
    all_groups = "\n\n".join(groups_text)
    
    clingen_section = ""
    if clingen_context and "Official ClinGen matches found" in clingen_context:
        clingen_section = f"""
### CLINICAL GENE VALIDITY EVIDENCE (CLINGEN)
To ensure questions address clinically validated pathology, target your questions toward pathways driven by official ClinGen validated genes. Items labeled "Not ClinGen" are local DisGeNET fallback buckets only:

{clingen_context}

CRITICAL DIAGNOSTIC QUESTION RULES:
1. Focus questions on clinical features or comorbidities associated with official ClinGen **Definitive** and **Strong** gene targets.
2. Avoid formulating primary screening questions around pathways driven solely by **Limited**, weak, or "Not ClinGen" fallback targets.
"""
    
    prompt = f"""You are a senior clinical diagnostician. Your task is to analyze the provided disease groups and generate a structured clinical interview guide.

The patient is being evaluated for **{disease_name}**. Here are the enrichment analysis results showing associated conditions and pathways:

{all_groups}
{clingen_section}

You must return your response in a strict JSON format. 
The JSON must be a single list (array) of objects, where each object represents one disease group.

Each object in the list must contain exactly these keys:
1. "group_label": A short, descriptive title for the group (e.g., "Group 1: Vascular & Tobacco").
2. "suspected_driver": A concise summary of the underlying pathology (e.g., "Systemic Nicotine Toxicity").
3. "clinical_questions": An array of strings. Each string is a specific high-yield question the doctor should ask the patient.
4. "rationale_hidden": A Markdown-formatted string explaining *why* these questions are critical and what the doctor should look for. This will be shown only when requested.

Example Structure:
[
  {{
    "group_label": "Group 1...",
    "suspected_driver": "...",
    "clinical_questions": ["Question 1?", "Question 2?"],
    "rationale_hidden": "**Why this matters:** This tests for..."
  }}
]

Generate exactly {num_groups} group objects, one for each prescription group.

Do not include any text outside the JSON array."""

    response_text = get_gemini_response(prompt)
    
    if not response_text:
        return None
    
    # Try to parse JSON array from response
    parsed = extract_json_array_from_response(response_text)
    
    if parsed and isinstance(parsed, list):
        return parsed
    
    return None


def extract_json_array_from_response(text: str) -> list:
    """
    Extract JSON array from LLM response text.
    Handles cases where JSON is wrapped in markdown code blocks.
    """
    if not text:
        return None
    
    # Try to find JSON in code blocks first
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to find raw JSON array
        json_match = re.search(r'\[[\s\S]*\]', text)
        if json_match:
            json_str = json_match.group(0)
        else:
            return None
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        return None


def generate_single_prescription_analysis(disease_name: str, enrichment_data: list, clingen_context: str = None) -> dict:
    """
    Generate analysis for a single prescription (when only one Rx is provided).
    """
    formatted_data = format_enrichment_data_for_llm(enrichment_data)
    
    clingen_section = ""
    if clingen_context and "Official ClinGen matches found" in clingen_context:
        clingen_section = f"""
### CLINICAL GENE VALIDITY EVIDENCE (CLINGEN)
The following official ClinGen Gene-Disease Validity data has been matched to target genes. Items labeled "Not ClinGen" are local DisGeNET score buckets only:

{clingen_context}

CRITICAL MOA REASONING RULES:
1. **Prioritize Official ClinGen Targets**: Base mechanism hypotheses on official ClinGen 'Definitive' and 'Strong' targets.
2. **Exercise Skepticism on Weak or Fallback Targets**: Treat 'Limited', 'Moderate', and all "Not ClinGen" fallback buckets as speculative or low-confidence.
3. **Pathology Relevance**: Connect high-confidence targets explicitly to the standard pathological process of {disease_name}.
"""
    
    prompt = f"""You are an expert Research Scientist in pathology and bioinformatics. Analyze the gene enrichment results for a traditional Chinese medicine prescription targeting **{disease_name}**.

Enrichment Results:
{formatted_data}
{clingen_section}

You must return your response in a strict JSON format with exactly two keys: "summary_table" and "detailed_analysis".

1. "summary_table":
   - An array of objects with keys: "Feature", "Finding".
   - Include rows for: "Primary Driver", "Key Tissue", "Main Consequence", "Cancer Risk".
   - Keep values concise (under 10 words).

2. "detailed_analysis":
   - A Markdown-formatted report including:
     - "1. Key Findings": Main discoveries from the enrichment analysis.
     - "2. Mechanism of Action": How the prescription may work for {disease_name}.
     - Use bolding and bullet points for readability.

Do not include any text outside the JSON object."""

    response_text = get_gemini_response(prompt)
    
    if not response_text:
        return None
    
    parsed = extract_json_from_response(response_text)
    
    if parsed and 'summary_table' in parsed and 'detailed_analysis' in parsed:
        return parsed
    
    return {
        'summary_table': [],
        'detailed_analysis': response_text if response_text else "Analysis could not be generated.",
        'parse_error': True
    }


def generate_single_clinical_questions(disease_name: str, enrichment_data: list, clingen_context: str = None) -> list:
    """
    Generate clinical questions for a single prescription.
    Returns a structured JSON array with one group card.
    """
    formatted_data = format_enrichment_data_for_llm(enrichment_data, top_n=8)
    
    clingen_section = ""
    if clingen_context and "Official ClinGen matches found" in clingen_context:
        clingen_section = f"""
### CLINICAL GENE VALIDITY EVIDENCE (CLINGEN)
To ensure questions address clinically validated pathology, target your questions toward pathways driven by official ClinGen validated genes. Items labeled "Not ClinGen" are local DisGeNET fallback buckets only:

{clingen_context}

CRITICAL DIAGNOSTIC QUESTION RULES:
1. Focus questions on clinical symptoms associated with official ClinGen **Definitive** and **Strong** targets.
2. Avoid clinical screening questions for pathways driven only by **Limited**, weak, or "Not ClinGen" fallback targets.
"""
    
    prompt = f"""You are a senior clinical diagnostician. Your task is to analyze the provided disease pathway data and generate a structured clinical interview guide.

The patient is being evaluated for **{disease_name}**. Here are the enrichment analysis results:

{formatted_data}
{clingen_section}

You must return your response in a strict JSON format. 
The JSON must be a single list (array) containing exactly ONE object representing this analysis.

The object must contain exactly these keys:
1. "group_label": A short, descriptive title (e.g., "Prescription Analysis: Key Pathways").
2. "suspected_driver": A concise summary of the underlying pathology being screened.
3. "clinical_questions": An array of strings. Each string is a specific high-yield question the doctor should ask the patient. Include 5-8 questions.
4. "rationale_hidden": A Markdown-formatted string explaining *why* these questions are critical and what the doctor should look for. This will be shown only when requested.

Example Structure:
[
  {{
    "group_label": "Prescription Analysis...",
    "suspected_driver": "...",
    "clinical_questions": ["Question 1?", "Question 2?", ...],
    "rationale_hidden": "**Why this matters:** This tests for..."
  }}
]

Do not include any text outside the JSON array."""

    response_text = get_gemini_response(prompt)
    
    if not response_text:
        return None
    
    parsed = extract_json_array_from_response(response_text)
    
    if parsed and isinstance(parsed, list):
        return parsed
    
    return None


def generate_full_ai_analysis(disease_name: str, results: dict) -> dict:
    """
    Generate complete AI analysis with:
    - summary_table: Comparison table data
    - detailed_analysis: Full markdown analysis
    - clinical_questions: Diagnostic interview questions
    """
    print(f"[LLM] Starting AI analysis for disease: {disease_name}")
    
    ai_results = {
        'summary_table': [],
        'detailed_analysis': None,
        'clinical_questions': None,
        'has_ai_analysis': False,
        'error': None
    }
    
    # Check if API key is configured
    if not Config.GEMINI_API_KEY:
        ai_results['error'] = "Gemini API key not configured"
        print("[LLM] Error: No API key configured")
        return ai_results
    
    # Extract prescription enrichment data
    prescription_enrichments = results.get('prescription_enrichments', {})
    print(f"[LLM] Found {len(prescription_enrichments)} prescription enrichments")
    
    # Extract ClinGen validity context
    prescriptions = results.get('prescriptions', [])
    clingen_context = format_clingen_data_for_llm(prescriptions)
    print(f"[LLM] Prepared ClinGen validity context: {len(clingen_context)} chars")
    
    # Debug: Print structure of enrichment data
    for rx_key, rx_data in prescription_enrichments.items():
        disgenet_data = rx_data.get('DisGeNET', [])
        print(f"[LLM] {rx_key}: {len(disgenet_data)} DisGeNET entries")
    
    if len(prescription_enrichments) > 1:
        # Multiple prescriptions - do comparative analysis
        print("[LLM] Running comparative analysis for multiple prescriptions")
        prescription_data = {}
        for rx_key, rx_data in prescription_enrichments.items():
            rx_disgenet = rx_data.get('DisGeNET', [])
            if rx_disgenet:
                prescription_data[rx_key] = rx_disgenet
        
        if prescription_data:
            print(f"[LLM] Valid prescription data for {len(prescription_data)} groups")
            # Generate comparative analysis
            analysis = generate_comparative_analysis(disease_name, prescription_data, clingen_context)
            if analysis:
                ai_results['summary_table'] = analysis.get('summary_table', [])
                ai_results['detailed_analysis'] = analysis.get('detailed_analysis', '')
                ai_results['has_ai_analysis'] = True
                print("[LLM] Comparative analysis completed successfully")
            else:
                ai_results['error'] = "Failed to generate comparative analysis"
                print("[LLM] Comparative analysis returned None")
            
            # Generate clinical questions
            clinical = generate_clinical_questions(disease_name, prescription_data, clingen_context)
            if clinical:
                ai_results['clinical_questions'] = clinical
        else:
            ai_results['error'] = "No valid enrichment data in any prescription"
            print("[LLM] Error: No valid enrichment data in prescriptions")
    
    elif len(prescription_enrichments) == 1:
        # Single prescription analysis
        rx_key = list(prescription_enrichments.keys())[0]
        rx_data = prescription_enrichments[rx_key].get('DisGeNET', [])
        print(f"[LLM] Single prescription mode: {rx_key} with {len(rx_data)} enrichment entries")
        
        if rx_data:
            # Generate single analysis
            analysis = generate_single_prescription_analysis(disease_name, rx_data, clingen_context)
            if analysis:
                ai_results['summary_table'] = analysis.get('summary_table', [])
                ai_results['detailed_analysis'] = analysis.get('detailed_analysis', '')
                ai_results['has_ai_analysis'] = True
                print("[LLM] Single prescription analysis completed successfully")
            else:
                print("[LLM] Single prescription analysis returned None")
            
            # Generate clinical questions
            clinical = generate_single_clinical_questions(disease_name, rx_data, clingen_context)
            if clinical:
                ai_results['clinical_questions'] = clinical
        else:
            ai_results['error'] = "No enrichment data available for analysis"
            print("[LLM] Error: No enrichment data in single prescription")
    
    else:
        # No prescription enrichments found
        print("[LLM] No prescription enrichments found, checking fallback...")
        
        # Fallback to general enrichment data
        enrichment = results.get('enrichment', {})
        disgenet_results = enrichment.get('DisGeNET', [])
        
        if disgenet_results:
            print(f"[LLM] Using fallback enrichment data: {len(disgenet_results)} entries")
            analysis = generate_single_prescription_analysis(disease_name, disgenet_results, clingen_context)
            if analysis:
                ai_results['summary_table'] = analysis.get('summary_table', [])
                ai_results['detailed_analysis'] = analysis.get('detailed_analysis', '')
                ai_results['has_ai_analysis'] = True
            
            clinical = generate_single_clinical_questions(disease_name, disgenet_results, clingen_context)
            if clinical:
                ai_results['clinical_questions'] = clinical
        else:
            ai_results['error'] = "No enrichment data available for analysis. Please ensure the prescription has valid gene-disease associations."
            print("[LLM] Error: No enrichment data available in any location")
    
    print(f"[LLM] Analysis complete. has_ai_analysis={ai_results['has_ai_analysis']}, error={ai_results.get('error')}")
    return ai_results
