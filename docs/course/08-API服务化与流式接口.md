# 第 8 讲：API 服务化与流式接口

> 对应笔记：第 7 章「API 接口」
> 学时：4（理论 2 + 上机 2）

---

## 一、教学目标

1. 理解 FastAPI 应用的组织：应用实例、路由、schema、依赖。
2. 掌握 **lifespan** 在应用启停时初始化/释放长连接客户端。
3. 掌握 **Depends 依赖注入**如何为每个请求装配 `QueryService` 与每请求 session。
4. 掌握 **SSE（Server-Sent Events）流式接口**：把 graph 的事件流实时推给前端。

## 二、教学重点

- lifespan 与客户端单例的配合（呼应第 3 讲）。
- 依赖注入链：从 client → repository → service。
- SSE 的数据格式与 `StreamingResponse`。

## 三、教学难点

- 异步生成器 + SSE 的 `data: {...}\n\n` 格式。
- 为什么连接型客户端在 lifespan 建、session 在 Depends 建（生命周期不同）。

---

## 四、原理精讲

### 4.1 应用入口 `backend/main.py`

```python
app = FastAPI(lifespan=lifespan)                 # 注册生命周期
app.add_middleware(CORSMiddleware,
    allow_origins=["http://localhost:5173","http://127.0.0.1:5173"], ...)  # 只放行前端
app.include_router(query_router)                 # 注册路由

@app.middleware("http")
async def assign_request_id(request, call_next):
    request_id_ctx_var.set(uuid.uuid4())         # 每个请求生成唯一 request_id（配合日志）
    return await call_next(request)
```

要点：
- `lifespan` 管启停（4.2）。
- CORS 白名单只放行前端的 5173（同源安全）。
- HTTP 中间件给每个请求注入 `request_id`，配合第 3 讲的日志，能把一次请求的所有日志串起来追踪。
- **启动方式**：`python -m backend.main`（绝对导入要求），不能 `python backend/main.py`。

### 4.2 lifespan：长连接客户端的启停

`backend/app/core/lifespan.py`：
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    embedding_client_manager.init()      # 应用启动前：建所有长连接
    qdrant_client_manager.init()
    es_client_manager.init()
    meta_mysql_client_manager.init()
    dw_mysql_client_manager.init()
    yield                                # ← 应用运行期
    await qdrant_client_manager.close()  # 应用关闭前：释放
    await es_client_manager.close()
    await meta_mysql_client_manager.close()
    await dw_mysql_client_manager.close()
```

呼应第 3 讲：**引擎/连接池等长连接，在应用启动时 init 一次、关闭时 close**，全程复用。`yield` 之前是启动逻辑，之后是关闭逻辑。

### 4.3 依赖注入链 `backend/app/api/dependencies.py`

FastAPI 的 `Depends` 把对象的“装配过程”声明出来，按需、按请求构造。本项目的依赖链：

```
get_meta_session / get_dw_session   （每请求新建 session，用 async with 自动关闭）
        ↓
get_*_repository                    （用 session/client 构造 repository）
        ↓
get_query_service                   （把所有 repository + embedding client 装进 QueryService）
```

关键代码：
```python
async def get_meta_session():
    async with meta_mysql_client_manager.session_factory() as session:   # 每请求一个新 session
        yield session

async def get_meta_mysql_repository(session: AsyncSession = Depends(get_meta_session)):
    return MetaMySQLRepository(session)

async def get_query_service(
        embedding_client = Depends(get_embedding_client),
        column_qdrant_repository = Depends(get_column_qdrant_repository),
        ... ) -> QueryService:
    return QueryService(embedding_client=embedding_client, ...)
```

精读要点（呼应第 3 讲 4.5）：
- **session 用 `Depends(get_meta_session)` 每请求新建**，`async with` 保证请求结束自动关闭——和 lifespan 里的“长连接单例”形成对比：**连接池长存、session 短命**。
- repository 是对 session/client 的薄封装，依赖注入让它们自动装配。
- `QueryService` 拿到全套依赖，成为路由可直接调用的“业务门面”。

### 4.4 查询路由 `backend/app/api/routers/query_router.py`

```python
@query_router.post("/api/query")
async def query(schema: QuerySchema, query_service: QueryService = Depends(get_query_service)):
    logger.info(f"收到查询请求，入参: {schema}")
    return StreamingResponse(query_service.query(schema.query),
                             media_type="text/event-stream")     # ← SSE
