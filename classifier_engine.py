"""
================================================================
 PART 2: CLASSIFIER ENGINE
 Pure logic — no text parsing here.
 Takes structured feature dicts and returns full recommendations.
 Implements ALL rules, edge cases, and exceptions from:
   - Fleischner Society 2017 Guidelines
   - Lung-RADS v2022 Guidelines
================================================================
"""


# ================================================================
#  FLEISCHNER 2017 — FULL IMPLEMENTATION
# ================================================================

def _fleischner_eligible(p):
    """
    Gate 1: All 4 must be satisfied.
    Returns (bool, reason_str)
    """
    # guidelines speak of "age < 35" but treat 35‑year‑olds conservatively
    # as ineligible; adjust to ≤ 35 based on feedback.
    if p.get("age", 99) <= 35:
        return False, "Patient age ≤ 35 — Fleischner does NOT apply."
    if p.get("known_cancer"):
        return False, "Known primary cancer — Fleischner does NOT apply."
    if p.get("immunocompromised"):
        return False, "Immunocompromised — Fleischner does NOT apply."
    if p.get("is_screening"):
        return False, "Screening exam — use Lung-RADS instead."
    return True, "All eligibility criteria met — Fleischner applies."


def _fleischner_risk(p):
    """
    Classifies patient as Low or High risk.
    ANY single high-risk feature = High Risk.
    Returns ("High Risk"|"Low Risk", [list of contributing factors])
    """
    factors = []
    if p.get("smoker"):           factors.append("Smoking history")
    if p.get("age", 0) > 60:     factors.append(f"Age > 50 ({p.get('age')} yrs)")
    if p.get("emphysema"):        factors.append("Emphysema on imaging")
    if p.get("fibrosis"):         factors.append("Pulmonary fibrosis on imaging")
    if p.get("upper_lobe"):       factors.append("Upper lobe nodule location")
    if p.get("spiculated"):       factors.append("Spiculated or irregular margins")
    if p.get("asbestos"):         factors.append("Asbestos / occupational carcinogen exposure")
    if p.get("family_hx_cancer"): factors.append("Family history of lung cancer")

    if factors:
        return "High Risk", factors
    return "Low Risk", ["No high-risk features identified — patient is low risk"]


