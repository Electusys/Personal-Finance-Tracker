import argparse
import json
import os
import shutil
import sys
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app_paths import app_dir

DEFAULT_DATA_FILE = "finance_data.json"
VALID_TYPES = frozenset({"Income", "Expense"})


def default_data_path() -> Path:
    """Data file lives next to the app/exe, not inside a frozen bundle."""
    return app_dir() / DEFAULT_DATA_FILE


def clean_amount(amount_str: str) -> Decimal:
    """
    Normalize inputs like 10.000,00 or 10,000.00 to Decimal.

    Supports European and US formats, including thousand separators
    without a decimal part (10.000 and 10,000 -> 10000).
    """
    amount_str = amount_str.strip().replace(" ", "").replace("\u00a0", "")
    if not amount_str:
        raise ValueError("empty amount")

    if amount_str.count(".") > 1 and "," not in amount_str:
        # European thousands only: 10.000 or 1.250.000
        amount_str = amount_str.replace(".", "")
    elif amount_str.count(",") > 1 and "." not in amount_str:
        # US thousands only with commas: 10,000,000
        amount_str = amount_str.replace(",", "")
    elif "." in amount_str and "," in amount_str:
        if amount_str.find(".") < amount_str.find(","):
            # European: 1.250,50 -> 1250.50
            amount_str = amount_str.replace(".", "").replace(",", ".")
        else:
            # US: 1,250.50 -> 1250.50
            amount_str = amount_str.replace(",", "")
    elif "," in amount_str:
        left, _, right = amount_str.partition(",")
        if len(right) == 3 and right.isdigit() and left.replace("-", "").isdigit():
            # Thousands: 10,000 -> 10000
            amount_str = left + right
        else:
            # Decimal: 1250,50 -> 1250.50
            amount_str = amount_str.replace(",", ".")
    elif "." in amount_str:
        left, _, right = amount_str.partition(".")
        if len(right) == 3 and right.isdigit() and left.replace("-", "").isdigit():
            # Thousands: 10.000 -> 10000
            amount_str = left + right

    try:
        value = Decimal(amount_str)
    except InvalidOperation as exc:
        raise ValueError("invalid amount") from exc

    if not value.is_finite():
        raise ValueError("invalid amount")
    return value.quantize(Decimal("0.01"))


def amount_to_str(amount: Decimal) -> str:
    return format(amount.quantize(Decimal("0.01")), "f")


def parse_amount_field(raw) -> Decimal:
    """Load amount from JSON (string preferred, number accepted for old files)."""
    if isinstance(raw, bool) or raw is None:
        raise ValueError("invalid amount field")
    if isinstance(raw, Decimal):
        return raw.quantize(Decimal("0.01"))
    if isinstance(raw, (int, float)):
        return Decimal(str(raw)).quantize(Decimal("0.01"))
    return Decimal(str(raw)).quantize(Decimal("0.01"))


def normalize_transaction(item: dict) -> dict | None:
    """Return a valid transaction dict, or None if the record is unusable."""
    if not isinstance(item, dict):
        return None

    t_type = item.get("type")
    if t_type not in VALID_TYPES:
        return None

    try:
        amount = parse_amount_field(item.get("amount"))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if amount <= 0:
        return None

    category = str(item.get("category", "")).strip()
    if not category:
        return None

    date = item.get("date")
    if not isinstance(date, str) or not date.strip():
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    record_id = item.get("id")
    if not isinstance(record_id, str) or not record_id.strip():
        record_id = str(uuid.uuid4())

    return {
        "id": record_id,
        "type": t_type,
        "amount": amount_to_str(amount),
        "category": category,
        "date": date.strip(),
    }


def load_data(path: Path) -> list[dict]:
    """Load financial data from JSON. Corrupt files are backed up, not wiped."""
    if not path.exists():
        return []

    try:
        with path.open("r", encoding="utf-8") as file:
            raw = json.load(file)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        backup_corrupt_file(path)
        print(f"[!] Data file was unreadable. Backed up and starting empty: {path.name}")
        return []

    if not isinstance(raw, list):
        backup_corrupt_file(path)
        print(f"[!] Data file had an unexpected shape. Backed up and starting empty: {path.name}")
        return []

    normalized = []
    changed = False
    for item in raw:
        record = normalize_transaction(item)
        if record is None:
            changed = True
            continue
        if (
            item.get("id") != record["id"]
            or str(item.get("amount")) != record["amount"]
            or item.get("date") != record["date"]
            or item.get("category") != record["category"]
        ):
            changed = True
        normalized.append(record)

    if changed:
        save_data(path, normalized)

    return normalized


def backup_corrupt_file(path: Path) -> Path | None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(f"{path.stem}.corrupt.{stamp}{path.suffix}")
    try:
        shutil.copy2(path, backup)
        return backup
    except OSError:
        try:
            path.rename(backup)
            return backup
        except OSError:
            return None


def save_data(path: Path, data: list[dict]) -> None:
    """Save financial data to JSON (atomic replace when possible)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = []
    for item in data:
        record = normalize_transaction(item)
        if record is not None:
            payload.append(record)

    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=4, ensure_ascii=False)
        file.write("\n")
    os.replace(temp_path, path)


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

                        PERSONAL FINANCE TRACKER v1.1
    ========================================================================
    """)


