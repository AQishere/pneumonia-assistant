# Pneumonia Risk Assistant

A home-monitoring app for health-conscious people, built for a Final Year Project. Wearable
devices send vital signs, users upload their lab results, a two-stage screening model estimates
their risk of a chest infection such as pneumonia, and an AI assistant explains the result in plain
language and tells them what to do. Users can link a doctor who sees their results.
**Guidance only, not a diagnosis.** The training data is MIMIC-derived: only synthetic demo
patients are ever stored.

```
Patient ─▶ Next.js app ──Firebase sign-in token──▶ FastAPI ──▶ Firestore
   │            │                                     │ validation, safety alerts,
   │            └──── /chat ─▶ Agent (Gemini) ─tools─▶│ features, Stage 1 → Stage 2 v2,
IoT devices ──────────── readings (API key) ─────────▶│ persistence rule, fixed advice text
```

Anything that must always happen (range checks, alerts, time windows, which stage runs, the
advice text, who may see which record) lives in Python. The LLM only talks to the user and relays
results; its prompt rules are a second layer of defence, and code guards stop it inventing readings.

## Setup

From this folder, using the project's `.venv` (the one the notebook used, so scikit-learn
matches):

```powershell
..\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt   # requirements.txt alone is what the deployed API needs
copy .env.example .env      # then fill in API_KEY, GEMINI_API_KEY, Firebase settings

cd frontend
npm install
copy .env.local.example .env.local   # then fill in the Firebase web app config
```

The Firebase web config comes from the Firebase console: Project settings → General → Your apps →
Add app (Web). It is public by design; the API key in `.env` is never sent to the browser.

## Run

```powershell
# 1. API (with DB_BACKEND=memory it seeds the demo patients on start)
uvicorn api.main:create_app --factory --port 8000

# 2. Web app (http://localhost:3000)
cd frontend; npm run dev

# Optional: terminal chat against the API
python -m agent.chat --show-tools
```

For Firestore, set `DB_BACKEND=firestore` and `FIREBASE_CREDENTIALS` (service-account JSON
path), then load the demo patients with `python seed_demo_data.py`.

## API (main routes)

| Route | Who | Purpose |
|---|---|---|
| `POST /patients` | signed-in user | Signup: name, age, sex, six conditions (all required) |
| `POST /doctors` | signed-in user | Register as a doctor |
| `GET /me` | user | Role and profile |
| `GET /patients/{id}` | patient (own), linked doctor | Alerts, latest readings, labs, readiness |
| `POST /patients/{id}/readings` | patient, device (API key) | Store readings (validated) |
| `POST /patients/{id}/labs` | patient | Upload WBC, neutrophils, lymphocytes, CRP |
| `POST /patients/{id}/assess` | patient | Run the check (breathing + cough/fever/weakness answers) |
| `GET /patients/{id}/assessments`, `/readings` | patient, linked doctor | History |
| `POST /patients/{id}/doctors` | patient | Link a doctor by email |
| `POST /chat` | patient (own record only) | The assistant |
| `POST /demo/run` | signed-in user | Demo Test page: run the models on hand-entered data; nothing stored, no LLM |

## Tests

```powershell
pytest                                  # offline: models, API, auth, agent, persistence
python -m tests.run_agent_scenarios     # live agent scenarios against the LLM (uses quota)
cd frontend; npm run build; npm run lint
```

## How an assessment works

| Used by | Window | Needs |
|---|---|---|
| Stage 1 (6 features) | last 24 h | 1 reading per vital + "short of breath?" |
| Stage 2 v2 (43 features) | last 7 days | 2 readings per vital, profile, weakness answer, labs from the last 7 days |
| Critical alerts (SpO2 < 90, RR > 30, SBP < 90) | last 24 h | always run |

1. Safety alerts always run, even when inputs are missing.
2. Stage 1 inputs missing → `missing`, no result.
3. Stage 1 below 0.26 → **Low**.
4. Stage 1 flags but Stage 2 inputs are missing → **Pending**, with exactly what is missing.
5. Stage 2 below 0.53 → **Moderate**. At or above: **High** if ≥ 0.70 or confirmed by a positive
   assessment 4–36 h earlier, otherwise **Watch** (persistence rule; validated only by simulation).

Outputs are **risk scores, not probabilities**: the models were trained with class weighting.

## Model performance (test set, n = 1,530)

| Model | ROC AUC | Balanced accuracy | Pneumonia found | Controls cleared |
|---|---|---|---|---|
| Stage 1 | 78.2% | 64.9% | 90.6% | 39.1% |
| Stage 2 v2 | 80.8% (CI 78.2–83.3) | 72.8% | 73.8% | 71.8% |
| Two-stage system with v2 | – | 72.6% | 73.3% | 71.8% |

Stage 2 v2 beats the original Stage 2 (79.7% AUC) by +1.2 AUC (95% CI +0.3 to +2.1). Plain
accuracy is misleading here: 74.8% of test patients have pneumonia.

## Stage 2 v2 (frozen)

- **Model:** soft-voting average of logistic regression and CatBoost, original settings, both
  classes weighted equally. Threshold **0.53**, where the share of pneumonia caught equals the
  share of controls cleared (set on out-of-fold training scores).
- **43 features:** vital statistics (mean/min/max/std), engineered vitals (NEWS2-style points,
  shock index, measured fever, SpO2 drop, ranges), respiratory distress, age, sex, six
  conditions, weakness, hypoxemia, WBC, neutrophils, lymphocytes, NLR, CRP. Cough and fever
  answers are recorded but not used: they were almost never recorded in the training data.
- **Hypoxemia** is trained with the app's rule (any SpO2 < 90, or the recorded flag).
- **Rebuild:** `python -m training.train_stage2_v2`, `python -m training.split_by_label`, then
  `python -m training.train_stage2_cost equal` (writes `models/stage2_v2.joblib`).
- **Demo Test page (`/demo`):** shows both raw scores and a green / **amber** / red zone for
  Stage 2. Amber is 0.43–0.63 (threshold ± 0.10): too close to call from vitals and labs, so a
  chest X-ray would decide. On the test set this marks about 16% of patients; the others are about
  77% correct (measured just before the hypoxemia fix). Demo page only; the app's bands are unchanged.

**Ablation (all scripts in `training/experiments/`; none beat the frozen model on AUC, ~81 is the ceiling
for vitals + basic labs):** Optuna tuning (`tune_stage2_v2`), cost-sensitive weights in both
directions (`train_stage2_cost`), two-step cost training (`train_stage2_sequential`),
labs-complete patients only (`labs_only_experiment`), dropping CRP (`drop_crp_experiment`),
trends / calibration / uncertain band (`improvements_experiment`), SIRS, ROX, splines and MICE
(`feature_engineering_experiment`).

## Caveats (for the report)

- **Audience shift:** the models were trained on hospital inpatients; the app serves people at
  home. Real-world performance is unknown until validated on real device data.
- The dataset doesn't document the time window its vitals cover; the app assumes 24 h for
  Stage 1 and up to 7 days for Stage 2.
- CRP was measured for only 13% of training patients (others imputed); the app always has it.
- `hypoxemia` is now trained with the app's rule (SpO2 < 90 or the recorded flag); the recorded
  flag alone matched that rule for only 59% of patients.
- PPV and NPV depend on prevalence (75% pneumonia here, far lower at home). Sensitivity and
  specificity were measured against hospitalized controls, not healthy people.
- The persistence rule and its settings (0.70, 4 h, 36 h) are validated only by simulation.
- The patient-facing advice text (`api/templates.py`) must be reviewed by a clinician/supervisor.