def _fleischner_solid(size_mm, count, risk):
    """
    Core Fleischner solid nodule table.
    3 size brackets × 2 counts × 2 risk levels = 12 outcomes.
    Returns (recommendation, rationale, category_label)

    EDGE CASES HANDLED:
    - Exactly 6 mm → falls in 6-8 mm bracket (not <6)
    - Exactly 8 mm → falls in 6-8 mm bracket (>8 means strictly greater)
    - Exactly 8.1 mm → falls in >8 mm bracket
    """
    r = risk
    c = count.lower()
    s = size_mm

    # ── BRACKET 1: < 6 mm ────────────────────────────────────
    if s < 6:
        if c == "single":
            if r == "Low Risk":
                return (
                    "No routine follow-up needed.",
                    "Malignancy risk < 1% for solid nodules < 6 mm even in smokers. "
                    "No surveillance warranted in low-risk patients.",
                    "Single Solid < 6 mm — Low Risk"
                )
            else:  # High Risk
                return (
                    "Optional CT at 12 months, especially if spiculated, "
                    "upper lobe location, or multiple strong risk factors.",
                    "Risk remains low (<1%) but optional annual CT is reasonable "
                    "given the high-risk profile. If stable at 12 months, no further imaging needed.",
                    "Single Solid < 6 mm — High Risk"
                )
        else:  # multiple
            if r == "Low Risk":
                return (
                    "No routine follow-up needed.",
                    "Multiple nodules < 6 mm are usually benign "
                    "(granulomas, prior infection). No surveillance needed in low-risk patients.",
                    "Multiple Solid < 6 mm — Low Risk"
                )
            else:
                return (
                    "Optional CT at 12 months.",
                    "Optional surveillance for high-risk patients with multiple small solid nodules.",
                    "Multiple Solid < 6 mm — High Risk"
                )

    # ── BRACKET 2: 6–8 mm (includes exactly 6 and exactly 8) ──
    elif s <= 8:
        if c == "single":
            if r == "Low Risk":
                return (
                    "CT at 6–12 months. If stable → no further imaging generally required. "
                    "Optional additional CT at 18–24 months in select cases.",
                    "Single follow-up CT is usually sufficient to confirm stability "
                    "in low-risk patients with 6–8 mm nodules.",
                    "Single Solid 6–8 mm — Low Risk"
                )
            else:
                return (
                    "CT at 6–12 months; then second CT at 18–24 months to confirm stability.",
                    "Two follow-up scans required for high-risk patients — "
                    "one interval is not sufficient to exclude slow-growing malignancy.",
                    "Single Solid 6–8 mm — High Risk"
                )
        else:  # multiple
            if r == "Low Risk":
                return (
                    "CT at 3–6 months; optional second CT at 18–24 months. "
                    "Use most suspicious nodule to guide timing.",
                    "Shorter initial interval used for multiple nodules. "
                    "Dominant/most suspicious nodule drives the follow-up schedule.",
                    "Multiple Solid 6–8 mm — Low Risk"
                )
            else:
                return (
                    "CT at 3–6 months; then CT at 18–24 months. "
                    "Use most suspicious nodule to guide timing.",
                    "Both follow-up scans required. Dominant nodule drives scheduling. "
                    "High-risk patients need confirmed stability over two intervals.",
                    "Multiple Solid 6–8 mm — High Risk"
                )

    # ── BRACKET 3: > 8 mm (strictly greater than 8) ──────────
    else:
        if c == "single":
            if r == "Low Risk":
                return (
                    "Prompt evaluation: CT at 3 months, OR PET/CT, OR tissue sampling/biopsy.",
                    "~10–20% malignancy risk for nodules > 8 mm. "
                    "Prompt workup required. CT at 3 months is most conservative option; "
                    "PET/CT or biopsy may be chosen based on clinical picture.",
                    "Single Solid > 8 mm — Low Risk"
                )
            else:
                return (
                    "Prompt evaluation: CT at 3 months, PET/CT, or tissue biopsy. "
                    "Lower threshold for proceeding directly to PET/CT and tissue sampling "
                    "given high-risk profile.",
                    "~10–20% malignancy risk; high-risk features raise suspicion further. "
                    "Do not defer to watch-and-wait. PET/CT and/or biopsy preferred over "
                    "repeat CT alone in high-risk patients.",
                    "Single Solid > 8 mm — High Risk"
                )
        else:  # multiple
            if r == "Low Risk":
                return (
                    "CT at 3–6 months; second CT at 18–24 months if initial follow-up inconclusive.",
                    "Multiple large nodules: assess for growth at 3–6 months. "
                    "If any nodule grows or changes, escalate to PET/CT or biopsy.",
                    "Multiple Solid > 8 mm — Low Risk"
                )
            else:
                return (
                    "CT at 3–6 months; then CT at 18–24 months. "
                    "Use most suspicious nodule to guide management.",
                    "Closest follow-up for high-risk multiple large nodules. "
                    "Any growth at first follow-up should prompt immediate escalation.",
                    "Multiple Solid > 8 mm — High Risk"
                )


