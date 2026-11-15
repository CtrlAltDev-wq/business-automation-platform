# 代码修改说明（中文学习版）

> 项目：Business Automation Platform
> 生成时间：2026-11-15
> 说明：本文档仅用于学习与复盘，**未提交到 Git**，可随时删除或修改。

---

## 0. 项目背景

这是一个用 **FastAPI + SQLAlchemy 2.0** 编写的客户线索（Lead）管理 API，作为「业务自动化平台」的第一个模块，用于演示：

- 分层架构：`api / schemas / services / models / db / core`
- 数据校验（Pydantic v2）
- 业务状态机（线索流转规则）
- 并发安全的外部 Webhook 接入（幂等）
- 从 SQLite 平滑切换到 PostgreSQL

| 迭代 | 时间 | 技术栈 | 主题 |
| --- | --- | --- | --- |
| 1 | 2026-11-15 | FastAPI、SQLAlchemy 2.0、Pydantic v2、SQLite、pytest | 项目初始化与代码体检修复 |
| 2 | 2026-11-15 | FastAPI、SQLAlchemy（`GROUP BY` / `JOIN`）、`Literal` + `get_args` | 统计（Dashboard）接口 |
| 3 | 2026-11-15 | FastAPI、Pydantic v2、SHA-256、`secrets.compare_digest`、数据库唯一约束 | 签名 + 幂等的 Webhook |
| 4 | 2026-11-15 | pydantic-settings、Git `.gitignore` 否定规则 | 提交 `.env.example`、忽略 `.env` |
| 5 | 2026-11-15 | PostgreSQL 17、psycopg 3、SQLAlchemy、Docker | 数据库切换为 PostgreSQL 并迁移数据 |
| 6 | 2026-11-15 | FastAPI、Pydantic v2、SQLAlchemy + PostgreSQL `JSON`、Outbox、google-auth、httpx、smtplib、n8n、logging、pytest | 表单接入 + 客户信息识别 + Sheets/邮件/n8n + Outbox 重试 + 日志（28 个文件） |

---

## 1. 迭代一：项目初始化与代码体检（FastAPI / SQLAlchemy / pytest）

### 1.1 发现的问题 → 处理方式

| 问题 | 后果 | 处理 |
| --- | --- | --- |
| `tests/test_lead.py` 里同名测试函数定义了两次 | 后者覆盖前者，实际少跑一个用例 | 删除重复定义，补齐用例 |
| `requirements.txt` 缺 `email-validator`、`dnspython` | 别人 `pip install` 后 `EmailStr` 直接报错 | 按实际环境重新生成依赖 |
| 没有 `.gitignore` | `business.db`、`.venv`、缓存会被提交 | 新增 `.gitignore` |
| `create_engine(echo=True)` 写死 | 生产环境 SQL 日志噪音大 | 改为环境变量开关 |
| API 文档 tag 是中文 | 与英文仓库风格不一致 | 改为 `leads` / `dashboard` |
| 注释中英混杂、函数无 docstring | 可读性差 | 全部统一为英文注释 + docstring |

### 1.2 代码示例：数据库配置改为环境变量

改动前（历史版本）：

```python
# 数据库地址写死，SQL 日志永远打开
engine = create_engine(
    "sqlite:///./business.db",
    connect_args={"check_same_thread": False},
    echo=True,
)
```

改动后：

```python
# app/db/database.py
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./business.db")

# 只有 SQLite 需要关闭线程检查：FastAPI 在线程池里跑同步请求
connect_args = (
    {"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {}
)

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
)
```

**学习点**：`connect_args` 是驱动级别的参数，只有对应数据库才认识。用 `startswith("sqlite")` 做条件判断，可以一套代码同时支持 SQLite 与 PostgreSQL。

### 1.3 代码示例：测试为什么用内存数据库

```python
# tests/conftest.py
test_engine = create_engine(
    "sqlite://",                      # 内存库，进程结束即消失
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,             # 让多个连接共享同一个内存库
)

@pytest.fixture
def client():
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
```

**学习点**：
- `sqlite://` 是内存库，测试跑完不留垃圾文件。
- `StaticPool` 保证所有连接指向同一份内存数据，否则每建一个连接就是空库。
- `app.dependency_overrides` 是 FastAPI 官方推荐的依赖替换机制，无需启动真实服务。

---

## 2. 迭代二：统计接口（FastAPI / SQLAlchemy / Pydantic）

### 2.1 需求

一个看板接口，返回：线索总数、跟进总数、各状态数量、最近 5 条跟进。

### 2.2 问题：状态列表重复了 3 份

原来 `"NEW" / "CONTACTED" / ...` 同时出现在 schema、service、dashboard 三处，新增状态必然漏改。

改为**单一数据源**：

