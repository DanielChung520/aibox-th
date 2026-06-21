# ABC Desktop / AIBox-TH 部署指南

> **架構摘要**：開發在 Spark-5277，Mac Mini 客戶端只跑 Docker 容器，不放置原始碼。
>
> 版本：v1.0.0 | 最後更新：2026-06-12

---

## 目錄

1. [上線前準備工作](#1-上線前準備工作)
2. [上線演練（預習）](#2-上線演練預習)
3. [上線當天流程](#3-上線當天流程)
4. [日常更新流程](#4-日常更新流程)
5. [斷網應變](#5-斷網應變)

---

## 1. 上線前準備工作

這些是 **現在就該做** 的事，不要等到上線當天。

### 1.1 Container Registry 準備

選擇一個 registry，把你的 Docker images 存到那裡。

| 選項 | 優點 | 操作 |
|------|------|------|
| **GitHub Container Registry** (推薦) | 跟 repo 同帳號，免費 | `ghcr.io/danielchung520/aibox` |
| **Docker Hub** | 最常見 | `docker.io/yourname/aibox` |
| **自建 Harbor** | 客戶內網適用 | 需額外維護 |

以 GitHub Container Registry 為例：

```bash
# 1. 先在 GitHub 產生 Personal Access Token（classic，勾 read:packages, write:packages）
# 2. 在你的 Spark-5277 登入
echo $GH_PAT | docker login ghcr.io -u DanielChung520 --password-stdin
```

### 1.2 修復 Dockerfile（關鍵）

**`docker/Dockerfile.python`** 需要修正，讓 production image **不依賴 bind mount volume**：

```dockerfile
# ── 現狀（第 42-43 行）：被註解掉了 ──
# COPY ai-services/ /app/

# ── 必須改成 production 模式 ──
COPY ai-services/ /app/
```

同樣地 **`docker/Dockerfile.rust-api`** 的 frontend dist 也需要打包進 image：

```dockerfile
# 在 Stage 2 Runtime 加入（在第 58 行之後）
COPY dist/ /app/dist/
```

並在 `docker-compose.yml` 中移除 production 環境的 volume mount：

```yaml
# ⚠️ production 時要移除或註解掉這個 volume
# volumes:
#   - ../ai-services:/app      ← 開發用的 hot-reload
#   - ../dist:/app/dist        ← 開發用的前端檔案
```

> **現在就先改好**，這樣你的 Spark-5277 也能用 production mode 測試。

### 1.3 建立 Image Tag 腳本

建立 `docker/push-images.sh`：

```bash
#!/bin/bash
set -e

REGISTRY="ghcr.io/danielchung520"
TAG="${1:-latest}"

echo "=== Building & Pushing AIBox-TH images (tag: $TAG) ==="

# Build Rust API
docker build -f docker/Dockerfile.rust-api \
  -t "$REGISTRY/aibox-rust-api:$TAG" .
docker push "$REGISTRY/aibox-rust-api:$TAG"

# Build Python base
docker build -f docker/Dockerfile.python \
  -t "$REGISTRY/aibox-python-base:$TAG" .
docker push "$REGISTRY/aibox-python-base:$TAG"

echo "✅ All images pushed: $TAG"
```

### 1.4 建立 Mac Mini 部署腳本

在專案根目錄建立 `deploy-macmini.sh`（這個檔案會 push 到 registry，不會留在 Mac Mini 上，僅供參考流程）：

```bash
#!/bin/bash
# ===================================================
# Mac Mini 部署腳本 — 在客戶端執行
# 使用方式：ssh user@macmini 'bash -s' < deploy-macmini.sh
# ===================================================
set -e

REGISTRY="ghcr.io/danielchung520"
TAG="${1:-latest}"
ENV_FILE="${2:-/etc/aibox/prod.env}"

echo "=== Deploying AIBox-TH $TAG to Mac Mini ==="

# 1. 登入 registry
echo "$GH_PAT" | docker login ghcr.io -u DanielChung520 --password-stdin

# 2. Pull images
docker pull "$REGISTRY/aibox-rust-api:$TAG"
docker pull "$REGISTRY/aibox-python-base:$TAG"

# 3. 啟動服務（使用外部的 env file）
docker compose \
  --env-file "$ENV_FILE" \
  -f docker-compose.infra.yml \
  -f docker/docker-compose.yml \
  up -d

# 4. 健康檢查
echo "Waiting for services..."
sleep 5
curl -sf http://localhost:6500/health && echo "✅ API Healthy"
```

### 1.5 環境變數管理

在 Mac Mini 上建立 `/etc/aibox/prod.env`（權限 600）：

```bash
# Mac Mini 上執行（手動 SSH 進去）
sudo mkdir -p /etc/aibox
sudo tee /etc/aibox/prod.env << 'EOF'
ARANGODB_PASSWORD=abc_desktop_2026
ARANGODB_DATABASE=aibox_th
JWT_SECRET=change-this-to-random-string
VITE_API_URL=https://your-domain.com
EOF
sudo chmod 600 /etc/aibox/prod.env
```

### 1.6 備份策略

上線前先確認 Mac Mini 的備份機制：

```bash
# 每天凌晨備份 ArangoDB
0 3 * * * docker exec arangodb arangodump \
  --output-directory /backups/$(date +\%Y\%m\%d) \
  --overwrite true

# 備份保留 7 天
0 5 * * * find /backups -mtime +7 -delete
```

---

## 2. 上線演練（預習）

> **目的**：在上線日前，完整模擬一次所有步驟，確保流程通順、沒有遺漏。

### 2.1 演練時間點

建議排程 3 次演練：

| 次數 | 時機 | 目標 |
|------|------|------|
| **T-14 天** | 上線前兩週 | 流程確認，補腳本漏洞 |
| **T-7 天** | 上線前一週 | 完整 Run Through |
| **T-1 天** | 上線前一天 | 最終確認，無延遲 |

### 2.2 演練腳本（在你的 Spark-5277 上模擬）

```bash
# ─── 演練開始 ───

# Step 1: Build production images
echo "=== Step 1: Build ==="
docker build -f docker/Dockerfile.rust-api -t aibox-rust-api:test .
docker build -f docker/Dockerfile.python -t aibox-python-base:test .

# Step 2: Push to registry（模擬）
echo "=== Step 2: Tag & Push ==="
docker tag aibox-rust-api:test ghcr.io/danielchung520/aibox-rust-api:test
docker push ghcr.io/danielchung520/aibox-rust-api:test

# Step 3: 模擬 Mac Mini 的乾淨環境
echo "=== Step 3: Simulate clean deploy ==="
# 先停掉所有 container
docker compose -f docker-compose.infra.yml -f docker/docker-compose.yml down

# 用 production mode 重啟（不使用 volume mount）
docker compose \
  --env-file docker/.env.ubuntu \
  -f docker-compose.infra.yml \
  -f docker/docker-compose.yml \
  up -d

# Step 4: 驗證
echo "=== Step 4: Verify ==="
sleep 5
curl -s http://localhost:6500/health | jq .
curl -s http://localhost:8001/docs > /dev/null && echo "✅ AITask reachable"
curl -s http://localhost:8011/docs > /dev/null && echo "✅ Unified Agents reachable"

# Step 5: 測試重新部署（模擬更新）
echo "=== Step 5: Simulate update ==="
# 修改一點 Rust 程式碼，重新 build
# 然後測試 pull + restart 流程
```

### 2.3 演練檢查清單

```
□ 從 Spark-5277 push images → registry 成功
□ 從 Mac Mini（模擬）pull images 成功
□ 所有 container 正常啟動
□ /health 回傳 healthy
□ 所有 AI 服務 /docs 可達
□ ArangoDB 資料可讀寫
□ Qdrant vector search 正常
□ 登入流程正常（JWT）
□ 前端 Desktop app 連上 API 正常
□ 環境變數正確載入（無 hardcoded 值在 image 內）
□ Image 內沒有原始碼洩漏問題
□  docker compose down → up 重啟不遺失資料
```

---

## 3. 上線當天流程

### 3.1 在 Spark-5277（最後一次 build）

```bash
# 1. 確認程式碼是最終版本
git status
git log --oneline -5

# 2. Build production images
docker build -f docker/Dockerfile.rust-api \
  -t ghcr.io/danielchung520/aibox-rust-api:latest .
docker build -f docker/Dockerfile.python \
  -t ghcr.io/danielchung520/aibox-python-base:latest .

# 3. Push 到 registry
docker push ghcr.io/danielchung520/aibox-rust-api:latest
docker push ghcr.io/danielchung520/aibox-python-base:latest

# 4. 同時也保留版本標籤（便於回滾）
DATE_TAG=$(date +%Y%m%d)
docker tag ghcr.io/danielchung520/aibox-rust-api:latest \
  ghcr.io/danielchung520/aibox-rust-api:$DATE_TAG
docker push ghcr.io/danielchung520/aibox-rust-api:$DATE_TAG
docker tag ghcr.io/danielchung520/aibox-python-base:latest \
  ghcr.io/danielchung520/aibox-python-base:$DATE_TAG
docker push ghcr.io/danielchung520/aibox-python-base:$DATE_TAG
```

### 3.2 在 Mac Mini（第一次部署）

```bash
# 登入 Mac Mini
ssh user@macmini-ip

# 1. 確認 Docker 已安裝
docker --version && docker compose version

# 2. 建立環境變數檔案（手動輸入，不要複製貼上 .env）
sudo mkdir -p /etc/aibox
sudo vi /etc/aibox/prod.env
# 貼上生產環境的變數

# 3. 設定正確的權限
sudo chmod 600 /etc/aibox/prod.env
sudo chown root:root /etc/aibox/prod.env

# 4. 登入 registry
echo $GH_PAT | docker login ghcr.io -u DanielChung520 --password-stdin

# 5. 把 docker-compose 檔案複製到 Mac Mini
# 選項 A：從 Spark-5277 scp 過去
scp docker-compose.infra.yml docker/docker-compose.yml \
  docker/.env.ubuntu user@macmini:~

# 選項 B：直接從 GitHub 下載（如果 repo 是 public）
curl -O https://raw.githubusercontent.com/DanielChung520/aibox-th/main/docker-compose.infra.yml
curl -O https://raw.githubusercontent.com/DanielChung520/aibox-th/main/docker/docker-compose.yml

# 6. 啟動所有服務
docker compose \
  --env-file /etc/aibox/prod.env \
  -f docker-compose.infra.yml \
  -f docker/docker-compose.yml \
  up -d

# 7. 健康檢查
sleep 10
curl -s http://localhost:6500/health
# 預期回應：{"status":"healthy","services":{"arangodb":true,"qdrant":true}}

# 8. 確認所有 container 都在 running
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### 3.3 驗證清單（上線當天）

```
□ /health 回傳 {"status":"healthy"}
□ ArangoDB connectable（curl :8529/_api/version）
□ Qdrant connectable（curl :6333/collections）
□ API 可正常登入（POST /api/v1/auth/login）
□ Desktop App 可連上 API
   ├── □ 本機相同 Wi-Fi 測試
   └── □ 遠端連線測試（如果 API 有公開）
□ 所有 AI 服務正常回應
□ 環境變數無洩漏
□ Container 無異常重啟
```

---

## 4. 日常更新流程

### 4.1 修改程式碼並發布

```bash
# Spark-5277 上：

# 1. 改 code，本地測試
docker compose up -d          # 用 dev mode 測試
# ... 確認功能正常 ...

# 2. Build production images
docker build -f docker/Dockerfile.rust-api \
  -t ghcr.io/danielchung520/aibox-rust-api:latest .
docker build -f docker/Dockerfile.python \
  -t ghcr.io/danielchung520/aibox-python-base:latest .

# 3. Tag 版本（便於回滾）
DATE_TAG=$(date +%Y%m%d-%H%M)
docker tag ghcr.io/danielchung520/aibox-rust-api:latest \
  ghcr.io/danielchung520/aibox-rust-api:$DATE_TAG
docker tag ghcr.io/danielchung520/aibox-python-base:latest \
  ghcr.io/danielchung520/aibox-python-base:$DATE_TAG

# 4. Push 全部
docker push ghcr.io/danielchung520/aibox-rust-api --all-tags
docker push ghcr.io/danielchung520/aibox-python-base --all-tags
```

### 4.2 部署到 Mac Mini

```bash
# Spark-5277 上執行 SSH 指令到 Mac Mini
ssh user@macmini '
  # Pull 最新 images
  docker pull ghcr.io/danielchung520/aibox-rust-api:latest
  docker pull ghcr.io/danielchung520/aibox-python-base:latest

  # 重啟服務（不中斷 infrastucture）
  docker compose \
    --env-file /etc/aibox/prod.env \
    -f docker-compose.infra.yml \
    -f docker/docker-compose.yml \
    up -d --no-deps rust-api aitask unified_agents mcp_tools aiq_agent skills_rag
'
```

### 4.3 回滾流程

```bash
# 如果有問題，回到上一個版本
ssh user@macmini '
  # 例如回到 20260611 的版本
  docker pull ghcr.io/danielchung520/aibox-rust-api:20260611
  docker pull ghcr.io/danielchung520/aibox-python-base:20260611

  # 重新 tag 成 latest
  docker tag ghcr.io/danielchung520/aibox-rust-api:20260611 \
    ghcr.io/danielchung520/aibox-rust-api:latest
  docker tag ghcr.io/danielchung520/aibox-python-base:20260611 \
    ghcr.io/danielchung520/aibox-python-base:latest

  # 重啟服務
  docker compose ... up -d --no-deps rust-api aitask ...
'
```

---

## 5. 斷網應變

如果 Mac Mini 在客戶內網無法連 Docker Registry：

### 方法 A：預先下載 Images

```bash
# Spark-5277 上
docker save ghcr.io/danielchung520/aibox-rust-api:latest | gzip > aibox-images.tar.gz
docker save ghcr.io/danielchung520/aibox-python-base:latest | gzip >> aibox-images.tar.gz

# 用 USB 或區域網路複製到 Mac Mini
scp aibox-images.tar.gz user@macmini:~

# Mac Mini 上
docker load < aibox-images.tar.gz
```

### 方法 B：區域內自建 Registry

在客戶內網的某台機器上跑一個 local registry，Mac Mini 從 local registry pull：

```bash
# 內網 registry 機器
docker run -d -p 5000:5000 --name registry registry:2

# Spark-5277 上 push 到 local registry
docker tag aibox-rust-api:latest internal-registry:5000/aibox-rust-api:latest
docker push internal-registry:5000/aibox-rust-api:latest

# Mac Mini 從 local registry pull
docker pull internal-registry:5000/aibox-rust-api:latest
```

---

## 附錄 A：需修改的檔案一覽

上線前要改的檔案：

| 檔案 | 修改內容 | 重要性 |
|------|---------|--------|
| `docker/Dockerfile.python` | 取消註解 `COPY ai-services/ /app/` | 🔴 必須 |
| `docker/Dockerfile.rust-api` | 加入 `COPY dist/ /app/dist/` | 🔴 必須 |
| `docker/docker-compose.yml` | Python services 移除 `volumes:` bind mount | 🔴 必須 |
| - | 新增 `docker/push-images.sh` | 🟡 建議 |
| - | 新增 `deploy-macmini.sh` | 🟡 建議 |

## 附錄 B：演練時程建議

```
T-14 天 ── 第一次演練（流程驗證）
  □ 確認 Dockerfile 修改完成
  □ 確認 registry push/pull 正常
  □ 模擬 Mac Mini 部署
  □ 確認所有服務正常啟動
  └── 修正腳本問題

T-7 天 ── 第二次演練（完整流程）
  □ 完整跑一次上線流程
  □ 確認回滾流程
  □ 確認備份機制
  └── 補遺漏

T-1 天 ── 最終確認
  □ 確認程式碼凍結
  □ 確認 Docker images 已 push
  □ 確認 Mac Mini 硬體狀態
  □ 確認網路連通性
  └── 安心睡覺

T-Day  ── 上線
  □ 照著 [3. 上線當天流程] 執行
```