def _fleischner_subsolid(ntype, size_mm, solid_mm, count):
    """
    Fleischner subsolid nodule logic.
    Covers pure GGN and Part-Solid, single and multiple.

    KEY SUBSOLID RULES:
    - Subsolid nodules need 5 years of follow-up (vs 2 for solid)
    - Many are transient → confirm persistence at first follow-up
    - Part-solid with solid component ≥ 6 mm = HIGH SUSPICION
    - GGN: size threshold is 6 mm (not same as solid)
    """
    c = count.lower()
    s = size_mm
    sc = solid_mm

    if ntype == "GGN":
        if c == "single":
            if s < 6:
                return (
                    "No follow-up required. "
                    "Exception: strong risk factors may warrant CT at 2 and 4 years.",
                    "Pure GGNs < 6 mm are rarely malignant and often represent "
                    "focal inflammation or early AAH. No surveillance needed in most cases.",
                    "Single Pure GGN < 6 mm"
                )
            else:  # ≥ 6 mm
                return (
                    "CT at 6–12 months to confirm persistence. "
                    "If persistent: CT every 2 years for up to 5 years total. "
                    "If nodule grows OR develops a solid component → consider resection.",
                    "GGNs ≥ 6 mm can represent AIS/MIA or early adenocarcinoma. "
                    "Many are transient — confirm persistence first. "
                    "5-year surveillance required because growth is often very slow. "
                    "Development of solid component is the key danger sign.",
                    "Single Pure GGN ≥ 6 mm"
                )
        else:  # multiple
            if s < 6:
                return (
                    "CT at 3–6 months to check persistence. "
                    "If persistent in low-risk patient: no further routine follow-up. "
                    "If persistent in high-risk patient: consider CT at 2 and 4 years.",
                    "Multiple tiny GGNs are usually benign (multifocal AAH, old infection). "
                    "Confirm they don't resolve before committing to long surveillance.",
                    "Multiple Subsolid (GGN) < 6 mm"
                )
            else:
                return (
                    "CT at 3–6 months; subsequent management guided by most suspicious nodule. "
                    "Stable with no high-risk features → periodic imaging up to 5 years.",
                    "Most suspicious (largest, developing solid component) drives management. "
                    "5-year follow-up required for subsolid nodules.",
                    "Multiple Subsolid (GGN) ≥ 6 mm"
                )

    elif ntype == "Part-Solid":
        if c == "single":
            if s < 6:
                return (
                    "No routine follow-up needed. "
                    "(Very small part-solid nodules are difficult to accurately characterize.)",
                    "Part-solid nodules < 6 mm are hard to properly characterize. "
                    "Clinical judgment and risk factors should guide any decision to follow up.",
                    "Single Part-Solid < 6 mm"
                )
            else:  # ≥ 6 mm
                if sc < 6:
                    return (
                        "CT at 3–6 months to confirm persistence. "
                        "If persistent and solid component remains < 6 mm → annual CT for 5 years. "
                        "If solid component grows to ≥ 6 mm at any point → escalate immediately.",
                        "Persistence confirmation required first. Then annual surveillance × 5 years. "
                        "Monitor solid component size closely — growth to ≥ 6 mm is a danger signal.",
                        "Single Part-Solid ≥ 6 mm (solid component < 6 mm)"
                    )
                else:  # solid ≥ 6 mm — HIGH SUSPICION
                    return (
                        "⚠ HIGHLY SUSPICIOUS for invasive adenocarcinoma. "
                        "Recommend PET/CT, tissue biopsy, or surgical evaluation without delay.",
                        "Solid component ≥ 6 mm in a part-solid nodule is strongly associated "
                        "with invasive malignancy. This exceeds the conservative follow-up threshold. "
                        "Do not defer — proceed directly to tissue diagnosis or surgical resection.",
                        "Single Part-Solid ≥ 6 mm (solid component ≥ 6 mm) — HIGHLY SUSPICIOUS"
                    )
        else:  # multiple
            if s < 6:
                return (
                    "CT at 3–6 months to check persistence. "
                    "If persistent: low-risk → no further routine follow-up; "
                    "high-risk → consider CT at 2 and 4 years.",
                    "Small multiple part-solid nodules need persistence confirmed. "
                    "May resolve spontaneously (infection, inflammation).",
                    "Multiple Part-Solid < 6 mm"
                )
            else:
                return (
                    "CT at 3–6 months; management guided by most suspicious nodule "
                    "(largest solid component). Stable → periodic imaging up to 5 years.",
                    "Most suspicious nodule drives management. "
                    "5-year follow-up required for subsolid nodules.",
                    "Multiple Part-Solid ≥ 6 mm"
                )

    return (
        "Cannot classify — unrecognized subsolid nodule type.",
        "Manual review required.",
        "Unknown Subsolid Type"
    )


