# Business Automation Platform（业务自动化平台）

一个基于 **FastAPI**、**SQLAlchemy 2.0** 和 **PostgreSQL** 的 RESTful 客户线索（Lead）管理 API。
它是「业务自动化平台」的第一个模块，帮助小型销售团队接收客户咨询、跟踪销售漏斗，
并记录跟进活动。

## 功能特性

- 线索的增删改查（完整 CRUD）
- 分页线索列表，支持关键词搜索、状态筛选与排序
- 枚举校验的线索状态 + 受控状态机：
  `NEW → CONTACTED → QUALIFIED → CONVERTED`（任何进行中的阶段都可以转到 `LOST`）
- 线索下的跟进记录，按时间倒序返回
- 统计看板接口：线索 / 跟进总数、各状态数量、最近 5 条跟进
- 带签名与幂等的 Webhook 接入（重试不会产生重复线索）
- 基于 Pydantic `EmailStr` 的邮箱校验
- 自动生成 OpenAPI / Swagger 文档
- 基于内存 SQLite 的测试套件

## 技术栈

| 层次 | 技术 |
| --- | --- |
| Web 框架 | FastAPI |
| ORM | SQLAlchemy 2.0（类型化 `Mapped` 模型） |
| 数据校验 | Pydantic v2 |
| 配置管理 | pydantic-settings（支持 `.env`） |
| 数据库 | PostgreSQL 17（通过 `psycopg`，同时兼容 SQLite） |
| 服务器 | Uvicorn |
| 测试 | pytest + FastAPI TestClient |

## 项目结构

```
business-automation-platform/
├── app/
│   ├── main.py                 # 应用入口与路由注册
│   ├── api/
│   │   └── v1/
│   │       ├── router.py       # v1 版本路由汇总
│   │       └── endpoints/
│   │           ├── lead.py     # 线索相关接口
│   │           ├── dashboard.py # 统计看板接口
│   │           └── webhook.py  # 带签名的线索接入接口
│   ├── core/
│   │   ├── config.py           # 环境变量配置（.env）
│   │   ├── constants.py        # 状态、状态流转规则等公共常量
│   │   └── security.py         # Webhook 共享密钥校验
│   ├── db/
│   │   ├── base.py             # 声明式基类
│   │   └── database.py         # 引擎、会话工厂、get_db 依赖
│   ├── models/
│   │   ├── lead.py             # 线索 ORM 模型
│   │   ├── lead_follow_up.py   # 跟进记录 ORM 模型
│   │   └── webhook_idempotency.py # Webhook 幂等记录
│   ├── schemas/
│   │   ├── lead.py             # 线索请求 / 响应模型
│   │   └── dashboard.py        # 统计响应模型
│   └── services/
│       ├── lead_service.py     # 线索业务逻辑与查询
│       └── dashboard_service.py # 统计聚合查询
├── tests/
│   ├── conftest.py             # 共享的内存数据库 fixture
│   ├── test_lead.py            # 线索接口测试
│   ├── test_dashboard.py       # 统计接口测试
│   └── test_webhook.py         # Webhook 与幂等测试
├── requirements.txt
└── README.md
```

## 快速开始

### 1. 环境要求

- Python 3.10+（已在 3.14 上验证）

### 2. 安装

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. 启动服务

```bash
uvicorn app.main:app --reload
```

服务地址为 `http://127.0.0.1:8000`，交互式文档：

- Swagger UI：`http://127.0.0.1:8000/docs`
- ReDoc：`http://127.0.0.1:8000/redoc`

首次启动时会自动创建数据库表（默认 SQLite 文件 `business.db`）。

### 4. 运行测试

```bash
pytest -q
```

## 配置说明

配置全部来自环境变量，不同环境之间无需改代码。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./business.db` | SQLAlchemy 连接串，例如 `postgresql+psycopg://app_user:secret@127.0.0.1:5432/business_automation` |
| `SQL_ECHO` | `false` | 设为 `true` 会打印每条 SQL |
| `WEBHOOK_SECRET` | `dev-secret-change-me` | `POST /webhooks/leads` 要求的共享密钥 |

复制模板并填入你自己的配置（`.env` 本身已被 Git 忽略）：

```bash
cp .env.example .env
```

### PostgreSQL

项目默认使用 SQLite 以便开箱即用，但**推荐使用 PostgreSQL**。
本地可以用 Docker 启动一个实例：

```bash
docker run -d --name business-automation-postgres \
  -e POSTGRES_DB=business_automation \
  -e POSTGRES_USER=app_user \
  -e POSTGRES_PASSWORD=ChangeMe_2026 \
  -p 5432:5432 postgres:17
```

然后把 `.env` 指向它：