```python
# app/core/constants.py
from typing import Literal, get_args

# 类型层面：给 Pydantic / IDE 用
LeadStatus = Literal["NEW", "CONTACTED", "QUALIFIED", "CONVERTED", "LOST"]

# 运行层面：给循环、统计用（get_args 从 Literal 里取出所有值）
LEAD_STATUSES: tuple[str, ...] = get_args(LeadStatus)

ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "NEW": {"CONTACTED", "LOST"},
    "CONTACTED": {"QUALIFIED", "LOST"},
    "QUALIFIED": {"CONVERTED", "LOST"},
    "CONVERTED": set(),
    "LOST": set(),
}
```

`schema` 直接复用：

```python
# app/schemas/lead.py
from app.core.constants import LeadStatus

class LeadStatusUpdate(BaseModel):
    status: LeadStatus
```

**学习点**：`typing.get_args()` 能把 `Literal[...]` 里的字面量取成元组，从而做到「类型定义只有一份，运行时也能拿到值」。

### 2.3 代码示例：一次查询完成分组统计

```python
# app/services/dashboard_service.py
status_statement = (
    select(Lead.status, func.count(Lead.id))
    .group_by(Lead.status)
)
status_rows = db.execute(status_statement).all()

# 先给所有状态填 0，保证没有数据的状态也会出现在返回里
status_counts = {status: 0 for status in LEAD_STATUSES}
for lead_status, count in status_rows:
    status_counts[lead_status] = count
```

**学习点**：`GROUP BY` 只会返回有数据的分组。前端图表通常要求「所有分类都在」，所以要先用常量字典补 0，再覆盖真实值。

### 2.4 代码示例：最近跟进用 JOIN 一次取回

```python
recent_statement = (
    select(
        LeadFollowUp.id,
        LeadFollowUp.lead_id,
        Lead.name.label("lead_name"),
        LeadFollowUp.content,
        LeadFollowUp.created_at,
    )
    .join(Lead, LeadFollowUp.lead_id == Lead.id)
    .order_by(LeadFollowUp.created_at.desc(), LeadFollowUp.id.desc())
    .limit(RECENT_FOLLOW_UP_LIMIT)   # 常量，避免魔法数字 5
)
rows = db.execute(recent_statement).mappings().all()
```

**学习点**：
- `.mappings()` 让结果可以按列名取值，直接 `dict(row)` 就能序列化。
- `created_at` 可能重复，加 `id desc` 作为第二排序键，保证顺序稳定。

---

## 3. 迭代三：Webhook 接入与幂等（FastAPI / SQLAlchemy / 唯一约束）

### 3.1 需求背景

外部系统（落地页、表单工具、CRM）把客户推过来。网络会重试，所以**同一个请求可能到达多次**，不能产生重复线索。

### 3.2 代码示例：共享密钥校验（恒定时间比较）

```python
# app/core/security.py
import secrets
from fastapi import Header, HTTPException, status as http_status

def verify_webhook_secret(
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
) -> None:
    # compare_digest 耗时与内容无关，避免通过响应时间猜出密钥
    if not x_webhook_secret or not secrets.compare_digest(
        x_webhook_secret,
        settings.webhook_secret,
    ):
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN,
                            detail="Invalid webhook credentials")
```

**学习点**：校验密码/密钥不要用 `==`，普通字符串比较是「发现第一个不同就返回」，时间差会泄露信息。

### 3.3 幂等表设计

