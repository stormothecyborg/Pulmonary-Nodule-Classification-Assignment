"""
================================================================
 PART 1: REPORT PARSER (v3 — sentence-level negation)
================================================================
"""
import re


# ================================================================
#  NEGATION — sentence-level, not window-based
# ================================================================

def _negated(full_text, match_obj):
    """
    Checks if a regex match is negated by finding the sentence
    that CONTAINS the match and looking for negation only within
    that sentence, BEFORE the match position.

    Uses '. ', '.\\n', '!', '?' as sentence boundaries.
    This prevents "not enlarged" (prior sentence) from negating
    "coronary calcifications" (next sentence).
    """
    text_before = full_text[:match_obj.start()]

    # Find start of the sentence containing this match
    last_boundary = -1
    for boundary in ['. ', '.\n', '! ', '? ', '\n\n']:
        pos = text_before.rfind(boundary)
        if pos > last_boundary:
            last_boundary = pos

    sentence_prefix = full_text[last_boundary + 2 if last_boundary >= 0 else 0
                                 : match_obj.start()].lower()

    neg_pat = r'\b(no|not|without|absence\s+of|no\s+evidence\s+of|deny|denies|negative\s+for)\b'
    return bool(re.search(neg_pat, sentence_prefix))


# ================================================================
#  DEMOGRAPHICS
# ================================================================

def extract_age(text):
    for pat in [r'[Aa]ge[:\s]+(\d{2,3})', r'(\d{2,3})[\s-]*year[\s-]*old']:
        m = re.search(pat, text)
        if m: return int(m.group(1))
    return None


def extract_smoking(text):
    t = text.lower()
    for pat in [r'non[\s-]*smoker', r'never[\s-]*smok',
                r'no\s+(history\s+of\s+)?smok', r'lifetime\s+non[\s-]*smoker',
                r'no\s+prior\s+history\s+of\s+smoking']:
        if re.search(pat, t): return False
    for pat in [r'\bsmoker\b', r'\bsmoking\b', r'tobacco',
                r'pack[\s-]*year', r'cigarette', r'nicotine']:
        if re.search(pat, t): return True
    return False


# ================================================================
#  NODULE TYPE  (with negation guard)
# ================================================================

def extract_nodule_type(text):
    t = text.lower()
    m = re.search(r'part[\s-]*solid|mixed[\s-]*(solid|ground|glass)', t)
    if m and not _negated(t, m): return "Part-Solid"

    for pat in [r'ground[\s-]*glass\s+(nodule|opacity|opacit)',
                r'\bggn\b', r'\bggo\b', r'non[\s-]*solid\s+nodule',
                r'pure\s+ground[\s-]*glass']:
        m = re.search(pat, t)
        if m and not _negated(t, m): return "GGN"

    return "Solid"


# ================================================================
#  SIZE — finds dominant (most suspicious) nodule
# ================================================================

def _parse_size_str(s):
    m2 = re.match(r'(\d+\.?\d*)\s*[xX×]\s*(\d+\.?\d*)\s*(mm|cm)', s)
    if m2:
        a, b = float(m2.group(1)), float(m2.group(2))
        if m2.group(3) == 'cm': a *= 10; b *= 10
        return round((max(a,b)+min(a,b))/2, 1), max(a,b), min(a,b)
    m1 = re.match(r'(\d+\.?\d*)\s*(mm|cm)', s)
    if m1:
        v = float(m1.group(1))
        if m1.group(2) == 'cm': v *= 10
        return round(v, 1), v, v
    return None, None, None


SIZE_PAT = r'(\d+\.?\d*\s*(?:[xX×]\s*\d+\.?\d*)?\s*(?:mm|cm))\b'


