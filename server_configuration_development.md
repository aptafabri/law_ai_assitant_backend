# Documentation of Your Configuration

This document provides a detailed overview of your current configuration for the backend server at `dev.backend.adaletgpt.com`. It includes the setup of Nginx, SSL certificates with Certbot, the FastAPI backend application managed by systemd, and other relevant settings. This documentation will help you understand your setup and assist in future maintenance or scaling efforts.

---

## Table of Contents

1. [Server Overview](#1-server-overview)
2. [Nginx Configuration](#2-nginx-configuration)
   - [Site Configuration File](#site-configuration-file)
3. [SSL Certificate Setup](#3-ssl-certificate-setup)
4. [Backend Application Setup](#4-backend-application-setup)
   - [Systemd Service File](#systemd-service-file)
   - [FastAPI Application Configuration](#fastapi-application-configuration)
5. [Frontend Application Configuration](#5-frontend-application-configuration)
6. [Firewall and Security Groups](#6-firewall-and-security-groups)
7. [Automated Tasks and Renewals](#7-automated-tasks-and-renewals)
8. [Monitoring and Logs](#8-monitoring-and-logs)
9. [Additional Notes](#9-additional-notes)

---

## 1. Server Overview

- **Operating System**: Ubuntu 22.04 LTS
- **Backend Server IP**: `3.75.191.42` (Replace with your actual server IP)
- **Domain**: `dev.backend.adaletgpt.com`
- **Backend Application**: FastAPI application running with Gunicorn and Uvicorn workers
- **Web Server**: Nginx
- **SSL Certificates**: Let's Encrypt via Certbot
- **Process Management**: Systemd service
- **Frontend Application**: `dev.chat.adaletgpt.com`

---

## 2. Nginx Configuration

### Site Configuration File

**Location**: `/etc/nginx/sites-available/dev.backend.adaletgpt.com`

**Symlink**: `/etc/nginx/sites-enabled/dev.backend.adaletgpt.com`

**Contents of the configuration file:**

```nginx
server {
    listen 80;
    server_name dev.backend.adaletgpt.com;

    location / {
        proxy_pass http://127.0.0.1:8000;  # Proxy to the backend application
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Redirect all HTTP requests to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name dev.backend.adaletgpt.com;

    ssl_certificate /etc/letsencrypt/live/dev.backend.adaletgpt.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/dev.backend.adaletgpt.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;  # Proxy to the backend application
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Explanation:**

- **Port 80 Server Block**:
  - Listens on port 80 for HTTP connections.
  - Proxies requests to the backend application running on `127.0.0.1:8000`.
  - Redirects all HTTP traffic to HTTPS.

- **Port 443 Server Block**:
  - Listens on port 443 for HTTPS connections.
  - Configured with SSL certificates provided by Let's Encrypt.
  - Proxies requests to the backend application.

**Enabling the Site:**

```bash
sudo ln -s /etc/nginx/sites-available/dev.backend.adaletgpt.com /etc/nginx/sites-enabled/
```

**Testing and Reloading Nginx:**

```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## 3. SSL Certificate Setup

SSL certificates are obtained from Let's Encrypt using Certbot.

**Installing Certbot:**

```bash
sudo apt update
sudo apt install certbot python3-certbot-nginx
```

**Obtaining Certificates:**

```bash
sudo certbot --nginx -d dev.backend.adaletgpt.com
```

Certbot modifies the Nginx configuration to include SSL directives and sets up automatic renewal.

**Certificate Files Location:**

```bash
/etc/letsencrypt/live/dev.backend.adaletgpt.com/
```

**Verifying Certificates:**

```bash
sudo ls /etc/letsencrypt/live/dev.backend.adaletgpt.com/
```

**Automated Renewal:**

Certbot sets up a cron job or systemd timer for automatic certificate renewal.

---

## 4. Backend Application Setup

### Systemd Service File

**Location**: `/etc/systemd/system/adaletgpt_backend.service`

**Contents of the service file:**

```ini
[Unit]
Description=AdaletGPT Backend service
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/AdaletGPT_Backend/app
ExecStart=/home/ubuntu/AdaletGPT_Backend/venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 127.0.0.1:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

**Explanation:**

- **User**: Runs under the `ubuntu` user.
- **WorkingDirectory**: Directory where the backend application code resides.
- **ExecStart**: Command to start the Gunicorn server with 4 Uvicorn workers, binding to `127.0.0.1:8000`.
- **Restart**: Automatically restarts the service on failure.

**Managing the Service:**

```bash
sudo systemctl daemon-reload
sudo systemctl start adaletgpt_backend.service
sudo systemctl enable adaletgpt_backend.service
sudo systemctl status adaletgpt_backend.service
```

### FastAPI Application Configuration

- **Application Directory**: `/home/ubuntu/AdaletGPT_Backend/app`
- **Virtual Environment**: `/home/ubuntu/AdaletGPT_Backend/venv`

**Setting Up the Virtual Environment:**

```bash
cd /home/ubuntu/AdaletGPT_Backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
```

**Environment Variables (.env file):**

**Location**: `/home/ubuntu/AdaletGPT_Backend/.env`

**Contents Example:**

```env
DATABASE_URL=postgresql://username:password@localhost/dbname
SECRET_KEY=your_secret_key
```

**CORS Configuration in `main.py`:**

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://dev.chat.adaletgpt.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 5. Frontend Application Configuration

**Domain**: `dev.chat.adaletgpt.com`

**API Base URL Configuration:**

**Environment File**: `/home/ubuntu/AdaletGPT_Frontend/.env`

**Contents:**

```env
REACT_APP_API_BASE_URL=https://dev.backend.adaletgpt.com
```

**Building the Frontend Application:**

```bash
cd /home/ubuntu/AdaletGPT_Frontend
npm install
npm run build
```

**Running the Frontend Application with PM2:**

```bash
pm2 start server.js --name adaletgpt-frontend
pm2 save
```

---

## 6. Firewall and Security Groups

### UFW Firewall (if enabled)

**Check UFW Status:**

```bash
sudo ufw status
```

**Allow Nginx Full Profile:**

```bash
sudo ufw allow 'Nginx Full'
sudo ufw reload
```

### AWS Security Groups

**Inbound Rules for the Backend Server:**

- **HTTP (Port 80):**

  - **Type**: HTTP
  - **Protocol**: TCP
  - **Port Range**: 80
  - **Source**: 0.0.0.0/0

- **HTTPS (Port 443):**

  - **Type**: HTTPS
  - **Protocol**: TCP
  - **Port Range**: 443
  - **Source**: 0.0.0.0/0

**Ensure these ports are open to allow incoming traffic to your backend server.**

---

## 7. Automated Tasks and Renewals

### Certbot Automatic Renewal

**Verify Renewal Timer:**

```bash
sudo systemctl list-timers | grep certbot
```

**Test Renewal Process:**

```bash
sudo certbot renew --dry-run
```

### System Updates

**Regularly update system packages:**

```bash
sudo apt update && sudo apt upgrade -y
```

Consider setting up unattended upgrades for security updates.

---

## 8. Monitoring and Logs

### Nginx Logs

- **Access Log**: `/var/log/nginx/access.log`
- **Error Log**: `/var/log/nginx/error.log`

### Backend Application Logs

**Access logs using journalctl:**

```bash
sudo journalctl -u adaletgpt_backend.service -f
```

### Frontend Application Logs

**Access PM2 logs:**

```bash
pm2 logs adaletgpt-frontend
```

---

## 9. Additional Notes

### Security Best Practices

- **SSH Access**:

  - Limit SSH access to trusted IP addresses.
  - Use SSH keys instead of passwords.
  - Disable root login via SSH.

- **Nginx Security Enhancements**:

  Add security headers to your Nginx configuration:

  ```nginx
  add_header X-Frame-Options SAMEORIGIN;
  add_header X-Content-Type-Options nosniff;
  add_header X-XSS-Protection "1; mode=block";
  add_header Content-Security-Policy "default-src 'self'";
  ```

- **Regular Backups**:

  Implement a backup strategy for your application data and configurations.

### Documentation and Version Control

- **Version Control**:

  - Keep your code and configuration files under version control using Git.
  - Use branches to manage development and production versions.

- **Documentation**:

  - Document any manual changes or custom configurations.
  - Maintain README files with setup instructions.

### Scaling Considerations

- **Load Balancing**:

  - Consider using a load balancer if scaling horizontally.

- **Containerization**:

  - Use Docker to containerize your application for consistent deployment environments.

- **Orchestration Tools**:

  - Explore using Kubernetes or Docker Swarm for managing multiple containers and services.

---

**End of Document**

---

Feel free to update or expand upon this documentation as your application evolves. Keeping thorough and up-to-date documentation is essential for effective maintenance, troubleshooting, and onboarding new team members.

If you have any questions or need further assistance, please don't hesitate to ask.