```python
# app/models/webhook_idempotency.py
class WebhookIdempotency(Base):
    __tablename__ = "webhook_idempotency"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 调用方传的事件 id，唯一索引是幂等的最后一道防线
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # 请求体指纹，用于识别「同一个 key 传了不同内容」
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    lead_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

### 3.4 代码示例：请求体指纹

```python
def _calculate_payload_hash(data: LeadCreate) -> str:
    payload = data.model_dump(mode="json")
    canonical_json = json.dumps(
        payload,
        sort_keys=True,          # 键排序：字段顺序不同也算同一个请求
        ensure_ascii=False,
        separators=(",", ":"),   # 去掉空格：序列化结果唯一
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
```

**学习点**：判断「两个 JSON 是否内容相同」不能直接比较字符串（键顺序、空格都会变）。先规范化为**规范 JSON（canonical JSON）**再哈希。

### 3.5 代码示例：一个事务里写两张表 + 竞态兜底

```python
def create_lead_from_webhook(db, data, idempotency_key) -> tuple[Lead, bool]:
    payload_hash = _calculate_payload_hash(data)

    # 1. 快路径：key 已经处理过
    existing = db.scalar(
        select(WebhookIdempotency).where(
            WebhookIdempotency.idempotency_key == idempotency_key
        )
    )
    if existing:
        return _resolve_existing_webhook_event(db, existing, payload_hash), False

    try:
        # 2. 慢路径：先写线索，flush 拿到自增 id
        lead = _build_lead(data)
        db.add(lead)
        db.flush()

        # 3. 再写幂等记录，最后一起提交
        db.add(WebhookIdempotency(
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            lead_id=lead.id,
        ))
        db.commit()
        db.refresh(lead)
        return lead, True

    except IntegrityError:
        # 4. 两个请求同时通过第 1 步时，唯一索引会让后者在这里失败
        db.rollback()
        existing = db.scalar(
            select(WebhookIdempotency).where(
                WebhookIdempotency.idempotency_key == idempotency_key
            )
        )
        if existing is None:
            raise            # 不是幂等冲突，正常抛出
        return _resolve_existing_webhook_event(db, existing, payload_hash), False
```

**学习点**：
- 「查一下有没有」和「插入」之间存在时间窗，**应用层判断无法防并发**，必须依赖数据库唯一约束。
- `db.flush()` 与 `db.commit()` 的区别：`flush` 只把 SQL 发给数据库（拿到自增 ID），事务还没提交；`commit` 才真正落盘。
- 捕获 `IntegrityError` 后必须 `rollback()`，否则 Session 会处于不可用状态。

### 3.6 返回码语义

| 场景 | 状态码 | 含义 |
| --- | --- | --- |
| 首次创建 | `201` | 新线索已创建 |
| 相同 key + 相同内容 | `200` | 重复投递，返回原来那条线索 |
| 相同 key + 不同内容 | `409` | 调用方把 key 用错了 |
| 缺少/错误密钥 | `403` | 鉴权失败 |

实现时用 `response_model=LeadResponse` + 手动覆盖状态码：

```python
lead, created = lead_service.create_lead_from_webhook(...)
if not created:
    response.status_code = http_status.HTTP_200_OK
return lead
```

---

## 4. 迭代四：`.env.example` 与 `.env`（pydantic-settings / Git）

### 4.1 问题

`.gitignore` 里写了 `.env.*`，把模板文件 `.env.example` 也一起忽略了。

### 4.2 解决方案：否定规则

```gitignore
# Environment variables
.env
.env.*
!.env.example     # ! 表示重新纳入版本控制
```

**学习点**：`.gitignore` 从上到下匹配，**后出现的规则优先级更高**，所以否定规则必须写在忽略规则之后。

验证命令：

```bash
git check-ignore -v .env          # 命中 .env 规则 → 被忽略
git check-ignore -v .env.example  # 命中 !.env.example → 不忽略
```

### 4.3 模板文件

```bash
# .env.example
WEBHOOK_SECRET=replace-with-your-own-secret
# DATABASE_URL=postgresql+psycopg://app_user:your-password@127.0.0.1:5432/business_automation
# SQL_ECHO=false
```

---

## 5. 迭代五：SQLite → PostgreSQL（PostgreSQL 17 / psycopg 3 / Docker）

### 5.1 一个隐藏的坑：`.env` 里的 `DATABASE_URL` 根本没生效

改动前：

```python
# app/db/database.py
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./business.db")
```

`os.getenv` 只读**进程环境变量**。项目虽然用 pydantic-settings 支持 `.env`，但那份 `.env` 只被 `Settings` 读取，不会写回 `os.environ`，所以往 `.env` 里写 `DATABASE_URL` 完全无效。

改动后：统一由 `Settings` 读取。

```python
# app/core/config.py
class Settings(BaseSettings):
    webhook_secret: str = "dev-secret-change-me"
    database_url: str = "sqlite:///./business.db"   # ← 对应环境变量 DATABASE_URL
    sql_echo: bool = False                          # ← 对应环境变量 SQL_ECHO

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
```

```python
# app/db/database.py
from app.core.config import settings

DATABASE_URL = settings.database_url
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=settings.sql_echo,
)
```

**学习点**：pydantic-settings 根据**字段名**匹配环境变量（大小写不敏感），`database_url` 自动对应 `DATABASE_URL`，不需要手写 `os.getenv`。优先级：真实环境变量 > `.env` 文件 > 代码默认值。

### 5.2 新增驱动依赖

```text
# requirements.txt
psycopg==3.3.9
psycopg-binary==3.3.9
```

URL 使用 `postgresql+psycopg://`（psycopg 3），而不是旧教程里的 `postgresql://`（默认 psycopg2）或 `postgresql+asyncpg://`（异步驱动）。

### 5.3 本地 `.env`

```bash
DATABASE_URL=postgresql+psycopg://app_user:ChangeMe_2026%21@127.0.0.1:5432/business_automation
SQL_ECHO=false
```

**踩坑点**：密码里的 `!` 在 URL 中属于特殊字符，必须编码成 `%21`。SQLAlchemy 解析 URL 时会自动解码，所以数据库端拿到的仍是 `ChangeMe_2026!`。

### 5.4 让测试不依赖 PostgreSQL

如果 `.env` 指向 PostgreSQL，`import app.main` 时就会去连 PG，CI 上没有数据库就会失败。所以在 conftest 里**在导入应用之前**覆盖环境变量：

