#!/usr/bin/env bash
# 在 Ubuntu 22.04+ 上一键安装 / 更新 PaperMate
# 用法：
#   sudo bash deploy-on-host.sh
# 前置：已将 papermate-*.tar.gz 放到 /tmp/papermate/（可用 PKG_DIR 覆盖）
#
# 更新时会尽量保留已有 .env 与 data/（SQLite）。

set -euo pipefail

# 若从即将被替换的 /opt/papermate/backend 目录启动，mv 后 getcwd 会失败
cd / || true

PKG_DIR="${PKG_DIR:-/tmp/papermate}"
BACKEND_ROOT="${BACKEND_ROOT:-/opt/papermate/backend}"
WEB_ROOT="${WEB_ROOT:-/var/www/papermate}"
APP_USER="${APP_USER:-papermate}"

echo "==> packages in ${PKG_DIR}"
ls -lh "${PKG_DIR}"/papermate-*.tar.gz

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-venv python3-pip nginx curl tar rsync software-properties-common

# Ubuntu 22.04 默认多为 3.10；项目要求 >=3.11
if ! python3.11 --version >/dev/null 2>&1; then
  add-apt-repository -y ppa:deadsnakes/ppa
  apt-get update -y
  apt-get install -y python3.11 python3.11-venv python3.11-dev
fi
# 必须用系统解释器，避免当前 shell 已 activate 旧 .venv 时
# command -v 指向即将被 rm -rf 的路径
if [[ -x /usr/bin/python3.11 ]]; then
  PYTHON_BIN=/usr/bin/python3.11
elif command -v python3.11 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3.11)"
else
  PYTHON_BIN="$(command -v python3)"
fi
echo "==> using ${PYTHON_BIN} ($("${PYTHON_BIN}" --version 2>&1))"

id -u "${APP_USER}" >/dev/null 2>&1 || useradd -r -m -d /opt/papermate -s /bin/bash "${APP_USER}"
mkdir -p /opt/papermate "${WEB_ROOT}" /var/log/papermate

BACKEND_TAR=$(ls -1 "${PKG_DIR}"/papermate-backend-*.tar.gz | tail -1)
FRONT_TAR=$(ls -1 "${PKG_DIR}"/papermate-frontend-*.tar.gz | tail -1)

echo "==> install backend from ${BACKEND_TAR}"
# 更新前暂存配置与数据
PRESERVE_DIR=$(mktemp -d /tmp/papermate-preserve.XXXXXX)
if [[ -f "${BACKEND_ROOT}/.env" ]]; then
  cp -a "${BACKEND_ROOT}/.env" "${PRESERVE_DIR}/.env"
fi
if [[ -d "${BACKEND_ROOT}/data" ]]; then
  cp -a "${BACKEND_ROOT}/data" "${PRESERVE_DIR}/data"
fi

rm -rf /opt/papermate/backend.new
mkdir -p /opt/papermate/backend.new
tar -xzf "${BACKEND_TAR}" -C /opt/papermate/backend.new
# tarball 顶层目录名为 backend
if [[ -d /opt/papermate/backend.new/backend ]]; then
  rm -rf "${BACKEND_ROOT}.bak"
  [[ -d "${BACKEND_ROOT}" ]] && mv "${BACKEND_ROOT}" "${BACKEND_ROOT}.bak" || true
  mv /opt/papermate/backend.new/backend "${BACKEND_ROOT}"
else
  rm -rf "${BACKEND_ROOT}.bak"
  [[ -d "${BACKEND_ROOT}" ]] && mv "${BACKEND_ROOT}" "${BACKEND_ROOT}.bak" || true
  mv /opt/papermate/backend.new "${BACKEND_ROOT}"
fi

# 恢复 .env / data
if [[ -f "${PRESERVE_DIR}/.env" ]]; then
  cp -a "${PRESERVE_DIR}/.env" "${BACKEND_ROOT}/.env"
  echo "==> restored existing .env"
fi
if [[ -d "${PRESERVE_DIR}/data" ]]; then
  mkdir -p "${BACKEND_ROOT}/data"
  # 不用 rsync：在失效 cwd 下 rsync 可能报 getcwd 错误
  cp -a "${PRESERVE_DIR}/data/." "${BACKEND_ROOT}/data/"
  echo "==> restored existing data/"
fi
rm -rf "${PRESERVE_DIR}"

cd "${BACKEND_ROOT}"
rm -rf .venv
"${PYTHON_BIN}" -m venv .venv
. .venv/bin/activate
pip install -U pip
# 演示默认 SQLite；若要用 PostgreSQL 改为: pip install -e '.[postgres]'
pip install -e .

if [[ ! -f .env ]]; then
  if [[ -f .env.production.example ]]; then
    cp .env.production.example .env
  else
    cat > .env <<'EOF'
