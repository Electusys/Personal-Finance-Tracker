import json
import os
from datetime import datetime

DATA_FILE = "finance_data.json"


def load_data():
    """Load financial data from JSON file."""
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_data(data):
    """Save financial data to JSON file."""
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def clean_amount(amount_str):
    """
    Normalize inputs like 10.000,00 or 10,000.00 to a float.
    Supports both European and American number formats.
    """
    amount_str = amount_str.strip()

    # Handle mixed formats like 1.250,50 or 1,250.50
    if "." in amount_str and "," in amount_str:
        if amount_str.find(".") < amount_str.find(","):
            # European format: 1.250,50 -> 1250.50
            amount_str = amount_str.replace(".", "").replace(",", ".")
        else:
            # US format: 1,250.50 -> 1250.50
            amount_str = amount_str.replace(",", "")

    # Handle single comma format: 1250,50 -> 1250.50
    elif "," in amount_str:
        amount_str = amount_str.replace(",", ".")

    return float(amount_str)


def print_header():
    """Display application header with ASCII art."""
    print(r"""
    ========================================================================
    $$$$$$$$\ $$$$$$\ $$\   $$\  $$$$$$\  $$\   $$\  $$$$$$\  $$$$$$$$\ 
    $$  _____|\_$$  _|$$$\  $$ |$$  __$$\ $$$\  $$ |$$  __$$\ $$  _____|
    $$ |        $$ |  $$$$\ $$ |$$ /  $$ |$$$$\ $$ |$$ /  \__|$$ |      
    $$$$$\      $$ |  $$ $$\$$ |$$$$$$$$ |$$ $$\$$ |$$ |      $$$$$\    
    $$  __|     $$ |  $$ \$$$$ |$$  __$$ |$$ \$$$$ |$$ |      $$  __|   
    $$ |        $$ |  $$ |\$$$ |$$ |  $$ |$$ |\$$$ |$$ |  $$\ $$ |      
    $$ |      $$$$$$\ $$ | \$$ |$$ |  $$ |$$ | \$$ |\$$$$$$  |$$$$$$$$\ 
    \__|      \______|\__|  \__|\__|  \__|\__|  \__| \______/ \________|

                        PERSONAL FINANCE TRACKER v1.0
    ========================================================================
    """)


def show_summary(data):
    """Display financial summary with total income, expenses, and balance."""
    total_income = sum(item["amount"] for item in data if item["type"] == "Income")
    total_expense = sum(item["amount"] for item in data if item["type"] == "Expense")
    balance = total_income - total_expense

    print("\n" + "┌─────────────────────────────────────┐")
    print(f"│         FINANCIAL SUMMARY           │")
    print("├─────────────────────────────────────┤")
    print(f"│  Total Income  : ${total_income:>14,.2f}  │")
    print(f"│  Total Expense : ${total_expense:>14,.2f}  │")
    print(f"│  Net Balance   : ${balance:>14,.2f}  │")
    print("└─────────────────────────────────────┘")


def show_category_breakdown(data):
    """Display spending breakdown by category."""
    if not data:
        print("\n[!] No transactions found.")
        return

    categories = {}
    for item in data:
        cat = item["category"]
        if cat not in categories:
            categories[cat] = {"Income": 0, "Expense": 0}
        categories[cat][item["type"]] += item["amount"]

    print("\n" + "┌────────────────────────────────────────────────┐")
    print("│         CATEGORY BREAKDOWN                     │")
    print("├────────────────────────────────────────────────┤")
    for cat, amounts in categories.items():
        income = amounts["Income"]
        expense = amounts["Expense"]
        net = income - expense
        print(f"│ {cat:<20} │ ${net:>18,.2f} │")
    print("└────────────────────────────────────────────────┘")


def add_transaction(data):
    """Add a new income or expense transaction."""
    print("\n--- NEW TRANSACTION ---")

    while True:
        t_type_raw = input("Type (I for Income / E for Expense): ").upper()
        if t_type_raw in ['I', 'E']:
            t_type = "Income" if t_type_raw == "I" else "Expense"
            break
        print("❌ Invalid input! Please enter 'I' or 'E'.")

    raw_amount = input("Amount (e.g., 1.250,50 or 10,000): $")

    try:
        amount = clean_amount(raw_amount)
        if amount <= 0:
            print("❌ Error: Amount must be greater than zero!")
            return
    except ValueError:
        print("❌ Error: Invalid format! Use numbers (e.g., 1500 or 1.500,50).")
        return

    category = input("Category (e.g., Food, Rent, Salary): ").strip()
    if not category:
        print("❌ Error: Category cannot be empty!")
        return

    data.append({
        "type": t_type,
        "amount": amount,
        "category": category,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    save_data(data)
    print(f"✅ Successfully added: {category} (${amount:,.2f})")


def list_transactions(data):
    """Display all transactions with details."""
    if not data:
        print("\n[!] No transactions found.")
        return

    print("\n" + "=" * 70)
    print("ID  | TYPE    | CATEGORY         | AMOUNT        | DATE")
    print("=" * 70)
    for i, item in enumerate(data, 1):
        date = item.get("date", "N/A")
        print(f"{i:<3} | {item['type']:<7} | {item['category']:<16} | ${item['amount']:>10,.2f} | {date}")
    print("=" * 70)


def delete_transaction(data):
    """Delete a transaction by ID."""
    if not data:
        print("\n[!] No transactions to delete.")
        return

    list_transactions(data)
    try:
        transaction_id = int(input("\nEnter transaction ID to delete (0 to cancel): "))
        if transaction_id == 0:
            print("Deletion cancelled.")
            return
        if 1 <= transaction_id <= len(data):
            deleted = data.pop(transaction_id - 1)
            save_data(data)
            print(f"✅ Deleted: {deleted['category']} (${deleted['amount']:,.2f})")
        else:
            print("❌ Invalid ID!")
    except ValueError:
        print("❌ Please enter a valid number!")


def main():
    """Main application loop."""
    data = load_data()

    while True:
        print_header()
        print(" [1] Add New Transaction")
        print(" [2] View Summary")
        print(" [3] Transaction History")
        print(" [4] Category Breakdown")
        print(" [5] Delete Transaction")
        print(" [6] Exit")
        print("\n" + "=" * 72)

        choice = input("Select an option » ")

        if choice == "1":
            add_transaction(data)
        elif choice == "2":
            show_summary(data)
        elif choice == "3":
            list_transactions(data)
        elif choice == "4":
            show_category_breakdown(data)
        elif choice == "5":
            delete_transaction(data)
        elif choice == "6":
            print("\n💾 Saving data... Goodbye!")
            break
        else:
            print("\n⚠️ Invalid selection! Please choose 1-6.")

        input("\nPress Enter to return to menu...")
        os.system('cls' if os.name == 'nt' else 'clear')


if __name__ == "__main__":
    main()