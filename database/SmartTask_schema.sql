-- SmartTask database schema
-- SQLite 3.x
-- Enable foreign-key enforcement on every DB connection.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    email         VARCHAR(255) NOT NULL COLLATE NOCASE UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (length(trim(username)) > 0),
    CHECK (length(trim(email)) > 0)
);

CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    name        VARCHAR(80) NOT NULL,
    description VARCHAR(255),
    color       VARCHAR(7) NOT NULL DEFAULT '#64748B',
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (user_id, name),
    CHECK (length(trim(name)) > 0)
);

CREATE TABLE IF NOT EXISTS tasks (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                  INTEGER NOT NULL,
    category_id              INTEGER,
    title                    VARCHAR(200) NOT NULL,
    description              TEXT,
    priority                 VARCHAR(10) NOT NULL DEFAULT 'MEDIUM'
                                 CHECK (priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    status                   VARCHAR(20) NOT NULL DEFAULT 'NEW'
                                 CHECK (status IN ('NEW', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')),
    deadline                 DATETIME NOT NULL,
    estimated_duration_minutes INTEGER NOT NULL DEFAULT 60
                                 CHECK (estimated_duration_minutes > 0),
    actual_duration_minutes  INTEGER
                                 CHECK (actual_duration_minutes IS NULL OR actual_duration_minutes >= 0),
    created_at               DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at               DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at             DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL,
    CHECK (length(trim(title)) > 0),
    CHECK (
        (status = 'COMPLETED' AND completed_at IS NOT NULL)
        OR
        (status <> 'COMPLETED' AND completed_at IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS task_history (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id             INTEGER NOT NULL,
    changed_by_user_id  INTEGER,
    event_type          VARCHAR(30) NOT NULL
                            CHECK (event_type IN (
                                'CREATED', 'STATUS_CHANGED', 'DEADLINE_CHANGED', 'UPDATED'
                            )),
    old_status          VARCHAR(20)
                            CHECK (old_status IS NULL OR old_status IN
                                ('NEW', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')),
    new_status          VARCHAR(20)
                            CHECK (new_status IS NULL OR new_status IN
                                ('NEW', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')),
    old_deadline        DATETIME,
    new_deadline        DATETIME,
    note                TEXT,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    FOREIGN KEY (changed_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS predictions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id           INTEGER NOT NULL,
    risk_score        REAL NOT NULL CHECK (risk_score >= 0.0 AND risk_score <= 1.0),
    risk_level        VARCHAR(10) NOT NULL
                          CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH')),
    source            VARCHAR(10) NOT NULL
                          CHECK (source IN ('ML', 'FALLBACK')),
    model_version     VARCHAR(50),
    features_snapshot TEXT NOT NULL DEFAULT '{}',
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    CHECK (
        (source = 'ML' AND model_version IS NOT NULL)
        OR
        (source = 'FALLBACK')
    )
);

-- Indexes for the most common list/filter/history queries.
CREATE INDEX IF NOT EXISTS idx_tasks_user_status
    ON tasks(user_id, status);

CREATE INDEX IF NOT EXISTS idx_tasks_user_deadline
    ON tasks(user_id, deadline);

CREATE INDEX IF NOT EXISTS idx_tasks_user_priority
    ON tasks(user_id, priority);

CREATE INDEX IF NOT EXISTS idx_tasks_category
    ON tasks(category_id);

CREATE INDEX IF NOT EXISTS idx_task_history_task_created
    ON task_history(task_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_predictions_task_created
    ON predictions(task_id, created_at DESC);

-- Notes:
-- 1) Validate that category_id belongs to the same user_id in TaskService.
--    A plain FK guarantees category existence but not ownership equality.
-- 2) Update tasks.updated_at in TaskService whenever a task is modified.
-- 3) Set completed_at when status changes to COMPLETED; clear it if the task
--    leaves COMPLETED status.
-- 4) OVERDUE is derived, not stored: deadline < current time and status is
--    neither COMPLETED nor CANCELLED.
