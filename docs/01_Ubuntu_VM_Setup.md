# قدم ۱ — آماده‌سازی VM اوبونتو (Python + PostgreSQL)

این فایل رو دقیقاً روی VM اوبونتوی خودتون (نه روی سیستم من) اجرا کنین. فرض بر اینه Ubuntu 22.04 یا 24.04 دارین.

## ۱.۱ آپدیت سیستم
```bash
sudo apt update && sudo apt upgrade -y
```

## ۱.۲ نصب Python (اوبونتو ۲۲/۲۴ از قبل Python 3.10+ داره، فقط ابزارهای جانبی رو نصب می‌کنیم)
```bash
python3 --version    # باید 3.10 یا بالاتر باشه
sudo apt install -y python3-pip python3-venv
```

## ۱.۳ نصب PostgreSQL
```bash
sudo apt install -y postgresql postgresql-contrib libpq-dev
sudo systemctl enable postgresql
sudo systemctl start postgresql
sudo systemctl status postgresql   # باید active (running) باشه
```
> `libpq-dev` لازمه چون پکیج پایتونی `psycopg2` موقع نصب باهاش کامپایل می‌شه.

## ۱.۴ ساخت دیتابیس و یوزر اختصاصی
```bash
sudo -u postgres psql
```
داخل پرامپت `postgres=#` این دستورات رو بزنین (رمز دلخواه خودتون رو جای `CHANGE_ME` بذارین):
```sql
CREATE USER sdhub_user WITH PASSWORD 'CHANGE_ME';
CREATE DATABASE sdhub OWNER sdhub_user;
\q
```

## ۱.۵ تست اتصال
```bash
psql -U sdhub_user -d sdhub -h localhost -W
```
رمز رو وارد کنین؛ اگه پرامپت `sdhub=>` اومد یعنی دیتابیس آماده‌ست. با `\q` خارج شین.

## ۱.۶ نصب Git (اگه از قبل نیست)
```bash
sudo apt install -y git
```

---
✅ **در این مرحله چی آماده شد:** Python، PostgreSQL، و یه دیتابیس خالی به اسم `sdhub`.
➡️ **قدم بعدی:** فایل `docs/02_Database_Setup.md`
