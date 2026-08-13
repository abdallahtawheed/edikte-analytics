import re

# Each entry: (flag_type, category, list of regex patterns, case-insensitive)
# Categories exist for Streamlit display grouping, flag_type is the specific signal.
#
# Methodology note: every pattern here was verified against real excerpts from the
# actual scraped corpus (~450 listings) before inclusion, not guessed from general
# knowledge of German real estate terms. See DECISIONS.md ADR-011 for the process
# and for terms explicitly REJECTED after checking (Risiko, Räumung, Delogierung,
# Wiederversteigerung, Schuld, Errichtet, Abgaben all confirmed boilerplate).

FLAG_CATEGORIES = {
    "structural_damage": {
        "label": "Structural & Physical Damage",
        "patterns": {
            "moisture_damage": [r"Feuchtigkeit\w*", r"Wasserschaden", r"Wasserschäden",
                                 r"Schimmel\w*", r"Wassereintritt\w*"],
            "structural_defect": [r"Rissbildung", r"Setzungsriss\w*", r"einsturzgefährdet",
                                   r"Einsturz", r"Putzschäden", r"Schäden\b"],
            "renovation_needed": [r"sanierungsbedürftig\w*", r"renovierungsbedürftig",
                                   r"instandsetzungsbedürftig", r"Sanierungsmaßnahmen",
                                   r"Sanierungskonzept"],
            "fire_damage": [r"Brandschaden", r"\bBrand\b"],
        },
    },
    "construction_legality": {
        "label": "Construction & Permit Issues",
        "patterns": {
            "incomplete_construction": [r"unfertig\w*", r"Rohbau", r"Fertigstellungsrückstau",
                                         r"nicht fertiggestellt"],
            "unauthorized_construction": [r"konsenslos\w*"],
            "electrical_issue": [r"E-Verteiler.*veraltet", r"nicht nutzungssicher"],
        },
    },
    "legal_financial": {
        "label": "Legal & Financial Encumbrances",
        "patterns": {
            "easement_encumbrance": [r"Dienstbarkeit\w*", r"Servitut\w*", r"Reallast\w*"],
            "financial_claim": [r"\bLasten\b", r"Forderungen", r"Rückstände",
                                 r"Abgabenrückstände"],
            "litigation": [r"Rechtsstreit\w*", r"\bKlage\b", r"Verjährungsproblematik"],
            "value_impairment": [r"[Ww]ertmindernd"],
        },
    },
    "boundary_access": {
        "label": "Boundary & Access Disputes",
        "patterns": {
            "boundary_dispute": [r"Grundgrenze", r"Grenzüberbau", r"Überbau\w*"],
            "access_dispute": [r"Zufahrtsrecht", r"Zufahrtsproblem", r"Wegerecht.*streitig",
                                r"Besitzstörung\w*"],
        },
    },
    "environmental": {
        "label": "Environmental Concerns",
        "patterns": {
            "contamination": [r"Altlast\w*", r"Bodenaustausch", r"kontaminiert\w*"],
        },
    },
    "buyer_restrictions": {
        "label": "Buyer Eligibility Restrictions",
        "patterns": {
            "foreign_buyer_restriction": [r"Ausländergrundverkehrsgesetz", r"Grundverkehrsgesetz",
                                           r"Grundverkehrsbehörde", r"\bAusländer\w*"],
            "vacation_home_only": [r"Freizeitwohnsitzwidmung"],
        },
    },
}

NEGATION_WORDS = ["nicht", "kein", "keine", "keinem", "keiner"]

def is_negated(text: str, match_start: int, window: int = 30) -> bool:
    preceding = text[max(0, match_start - window):match_start].lower()
    return any(neg in preceding for neg in NEGATION_WORDS)


def scan_for_flags(text: str) -> list[dict]:
    """
    Scan free text for known defect/condition/risk keyword patterns.
    Returns a list of {category, category_label, flag_type, matched_keyword, source_excerpt}.
    """
    if not text:
        return []
    found = []
    for category_key, category_data in FLAG_CATEGORIES.items():
        for flag_type, patterns in category_data["patterns"].items():
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    if is_negated(text, match.start()):
                        continue
                    start = max(0, match.start() - 60)
                    end = min(len(text), match.end() + 60)
                    excerpt = text[start:end].strip()
                    found.append({
                        "category": category_key,
                        "category_label": category_data["label"],
                        "flag_type": flag_type,
                        "matched_keyword": match.group(),
                        "source_excerpt": excerpt,
                    })
    return found