# 部署与下线

在线演示:https://ocr.wyphub.com(德国 Hetzner VPS,2 核 / 4G,CPU 版 PaddleOCR)

## 架构

```
浏览器 → Cloudflare(HTTPS) → Cloudflare Tunnel → cloudflared(VPS) → 127.0.0.1:8090 uvicorn
```

| 选择 | 原因 |
|---|---|
| Cloudflare Tunnel,不开端口 | 443 已被别的服务占用;Tunnel 由服务器主动连出去,不需要开放任何入站端口,HTTPS 由 Cloudflare 负责 |
| systemd + uv,不用 Docker | 机器上没有 Docker,少装一样也少删一样 |
| `Nice=10`、`CPUWeight=20`、`MemoryMax=2500M` | 同机还有其他服务;OCR 吃满 CPU 时让它们优先,内存超限只影响本服务 |
| 2G swap | 原本没有 swap,PaddleOCR 加载模型有内存峰值 |
| 不做调用限额 | 内置样本默认展示缓存的实验结果,不调大模型;实时调用约 0.002 元/次,API 余额用完即停 |

## 部署

1. 本机把 `.env` 传上去(不在终端打印内容):

   ```powershell
   scp .env root@<服务器IP>:/root/bill-ocr.env
   ```

2. 服务器上安装服务:

   ```bash
   git clone https://github.com/ypwang5/bill-ocr-llm.git /opt/bill-ocr && bash /opt/bill-ocr/deploy/setup.sh
   curl -s 127.0.0.1:8090/health      # 首次加载模型约 1 分钟
   ```

3. 服务器上配置 Tunnel(`login` 会打印一个链接,在浏览器里登录 Cloudflare 并选择域名授权):

   ```bash
   # 安装 cloudflared(官方 apt 源)
   mkdir -p --mode=0755 /usr/share/keyrings
   curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg -o /usr/share/keyrings/cloudflare-main.gpg
   echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main' > /etc/apt/sources.list.d/cloudflared.list
   apt-get update && apt-get install -y cloudflared

   cloudflared tunnel login
   cloudflared tunnel create bill-ocr
   cloudflared tunnel route dns bill-ocr ocr.wyphub.com
   mkdir -p /etc/cloudflared
   cat > /etc/cloudflared/config.yml <<EOF
   tunnel: bill-ocr
   credentials-file: $(ls /root/.cloudflared/*.json)
   ingress:
     - hostname: ocr.wyphub.com
       service: http://127.0.0.1:8090
     - service: http_status:404
   EOF
   cloudflared service install && echo tunnel >> /root/bill-ocr-installed.txt
   ```

更新代码:`bash /opt/bill-ocr/deploy/setup.sh`(会 `git pull` 并重启)。

## 下线

所有新装的东西都记在服务器的 `/root/bill-ocr-installed.txt` 里,下线脚本只删清单上的内容。

```bash
bash /opt/bill-ocr/deploy/teardown.sh
```

| 删除内容 | 位置 |
|---|---|
| 服务 | `bill-ocr.service`、`cloudflared` 服务、cloudflared 本体 |
| Tunnel | `bill-ocr`、`/etc/cloudflared`、`/root/.cloudflared` |
| 代码、密钥、依赖 | `/opt/bill-ocr`(含 `.env`、`.venv`) |
| 用户及其目录 | `ocr`、`/home/ocr`(含 uv、uv 缓存、PaddleOCR 模型) |
| swap | `/swapfile` 及 `/etc/fstab` 中对应的那一行 |

脚本最后会检查残留。有两步要**手动**做:

1. Cloudflare 面板 → wyphub.com → DNS:删掉 `ocr` 这条 CNAME 记录
2. DeepSeek 控制台:删掉部署时用的 API Key