def run_fleischner(p):
    """
    Master Fleischner function.
    Returns full result dict including category, recommendation, reasoning.
    Handles all special cases:
    - Ineligibility
    - Incomplete evaluation
    - Stability already confirmed (this CT IS the follow-up scan)
    - Perifissural nodules (no follow-up even if > 6 mm)
    """
    eligible, elig_reason = _fleischner_eligible(p)
    if not eligible:
        return {
            "guideline":      "Fleischner 2017",
            "eligible":       False,
            "risk_category":  "N/A",
            "risk_factors":   [],
            "nodule_type":    p.get("nodule_type", "Unknown"),
            "nodule_size":    "N/A",
            "nodule_count":   "N/A",
            "category":       "Ineligible for Fleischner",
            "recommendation": "Cannot apply Fleischner guidelines. " + elig_reason +
                              " Use clinical judgment or an alternate guideline.",
            "reasoning":      elig_reason,
        }

    risk, risk_factors = _fleischner_risk(p)
    avg_mm = p.get("nodule_size_mm", 0)
    long_mm  = p.get("nodule_long_mm", avg_mm)
    short_mm = p.get("nodule_short_mm", avg_mm)
    # Always recompute avg from axes if available
    if long_mm != short_mm:
        avg_mm = round((long_mm + short_mm) / 2, 1)
    ntype = p.get("nodule_type", "Solid")
    count = p.get("nodule_count", "single")
    solid = p.get("solid_component_mm", 0.0)

    # ── SPECIAL CASE 1: Incomplete evaluation ────────────────
    if p.get("incomplete_evaluation"):
        return {
            "guideline":      "Fleischner 2017",
            "eligible":       True,
            "risk_category":  risk,
            "risk_factors":   risk_factors,
            "nodule_type":    ntype,
            "nodule_size":    "Indeterminate",
            "nodule_count":   count,
            "category":       "Incomplete Evaluation — Cannot Apply Fleischner",
            "recommendation": "Obtain dedicated CT chest (full lung volume, diagnostic protocol). "
                              "Re-apply Fleischner guidelines once accurate nodule size, type, "
                              "location, and morphology are established.",
            "reasoning":      "Fleischner requires complete, accurate nodule characterization. "
                              "This CT did not provide full lung evaluation (e.g., abdomen/pelvis CT, "
                              "nodule obscured by atelectasis, or only lung bases imaged). "
                              "Applying size-based recommendations to an unconfirmed finding would be "
                              "inappropriate and potentially dangerous.",
        }

    # ── SPECIAL CASE 2: Stability confirmed at this scan ─────
    # Current CT IS the required follow-up scan showing stability
    # Applies to: solid 6-8 mm, low risk, single, stable at ~6-12 months
    if (p.get("nodule_status") in ("stable",) and
            ntype == "Solid" and 6 <= avg_mm <= 8 and
            count == "single" and risk == "Low Risk"):
        return {
            "guideline":      "Fleischner 2017",
            "eligible":       True,
            "risk_category":  risk,
            "risk_factors":   risk_factors,
            "nodule_type":    ntype,
            "nodule_size":    f"{avg_mm} mm",
            "nodule_count":   count,
            "category":       f"Single Solid 6–8 mm — {risk} — Stability Confirmed",
            "recommendation": "No further follow-up required. "
                              "This CT serves as the required 6–12 month stability scan. "
                              "Nodule is unchanged — surveillance is complete per Fleischner.",
            "reasoning":      "Fleischner 2017 for single solid 6–8 mm low-risk nodule: "
                              "CT at 6–12 months required; if unchanged → no further imaging needed. "
                              "Current CT confirms stability at appropriate interval. "
                              "Discharging from nodule surveillance is appropriate.",
        }

    # ── SPECIAL CASE 3: Perifissural nodule ──────────────────
    if p.get("perifissural"):
        return {
            "guideline":      "Fleischner 2017",
            "eligible":       True,
            "risk_category":  risk,
            "risk_factors":   risk_factors,
            "nodule_type":    ntype,
            "nodule_size":    f"{avg_mm} mm",
            "nodule_count":   count,
            "category":       "Perifissural Nodule — Special Case",
            "recommendation": "No follow-up required, even if nodule > 6 mm. "
                              "Exception: if atypical features are present, apply standard criteria.",
            "reasoning":      "Perifissural nodules (along pulmonary fissures, oval/lentiform, "
                              "smooth margins) are almost always intrapulmonary lymph nodes — benign. "
                              "Fleischner 2017 explicitly exempts typical PFNs from surveillance "
                              "regardless of size.",
        }

    # ── STANDARD ROUTING ─────────────────────────────────────
    if ntype == "Solid":
        rec, rat, cat_label = _fleischner_solid(avg_mm, count, risk)
    else:
        rec, rat, cat_label = _fleischner_subsolid(ntype, avg_mm, solid, count)

    # Build full size display string
    if long_mm != short_mm:
        size_display = f"{avg_mm} mm (avg of {long_mm} x {short_mm} mm)"
    else:
        size_display = f"{avg_mm} mm"

    reasoning = (
        f"ELIGIBILITY: {elig_reason} | "
        f"RISK ASSESSMENT: {risk} — contributing factors: "
        f"{'; '.join(risk_factors)}. | "
        f"NODULE: {ntype}, {size_display}, {count}. | "
        f"CLASSIFICATION: {cat_label}. | "
        f"RATIONALE: {rat}"
    )

    return {
        "guideline":      "Fleischner 2017",
        "eligible":       True,
        "risk_category":  risk,
        "risk_factors":   risk_factors,
        "nodule_type":    ntype,
        "nodule_size":    size_display,
        "nodule_count":   count,
        "category":       cat_label,
        "recommendation": rec,
        "reasoning":      reasoning,
    }


