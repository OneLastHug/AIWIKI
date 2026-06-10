# 文件：platform/reworkd_platform/web/api/router.py
## 一句话定位
这个文件是 Web API 的总装配点，负责把多个子模块的 `FastAPI` 路由聚合成一个统一的 `api_router`，供应用入口一次性挂载到 `/api` 下。它本身不处理业务逻辑，只定义 API 分组和路径前缀。

## 它暴露/定义了什么
它只暴露一个核心对象：`api_router = APIRouter()`。随后通过多次 `include_router()` 把 `monitoring`、`agent`、`models`、`auth`、`metadata` 五个子路由接进来，并分别加上 `prefix` 和 `tags`。根据当前片段推断，它不定义额外函数或类，职责就是路由编排。

## 谁调用它
最直接的调用者是 `platform/reworkd_platform/web/application.py` 里的 `get_app()`。那里会执行 `app.include_router(router=api_router, prefix="/api")`，把这里组装好的总路由挂到应用实例上。进一步来说，运行时所有访问 `/api/...` 的 HTTP 请求，最终都会经过这个文件组织出来的路由树。

## 它调用谁
它调用的是各子模块导出的 `router`，包括 `reworkd_platform.web.api.monitoring`、`agent`、`models`、`auth`、`metadata`。这些模块通常在各自的 `__init__.py` 中把 `views.py` 里的 `router` 重新导出，因此这里实际上是在组合“已定义好的端点集合”。

## 核心流程
核心流程很简单：先创建一个总 `APIRouter`，再把各业务域的路由按模块接入。接入时使用不同的 `prefix`，例如 `/monitoring`、`/agent`、`/models`、`/auth`、`/metadata`，同时用 `tags` 控制 OpenAPI 文档中的分组展示。最终在应用层再统一加上 `/api` 前缀，所以对外路径会变成类似 `/api/agent/...`、`/api/auth/...` 这种层级结构。这个设计把“路由聚合”和“业务实现”分开，入口文件只负责拼装。

## 关键函数的高层作用
这里没有自定义业务函数，真正的关键动作是几次 `api_router.include_router(...)`。它们的高层作用分别是：
- `monitoring`：暴露健康检查、状态类接口，通常用于运维探活。
- `agent`：暴露与智能体执行、分析、聊天等相关接口。
- `models`：暴露模型信息查询接口。
- `auth`：暴露认证、回调、组织信息等接口。
- `metadata`：暴露平台元数据相关接口。  
这些作用主要从子模块命名和其 `views.py` 中的装饰器路由可以直接看出来。

## 修改风险
这个文件改动的风险主要在“路径编排”而不是“业务逻辑”。一旦改错 `prefix`，外部调用路径就会整体变化，前端、网关、文档和测试都可能一起失效。`tags` 改动虽然不影响运行，但会影响 Swagger/OpenAPI 的分组展示，容易让接口维护者误判结构。新增或移除子路由时，还要注意和子模块 `__init__.py` 的导出保持一致，否则会出现导入失败或接口丢失。另一个风险是路径冲突：如果不同子路由下的具体端点重复，而上层前缀又调整不当，可能导致覆盖或歧义。总体上这是一个低代码量、但高联动性的入口文件，改动应优先检查应用挂载后的最终 URL。
