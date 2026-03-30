# Quick Start Setup (5 Minutes)

Follow these steps to get MediChain running locally in 5 minutes.

---

## ✅ Prerequisites Checklist

- [ ] Python 3.9+ installed → `python --version`
- [ ] MySQL 8.0+ installed & running
- [ ] Git installed
- [ ] Code editor (VS Code recommended)

If any missing, install from:
- Python: https://www.python.org/downloads/
- MySQL: https://www.mysql.com/downloads/
- Git: https://git-scm.com/

---

## 🚀 5-Minute Setup

### Step 1: Clone Repository (1 min)

```powershell
# Open PowerShell or Command Prompt
git clone https://github.com/your-username/medichain.git
cd medichain
```

### Step 2: Create Virtual Environment (1 min)

```powershell
# Create venv
python -m venv venv

# Activate it
.\venv\Scripts\Activate.ps1

# You should see (venv) in terminal prompt
```

### Step 3: Install Dependencies (1 min)

```powershell
pip install -r requirements.txt
```

### Step 4: Configure Environment (1 min)

```powershell
# Copy example file
Copy-Item .env.example .env

# Edit .env (open in VS Code)
code .env
```

**Minimum required in .env:**
```env
SECRET_KEY=your-secret-key
DEBUG=True
DB_NAME=medichain
DB_USER=root
DB_PASSWORD=<your_mysql_password>
DB_HOST=localhost
DB_PORT=3306
```

**Generate SECRET_KEY (PowerShell):**
```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy output and paste in `.env`

### Step 5: Setup Database (1 min)

**Open MySQL:**
```powershell
mysql -u root -p
```

**Create database:**
```sql
CREATE DATABASE medichain;
GRANT ALL PRIVILEGES ON medichain.* TO 'root'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

**Run migrations:**
```powershell
python manage.py migrate
```

---

## ▶️ Start Server

```powershell
python manage.py runserver
```

✅ **Server running at**: http://localhost:8000/

---

## 🧪 Test It Works

### Option 1: Browser

1. Open http://localhost:8000/
2. Should see MediChain homepage

### Option 2: API Test

```powershell
# Open new PowerShell window (keep server running)

# Register hospital
curl -X POST http://localhost:8000/api/v1/register/ `
  -H "Content-Type: application/json" `
  -d '{
    "hospital_name": "Test Hospital",
    "email": "admin@test.com",
    "password": "TestPass123",
    "contact_number": "9999999999"
  }'

# Copy request_id from response
```

---

## 📝 What to Do Next

### 1. Read Documentation
- [ ] Read `README.md` - Full documentation
- [ ] Read `API_REFERENCE.md` - All API endpoints
- [ ] Read `CONTRIBUTING.md` - How to code & contribute

### 2. Explore Code
- [ ] Open `hospitals/models.py` - Database schema
- [ ] Open `hospitals/api_views.py` - API logic
- [ ] Open `hospitals/api_urls.py` - URL routes

### 3. Test Complete Workflow
- [ ] Register a hospital
- [ ] Create admin account
- [ ] Add a doctor
- [ ] Create a patient
- [ ] Send to lab test
- [ ] Create medical record

---

## 🔧 Troubleshooting

### Can't Connect to MySQL
```powershell
# Check MySQL is running
mysql -u root -p

# If fails, start MySQL service
# Windows: Services app → Search "MySQL" → Start
```

### Package Install Failed
```powershell
# Upgrade pip
python -m pip install --upgrade pip

# Try again
pip install -r requirements.txt
```

### Port 8000 Already in Use
```powershell
# Need to use different port
python manage.py runserver 8001

# Or kill process on 8000
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### JWT Token Issues
```env
# Make sure SECRET_KEY in .env is long and random
# Then restart server: Ctrl+C and python manage.py runserver
```

---

## 📚 Next Steps

1. **Understand Architecture** → Read README.md
2. **Test All Endpoints** → Use API_REFERENCE.md with Postman
3. **Understand Code** → Start with models.py, then api_views.py
4. **Implement Features** → Follow CONTRIBUTING.md
5. **Prepare for Deployment** → Read DEPLOYMENT.md

---

## 📞 Need Help?

**Check in order:**
1. This quick start guide
2. README.md (full documentation)
3. CONTRIBUTING.md (coding questions)
4. Code comments
5. Django/DRF documentation

---

## ✨ You're Ready!

Server is running. Database is set up. APIs are ready to test.

**Next: Read README.md for detailed documentation.**

Happy coding! 🚀
