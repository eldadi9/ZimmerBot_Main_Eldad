# התקנת Redis ב-Windows

Redis לא זמין באופן native ב-Windows, אבל יש כמה דרכים להתקין אותו:

---

## שיטה 1: WSL (Windows Subsystem for Linux) - מומלץ ⭐

זו השיטה הכי פשוטה ויציבה.

### שלב 1: התקן WSL

1. פתח PowerShell **כ-Administrator** (לחץ ימין → "Run as administrator")
2. הרץ:
   ```powershell
   wsl --install
   ```
3. הפעל מחדש את המחשב

### שלב 2: התקן Redis ב-WSL

1. פתח את **Ubuntu** (יופיע בתפריט Start אחרי ההתקנה)
2. הרץ:
   ```bash
   sudo apt update
   sudo apt install redis-server -y
   ```

### שלב 3: הפעל Redis

```bash
redis-server
```

**או כשירות רקע:**
```bash
sudo service redis-server start
```

### שלב 4: בדוק שהכל עובד

פתח terminal חדש ב-WSL:
```bash
redis-cli ping
```

אמור להחזיר: `PONG`

---

## שיטה 2: Memurai (Redis-Compatible for Windows)

Memurai הוא Redis-compatible server שמיועד ל-Windows.

### שלב 1: הורד Memurai

1. לך ל: https://www.memurai.com/get-memurai
2. הורד את הגרסה החינמית (Community Edition)
3. התקן את הקובץ שהורדת

### שלב 2: הפעל Memurai

Memurai יתקין את עצמו כשירות Windows ויתחיל אוטומטית.

### שלב 3: בדוק שהכל עובד

פתח PowerShell:
```powershell
redis-cli ping
```

אמור להחזיר: `PONG`

**אם `redis-cli` לא נמצא:**
- Memurai כולל `redis-cli` בתיקיית ההתקנה (בדרך כלל: `C:\Program Files\Memurai\`)
- הוסף את התיקייה ל-PATH, או השתמש בנתיב המלא

---

## שיטה 3: Docker

אם יש לך Docker Desktop מותקן:

```powershell
docker run -d -p 6379:6379 --name redis redis:latest
```

זה ייצור container של Redis שרץ על פורט 6379.

---

## שיטה 4: Chocolatey (Package Manager)

אם יש לך Chocolatey מותקן:

```powershell
choco install redis-64 -y
```

---

## בדיקה שהכל עובד

לאחר ההתקנה, בדוק:

### 1. בדוק שהשרת רץ

**ב-WSL:**
```bash
redis-cli ping
```

**ב-Windows (אם יש redis-cli):**
```powershell
redis-cli ping
```

**תשובה צפויה:** `PONG`

### 2. בדוק שהשרת מאזין על הפורט הנכון

```powershell
netstat -an | findstr 6379
```

אמור להראות משהו כמו:
```
TCP    0.0.0.0:6379           0.0.0.0:0              LISTENING
```

### 3. בדוק מה-API

פתח את `http://127.0.0.1:8000/docs` ב-Swagger ונסה ליצור Hold.

אם Redis עובד, לא תראה את ההודעה:
```
"warning": "Redis unavailable - hold not protected"
```

---

## הגדרת Redis ב-`.env`

ודא שהקובץ `.env` מכיל:

```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
HOLD_DURATION_SECONDS=900
```

**אם Redis רץ ב-WSL:**
- `REDIS_HOST=localhost` (עובד גם מ-Windows)
- או `REDIS_HOST=127.0.0.1`

**אם Redis רץ ב-Docker:**
- `REDIS_HOST=localhost` (אם Docker Desktop רץ)
- או `REDIS_HOST=127.0.0.1`

---

## פתרון בעיות

### בעיה: "Error 10061 connecting to localhost:6379"

**פתרונות:**
1. ודא ש-Redis רץ:
   - **WSL:** `sudo service redis-server status`
   - **Memurai:** פתח Services (services.msc) ובדוק ש-Memurai רץ
   - **Docker:** `docker ps` (אמור להראות redis container)

2. בדוק שהפורט 6379 פתוח:
   ```powershell
   netstat -an | findstr 6379
   ```

3. נסה להתחבר ידנית:
   ```powershell
   redis-cli -h localhost -p 6379 ping
   ```

### בעיה: "redis-cli: command not found"

**פתרונות:**
1. **WSL:** ודא שהתקנת redis-server:
   ```bash
   sudo apt install redis-tools
   ```

2. **Windows:** הוסף את נתיב ההתקנה ל-PATH, או השתמש בנתיב המלא

### בעיה: Redis לא מתחיל

**WSL:**
```bash
sudo service redis-server start
sudo service redis-server status
```

**Memurai:**
- פתח Services (Win+R → `services.msc`)
- מצא "Memurai"
- לחץ ימין → Start

---

## המלצה

**לפיתוח מקומי:** השתמש ב-**WSL** (שיטה 1) - הכי פשוט ויציב.

**לפרודקשן:** השתמש ב-**Memurai** או **Redis ב-Linux server**.

---

## קישורים שימושיים

- **Redis Documentation:** https://redis.io/docs/
- **WSL Installation:** https://learn.microsoft.com/en-us/windows/wsl/install
- **Memurai:** https://www.memurai.com/
- **Docker Redis:** https://hub.docker.com/_/redis

---

## הערות חשובות

1. **Redis ב-WSL** עובד מצוין, אבל אם תסגור את ה-WSL terminal, Redis ייסגר. השתמש ב-`sudo service redis-server start` כדי שיתחיל אוטומטית.

2. **Memurai** רץ כשירות Windows, אז הוא יתחיל אוטומטית עם Windows.

3. **Hold ב-memory** (כש-Redis לא זמין) עובד, אבל לא persistent - אחרי הפעלה מחדש של השרת, ה-Holds יאבדו.

4. **לפרודקשן:** תמיד השתמש ב-Redis persistent (לא memory-only).

