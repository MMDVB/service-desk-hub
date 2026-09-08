# قدم ۲ — بارگذاری اسکیمای دیتابیس

## ۲.۱ کپی کردن پروژه روی VM
اگه فایل‌های این پروژه (پوشه‌ی `backend/`) رو از طریق زیپ گرفتین، اونو روی VM آپلود کنین (با `scp`، یا یه فلش/فولدر مشترک اگه VM لوکاله)، مثلاً تو مسیر:
```bash
~/service-desk-hub/backend_py
```

## ۲.۲ اجرای schema.sql
```bash
cd ~/service-desk-hub/backend_py
psql -U sdhub_user -d sdhub -h localhost -f sql/schema.sql
```
رمزی که تو قدم قبل ساختین رو می‌خواد. اگه بدون خطا تموم شد، یعنی جدول‌ها ساخته شدن.

## ۲.۳ تأیید اینکه جدول‌ها ساخته شدن
```bash
psql -U sdhub_user -d sdhub -h localhost -c "\dt"
```
باید یه لیست شامل این جدول‌ها ببینین:
```
users, team_members, roster_columns, roster_entries,
roster_entry_members, holidays, audit_log
```

## ۲.۴ تأیید داده‌ی اولیه (۹ ستون پیش‌فرض راستر)
```bash
psql -U sdhub_user -d sdhub -h localhost -c "SELECT key, label_en FROM roster_columns ORDER BY sort_order;"
```
باید ۹ ردیف ببینین: day1, day2, hq, night1, night2, oncall, off, leaveRequest, cab.

---
✅ **در این مرحله چی آماده شد:** ساختار کامل دیتابیس + ستون‌های پیش‌فرض راستر.
➡️ **قدم بعدی:** فایل `docs/03_Backend_Setup.md`
