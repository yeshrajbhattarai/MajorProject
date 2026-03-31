# Deployment Guide

This guide explains how to deploy MediChain to production.

---

## 🚀 Pre-Deployment Checklist

- [ ] All tests passing locally
- [ ] Environment variables configured
- [ ] Database backups created
- [ ] Static files collected
- [ ] SSL certificate obtained
- [ ] Domain configured
- [ ] Email service verified
- [ ] Code committed & pushed

---

## 🔒 Security Hardening

### 1. Update Settings for Production

```python
# In settings.py or .env

DEBUG = False
ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com']

# HTTPS only
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_SECURITY_POLICY = {...}

# Generate strong SECRET_KEY
SECRET_KEY = 'your-very-long-random-string-here'
```

### 2. Database Security

```sql
-- Create dedicated MySQL user (not root)
CREATE USER 'medichain_user'@'localhost' IDENTIFIED BY 'strong_password';
GRANT ALL PRIVILEGES ON medichain.* TO 'medichain_user'@'localhost';
FLUSH PRIVILEGES;

-- In .env
DB_USER=medichain_user
DB_PASSWORD=strong_password
```

### 3. Restrict File Uploads

```python
# Only allow specific file types
ALLOWED_UPLOAD_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png']
MAX_UPLOAD_SIZE = 5242880  # 5MB

# Store outside web root
MEDIA_ROOT = '/var/medichain/media/'
```

---

## 📦 Deployment Options

### Option 1: AWS (Recommended for Production)

**Services**:
- EC2 (Django application)
- RDS (MySQL database)
- S3 (Media & static files)
- CloudFront (CDN)
- Route53 (DNS)

**Setup Steps**:

```bash
# 1. Launch EC2 instance (Ubuntu 22.04)
# 2. Connect via SSH
ssh -i key.pem ubuntu@your-instance-ip

# 3. Install dependencies
sudo apt update && sudo apt upgrade
sudo apt install python3-pip python3-venv mysql-client nginx

# 4. Clone repository
git clone https://github.com/your-repo/medichain.git
cd medichain

# 5. Setup virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn whitenoise

# 6. Configure .env with AWS RDS credentials
nano .env

# 7. Run migrations
python manage.py migrate

# 8. Collect static files
python manage.py collectstatic --noinput

# 9. Create gunicorn systemd service
sudo nano /etc/systemd/system/gunicorn.service
```

**Gunicorn Service File**:

```ini
[Unit]
Description=Gunicorn daemon for MediChain
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/medichain
ExecStart=/home/ubuntu/medichain/venv/bin/gunicorn \
          --workers 4 \
          --bind unix:/run/gunicorn.sock \
          medichain.wsgi:application

[Install]
WantedBy=multi-user.target
```

**Nginx Configuration**:

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    location / {
        proxy_pass http://unix:/run/gunicorn.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /static/ {
        alias /home/ubuntu/medichain/staticfiles/;
    }

    location /media/ {
        alias /home/ubuntu/medichain/media/;
    }
}
```

### Option 2: DigitalOcean App Platform

Simple 1-click deployment:
1. Connect GitHub repository
2. Choose Python runtime
3. Configure environment variables
4. Deploy

### Option 3: Heroku

```bash
# Install Heroku CLI
# Login
heroku login

# Create app
heroku create medichain-hospital

# Add MySQL addon
heroku addons:create cleardb:ignite

# Set environment variables
heroku config:set SECRET_KEY='...'
heroku config:set FERNET_KEY='...'

# Deploy
git push heroku main

# Run migrations
heroku run python manage.py migrate
```

---

## 🗄️ Database Migration for Production

### Backup Existing Database

```bash
# Backup MySQL
mysqldump -u root -p medichain > backup_medichain.sql

# Restore if needed
mysql -u root -p medichain < backup_medichain.sql
```

### Run Migrations Safely

```bash
# Test migrations in staging first
python manage.py migrate --plan

# Run migrations
python manage.py migrate

