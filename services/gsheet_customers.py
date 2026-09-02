import os
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from config import Config, BASE_DIR

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SHEET_TAB_NAME = "باشگاه مشتریان"
HEADERS = ["شماره", "نام", "تاریخ تولد", "شهر"]

_client = None


def _get_worksheet():
    global _client
    if _client is None:
        creds = Credentials.from_service_account_file(
            Config.GOOGLE_CREDENTIALS_PATH, scopes=SCOPES
        )
        _client = gspread.authorize(creds)

    sheet_id = getattr(Config, "CUSTOMERS_SHEET_ID", "") or Config.GOOGLE_SHEET_ID
    spreadsheet = _client.open_by_key(sheet_id)

    try:
        worksheet = spreadsheet.worksheet(SHEET_TAB_NAME)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=SHEET_TAB_NAME, rows=500, cols=4)
        worksheet.update("A1:D1", [HEADERS], value_input_option="USER_ENTERED")
        worksheet.format("A1:D1", {"textFormat": {"bold": True}})

    return worksheet


def _log_error(message):
    try:
        with open(os.path.join(BASE_DIR, "gsheet_error.log"), "a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()} — [باشگاه مشتریان] {message}\n")
    except Exception:
        pass


def _search_key(phone):
    """
    عمداً از USER_ENTERED استفاده می‌کنیم (نه RAW) چون همون ظاهر بدون صفر اول
    که دوست داری رو حفظ می‌کنه — گوگل‌شیت شماره رو به‌عنوان عدد ذخیره می‌کنه.
    ولی همین یعنی وقتی می‌خوایم یه ردیف موجود رو برای ویرایش/حذف پیدا کنیم،
    باید دقیقاً با همون فرمت (بدون صفر اول) جستجو کنیم، وگرنه find() هیچ‌وقت
    تطبیق پیدا نمی‌کنه و همیشه فکر می‌کنه ردیف جدیده — همون باگی که داشتیم.
    """
    return phone[1:] if phone.startswith("0") else phone


def upsert_customer(customer):
    """
    مشتری رو بر اساس شماره پیدا می‌کنه و آپدیت می‌کنه؛ اگه نبود ردیف جدید
    اضافه می‌کنه. هرگز نباید فرآیند اصلی (ثبت مشتری توی دیتابیس) رو متوقف کنه.
    """
    try:
        worksheet = _get_worksheet()
        cell = worksheet.find(_search_key(customer.phone), in_column=1)
        row = [customer.phone, customer.name, customer.birthdate or "", customer.city or ""]

        if cell:
            worksheet.update(f"A{cell.row}:D{cell.row}", [row], value_input_option="USER_ENTERED")
        else:
            worksheet.append_row(row, value_input_option="USER_ENTERED")

        return True
    except Exception as e:
        _log_error(f"خطا در ثبت/آپدیت مشتری {customer.phone}: {e}")
        return False


def delete_customer_row(phone):
    try:
        worksheet = _get_worksheet()
        cell = worksheet.find(_search_key(phone), in_column=1)
        if cell:
            worksheet.delete_rows(cell.row)
        return True
    except Exception as e:
        _log_error(f"خطا در حذف مشتری {phone}: {e}")
        return False


def clear_all():
    """پاک‌کردن همه‌ی ردیف‌های داده (هدر دست‌نخورده می‌مونه) — برای پاک‌سازی داده‌ی تستی."""
    try:
        worksheet = _get_worksheet()
        worksheet.batch_clear(["A2:D1000"])
        return True
    except Exception as e:
        _log_error(f"خطا در پاک‌سازی کامل باشگاه مشتریان: {e}")
        return False
