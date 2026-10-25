#!/usr/bin/env bash
# 在服务器上以 root 运行:装好演示服务(不含 Cloudflare Tunnel,见 docs/deploy.md)。
# 所有新建的东西都记进 MANIFEST,下线时 teardown.sh 只删清单里的,不碰机器上的其他服务。
set -euo pipefail

REPO=https://github.com/ypwang5/bill-ocr-llm.git
APP=/opt/bill-ocr
MANIFEST=/root/bill-ocr-installed.txt
note() { grep -qxF "$1" "$MANIFEST" 2>/dev/null || echo "$1" >> "$MANIFEST"; }

# 1. swap:PaddleOCR 加载模型时有内存峰值,机器原本没有 swap
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
  note swap
fi

# 1b. OpenCV(PaddleOCR 依赖)需要系统的 libGL;只在原本没装时安装并记账,下线时才知道该不该删
for pkg in libgl1 libglib2.0-0; do
  if ! dpkg -s "$pkg" >/dev/null 2>&1; then
    apt-get install -y "$pkg" >/dev/null
    note "apt:$pkg"
  fi
done

# 2. 专用用户:服务不用 root 跑
if ! id ocr >/dev/null 2>&1; then
  useradd --system --create-home --home-dir /home/ocr --shell /usr/sbin/nologin ocr
  note user
fi

# 3. 代码 + 依赖(uv 装在 ocr 用户自己的目录里,下线删用户即删干净)
if [ ! -d "$APP/.git" ]; then
  git clone "$REPO" "$APP"
  note app
fi
chown -R ocr:ocr "$APP"
sudo -u ocr -H bash -c 'command -v ~/.local/bin/uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh'
sudo -u ocr -H bash -c "cd $APP && git pull --ff-only && ~/.local/bin/uv sync --no-dev"

# 4. .env 由本机 scp 到 /root/bill-ocr.env,这里只移动并收紧权限,不打印内容
if [ -f /root/bill-ocr.env ]; then
  install -o ocr -g ocr -m 600 /root/bill-ocr.env "$APP/.env" && rm -f /root/bill-ocr.env
fi
[ -f "$APP/.env" ] || { echo "缺少 $APP/.env"; exit 1; }

# 5. systemd 服务
install -m 644 "$APP/deploy/bill-ocr.service" /etc/systemd/system/bill-ocr.service
note service
systemctl daemon-reload
systemctl enable --now bill-ocr
systemctl restart bill-ocr
echo "已启动;首次加载模型约 1 分钟:curl -s 127.0.0.1:8090/health"