# Verify
python manage.py showmigrations
```

---

## 📧 Email Service Configuration

### Gmail (Development Only)

Already configured in `.env.example`

### SendGrid (Production Recommended)

```bash
pip install sendgrid
```

```python
# settings.py
EMAIL_BACKEND = 'sendgrid_backend.SendgridBackend'
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')
```

### AWS SES

```python
EMAIL_BACKEND = 'django_ses.SESBackend'
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_SES_REGION_NAME = 'us-east-1'
AWS_SES_REGION_ENDPOINT = 'email.us-east-1.amazonaws.com'
```

---

## 🔍 Monitoring & Logging

### Log Files

```bash
# Django logs
tail -f /var/log/medichain/django.log

# Nginx logs
tail -f /var/log/nginx/error.log

# Gunicorn logs
journalctl -u gunicorn -f
```

### Error Tracking

Use Sentry for error monitoring:

```python
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn=os.environ.get('SENTRY_DSN'),
    integrations=[DjangoIntegration()],
    traces_sample_rate=0.1,
    send_default_pii=False
)
```

### Performance Monitoring

```bash
pip install django-debug-toolbar
# Configure for production monitoring
```

---

## 📈 Scaling

### Horizontal Scaling (Multiple Servers)

1. **Load Balancer**: Route traffic between servers
2. **Shared Database**: Single RDS instance
3. **Shared Media**: S3 bucket
4. **Cache**: Redis for sessions

### Vertical Scaling

1. Upgrade EC2 instance size
2. Increase database resources
3. Increase worker processes

---

## 🔄 Continuous Integration/Deployment

### GitHub Actions Example

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Run tests
        run: |
          python -m pip install -r requirements.txt
          python manage.py test
      
      - name: Deploy to server
        run: |
          # SSH into server and pull latest code
          ssh -i ${{ secrets.DEPLOY_KEY }} ubuntu@${{ secrets.SERVER_IP }} \
            'cd medichain && git pull && source venv/bin/activate && \
            pip install -r requirements.txt && \
            python manage.py migrate && \
            python manage.py collectstatic --noinput && \
            sudo systemctl restart gunicorn'
```

---

## 🚨 Incident Response

### Database Down

```bash
# Check MySQL status
sudo systemctl status mysql

# Restart if needed
sudo systemctl restart mysql

# Check logs
sudo tail -f /var/log/mysql/error.log
```

### High Memory Usage

```bash
# Check processes
top

# Identify Django/Gunicorn processes
ps aux | grep gunicorn

# Restart service
sudo systemctl restart gunicorn
```

### Email Not Sending

```bash
# Check email credentials in .env
cat .env | grep EMAIL

# Test SMTP connection
python -c "
import smtplib
with smtplib.SMTP('smtp.gmail.com', 587) as s:
    s.starttls()
    s.login('user@gmail.com', 'password')
    print('Connection successful')
"
```

---

## 📊 Performance Optimization

### Database Indexing

```python
# In models.py
class MedicalRecord(models.Model):
    patient_id = models.UUIDField(db_index=True)  # Add index
    hospital_id = models.UUIDField(db_index=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['patient_id', 'created_at']),
            models.Index(fields=['hospital_id', '-created_at']),
        ]
```

### Caching

```python
# Cache API responses
from django.views.decorators.cache import cache_page

@cache_page(60 * 5)  # 5 minutes
def get_dashboard(request):
    ...
```

### Compress Responses

```python
# Install compression middleware
pip install django-compressor

# Add to INSTALLED_APPS
INSTALLED_APPS += ['compressor']
```

---

## ✅ Post-Deployment Checklist

- [ ] Access application at domain
- [ ] Test user registration
- [ ] Test email sending (OTP)
- [ ] Test database connectivity
- [ ] Verify static/media files loading
- [ ] Check error logs
- [ ] Monitor server resources
- [ ] Backup database
- [ ] Set up monitoring alerts
- [ ] Configure uptime monitoring

---

## 📞 Deployment Support

Contact hosting provider for:
- SSL certificate renewal
- Server maintenance
- Database backups
- Security updates
- Scaling assistance

---

**Status**: Ready for production deployment
**Last Updated**: March 30, 2026