```python
# tests/conftest.py
import os

# 必须写在 import app.* 之前：app.db.database 在模块导入时就创建 engine
os.environ["DATABASE_URL"] = "sqlite://"

from app.db.base import Base  # noqa: E402
from app.db.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
```

**学习点**：模块级副作用（`create_engine`、`create_all`）发生在 `import` 那一刻，所以环境变量必须在 import 前就位。

### 5.5 数据迁移脚本（一次性，未入库）

思路：读 SQLite → 按原主键插入 PostgreSQL → **校准自增序列**。

```python
import sqlite3
import psycopg

TABLES = {
    "leads": ["id", "name", "phone", "email", "company", "message", "status"],
    "lead_follow_ups": ["id", "lead_id", "content", "created_at"],
    "webhook_idempotency": ["id", "idempotency_key", "payload_hash", "lead_id", "created_at"],
}

src = sqlite3.connect("business.db")
src.row_factory = sqlite3.Row

with psycopg.connect(
    host="127.0.0.1", port=5432, dbname="business_automation",
    user="app_user", password="ChangeMe_2026!",
) as conn, conn.cursor() as cur:
    for table, cols in TABLES.items():
        rows = src.execute(f"select {', '.join(cols)} from {table}").fetchall()

        placeholders = ", ".join(["%s"] * len(cols))
        stmt = (
            f"insert into {table} ({', '.join(cols)}) "
            f"values ({placeholders}) on conflict (id) do nothing"
        )
        for row in rows:
            cur.execute(stmt, tuple(row[c] for c in cols))

        # 关键：把 PostgreSQL 的自增序列推到当前最大 id，否则下次插入主键冲突
        cur.execute(
            f"select setval(pg_get_serial_sequence('{table}', 'id'), "
            f"coalesce((select max(id) from {table}), 1))"
        )
    conn.commit()
```

**学习点**：
- 迁移时显式带 `id` 插入可以保住外键关系（`lead_follow_ups.lead_id`）。
- `SERIAL / IDENTITY` 的自增计数器不会因为手工插入而前进，必须 `setval` 校准，否则下一条 INSERT 会撞主键。
- `on conflict (id) do nothing` 让脚本可以重复执行（幂等）。

### 5.6 迁移结果

```text
leads:               sqlite=24  postgres=24
lead_follow_ups:     sqlite=2   postgres=2
webhook_idempotency: sqlite=2   postgres=2
```

API 实测：

```text
total leads: 24 | first: wangqi
dashboard: 24 2 {'NEW': 23, 'CONTACTED': 1, 'QUALIFIED': 0, 'CONVERTED': 0, 'LOST': 0}
create: 201 25          # 新 id 接在 24 之后，说明序列校准成功
status update: 200 CONTACTED
delete: 200 {'message': 'Lead deleted successfully'}
```

测试：

```text
28 passed
```

---

## 6. 迭代六：业务自动化闭环（FastAPI / Outbox / n8n / Sheets / SMTP）

> 目标：把「网站表单 → 信息识别 → 入库去重 → Google Sheets / 邮件 / n8n → 失败重试 → 日志」串成一条可演示的闭环。
> 验证结果：`38 passed`；并在真实 PostgreSQL 上跑通了表单接入冒烟测试（3 个事件全部 SENT，测试数据已清理）。

### 6.1 功能点 → 代码 → 技术栈

| 功能点 | 入口 | 核心实现 | 技术栈 |
| --- | --- | --- | --- |
| 自动接收网站表单 | `POST /api/v1/intake/forms` | `intake.py` + `intake_service.submit_form()` | FastAPI、Pydantic v2（`extra="allow"`） |
| 自动识别和整理客户信息 | 同上 | `normalize_email` / `normalize_phone` / `extract_contact_info` | Python `re` |
| 同步 Google Sheets | 事件 `sheets.append_lead` | `integrations/sheets.py` | google-auth（服务账号）+ httpx + Sheets API v4 |
| 自动发送邮件 | 事件 `email.auto_reply` | `integrations/mailer.py` | `smtplib` + `EmailMessage` |
| Webhook 触发工作流 | 事件 `n8n.lead_created` | `integrations/n8n.py` | httpx + n8n Webhook 节点 |
| 失败重试 | `/integrations/process` + worker | `integration_service.process_event()` | SQLAlchemy 事务 + 指数退避 |
| 日志记录 | 全链路 | `core/logging.py` | 标准库 `logging`（stdout） |

### 6.2 本轮补充的技术栈

