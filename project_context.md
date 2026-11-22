# Project Context for TRAECode – Nutrition Claim Verifier (URE Project)

## 1. Project Overview

**Project Title:** Do the Claims Match the Contents? – An Audit of Nutrition Claims on Packaged Foods Sold in India

**Phase:** Implementation Phase 1 (after survey paper was accepted with <10% similarity)

**Core Goal:**  
Build a web application where a user:
1. Enters / selects a front-of-pack claim (e.g. “No Added Sugar”, “High Protein”, “100% Atta”)
2. Uploads a photo of the back-of-pack (nutrition panel + ingredients list)
3. The system uses OCR to extract the text
4. Checks the claim against official FSSAI rules
5. Tells the user whether the claim is technically compliant
6. Explains the loophole / deceptive mechanism (if any) in clear language
7. Shows similar real examples from a curated Indian product dataset

The system must stay **grounded** in:
- Official FSSAI rules (provided as JSON)
- The user’s own dataset of 25 Indian products
- The OCR text of the current product

It should **not** freely search the web or use general knowledge that could introduce bias.

---

## 2. Key Decisions Already Made

### Tech Stack (Free / Student-friendly)
- **Coding Environment:** TRAECode (ByteDance AI IDE)
- **Frontend + Quick Backend:** Streamlit (preferred for fast demo) or FastAPI
- **OCR:** PaddleOCR (PP-OCRv4) – best free option for Indian packaging
- **Rule Engine:** Custom Python logic using `fssai_phase1_rules.json`
- **Dataset:** `fmcg_label_audit_dataset.csv` (25 real Indian products with claims, ingredients, nutrition values, compliance labels, and deceptive mechanisms)
- **LLM for Explanation (Completely Free):** Groq free tier (currently strong free models such as Qwen / gpt-oss series). Fallback: DeepSeek free tier.
- **Hosting for Demo:** Streamlit Cloud or Hugging Face Spaces

### Important Constraints
- Must be completely free for the student to run and demo
- Answers must be grounded in the provided dataset + FSSAI rules
- Clear separation between “technically compliant according to FSSAI” and “deceptive / health-halo for consumers”
- Good explanations of loopholes (e.g. “No Added Sugar” but uses apple juice concentrate / dates / maltodextrin)

---

## 3. Core Files That Must / will Exist

| File | Purpose |
|------|---------|
| `fssai_phase1_rules.json` | Simplified high-priority FSSAI rules (High Protein, No Added Sugar, Sugar Free, High Fibre, prohibited claims, etc.) |
| `fmcg_label_audit_dataset.csv` | 25 real Indian products with front claims, ingredients, full nutrition panel, technical compliance, and deceptive mechanism |
| `app.py` | Main Streamlit application |
| `ocr_utils.py` | PaddleOCR extraction |
| `rule_engine.py` | Loads JSON and decides Compliant / Non-compliant |
| `dataset_utils.py` | Searches the CSV for similar products |
| `llm_utils.py` | Calls Groq with strict grounded prompt |
| `requirements.txt` | Dependencies |

---

## 4. System Architecture
User Input (Claim + Image)
↓
Streamlit Frontend
↓
PaddleOCR → Extract ingredients + nutrition text
Rule Engine (fssai_phase1_rules.json) → Technical compliance decision
Dataset lookup → Find 2–3 similar products
Free LLM (Groq) → Generate clear explanation + loophole
↓
Display:
Compliant? (Yes/No)
Which FSSAI rule was applied
Explanation of loophole
Similar real examples from dataset


## 5. FSSAI Rules Summary (Already Prepared)

The system uses a simplified Phase-1 rule set covering the most common claims:

- High Protein / Source of Protein (RDA thresholds)
- Sugar Free (≤ 0.5 g / 100g)
- Low Sugar
- No Added Sugar (strict conditions + mandatory “Contains naturally occurring sugars” disclaimer)
- High Fibre / Source of Fibre
- Low Fat
- Immediate flag for prohibited / high-risk words (“100% Pure”, “Healthy”, “Prevents”, “Cures”, “Diabetic Friendly”, “Boosts Immunity”, etc.)

Full detailed rules and the JSON versions were already created in the conversation.

---

## 6. Dataset Summary

File: `fmcg_label_audit_dataset.csv`  
Contains 25 real Indian FMCG products with columns:
- product_name, category, front_claim
- ingredients
- energy_kcal, protein_g, carbohydrates_g, total_sugars_g, added_sugars_g, dietary_fibre_g, total_fat_g, etc.
- is_technically_compliant (True/False)
- compliance_clause
- deceptive_mechanism
- severity_level

This dataset is the primary source of truth for examples and loophole patterns.

---

## 7. LLM Prompting Strategy (Critical)

The LLM must be forced to stay grounded. Use a strict system prompt:
Always pass:
- OCR text
- Rule engine decision
- 2–3 similar rows from the CSV

---

## 8. Current Status & What Needs to Be Built

**Already Done:**
- Survey paper completed and accepted
- FSSAI rules extracted and converted to JSON (full + Phase-1 simplified)
- Curated dataset of 25 products created
- Architecture and free tech stack decided
- Grounding strategy decided

**What TRAECode should help build now:**
1. Project structure and `requirements.txt`
2. `ocr_utils.py` using PaddleOCR
3. `rule_engine.py` that loads the JSON and evaluates claims
4. `dataset_utils.py` for similarity search in the CSV
5. `llm_utils.py` with Groq + strict grounded prompt
6. Main `app.py` (Streamlit) with clean UI:
   - Claim input
   - Image upload
   - Results display (compliance + explanation + similar examples)
7. Basic error handling (blurry image, missing nutrition values, etc.)
8. Simple testing flow using the existing 25 products

---

## 9. Success Criteria for Phase 1 Demo

- User can upload a real product label photo
- System correctly extracts key nutrition numbers and ingredients
- Correctly classifies the claim as Compliant / Non-compliant according to FSSAI rules
- Gives a clear, human-readable explanation of any loophole
- Shows relevant similar products from the dataset
- Runs completely free (Groq free tier + local PaddleOCR)
- Works reliably on the 25 products in the dataset

---

## 10. Important Notes for TRAECode

- Prefer simple, readable, well-commented code (student project)
- Keep the LLM strictly grounded – never let it invent product information
- Make the UI clean and presentation-ready (good for university demo)
- Add clear print/logging so debugging is easy
- Start with Streamlit for speed; we can move to FastAPI later if needed

This document contains the full context of the project up to this point. Please use it as the single source of truth while helping build the application.