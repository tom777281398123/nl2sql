# 教案详案 · 第 8 讲：API 服务化与流式接口

> 教师授课用逐段细案，配合 `08-API服务化与流式接口.md`（学生教案）使用。
> 体例：⏱ 时间 / 🗣 讲稿 / ✍ 板书 / ❓ 提问 / 💻 上机 / ⚠ 预案。

---

## 一、本讲定位与教学法说明

- **性质**：把命令行里的智能体，包装成真正的 Web 服务。建造“支柱三：服务化”。
- **核心矛盾**：学生看到的智能体一直在命令行跑；要让他们理解 Web 服务的两个关键工程问题——**资源生命周期管理**（lifespan + Depends）和**流式传输**（SSE）。
- **必须钉死的认知**：
  1. **长连接 lifespan 建、session Depends 每请求建**（回收第 3 讲，这里看实现）。
  2. **SSE 的格式 `data: {...}\n\n`** 与异步生成器“边算边推”。
  3. **节点的 writer → service 包成 SSE → 前端按 type 渲染** 这条事件链。
- **教学法**：顺着“一次请求的旅程”讲——入口→生命周期→依赖装配→流式产出。**跟着请求走一遍**。
- **总时长**：4 学时（理论约 80 分钟 + 上机约 100 分钟）。

---

## 二、课时分配总览

| 段落 | 内容 | 时长 |
| --- | --- | --- |
| 0 | 承上：从命令行到 Web 服务 | 6 min |
| 1 | 应用入口 main.py（路由/CORS/中间件） | 14 min |
| 2 | lifespan：长连接启停 | 12 min |
| 3 | Depends 依赖注入链（难点） | 20 min |
| 4 | SSE 流式：service 转发 graph 事件（重点） | 20 min |
| 5 | 事件协议回顾 + 小结 | 8 min |
| —— | 课间 | 10 min |
| 6 | 上机：看 docs / curl SSE / 追 request_id | 90 min |
| 7 | 作业与预告 | 10 min |

---

## 三、逐段细案（理论部分）

### 段落 0 · 承上：从命令行到 Web 服务（6 min）

⏱ 0:00–0:06

🗣 **讲稿**：
- “第 6、7 讲，智能体已经能从一句话跑到结果——但都在命令行 `python -m ... graph` 里。今天把它包成真正的 Web 服务：一个 HTTP 接口，前端能调，结果**流式**推回去。”
- 抛两个今天要解决的工程问题：“① 数据库连接这种‘贵资源’，在 Web 服务里什么时候建、什么时候放？② 智能体跑十几秒，怎么让用户**实时**看到进度，而不是干等？”

✍ **板书（主板，保留）**：
```
支柱三: 服务化 (命令行 → Web服务)
两个工程问题:
  ① 贵资源(DB连接)何时建/放? → lifespan + Depends
  ② 长耗时怎么实时反馈? → SSE 流式
```

---

### 段落 1 · 应用入口 main.py（14 min）

⏱ 0:06–0:20

🗣 **讲稿**：打开 `backend/main.py`：
```python
app = FastAPI(lifespan=lifespan)                          # ① 注册生命周期
app.add_middleware(CORSMiddleware,
    allow_origins=["http://localhost:5173","http://127.0.0.1:5173"], ...)  # ② CORS白名单
app.include_router(query_router)                          # ③ 注册路由

@app.middleware("http")
async def assign_request_id(request, call_next):
    request_id_ctx_var.set(uuid.uuid4())                  # ④ 每请求生成 request_id
    return await call_next(request)
```
🗣 四个讲点：
1. **lifespan**：管资源启停，段落 2 详讲。
2. **CORS 白名单**：“只放行前端的 5173。**为什么要白名单？**——浏览器跨域安全机制，不放行前端就调不通。这也是为什么第 9 讲前端必须跑在 5173。”
3. **路由注册**：把 `/api/query` 挂上。
4. **HTTP 中间件 + request_id**（回收第 3 讲日志）：“每个请求进来生成一个唯一 id，注入日志。**作用**：一次请求会经过十几个节点、打几十条日志，靠 request_id 才能把它们串成一条线追踪。”