def extract_dominant_size(text):
    """
    Extracts DOMINANT nodule size. Priority:
    1. Size near 'dominant/largest/most suspicious' keywords
    2. Size near 'growing/new/interval growth' keywords
    3. Largest size associated with 'nodule'
    """
    candidates = []

    # Priority 1: dominant/largest context
    for ctx in re.finditer(
        r'(most\s+(suspicious|conspicuous)|dominant|largest).{0,150}', text, re.IGNORECASE
    ):
        m = re.search(SIZE_PAT, ctx.group(0))
        if m:
            avg, lng, shrt = _parse_size_str(m.group(1))
            if avg and 1 <= avg <= 150:
                return {'avg_mm': avg, 'long_mm': lng, 'short_mm': shrt}

    # Priority 2: growing/new context
    for ctx in re.finditer(
        r'(interval\s+(growth|thicken|enlarg|increas)|new\s+.{0,15}nodule|growing).{0,200}',
        text, re.IGNORECASE
    ):
        m = re.search(SIZE_PAT, ctx.group(0))
        if m:
            avg, lng, shrt = _parse_size_str(m.group(1))
            if avg and 1 <= avg <= 150:
                return {'avg_mm': avg, 'long_mm': lng, 'short_mm': shrt}

    # Priority 3: all nodule/mass-associated sizes → take largest
    # Includes "mass" because some reports describe dominant finding as "mass" not "nodule"
    for ctx in re.finditer(
        SIZE_PAT + r'.{0,80}(nodule|mass)|(?:nodule|mass).{0,80}?' + SIZE_PAT,
        text, re.IGNORECASE
    ):
        m = re.search(SIZE_PAT, ctx.group(0))
        if m:
            avg, lng, shrt = _parse_size_str(m.group(1))
            if avg and 1 <= avg <= 150:
                candidates.append((avg, lng, shrt))

    if candidates:
        candidates.sort(reverse=True)
        avg, lng, shrt = candidates[0]
        return {'avg_mm': avg, 'long_mm': lng, 'short_mm': shrt}

    # Fallback: first size in text
    m = re.search(SIZE_PAT, text)
    if m:
        avg, lng, shrt = _parse_size_str(m.group(1))
        if avg and 1 <= avg <= 150:
            return {'avg_mm': avg, 'long_mm': lng, 'short_mm': shrt}

    return None


# ================================================================
#  NODULE COUNT  (guards "No other nodules" false positive)
# ================================================================

def extract_nodule_count(text):
    t = text.lower()
    if re.search(r'\b(single|solitary|one)\b.{0,30}nodule', t):
        return "single"

    for pat in [
        r'multiple\s+(nodules?|lesions?|bilateral)',
        r'bilateral\s+(nodules?|lesions?)',
        r'several\s+nodules?',
        r'numerous\s+nodules?',
        r'scattered\s+.{0,20}nodules?',
    ]:
        for m in re.finditer(pat, t):
            if not _negated(t, m): return "multiple"

    # Plural "nodules" only if NOT in a negated context
    for m in re.finditer(r'\bnodules\b', t):
        if not _negated(t, m): return "multiple"

    return "single"


# ================================================================
#  LOCATION
# ================================================================

def extract_upper_lobe(text):
    t = text.lower()
    upper = r'upper\s+lobe|apical\s+(segment|nodule)|apex\s+|right\s+upper|left\s+upper|\brul\b|\blul\b'
    lower = r'lower\s+lobe|basal|right\s+lower|left\s+lower|\brll\b|\blll\b|middle\s+lobe|lingula'

    # Check dominant context first
    dom = re.search(r'(most\s+(suspicious|conspicuous)|dominant|largest).{0,200}', t)
    if dom:
        ctx = dom.group(0)
        if re.search(upper, ctx): return True
        if re.search(lower, ctx): return False

    # First nodule description
    fn = re.search(r'nodule.{0,200}', t)
    if fn:
        ctx = fn.group(0)
        if re.search(upper, ctx): return True

    return False


# ================================================================
#  IMAGING FEATURES  (all with sentence-level negation)
# ================================================================

def _pos_match(text, pattern):
    """Returns True if pattern found in a non-negated context."""
    m = re.search(pattern, text, re.IGNORECASE)
    return bool(m) and not _negated(text, m)


def extract_emphysema(text):
    return _pos_match(text, r'emphysem|centrilobular\s+.{0,20}emphysem|paraseptal\s+emphysem')


def extract_fibrosis(text):
    return _pos_match(text, r'pulmonary\s+fibros|interstitial\s+(thicken|lung\s+disease|fibros)')


def extract_spiculated(text):
    if _pos_match(text, r'spiculat|stellate\s+(margin|nodule)'): return True
    if _pos_match(text, r'irregular\s+(margin|border)'): return True
    return False


def extract_asbestos(text):
    return _pos_match(text, r'asbestos|pleural\s+plaque|occupational\s+(exposure|carcinogen)')


def extract_family_hx(text):
    return bool(re.search(r'family\s+history.{0,30}(lung|cancer)', text, re.IGNORECASE))


def extract_known_cancer(text):
    return bool(re.search(
        r'known\s+(primary|cancer|malignancy|tumor)|history\s+of\s+(cancer|malignancy)',
        text, re.IGNORECASE
    ))


def extract_immunocompromised(text):
    return bool(re.search(r'immunocompromised|immunosuppressed|transplant|\bhiv\b|\baids\b',
                           text, re.IGNORECASE))


