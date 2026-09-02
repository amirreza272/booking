import os
from datetime import datetime
import jdatetime
import gspread
from google.oauth2.service_account import Credentials
from config import Config, BASE_DIR
from services.schedule_constants import AVAILABLE_TIMES, EXTRA_ROWS_PER_DAY

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

JALALI_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

STATUS_COLORS = {
    "paid":    {"red": 0.80, "green": 0.94, "blue": 0.80},
    "cancel":  {"red": 0.98, "green": 0.80, "blue": 0.80},
    "not":     {"red": 1.00, "green": 0.95, "blue": 0.75},
    "blocked": {"red": 0.85, "green": 0.85, "blue": 0.85},
}

# باید دقیقاً با services/gsheet_setup.py یکی باشه
BLOCK_SIZE = 2 + len(AVAILABLE_TIMES) + EXTRA_ROWS_PER_DAY + 1

_client = None
_spreadsheet = None


def _get_spreadsheet():
    global _client, _spreadsheet
    if _spreadsheet is None:
        creds = Credentials.from_service_account_file(
            Config.GOOGLE_CREDENTIALS_PATH, scopes=SCOPES
        )
        _client = gspread.authorize(creds)
        _spreadsheet = _client.open_by_key(Config.GOOGLE_SHEET_ID)
    return _spreadsheet


def _log_error(message):
    try:
        with open(os.path.join(BASE_DIR, "gsheet_error.log"), "a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()} — {message}\n")
    except Exception:
        pass


def _month_name_for(date_str):
    g_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    j_date = jdatetime.date.fromgregorian(date=g_date)
    return JALALI_MONTHS[j_date.month - 1], j_date


def _block_start_row(j_date):
    return 3 + (j_date.day - 1) * BLOCK_SIZE


def _row_for(date_str, time_str):
    g_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    j_date = jdatetime.date.fromgregorian(date=g_date)
    month_name = JALALI_MONTHS[j_date.month - 1]

    if time_str not in AVAILABLE_TIMES:
        raise ValueError(f"ساعت ناشناخته: {time_str}")

    time_offset = AVAILABLE_TIMES.index(time_str)
    row_num = _block_start_row(j_date) + 2 + time_offset

    return month_name, row_num


def _write_standard(appointment, month_name, row_num):
    worksheet = _get_spreadsheet().worksheet(month_name)

    time_offset = AVAILABLE_TIMES.index(appointment.time)
    session_label = "آنلاین" if appointment.session_type == "online" else "حضوری"

    values = [
        str(time_offset + 1),
        appointment.name,
        appointment.time,
        session_label,
        appointment.payment_status,
        appointment.phone,
        appointment.notes or "",
    ]

    cell_range = f"A{row_num}:G{row_num}"
    worksheet.update(cell_range, [values], value_input_option="RAW")

    color = STATUS_COLORS.get(appointment.payment_status, {"red": 1, "green": 1, "blue": 1})
    worksheet.format(cell_range, {"backgroundColor": color})


def _find_free_buffer_row(worksheet, j_date):
    extra_start = _block_start_row(j_date) + 2 + len(AVAILABLE_TIMES)
    extra_end = extra_start + EXTRA_ROWS_PER_DAY - 1

    values = worksheet.get(f"A{extra_start}:A{extra_end}")
    for i in range(EXTRA_ROWS_PER_DAY):
        cell_value = values[i][0] if i < len(values) and values[i] else ""
        if not cell_value.strip():
            return extra_start + i
    return None


