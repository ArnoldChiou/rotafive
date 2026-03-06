# RotaFive — Project Context Document
> 此檔案供 LLM 快速理解本專案的全貌，包含架構、功能、技術與資料流。

---

## 專案概述

**RotaFive** 是一個自由工作者「公平輪值配對」媒合平台原型。
核心理念：當客戶提出需求，系統不讓接案者競標，而是主動根據「最久沒接到案子的人優先」的公平演算法，自動挑選最符合技能的前 5 名候選人供客戶指派。

---

## 技術棧

| 層 | 技術 |
|---|---|
| **Frontend** | Vue 3 (Composition API) + Vite + Tailwind CSS v4 + DaisyUI v5 + Lucide-Vue-Next |
| **Backend** | FastAPI (Python) + Uvicorn / Gunicorn |
| **Database** | PostgreSQL 15 (`asyncpg` driver) |
| **Cache / Real-time** | Redis (`redis-py`) |
| **Containerization** | Docker + Docker Compose |
| **CI/CD** | GitHub Actions → GHCR (GitHub Container Registry) |

---

## 目錄結構

```
RotaFive/
├── backend/
│   ├── main.py              # FastAPI 所有 API 端點
│   ├── seed.py              # 初始測試資料寫入腳本
│   ├── requirements.txt     # Python 依賴
│   ├── Dockerfile.prod      # 後端生產 Dockerfile (non-root + Gunicorn)
│   └── .env.example         # 環境變數範本
│
├── src/
│   ├── main.js              # Vue 入口
│   ├── App.vue              # 根元件，含 Navbar + View 切換
│   ├── store.js             # 全域狀態 + API 呼叫集中管理 (reactive store)
│   ├── style.css            # Global CSS (Tailwind + DaisyUI theme override)
│   └── components/
│       ├── ClientView.vue            # 客戶端：發案、技能選擇、配對結果、邀請
│       ├── QueueView.vue             # 管理端：全部接案者輪值佇列 (5秒輪詢)
│       └── FreelancerSimulationView.vue  # 接案者模擬信箱 (Accept/Decline)
│
├── init.sql                 # DB 建表：freelancers, projects, dispatch_logs
├── docker-compose.yml       # 開發環境：PostgreSQL + Redis (讀 backend/.env)
├── Dockerfile.prod          # 前端生產 Dockerfile (Node build → Nginx Alpine)
├── nginx.conf               # Nginx：Vue Router history mode + /api/ 反向代理
├── .github/workflows/main.yml  # GitHub Actions CI/CD (push to main → GHCR)
├── .gitignore               # 排除 .env, .venv, node_modules, *.session.sql 等
└── CONTEXT.md               # 本檔案
```

---

## 資料庫 Schema (init.sql)