def format_money(amount: Decimal) -> str:
    return f"${amount:,.2f}"


def show_summary(data: list[dict]):
    """Display financial summary with total income, expenses, and balance."""
    total_income = sum(
        (parse_amount_field(item["amount"]) for item in data if item["type"] == "Income"),
        Decimal("0.00"),
    )
    total_expense = sum(
        (parse_amount_field(item["amount"]) for item in data if item["type"] == "Expense"),
        Decimal("0.00"),
    )
    balance = total_income - total_expense

    print("\n" + "┌─────────────────────────────────────┐")
    print("│         FINANCIAL SUMMARY           │")
    print("├─────────────────────────────────────┤")
    print(f"│  Total Income  : {format_money(total_income):>15}  │")
    print(f"│  Total Expense : {format_money(total_expense):>15}  │")
    print(f"│  Net Balance   : {format_money(balance):>15}  │")
    print("└─────────────────────────────────────┘")


def show_category_breakdown(data: list[dict]):
    """Display net amount by category (income minus expense)."""
    if not data:
        print("\n[!] No transactions found.")
        return

    categories: dict[str, dict[str, Decimal]] = {}
    for item in data:
        cat = item["category"]
        if cat not in categories:
            categories[cat] = {"Income": Decimal("0.00"), "Expense": Decimal("0.00")}
        categories[cat][item["type"]] += parse_amount_field(item["amount"])

    print("\n" + "┌────────────────────────────────────────────────┐")
    print("│         CATEGORY BREAKDOWN                     │")
    print("├────────────────────────────────────────────────┤")
    for cat, amounts in categories.items():
        net = amounts["Income"] - amounts["Expense"]
        print(f"│ {cat:<20} │ {format_money(net):>18} │")
    print("└────────────────────────────────────────────────┘")


def add_transaction(data: list[dict], path: Path):
    """Add a new income or expense transaction."""
    print("\n--- NEW TRANSACTION ---")

    while True:
        t_type_raw = input("Type (I for Income / E for Expense): ").upper().strip()
        if t_type_raw in ["I", "E"]:
            t_type = "Income" if t_type_raw == "I" else "Expense"
            break
        print("Invalid input! Please enter 'I' or 'E'.")

    raw_amount = input("Amount (e.g., 1.250,50 or 10,000): ")

    try:
        amount = clean_amount(raw_amount)
        if amount <= 0:
            print("Error: Amount must be greater than zero!")
            return
    except ValueError:
        print("Error: Invalid format! Use numbers (e.g., 1500, 10.000 or 1.500,50).")
        return

    category = input("Category (e.g., Food, Rent, Salary): ").strip()
    if not category:
        print("Error: Category cannot be empty!")
        return

    data.append(
        {
            "id": str(uuid.uuid4()),
            "type": t_type,
            "amount": amount_to_str(amount),
            "category": category,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    save_data(path, data)
    print(f"Successfully added: {category} ({format_money(amount)})")


def list_transactions(data: list[dict]):
    """Display all transactions with details."""
    if not data:
        print("\n[!] No transactions found.")
        return

    print("\n" + "=" * 78)
    print("ID  | TYPE    | CATEGORY         | AMOUNT        | DATE")
    print("=" * 78)
    for i, item in enumerate(data, 1):
        date = item.get("date", "N/A")
        amount = parse_amount_field(item["amount"])
        print(
            f"{i:<3} | {item['type']:<7} | {item['category']:<16} | "
            f"{format_money(amount):>12} | {date}"
        )
    print("=" * 78)


def delete_transaction(data: list[dict], path: Path):
    """Delete a transaction by list position (stable UUID kept in storage)."""
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
            save_data(path, data)
            amount = parse_amount_field(deleted["amount"])
            print(f"Deleted: {deleted['category']} ({format_money(amount)})")
        else:
            print("Invalid ID!")
    except ValueError:
        print("Please enter a valid number!")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Personal Finance Tracker")
    parser.add_argument(
        "--data",
        type=Path,
        default=None,
        help=f"Path to JSON data file (default: {DEFAULT_DATA_FILE} next to this script)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None):
    """Main application loop."""
    args = parse_args(argv)
    path = args.data.resolve() if args.data else default_data_path()
    data = load_data(path)

    while True:
        print_header()
        print(f" Data file: {path}")
        print(" [1] Add New Transaction")
        print(" [2] View Summary")
        print(" [3] Transaction History")
        print(" [4] Category Breakdown")
        print(" [5] Delete Transaction")
        print(" [6] Exit")
        print("\n" + "=" * 72)

        choice = input("Select an option » ").strip()

        if choice == "1":
            add_transaction(data, path)
        elif choice == "2":
            show_summary(data)
        elif choice == "3":
            list_transactions(data)
        elif choice == "4":
            show_category_breakdown(data)
        elif choice == "5":
            delete_transaction(data, path)
        elif choice == "6":
            print("\nGoodbye!")
            break
        else:
            print("\nInvalid selection! Please choose 1-6.")

        input("\nPress Enter to return to menu...")
        os.system("cls" if os.name == "nt" else "clear")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)