| 技术 | 用途 | 为什么选它 |
| --- | --- | --- |
| 事务性 Outbox（`integration_events` 表） | 可靠投递 | 不引入 Kafka / Redis，也能做到「先落库再投递、可重试、进程重启不丢」 |
| PostgreSQL `JSON` 列 | 保存事件 payload 快照 | 重试时发送的数据不变；SQLAlchemy 直接映射成 `dict` |
| google-auth | 服务账号换取 access token | 比 `google-api-python-client` 轻，直接用 httpx 调 REST |
| httpx | 调 Sheets / n8n | 同步客户端，接口简单，超时可控 |
| smtplib + EmailMessage | 邮件自动回复 | 标准库，零额外依赖 |
| n8n Webhook 节点 | 低代码工作流 | HTTP 即可对接，演示时可视化效果最好 |
| argparse worker | 独立重试进程 | 与 Web 进程解耦，可单独部署 / 单独调试 |
| pytest + monkeypatch | 测试外部集成 | 不真的发邮件、不真的写表格 |

### 6.3 数据流

```
POST /intake/forms  或  POST /webhooks/leads
        │
        ▼
 intake_service：归一化 → 自由文本抽取 → 去重
        │ 新线索
        ▼
   leads 表（同一事务）
        │
        ▼
 integration_events：3 条 PENDING（sheets / email / n8n）
        │
        ├─ 请求内首次投递 process_pending()
        │        ├─ 成功 → SENT
        │        └─ 失败 → attempts+1、next_retry_at = now + 30s * 2^(n-1)
        ▼
 integration_worker --interval 15 → 到期重试 → 超过 5 次 → FAILED
        │
        ▼
 GET /integrations/events + GET /dashboard/summary 查看投递健康度
```

### 6.4 关键代码

#### 6.4.1 表单模型：允许未知字段

```python
# app/schemas/intake.py
class FormSubmission(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: Optional[str] = Field(default=None, max_length=100)
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=30)
    company: Optional[str] = Field(default=None, max_length=255)
    message: Optional[str] = None
    source: Optional[str] = Field(default=None, max_length=50)
```

**学习点**：表单工具常带 `utm_source`、`page_url` 等自定义字段。`extra="allow"` 让它们进入 `model_extra`，既能用于信息抽取，也不会因为多传字段直接返回 422。

#### 6.4.2 手机号归一化与正则边界

```python
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:\+?86[\s-]?)?(1[3-9]\d(?:[\s-]?\d{4}){2})(?!\d)"
)


def normalize_phone(raw: str | None) -> str | None:
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("0086"):
        digits = digits[4:]
    elif digits.startswith("86") and len(digits) == 13:
        digits = digits[2:]
    return digits if 6 <= len(digits) <= 15 else None
```

**学习点**：
- `(?<!\d)` / `(?!\d)` 防止从一长串数字中间截出「手机号」。
- `(?:[\s-]?\d{4}){2}` 同时支持 `13900139000`、`139 0013 9000`、`139-0013-9000`。
- 归一化先做「去非数字 → 去国家码 → 长度校验」，后续去重才能精确匹配。

#### 6.4.3 缺失字段从自由文本恢复

```python
extra_text = _collect_extra_text(submission)
free_text = "\n".join(part for part in (submission.message, extra_text) if part)

email = normalize_email(submission.email)
if email is None and free_text:
    match = EMAIL_PATTERN.search(free_text)
    if match:
        email = normalize_email(match.group(0))
        if email:
            extracted.append("email")

name = (submission.name or "").strip() or None
if name is None and email:
    name = email.split("@")[0].replace(".", " ").replace("_", " ").title()
    extracted.append("name")
```

**学习点**：`jane.doe@example.com` 会生成 `Jane Doe`，避免线索列表里全是空姓名；接口把 `extracted_fields` 返回给调用方，让「推断」是透明的。

#### 6.4.4 重复提交转为跟进记录

```python
def find_duplicate(db: Session, email: str | None, phone: str | None) -> Lead | None:
    conditions = []
    if email:
        conditions.append(func.lower(Lead.email) == email)
    if phone:
        conditions.append(Lead.phone == phone)

    statement = select(Lead).where(or_(*conditions)).order_by(Lead.id.asc()).limit(1)
    return db.scalars(statement).first()
```

命中后写入 `LeadFollowUp(content="Duplicate submission (source): ...")`，接口返回 `200` + `"duplicate": true`。

**学习点**：同一个人再次询价是「跟进信号」，不是脏数据；用邮箱或手机号任一匹配即可，避免表单只填其中一项时漏判。

#### 6.4.5 Outbox 入队：与线索同一事务

```python
def enqueue_lead_created(db: Session, lead: Lead, source: str) -> list[str]:
    if not settings.integrations_enabled:
        return []

    payload = build_lead_payload(lead, source)

    for event_type in EVENT_HANDLERS:
        db.add(
            IntegrationEvent(
                event_type=event_type,
                payload=payload,
                status=EVENT_PENDING,
            )
        )

    db.commit()
    return list(EVENT_HANDLERS)
```

