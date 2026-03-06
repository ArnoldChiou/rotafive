-- ===============================================
-- RotaFive Database Schema (with Auth)
-- ===============================================
-- 0. 使用者帳號表
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'client',
    -- 'client' or 'freelancer'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- 1. 接案者檔案：核心在於 last_assigned_at
CREATE TABLE freelancers (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE
    SET NULL,
        -- linked user account
        name VARCHAR(100) NOT NULL,
        skills JSONB,
        -- 存放標籤，如 ["Python", "Vue"]
        rating DECIMAL(3, 2) DEFAULT 5.0,
        status VARCHAR(20) DEFAULT 'idle',
        -- idle, working, cooling
        last_assigned_at TIMESTAMP DEFAULT '1970-01-01 00:00:00' -- 初始給一個極早的時間
);
-- 2. 案件表
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    client_id INT REFERENCES users(id) ON DELETE
    SET NULL,
        -- linked client user
        title VARCHAR(200),
        required_skills JSONB,
        status VARCHAR(20) DEFAULT 'matching' -- matching, active, completed
);
-- 3. 派單紀錄表：記錄系統每次「選中的 5 個人」
CREATE TABLE dispatch_logs (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES projects(id),
    freelancer_id INT REFERENCES freelancers(id),
    status VARCHAR(20) DEFAULT 'invited',
    -- matched, invited, accepted, declined, expired
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);