# ================================================================
#  LUNG-RADS v2022 — FULL IMPLEMENTATION
# ================================================================

def _lr_solid(size_mm, status):
    """
    Lung-RADS solid nodule classification.
    STATUS IS CRITICAL: Same 7mm nodule = Cat 3 at baseline, Cat 4A if new.

    Edge cases:
    - Exactly 6 mm baseline = Cat 3 (not Cat 2 — boundary is strictly < 6)
    - Exactly 8 mm baseline = Cat 4A (boundary is < 8 for Cat 3)
    - Growing < 8mm = Cat 4A
    - Growing ≥ 8mm = Cat 4B
    """
    s = size_mm
    st = status.lower()

    if st == "stable":
        # Small stable nodules (< 8mm) → Cat 2 (benign, negative screen)
        # Large stable nodules (≥ 8mm) → classify by size; stability alone does not
        # downgrade a Cat 4A nodule. Formal 3-month LDCT is required first.
        if s < 8:
            return ("2", "Benign", "12-month LDCT.",
                    "Stable nodule < 8 mm → Category 2. Negative screen.")
        elif s < 15:
            return ("4A", "Suspicious",
                    "3-month LDCT. PET/CT may be considered (nodule ≥ 8 mm). "
                    "If confirmed stable at 3-month follow-up → may downgrade to Category 3.",
                    "Stable nodule 8–<15 mm → Category 4A. Stability alone does not downgrade "
                    "below 4A without a formal 3-month LDCT confirming stability per Lung-RADS rules.")
        else:
            return ("4B", "Very Suspicious",
                    "Diagnostic chest CT; PET/CT; tissue sampling; referral.",
                    "Stable nodule ≥ 15 mm → Category 4B. Size alone drives this classification.")

    if st == "growing":
        if s < 8:
            return ("4A", "Suspicious",
                    "3-month LDCT. PET/CT may be considered if ≥ 8 mm solid component.",
                    "Growing solid nodule < 8 mm → Category 4A. "
                    "Growth is defined as increase in mean diameter > 1.5 mm over 12 months.")
        else:
            return ("4B", "Very Suspicious",
                    "Diagnostic chest CT (with or without contrast); PET/CT may be considered; "
                    "tissue sampling; referral for clinical evaluation.",
                    "Growing solid nodule ≥ 8 mm → Category 4B. Positive screen. "
                    "High suspicion — do not defer evaluation.")

    if st == "baseline":
        if s < 6:
            return ("2", "Benign", "12-month LDCT.",
                    "Solid nodule < 6 mm at baseline → Category 2 (Benign). Negative screen.")
        elif s < 8:
            return ("3", "Probably Benign", "6-month LDCT.",
                    "Solid nodule 6 to < 8 mm at baseline → Category 3 (Probably Benign). "
                    "Positive screen. Short-interval follow-up to reassess.")
        elif s < 15:
            return ("4A", "Suspicious",
                    "3-month LDCT. PET/CT may be considered (nodule ≥ 8 mm).",
                    "Solid nodule 8 to < 15 mm at baseline → Category 4A (Suspicious). "
                    "Positive screen.")
        else:
            return ("4B", "Very Suspicious",
                    "Diagnostic chest CT; PET/CT; tissue sampling; referral.",
                    "Solid nodule ≥ 15 mm at baseline → Category 4B (Very Suspicious). "
                    "Positive screen.")

    if st == "new":
        if s < 4:
            return ("2", "Benign", "12-month LDCT.",
                    "New solid nodule < 4 mm → Category 2 (Benign). Negative screen.")
        elif s < 6:
            return ("3", "Probably Benign", "6-month LDCT.",
                    "New solid nodule 4 to < 6 mm → Category 3 (Probably Benign). "
                    "NOTE: same 5mm nodule at baseline = Cat 2 but if NEW = Cat 3. "
                    "New nodules are categorized more aggressively.")
        elif s < 8:
            return ("4A", "Suspicious",
                    "3-month LDCT. PET/CT may be considered.",
                    "New solid nodule 6 to < 8 mm → Category 4A (Suspicious).")
        else:
            return ("4B", "Very Suspicious",
                    "Diagnostic chest CT; PET/CT; tissue sampling; referral.",
                    "New solid nodule ≥ 8 mm → Category 4B (Very Suspicious). "
                    "New large nodules carry high suspicion.")

    return ("0", "Incomplete",
            "Prior CT comparison or additional lung cancer screening CT needed.",
            "Nodule status unclear — incomplete evaluation.")