**学习点**：
- 先落库再投递，**进程崩溃也不会丢任务**；
- `build_lead_payload` 是快照，之后修改线索不会影响已排队事件；
- `EVENT_HANDLERS` 既是「支持的事件类型」，也是「入队清单」，新增集成只改一处。

#### 6.4.6 失败重试与指数退避

```python
try:
    detail = handler(event.payload)
except Exception as exc:
    event.attempts += 1
    event.last_error = f"{type(exc).__name__}: {exc}"

    if event.attempts >= settings.integration_max_attempts:
        event.status = EVENT_FAILED
        event.next_retry_at = None
    else:
        event.status = EVENT_PENDING
        event.next_retry_at = _utcnow() + timedelta(
            seconds=_retry_delay_seconds(event.attempts)
        )

    db.commit()
```

```python
def _retry_delay_seconds(attempts: int) -> int:
    # 30s、60s、120s、240s ...
    return settings.integration_retry_base_seconds * (2 ** max(attempts - 1, 0))
```

**学习点**：
- 重试状态必须落库（`attempts`、`next_retry_at`、`last_error`），否则重启即清零；
- `_utcnow()` 返回 **naive UTC**（`datetime.now(timezone.utc).replace(tzinfo=None)`），SQLite 与 PostgreSQL 都能比较；
- 退避上限由 `INTEGRATION_MAX_ATTEMPTS` 控制，避免无限重试。

#### 6.4.7 适配器 dry-run（以 n8n 为例）

```python
# app/services/integrations/n8n.py
def trigger_lead_created(payload: dict) -> dict:
    if not settings.n8n_webhook_url:
        logger.info("n8n webhook URL is not configured, ...")
        return {"dry_run": True}

    response = httpx.post(
        settings.n8n_webhook_url,
        json={"event": "lead.created", "data": payload},
        timeout=10.0,
    )
    response.raise_for_status()

    return {"status_code": response.status_code}
```

**学习点**：
- `raise_for_status()` 把 4xx / 5xx 变成异常，才能进入统一重试逻辑；
- 未配置凭据时返回 `dry_run` 而不是抛错，保证「零配置也能演示」；
- 统一事件外壳 `{"event": ..., "data": ...}`，n8n 侧用 `{{ $json.data.email }}` 取值即可。

Sheets 与邮件同理：

```python
# sheets.py：服务账号换 token，再调 values:append
credentials = service_account.Credentials.from_service_account_file(
    settings.google_service_account_file,
    scopes=SCOPES,
)
credentials.refresh(Request())
```

```python
# mailer.py：没配 SMTP 只写日志，配了才真正发送
if not settings.smtp_host:
    return {"dry_run": True, "to": recipient, "subject": subject}

with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
    if settings.smtp_use_tls:
        server.starttls()
    if settings.smtp_username:
        server.login(settings.smtp_username, settings.smtp_password or "")
    server.send_message(message)
```

#### 6.4.8 worker：独立进程处理重试

```python
# app/workers/integration_worker.py
while True:
    result = integration_service.run_pending_once()
    logger.info(
        "Integration dispatch: processed=%s sent=%s retrying=%s failed=%s",
        result["processed"], result["sent"], result["retrying"], result["failed"],
    )
    if once:
        return
    time.sleep(interval)
```

`run_pending_once()` 内部自己创建 `SessionLocal()`，因为 worker 不在请求上下文里，没有 `get_db` 可用。

#### 6.4.9 本轮踩坑：为什么不用 BackgroundTasks

最初在端点里用 `BackgroundTasks` 调 `run_pending_once()`，测试直接报：

```text
sqlite3.OperationalError: no such table: integration_events
```

原因有两个：

1. 后台任务用真实的 `SessionLocal`，而测试通过 `dependency_overrides` 注入的是另一份内存库引擎；
2. 后台任务异步执行，断言时事件可能还没投递，测试结果不稳定。

最终方案：**请求内同步完成首次投递**，复用请求的 session：

```python
events_queued = integration_service.enqueue_lead_created(db, lead, source)
if events_queued:
    integration_service.process_pending(db, limit=len(events_queued))
```

后续重试交给 worker。牺牲少量响应时间，换来确定性、可测试性，以及「事件不会因为进程退出而丢」。

#### 6.4.10 看板增加投递健康度

```python
event_statement = (
    select(IntegrationEvent.status, func.count(IntegrationEvent.id))
    .group_by(IntegrationEvent.status)
)

integration_events = {status: 0 for status in INTEGRATION_EVENT_STATUSES}
for event_status, count in db.execute(event_statement).all():
    integration_events[event_status] = count
```

**学习点**：和状态统计一样，先用常量补 0，保证 `PENDING / SENT / FAILED` 三项永远存在，前端不用做空值判断。

### 6.5 本地跑一遍（验证步骤）

前置条件：PostgreSQL 容器已启动，`.env` 已配置 `DATABASE_URL` / `WEBHOOK_SECRET`。

**1）启动服务**