def _write_extra(appointment, month_name, j_date):
    worksheet = _get_spreadsheet().worksheet(month_name)

    session_label = "آنلاین" if appointment.session_type == "online" else (
        "حضوری" if appointment.session_type == "inperson" else "—"
    )

    row_num = _find_free_buffer_row(worksheet, j_date)

    if row_num is not None:
        values = ["✚", appointment.name, appointment.time, session_label,
                   appointment.payment_status, appointment.phone, appointment.notes or ""]
        cell_range = f"A{row_num}:G{row_num}"
        worksheet.update(cell_range, [values], value_input_option="RAW")
        color = STATUS_COLORS.get(appointment.payment_status, {"red": 1, "green": 1, "blue": 1})
        worksheet.format(cell_range, {"backgroundColor": color})
        return

    weekday_fa = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"][j_date.weekday()]
    values = [
        f"⚠️ اضافه (بافر پر بود) — {weekday_fa} {j_date.day} {month_name}",
        appointment.name,
        appointment.time,
        session_label,
        appointment.payment_status,
        appointment.phone,
        appointment.notes or "",
    ]
    worksheet.append_row(values, value_input_option="RAW")
    all_values = worksheet.get_all_values()
    last_row = len(all_values)
    color = STATUS_COLORS.get(appointment.payment_status, {"red": 1, "green": 1, "blue": 1})
    worksheet.format(f"A{last_row}:G{last_row}", {"backgroundColor": color})


def write_appointment(appointment):
    try:
        month_name, j_date = _month_name_for(appointment.date)

        if appointment.time in AVAILABLE_TIMES:
            _, row_num = _row_for(appointment.date, appointment.time)
            _write_standard(appointment, month_name, row_num)
        else:
            _write_extra(appointment, month_name, j_date)

        return True
    except Exception as e:
        _log_error(f"خطا در نوشتن روی گوگل شیت: {e}")
        return False


log_appointment = write_appointment


def update_status(date_str, time_str, new_status):
    if time_str not in AVAILABLE_TIMES:
        _log_error(
            f"آپدیت وضعیت رد شد — ساعت غیراستاندارد ({time_str} در {date_str}) "
            f"باید دستی توی شیت اصلاح بشه"
        )
        return False

    try:
        month_name, row_num = _row_for(date_str, time_str)
        worksheet = _get_spreadsheet().worksheet(month_name)

        worksheet.update(f"E{row_num}", [[new_status]], value_input_option="USER_ENTERED")

        color = STATUS_COLORS.get(new_status, {"red": 1, "green": 1, "blue": 1})
        worksheet.format(f"A{row_num}:G{row_num}", {"backgroundColor": color})

        return True
    except Exception as e:
        _log_error(f"خطا در آپدیت وضعیت گوگل شیت: {e}")
        return False


def clear_appointment_row(appointment):
    """
    یه نوبت رو طوری از گوگل‌شیت پاک می‌کنه که انگار اصلاً وجود نداشته.
    """
    try:
        month_name, j_date = _month_name_for(appointment.date)
        worksheet = _get_spreadsheet().worksheet(month_name)

        if appointment.time in AVAILABLE_TIMES:
            _, row_num = _row_for(appointment.date, appointment.time)
            time_offset = AVAILABLE_TIMES.index(appointment.time)
            blank_row = [str(time_offset + 1), "", "", "", "", "", ""]
            cell_range = f"A{row_num}:G{row_num}"
            worksheet.update(cell_range, [blank_row], value_input_option="RAW")
            worksheet.format(cell_range, {"backgroundColor": {"red": 1, "green": 1, "blue": 1}})
        else:
            extra_start = _block_start_row(j_date) + 2 + len(AVAILABLE_TIMES)
            extra_end = extra_start + EXTRA_ROWS_PER_DAY - 1
            found = False

            for row_num in range(extra_start, extra_end + 1):
                row_values = worksheet.row_values(row_num)
                if len(row_values) >= 6 and row_values[5] == appointment.phone and row_values[2] == appointment.time:
                    cell_range = f"A{row_num}:G{row_num}"
                    worksheet.update(cell_range, [["", "", "", "", "", "", ""]], value_input_option="RAW")
                    worksheet.format(cell_range, {"backgroundColor": {"red": 1, "green": 1, "blue": 1}})
                    found = True
                    break

            if not found:
                all_values = worksheet.get_all_values()
                for idx, row in enumerate(all_values, start=1):
                    if len(row) >= 6 and row[5] == appointment.phone and row[2] == appointment.time:
                        worksheet.delete_rows(idx)
                        break

        return True
    except Exception as e:
        _log_error(f"خطا در حذف کامل نوبت از گوگل‌شیت: {e}")
        return False