# Business Automation Platform（业务自动化平台）

一个基于 **FastAPI**、**SQLAlchemy 2.0**、**PostgreSQL** 和 **n8n** 的业务自动化平台。
它帮助小型销售团队接收网站表单与 Webhook 咨询、清洗客户信息、跟踪销售漏斗，
并把新线索可靠地分发到 Google Sheets、邮件自动回复和 n8n 工作流。

## 功能特性

- 网站表单接入：`POST /intake/forms` 把原始表单提交转换为线索
- 客户信息自动识别：从自由文本中补齐缺失的邮箱 / 手机号 / 姓名（支持 `+86`、空格和横线）
- 重复检测：已存在的邮箱或手机号会转为跟进记录，而不是新建重复线索
- 事务性 Outbox（`integration_events`）保证出站集成可靠投递：
  每个目标一条事件，请求内首次投递，失败后由 worker 指数退避重试
- Google Sheets 同步（`values:append`）、SMTP 邮件自动回复、n8n Webhook 触发
- 未配置凭据时集成自动降级为 dry-run（只写日志），保证空 `.env` 也能跑通演示
- 带签名与幂等的 Webhook 接入（重试不会产生重复线索）
- 线索的增删改查（完整 CRUD）
- 分页线索列表，支持关键词搜索、状态筛选与排序
- 枚举校验的线索状态 + 受控状态机：
  `NEW → CONTACTED → QUALIFIED → CONVERTED`（任何进行中的阶段都可以转到 `LOST`）