🗣 **启动方式**（再次强调）：“`python -m backend.main`，不能 `python backend/main.py`——绝对导入要求。这点从第 1 讲念叨到现在。”

✍ **板书（副板）**：
```
main.py: FastAPI(lifespan) + CORS白名单(只放5173) + 路由 + 中间件(request_id)
启动: python -m backend.main
```

---

### 段落 2 · lifespan：长连接启停（12 min）

⏱ 0:06–0:20 → 0:20–0:32

> 钉死认知 1 的前半（“长连接 lifespan 建”）。

🗣 **讲稿**：打开 `backend/app/core/lifespan.py`：
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    embedding_client_manager.init()      # 启动前: 建所有长连接(连接池/ES/Qdrant客户端)
    qdrant_client_manager.init()
    es_client_manager.init()
    meta_mysql_client_manager.init()
    dw_mysql_client_manager.init()
    yield                                # ← 应用运行期
    await qdrant_client_manager.close()  # 关闭前: 释放
    ...
```
🗣 讲透“为什么在这里建”（回收第 3 讲）：
> “第 3 讲我们说过——连接池、ES/Qdrant 客户端这些**长连接，建立成本高，应该启动建一次、全程复用**。lifespan 就是干这个的地方：`yield` 之前是启动逻辑（建连接），`yield` 之后是关闭逻辑（释放）。整个应用生命周期内，这些连接只建一次。”

❓ **提问（埋认知 1 的后半）**：“连接池在这儿建了一次。那每个请求要用的数据库 session 呢？也在这儿建吗？”（引导：不是！session 不能共享——段落 3 揭晓。）

✍ **板书（重点）**：
```
lifespan: yield前=启动建长连接 / yield后=关闭释放
长连接(连接池/ES/Qdrant) → 应用级,只建一次,复用 (第3讲)
那 session 呢? → 段落3
```

---

### 段落 3 · Depends 依赖注入链（难点，20 min）

⏱ 0:32–0:52

> 钉死认知 1 的后半 + 揭示 IoC 的优雅。本讲最“工程味”的一段。

🗣 **讲稿**：打开 `backend/app/api/dependencies.py`，先画依赖链：
```
get_meta_session/get_dw_session  (每请求新建session, async with自动关)
        ↓
get_*_repository                 (用session/client构造repository)
        ↓
get_query_service                (把所有repository+embedding装进QueryService)
```
看关键代码：
```python
async def get_meta_session():
    async with meta_mysql_client_manager.session_factory() as session:  # ← 每请求一个新session
        yield session                                                   # ← yield后async with自动关闭

async def get_meta_mysql_repository(session = Depends(get_meta_session)):
    return MetaMySQLRepository(session)

async def get_query_service(embedding_client=Depends(get_embedding_client),
                            column_qdrant_repository=Depends(get_column_qdrant_repository),
                            ...) -> QueryService:
    return QueryService(...)
```
🗣 **回收认知 1（揭晓段落 2 的提问）**：
> “看 `get_meta_session`——它用 `async with session_factory()` **每个请求新建一个 session**，请求结束 `async with` 自动关闭。对比 lifespan 里的连接池——**连接池长存、session 短命**。这正是第 3 讲那句‘engine 单例、session 每请求’的实现。`Depends` + `async with` 优雅地做到了‘每请求一个、用完自动关’。”

🗣 **讲 IoC 的好处（口头禅）**：
> “路由只需声明‘我要一个 QueryService’，FastAPI 自动把整条链装配好——session→repository→service，还自动管 session 的关闭。**不用 Depends 会怎样？**——你得在每个路由里手动 new session、new 一堆 repository、最后 try/finally 关 session，又长又易漏关。Depends 把这些都自动化了，这叫**控制反转（IoC）**。”

❓ **提问（第 8 讲思考题 3）**：“这种‘声明式装配’相比手动 new 对象，好处是什么？”（自动装配链、自动管生命周期、便于测试 override、路由只关心‘要什么’。）

✍ **板书（重点）**：
```
Depends 依赖链: session → repository → QueryService
get_meta_session: async with 每请求新建session,自动关
  ⇒ 兑现第3讲"engine单例/session每请求"
