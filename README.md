# 🫁 Pulmonary Nodule Classifier

An end-to-end NLP pipeline that reads raw radiology reports and automatically classifies pulmonary nodules according to two major clinical guidelines — **Fleischner Society 2017** and **Lung-RADS v2022** — outputting structured management recommendations with detailed clinical reasoning.

Built as part of a pre-assignment for **[Qure.ai](https://qure.ai)** — an AI medical imaging company.

---

## What It Does

Radiologists produce free-text CT reports. This pipeline reads those reports, extracts every clinically relevant feature using rule-based NLP, and applies the correct guideline to produce a structured output — the same classification a trained physician would produce.

```
Raw radiology report (free text)
           │
           ▼
    report_parser.py          ← NLP: extract age, size, risk factors, S-modifier findings...
           │
           ▼
   classifier_engine.py       ← Logic: apply Fleischner 2017 or Lung-RADS v2022
           │
           ▼
      pipeline.py             ← I/O: read CSV → classify → write CSV
           │
           ▼
output_assignment_cases_updated.csv  ← Structured output with categories + reasoning
```

**Input:** `assignment_cases.csv` — 20 cases, each with a full CT report and blank answer columns  
**Output:** `output_assignment_cases_updated.csv` — same file, every answer column filled

---

## Guidelines Implemented

### Fleischner Society 2017 (Cases F-1 to F-10)
For **incidental** pulmonary nodules found on CT ordered for any non-screening reason.

| Step | What the code does |
|---|---|
| Eligibility check | 4-gate filter: age ≥ 36, no known cancer, not immunocompromised, not a screening exam |
| Risk stratification | 8 risk factors → Low Risk or High Risk (any single factor = High) |
| Nodule characterization | Type (Solid/GGN/Part-Solid), average diameter `(long + short) / 2`, count |
| Guideline table | 3 size brackets × 2 counts × 2 risk levels = 12 possible outcomes for solid nodules |
| Special cases | Incomplete evaluation, stability confirmed at follow-up, perifissural nodules |

**Key size thresholds (solid nodules):**
- `< 6 mm` → Low risk: no follow-up; High risk: optional CT at 12 months
- `6–8 mm` → Low risk: CT 6–12 months (then done); High risk: CT 6–12 months + 18–24 months
- `> 8 mm` → Both risks: CT 3 months / PET-CT / biopsy (high risk has lower threshold for PET/biopsy)

> ⚠️ **Critical edge case:** `8.0 mm` falls in the `6–8 mm` bracket. `> 8 mm` requires *strictly* greater than 8.0 mm. This is intentional Fleischner design and a common clinical exam question.

### Lung-RADS v2022 (Cases L-1 to L-10)
For pulmonary nodules found on **dedicated lung cancer screening** low-dose CT (LDCT).

| Category | Name | Solid nodule size (baseline) | Action |
|---|---|---|---|
| 1 | Negative | No nodules / only calcified | 12-month LDCT |
| 2 | Benign | < 6 mm | 12-month LDCT |
| 3 | Probably Benign | 6–< 8 mm | 6-month LDCT |
| 4A | Suspicious | 8–< 15 mm | 3-month LDCT |
| 4B | Very Suspicious | ≥ 15 mm | Diagnostic CT / PET / biopsy |
| 4X | Very Suspicious + features | Any 3/4 with spiculation, lymphadenopathy, metastases | Same as 4B |
| S modifier | Significant finding | Any category | Appended as e.g. `2S`, `4AS` — does not change nodule number |

> **Key concept:** The same nodule size gets a *higher* category if it's **new** vs at baseline. A 5 mm nodule at baseline = Category 2. The same 5 mm nodule if *new* = Category 3. Being new increases suspicion.

---

## Architecture

### `report_parser.py` — The NLP Layer
Converts free-text reports to structured dicts. Zero clinical logic here.

**Negation detection** is the hardest problem. Two levels:

- **Window-based `_negated()`** — checks 70 characters before a match for negation words (`no`, `without`, `absence of`, `negative for`). Used for most findings.
- **Sentence-level `_sentence_negated()`** — used for S-modifier findings (coronary calcification, pericardial effusion, aortic aneurysm). Prevents cross-sentence bleed: `"No substantial pericardial effusion. Coronary artery calcification is evident."` correctly returns `pericardial=False`, `coronary=True`.

**Size extraction priority cascade:**
1. Two-axis measurement near a priority keyword (`dominant`, `largest`, `spiculated`, `measuring`)
2. Any two-axis measurement in the report (largest wins)
3. Single-axis near `measuring`, `diameter`, `mean`
4. Fallback: 0mm → triggers incomplete evaluation downstream

**Nodule type priority order:** `Part-Solid > GGN > Solid`
Part-Solid is checked first because it contains both solid and GGN components — checking GGN first would misclassify it. GGN is excluded when mentioned in a negative context (`"No ground-glass opacities"` → `Solid`).

### `classifier_engine.py` — The Logic Layer
Pure classification, no text parsing. Works only with the clean dict from the parser.

```python
def classify(patient: dict) -> dict:
    if patient.get("is_screening"):
        return run_lung_rads(patient)
    else:
        return run_fleischner(patient)
```

The Fleischner engine runs as a strict sequential pipeline:
```
_eligible() → _risk() → size calculation → special case check → _solid_table() / _subsolid_table()
```

The Lung-RADS engine runs as:
```
nodule type router → _lr_solid() / _lr_part_solid() / _lr_ggn() → _check_4x() → _s_modifier()
```

### `pipeline.py` — The Orchestrator
Connects the other two modules to files. The dependency graph is strictly one-directional:

```
pipeline.py
    ├── imports parse_report  from report_parser.py
    └── imports classify      from classifier_engine.py

report_parser.py      ← no project imports
classifier_engine.py  ← no project imports
```

Neither `report_parser.py` nor `classifier_engine.py` imports from each other. This means you can test either module independently of the other.

---

## Project Structure

```
.
├── pipeline.py               # Entry point — run this
├── report_parser.py          # NLP: free text → structured patient dict
├── classifier_engine.py      # Logic: patient dict → classification result
├── assignment_cases.csv      # Input: 20 cases with blank answer columns
├── assignment_cases_updated.csv  # Output: all answers filled
└── README.md
```

---

## Usage

```bash
# Clone the repo
git clone https://github.com/stormothecyborg/Pulmonary-Nodule-Classification-Assignment
cd Pulmonary-Nodule-Classification-Assignment

# No dependencies beyond the Python standard library
python3 pipeline.py
```

Output is written to EXCEL file `assignment_cases_updated.xlsx` and CSV `output_assignment_cases_updated.csv`.

### Use the classifier directly

```python
from report_parser import parse_report
from classifier_engine import classify

report = """
PATIENT: 68M, 45 pack-year smoker, emphysema.
CT CHEST: New 7 mm solid nodule right upper lobe.
COMPARISON: Prior CT January 2023.
"""

patient = parse_report(report, "Fleischner")
result  = classify(patient)

print(result["category"])          # Single Solid 6–8 mm — High Risk
print(result["recommendation"])    # CT at 6–12 months; then CT at 18–24 months
print(result["reasoning"])         # Full step-by-step reasoning string
```

```python
# Lung-RADS example
patient = parse_report(report, "Lung-RADS")
result  = classify(patient)

print(result["lung_rads_category"])   # 3S
print(result["S_modifier_findings"])  # ['Coronary artery calcification']
print(result["screen_result"])        # Positive
```

---

## Key Clinical Edge Cases Handled

| Case | Issue | How it's handled |
|---|---|---|
| F-3 | 7mm nodule, stable at 11 months — why no further follow-up? | `stable_on_followup=True` triggers a special branch: current CT *is* the required 6–12 month follow-up; surveillance complete |
| F-6 | Abdominal CT with limited lung coverage | `incomplete_evaluation=True` → cannot apply Fleischner → get dedicated chest CT first |
| F-7 | Low-dose technique but NOT a screening exam | `is_screening` is set by the *clinical indication*, not the imaging technique |
| F-7 | 8mm nodule — which bracket? | `<= 8` check → 6–8mm bracket. `> 8mm` requires strictly > 8.0mm |
| L-4 | Growing 11mm nodule | `growing` + `size >= 8` → Category 4B (growth is the dominant feature, not baseline size) |
| L-7 | 11.6mm nodule, stable at follow-up | Lung-RADS downgrades: 4A stable at 3-month follow-up → Category 3, not 2 |
| L-1/L-5/L-9 | No nodule or only calcified nodule | `no_nodule=True` or `benign_calcification=True` → Category 1 |
| Any L case | Coronary calcification, vertebral fracture, pericardial effusion | S modifier appended — does not change the nodule category number |

---

## Known Limitations

- **Rule-based NLP** — the parser uses regex patterns, not a trained NLP model. It handles the report formats in this dataset well, but may need pattern additions for differently structured reports.
- **Single dominant nodule** — the pipeline classifies based on the most suspicious nodule. In multi-nodule cases it uses the largest nodule to determine timing, per both guidelines.
- **No DICOM integration** — classification is based on report text only. Actual size measurements from imaging would be more accurate.
- **Guideline versions** — implements Fleischner 2017 and Lung-RADS v2022 specifically. Future guideline updates would require engine changes.

---

## Requirements

- Python 3.7+
- Standard library only (`re`, `csv`, `os`, `sys`)
- No external dependencies

---

## References

- MacMahon H, et al. *Guidelines for Management of Incidental Pulmonary Nodules Detected on CT Images.* Radiology. 2017.
- American College of Radiology. *Lung-RADS Version 2022.* ACR, 2022.