```powershell
cd d:\workspace_upwork\python_workspace\business-automation-platform
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

或在 VS Code 按 F5，选择 `Python: FastAPI (Debug)`。

启动时会自动创建 `integration_events` 表（`Base.metadata.create_all`），无需手工执行 SQL。

**2）Swagger 验证**：打开 `http://127.0.0.1:8000/docs`

`POST /api/v1/intake/forms`，请求体：

```json
{"name":"","email":"","message":"Hi, I am Alice, alice@example.com, 138 0013 8000","source":"landing_page"}
```

预期：`201`，`extracted_fields` 为 `["email","phone","name"]`，`events_queued` 为三个事件类型。

再发送相同内容：`200`，`duplicate: true`，跟进记录 +1。

`GET /api/v1/integrations/events`：Header `X-Webhook-Secret` 填 `.env` 里的 `WEBHOOK_SECRET`。

`GET /api/v1/dashboard/summary`：`integration_events` 中出现 `SENT` 计数。

**3）PowerShell 等价命令**

```powershell
$body = @{ message = "Hi, Alice, alice2@example.com, 139 0013 9000"; source = "landing_page" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/intake/forms -ContentType "application/json" -Body $body

$h = @{ "X-Webhook-Secret" = "<.env 里的 WEBHOOK_SECRET>" }
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/integrations/events?limit=20" -Headers $h
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/integrations/process -Headers $h
```

**4）接入 n8n**

在 `.env` 增加（**改完必须重启进程**，`--reload` 不会重读 `.env`）：

```bash
N8N_WEBHOOK_URL=http://127.0.0.1:5678/webhook/<你的路径>
```

然后提交一次表单，n8n 里应看到 `lead.created` 事件和 `data.email` 等字段。

**5）运行重试 worker**

```powershell
# 处理一次到期事件后退出
.\.venv\Scripts\python.exe -m app.workers.integration_worker --once

# 持续运行，每 15 秒轮询
.\.venv\Scripts\python.exe -m app.workers.integration_worker --interval 15
```

VS Code 中对应 `Integration worker (once)` / `Integration worker (loop)` 两个调试配置。

