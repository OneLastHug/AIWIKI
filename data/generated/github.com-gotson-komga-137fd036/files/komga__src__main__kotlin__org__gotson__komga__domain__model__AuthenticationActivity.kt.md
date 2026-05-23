# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/AuthenticationActivity.kt

## 它负责什么

`AuthenticationActivity` 是一个很轻量的领域数据模型，用来记录“某次认证尝试”的完整上下文。根据当前文件和调用方片段推断，它既承载成功登录，也承载失败登录的审计信息，核心用途是留痕、查询和清理，而不是参与认证判断本身。

它记录的不是“用户当前是否登录”，而是“曾经发生过一次什么样的认证事件”。因此它更像审计日志条目，服务于后台管理、用户自查、风控排查和定期清理。

## 关键组成

这个文件只有一个 `data class`，没有方法，所有行为都在调用方和持久化层完成。

`AuthenticationActivity` 的字段含义如下：

- `userId: String?`  
  关联到 `KomgaUser` 的用户 ID。成功登录时通常有值，失败时可能通过邮箱反查到用户后补上，也可能为空。

- `email: String?`  
  认证时使用的邮箱。对用户名密码登录、OAuth2 登录等通常有意义；对 API Key 失败场景，调用方会把它置空。

- `apiKeyId: String?`  
  如果这次认证是通过 API Key 触发，这里记录 API Key 的 ID。

- `apiKeyComment: String?`  
  API Key 的备注信息，或者在 API Key 失败时作为 principal 的替代信息记录下来。

- `ip: String?`  
  发起认证请求的客户端 IP。

- `userAgent: String?`  
  发起认证请求的浏览器或客户端标识。

- `success: Boolean`  
  认证是否成功。这是这个模型里最关键的业务标志。

- `error: String?`  
  失败原因，通常来自认证异常消息；成功时一般为空。

- `dateTime: LocalDateTime = LocalDateTime.now()`  
  记录时间，默认取当前时间。根据 DAO 的映射逻辑，落库和读回时还会做时区转换。

- `source: String?`  
  认证来源标签，例如 `Password`、`ApiKey`、`RememberMe`、`OAuth2:xxx`。这个字段主要帮助区分认证通道。

从结构上看，它是一个纯数据容器，几乎没有领域行为，所有约束都依赖调用方自觉构造。

## 上下游关系

上游主要有三类：

1. `org.gotson.komga.infrastructure.security.LoginListener`  
   这是最主要的写入来源。它监听 Spring Security 的认证成功/失败事件，然后组装 `AuthenticationActivity` 再调用仓储插入。

2. `org.gotson.komga.infrastructure.jooq.main.AuthenticationActivityDao`  
   这是持久化实现。它负责把 `AuthenticationActivity` 和数据库表 `AUTHENTICATION_ACTIVITY` 互相转换。

3. `org.gotson.komga.domain.service.KomgaUserLifecycle`  
   在删除用户时，会调用 `authenticationActivityRepository.deleteByUser(user)` 清掉这类历史记录。

下游主要有两类：

1. `org.gotson.komga.interfaces.api.rest.dto.AuthenticationActivityDto`  
   API 层不会直接暴露领域模型，而是把它转换成 DTO 返回给前端或外部调用者。

2. `org.gotson.komga.interfaces.api.rest.UserController`  
   这里提供查询接口，包括当前用户的认证历史、管理员查看全局历史、查看某个用户最近一次认证活动。

另外还有一个定时清理入口：

- `org.gotson.komga.interfaces.scheduler.AuthenticationActivityCleanupController`  
  它会定期删除一个月以前的认证活动，说明这个模型是有保留期限的审计数据，而不是永久记录。

## 运行/调用流程

根据当前片段推断，典型流程大致是这样：

1. 用户发起登录，Spring Security 产生认证成功或失败事件。
2. `LoginListener` 监听事件，提取用户、邮箱、API Key、IP、User-Agent、来源、错误信息等。
3. `LoginListener` 构造一个 `AuthenticationActivity` 对象。
4. 通过 `AuthenticationActivityRepository.insert(activity)` 写入数据库。
5. 查询时，`UserController` 或其他服务通过 `AuthenticationActivityRepository` 读出活动记录。
6. `AuthenticationActivityDao` 把数据库行映射回 `AuthenticationActivity`，其中 `dateTime` 会做时区转换。
7. API 层再调用 `toDto()`，把领域对象转成 `AuthenticationActivityDto`，并把时间转成 UTC 格式输出。
8. 定时任务 `AuthenticationActivityCleanupController` 会按时间删除旧记录。
9. 删除用户时，`KomgaUserLifecycle` 也会顺带删除该用户关联的认证活动。

这条链路说明：`AuthenticationActivity` 是一条贯穿“事件监听 -> 持久化 -> 查询展示 -> 定期清理”的日志型模型。

## 小白阅读顺序

如果是第一次读这块代码，建议按下面顺序看：

1. 先看 `AuthenticationActivity.kt`  
   先确认它有哪些字段，理解它就是一条审计记录。

2. 再看 `LoginListener.kt`  
   这里能直接看到这个对象是怎么被组装出来的，最容易理解各字段的业务含义。

3. 再看 `AuthenticationActivityRepository.kt`  
   理解它支持哪些查询和删除操作，知道这个模型的生命周期边界。

4. 再看 `AuthenticationActivityDao.kt`  
   这里能看到它如何和数据库表对应，尤其是排序、分页、时间转换、按用户查询。

5. 再看 `AuthenticationActivityDto.kt` 和 `UserController.kt`  
   这一步能理解前端看到的数据长什么样，以及哪些接口会消费它。

6. 最后看 `AuthenticationActivityCleanupController.kt` 和 `KomgaUserLifecycle.kt`  
   这一步补上清理逻辑，理解它不是无限增长的数据表。

## 常见误区

- 把它当成“登录状态”对象。  
  其实它记录的是历史事件，不是 session，也不是当前在线状态。

- 以为 `success = false` 就一定没有 `userId`。  
  不一定。失败时如果还能从邮箱反查到用户，`userId` 仍可能有值。

- 以为 `email` 和 `apiKeyComment` 一定同时存在。  
  不是。它们会根据认证方式不同而取不同值，某些场景下其中一个会为空。

- 忽略 `source` 字段。  
  它不是装饰字段，排查时很重要，因为它能区分是密码、API Key、OAuth2 还是记住我登录。

- 以为 `dateTime` 直接就是最终输出时间。  
  不是。DAO 读取时会做时区转换，DTO 输出时又会转成 UTC，所以展示层和存储层的时间语义不完全一样。

- 误以为这个类里有业务逻辑。  
  实际上它只是数据结构，真正的规则在 `LoginListener`、DAO、Controller 和清理任务里。

- 认为认证活动会永久保留。  
  事实上仓库里已经有按月清理逻辑，删除用户时也会同步删除相关记录。
