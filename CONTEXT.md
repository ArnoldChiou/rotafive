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
| **Frontend** | Vue 3 (Composition API) + Vue Router 4 + Vite + Tailwind CSS v4 + DaisyUI v5 + Lucide-Vue-Next |
| **Backend** | FastAPI (Python) + Uvicorn / Gunicorn |
| **Auth** | JWT (`python-jose`) + bcrypt (密碼 hash) + `python-multipart` (OAuth2 form) |
| **Database** | PostgreSQL 15 (`asyncpg` driver) |
| **Cache / Real-time** | Redis (`redis-py`) |
| **Containerization** | Docker + Docker Compose |
| **CI/CD** | GitHub Actions → GHCR (GitHub Container Registry) |

---

## 目錄結構

```
RotaFive/
├── backend/
│   ├── main.py              # FastAPI 所有 API 端點 + 身份驗證整合
│   ├── auth.py              # JWT 建立/驗證、bcrypt hash、get_current_user dependency
│   ├── seed.py              # 初始測試資料寫入腳本（10 名接案者）
│   ├── requirements.txt     # Python 依賴
│   ├── Dockerfile.prod      # 後端生產 Dockerfile (non-root + Gunicorn)
│   └── .env.example         # 環境變數範本
│
├── src/
│   ├── main.js              # Vue 入口 (createApp + use(router))
│   ├── App.vue              # 根元件：Navbar（角色 badge + 登出）+ RouterView
│   ├── router.js            # Vue Router 路由設定 + 導航守衛
│   ├── store.js             # 全域狀態 + API 呼叫 + Auth 狀態管理 (reactive store)
│   ├── style.css            # Global CSS (Tailwind + DaisyUI theme override)
│   └── components/
│       ├── LoginView.vue             # 登入頁
│       ├── RegisterView.vue          # 註冊頁（含角色選擇 + freelancer 技能選擇）
│       ├── HomeView.vue              # 主頁，依角色決定顯示 Client/Queue/FreelancerMock
│       ├── ClientView.vue            # 客戶端：發案、技能選擇、配對結果、邀請
│       ├── QueueView.vue             # 管理端：全部接案者輪值佇列 (5秒輪詢)
│       └── FreelancerSimulationView.vue  # 接案者信箱 (Accept/Decline)
│
├── init.sql                 # DB 建表：users, freelancers, projects, dispatch_logs
├── docker-compose.yml       # 開發環境：PostgreSQL + Redis (讀 backend/.env)
├── Dockerfile.prod          # 前端生產 Dockerfile (Node build → Nginx Alpine)
├── nginx.conf               # Nginx：Vue Router history mode + /api/ 反向代理
├── .github/workflows/main.yml  # GitHub Actions CI/CD (push to main → GHCR)
├── .gitignore               # 排除 .env, .venv, node_modules, *.session.sql 等
├── README.md                # 使用說明（含啟動步驟、操作流程）
└── CONTEXT.md               # 本檔案
```

---

## 資料庫 Schema (init.sql)