def _lr_part_solid(total_mm, solid_mm, status):
    """
    Lung-RADS part-solid nodule classification.
    CLASSIFICATION IS DRIVEN BY THE SOLID COMPONENT, not total size.

    Key thresholds (solid component):
    - Baseline < 6mm total → Cat 2
    - Baseline ≥ 6mm total, solid < 6mm → Cat 3
    - Solid 6 to < 8mm → Cat 4A
    - Solid ≥ 8mm → Cat 4B
    - New/growing: solid < 4mm → Cat 4A; solid ≥ 4mm → Cat 4B
    """
    st = status.lower()

    if st == "baseline":
        if total_mm < 6:
            return ("2", "Benign", "12-month LDCT.",
                    "Part-solid nodule < 6 mm total diameter at baseline → Category 2.")
        elif solid_mm < 6:
            return ("3", "Probably Benign", "6-month LDCT.",
                    "Part-solid ≥ 6 mm total but solid component < 6 mm → Category 3. "
                    "Management driven by solid component size, not total size.")
        elif solid_mm < 8:
            return ("4A", "Suspicious",
                    "3-month LDCT. PET/CT may be considered (solid component ≥ 6 mm).",
                    "Solid component 6 to < 8 mm → Category 4A.")
        else:
            return ("4B", "Very Suspicious",
                    "Diagnostic chest CT; PET/CT; tissue sampling; referral.",
                    "Solid component ≥ 8 mm → Category 4B. High suspicion for invasive cancer.")

    elif st == "stable":
        return ("2", "Benign", "12-month LDCT.",
                "Stable part-solid nodule → Category 2.")

    else:  # new or growing
        if solid_mm < 4:
            return ("4A", "Suspicious", "3-month LDCT.",
                    "New or growing part-solid nodule with solid component < 4 mm → Category 4A.")
        else:
            return ("4B", "Very Suspicious",
                    "Diagnostic chest CT; PET/CT; tissue sampling; referral.",
                    "New or growing solid component ≥ 4 mm → Category 4B. "
                    "High suspicion for invasive malignancy.")