IoC(控制反转): 路由只声明"要QueryService", 框架自动装配+管生命周期
  (手动new则要自己建链+try/finally关session,易漏)
```

---

### 段落 4 · SSE 流式：service 转发 graph 事件（重点，20 min）

⏱ 0:52–1:12

> 钉死认知 2、3。本讲的高潮——把第 6/7 讲一路看到的 `writer` 变成前端能收的流。

🗣 **先看路由**：打开 `backend/app/api/routers/query_router.py`：
```python
@query_router.post("/api/query")
async def query(schema: QuerySchema, query_service = Depends(get_query_service)):
    return StreamingResponse(query_service.query(schema.query),
                             media_type="text/event-stream")     # ← SSE 关键
```
🗣 两点：`QuerySchema` 自动校验请求体；返回 `StreamingResponse` + `media_type="text/event-stream"`——这就是 SSE。

🗣 **再看 service（核心）**：打开 `backend/app/services/query_service.py`：
```python
async def query(self, query: str):
    context = DataAgentContext(embedding_client=self.embedding_client,
                               column_qdrant_repository=self.column_qdrant_repository, ...)  # 装Context
    state = DataAgentState(query=query)
    try:
        async for chunk in graph.astream(input=state, context=context, stream_mode="custom"):
            yield f"data: {json.dumps(chunk, ensure_ascii=False, default=str)}\n\n"  # ← SSE格式
    except Exception as e:
        yield f"data: {json.dumps({'type':'error','message':str(e)}, ...)}\n\n"
