#!/usr/bin/env bash
# ==============================================================================
# SCRIPT AUTOMATIZADO DE DESPLIEGUE EN AWS ACADEMY EC2 (UBUNTU 22.04 / 24.04 LTS)
# Proyecto 3: Sistema de Trazabilidad y Pedidos Pastelería Artesanal "Dulce Arte"
# Stack: Nginx + Gunicorn + Django / DRF + PostgreSQL (Instancia EC2 Única)
# ==============================================================================
set -e

echo "=================================================================="
echo "🎂 Iniciando Despliegue de DULCE ARTE en AWS EC2..."
echo "=================================================================="

APP_DIR=$(pwd)
DB_NAME="dulce_arte_db"
DB_USER="dulce_arte_user"
DB_PASS="DulceArte2026_AWS!"

# 1. Obtener IP Pública de la instancia EC2 automáticamente (IMDSv2 / IMDSv1)
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" || true)
if [ -n "$TOKEN" ]; then
    PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4 || echo "localhost")
else
    PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 || echo "localhost")
fi
echo "🌐 IP Pública detectada en AWS EC2: $PUBLIC_IP"

# 2. Instalar paquetes del sistema (PostgreSQL, Python, Nginx)
sudo apt-get update -y
sudo apt-get install -y python3-pip python3-venv python3-dev libpq-dev postgresql postgresql-contrib nginx curl

# 3. Configurar Base de Datos Relacional PostgreSQL en la instancia EC2
sudo systemctl enable postgresql
sudo systemctl start postgresql

sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname = '$DB_USER'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';"

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER ENCODING 'UTF8';"

sudo -u postgres psql -c "ALTER ROLE $DB_USER SET client_encoding TO 'utf8';"
sudo -u postgres psql -c "ALTER ROLE $DB_USER SET default_transaction_isolation TO 'read committed';"
sudo -u postgres psql -c "ALTER ROLE $DB_USER SET timezone TO 'America/Santiago';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"

# 4. Crear archivo .env de producción en EC2
cat > "$APP_DIR/.env" <<EOF
SECRET_KEY=django-production-dulce-arte-aws-ec2-key-2026-segura
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,$PUBLIC_IP,*
CSRF_TRUSTED_ORIGINS=http://localhost,http://127.0.0.1,http://$PUBLIC_IP,http://$PUBLIC_IP:8000

DB_ENGINE=postgresql
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASS
DB_HOST=localhost
DB_PORT=5432

AWS_EC2_PUBLIC_IP=$PUBLIC_IP
EOF

# 5. Entorno Virtual Python e Instalación de Dependencias
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

# 6. Aplicar Migraciones del ORM a PostgreSQL, Poblar Datos y Recolectar Estáticos
"$APP_DIR/venv/bin/python" "$APP_DIR/manage.py" makemigrations
"$APP_DIR/venv/bin/python" "$APP_DIR/manage.py" migrate
"$APP_DIR/venv/bin/python" "$APP_DIR/manage.py" collectstatic --noinput
"$APP_DIR/venv/bin/python" "$APP_DIR/manage.py" seed_dulce_arte

# Asegurar permisos para que Nginx (www-data) pueda servir staticfiles y media
mkdir -p "$APP_DIR/media"
chmod o+x "$HOME" 2>/dev/null || true
chmod o+x "$APP_DIR" 2>/dev/null || true
chmod -R 755 "$APP_DIR/staticfiles" 2>/dev/null || true
chmod -R 775 "$APP_DIR/media" 2>/dev/null || true
sudo chown -R $(whoami):www-data "$APP_DIR/media" 2>/dev/null || true

# 7. Configurar Servicio Systemd para Gunicorn
USER_ACTUAL=$(whoami)
sudo bash -c "cat > /etc/systemd/system/dulce_arte.service" <<EOF
[Unit]
Description=Gunicorn Daemon para Pasteleria Dulce Arte (Django + DRF)
After=network.target postgresql.service

[Service]
User=$USER_ACTUAL
Group=www-data
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 dulce_arte_project.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable dulce_arte
sudo systemctl restart dulce_arte

# 8. Configurar Nginx como Reverse Proxy en Puerto 80
sudo bash -c "cat > /etc/nginx/sites-available/dulce_arte" <<EOF
server {
    listen 80;
    server_name $PUBLIC_IP _;
    client_max_body_size 15M;

    location /static/ {
        alias $APP_DIR/staticfiles/;
    }

    location /media/ {
        alias $APP_DIR/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/dulce_arte /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

echo "=================================================================="
echo "✅ DESPLIEGUE COMPLETADO EXITOSAMENTE EN AWS EC2"
echo "🌐 Plataforma Web      : http://$PUBLIC_IP/"
echo "🛡️  Django Admin        : http://$PUBLIC_IP/admin/"
echo "⚡ API REST (DRF)      : http://$PUBLIC_IP/api/v1/"
echo "🔑 Usuario Admin       : admin / dulcearte2026"
echo "=================================================================="
