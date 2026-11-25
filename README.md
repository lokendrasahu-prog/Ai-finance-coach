# AI Personal Finance Coach

A beginner-friendly Streamlit prototype for a college project.

## Features
- Upload transaction data from CSV, Excel, or text-based PDF tables.
- Categorise transactions using transparent keyword rules.
- Save transactions locally in SQLite.
- Dashboard for income, expenses, cash flow, category distribution and monthly trends.
- Purchase affordability calculator with EMI, down payment and protected emergency reserve.
- Savings-goal planner.
- Basic rule-based finance Q&A.

## Run the project
1. Install Python 3.10 or newer.
2. Extract this ZIP and open a terminal in the project folder.
3. Create and activate a virtual environment (recommended).
4. Install dependencies:
   `pip install -r requirements.txt`
5. Start the app:
   `streamlit run app.py`

The app opens in your browser, usually at http://localhost:8501.

## Statement format
CSV/Excel should include:
- Date
- Description (or Narration / Details)
- Amount

Alternatively, use separate Debit and Credit columns. Positive amounts are treated as income and negative amounts as expenses when using a single Amount column. For Debit/Credit columns, Credit is treated as income and Debit as expense.

Example file: `sample_transactions.csv`.

## Important limitations
- This is a prototype, not a bank-connected product.
- Transaction categories are assigned by keyword rules, not a trained machine-learning model. Verify categories manually.
- PDF support works only when the statement contains extractable transaction tables. Scanned PDFs need OCR and may require preprocessing.
- Calculations are estimates and do not include every tax, fee, insurance, ownership cost or lender condition.
- Do not upload real bank statements to a public/shared computer. Use anonymised sample data for demonstrations.
- This app is educational and is not financial, investment, tax or legal advice.
