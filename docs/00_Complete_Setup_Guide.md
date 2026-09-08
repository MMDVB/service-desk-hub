# راهنمای کامل — راه‌اندازی Service Desk Hub روی اوبونتو

این یه راهنمای کامل و یک‌جاست — از صفر تا سیستم کاملاً بالا و قابل‌استفاده. نیازی نیست بین فایل‌های دیگه‌ی `docs/` بگردین؛ همه‌چیز این‌جاست، به ترتیب.

**چیزی که در آخر خواهید داشت:**
یه سرور روی `localhost:4000` که هم API واقعی (با دیتابیس PostgreSQL) میده، هم کل داشبورد (نمای کلی + گزارش SDCM + گزارش AICC + گزارش SLA + راستر شیفت) رو سرو می‌کنه.

**زمان تقریبی:** ۳۰ تا ۴۵ دقیقه (بار اول).

---

## پیش‌نیاز: چی باید از قبل داشته باشین

- یه ماشین/VM با **Ubuntu 22.04 یا 24.04**
- دسترسی `sudo` روی اون ماشین
- فایل `service-desk-hub-backend-python.zip` که از چت دانلود کردین

---

## قدم ۱ — آپدیت سیستم و نصب پیش‌نیازها

```bash
sudo apt update && sudo apt upgrade -y
```

### نصب Python
اوبونتوی ۲۲/۲۴ از قبل Python 3.10+ داره؛ فقط ابزارهای جانبی لازمه:
```bash
python3 --version    # باید 3.10 یا بالاتر باشه
sudo apt install -y python3-pip python3-venv
```

### نصب PostgreSQL
```bash
sudo apt install -y postgresql postgresql-contrib libpq-dev
sudo systemctl enable postgresql
sudo systemctl start postgresql
sudo systemctl status postgresql   # باید active (running) باشه — با q خارج شین
```
> `libpq-dev` لازمه چون پکیج پایتونی `psycopg2` موقع نصب باهاش کامپایل می‌شه.

### نصب ابزارهای جانبی
```bash
sudo apt install -y git unzip
```

---

## قدم ۲ — ساخت دیتابیس

```bash
sudo -u postgres psql
```
داخل پرامپت `postgres=#` (رمز دلخواه خودتون رو جای `CHANGE_ME` بذارین — همین رمز رو یادداشت کنین، تو قدم ۴ لازمش دارین):
```sql
CREATE USER sdhub_user WITH PASSWORD 'CHANGE_ME';
CREATE DATABASE sdhub OWNER sdhub_user;
\q
```

تست اتصال:
```bash
psql -U sdhub_user -d sdhub -h localhost -W
```
رمز رو وارد کنین؛ اگه پرامپت `sdhub=>` اومد یعنی درسته. با `\q` خارج شین.

---

## قدم ۳ — آپلود و باز کردن پروژه

فایل zip رو رو سرور ببرین (با `scp`، فلش، یا هر روشی که VM‌تون بهش دسترسی داره)، مثلاً تو مسیر خانه:
```bash
mkdir -p ~/service-desk-hub
cd ~/service-desk-hub
unzip service-desk-hub-backend-python.zip -d .
```

ساختار نهایی باید این‌جوری باشه:
```
~/service-desk-hub/
├── sql/schema.sql
├── main.py
├── app/...
├── scripts/create_admin.py
├── public/
│   ├── admin/index.html
│   └── dashboard/           ← کل داشبورد این‌جاست
├── requirements.txt
├── .env.example
└── docs/
```

### بارگذاری ساختار دیتابیس
```bash
cd ~/service-desk-hub
psql -U sdhub_user -d sdhub -h localhost -f sql/schema.sql
```
اگه بدون خطا تموم شد، جدول‌ها ساخته شدن. تأیید کنین:
```bash
psql -U sdhub_user -d sdhub -h localhost -c "\dt"
```
باید یه لیست شامل `users, team_members, roster_columns, roster_entries, roster_entry_members, holidays, audit_log, sdcm_reports, aicc_reports, sla_reports` ببینین.

---

## قدم ۴ — نصب و پیکربندی بک‌اند

### محیط مجازی پایتون
```bash
cd ~/service-desk-hub
python3 -m venv venv
source venv/bin/activate
```
باید `(venv)` رو اول خط ترمینال ببینین. حالا پکیج‌ها رو نصب کنین:
```bash
pip install -r requirements.txt
```
> ⚠️ هر بار ترمینال جدید باز کردین، اول باید دوباره `source venv/bin/activate` بزنین.

### فایل تنظیمات (.env)
```bash
cp .env.example .env
nano .env
```
این خط‌ها رو با مقادیر واقعی خودتون پر کنین:
```
DATABASE_URL=postgresql://sdhub_user:همون‌رمز‌قدم۲@localhost:5432/sdhub
JWT_SECRET=<یه رشته‌ی رندوم طولانی>
```
برای ساختن `JWT_SECRET` امن:
```bash
openssl rand -base64 48
```
خروجی رو کپی کنین و جای `JWT_SECRET` تو `.env` بذارین. ذخیره کنین (Ctrl+O، Enter، Ctrl+X).

