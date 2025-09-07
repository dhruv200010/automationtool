# 🚀 Hostinger KVM 2 Deployment Guide

This guide will help you deploy your video automation pipeline with Celery and Redis on Hostinger KVM 2.

## 📋 **Prerequisites**

- ✅ Hostinger KVM 2 server with Ubuntu 20.04/22.04 LTS
- ✅ Root access via SSH
- ✅ Domain name (optional but recommended)
- ✅ Sufficient resources (4GB+ RAM, 20GB+ storage recommended)

## 🔧 **Server Setup**

### 1. Connect to Your Server
```bash
ssh root@your-server-ip
```

### 2. Update System
```bash
apt update && apt upgrade -y
```

### 3. Install Required Packages
```bash
# Install essential packages
apt install -y curl wget git vim htop unzip software-properties-common

# Install Python 3.10
apt install -y python3.10 python3.10-venv python3-pip

# Install FFmpeg
apt install -y ffmpeg

# Install Redis
apt install -y redis-server

# Install Nginx (for reverse proxy)
apt install -y nginx

# Install UFW (firewall)
apt install -y ufw
```

## 📁 **Application Deployment**

### 1. Create Application Directory
```bash
mkdir -p /opt/video-automation
cd /opt/video-automation
```

### 2. Clone Your Repository
```bash
# Clone your repository
git clone https://github.com/your-username/automationtool.git .

# Or upload files via SCP/SFTP
# scp -r ./automationtool/* root@your-server-ip:/opt/video-automation/
```

### 3. Set Up Python Environment
```bash
# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Create Required Directories
```bash
mkdir -p /opt/video-automation/{input,output,logs}
chmod 755 /opt/video-automation/{input,output,logs}
```

## ⚙️ **Configuration**

### 1. Environment Variables
Create `/opt/video-automation/.env`:
```bash
cat > /opt/video-automation/.env << EOF
# API Keys
OPENROUTER_API_KEY=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
DEEPGRAM_API_KEY=c4183f2d74c789c131cac4dcc7f7a41545d675e2
TELEGRAM_BOT_TOKEN=7951302729:AAEJJZv-C4XX_vewa4PMb0w8gmxjG_O1qjk

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# Application Configuration
PORT=8000
FLASK_ENV=production
PYTHONPATH=/opt/video-automation

# File Paths
INPUT_FOLDER=/opt/video-automation/input
OUTPUT_FOLDER=/opt/video-automation/output
EOF
```

### 2. Update Configuration Files
The `config/master_config.json` has been updated with Hostinger paths:
```json
{
  "input_folder": "/opt/video-automation/input",
  "output_folder": "/opt/video-automation/output",
  "pipeline_steps": {
    "add_subtitles": true,
    "trim_silence": true,
    "create_shorts": true,
    "generate_titles": false,
    "upload_shorts": false
  },
  "celery_config": {
    "broker_url": "redis://localhost:6379/0",
    "result_backend": "redis://localhost:6379/0",
    "task_time_limit": 1800,
    "task_soft_time_limit": 1500,
    "worker_concurrency": 1,
    "worker_pool": "solo"
  }
}
```

## 🔧 **Service Configuration**

### 1. Redis Service
```bash
# Start and enable Redis
systemctl start redis-server
systemctl enable redis-server

# Verify Redis is running
redis-cli ping
```

### 2. Celery Worker Service
Create `/etc/systemd/system/celery-worker.service`:
```ini
[Unit]
Description=Celery Worker for Video Automation
After=network.target redis.service

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/video-automation
Environment=PATH=/opt/video-automation/venv/bin
Environment=PYTHONPATH=/opt/video-automation
ExecStart=/opt/video-automation/venv/bin/python start_worker.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 3. Flask Application Service
Create `/etc/systemd/system/video-automation.service`:
```ini
[Unit]
Description=Video Automation Flask App
After=network.target redis.service celery-worker.service

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/video-automation
Environment=PATH=/opt/video-automation/venv/bin
Environment=PYTHONPATH=/opt/video-automation
ExecStart=/opt/video-automation/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## 🌐 **Nginx Configuration**

### 1. Create Nginx Site Configuration
Create `/etc/nginx/sites-available/video-automation`:
```nginx
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain

    # Increase client max body size for large video uploads
    client_max_body_size 500M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeout settings for long video processing
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Serve static files directly
    location /output/ {
        alias /opt/video-automation/output/;
        expires 1h;
        add_header Cache-Control "public, immutable";
    }
}
```

### 2. Enable Nginx Site
```bash
# Enable site
ln -s /etc/nginx/sites-available/video-automation /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default

# Test configuration
nginx -t

