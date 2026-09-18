import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = "8282cd334158521e3de2216b855577207e84e9e16b0206700dff4c909c4d2f9f"

    SQLALCHEMY_DATABASE_URI = (
        "sqlite:///" + os.path.join(BASE_DIR, "database.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # قبلاً ۳۶۰۰ ثانیه (۱ ساعت) بود — یعنی منشی هر ساعت مجبور می‌شد دوباره
    # رمز بزنه. الان ۳۰ روز — چون این لاگین پشت رمز عبوره و آدرسش عمومی
    # تبلیغ نمی‌شه، ریسک نگه‌داشتن نشست طولانی‌تر قابل‌قبوله.
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 30
    SESSION_COOKIE_PATH = "/"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = True  # فقط از طریق HTTPS ارسال بشه — سایت روی https هست

    # ─── حالت تست زرین‌پال ──────────────────────────────
    # True  = sandbox (بدون کسر پول واقعی)
    # False = درگاه واقعی
    ZARINPAL_SANDBOX = False

    SETUP_SECRET_KEY = "8282cd334158521e3de2216b855577207e84e9e16b0206700dff4c909c4d2f9f"

    # ─── گوگل شیت ────────────────────────────────────────
    GOOGLE_CREDENTIALS_PATH = os.path.join(BASE_DIR, "google_credentials.json")
    GOOGLE_SHEET_ID = "19Mx0f1lpqBImsayleDKb7x5iAO9_m4v--aOrO2xbMo0"   # ← آیدی شیتت رو اینجا بذار
    GOOGLE_SHEET_NAME = "Sheet1"


    # ─── پنل مدیریت ──────────────────────────────────────
    ADMIN_USERNAME = "amirreza272"
    ADMIN_PASSWORD_HASH = "scrypt:32768:8:1$VSyvdED4aXOkBwiG$933395416c783c86aabb75fc96f19ec3ef14d131d45a93d30c90d0e944d6f1a2dbec5566809dbc9573deab60288b0c4d757c5e2b2e299e23c6314555ea90d91a"

    # ─── پیامک — SignalAds (Transmitor) ──────────────────
    # SMS_API_TOKEN: از پنل SignalAds بگیر (Bearer token)
    # SMS_FROM: شماره‌ی خط اختصاصی که ازشون گرفتی
    # DOCTOR_PHONE: موبایل خانم دکتر — برای گزارش روزانه
    # ─── پیامک — SignalAds (Transmitor) ──────────────────
    SMS_API_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIyIiwianRpIjoiMmZiYThjNTViNjExNjkyZDcwOWI3NjM0MTM0ZDhjNWVkMTJkNWJmM2IyNjJmZjhmMDdjMmViY2EzNzBiMDg5MWJmY2YyOTEyMzY5YWM0ZTciLCJpYXQiOjE3ODkyMDg2NjUuNzQyMTI0LCJuYmYiOjE3ODkyMDg2NjUuNzQyMTI0LCJleHAiOjE4MjA3NDQ2NjUuNzQyMTI0LCJzdWIiOiIxNzU2NCIsInNjb3BlcyI6IltdIn0.1NZKc1yCx4MdeZgIdMA_LS9CTKRcUPBEEFKEMfACbZxgAx1b7O1QlFXAELtZtXgMW-a7lf8F-fi2XkAAZtJyzubIcqqAwYR0LgHCRiLYTdsKQiR8FfYR-ByKgLX8JPn31wCQp-xM0vpuE5JgKbVY1vpDbNNlZg3xqRVMXhfJ4M-_CUKx5jfLx_Z-yzI5dtwHpXghJrRmsHeAGEgwMXEVZ1Y44nRjTM2Su61CO_kX4VIk8cPVACErYfJbpbnGYBa7hNTYvFaWOuGolRGWDbQFYp1ljNSWNTNGqbr9bsAvGKdq60DX5o0NGGhepHbmwv3kCOHw2otcwexA3RNr5elF-mB9U2mJ_S2nPjuNgNprOjq668Jk-46uU-FgiKOun5iJnIo2hg4-lfv_i2Cxi2F2yCcQ5fISO0fFErgSIrSFO2CxHUyiybVu77L24t2jnZSzxUvbK3GSd1tXgMGTC7Vo1wNjwluXeMu6rItqVRNciSJ9yZC9infAyZirzJOlpDixMQcrEW6UtLJH91y4ZPft4p-asC3H_0rFz5hVyqkonbhs8at69Dt9qXi61GJaGRgw5rixP522ld8N_Y8OXIcu7UvIaTIZbiU4qPZhkB1ci5G_4VYqPNhJ4R1jGzbo9BDnTdgenkJ2D836Zkqe03joUbm9nFvHwbcrC-69MIBojQ8"
    SMS_FROM = "989998623317"
    DOCTOR_PHONE = "09363643522"

    # ─── آدرس پایه‌ی سایت — برای ساخت لینک‌های پیامکی ────
    SITE_BASE_URL = "https://masircenter.com/booking"

    # ─── کلید محافظت روت‌های Cron (همون کلید setup رو بازاستفاده می‌کنیم) ───
    CRON_SECRET_KEY = "8282cd334158521e3de2216b855577207e84e9e16b0206700dff4c909c4d2f9f"

    # اطلاعات مطب/جلسه‌ی آنلاین — برای صفحه‌ی پرداخت (pay.html)
    CLINIC_ADDRESS = "ارومیه، عمار، روبه‌روی خیابان شفا، ساختمان مرتاض، طبقه ۶، واحد C"
    SESSION_LINK = "https://event.alocom.co/class/solmadan/e8b49b83"

    # سوییچ پسوند «لغو 11» — با تست واقعی (2026-08-06) قطعی شد: اجباریه.
    # API با نبودش خطای 400 می‌ده، حتی برای خط خدماتی.
    SMS_APPEND_UNSUBSCRIBE = True

    # ─── باشگاه مشتریان ───────────────────────────────────
    # شیت جداگانه (فایل مجزا از شیت رزرو) — از قبل ساخته شده و
    # باید با همون client_email سرویس‌اکانت Editor شیر شده باشه.
    CUSTOMERS_SHEET_ID = "13YJEDgAmBPKWdCagQv16_7oDH9R0s8lx-tuUTaZVH0Y"