### ساخت اولین کاربر ادمین
```bash
python scripts/create_admin.py admin "مدیر سیستم" "یک-رمز-قوی-اینجا"
```
باید ببینین: `Admin user "admin" is ready.`

---

## قدم ۵ — بالا آوردن سرور

```bash
uvicorn main:app --reload --port 4000
```
باید این‌جوری چیزی ببینین:
```
Uvicorn running on http://127.0.0.1:4000
Application startup complete.
```
با `--reload`، هر بار کدی رو عوض کنین سرور خودش ری‌استارت می‌شه.

### تست سریع
تو یه ترمینال دیگه:
```bash
curl http://localhost:4000/api/health
```
باید ببینین: `{"ok":true}`

---

## قدم ۶ — دیدن سیستم تو مرورگر

این آدرس‌ها رو باز کنین:

| آدرس | چی نشون می‌ده |
|---|---|
| `http://localhost:4000/` | خودکار به داشبورد ریدایرکت می‌شه |
| `http://localhost:4000/dashboard/` | **کل داشبورد** — نمای کلی، SDCM، AICC، SLA، راستر شیفت |
| `http://localhost:4000/dashboard/Shift_Roster.html` | مستقیم راستر شیفت |
| `http://localhost:4000/docs` | مستندات تعاملی API (Swagger UI) — می‌تونین هر endpoint رو مستقیم تست کنین |
| `http://localhost:4000/admin` | صفحه‌ی تست ساده‌ی API (لاگین + ستون‌ها + افزودن عضو) |

### اگه از سیستم خودتون (نه از داخل VM) وصل می‌شین
اگه VM با VirtualBox/VMware/Hyper-V بالا اومده، پورت ۴۰۰۰ رو forward کنین:
- **VirtualBox:** Settings → Network → Advanced → Port Forwarding → قانون جدید: Host Port `4000` → Guest Port `4000`
- بعدش همون آدرس‌های بالا رو تو مرورگر خودتون باز کنین.

---

## قدم ۷ — ورود به پنل لیدرشیپ (برای ویرایش راستر)

1. `http://localhost:4000/dashboard/Shift_Roster.html` رو باز کنین
2. دکمه‌ی **👑 Leadership** رو بزنین
3. رمز پیش‌فرض: `leadership2026`

> ⚠️ **حتماً این رمز رو عوض کنین** — تو فایل `public/dashboard/Shift_Roster.html` دنبال `LEAD_PASSCODE` بگردین (`Ctrl+F` تو یه ادیتور متنی) و مقدارش رو عوض کنین. این یه گیت ساده‌ی سمت کاربره، نه یه لایه‌ی امنیتی واقعی — برای همین باید طبق نیازتون سخت‌گیرانه‌ترش کنین (مثلاً بعداً وصلش کنیم به همون سیستم لاگین واقعی JWT که برای API ساختیم).

بعد از ورود می‌تونین:
- 👥 اعضای تیم اضافه/حذف کنین
- 📅 تعطیلات رسمی ثبت کنین
- 🎨 ستون‌های شیفت رو مدیریت کنین
- 📥 از اکسل درون‌ریزی کنین
- روی هر خونه کلیک یا درگ‌اند‌دراپ کنین تا شیفت تخصیص بدین

---

## عیب‌یابی سریع

| مشکل | راه‌حل |
|---|---|
| `psql: connection refused` | `sudo systemctl status postgresql` رو چک کنین؛ اگه خاموشه: `sudo systemctl start postgresql` |
| `ModuleNotFoundError` وقتی `uvicorn` رو اجرا می‌کنین | یادتون رفته `source venv/bin/activate` بزنین |
| `KeyError: 'DATABASE_URL'` | فایل `.env` رو نساختین یا اسمش اشتباهه (باید دقیقاً `.env` باشه، نه `.env.example`) |
| صفحه‌ی `/dashboard/` باز نمی‌شه (۴۰۴) | مطمئن شین پوشه‌ی `public/dashboard/` واقعاً از zip استخراج شده و کنار `main.py`ه |
| رمز لیدرشیپ کار نمی‌کنه | پیش‌فرض `leadership2026`ه؛ اگه عوضش کردین، همون مقدار جدید رو وارد کنین |

---

## بعدش چی؟

سیستم الان **زنده و قابل‌استفاده‌ست**، ولی راستر هنوز داده‌هاش رو تو `localStorage` مرورگر نگه می‌داره (نه دیتابیسی که همین الان راه انداختیم). وصل‌کردن این دو به هم، و ادامه‌ی نقشه‌ی یکپارچه‌سازی، تو فایل `docs/05_Unification_Roadmap.md` توضیح داده شده — هر وقت آماده بودین برگردین بگین «بریم فاز بعد».
