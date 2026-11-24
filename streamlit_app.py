"""Streamlit dashboard for Personal Finance Tracker."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

import pandas as pd
import streamlit as st

from ai_assistant import ask_finance_assistant, get_api_key
from app_paths import app_dir
from personel_finance_tracker import (
    amount_to_str,
    clean_amount,
    default_data_path,
    load_data,
    parse_amount_field,
    save_data,
)

ROOT = app_dir()
DATA_PATH = default_data_path()


def reload_data() -> list[dict]:
    return load_data(DATA_PATH)


def transactions_to_frame(data: list[dict]) -> pd.DataFrame:
    if not data:
        return pd.DataFrame(columns=["id", "type", "category", "amount", "date"])
    rows = []
    for item in data:
        rows.append(
            {
                "id": item["id"],
                "type": item["type"],
                "category": item["category"],
                "amount": float(parse_amount_field(item["amount"])),
                "date": item.get("date", ""),
            }
        )
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    return frame.sort_values("date", ascending=False, na_position="last")


def compute_totals(data: list[dict]) -> tuple[Decimal, Decimal, Decimal]:
    income = sum(
        (parse_amount_field(i["amount"]) for i in data if i["type"] == "Income"),
        Decimal("0.00"),
    )
    expense = sum(
        (parse_amount_field(i["amount"]) for i in data if i["type"] == "Expense"),
        Decimal("0.00"),
    )
    return income, expense, income - expense


def add_transaction(t_type: str, amount_raw: str, category: str) -> None:
    amount = clean_amount(amount_raw)
    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    category = category.strip()
    if not category:
        raise ValueError("Category cannot be empty.")

    data = reload_data()
    data.append(
        {
            "id": str(uuid.uuid4()),
            "type": t_type,
            "amount": amount_to_str(amount),
            "category": category,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    save_data(DATA_PATH, data)


def delete_by_id(record_id: str) -> bool:
    data = reload_data()
    new_data = [item for item in data if item["id"] != record_id]
    if len(new_data) == len(data):
        return False
    save_data(DATA_PATH, new_data)
    return True


def render_sidebar(data: list[dict]) -> None:
    st.sidebar.header("Add transaction")
    with st.sidebar.form("add_form", clear_on_submit=True):
        t_type = st.selectbox("Type", ["Expense", "Income"])
        amount_raw = st.text_input("Amount", placeholder="1.250,50 or 10,000")
        category = st.text_input("Category", placeholder="Food, Rent, Salary")
        submitted = st.form_submit_button("Save", use_container_width=True)
        if submitted:
            try:
                add_transaction(t_type, amount_raw, category)
                st.sidebar.success("Saved.")
                st.rerun()
            except ValueError as exc:
                st.sidebar.error(str(exc))

    st.sidebar.divider()
    st.sidebar.header("Delete transaction")
    if not data:
        st.sidebar.caption("No transactions yet.")
        return

    labels = {
        item["id"]: (
            f"{item.get('date', '')} · {item['type']} · "
            f"{item['category']} · {item['amount']}"
        )
        for item in reversed(data)
    }
    selected = st.sidebar.selectbox(
        "Select record",
        options=list(labels.keys()),
        format_func=lambda rid: labels[rid],
    )
    if st.sidebar.button("Delete selected", type="primary", use_container_width=True):
        if delete_by_id(selected):
            st.sidebar.success("Deleted.")
            st.rerun()
        else:
            st.sidebar.error("Record not found.")


def render_overview(data: list[dict], frame: pd.DataFrame) -> None:
    income, expense, balance = compute_totals(data)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Income", f"${income:,.2f}")
    c2.metric("Expense", f"${expense:,.2f}")
    c3.metric("Balance", f"${balance:,.2f}")
    c4.metric("Transactions", f"{len(data)}")

    left, right = st.columns(2)
    with left:
        st.subheader("Income vs expense")
        chart_df = pd.DataFrame(
            {"Amount": [float(income), float(expense)]},
            index=["Income", "Expense"],
        )
        st.bar_chart(chart_df)
    with right:
        st.subheader("Expense by category")
        expenses = frame[frame["type"] == "Expense"]
        if expenses.empty:
            st.caption("No expenses yet.")
        else:
            by_cat = (
                expenses.groupby("category", as_index=True)["amount"]
                .sum()
                .sort_values(ascending=False)
            )
            st.bar_chart(by_cat)

    st.subheader("Transactions")
    if frame.empty:
        st.info("No transactions yet. Add one from the sidebar.")
    else:
        display = frame.copy()
        display["amount"] = display["amount"].map(lambda x: f"${x:,.2f}")
        st.dataframe(
            display[["date", "type", "category", "amount", "id"]],
            use_container_width=True,
            hide_index=True,
        )


def render_chat(data: list[dict]) -> None:
    st.subheader("AI assistant")
    if get_api_key() is None:
        st.warning(
            "GEMINI_API_KEY is missing. Copy `.env.example` to `.env` and add your key. "
            "The rest of the dashboard still works."
        )
        return

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Ask about your spending, balance, or savings tips…")
    if not prompt:
        return

    st.session_state.chat_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                answer = ask_finance_assistant(prompt, data)
            except ValueError as exc:
                answer = f"Could not get an answer: {exc}"
        st.markdown(answer)
    st.session_state.chat_messages.append({"role": "assistant", "content": answer})


def main() -> None:
    st.set_page_config(
        page_title="Personal Finance Tracker",
        page_icon=":moneybag:",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("Personal Finance Tracker")
    st.caption(f"Data file: `{DATA_PATH}`")

    data = reload_data()
    render_sidebar(data)
    data = reload_data()
    frame = transactions_to_frame(data)

    tab_overview, tab_chat = st.tabs(["Overview", "AI chat"])
    with tab_overview:
        render_overview(data, frame)
    with tab_chat:
        render_chat(data)


if __name__ == "__main__":
    main()