```bash
DATABASE_URL=postgresql+psycopg://app_user:ChangeMe_2026@127.0.0.1:5432/business_automation
```

密码中的特殊字符需要做 URL 编码（例如 `!` 要写成 `%21`）。
数据表会在启动时自动创建；涉及表结构变更时建议引入 Alembic 等迁移工具。

## 接口说明

基础路径：`/api/v1`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/leads` | 创建线索 |
| `GET` | `/leads` | 线索列表（`page`、`page_size`、`keyword`、`status`、`sort_by`、`sort_order`） |
| `GET` | `/leads/{lead_id}` | 按 id 获取线索 |
| `PUT` | `/leads/{lead_id}` | 部分更新线索 |
| `DELETE` | `/leads/{lead_id}` | 删除线索及其跟进记录 |
| `PATCH` | `/leads/{lead_id}/status` | 变更线索状态 |
| `POST` | `/leads/{lead_id}/follow-ups` | 新增跟进记录 |
| `GET` | `/leads/{lead_id}/follow-ups` | 跟进记录列表（倒序） |
| `GET` | `/dashboard/summary` | 看板统计：总数、各状态数量、最近 5 条跟进 |
| `POST` | `/webhooks/leads` | 带认证与幂等的线索接入 |

健康检查：`GET /health`

### 调用示例

```bash
# 创建线索
curl -X POST http://127.0.0.1:8000/api/v1/leads \
  -H "Content-Type: application/json" \
  -d '{"name":"Alice Chen","phone":"13800138000","email":"alice@example.com","company":"ABC Tech"}'

# 推进销售阶段
curl -X PATCH http://127.0.0.1:8000/api/v1/leads/1/status \
  -H "Content-Type: application/json" \
  -d '{"status":"CONTACTED"}'

# 添加跟进记录
curl -X POST http://127.0.0.1:8000/api/v1/leads/1/follow-ups \
  -H "Content-Type: application/json" \
  -d '{"content":"Called the customer, demo scheduled."}'

# 看板统计
curl http://127.0.0.1:8000/api/v1/dashboard/summary
```

统计接口响应示例：

```json
{
  "total_leads": 2,
  "total_follow_ups": 1,
  "status_counts": {
    "NEW": 1,
    "CONTACTED": 1,
    "QUALIFIED": 0,
    "CONVERTED": 0,
    "LOST": 0
  },
  "recent_follow_ups": [
    {
      "id": 1,
      "lead_id": 1,
      "lead_name": "Alice Chen",
      "content": "Called the customer, demo scheduled.",
      "created_at": "2026-11-12T08:30:00"
    }
  ]
}
```

### Webhook 接入

外部系统（落地页、表单工具、CRM 连接器）可以把线索推送到
`POST /api/v1/webhooks/leads`。

| 请求头 | 是否必填 | 说明 |
| --- | --- | --- |
| `X-Webhook-Secret` | 是 | 必须与 `WEBHOOK_SECRET` 一致，否则返回 `403` |
| `Idempotency-Key` | 是 | 每个事件的唯一 id，1–255 字符，用于防止重试重复创建 |
| `Content-Type` | 是 | `application/json` |

响应语义：

| 状态码 | 含义 |
| --- | --- |
| `201 Created` | 本次请求创建了新线索 |
| `200 OK` | 重复投递：返回第一次创建的线索，不会新建 |
| `403 Forbidden` | 密钥缺失或错误 |
| `409 Conflict` | 同一 Key 搭配了不同内容，或其对应的线索已被删除 |
| `422 Unprocessable Entity` | 缺少必需请求头或请求体不合法 |

```bash
curl -X POST http://127.0.0.1:8000/api/v1/webhooks/leads \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: $WEBHOOK_SECRET" \
  -H "Idempotency-Key: evt_20261115_0001" \
  -d '{"name":"Alice Chen","phone":"13800138000","email":"alice@example.com"}'
```

每个请求的内容会被规范化为 JSON 后计算 SHA-256 指纹，并在**同一个事务**里与新建的线索
一起写入 `webhook_idempotency` 表。并发重试由 `idempotency_key` 上的唯一约束兜底。

### 状态流转

```
NEW ──► CONTACTED ──► QUALIFIED ──► CONVERTED
 │          │             │
 └──────────┴─────────────┴──► LOST
```

非法的状态流转返回 `409 Conflict`；未知状态值返回 `422 Unprocessable Entity`。

## 后续规划

- [ ] 认证与基于角色的权限控制
- [ ] Alembic 数据库迁移
- [ ] 客户（Customer）与商机（Deal）模块
- [ ] 邮件 / 通知自动化后台任务
- [ ] Docker 镜像与 CI 流水线

## 许可证

本项目仅用于作品集与演示用途。
