import jdatetime
import gspread
from google.oauth2.service_account import Credentials
from config import Config
from services.schedule_constants import AVAILABLE_TIMES, EXTRA_ROWS_PER_DAY

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

JALALI_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

WEEKDAY_FA = {
    0: "دوشنبه", 1: "سه‌شنبه", 2: "چهارشنبه", 3: "پنجشنبه",
    4: "جمعه", 5: "شنبه", 6: "یکشنبه",
}

COLUMN_HEADERS = ["ردیف", "نام مراجع", "ساعت", "نوع جلسه", "وضعیت", "موبایل", "یادداشت"]

# ردیف‌های استاندارد (به تعداد AVAILABLE_TIMES) + چندتا ردیف بافر خالی برای
# نوبت‌های با ساعت غیراستاندارد — تا اون‌ها هم همون داخل روز خودشون
# نوشته بشن، نه ته کل شیت.
DATA_ROWS_PER_DAY = len(AVAILABLE_TIMES) + EXTRA_ROWS_PER_DAY


def _days_in_month(jy, jm):
    for d in range(31, 0, -1):
        try:
            jdatetime.date(jy, jm, d)
            return d
        except ValueError:
            continue
    return 29


def build_year(jalali_year=1405, force=False):
    creds = Credentials.from_service_account_file(
        Config.GOOGLE_CREDENTIALS_PATH, scopes=SCOPES
    )
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(Config.GOOGLE_SHEET_ID)

    existing_titles = [ws.title for ws in spreadsheet.worksheets()]
    report = {}

    for month_index, month_name in enumerate(JALALI_MONTHS, start=1):
        days = _days_in_month(jalali_year, month_index)
        total_rows = 2 + days * (2 + DATA_ROWS_PER_DAY + 1)
        expected_title_cell = f"دفتر نوبت‌دهی کلینیک مسیر — {month_name} {jalali_year}"

        if month_name in existing_titles:
            worksheet = spreadsheet.worksheet(month_name)
            current_a1 = worksheet.acell("A1").value
            if current_a1 == expected_title_cell and not force:
                report[month_name] = "skipped (already built)"
                continue
            worksheet.clear()
            worksheet.resize(rows=total_rows, cols=7)
        else:
            worksheet = spreadsheet.add_worksheet(title=month_name, rows=total_rows, cols=7)

        rows_data = [
            [expected_title_cell],
            ["🟢 paid = پرداخت موفق   🔴 cancel = کنسل شده   🟡 not = ثبت بدون پرداخت (بدهی)   |   online = آنلاین   حضوری = حضوری   |   ✚ = نوبت با ساعت غیراستاندارد"],
        ]

        for d in range(1, days + 1):
            j_date = jdatetime.date(jalali_year, month_index, d)
            g_date = j_date.togregorian()
            weekday_fa = WEEKDAY_FA[g_date.weekday()]
            header_text = (
                f"{weekday_fa}  —  {d} {month_name} {jalali_year}  "
                f"({g_date.year}/{g_date.month:02d}/{g_date.day:02d})"
            )
            rows_data.append([header_text])
            rows_data.append(COLUMN_HEADERS)
            rows_data.extend([["", "", "", "", "", "", ""] for _ in range(DATA_ROWS_PER_DAY)])
            rows_data.append([""])

        worksheet.update("A1", rows_data, value_input_option="USER_ENTERED")
        worksheet.format("A1", {"textFormat": {"bold": True, "fontSize": 12}})
        report[month_name] = f"built ({total_rows} rows, {DATA_ROWS_PER_DAY} data rows/day)"

    return report