```

要点：
- 入参 `QuerySchema`（`backend/app/api/schemas/query_schema.py`，Pydantic 模型）自动做请求体校验。
- `query_service` 由 `Depends(get_query_service)` 注入（4.3 的链最终在这里被触发）。
- 返回 `StreamingResponse` + `media_type="text/event-stream"`——这是 SSE 的关键。

### 4.5 SSE 流式：QueryService 如何转发 graph 事件

`backend/app/services/query_service.py`：
```python
async def query(self, query: str):
    context = DataAgentContext(embedding_client=self.embedding_client,
                               column_qdrant_repository=self.column_qdrant_repository, ...)  # 装 Context
    state = DataAgentState(query=query)
    try:
        async for chunk in graph.astream(input=state, context=context, stream_mode="custom"):
            yield f"data: {json.dumps(chunk, ensure_ascii=False, default=str)}\n\n"   # ← SSE 格式
    except Exception as e:
        yield f"data: {json.dumps({'type':'error','message':str(e)}, ensure_ascii=False)}\n\n"
```

精读要点：
- 这里把第 6/7 讲的 `runtime.context` 真正“喂”进 graph——Context 在此装配。
- `graph.astream(..., stream_mode="custom")`：配合节点里的 `stream_writer`，逐个产出节点推送的事件（progress / result / error）。
- **SSE 格式**：每条消息是 `data: <内容>\n\n`（两个换行结尾）。这是 SSE 协议规定，浏览器 `EventSource`/前端按此解析。
- `ensure_ascii=False`：中文不转义，前端可读；`default=str`：兜底序列化（如 datetime）。
- 整个函数是**异步生成器**（`yield`），与 `StreamingResponse` 配合实现“边算边推”。

### 4.6 前后端约定的事件协议（回顾）

| type | 含义 | 示例 |
| --- | --- | --- |
| `progress` | 节点进度 | `{"type":"progress","step":"召回字段","status":"running"}` |
| `result` | 查询结果 | `{"type":"result","data":[{...}]}` |
| `error` | 错误 | `{"type":"error","message":"..."}` |

节点用 `writer(...)` 推送（第 6/7 讲），service 包成 `data: ...\n\n` 转发，前端按 type 渲染。**这套协议是前后端解耦的契约。**

---

## 五、环境与上机

### 上机任务 1：看接口文档
启动后端后打开 http://localhost:8000/docs ，找到 `POST /api/query`，看请求体 schema。

### 上机任务 2：用 curl 观察 SSE
```sh
curl -s -N -X POST http://localhost:8000/api/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"统计一下各个地区销售排行前三的产品"}'
```
逐行观察 `data: {...}`，对应第 6/7 讲的每个节点，最后是 `result`。

### 上机任务 3：追踪 request_id
连续打两次请求，看后端日志里两次请求的 `request_id` 是否不同，理解中间件注入的作用。

---

## 六、常见坑

- 前端跨域被拦：检查 CORS 白名单是否包含前端实际地址。
- SSE 没换两行（少一个 `\n`）会导致前端解析不出——格式必须 `data: ...\n\n`。
- session 没用 `async with` 会泄漏连接，压测时连接池耗尽。
- `python backend/main.py` 启动报 import 错——必须 `-m backend.main`。

---

## 七、扩展练习

### 基础级
1. 给 `QuerySchema` 加字段校验（如 query 非空、长度上限），观察非法请求返回的 422 错误。
2. 新增一个 `GET /health` 接口，返回服务运行状态（可结合第 3 讲挑战题的健康检查聚合）。

### 进阶级
3. 给 `/api/query` 加上耗时统计：在中间件里记录每个请求从开始到结束的时间，写进日志和响应头。
4. 把 SSE 换成 WebSocket 实现同样的流式效果，对比两者在“服务端单向推送”场景下的优劣。

### 挑战级（指向课程设计）
5. **会话管理（多轮对话方向）**：给接口加 `session_id`，在服务端维护每个会话的历史，使 `/api/query` 支持上下文追问。需要打通到 graph 的 State（呼应第 6 讲扩展）。
6. **限流与并发**：给接口加简单限流（如每 IP 每秒 N 次）和并发上限，压测对比加与不加的稳定性。讨论 LLM 应用为什么尤其需要限流。

---

## 八、思考题

1. 为什么连接型客户端在 lifespan 建（单例），而 session 在 Depends 建（每请求）？把 session 也做成单例会出什么问题？
2. SSE 相比“一次性返回全部结果”，对用户体验和服务端资源各有什么影响？什么场景下流式是必须的？
3. `Depends` 的依赖链是“声明式”的——路由只声明它要 `QueryService`，FastAPI 自动把整条链装配好。这种 IoC（控制反转）相比手动 new 对象有什么好处？
4. `query_service.query` 是异步生成器，一旦客户端中途断开连接，服务端的 graph 还会继续跑吗？该如何优雅处理？