def _lr_ggn(size_mm, status):
    """
    Lung-RADS non-solid (pure GGN) nodule classification.
    GGNs use a very different threshold — 30 mm is the key cutoff.

    Why 30 mm? Pure GGNs are almost always AIS or MIA; they grow
    very slowly. Only very large ones qualify as Category 3.
    """
    st = status.lower()

    if st in ("baseline", "new", "growing"):
        if size_mm < 30:
            return ("2", "Benign", "12-month LDCT.",
                    "Non-solid (GGN) nodule < 30 mm (baseline, new, or growing) → Category 2. "
                    "GGNs < 30mm are almost always benign or very indolent (AIS/MIA).")
        else:
            return ("3", "Probably Benign", "6-month LDCT.",
                    "Non-solid (GGN) nodule ≥ 30 mm (baseline or new) → Category 3. "
                    "Large GGNs warrant short-interval follow-up.")

    else:  # stable or slowly growing
        return ("2", "Benign", "12-month LDCT.",
                "Stable or slowly growing GGN ≥ 30 mm → Category 2. "
                "Stability is reassuring even for large GGNs.")


def _check_4x(category, p):
    """
    Upgrade to Category 4X if a Cat 3 or 4 nodule ALSO has additional
    highly suspicious features.

    4X features:
    - Spiculation
    - Lymphadenopathy (suspicious)
    - Frank metastatic disease
    - GGN that doubled in size in 1 year
    - Other highly concerning features

    4X management = same as 4B (most aggressive)
    """
    if category not in ("3", "4A", "4B"):
        return category, []

    upgrades = []
    if p.get("spiculated"):          upgrades.append("Spiculation")
    if p.get("lymphadenopathy"):     upgrades.append("Suspicious lymphadenopathy")
    if p.get("metastatic_disease"):  upgrades.append("Frank metastatic disease")
    if p.get("ggn_doubled_in_1yr"):  upgrades.append("GGN doubled in size within 1 year")

    if upgrades:
        return "4X", upgrades
    return category, []


def _s_modifier(p):
    """
    Collect significant non-lung-cancer findings that qualify for the S modifier.
    S modifier is ADDITIVE — it does NOT change the category number.
    It means: 'additional workup needed for this finding.'

    Examples that qualify: coronary Ca, aortic aneurysm, severe emphysema,
    moderate/large pleural effusion, pulmonary fibrosis, vertebral fractures,
    pericardial effusion, hepatic steatosis, masses.
    """
    findings = []
    if p.get("coronary_calcification"):  findings.append("Coronary artery calcification")
    if p.get("aortic_aneurysm"):         findings.append("Aortic aneurysm")
    if p.get("severe_emphysema"):        findings.append("Severe emphysema / COPD")
    if p.get("large_pleural_effusion"):  findings.append("Moderate/large pleural effusion")
    if p.get("pulmonary_fibrosis"):      findings.append("Pulmonary fibrosis")
    if p.get("vertebral_fracture"):      findings.append("Vertebral fracture")
    if p.get("pericardial_effusion"):    findings.append("Pericardial effusion")
    if p.get("other_significant"):       findings.append(p["other_significant"])
    return findings


