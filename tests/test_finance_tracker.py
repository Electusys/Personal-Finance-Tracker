import json
from decimal import Decimal
from pathlib import Path

import pytest

import personel_finance_tracker as app


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1500", Decimal("1500.00")),
        ("1.250,50", Decimal("1250.50")),
        ("1,250.50", Decimal("1250.50")),
        ("10,000", Decimal("10000.00")),
        ("10.000", Decimal("10000.00")),
        ("1.250.000", Decimal("1250000.00")),
        ("10,000,000", Decimal("10000000.00")),
        ("1250,50", Decimal("1250.50")),
        ("99.99", Decimal("99.99")),
        (" 1 000,25 ", Decimal("1000.25")),
    ],
)
def test_clean_amount_parses_common_formats(raw, expected):
    assert app.clean_amount(raw) == expected


@pytest.mark.parametrize("raw", ["", "abc", "--", "€50"])
def test_clean_amount_rejects_invalid(raw):
    with pytest.raises(ValueError):
        app.clean_amount(raw)


def test_load_data_missing_file_returns_empty(tmp_path: Path):
    path = tmp_path / "finance_data.json"
    assert app.load_data(path) == []


def test_load_data_migrates_legacy_records(tmp_path: Path):
    path = tmp_path / "finance_data.json"
    path.write_text(
        json.dumps(
            [
                {
                    "type": "Income",
                    "amount": 1000.5,
                    "category": "Salary",
                    "date": "2024-01-01 10:00:00",
                }
            ]
        ),
        encoding="utf-8",
    )

    data = app.load_data(path)

    assert len(data) == 1
    assert data[0]["amount"] == "1000.50"
    assert "id" in data[0]
    assert len(data[0]["id"]) > 10

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved[0]["amount"] == "1000.50"
    assert saved[0]["id"] == data[0]["id"]


def test_load_data_backs_up_corrupt_json(tmp_path: Path):
    path = tmp_path / "finance_data.json"
    path.write_text("{not-json", encoding="utf-8")

    data = app.load_data(path)

    assert data == []
    backups = list(tmp_path.glob("finance_data.corrupt.*.json"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "{not-json"


def test_save_and_delete_keeps_stable_ids(tmp_path: Path):
    path = tmp_path / "finance_data.json"
    data = [
        {
            "id": "aaa",
            "type": "Expense",
            "amount": "10.00",
            "category": "Food",
            "date": "2024-01-01 10:00:00",
        },
        {
            "id": "bbb",
            "type": "Expense",
            "amount": "20.00",
            "category": "Rent",
            "date": "2024-01-02 10:00:00",
        },
    ]
    app.save_data(path, data)

    loaded = app.load_data(path)
    deleted = loaded.pop(0)
    app.save_data(path, loaded)

    remaining = app.load_data(path)
    assert deleted["id"] == "aaa"
    assert len(remaining) == 1
    assert remaining[0]["id"] == "bbb"
    assert remaining[0]["amount"] == "20.00"


def test_default_data_path_is_beside_script():
    assert app.default_data_path() == Path(app.__file__).resolve().parent / "finance_data.json"


def test_parse_args_data_flag(tmp_path: Path):
    custom = tmp_path / "custom.json"
    args = app.parse_args(["--data", str(custom)])
    assert args.data == custom
