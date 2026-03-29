# Test Coverage Analysis — ValidPay-ASBC

## Current State

**Test coverage: 0%** — The project has no test files, no test framework configured, and no test dependencies installed.

---

## Testable Units Identified

The application (`validapay.py`, 496 lines) contains several pure functions and logical blocks that can and should be tested.

### 1. `normaliser_texte(valeur)` (line 52) — **Priority: HIGH**

Normalizes text by stripping whitespace, converting to uppercase, and collapsing multiple spaces.

**What to test:**
- Standard input → uppercase, trimmed
- Extra internal whitespace collapsed
- Leading/trailing whitespace removed
- Non-string inputs (numbers, None, NaN)
- Empty string input
- Already-normalized input (idempotency)

---

### 2. `nettoyer_telephone(valeur)` (line 56) — **Priority: HIGH**

Strips non-digit characters from phone numbers.

**What to test:**
- Pure digit input unchanged
- Letters and special characters removed
- Mixed alphanumeric input (e.g., `"70aa5522"` → `"70005522"` — note: letters become nothing, not zeros)
- Spaces, dashes, dots removed
- Empty string / None / NaN handling
- Float-like input (e.g., `"70123456.0"`)

---

### 3. `valider_format_tel(val)` (line 117) — **Priority: HIGH**

Validates phone numbers: must be exactly 8 digits, purely numeric.

**What to test:**
- Valid 8-digit number → `"OK"`
- Alphanumeric input → `"Alphanumérique"`
- Too short / too long → `"Longueur Incorrecte"`
- Empty string
- Whitespace-only input
- Number with leading/trailing spaces (the function does `.strip()`)

---

### 4. Validation Logic (`executer_validation()`, line 111) — **Priority: CRITICAL**

The core business logic that assigns statuses: `Valide`, `Erreur Format Tel`, `Absent`, `Doublon`, `Quota Village Dépassé`.

**What to test:**
- A record present in reference → `Valide`
- A record absent from reference → `Absent`
- Duplicate records → `Doublon`
- Invalid phone format → `Erreur Format Tel`
- Village with >2 ASBCs → `Quota Village Dépassé`
- **Priority ordering**: Absent overrides phone error; Doublon overrides Absent; Village quota overrides all
- Empty dataframes
- Single-row dataframes
- All-valid scenario
- All-invalid scenario

---

### 5. `construire_contexte_ia(dataframe)` (line 364) — **Priority: MEDIUM**

Builds an AI prompt context string from validation results.

**What to test:**
- Returns fallback message when dataframe is None
- Returns fallback when `Statut_ValidaPay` column missing
- Correct statistics extraction (total agents, anomaly rate)
- Geographic column auto-detection (`district`, `ds`, `région`, `province`)
- Output contains expected structured sections

---

### 6. `reponse_assistant_local(dataframe, question)` (line 400) — **Priority: MEDIUM**

Generates a local (non-API) analysis response.

**What to test:**
- Returns fallback message when dataframe is None
- Returns fallback when column missing
- Correct calculation of rejection count and anomaly rate
- Question text appears in the response
- Geographic breakdown included when geo column exists
- Zero-anomaly scenario

---

### 7. Correction Logic (lines 158–224) — **Priority: HIGH**

Generates a journal of proposed corrections and applies them.

**What to test:**
- Text normalization corrections are detected and journaled
- Phone cleaning corrections are detected and journaled
- Only fixable phone numbers (resulting in valid 8-digit) are proposed
- No corrections proposed when data is already clean
- Corrections are correctly applied to the dataframe
- `CLE_UNIQUE` is recalculated after corrections

---

### 8. Geographic Column Auto-Detection (line 277) — **Priority: LOW**

Searches column names for keywords like `district`, `ds`, `région`, `province`.

**What to test:**
- Column named `"District Sanitaire"` → detected
- Column named `"DS"` → detected
- Column named `"Région"` → detected
- No matching column → returns None
- Case insensitivity

---

### 9. Excel Export Logic (lines 293–338) — **Priority: MEDIUM**

Generates colored Excel reports.

**What to test:**
- Valid rows get green fill, invalid rows get red fill
- `CLE_UNIQUE` column is excluded from export
- Valid-only export contains no rejected records
- Correction journal export contains all logged corrections
- Files are valid `.xlsx` (can be re-read by openpyxl)

---

## Recommended Test Strategy

### Phase 1 — Unit Tests (immediate)
Extract pure functions and test them in isolation:
- `normaliser_texte`
- `nettoyer_telephone`
- `valider_format_tel`
- `construire_contexte_ia`
- `reponse_assistant_local`

### Phase 2 — Validation Logic Tests (high priority)
Create test DataFrames and verify the full validation pipeline:
- Status assignment correctness
- Priority ordering of statuses
- Edge cases (empty data, all duplicates, etc.)

### Phase 3 — Correction Logic Tests
- Verify correction detection and journal generation
- Verify correction application and re-validation

### Phase 4 — Export Tests
- Verify Excel file generation and formatting
- Verify data integrity in exported files

### Phase 5 — Integration Tests (optional, requires Streamlit test harness)
- End-to-end file upload → validation → export flow
- AI chatbot context building and fallback behavior

---

## Recommended Refactoring for Testability

The current codebase has all logic in a single file interleaved with Streamlit UI code. To enable proper testing:

1. **Extract business logic** into a separate module (e.g., `validation.py`) with pure functions that accept DataFrames and return results — no Streamlit dependencies.
2. **Extract AI helpers** into a separate module (e.g., `ai_assistant.py`).
3. **Extract export logic** into a separate module (e.g., `export.py`).
4. Keep `validapay.py` as the thin Streamlit UI layer that calls these modules.

This separation enables testing business logic without needing to mock Streamlit.
