# LimeSlake-01 · 石灰熟化池作业板

厂区熟化池平面图作业基线（Flask + Jinja + Stimulus）。主界面是按厂区排布的池位瓦片，点选后在右侧抽屉登记峰值温度并改状态——不是侧栏双列表 CRUD。

## 技术栈

| 层 | 技术 |
| --- | --- |
| Web | Flask 3 · Blueprints · Flask-Login · Jinja2 · Stimulus CDN |
| 数据 | SQLAlchemy · PostgreSQL 15 |
| 部署 | Docker Compose · Gunicorn |

## 路径与端口

- **项目路径**：`d:\work\document\bytecode\claudeCodePro\LimeSlake\LimeSlake-01`
- **Web**：http://localhost:4730
- **PostgreSQL**：localhost:6130

## 演示账号

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | 管理员 |
| `worker` | `123456` | 操作工 |

登录页已预填 `admin` / `123456`。启动时 entrypoint 会建表并写入种子数据（示范厂区：**东湾石灰厂**）。

## 主界面

- **熟化池平面图**（`/board/`）：CSS 网格池位瓦片，按状态着色（注水中 / 熟化中 / 已出灰）
- 顶部厂区切换芯片（多厂时切换）
- 点击瓦片 → 右侧抽屉展示最近 `SlakeBatch`，可登记峰值温度并变更池状态
- **池号更名台**（`/rename/`）：管理员专页改池号；同厂池号唯一（应用校验 + 数据库唯一约束兜底，并发撞号仅一笔生效，另一笔中文挡下且整体回滚），更名只改池号、不动池态，平面图瓦片 / 抽屉标题 / 批次列表即时认新号
- 主导航挂「平面图 / 池号更名」；旧 `/ponds/`、`/batches/` 路由仍保留但不作为作业入口（编辑池资料页不再提供池号修改）

## 业务规则

熟化池状态不可设为「已出灰」（`drawn`），除非该池**最近一条** `SlakeBatch` 的 `peakTempC` 已记录且 **≥ 60℃**。

规则实现：`app/services/rules.py`

## 快速启动

```bash
cd d:\work\document\bytecode\claudeCodePro\LimeSlake\LimeSlake-01
docker compose up --build
```

浏览器打开 http://localhost:4730

停止：

```bash
docker compose down
```

## 目录结构

```
LimeSlake-01/
├── docker-compose.yml
├── Dockerfile
├── entrypoint.sh
├── wsgi.py
├── app/
│   ├── __init__.py          # 工厂 + seed
│   ├── models.py
│   ├── services/rules.py
│   └── blueprints/{auth,board,ponds,batches}
├── templates/
│   └── board/floor.html     # 平面图 + 抽屉
└── static/
```