PAPERMATE_ENV=prod
PAPERMATE_DATABASE_URL=sqlite:////opt/papermate/backend/data/prod.db
PAPERMATE_AUTH_SECRET=CHANGE_ME_AFTER_INSTALL
PAPERMATE_CORS_ORIGINS=http://127.0.0.1
PAPERMATE_ENABLE_DOCS=false
PAPERMATE_WORKER_TOKEN=CHANGE_ME_WORKER_TOKEN
PAPERMATE_LLM_API_KEY=
PAPERMATE_LLM_MODEL=deepseek-v4-flash
PAPERMATE_LLM_API_BASE=https://api.deepseek.com
PAPERMATE_CRAWL_ENABLED=true
EOF
  fi
  mkdir -p data
  sed -i 's|^PAPERMATE_ENV=.*|PAPERMATE_ENV=prod|' .env || true
  grep -q '^PAPERMATE_DATABASE_URL=' .env || echo 'PAPERMATE_DATABASE_URL=sqlite:////opt/papermate/backend/data/prod.db' >> .env
  sed -i 's|^PAPERMATE_DATABASE_URL=.*|PAPERMATE_DATABASE_URL=sqlite:////opt/papermate/backend/data/prod.db|' .env
  # 可按主机覆盖：PAPERMATE_PUBLIC_ORIGINS=http://10.119.9.119,http://192.168.1.4
  if [[ -n "${PAPERMATE_PUBLIC_ORIGINS:-}" ]]; then
    sed -i "s|^PAPERMATE_CORS_ORIGINS=.*|PAPERMATE_CORS_ORIGINS=${PAPERMATE_PUBLIC_ORIGINS}|" .env
  fi
  sed -i 's|^PAPERMATE_ENABLE_DOCS=.*|PAPERMATE_ENABLE_DOCS=false|' .env
  grep -q '^PAPERMATE_WORKER_TOKEN=' .env || echo 'PAPERMATE_WORKER_TOKEN=CHANGE_ME_WORKER_TOKEN' >> .env
  chmod 600 .env
  echo "==> 已生成 ${BACKEND_ROOT}/.env ，请编辑 AUTH_SECRET、WORKER_TOKEN 与 LLM_API_KEY（生产勿用占位符）"
fi

python -m alembic upgrade head

echo "==> install frontend from ${FRONT_TAR}"
rm -rf /tmp/pm-frontend
mkdir -p /tmp/pm-frontend
tar -xzf "${FRONT_TAR}" -C /tmp/pm-frontend
if [[ -d /tmp/pm-frontend/frontend ]]; then
  rsync -a --delete /tmp/pm-frontend/frontend/ "${WEB_ROOT}/"
else
  rsync -a --delete /tmp/pm-frontend/ "${WEB_ROOT}/"
fi
chown -R www-data:www-data "${WEB_ROOT}"

echo "==> nginx"
cat >/etc/nginx/sites-available/papermate <<'NGINX'
upstream papermate_api {
    server 127.0.0.1:8000;
    keepalive 16;
}
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    root /var/www/papermate;
    index index.html;
    client_max_body_size 32m;

    location /api/ {
        proxy_pass http://papermate_api/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 180s;
        proxy_send_timeout 180s;
    }
    location /health {
        proxy_pass http://papermate_api/health;
    }
    location / {
        try_files $uri $uri/ /index.html;
    }
}
NGINX
ln -sfn /etc/nginx/sites-available/papermate /etc/nginx/sites-enabled/papermate
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable --now nginx
systemctl reload nginx

echo "==> systemd"
cat >/etc/systemd/system/papermate-backend.service <<EOF
[Unit]
Description=PaperMate FastAPI Backend
After=network.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${BACKEND_ROOT}
EnvironmentFile=${BACKEND_ROOT}/.env
ExecStart=${BACKEND_ROOT}/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

chown -R "${APP_USER}:${APP_USER}" /opt/papermate
systemctl daemon-reload
systemctl enable --now papermate-backend
systemctl restart papermate-backend
sleep 2
curl -fsS http://127.0.0.1:8000/health || (journalctl -u papermate-backend -n 50 --no-pager; exit 1)
curl -fsS -o /dev/null -w "nginx_health=%{http_code}\n" http://127.0.0.1/health || true

echo
echo "安装/更新完成。"
echo "1) 核对 ${BACKEND_ROOT}/.env（PAPERMATE_LLM_API_KEY、PAPERMATE_AUTH_SECRET、CORS）"
echo "2) systemctl restart papermate-backend"
echo "3) 浏览器访问站点（校园网/VPN 下的浮动 IP 或内网 IP）"
echo "4) 可选导入种子: cd ${BACKEND_ROOT} && . .venv/bin/activate && python -m scripts.import_seed --seed ${PKG_DIR}/seed.json"
echo "运维说明见仓库 docs/服务器运维与更新.md"