def extract_incomplete_eval(text):
    t = text.lower()
    return bool(re.search(
        r'partially\s+obscured|obscured\s+by\s+atelectasis|field\s+of\s+view'
        r'|lung\s+apices?\s+were\s+not\s+imaged'
        r'|limited\s+(evaluation|assessment)\s+of\s+the\s+lung'
        r'|complete\s+evaluation\s+is\s+not\s+possible'
        r'|may\s+(contain|be\s+present)', t
    ))


# ================================================================
#  STABILITY
# ================================================================

def extract_nodule_status(text):
    t = text.lower()

    for pat in [r'interval\s+(growth|increase|enlarg|thicken)',
                r'(has\s+)?(grown|increased\s+in\s+size)',
                r'development\s+of\s+(new\s+)?nodule']:
        m = re.search(pat, t)
        if m and not _negated(t, m):
            return "growing"

    for pat in [r'new\s+(solid|nodule|ground|part)',
                r'nodule.{0,30}\bnew\b',
                r'newly\s+(identified|apparent|seen)',
                r'not\s+(seen|present|identified)\s+on\s+(prior|previous)',
                r'new\s+.{0,10}(solid|nodular|opacity)']:
        m = re.search(pat, t)
        if m and not _negated(t, m):
            return "new"

    for pat in [r'unchanged|no\s+(interval\s+)?change|no\s+growth',
                r'demonstrating\s+no\s+(growth|change)',
                r'again\s+(seen|note)']:
        m = re.search(pat, t)
        if m and not _negated(t, m):
            return "stable"

    if re.search(r'comparison[:\s]+none|no\s+(prior|comparison|previous)\s+(ct|study|exam)', t):
        return "baseline"
    if re.search(r'comparison|prior\s+(ct|study|exam|chest)', t):
        return "stable"

    return "baseline"


def extract_solid_component(text):
    t = text.lower()
    m = re.search(r'solid\s+component.{0,50}?(\d+\.?\d*)\s*(mm|cm)', t)
    if m:
        v = float(m.group(1))
        if m.group(2) == 'cm': v *= 10
        return round(v, 1)
    return 0.0


# ================================================================
#  LUNG-RADS SPECIFIC
# ================================================================

def extract_benign_calcification(text):
    t = text.lower()
    for pat in [r'calcified\s+granuloma',
                r'(complete|central|popcorn|concentric\s+ring)\s+calcif',
                r'fat[\s-]*containing\s+nodule']:
        m = re.search(pat, t)
        if m and not _negated(t, m): return True
    # "benign" near "calcif" but NOT in "calcified granulomas in both lungs" → already caught
    m = re.search(r'benign.{0,10}calcif', t)
    if m and not _negated(t, m): return True
    return False


def extract_no_nodule(text):
    """
    True only when the whole lungs have no nodules.
    'No other nodule' or 'No suspicious adenopathy' must NOT trigger this.
    """
    t = text.lower()
    for pat in [
        r'no\s+pulmonary\s+(nodule|mass)\b',    # "no pulmonary nodule"
        r'no\s+focal\s+(nodule|mass|lesion)\b',  # "no focal nodule"
        r'lungs\s+(are\s+)?clear\b',
    ]:
        if re.search(pat, t): return True
    return False


def extract_s_coronary(text):
    t = text.lower()
    # Multiple patterns; any non-negated match qualifies
    pats = [
        r'coronary\s+(artery\s+)?calcif',
        r'calcif.{0,50}coronary',            # "calcification ... coronary" (extended window)
        r'coronary.{0,50}calcif',            # "coronary ... calcification"
        r'calcif.{0,30}(lad|rca|lcx|left\s+main|left\s+anterior|right\s+coronary)',
        r'coronary\s+atherosclerosis',
    ]
    for pat in pats:
        m = re.search(pat, t)
        if m and not _negated(t, m): return True
    return False


def extract_s_pericardial(text):
    t = text.lower()
    m = re.search(r'pericardial\s+effusion', t)
    return bool(m) and not _negated(t, m)


def extract_s_pleural(text):
    t = text.lower()
    return bool(re.search(r'(moderate|large|significant)\s+pleural\s+effusion', t))


def extract_s_vertebral(text):
    t = text.lower()
    m = re.search(
        r'(vertebral|compression|endplate)\s+(fracture|collapse|wedg)'
        r'|(anterior\s+)?wedging\s+at\s+[a-z]\d'
        r'|compression\s+fracture', t
    )
    return bool(m) and not _negated(t, m) if m else False


def extract_s_aortic(text):
    t = text.lower()
    m = re.search(r'aortic\s+aneurysm|aneurysmal\s+(aorta|change)', t)
    return bool(m) and not _negated(t, m) if m else False