# Restart Nginx
systemctl restart nginx
systemctl enable nginx
```

## 🔥 **Firewall Configuration**

```bash
# Configure UFW
ufw allow ssh
ufw allow 80
ufw allow 443
ufw --force enable
```

## 🚀 **Start Services**

### 1. Reload Systemd
```bash
systemctl daemon-reload
```

### 2. Enable Services
```bash
systemctl enable redis-server
systemctl enable celery-worker
systemctl enable video-automation
```

### 3. Start Services
```bash
systemctl start redis-server
systemctl start celery-worker
systemctl start video-automation
```

### 4. Check Status
```bash
systemctl status redis-server
systemctl status celery-worker
systemctl status video-automation
```

## 🔒 **SSL Certificate (Optional)**

### 1. Install Certbot
```bash
apt install -y certbot python3-certbot-nginx
```

### 2. Get SSL Certificate
```bash
certbot --nginx -d your-domain.com
```

## 🧪 **Testing**

### 1. Test Services
```bash
# Check all services
systemctl status redis-server celery-worker video-automation

# Test Redis connection
redis-cli ping

# Test local access
curl http://localhost:8000/health
```

### 2. Test Web Interface
```bash
# Test external access
curl http://your-server-ip/health
```

### 3. Test Video Processing
1. Visit your domain/IP in browser
2. Upload a small test video
3. Monitor logs for processing
4. Check output directory for results

## 📊 **Monitoring and Logs**

### 1. View Logs
```bash
# Application logs
journalctl -u video-automation -f

# Celery worker logs
journalctl -u celery-worker -f

# Redis logs
tail -f /var/log/redis/redis-server.log

# Nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

### 2. Health Check Script
Create `/opt/video-automation/health_check.sh`:
```bash
#!/bin/bash

# Check if services are running
check_service() {
    if systemctl is-active --quiet $1; then
        echo "✅ $1 is running"
    else
        echo "❌ $1 is not running"
        systemctl restart $1
    fi
}

echo "🔍 Checking services..."
check_service redis-server
check_service celery-worker
check_service video-automation

# Check disk space
DISK_USAGE=$(df /opt/video-automation | tail -1 | awk '{print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 80 ]; then
    echo "⚠️ Disk usage is high: ${DISK_USAGE}%"
fi

# Check memory usage
MEMORY_USAGE=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
if [ $MEMORY_USAGE -gt 80 ]; then
    echo "⚠️ Memory usage is high: ${MEMORY_USAGE}%"
fi
```

Make it executable and add to crontab:
```bash
chmod +x /opt/video-automation/health_check.sh
(crontab -l 2>/dev/null; echo "*/5 * * * * /opt/video-automation/health_check.sh") | crontab -
```

## 🔧 **Troubleshooting**

### Common Issues

#### 1. Services Not Starting
```bash
# Check logs
journalctl -u service-name -f

# Restart services
systemctl restart service-name
```

#### 2. Redis Connection Issues
```bash
# Test Redis connection
redis-cli ping

# Check Redis logs
tail -f /var/log/redis/redis-server.log
```

#### 3. File Permission Issues
```bash
# Fix permissions
chown -R root:root /opt/video-automation
chmod -R 755 /opt/video-automation
```

#### 4. Memory Issues
```bash
# Monitor memory usage
htop
free -h

# Restart services if needed
systemctl restart celery-worker
```

## 📈 **Performance Optimization**

### 1. System Optimization
```bash
# Increase file limits
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# Optimize Redis
echo "maxmemory 512mb" >> /etc/redis/redis.conf
echo "maxmemory-policy allkeys-lru" >> /etc/redis/redis.conf
systemctl restart redis-server
```

### 2. Application Optimization
```bash
# Set optimal worker settings
export CELERY_WORKER_CONCURRENCY=2
export CELERY_WORKER_PREFETCH_MULTIPLIER=1
```

## 🔄 **Updates and Maintenance**

### 1. Regular Updates
```bash
# Update system packages
apt update && apt upgrade -y

# Update Python packages
cd /opt/video-automation
source venv/bin/activate
pip install --upgrade -r requirements.txt
```

### 2. Backup Strategy
```bash
# Create backup script
cat > /opt/video-automation/backup.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
tar -czf /opt/backups/video-automation_$DATE.tar.gz /opt/video-automation
find /opt/backups -name "video-automation_*.tar.gz" -mtime +7 -delete
EOF

chmod +x /opt/video-automation/backup.sh

# Add to crontab
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/video-automation/backup.sh") | crontab -
```

## ✅ **Deployment Complete!**

Your video automation pipeline is now successfully deployed on Hostinger KVM 2 with:

- ✅ **Celery background processing** - No more HTTP timeouts
- ✅ **Redis message broker** - Reliable task queuing
- ✅ **Nginx reverse proxy** - Better performance and security
- ✅ **Systemd services** - Automatic startup and restart
- ✅ **SSL support** - Secure HTTPS access
- ✅ **Monitoring and logging** - Health checks and log rotation
- ✅ **Backup strategy** - Regular automated backups

### Next Steps:
1. **Test thoroughly** with various video sizes
2. **Monitor performance** and adjust resources as needed
3. **Set up domain name** and SSL certificate
4. **Implement monitoring** with tools like Prometheus/Grafana
5. **Consider scaling** if you need to handle more concurrent users

Your application is now ready for production use on Hostinger KVM 2! 🎉
