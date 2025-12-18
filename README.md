# Student Record Browser (Streamlit)

Browse student records from the provided Commerce report CSV (CB015). The app parses the semi-structured CSV and presents per-student details and year-by-year course performance.

## Quick Start

1. Create/activate your Python virtual environment (optional but recommended):

```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the app:

```bash
streamlit run app.py
```

By default the app loads `CB015 - December 2024.csv` from this folder. You can change the CSV path from the sidebar.

## Navigation

Use the sidebar buttons: **First student**, **Prev**, **Next**, **Last Student**. The main page shows the current student's name, campus ID, and program details, followed by year-by-year course tables.

## Notes

- The parser handles both CB015 and CB024 report formats. CB024 files include additional term metrics (JT, JE, ST, SE, TT, TE, CE, weighted GPA, term GPA, cumulative GPA) that are displayed above the course table in each year tab.
- The parser handles CSV inconsistencies including quoted fields with embedded commas.
- For large files, the initial parse may take a few seconds; subsequent loads are cached.