def extract_s_severe_emphysema(text):
    t = text.lower()
    return bool(re.search(
        r'(severe|moderate|significant)\s+.{0,25}emphysem'
        r'|emphysem.{0,25}(severe|moderate|significant)', t
    ))


def extract_s_fibrosis(text):
    t = text.lower()
    m = re.search(r'pulmonary\s+fibros|interstitial\s+(lung\s+disease|fibros)', t)
    return bool(m) and not _negated(t, m) if m else False


def extract_lymphadenopathy(text):
    """
    4X trigger: suspicious/enlarged lymph nodes. Checks ALL occurrences.
    'No lymphadenopathy' or 'No suspicious adenopathy' → False.
    """
    t = text.lower()
    # Check every occurrence of adenopathy/lymphadenopathy
    for m in re.finditer(r'\badenopathy\b|\blymphadenopathy\b', t):
        if not _negated(t, m):
            return True
    # Also check "enlarged ... lymph node" patterns
    for m in re.finditer(
        r'(mediastinal|hilar|paratracheal|lymph\s+node).{0,30}'
        r'(suspicious|enlarged|patholog|metastas)', t
    ):
        if not _negated(t, m):
            return True
    return False


def extract_other_significant(text):
    t = text.lower()
    found = []
    if re.search(r'old\s+(rib|healed)\s+fracture|multiple.{0,15}rib\s+fracture', t):
        found.append("Multiple old rib fractures")
    if re.search(r'calcified.{0,20}(lymph\s+node|hilar|subcarinal)', t):
        found.append("Calcified lymph nodes")
    if re.search(r'hepatic\s+steatosis|fatty\s+liver', t):
        found.append("Hepatic steatosis")
    if re.search(r'gynecomastia', t):
        found.append("Gynecomastia")
    return "; ".join(found) if found else None


# ================================================================
#  MASTER EXTRACTOR
# ================================================================

def parse_report(report_text, case_type):
    t = report_text
    is_scr = (case_type == "Lung-RADS")

    age       = extract_age(t)
    smoker    = extract_smoking(t)
    emphysema = extract_emphysema(t)
    fibrosis  = extract_fibrosis(t)
    spic      = extract_spiculated(t)
    asbestos  = extract_asbestos(t)
    upper     = extract_upper_lobe(t)
    fam_hx    = extract_family_hx(t)
    known_ca  = extract_known_cancer(t)
    immuno    = extract_immunocompromised(t)
    incompl   = extract_incomplete_eval(t)

    ntype    = extract_nodule_type(t)
    size_d   = extract_dominant_size(t)
    avg_mm   = size_d['avg_mm']   if size_d else 0.0
    long_mm  = size_d['long_mm']  if size_d else 0.0
    short_mm = size_d['short_mm'] if size_d else 0.0
    count    = extract_nodule_count(t)
    status   = extract_nodule_status(t)
    solid_c  = extract_solid_component(t)

    benign_calc = extract_benign_calcification(t)
    no_nodule   = extract_no_nodule(t)
    lymphad     = extract_lymphadenopathy(t)
    s_coronary  = extract_s_coronary(t)
    s_pericardial = extract_s_pericardial(t)
    s_pleural   = extract_s_pleural(t)
    s_vertebral = extract_s_vertebral(t)
    s_aortic    = extract_s_aortic(t)
    s_emph_mod  = extract_s_severe_emphysema(t)
    s_fibrosis  = extract_s_fibrosis(t)
    other_sig   = extract_other_significant(t)

    return {
        "age": age or 50, "is_screening": is_scr,
        "known_cancer": known_ca, "immunocompromised": immuno,
        "incomplete_evaluation": incompl,
        "nodule_type": ntype, "nodule_size_mm": avg_mm,
        "nodule_long_mm": long_mm, "nodule_short_mm": short_mm,
        "nodule_count": count, "nodule_status": status,
        "solid_component_mm": solid_c,
        "smoker": smoker, "emphysema": emphysema, "fibrosis": fibrosis,
        "upper_lobe": upper, "spiculated": spic, "asbestos": asbestos,
        "family_hx_cancer": fam_hx,
        "benign_calcification": benign_calc, "no_nodule": no_nodule,
        "lymphadenopathy": lymphad,
        "coronary_calcification": s_coronary, "pericardial_effusion": s_pericardial,
        "large_pleural_effusion": s_pleural, "vertebral_fracture": s_vertebral,
        "aortic_aneurysm": s_aortic, "severe_emphysema": s_emph_mod,
        "pulmonary_fibrosis": s_fibrosis, "other_significant": other_sig,
        "metastatic_disease": False, "ggn_doubled_in_1yr": False,
    }