- 线索下的跟进记录，按时间倒序返回
- 统计看板接口：线索 / 跟进总数、各状态数量、集成事件数量、最近 5 条跟进
- 结构化日志（`时间 | 级别 | logger | 消息`）输出到 stdout
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
| 集成 | n8n Webhook、Google Sheets API v4、SMTP 邮件 |
| HTTP 客户端 | httpx / google-auth |
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
│   │           ├── lead.py         # 线索相关接口
│   │           ├── dashboard.py    # 统计看板接口
│   │           ├── intake.py       # 网站表单接入接口
│   │           ├── integrations.py # Outbox 查询与手动重试
│   │           └── webhook.py      # 带签名的线索接入接口
│   ├── core/
│   │   ├── config.py           # 环境变量配置（.env）
│   │   ├── constants.py        # 状态、事件类型等公共常量
│   │   ├── logging.py          # 结构化 stdout 日志
│   │   └── security.py         # Webhook 共享密钥校验
│   ├── db/
│   │   ├── base.py             # 声明式基类
│   │   └── database.py         # 引擎、会话工厂、get_db 依赖
│   ├── models/
│   │   ├── lead.py             # 线索 ORM 模型
│   │   ├── lead_follow_up.py   # 跟进记录 ORM 模型
│   │   ├── integration_event.py # 出站集成事件 Outbox
│   │   └── webhook_idempotency.py # Webhook 幂等记录
│   ├── schemas/
│   │   ├── lead.py             # 线索请求 / 响应模型
│   │   ├── dashboard.py        # 统计响应模型
│   │   ├── intake.py           # 表单提交模型
│   │   └── integration.py      # 集成事件模型
│   ├── services/
│   │   ├── lead_service.py     # 线索业务逻辑与查询
│   │   ├── intake_service.py   # 归一化、信息抽取与去重
│   │   ├── integration_service.py # Outbox 入队、投递与重试策略
│   │   ├── dashboard_service.py # 统计聚合查询
│   │   └── integrations/
│   │       ├── sheets.py       # Google Sheets 追加适配器
│   │       ├── mailer.py       # SMTP 自动回复适配器
│   │       └── n8n.py          # n8n Webhook 适配器
│   └── workers/
│       └── integration_worker.py # 待投递事件的重试 worker
├── tests/
│   ├── conftest.py             # 共享的内存数据库 fixture
│   ├── test_lead.py            # 线索接口测试
│   ├── test_dashboard.py       # 统计接口测试
│   ├── test_webhook.py         # Webhook 与幂等测试
│   ├── test_intake.py          # 表单接入、信息抽取与去重测试
│   └── test_integrations.py    # Outbox 入队、重试与计数测试
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
| `WEBHOOK_SECRET` | `dev-secret-change-me` | `POST /webhooks/leads` 与 `/integrations/*` 要求的共享密钥 |
| `INTEGRATIONS_ENABLED` | `true` | 出站自动化队列总开关 |
| `INTEGRATION_MAX_ATTEMPTS` | `5` | 最大投递次数，超过后标记为 `FAILED` |
| `INTEGRATION_RETRY_BASE_SECONDS` | `30` | 退避基数，重试间隔为 30s、60s、120s…… |
| `N8N_WEBHOOK_URL` | – | n8n Webhook 节点地址，留空为 dry-run |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | – | Google 服务账号 JSON 密钥路径 |
| `GOOGLE_SHEETS_SPREADSHEET_ID` | – | 目标表格 id |
| `GOOGLE_SHEETS_RANGE` | `Leads!A:H` | `values:append` 使用的范围 |
| `SMTP_HOST` | – | SMTP 服务器，留空时自动回复只写日志 |
| `SMTP_PORT` | `587` | SMTP 端口 |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | – | SMTP 账号密码 |
| `SMTP_FROM` | `noreply@example.com` | 发件人地址 |
| `SMTP_USE_TLS` | `true` | 是否使用 STARTTLS |
| `AUTO_REPLY_SUBJECT` / `AUTO_REPLY_BODY` | 见 `.env.example` | 自动回复模板，`{name}` 会替换为线索姓名 |

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
| `POST` | `/intake/forms` | 把网站表单提交转换为线索 |
| `GET` | `/dashboard/summary` | 看板统计：总数、各状态数量、集成事件数量、最近 5 条跟进 |
| `POST` | `/webhooks/leads` | 带认证与幂等的线索接入 |
| `POST` | `/integrations/process` | 立即投递所有到期事件（手动重试） |
| `GET` | `/integrations/events` | 查询出站事件（`status`、`limit`） |

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
  "integration_events": {
    "PENDING": 0,
    "SENT": 3,
    "FAILED": 0
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

### 网站表单接入

`POST /api/v1/intake/forms` 接收原始表单内容。除联系方式外所有字段都可选，
并允许携带未知字段（额外的表单控件）。

```bash
curl -X POST http://127.0.0.1:8000/api/v1/intake/forms \
  -H "Content-Type: application/json" \
  -d '{"name":"","email":"","message":"Hi, I am Alice, alice@example.com, 138 0013 8000","source":"landing_page"}'
```

处理流程：

1. **归一化**：邮箱转小写并校验；手机号去掉空格、横线和 `+86` / `0086` 前缀。
2. **信息抽取**：表单里缺失的联系方式从 message 与额外字段中补齐
   （用正则提取邮箱和手机号；没有姓名时用邮箱前缀生成姓名）。
3. **去重**：已存在的邮箱或手机号会把本次提交存为跟进记录，
   返回 `200` 且 `"duplicate": true`，不会新建线索。
4. **排队自动化**：同一事务内写入 3 条 Outbox 事件（Google Sheets、邮件自动回复、n8n）。

如果完全无法识别出邮箱或手机号，返回 `422 Unprocessable Entity`。

### 出站集成与失败重试

新线索通过事务性 Outbox 表（`integration_events`）分发，无需引入消息队列：

| 事件类型 | 适配器 | 目标 |
| --- | --- | --- |
| `sheets.append_lead` | `services/integrations/sheets.py` | Google Sheets `values:append` |
| `email.auto_reply` | `services/integrations/mailer.py` | 通过 SMTP 自动回复线索 |
| `n8n.lead_created` | `services/integrations/n8n.py` | `POST {"event":"lead.created","data":{...}}` |

事件生命周期：`PENDING → SENT`；失败次数达到 `INTEGRATION_MAX_ATTEMPTS` 后变为 `FAILED`。
重试采用指数退避（30s、60s、120s……），记录在 `next_retry_at` 字段。
任何未配置凭据的适配器都会以 dry-run 方式执行并记为 SENT，因此空 `.env` 也能跑通演示。

```bash
# 查看最近事件（含失败原因 last_error）
curl -H "X-Webhook-Secret: $WEBHOOK_SECRET" \
  "http://127.0.0.1:8000/api/v1/integrations/events?status=PENDING&limit=20"

# 立即投递所有到期事件（手动重试）
curl -X POST -H "X-Webhook-Secret: $WEBHOOK_SECRET" \
  http://127.0.0.1:8000/api/v1/integrations/process
```

请求内完成首次投递，后续重试交给 worker：

```bash
# 处理一次到期事件后退出
python -m app.workers.integration_worker --once

# 持续运行，默认每 15 秒轮询一次
python -m app.workers.integration_worker --interval 15
```

### 状态流转

```
NEW ──► CONTACTED ──► QUALIFIED ──► CONVERTED
 │          │             │
 └──────────┴─────────────┴──► LOST
```

非法的状态流转返回 `409 Conflict`；未知状态值返回 `422 Unprocessable Entity`。

## 后续规划

- [x] 邮件 / Sheets / n8n 自动化的后台重试 worker
- [ ] 认证与基于角色的权限控制
- [ ] Alembic 数据库迁移
- [ ] 客户（Customer）与商机（Deal）模块
- [ ] Docker Compose（API + PostgreSQL + n8n）
- [ ] Docker 镜像与 CI 流水线

## 许可证

本项目仅用于作品集与演示用途。