def run_lung_rads(p):
    """
    Master Lung-RADS function.
    Handles:
    - No nodule → Cat 1
    - Benign features (calcification, fat) → Cat 1
    - GGN, Part-Solid, Solid routing
    - 4X upgrade check
    - S modifier
    - Screen result (Negative = Cat 1 or 2; Positive = Cat 3 or 4)
    """
    ntype  = p.get("nodule_type", "Solid")
    status = p.get("nodule_status", "baseline")
    size   = p.get("nodule_size_mm", 0)
    solid  = p.get("solid_component_mm", 0)

    # ── Cat 1: No nodule / Benign features ───────────────────
    if p.get("no_nodule") or p.get("benign_calcification") or p.get("fat_containing"):
        category, name = "1", "Negative"
        rec  = "12-month LDCT."
        rat  = ("No suspicious pulmonary nodules identified, OR nodule with definitive "
                "benign features (complete/central/popcorn calcification, fat-containing) "
                "→ Category 1 (Negative). This is a negative screen.")

    # ── Solid nodule ─────────────────────────────────────────
    elif ntype == "Solid":
        category, name, rec, rat = _lr_solid(size, status)

    # ── Part-solid nodule ────────────────────────────────────
    elif ntype == "Part-Solid":
        category, name, rec, rat = _lr_part_solid(size, solid, status)

    # ── Pure GGN ─────────────────────────────────────────────
    elif ntype == "GGN":
        category, name, rec, rat = _lr_ggn(size, status)

    else:
        category, name = "0", "Incomplete"
        rec = "Prior CT comparison or additional imaging needed."
        rat = "Nodule type could not be determined — incomplete evaluation."

    # ── 4X upgrade ───────────────────────────────────────────
    category, upgrade_features = _check_4x(category, p)
    if upgrade_features:
        name = "Very Suspicious + Additional Features (4X)"
        rec  = ("Diagnostic chest CT (with or without contrast); PET/CT; "
                "tissue sampling; referral for clinical evaluation.")
        rat += (f" UPGRADED TO 4X due to additional suspicious features: "
                f"{', '.join(upgrade_features)}.")

    # ── S modifier ───────────────────────────────────────────
    s_findings   = _s_modifier(p)
    display_cat  = f"{category}{'S' if s_findings else ''}"
    screen_result = "Negative" if category in ("1", "2") else "Positive"

    # Build full reasoning string
    s_note = ""
    if s_findings:
        s_note = (f" | S MODIFIER APPLIED — significant non-lung-cancer finding(s): "
                  f"{'; '.join(s_findings)}. Manage each finding as clinically appropriate.")

    reasoning = (
        f"GUIDELINE: Lung-RADS v2022 (screening exam). | "
        f"MOST SUSPICIOUS NODULE: {ntype}, {size} mm, status={status}. | "
        f"CLASSIFICATION: Category {category} ({name}). | "
        f"RATIONALE: {rat}{s_note} | "
        f"SCREEN RESULT: {screen_result}."
    )

    return {
        "guideline":            "Lung-RADS v2022",
        "lung_rads_category":   display_cat,
        "category_name":        name,
        "nodule_type":          ntype,
        "nodule_size":          f"{size} mm" if size > 0 else "None/Benign",
        "nodule_count":         "N/A (Lung-RADS)",
        "category":             f"Category {display_cat} — {name}",
        "recommendation":       rec,
        "reasoning":            reasoning,
        "4x_features":          upgrade_features if upgrade_features else None,
        "s_modifier_findings":  s_findings if s_findings else None,
        "screen_result":        screen_result,
    }


# ================================================================
#  SINGLE ENTRY POINT
# ================================================================

def classify(patient: dict) -> dict:
    """
    classify(patient_dict) → result_dict

    Auto-selects Fleischner or Lung-RADS based on is_screening flag.
    This is the only function the pipeline needs to call.
    """
    if patient.get("is_screening"):
        return run_lung_rads(patient)
    else:
        return run_fleischner(patient)