```sql
-- 使用者帳號
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    role VARCHAR(20) NOT NULL,          -- 'client' | 'freelancer'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 接案者（與 users 關聯）
CREATE TABLE freelancers (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE SET NULL,  -- 可 NULL (seed 資料)
    name VARCHAR(100) NOT NULL,
    skills JSONB,                        -- e.g. ["Vue", "Python"]
    rating DECIMAL(3,2) DEFAULT 5.0,
    status VARCHAR(20) DEFAULT 'idle',   -- idle | working | cooling
    last_assigned_at TIMESTAMP DEFAULT '1970-01-01 00:00:00'
);

-- 案件
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    client_id INT REFERENCES users(id) ON DELETE SET NULL,  -- 發案的 client user
    title VARCHAR(200),
    required_skills JSONB,
    status VARCHAR(20) DEFAULT 'matching'  -- matching | active | completed
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

## 身份驗證機制 (JWT Auth & RBAC)

### 角色

| 角色 | 說明 |
|---|---|
| `client` | 發佈需求、配對 Freelancer、送出邀請 |
| `freelancer` | 查看個人邀請信箱、接受/拒絕邀請 |

### 驗證流程

1. `POST /api/auth/register` → 建立帳號，bcrypt hash 密碼，寫入 `users`；若為 freelancer 同時寫入 `freelancers`
2. `POST /api/auth/token` → OAuth2PasswordRequestForm 驗證，回傳 JWT
3. JWT 儲存於前端 **`sessionStorage`**（每個分頁獨立 session，支援兩role同時測試）
4. 所有 API 請求帶 `Authorization: Bearer <token>`
5. FastAPI dependency `get_current_user(token, db_pool)` 解密 JWT，從 `users` 取使用者資訊

### auth.py 主要方法

```python
hash_password(password: str) -> str          # bcrypt gensalt + hashpw
verify_password(plain, hashed) -> bool       # bcrypt checkpw
create_access_token(data: dict) -> str       # python-jose jwt.encode
get_current_user(token, db_pool) -> dict     # JWT decode + DB user lookup
```

---

## Backend API 端點 (backend/main.py)

### Auth 端點

| Method | Path | 說明 |
|--------|------|------|
| `POST` | `/api/auth/register` | 建立帳號（email, password, role, name?, skills?[]）|
| `POST` | `/api/auth/token` | 登入，回傳 JWT access_token |
| `GET` | `/api/auth/me` | 取得目前登入使用者資訊 |

### 核心業務端點

| Method | Path | 權限 | 說明 |
|--------|------|------|------|
| `GET` | `/api/freelancers` | 登入 | 返回全部接案者，附加 Redis cooldown 資訊 |
| `GET` | `/api/match?skills=Vue,Python` | **client only** | RotaFive 核心：建立 project（記錄 `client_id`），找出前 5 名候選人 |
| `GET` | `/api/invitations` | 角色依據 | client 看自己發出的；freelancer 看自己收到的 |
| `POST` | `/api/invite` | 登入 | 送出邀請：dispatch_logs `matched` → `invited` |
| `POST` | `/api/respond-invitation` | 登入 | accept/decline；decline 觸發 Redis cooldown + 自動遞補 |
| `POST` | `/api/reset-cooling` | 登入 | 原型測試用：接案者重設為 `idle` |

---

## 核心 RotaFive 演算法說明

**配對邏輯（SQL 查詢，在 `/api/match`）：**
1. `status = 'idle'`：排除正在工作的人
2. `id NOT IN (cooldown 清單)`：排除 Redis 中有 cooldown key 的人
3. `skills @> $1::jsonb`：JSONB 包含運算子過濾技能（可選）
4. `ORDER BY last_assigned_at ASC`：最久沒接案排前面
5. `LIMIT 5`：取前 5 名

**Decline 遞補流程：**
1. `/api/respond-invitation` 收到 `decline`
2. Redis 設 `cooldown:{freelancer_id}` key，TTL = 1800 秒（30 分鐘）
3. 查找下一位符合條件的 idle 接案者（排除已 dispatch 過此案 + 排除 cooldown 中的人）
4. 在 `dispatch_logs` 寫入 `matched`，回傳給前端
5. 前端透過動畫滑出舊人、滑入新人

---

## 前端架構說明

### 路由 (`router.js`)

| 路徑 | 元件 | 守衛規則 |
|---|---|---|
| `/login` | `LoginView` | 已登入則自動跳轉 `/` |
| `/register` | `RegisterView` | 已登入則自動跳轉 `/` |
| `/` | `HomeView` | 未登入則跳轉 `/login` |

### `store.js`

- `reactive` store，集中管理 `token`、`user`、`freelancers` 與所有 API 呼叫
- Token 使用 **`sessionStorage`**（各分頁獨立，可同時測試不同角色）
- Auth 方法：`login()`, `logout()`, `register()`, `fetchMe()`
- API 方法：`fetchFreelancers()`, `getMatches()`, `inviteFreelancer()`, `selectFreelancer()`, `declineInvitation()`, `fetchInvitations()`
- 所有 API 請求自動附上 `Authorization: Bearer <token>`

### `App.vue`
- Navbar 依 `store.token` 決定是否顯示（登入/登出 + 角色 badge）
- `<RouterView>` 渲染當前路由元件

### `HomeView.vue`
- 依 `store.user.role` 決定顯示的分頁：
  - `client`：Client Match + Rotation Queue
  - `freelancer`：只顯示 Freelancer 邀請信箱

### `ClientView.vue`
- 輸入 Job Title + 選擇技能 → 呼叫 `getMatches()`
- 顯示 5 張候選人卡片（Send Job Invite / Simulate Decline）
- 監聽 `BroadcastChannel('rotafive_sync')` 做跨分頁即時更新
- **3 秒 polling fallback**：輪詢 `/api/invitations` 偵測 Decline（跨 session 的備援機制）

### `RegisterView.vue`
- 選擇 Client 或 Freelancer 角色
- Freelancer 才顯示：**顯示名稱** + **技能 badge 選擇器**（20+ 技能可選）
- 成功後自動 login 跳轉 `/`

---

## 環境變數

| 變數 | 位置 | 說明 |
|------|------|------|
| `DATABASE_URL` | `backend/.env` | PostgreSQL 連線字串 |
| `POSTGRES_PASSWORD` | `backend/.env` | Docker Compose 啟動 DB 用 |
| `REDIS_URL` | `backend/.env` | Redis 連線字串 |
| `JWT_SECRET_KEY` | `backend/.env` | JWT 簽名密鑰（生產環境使用長隨機字串）|
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `backend/.env` | JWT 有效時間（預設 60 分鐘）|
| `VITE_API_BASE_URL` | Build arg / GitHub Vars | 前端 API base URL（生產環境用）|

---

## Redis 使用方式

| Key Pattern | TTL | 值 | 用途 |
|---|---|---|---|
| `cooldown:{freelancer_id}` | 1800秒（30分鐘）| project_id | 記錄某接案者因拒絕而進入 cooling 狀態 |

---

## 跨分頁即時同步

| 機制 | 說明 |
|---|---|
| **BroadcastChannel** | 同一瀏覽器不同分頁，發送 `DECLINED_REPLACED` / `DECLINED_NO_REPLACEMENT` / `ACCEPTED` 事件 |
| **Polling fallback** | ClientView 每 3 秒輪詢 `/api/invitations`，偵測被邀請的接案者是否已回應（跨 session 備援）|

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
5. **sessionStorage vs localStorage**：Token 改用 `sessionStorage`，每個分頁獨立 session，支援同時以 Client 和 Freelancer 身份測試
6. **passlib 相容性**：`passlib` 與 `bcrypt 4.x/5.x` 不相容（會卡死）。改用 bcrypt 原生套件直接呼叫 `bcrypt.hashpw`/`bcrypt.checkpw`
7. **seed.py**：`docker compose down -v` 後需重新執行 `python seed.py` 補充測試用接案者資料
