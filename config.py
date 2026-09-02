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
    SMS_API_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIyIiwianRpIjoiMTMyMGJiODA2ZDNlOGEzZDg2NGFmNzk0OTY0YTgzODJhMDVmMTdlZGMyZTI4NTA2NWZmMWJhMTdlOWJkNWVhZGUyMjE2MmQ2YWZhZTAyODgiLCJpYXQiOjE3ODU5NTcxMTkuNzE4MDQ2LCJuYmYiOjE3ODU5NTcxMTkuNzE4MDQ2LCJleHAiOjE4MTc0OTMxMTkuNzE4MDQ2LCJzdWIiOiIxNzU2NCIsInNjb3BlcyI6IltdIn0.zQvtNDqNa6Q93oaE5ZcKiyobuLzMKyIp37S6kKAzQbEduE6ypVFZwz2KsaB3rZmMOdeO9vIRcFeb91j51pCkXElABXU57ThRdQLjJ_rGPKgqtbZbkW5o-1qsqOh14-0RMuFsY_YDhi3B6Ox1RINnRGfsac2VYI5wWA08z0nYzhRmpuwp3-Em43I4QmA6A7jtS58A0HUDyLVWHDtSSkcvkRGvQk_qkb8uhnwTJ4pI25Hz1O9ZIixGHkVguKrJwgLav8ltiSo56W4zOQgYbV8FTFLmwqopMGSsAvucgXE3ibTi5Hm0hYVJdW7MPZfyNYw5f4lwy3Fu2tbRlcnY1wwBuLM-XM2YTRDC8xYXyfV6KjawCYkKNTNHi0NHzgCIVKtvv4XWkMYdjnXp67sd8AZMZr87z6NTyPUDa3wm1JUcvo_-pNcHd3hu7YOycpju3vhy94cK7B9ydvQWr8nqQxrnbNCHJ-a_xCSeIhmdXJSgnZIEO4K3GwKPHPCudLcCQLSH7edtxYBC_PHunuXVgN7NcVZh93wF19vrTKPPDePQnSc5z2vUiy7XYFZBBv8TwgWN9wgH1hUL3jCq6h5wK4ug_2gCNXU-dLwkWjIHQXLgZeWUCZ7VrPep9BoqzmLwCrAYkIi5brlTdqeyjkXg0Pkimbfcpj1ZvviFyBeKKlKglv8"   # ← پر کن
    SMS_FROM = "989998623317"         # ← پر کن
    DOCTOR_PHONE = "9363643522"     # ← پر کن

    # سوییچ پسوند «لغو 11» — با تست واقعی (2026-08-06) قطعی شد: اجباریه.
    # API با نبودش خطای 400 می‌ده، حتی برای خط خدماتی.
    SMS_APPEND_UNSUBSCRIBE = True

    # ─── باشگاه مشتریان ───────────────────────────────────
    # شیت جداگانه (فایل مجزا از شیت رزرو) — از قبل ساخته شده و
    # باید با همون client_email سرویس‌اکانت Editor شیر شده باشه.
    CUSTOMERS_SHEET_ID = "13YJEDgAmBPKWdCagQv16_7oDH9R0s8lx-tuUTaZVH0Y"
