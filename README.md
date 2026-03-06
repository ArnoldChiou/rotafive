# RotaFive - Fair Dispatch Freelance Marketplace

RotaFive 是一個主打「公平輪值配對」的自由工作者媒合平台原型。
有別於傳統客戶發包、接案者比價競爭的模式，RotaFive 採用類似 Uber 的演算法派單系統：當客戶提出需求，系統會即時篩選出符合技能條件的空閒接案者，並根據「最久沒接到案子（`last_assigned_at`）」優先的原則，精準挑選出前 5 名最適合的人選供客戶挑選。

---

## 🛠 技術棧 (Tech Stack)

此專案為前後端分離架構，使用了以下現代化技術：

### 前端 (Frontend)
- **核心框架**：Vue 3 (Composition API)
- **路由管理**：Vue Router 4
- **建置工具**：Vite
- **樣式系統**：Tailwind CSS v4 + DaisyUI v5
- **圖示庫**：Lucide-Vue-Next
- **即時通訊**：原生 `WebSocket` API 與 Fetch API

### 後端 (Backend)
- **核心框架**：FastAPI (Python)
- **伺服器**：Uvicorn (`uvicorn[standard]`) / Gunicorn
- **非同步資料庫驅動程式**：`asyncpg`
- **資料驗證**：Pydantic
- **身份驗證**：JWT (`python-jose`) + bcrypt 密碼 hash
- **即時推播 / 快取**：Redis (Pub/Sub) + FastAPI WebSockets

### 資料庫 (Database)
- **關聯式資料庫**：PostgreSQL 15
- **容器化部署**：Docker & Docker Compose

---

## 🔐 身份驗證機制 (JWT Auth & RBAC)

### 使用者角色

| 角色 | 可使用的功能 |
|---|---|
| **Client（客戶）** | 發佈需求、配對 Freelancer、送出邀請 |
| **Freelancer（接案者）** | 查看個人邀請信箱、接受/拒絕邀請 |

### 驗證流程
1. 在 `/register` 選擇角色並建立帳號（Freelancer 需填姓名與技能）
2. 在 `/login` 輸入 Email + 密碼，取得 **JWT Token**
3. Token 儲存於 **`sessionStorage`**（每個分頁獨立登入，支援同時 Client + Freelancer 測試）
4. 後續所有 API 請求自動附上 `Authorization: Bearer <token>` header
5. 後端 FastAPI 以 `get_current_user` dependency 驗證 token，並依 role 決定存取權限

### API 保護規則
- `GET /api/match` — 僅 **client** 可呼叫；自動將 `client_id` 記入 project
- `GET /api/invitations` — **client** 看自己發出的邀請；**freelancer** 看自己收到的邀請
- `POST /api/invite`, `POST /api/respond-invitation` — 登入即可使用

### 環境變數（需加入 `backend/.env`）
```bash
JWT_SECRET_KEY=your-very-long-random-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

---

## ⚙️ 核心邏輯 (The "RotaFive" Algorithm)

系統的核心配對演算法完全實作於 PostgreSQL 資料庫的查詢語法中（透過 FastAPI 介接）。

當客戶發布需求時，演算法會進行以下四個步驟：
1. **技能篩選 (Skills Match)**：使用 PostgreSQL 的 JSONB 包含運算子 `@>` ，精準篩選出具備客戶所需技能標籤的人。
2. **排除工作中 (Availability Check)**：過濾掉當前系統狀態 `status = 'working'` 的人員。
3. **公平排序 (Fair Rotation)**：按照接案者的 `last_assigned_at` (上次派單時間) 進行升冪 (ASC) 排序。越久沒接到案子的人會排在越前面。
4. **精選名單 (Top 5 Candidates)**：使用 `LIMIT 5` 提取最前面的 5 位最佳候選人。

當客戶**決定指派 (Hire)** 其中一名候選人時：
- 系統會透過 Transaction 更新該員狀態為 `working`。
- 系統會將該員的 `last_assigned_at` 更新為當下時間 (`CURRENT_TIMESTAMP`)。這會確保他在完成工作退回為 `idle` 狀態時，會自動排到整個派單佇列的「最後方」。

---

## 🚀 系統啟動與使用方法

要能在本機完整運行 RotaFive，您需要同時啟動「資料庫」、「後端 API」以及「前端網頁」。

### 步驟一：啟動 PostgreSQL 資料庫 (Docker)
1. 請確認您的電腦已經安裝並啟動了 **Docker Desktop**。
2. 開啟終端機 (PowerShell / Command Prompt)，切換到專案根目錄：
   ```bash
   cd c:\RotaFive
   ```
3. 執行 Docker Compose 指令啟動資料庫背景服務（會自動載入 `init.sql` 建立資料表）：
   ```bash
   docker compose up -d
   ```

### 步驟二：啟動 FastAPI 後端伺服器
1. 開啟一個**全新**的終端機視窗。
2. 切換到 `backend` 目錄並啟動 Python 虛擬環境：
   ```bash
   cd c:\RotaFive\backend
   .\.venv\Scripts\Activate.ps1
   ```
3. 啟動 Uvicorn 伺服器，並指定運行在 8080 Port：
   ```bash
   uvicorn main:app --reload --port 8080
   ```
   *(請保持這個終端機視窗開啟，後端 API 將持續運行在 `http://localhost:8080`)*

> **💡 補充：寫入初始測試資料**
> 如果您是第一次建置，且資料庫內空無一物，可以在這個環境下執行：
> ```bash
> python seed.py
> ```
> 系統會自動幫您創造 10 筆測試用的自由工作者資料進資料庫！

