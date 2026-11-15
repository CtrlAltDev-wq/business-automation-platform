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

| 迭代 | 时间 | 提交 | 主题 |
| --- | --- | --- | --- |
| 1 | 2026-11-15 | `5dedcf1` | 项目初始化与代码体检修复 |
| 2 | 2026-11-15 | `46c88f6` | 统计（Dashboard）接口 |
| 3 | 2026-11-15 | `20de566` | 签名 + 幂等的 Webhook |
| 4 | 2026-11-15 | `0925174` | 提交 `.env.example`、忽略 `.env` |
| 5 | 2026-11-15 | *(未提交)* | 数据库切换为 PostgreSQL 并迁移数据 |

---

## 1. 迭代一：项目初始化与代码体检（`5dedcf1`）

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

## 2. 迭代二：统计接口（`46c88f6`）

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

## 3. 迭代三：Webhook 接入与幂等（`20de566`）

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

## 4. 迭代四：`.env.example` 与 `.env`（`0925174`）

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

## 5. 迭代五：SQLite → PostgreSQL（未提交，本地已生效）

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

## 6. 学习要点速查

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

## 7. 后续建议（Roadmap 摘要）

1. **Alembic 迁移**：目前依赖 `Base.metadata.create_all()`，字段变更无法追踪。
2. **认证与权限**：当前只有 Webhook 共享密钥，业务接口完全开放。
3. **`updated_at` 字段**：便于审计与缓存失效。
4. **CI 流水线**：跑 pytest + ruff，防止再次出现「依赖漏写」这类问题。
