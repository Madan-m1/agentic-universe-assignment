import csv

from solution.ingestion.csv_processor import process_csv_file


def write_csv(path, headers, rows):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(headers)
        writer.writerows(rows)


def test_process_valid_csv(tmp_path):
    path = tmp_path / "leads.csv"

    write_csv(
        path,
        ["Customer_Name", "Mobile No", "Policy No", "Premium"],
        [
            ["Aarav Menon", "9932302346", "MOT/001", "27554"],
            ["Nikhil Nair", "8880395512", "MOT/002", "6850"],
        ],
    )

    result = process_csv_file(path, "motor_renewal", "batch_001")

    assert len(result["accepted"]) == 2
    assert len(result["rejected"]) == 0
    assert result["nonblank_rows"] == 2


def test_blank_rows_are_skipped(tmp_path):
    path = tmp_path / "leads.csv"

    write_csv(
        path,
        ["Customer Name", "Phone", "Policy"],
        [
            ["Aarav Menon", "9932302346", "MOT/001"],
            ["", "", ""],
            ["Nikhil Nair", "8880395512", "MOT/002"],
        ],
    )

    result = process_csv_file(path, "motor_renewal", "batch_001")

    assert len(result["accepted"]) == 2
    assert result["nonblank_rows"] == 2
    assert result["accepted"][1]["row_number"] == 2


def test_rejected_rows_keep_nonblank_row_numbers(tmp_path):
    path = tmp_path / "leads.csv"

    write_csv(
        path,
        ["Customer Name", "Phone", "Policy"],
        [
            ["Aarav Menon", "9932302346", "MOT/001"],
            ["", "", ""],
            ["Nikhil Nair", "12345", "MOT/002"],
        ],
    )

    result = process_csv_file(path, "motor_renewal", "batch_001")

    assert len(result["accepted"]) == 1
    assert len(result["rejected"]) == 1
    assert result["rejected"][0]["row_number"] == 2
    assert result["rejected"][0]["reason"] == "invalid_phone"


def test_optional_field_warning_is_recorded(tmp_path):
    path = tmp_path / "leads.csv"

    write_csv(
        path,
        ["Customer Name", "Phone", "Policy", "Language"],
        [
            ["Aarav Menon", "9932302346", "MOT/001", "Hindi"],
        ],
    )

    result = process_csv_file(path, "motor_renewal", "batch_001")

    assert len(result["accepted"]) == 1
    assert result["accepted"][0]["data"]["preferred_language"] is None
    assert result["warnings"] == [
        {
            "batch_id": "batch_001",
            "row_number": 1,
            "field": "preferred_language",
        }
    ]


def test_unknown_columns_are_ignored(tmp_path):
    path = tmp_path / "leads.csv"

    write_csv(
        path,
        ["Customer Name", "Phone", "Policy", "Extra Column"],
        [
            ["Aarav Menon", "9932302346", "MOT/001", "ignored"],
        ],
    )

    result = process_csv_file(path, "motor_renewal", "batch_001")

    assert len(result["accepted"]) == 1
    assert "Extra Column" not in result["accepted"][0]["data"]