```sql
-- 接案者
CREATE TABLE freelancers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    skills JSONB,                        -- e.g. ["Vue", "Python"]
    rating DECIMAL(3,2) DEFAULT 5.0,
    status VARCHAR(20) DEFAULT 'idle',   -- idle | working | cooling
    last_assigned_at TIMESTAMP DEFAULT '1970-01-01 00:00:00'
);

-- 案件
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    client_id INT,
    title VARCHAR(200),
    required_skills JSONB,
    status VARCHAR(20) DEFAULT 'matching' -- matching | active | completed
);

-- 派單紀錄
CREATE TABLE dispatch_logs (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES projects(id),
    freelancer_id INT REFERENCES freelancers(id),
    status VARCHAR(20) DEFAULT 'invited',  -- matched | invited | accepted | declined
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Backend API 端點 (backend/main.py)

| Method | Path | 說明 |
|--------|------|------|
| `GET` | `/api/freelancers` | 返回全部接案者，附加 Redis cooldown 資訊 (`cooling`, `cooldown_ttl`) |
| `GET` | `/api/match?skills=Vue,Python` | RotaFive 核心：建立 project，找出前 5 名 idle + 非 cooldown 的接案者，在 dispatch_logs 寫入 `matched` 狀態 |
| `GET` | `/api/invitations` | 返回所有狀態為 `invited` 的派單紀錄（供接案者信箱用）|
| `POST` | `/api/invite` | 客戶明確邀請某人：將 dispatch_logs 從 `matched` 更新為 `invited` |
| `POST` | `/api/respond-invitation` | 接案者 accept/decline：accept → 設為 `working`；decline → Redis 設 30 分鐘 cooldown，自動找下一位補位（寫入 `matched`）|
| `POST` | `/api/reset-cooling` | 原型測試用：將接案者重設為 `idle` |
| `POST` | `/api/select` | 向下相容舊版，導向 `respond-invitation` accept 邏輯 |

---

## 核心 RotaFive 演算法說明

**配對邏輯（SQL 查詢，在 `/api/match`）：**
1. `status = 'idle'`：排除正在工作的人
2. `id NOT IN (cooldown 清單)`：排除 Redis 中有 cooldown key 的人
3. `skills @> $1::jsonb`：JSONB 包含運算子過濾技能（可選）
4. `ORDER BY last_assigned_at ASC`：最久沒接案排前面
5. `LIMIT 5`：取前 5 名

**邀請流程（On-demand，非自動）：**
- `/api/match` 只做「配對」，結果放到前端顯示
- 客戶手動點「Send Job Invite」才呼叫 `/api/invite` 送出邀請
- 接案者在 Freelancer Mock 頁面 Accept/Decline

**Decline 遞補流程：**
1. `/api/respond-invitation` 收到 `decline`
2. Redis 設 `cooldown:{freelancer_id}` key，TTL = 1800 秒（30 分鐘）
3. 查找下一位符合條件的 idle 接案者（排除已 dispatch 過此案 + 排除 cooldown 中的人）
4. 在 `dispatch_logs` 寫入 `matched`，回傳給前端
5. 前端透過動畫滑出舊人、滑入新人

**跨分頁即時同步：**
- 使用瀏覽器原生 `BroadcastChannel('rotafive_sync')`
- 事件類型：`DECLINED_REPLACED`、`DECLINED_NO_REPLACEMENT`、`ACCEPTED`

---

## 前端元件說明

### `store.js`
- `reactive` store，集中管理 `freelancers` 陣列與所有 API 呼叫
- `API_BASE_URL = 'http://localhost:8080/api'`（可用 `VITE_API_BASE_URL` 環境變數覆寫）
- 主要方法：`fetchFreelancers()`, `getMatches()`, `inviteFreelancer()`, `selectFreelancer()`, `declineInvitation()`, `fetchInvitations()`

### `ClientView.vue`
- 輸入 Job Title + 選擇技能 → 呼叫 `getMatches()`
- 結果顯示 5 張候選人卡片，每張有：
  - **Send Job Invite** 按鈕（呼叫 `/api/invite`）
  - 邀請後顯示 "Waiting for response..."
  - **Simulate Decline** 按鈕（快速測試遞補）
- 監聽 `BroadcastChannel` 做跨分頁即時更新

### `QueueView.vue`
- 每 5 秒輪詢 `/api/freelancers`
- 顯示排序後的佇列表格（idle 依照 last_assigned_at 排序，working 排最後）
- 狀態 Badge：`Idle`（綠）/ `Working`（橘閃）/ `Cooling`（藍 + 倒數計時）

### `FreelancerSimulationView.vue`
- 每 3 秒輪詢 `/api/invitations`
- 顯示所有 `invited` 狀態的邀請，可 Accept 或 Decline

---

## 環境變數

| 變數 | 位置 | 說明 |
|------|------|------|
| `DATABASE_URL` | `backend/.env` | PostgreSQL 連線字串 |
| `POSTGRES_PASSWORD` | `backend/.env` | Docker Compose 啟動 DB 用 |
| `REDIS_URL` | `backend/.env` | Redis 連線字串 |
| `VITE_API_BASE_URL` | Build arg / GitHub Vars | 前端 API base URL（生產環境用）|

---

## Redis 使用方式

| Key Pattern | TTL | 值 | 用途 |
|---|---|---|---|
| `cooldown:{freelancer_id}` | 1800秒（30分鐘）| project_id | 記錄某接案者因拒絕而進入 cooling 狀態 |

---

## CI/CD 流程

**觸發條件**：`git push` 到 `main` branch

**步驟**：
1. Checkout 程式碼
2. 強制轉小寫 GitHub Owner 名稱（GHCR 要求全小寫）
3. Docker Buildx 設定
4. 登入 GHCR
5. 建置並推送 **Backend** image → `ghcr.io/arnoldchiou/rotafive-backend:latest` + `:sha`
6. 建置並推送 **Frontend** image → `ghcr.io/arnoldchiou/rotafive-frontend:latest` + `:sha`（含 `VITE_API_BASE_URL` build arg）

---

## 已知設計決策 & 注意事項

1. **CORS**：目前設定 `allow_origins=["*"]`，生產環境應限制為特定網域
2. **Cooldown 儲存**：使用 Redis TTL 實現，重啟 Redis 後 cooldown 會消失（接受這個 tradeoff）
3. **dispatch_logs `matched` 狀態**：客戶配對後先用 `matched` 預佔位置，客戶實際送出邀請後才改 `invited`，防止同一人被配對兩次
4. **接案者 status 欄位**：DB 中只有 `idle`/`working`，`cooling` 狀態是由 Redis 動態覆蓋，不寫回 DB
5. **BroadcastChannel**：只在同一瀏覽器的不同分頁之間有效，不跨裝置
