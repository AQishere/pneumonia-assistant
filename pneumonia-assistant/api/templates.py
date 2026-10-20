"""Fixed result text, written for patients (plain language, actions they can take).

The agent may rephrase the tone but must not add advice. This wording is
medical guidance shown to the public: have it reviewed (supervisor / clinician)
before real use.
"""

RECOMMENDATIONS = {
    "Low": ("No signs of concern in your readings right now. This is not an all-clear: if you feel "
            "unwell or your symptoms get worse, contact a doctor."),
    "Pending": ("Your readings need a closer look, but some information is missing. Please answer the "
                "questions or add what is missing so the full check can run."),
    "Moderate": ("Some readings are outside the usual range. Keep wearing your device and check again "
                 "within 24 hours. Contact a doctor if you feel worse or develop a cough, fever or "
                 "breathing problems."),
    "Watch": ("The full check flagged a possible concern. It will be checked again in the next 4 to 24 "
              "hours to confirm. If you feel worse in the meantime or become short of breath, contact a "
              "doctor without waiting."),
    "High": ("Your results suggest a raised risk of a chest infection such as pneumonia. Please contact a "
             "doctor today; they may want to examine you and arrange a chest X-ray or blood test."),
}

# For the agent (and developers): what each band means technically.
BAND_MEANING = {
    "Low": "Stage 1 risk score below its threshold.",
    "Pending": "Flagged by Stage 1; Stage 2 has not run because inputs are missing.",
    "Moderate": "Flagged by Stage 1; Stage 2 risk score below its threshold.",
    "Watch": "Stage 2 risk score at or above its threshold, but not yet confirmed by a repeat assessment.",
    "High": "Stage 2 risk score at or above its threshold, confirmed by a repeat assessment or very high.",
}

CRITICAL_NOTICE = ("Some of your readings are at a level that needs attention now: please contact a doctor "
                   "or seek urgent medical care. If you have severe difficulty breathing, chest pain or "
                   "confusion, call Rescue 1122.")
DISCLAIMER = "This app gives guidance only. It cannot diagnose pneumonia or replace a doctor."
SCORE_NOTE = "Risk scores are model scores, not probabilities of pneumonia."
STAGE1_MISSING_NOTE = "Some device readings are missing, so the check could not run yet."


def lead_text(alerts: list[dict]) -> str | None:
    """The sentence a reply must open with when any critical alert fired."""
    if not alerts:
        return None
    return CRITICAL_NOTICE + " " + " ".join(f"{a['message']}." for a in alerts)
