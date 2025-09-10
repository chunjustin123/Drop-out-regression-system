# AI-based Drop-out Prediction and Counseling System

This project fuses attendance, assessment, and fee spreadsheets, applies configurable rule-based logic, trains a baseline regression model, shows a color-coded dashboard, and schedules notifications to mentors/parents.

## Quickstart

1) Install uv and dependencies (already done if you ran the setup):

```bash
source $HOME/.local/bin/env
cd /Users/lakshitha/Downloads/aibaseddropoutsystem
uv venv
source .venv/bin/activate
uv pip install -r <(echo)
```

2) Run Streamlit dashboard:

```bash
source .venv/bin/activate
streamlit run app/app.py
```

3) Train baseline model (after placing sample data in `data/inputs/`):

```bash
python -m src.model --train data/inputs
```

4) Start scheduler for notifications (optional):

```bash
python scripts/scheduler.py
```

## Data Inputs
Place spreadsheets in `data/inputs/`:
- attendance: columns `student_id,date,present`
- assessments: columns `student_id,assessment_name,score`
- fees: columns `student_id,amount_due,amount_paid,due_date`

You can configure column mappings and rules in `config/mappings.yaml` and `config/rules.yaml`.

## Environment Variables
Copy `.env.sample` to `.env` and fill in tokens for Slack/Twilio if you want notifications.
# Drop-out-regression-system
