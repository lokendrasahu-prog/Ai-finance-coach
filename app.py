import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import sqlite3
import re
from datetime import datetime
from io import BytesIO

st.set_page_config(page_title="AI Personal Finance Coach", page_icon="💰", layout="wide")

DB_PATH = "finance_coach.db"

# -------------------- DATA STORAGE --------------------
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT, description TEXT, amount REAL,
                transaction_type TEXT, category TEXT
            )
        """)

def save_transactions(df):
    with sqlite3.connect(DB_PATH) as conn:
        df[["date", "description", "amount", "transaction_type", "category"]].to_sql(
            "transactions", conn, if_exists="append", index=False
        )

def load_saved_transactions():
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query("SELECT date, description, amount, transaction_type, category FROM transactions ORDER BY date", conn)

def clear_saved_transactions():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM transactions")

# -------------------- TRANSACTION PROCESSING --------------------
CATEGORY_RULES = {
    "Food": ["swiggy", "zomato", "restaurant", "cafe", "grocery", "supermarket", "bigbasket"],
    "Transport": ["uber", "ola", "petrol", "fuel", "metro", "bus", "train", "irctc"],
    "Housing": ["rent", "maintenance", "electricity", "water bill", "gas bill"],
    "Shopping": ["amazon", "flipkart", "mall", "clothing", "shopping"],
    "Healthcare": ["hospital", "pharmacy", "medical", "doctor", "clinic"],
    "Education": ["school", "college", "university", "course", "tuition"],
    "Entertainment": ["netflix", "spotify", "movie", "cinema", "game"],
    "EMI / Loan": ["emi", "loan", "interest", "mortgage"],
    "Income": ["salary", "payroll", "credited", "refund", "interest received"]
}

def categorize(description, amount):
    text = str(description).lower()
    for category, keywords in CATEGORY_RULES.items():
        if any(word in text for word in keywords):
            return category
    return "Other Income" if amount > 0 else "Other Expense"

def normalize_transactions(raw):
    df = raw.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    aliases = {
        "date": ["date", "transaction date", "txn date"],
        "description": ["description", "narration", "details", "merchant", "particulars"],
        "amount": ["amount", "transaction amount", "txn amount"],
        "debit": ["debit", "withdrawal", "withdrawals"],
        "credit": ["credit", "deposit", "deposits"]
    }
    found = {}
    for target, options in aliases.items():
        for option in options:
            if option in df.columns:
                found[target] = option
                break

    if "date" not in found or "description" not in found:
        raise ValueError("Your file must contain a Date column and a Description/Narration column.")

    df["date"] = pd.to_datetime(df[found["date"]], errors="coerce", dayfirst=True)
    df["description"] = df[found["description"]].fillna("Unknown").astype(str)

    if "amount" in found:
        amount = pd.to_numeric(df[found["amount"]].astype(str).str.replace(",", ""), errors="coerce")
    elif "debit" in found or "credit" in found:
        debit = pd.to_numeric(df[found["debit"]].astype(str).str.replace(",", ""), errors="coerce").fillna(0) if "debit" in found else 0
        credit = pd.to_numeric(df[found["credit"]].astype(str).str.replace(",", ""), errors="coerce").fillna(0) if "credit" in found else 0
        amount = credit - debit
    else:
        raise ValueError("Your file must contain Amount, or separate Debit and Credit columns.")

    df["amount"] = amount
    df = df.dropna(subset=["date", "amount"])
    df["transaction_type"] = np.where(df["amount"] >= 0, "Income", "Expense")
    df["amount"] = df["amount"].abs()
    df["category"] = [categorize(d, a if t == "Income" else -a) for d, a, t in zip(df["description"], df["amount"], df["transaction_type"])]
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    return df[["date", "description", "amount", "transaction_type", "category"]]

def read_uploaded_file(uploaded):
    name = uploaded.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded)
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(uploaded)
    if name.endswith(".pdf"):
        try:
            import pdfplumber
        except ImportError:
            raise ValueError("PDF support needs pdfplumber. Install it with: pip install pdfplumber")
        rows = []
        with pdfplumber.open(uploaded) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if table and len(table) > 1:
                    rows.extend(table)
        if not rows:
            raise ValueError("No readable transaction table was found in this PDF. Try CSV or Excel.")
        return pd.DataFrame(rows[1:], columns=rows[0])
    raise ValueError("Upload a CSV, Excel, or text-based PDF file.")

# -------------------- FINANCIAL CALCULATORS --------------------
def calculate_emi(principal, annual_rate, months):
    if months <= 0:
        return 0.0
    monthly_rate = annual_rate / 12 / 100
    if monthly_rate == 0:
        return principal / months
    factor = (1 + monthly_rate) ** months
    return principal * monthly_rate * factor / (factor - 1)

def money(value):
    return f"₹{value:,.0f}"

def affordability(income, expenses, existing_emi, savings, purchase_price, down_pct, annual_rate, years, reserve):
    down_payment = purchase_price * down_pct / 100
    loan = max(0, purchase_price - down_payment)
    new_emi = calculate_emi(loan, annual_rate, years * 12)
    monthly_surplus = income - expenses - existing_emi
    available_savings = max(0, savings - reserve)
    cash_gap = max(0, down_payment - available_savings)
    post_purchase_surplus = monthly_surplus - new_emi
    return {
        "down_payment": down_payment, "loan": loan, "new_emi": new_emi,
        "monthly_surplus": monthly_surplus, "cash_gap": cash_gap,
        "post_purchase_surplus": post_purchase_surplus,
        "emi_ratio": ((existing_emi + new_emi) / income * 100) if income > 0 else 0
    }

init_db()
st.title("💰 AI Personal Finance Coach")
st.caption("A student project prototype for household budgeting, affordability checks and savings goals.")
st.info("Use sample or anonymised data. This prototype does not connect to banks and is not professional financial advice.")

with st.sidebar:
    st.header("📂 Transaction data")
    uploaded_file = st.file_uploader("Upload bank statement", type=["csv", "xlsx", "xls", "pdf"])
    if uploaded_file:
        try:
            raw = read_uploaded_file(uploaded_file)
            normalized = normalize_transactions(raw)
            st.success(f"Read {len(normalized)} transactions.")
            if st.button("Save transactions to dashboard", type="primary"):
                save_transactions(normalized)
                st.success("Transactions saved.")
        except Exception as e:
            st.error(str(e))
    if st.button("Load sample transactions"):
        sample = pd.read_csv("sample_transactions.csv")
        save_transactions(normalize_transactions(sample))
        st.success("Sample transactions added.")
    if st.button("Clear all saved transactions"):
        clear_saved_transactions()
        st.warning("Saved transaction data cleared.")

tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "🚗 Can I afford it?", "🎯 Savings goals", "💬 Finance assistant"])

with tab1:
    st.subheader("Household money overview")
    tx = load_saved_transactions()
    if tx.empty:
        st.write("No transactions saved yet. Upload a CSV/Excel statement or load the sample data from the sidebar.")
    else:
        tx["date"] = pd.to_datetime(tx["date"])
        income = tx.loc[tx.transaction_type == "Income", "amount"].sum()
        expenses = tx.loc[tx.transaction_type == "Expense", "amount"].sum()
        net = income - expenses
        c1, c2, c3 = st.columns(3)
        c1.metric("Total income", money(income))
        c2.metric("Total expenses", money(expenses))
        c3.metric("Net cash flow", money(net), delta=money(net))
        left, right = st.columns(2)
        exp_by_cat = tx[tx.transaction_type == "Expense"].groupby("category", as_index=False)["amount"].sum()
        if not exp_by_cat.empty:
            left.plotly_chart(px.pie(exp_by_cat, names="category", values="amount", title="Expense distribution"), use_container_width=True)
        monthly = tx.assign(month=tx.date.dt.to_period("M").astype(str)).groupby(["month", "transaction_type"], as_index=False)["amount"].sum()
        if not monthly.empty:
            right.plotly_chart(px.bar(monthly, x="month", y="amount", color="transaction_type", barmode="group", title="Monthly income vs expenses"), use_container_width=True)
        st.subheader("Transactions")
        st.dataframe(tx.sort_values("date", ascending=False), use_container_width=True, hide_index=True)
        st.caption("Categories are assigned using transparent keyword rules. Review them before making decisions.")

with tab2:
    st.subheader("Purchase affordability simulator")
    col1, col2 = st.columns(2)
    with col1:
        monthly_income = st.number_input("Monthly household take-home income (₹)", min_value=0, value=70000, step=1000)
        monthly_expenses = st.number_input("Monthly household expenses excluding EMIs (₹)", min_value=0, value=32000, step=1000)
        current_emi = st.number_input("Existing monthly EMIs (₹)", min_value=0, value=8000, step=500)
        current_savings = st.number_input("Current savings (₹)", min_value=0, value=300000, step=10000)
    with col2:
        price = st.number_input("Purchase price (₹)", min_value=0, value=1000000, step=50000)
        down_pct = st.slider("Down payment (%)", min_value=0, max_value=100, value=20)
        rate = st.number_input("Annual interest rate (%)", min_value=0.0, max_value=40.0, value=9.0, step=0.25)
        years = st.slider("Loan duration (years)", min_value=1, max_value=30, value=5)
        reserve = st.number_input("Emergency savings to protect (₹)", min_value=0, value=150000, step=10000)
    result = affordability(monthly_income, monthly_expenses, current_emi, current_savings, price, down_pct, rate, years, reserve)
    st.divider()
    a, b, c = st.columns(3)
    a.metric("Estimated new EMI", money(result["new_emi"]))
    b.metric("Monthly surplus after purchase", money(result["post_purchase_surplus"]))
    c.metric("EMIs as % of income", f'{result["emi_ratio"]:.1f}%')
    st.write(f"**Down payment:** {money(result['down_payment'])}  |  **Estimated loan:** {money(result['loan'])}")
    st.write(f"**Savings gap for down payment after protecting reserve:** {money(result['cash_gap'])}")
    if result["cash_gap"] > 0:
        st.warning("Your available savings do not fully cover the down payment while preserving the emergency reserve.")
    if result["post_purchase_surplus"] < 0:
        st.error("The estimated EMI makes monthly cash flow negative. Consider a lower-cost purchase, larger down payment, or longer timeline.")
    elif result["emi_ratio"] > 40:
        st.warning("Total EMIs exceed 40% of take-home income in this scenario. Review affordability carefully.")
    else:
        st.success("This scenario leaves a positive monthly surplus. Check insurance, fuel, maintenance and other ownership costs before deciding.")
    st.caption("EMI is an estimate based on a fixed interest rate. Lender fees, insurance, taxes and variable rates are not included.")

with tab3:
    st.subheader("Plan a savings goal")
    g1, g2 = st.columns(2)
    with g1:
        goal_name = st.text_input("Goal name", "House down payment")
        target = st.number_input("Target amount (₹)", min_value=1, value=1500000, step=50000)
        saved = st.number_input("Amount already saved (₹)", min_value=0, value=200000, step=10000)
    with g2:
        months = st.number_input("Months until target date", min_value=1, value=36, step=1)
        monthly_contribution = st.number_input("Planned monthly contribution (₹)", min_value=0, value=20000, step=1000)
    remaining = max(0, target - saved)
    required = remaining / months
    projected = saved + monthly_contribution * months
    st.metric("Monthly saving required", money(required))
    st.metric(f"Projected amount in {months} months", money(projected))
    if projected >= target:
        st.success(f"At this contribution, you are on track for {goal_name}.")
    else:
        st.warning(f"You may fall short by {money(target - projected)}. Increase monthly savings or extend the timeline.")

with tab4:
    st.subheader("Ask your finance coach")
    st.write("Ask a simple question about the transactions currently saved, or use the affordability and goal tabs for detailed calculations.")
    question = st.text_input("Your question", placeholder="How much did I spend on food?")
    if st.button("Get answer"):
        tx = load_saved_transactions()
        q = question.lower()
        if tx.empty:
            st.info("Upload or load transactions first so I can analyse your spending.")
        elif "income" in q:
            total = tx.loc[tx.transaction_type == "Income", "amount"].sum()
            st.success(f"Recorded income in the uploaded data is {money(total)}.")
        elif "expense" in q or "spend" in q or "spent" in q:
            if "food" in q:
                subset = tx[(tx.transaction_type == "Expense") & (tx.category == "Food")]
                st.success(f"Recorded Food spending is {money(subset.amount.sum())}.")
            elif "transport" in q:
                subset = tx[(tx.transaction_type == "Expense") & (tx.category == "Transport")]
                st.success(f"Recorded Transport spending is {money(subset.amount.sum())}.")
            else:
                total = tx.loc[tx.transaction_type == "Expense", "amount"].sum()
                st.success(f"Total recorded expenses are {money(total)}.")
        elif "save" in q or "saving" in q:
            inc = tx.loc[tx.transaction_type == "Income", "amount"].sum()
            exp = tx.loc[tx.transaction_type == "Expense", "amount"].sum()
            st.success(f"Net cash flow in this dataset is {money(inc-exp)}. This is not necessarily your long-term monthly saving rate.")
        else:
            st.info("I can currently answer basic questions about recorded income, total expenses, food spending, transport spending and net cash flow. More advanced conversational AI can be added later.")
