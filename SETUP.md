# راه‌اندازی و استقرار دایان

## آدرس‌ها
| سرویس | آدرس |
|--------|------|
| دانشجو | http://localhost:3000 |
| ادمین | http://localhost:3001 |
| دولوپر | http://localhost:4000 |
| API / Docs | http://127.0.0.1:8000 · http://127.0.0.1:8000/docs |
| Temporal UI | http://localhost:8080 |
| Health | http://127.0.0.1:8000/api/health |

---

## یک دستور — همه با Docker

```bash
copy .env.example .env
# JWT_SECRET را عوض کن
# MODEL_URL برای LM Studio روی ویندوز: http://host.docker.internal:1234

docker compose up -d --build
```

Temporal (ایندکس دانش) اختیاری است چون ایمیج‌ش سنگین است:

```bash
docker compose --profile temporal up -d
```

یا بدون پروفایل، Temporal CLI روی میزبان:

```powershell
tools\temporal-cli\temporal.exe server start-dev --ip 127.0.0.1 --port 7233 --ui-port 8080
```

صبر کن تا healthy شوند، بعد:

```bash
docker compose ps
curl http://127.0.0.1:8000/api/health
```

آدرس‌ها: دانشجو `:3000` · ادمین `:3001` · دولوپر `:4000` · API `:8000/docs`

توقف:

```bash
docker compose down
```

با حجم‌ها:

```bash
docker compose down -v
```

لاگ:

```bash
docker compose logs -f api
```

---

## اجرا بدون داکرایز اپ (فقط DB در Docker)

```bash
docker compose up -d postgres mongo redis qdrant

# Temporal محلی (اگر ایمیج Temporal کشیده نشد)
tools\temporal-cli\temporal.exe server start-dev --ip 127.0.0.1 --port 7233 --ui-port 8080

copy .env.example .env
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# ترمینال ۱ — API
$env:REDIS_URL="redis://127.0.0.1:6379/0"
$env:QDRANT_URL="http://127.0.0.1:6333"
$env:TEMPORAL_HOST="127.0.0.1:7233"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# ترمینال ۲ — Temporal worker
python -m temporal.worker

# ترمینال ۳–۵ — UI
cd frontend && npm install && npm run dev
cd admin && npm install && npm run dev
cd developer && npm install && npm run dev
```

---

## اولین ورود
- **ادمین** `:3001` — اگر ادمینی نیست، فرم ساخت ادمین اول؛ بعد رمز از تنظیمات
- **دولوپر** `:4000` — اکانت پیش‌ساخته ساخته می‌شود؛ بعد از ورود اول نام کاربری/رمز را عوض کن، بعد کاربر اضافه کن
- **دانشجو** `:3000/login` — ثبت‌نام یا seed: `student1` …

---

## چه چیزی آماده است
- چت با FAQ / مدل / RAG (امبد + چانک + Qdrant)
- Redis برای rate-limit
- Temporal برای ایندکس دانش (chunk → embed → upsert)
- عوض کردن رمز دانشجو و ادمین
- پنل دولوپر: لاگ، ری‌استارت، امکانات ادمین
- تور ورود اول دانشجو + چت با تاریخچه/تمام‌صفحه

---

## امنیت قبل از پروداکشن
- `APP_ENV=production` و `DEBUG=false`
- `JWT_SECRET` تصادفی بلند
- رمز Postgres عوض شود
- CORS فقط دامنه واقعی
- HTTPS پشت Nginx/Caddy
- بکاپ Postgres + volume `dayan_app_data`