**6）测试**

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q -k "intake or integrations"
```

### 6.6 调试参数速查

| 参数 / 开关 | 位置 | 建议值 | 作用 |
| --- | --- | --- | --- |
| `--reload` | uvicorn | 开发时开启 | 改代码自动重启（不监听 `.env`） |
| `--log-level debug` | uvicorn | 排查时 | 输出更多框架日志 |
| `SQL_ECHO` | `.env` | 演示 `false`，排查 `true` | 打印每条 SQL |
| `INTEGRATIONS_ENABLED` | `.env` | `true` | 设为 `false` 可只测表单入库、不发外部请求 |
| `INTEGRATION_RETRY_BASE_SECONDS` | `.env` | 演示时 `5` | 把 30s 退避缩短，几秒内看到重试 |
| `INTEGRATION_MAX_ATTEMPTS` | `.env` | 演示时 `2` | 快速进入 `FAILED`，观察 `last_error` |
| `N8N_WEBHOOK_URL` | `.env` | 指向测试工作流 | 留空即 dry-run |
| `--once` / `--interval` | worker | `--interval 5` | 控制轮询频率 |
| `-k "intake or integrations"` | pytest | – | 只跑本轮相关测试 |

重试演示步骤：把 `N8N_WEBHOOK_URL` 改成错误地址 → 提交表单 → `GET /integrations/events?status=FAILED` 查看 `last_error` 和 `attempts`。

### 6.7 本轮 28 个文件改动

| # | 文件 | 类型 | 说明 |
| --- | --- | --- | --- |
| 1 | `app/api/v1/endpoints/intake.py` | 新增 | 表单接入端点 |
| 2 | `app/api/v1/endpoints/integrations.py` | 新增 | 事件查询 + 手动重试 |
| 3 | `app/core/logging.py` | 新增 | 结构化日志配置 |
| 4 | `app/models/integration_event.py` | 新增 | Outbox 表模型 |
| 5 | `app/schemas/intake.py` | 新增 | 表单提交 / 响应模型 |
| 6 | `app/schemas/integration.py` | 新增 | 事件响应模型 |
| 7 | `app/services/intake_service.py` | 新增 | 归一化 / 抽取 / 去重 |
| 8 | `app/services/integration_service.py` | 新增 | 入队 / 投递 / 退避 |
| 9 | `app/services/integrations/__init__.py` | 新增 | 集成包初始化 |
| 10 | `app/services/integrations/sheets.py` | 新增 | Google Sheets 适配器 |
| 11 | `app/services/integrations/mailer.py` | 新增 | SMTP 邮件适配器 |
| 12 | `app/services/integrations/n8n.py` | 新增 | n8n Webhook 适配器 |
| 13 | `app/workers/__init__.py` | 新增 | worker 包初始化 |
| 14 | `app/workers/integration_worker.py` | 新增 | 重试 worker |
| 15 | `tests/test_intake.py` | 新增 | 5 个表单 / 抽取 / 去重用例 |
| 16 | `tests/test_integrations.py` | 新增 | 5 个入队 / 重试 / 统计用例 |
| 17 | `app/api/v1/router.py` | 修改 | 注册 intake、integrations 路由 |
| 18 | `app/api/v1/endpoints/webhook.py` | 修改 | 创建线索后入队并首次投递 |
| 19 | `app/core/config.py` | 修改 | 新增集成相关配置项 |
| 20 | `app/core/constants.py` | 修改 | 事件类型与事件状态常量 |
| 21 | `app/main.py` | 修改 | 日志初始化、模型注册、版本 0.2.0 |
| 22 | `app/schemas/dashboard.py` | 修改 | 响应增加 `integration_events` |
| 23 | `app/services/dashboard_service.py` | 修改 | 事件状态分组统计 |
| 24 | `requirements.txt` | 修改 | psycopg、google-auth、requests 等依赖 |
| 25 | `.env.example` | 修改 | 集成变量模板与注释 |
| 26 | `.vscode/launch.json` | 修改 | API + worker 三个调试配置 |
| 27 | `README.md` | 修改 | 新功能、接口、配置、worker 文档 |
| 28 | `docs/README.zh-CN.md` | 修改 | 中文文档同步（本文件不在提交范围） |

> 说明：`docs/CODE_CHANGES_zh.md` 与 `docs/README.zh-CN.md` 是本地学习文档，不纳入这次代码提交。

### 6.8 验证记录

- `pytest`：**38 passed**（原 28 个 + 本轮 10 个）。
- PostgreSQL 冒烟：`POST /intake/forms` → `201`，自动识别 `email / phone / name`，3 个事件全部 `SENT`，随后 `DELETE /leads/{id}` 清理测试数据。
- 启动自动建表：PG 中已存在 `integration_events`，无需手工迁移。
- 日志样例：

```text
2026-11-15 19:32:57 | INFO | app.services.integration_service | Queued 3 integration events for lead 26
2026-11-15 19:32:57 | INFO | app.services.integrations.sheets | Google Sheets is not configured, skipping append for lead 26
2026-11-15 19:32:57 | INFO | app.services.integration_service | Integration n8n.lead_created for lead 26 delivered: {'dry_run': True}
```

### 6.9 本轮学习点

| 主题 | 一句话结论 |
| --- | --- |
| 可靠投递 | Outbox 模式：事件与业务数据同事务落库，再异步投递 |
| 重试设计 | 状态、次数、下次时间、错误信息都要持久化，才能跨重启 |
| 退避策略 | `base * 2^(n-1)` + 最大次数，避免雪崩和无限重试 |
| 演示友好 | 外部依赖未配置时 dry-run，而不是启动即报错 |
| 测试隔离 | 外部适配器用 monkeypatch，测试不需要真账号 |
| 后台任务 | `BackgroundTasks` 用的是另一个 session，断言前可能没执行完 |
| 正则边界 | `(?<!\d)` / `(?!\d)` 避免从长数字串里误截手机号 |
| 时间处理 | naive UTC 同时兼容 SQLite 与 PostgreSQL |

---

## 7. 学习要点速查

| 主题 | 一句话结论 |
| --- | --- |
| 多数据库支持 | 驱动差异用 `connect_args` 条件隔离，业务代码保持不变 |
| 配置管理 | 统一走 pydantic-settings，字段名即环境变量名；别混用 `os.getenv` |
| 单一数据源 | `Literal` + `get_args()` 让类型和运行时共用一份状态列表 |
| 幂等设计 | 唯一索引 + 请求体指纹 + 同一事务，缺一不可 |
| 并发安全 | 应用层「先查再插」挡不住并发，最终靠数据库约束 |
| 测试隔离 | 内存 SQLite + `StaticPool` + `dependency_overrides`，不依赖外部服务 |
| 数据迁移 | 保留主键 + `setval` 校准序列 + 可重复执行 |
| URL 特殊字符 | `!` → `%21`，否则连接串解析会出错 |

---

## 8. 后续建议（Roadmap 摘要）

1. **Docker Compose**：把 API + PostgreSQL + n8n 编排成一个 `docker compose up` 的演示环境，Upwork 客户最容易验证。
2. **Alembic 迁移**：目前依赖 `Base.metadata.create_all()`，字段变更无法追踪。
3. **认证与权限**：当前只有 Webhook 共享密钥，业务接口完全开放。
4. **CI 流水线**：跑 pytest + ruff，防止再次出现「依赖漏写」这类问题。
5. **静态演示页**：加一个 `/demo` 表单页，客户点按钮即可看到完整自动化链路。
6. **`updated_at` 字段**：便于审计与缓存失效。
