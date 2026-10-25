#!/usr/bin/env bash
# 下线:在服务器上以 root 运行。只删除 setup.sh / docs/deploy.md 里装过的东西,
# 不碰 x-ui、Xray、nginx、qbittorrent 等其他服务。DeepSeek 的 API Key 要去控制台手动删除。
set -uo pipefail

MANIFEST=/root/bill-ocr-installed.txt
has() { grep -qxF "$1" "$MANIFEST" 2>/dev/null; }

echo "== 1. 停止并删除演示服务"
systemctl disable --now bill-ocr 2>/dev/null
rm -f /etc/systemd/system/bill-ocr.service
systemctl daemon-reload

echo "== 2. 删除 Cloudflare Tunnel(连带 DNS 记录 ocr.wyphub.com)"
if has tunnel; then
  systemctl disable --now cloudflared 2>/dev/null
  cloudflared service uninstall 2>/dev/null
  cloudflared tunnel cleanup bill-ocr 2>/dev/null
  cloudflared tunnel delete -f bill-ocr && echo "tunnel 已删除"
  echo "!! DNS 记录 ocr.wyphub.com 需要去 Cloudflare 面板手动删除(cloudflared 不会自动删)"
  rm -rf /etc/cloudflared /root/.cloudflared
  apt-get purge -y cloudflared >/dev/null 2>&1 && echo "cloudflared 已卸载"
fi

echo "== 3. 删除代码、密钥、依赖和模型"
rm -rf /opt/bill-ocr                        # 含 .env 和 .venv
if has user; then userdel -r ocr 2>/dev/null; rm -rf /home/ocr; fi  # 含 uv、uv 缓存、PaddleOCR 模型

echo "== 4. 删除 swap"
if has swap; then
  swapoff /swapfile 2>/dev/null; rm -f /swapfile
  sed -i '\#^/swapfile none swap sw 0 0$#d' /etc/fstab
fi

echo "== 4b. 卸载部署时新装的系统包(原本就有的不动)"
for pkg in $(grep '^apt:' "$MANIFEST" 2>/dev/null | cut -d: -f2); do
  apt-get purge -y "$pkg" >/dev/null 2>&1 && echo "已卸载 $pkg"
done

echo "== 5. 检查残留(下面应全部为空/不存在)"
systemctl list-unit-files | grep -E "bill-ocr|cloudflared" || echo "服务: 无"
id ocr 2>/dev/null || echo "用户 ocr: 无"
ls -d /opt/bill-ocr /home/ocr /swapfile /etc/cloudflared 2>/dev/null || echo "目录/文件: 无"
ss -ltn | grep -q ":8090 " && echo "!! 8090 仍在监听" || echo "端口 8090: 无"
rm -f "$MANIFEST"
echo "完成。别忘了:DeepSeek 控制台删 Key;Cloudflare 面板删 ocr.wyphub.com 的 DNS 记录。"