### 步驟三：啟動 Vue 前端網頁
1. 再次開啟一個**全新**的終端機視窗。
2. 切換到專案根目錄：
   ```bash
   cd c:\RotaFive
   ```
3. 啟動 Vite 開發伺服器：
   ```bash
   npm run dev
   ```
4. 在終端機中會出現一個本地網址（通常為 `http://localhost:5173`），請按住 `Ctrl` 點擊網址，或複製到您的瀏覽器中開啟。

---

## 網頁操作流程

打開 `http://localhost:5173` 後，系統會自動導向登入頁面。

### 完整測試流程（兩個分頁同時跑）

**分頁 1（Client 角色）：**
1. 前往 `/register` → 選擇 **Client** → 填入 Email + 密碼 → 建立帳號
2. 登入後進入主頁，看到 **Client Match** 和 **Rotation Queue** 分頁
3. 輸入專案名稱，選擇技能標籤（例如 `Vue`, `JavaScript`）
4. 點擊 **"Find My Top 5 Matches"** → 看到候選人列表
5. 點 **"Send Job Invite"** 邀請 Freelancer

**分頁 2（Freelancer 角色）：**
1. 同樣前往 `http://localhost:5173`（每個分頁獨立 session，可同時登不同帳號）
2. 前往 `/register` → 選擇 **Freelancer** → 填姓名、選技能 → 建立帳號
3. 登入後看到 **Freelancer 邀請信箱**
4. 點 **Accept** 接受派案 / **Decline** 拒絕
5. **分頁 1 的 Client 視圖會在 3 秒內自動更新**（無需重整）

### 各視圖說明

1. **Client Match（客戶端視圖）**
   - 選技能標籤後發案，呼叫 RotaFive 演算法
   - 顯示前 5 名最符合且最久等待的候選人
   - 可送出邀請、並即時反映 Freelancer 的回應

2. **Rotation Queue（管理端視圖）**
   - 即時顯示整個資料庫的派單佇列狀態
   - 可觀察接案者從 `Idle` → `Working` 的狀態流轉

3. **Freelancer 邀請信箱（Freelancer 視圖）**
   - 只有登入為 Freelancer 的帳號才看到
   - 列出所有寄來的邀請，可接受或拒絕

---

## 🔍 如何自行查詢資料庫驗證資料？

如果您想要直接進入 PostgreSQL 資料庫一探究竟，可以直接透過 Docker 執行 SQL 語法：

1. 開啟終端機。
2. 使用 `docker exec` 進入資料庫容器使用 `psql` 指令：
   ```bash
   docker exec -it rotafive_db psql -U postgres -d rotafive
   ```
3. 進入 `psql` 互動介面後，您可以輸入 SQL 查詢，例如查看所有自由工作者的狀態：
   ```sql
   SELECT id, name, skills, status, last_assigned_at FROM freelancers ORDER BY last_assigned_at ASC;
   ```
4. 查詢完畢後，輸入 `\q` 即可離開資料庫介面。

---

## 🧹 常用資料庫指令 (Useful Database Commands)

如果您在測試過程中需要清空所有指派紀錄、專案，並讓所有接案者恢復為 `idle` 狀態，可以打開終端機，執行以下可以直接在外層（不需進入 psql）運行的 Docker 指令：

**1. 清空專案紀錄 (連帶清空 dispatch_logs 派單紀錄)1**
```bash
docker exec rotafive_db psql -U postgres -d rotafive -c "TRUNCATE TABLE projects RESTART IDENTITY CASCADE;"
```

**2. 將所有接案者狀態強制重設為閒置中**
```bash
docker exec rotafive_db psql -U postgres -d rotafive -c "UPDATE freelancers SET status = 'idle';"
```

**3. 確認目前接案者的狀態分佈**
```bash
docker exec rotafive_db psql -U postgres -d rotafive -c "SELECT status, count(*) FROM freelancers GROUP BY status;"
```

---

## 🚢 生產環境部署 (Production Deployment)

### 相關建立的檔案

| 檔案 | 說明 |
|------|------|
| `backend/Dockerfile.prod` | 後端生產鏡像 (Python 3.11 slim + Gunicorn + Uvicorn workers) |
| `Dockerfile.prod` | 前端生產鏡像 (Node 建置 → Nginx Alpine 服務) |
| `nginx.conf` | Nginx 配置 (Vue Router history mode + 反向代理 `/api/`) |
| `.github/workflows/main.yml` | GitHub Actions CI/CD 工作流程 |

### 手動建立 Docker 映像（本機測試）

```bash
# 後端
docker build -f backend/Dockerfile.prod -t rotafive-backend:local ./backend

# 前端
docker build -f Dockerfile.prod -t rotafive-frontend:local .
```

### GitHub Actions 自動部署

每次 Push 至 `main` Branch 時，GitHub Actions 自動：
1. 建置 Backend 映像並推送到 GHCR (`ghcr.io/<owner>/rotafive-backend`)
2. 建置 Frontend 映像並推送到 GHCR (`ghcr.io/<owner>/rotafive-frontend`)
3. 每次推送都會產生兩個 Tag：`latest` 和 `<commit-SHA>`

> **💡 使用 VITE\_API\_BASE\_URL**
> 如果您的 API 不在同一網域下，可以在 GitHub 的 Repository Settings → Variables 中設定 `VITE_API_BASE_URL`（例如 `https://api.myserver.com`），GitHub Actions 會在建置時自動注入。