```
🗣 **逐点讲透**：
1. **Context 在这里装配**（回收第 6 讲）：“第 6/7 讲节点里 `runtime.context[...]` 取的工具，就是在这一行真正塞进去的。依赖注入的 repository 们，到这里组装成 Context 喂给 graph。”
2. **`graph.astream(stream_mode="custom")`**（回收第 7 讲）：“配合每个节点里的 `writer`，逐个产出节点推的事件（progress/result/error）。`async for` 一边算一边拿。”
3. **SSE 格式（钉死认知 2）**：
   > “每条消息是 `data: <内容>\n\n`——**两个换行**结尾，这是 SSE 协议规定。少一个 `\n` 前端就解析不出。`ensure_ascii=False` 让中文不转义、前端可读；`default=str` 兜底序列化 datetime 之类。”
4. **异步生成器 = 边算边推（钉死认知 2）**：“这个函数是 `yield` 的生成器，配合 `StreamingResponse`，实现‘算出一步推一步’，而不是憋到最后一次性返回。”

✍ **板书（重点框起来）**：
```
┌──────────────────────────────────────────────┐
│ 节点writer → service包成 data:{...}\n\n → 前端 │  (SSE事件链)
└──────────────────────────────────────────────┘
路由: StreamingResponse + media_type=text/event-stream
service: 装Context喂graph.astream(custom) → async for → yield SSE
SSE格式: data: ...\n\n (两个换行!) ; ensure_ascii=False
异步生成器 = 边算边推(不憋到最后)
```

---

### 段落 5 · 事件协议回顾 + 小结（8 min）

⏱ 1:12–1:20

🗣 **事件协议（钉死认知 3，画全链）**：
```
type=progress  {"step":"召回字段","status":"running"/"success"/"error"}  节点进度
type=result    {"data":[{...}]}                                          查询结果
type=error     {"message":"..."}                                          错误
```
> “节点用 `writer` 推（第 6/7 讲）→ service 包成 SSE 转发（今天）→ 前端按 type 渲染（第 9 讲）。**这套协议是前后端解耦的契约**——前端不用懂智能体内部，只认这三种 type。”

🗣 **小结三句**：
1. lifespan 建长连接、Depends 每请求建 session（生命周期不同）。
2. SSE = `data:...\n\n` + 异步生成器，边算边推。
3. writer → service → 前端，事件协议是解耦契约。

❓ 留作上机：“用 curl 看 SSE 一行行出来，对照第 6/7 讲的节点。”

---

## 四、上机部分细案（90 min）

⏱ 1:30–3:00

### 💻 上机任务 1：看接口文档（20 min）
启动后端，浏览器开 http://localhost:8000/docs ，找 `POST /api/query`，看 `QuerySchema` 请求体。
❓ 检查点：试着发一个空 query，看返回什么（体会 schema 校验）。

### 💻 上机任务 2：curl 观察 SSE（40 min，核心）
```sh
curl -s -N -X POST http://localhost:8000/api/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"统计一下各个地区销售排行前三的产品"}'
```
**分步骤**：
1. 观察输出是一行行 `data: {...}`。
2. 让学生**逐行对照第 6/7 讲的节点**：哪行是“召回字段 running”、哪行是“生成SQL success”、最后哪行是 `type:result`。
3. 数一数：从第一个 progress 到最后 result，一共多少个事件？
❓ 检查点：“为什么是流式一行行出来，而不是等十几秒一次性返回一大坨？这对用户体验意味着什么？”

### 💻 上机任务 3：追踪 request_id（30 min）
**分步骤**：
1. 连续发两次查询请求。
2. 看后端日志：
   ```sh
   grep request_id logs/app_$(date +%Y%m%d).log | tail -40
   ```
   （或观察日志里两次请求的标识。）
3. 确认两次请求的 request_id 不同，理解中间件“每请求一个 id”的作用——能把一次请求的所有节点日志串起来。

⚠ **进阶可选**：用浏览器开发者工具 Network 面板看 `/api/query` 的 EventStream，比 curl 更直观（为第 9 讲前端铺垫）。

---

## 五、作业与下讲预告（10 min）

🗣 **布置作业**：
- 必做（⭐）：练习 1（给 QuerySchema 加校验）+ 练习 2（加 GET /health 接口）。
- 推荐（⭐⭐）：练习 3（中间件加请求耗时统计，落日志/响应头）。
- **指向大作业（⭐⭐⭐）：练习 5 会话管理**（多轮对话方向，加 session_id + 服务端历史 + 打通 graph State）或 练习6 限流并发。
- 思考题 1、3、4 书面作答。

🗣 **下讲预告**：“最后一讲，我们把前端接上——你一直用 curl 看的那些 `data:` 事件，前端会渲染成进度条和结果表。然后做全链路串讲、故障演练，并正式启动你的**课程设计大作业**。”

---

## 六、本讲常见问题预案

| 学生可能问 | 应对 |
| --- | --- |
| CORS 是什么/为什么要白名单 | 浏览器跨域安全;不放行前端调不通;故前端必须5173 |
| 为什么 session 不在 lifespan 建 | session有事务态,每请求一个;lifespan建会变共享单例→串扰 |
| SSE 和 WebSocket 区别 | SSE 服务端单向推,够用且简单;WS 双向,本场景不需要 |
| data 后为什么两个换行 | SSE协议规定 \n\n 分隔消息,少一个前端解析不出 |
| 客户端断开后graph还跑吗 | 默认下次写入断开连接才感知;可用is_disconnected优雅处理(思考题4) |
| python backend/main.py 报错 | 必须 -m backend.main |

---

## 七、板书最终态

```
支柱三 服务化: 命令行→Web服务; 两问: 资源生命周期 + 流式

main.py: FastAPI(lifespan)+CORS白名单(5173)+路由+中间件(request_id)
lifespan: yield前建长连接/yield后释放 (连接池只建一次,第3讲)

【难点】Depends链: session(每请求async with自动关)→repository→QueryService
        兑现"engine单例/session每请求"; IoC:声明式装配,自动管生命周期

【重点】SSE: 节点writer→service包 data:{...}\n\n→前端
        StreamingResponse(text/event-stream); astream(custom)+异步生成器边算边推
        Context在service装配(第6讲取的工具来源)

事件协议: progress/result/error = 前后端解耦契约
```
