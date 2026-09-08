# Service Desk Hub — Backend (Python / FastAPI)

بک‌اند واقعی (Python + FastAPI + PostgreSQL) برای داشبورد سرویس دسک، شروع‌شده از راستر شیفت.
همون قابلیت‌های نسخه‌ی Node.js، این‌بار با پایتون — چون دارین پایتون یاد می‌گیرین.

## ترتیب راه‌اندازی (روی VM اوبونتوی خودتون)

📘 **راه سریع:** فایل **`docs/00_Complete_Setup_Guide.md`** یه راهنمای کامل و یک‌جاست — از نصب پیش‌نیازها تا دیدن داشبورد تو مرورگر، همه تو یه فایل. این تست شده (رو یه محیط کاملاً تازه، دقیقاً قدم‌به‌قدم اجرا شد) و ساده‌ترین مسیره.

اگه ترجیح می‌دین مرحله‌به‌مرحله و با جزئیات بیشتر پیش برین، همون مسیر با فایل‌های جدا:

1. **`docs/01_Ubuntu_VM_Setup.md`** — نصب Python و PostgreSQL
2. **`docs/02_Database_Setup.md`** — بارگذاری اسکیمای دیتابیس
3. **`docs/03_Backend_Setup.md`** — بالا آوردن سرور روی `localhost:4000` با `uvicorn` + تست زنده + مستندات خودکار API
4. **`docs/04_Next_Steps.md`** — نقشه‌ی راه برای وصل کردن داشبورد اصلی
5. **`docs/05_Unification_Roadmap.md`** — نقشه‌ی راه یکپارچه‌سازی کامل همه‌ی داشبوردها (۴ فاز)

## ساختار پوشه‌ها

```
backend_py/
├── sql/schema.sql              ← ساختار کامل دیتابیس (بدون تغییر نسبت به نسخه‌ی Node)
├── main.py                     ← نقطه‌ی ورود اصلی FastAPI
├── app/
│   ├── auth.py                 ← هش رمز عبور، ساخت/بررسی JWT، وابستگی‌های نقش کاربر
│   ├── db/
│   │   ├── session.py          ← اتصال SQLAlchemy به PostgreSQL
│   │   └── models.py           ← مدل‌های ORM (کلاس پایتونی معادل هر جدول)
│   └── routers/
│       ├── auth_router.py      ← لاگین
│       └── roster_router.py    ← ستون‌ها، اعضای تیم، شیفت‌ها، تعطیلات
├── scripts/create_admin.py     ← ساخت اولین کاربر ادمین
├── public/
│   ├── admin/index.html        ← صفحه‌ی تست ساده (http://localhost:4000/admin)
│   └── dashboard/               ← کل داشبورد (http://localhost:4000/dashboard/)
│       ├── index.html           ← شل اصلی (نمای کلی + منو)
│       ├── SDCM_Registration_Report.html
│       ├── Service_Desk_AICC_Agent_Performance_Dashboard.html
│       ├── Incident_SLA_Distribution_Dashboard.html
│       └── Shift_Roster.html
├── requirements.txt             ← پکیج‌های پایتونی لازم
├── .env.example                 ← الگوی تنظیمات (کپی کنین به .env)
└── docs/                        ← همین آموزش‌ها
```

## دستورات پرکاربرد

```bash
python3 -m venv venv && source venv/bin/activate   # ساخت و فعال‌سازی محیط مجازی
pip install -r requirements.txt                     # نصب پکیج‌ها
uvicorn main:app --reload --port 4000                # اجرای زنده با ری‌استارت خودکار
python scripts/create_admin.py <username> "<نام نمایشی>" <رمز>
```

## چیزی که مخصوص FastAPI رایگان بهتون می‌رسه
بعد از بالا آوردن سرور، آدرس `http://localhost:4000/docs` رو باز کنین — یه صفحه‌ی تعاملی (Swagger UI) که همه‌ی endpoint ها رو نشون می‌ده و می‌تونین مستقیم توش تست کنین. برای یادگیری هم‌زمان با ساخت این پروژه خیلی مفیده.
