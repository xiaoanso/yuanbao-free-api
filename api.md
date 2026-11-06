# YuanBao Free API — 架构与接口说明

本文说明本服务的核心架构、登录与鉴权逻辑，以及对外 / 对内接口。

---

## 1. 项目定位

本服务是一个 **腾讯元宝 Web 能力的 OpenAI 兼容代理**：

- 对外提供类 OpenAI 的 HTTP API（`/v1/chat/completions`、`/v1/upload`）
- 对内通过无头浏览器维持元宝登录态，拦截真实请求头后转发到元宝官方接口
- 将元宝 SSE 流式结果转换为 OpenAI `chat.completion.chunk` 格式

```
客户端 (OpenAI SDK / curl)
        │  Bearer API_KEYS
        ▼
┌───────────────────────────────┐
│  YuanBao Free API (FastAPI)   │
│  · 校验 API_KEYS              │
│  · BrowserManager 取鉴权头    │
│  · 编排会话 / 聊天 / 上传     │
└───────────────┬───────────────┘
                │  携带 x-uskey 等浏览器头
                ▼
        腾讯元宝 Web API + COS
```

---

## 2. 目录与模块职责

```
app.py                          # FastAPI 入口；启动时登录，关闭时释放浏览器
src/
  config.py                     # 环境变量配置（API_KEYS、COOKIES、超时等）
  const.py                      # 对外 model 名 → 元宝 chatModelId 映射
  dependencies/auth.py          # Bearer 鉴权依赖；校验 API Key 后生成上游 headers
  routers/
    chat.py                     # POST /v1/chat/completions
    upload.py                   # POST /v1/upload
  schemas/                      # 请求/响应 Pydantic 模型
  services/
    browser/browser_manager.py  # Playwright 单例：登录、Cookie、拦截请求头
    chat/
      conversation.py           # 创建 / 删除元宝会话
      completion.py             # 调用元宝聊天流式接口
    upload/
      info.py                   # 获取 COS 上传凭证
      uploader.py               # 上传文件到 COS
  utils/
    common.py                   # generate_headers（从浏览器取头）
    chat.py                     # 消息拼接、模型映射、SSE 格式转换
    qr_utils.py                 # 二维码解码与终端打印
    upload.py                   # COS 签名头与 Media 组装
```

---

## 3. 核心架构

### 3.1 生命周期

```
启动 lifespan
  └─ browser_manager.login()
       ├─ 有 COOKIES → 注入 Cookie → 刷新页面 → 校验登录态
       │     失败则回退扫码
       └─ 无 COOKIES → 打开登录二维码 → 终端展示 → 等待扫码
关闭 lifespan
  └─ browser_manager.close()
```

浏览器为 **进程级单例**（`BrowserManager`），全程复用同一 Playwright Chromium 页面，用于：

1. 维持元宝登录 Cookie
2. 在需要时 `reload` 页面，拦截发往 `yuanbao.tencent.com/api` 的请求，捕获含 `x-uskey` 的真实请求头

### 3.2 双层鉴权

| 层级 | 凭证 | 作用 |
|------|------|------|
| 对外 | `API_KEYS`（`.env`） | 调用本服务时的 `Authorization: Bearer <key>`，可自定义任意字符串 |
| 对内 | 元宝 Cookie / 扫码会话 | 浏览器登录态；每次业务请求前由 `generate_headers()` 拦截出上游 headers |

`API_KEYS` **不是** 元宝账号密码，只保护本代理不被未授权调用。

### 3.3 登录优先级

1. **Cookie 登录（优先）**：配置 `COOKIES=hy_source=web; hy_user=...; hy_token=...`
2. **扫码登录（回退）**：未配置 Cookie，或 Cookie 无效/过期时，截取二维码并打印到终端

Cookie 获取：浏览器打开 [元宝](https://yuanbao.tencent.com/) → F12 → Application → Cookies，复制至少 `hy_user`、`hy_token`。

### 3.4 请求头获取逻辑

每次业务接口经过 `get_authorized_headers`：

1. 校验 Bearer token ∈ `API_KEYS`
2. 调用 `browser_manager.get_headers()`：
   - 给当前页面注册 route 拦截
   - `page.reload()`，等待匹配 `header_api_pattern` 且带 `x-uskey` 的请求
   - 返回捕获到的完整 headers（含 Cookie、`x-uskey` 等）
3. 后续用该 headers 调用元宝 HTTP API

### 3.5 聊天核心流程

```
POST /v1/chat/completions
  │
  ├─ 无 chat_id → POST 元宝 create conversation → 得到 chat_id
  ├─ parse_messages(messages) → prompt 字符串
  ├─ get_model_info(model) → chatModelId / supportFunctions
  ├─ POST 元宝 /api/chat/{chat_id}（stream）
  │     └─ process_response_stream → OpenAI SSE chunk
  └─ should_remove_conversation=true 时 → POST 元宝 clear conversation
```

### 3.6 上传核心流程

```
POST /v1/upload
  │
  ├─ POST 元宝 /api/resource/genUploadInfo（拿 location / 签名字段 / resourceUrl）
  ├─ PUT 腾讯云 COS（upload_host + location，带 COS 签名头）
  └─ 返回 Media（type/url/fileName/size/...）供聊天 multimedia 使用
```

---

## 4. 对外 API（用户直接调用）

**Base URL**：`http://localhost:8000`  
**鉴权**：所有业务接口均需

```http
Authorization: Bearer <API_KEYS 中的某个 key>
```

---

### 4.1 聊天完成

`POST /v1/chat/completions`

兼容 OpenAI Chat Completions 风格，**仅支持流式**（`EventSourceResponse` / SSE）。

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `model` | string | 是 | 见 [§5 模型列表](#5-支持的模型) |
| `messages` | `Message[]` | 是 | 至少一条；`{ "role", "content" }` |
| `chat_id` | string \| null | 否 | 会话 ID；省略则自动创建 |
| `should_remove_conversation` | bool | 否 | 默认 `false`；结束后是否删除会话 |
| `multimedia` | `Media[]` | 否 | 默认 `[]`；来自上传接口返回值 |

```json
{
  "model": "deepseek-v3",
  "messages": [
    { "role": "user", "content": "你好" }
  ],
  "chat_id": null,
  "should_remove_conversation": false,
  "multimedia": []
}
```

#### 响应

`Content-Type: text/event-stream`

每个 data 块为 OpenAI 风格 JSON（`chat.completion.chunk`），`choices[0].delta.content` 中为元宝原始 chunk 的 JSON 字符串；结束时发送 `finish_reason` 与 `[DONE]`。

#### curl 示例

```bash
curl -N http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-v3",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

#### OpenAI SDK 示例

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1/", api_key="sk-your-api-key-here")

stream = client.chat.completions.create(
    model="deepseek-v3",
    messages=[{"role": "user", "content": "你好"}],
    stream=True,
    extra_body={
        "chat_id": "",
        "should_remove_conversation": False,
        "multimedia": [],
    },
)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="")
```

---

### 4.2 文件上传

`POST /v1/upload`

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file.file_name` | string | 是 | 文件名 |
| `file.file_data` | string | 是 | Base64 编码的文件内容 |
| `file.file_type` | string | 是 | 如 `image`、`doc`、`excel`、`pdf` 等 |

```json
{
  "file": {
    "file_name": "demo.png",
    "file_data": "<base64...>",
    "file_type": "image"
  }
}
```

#### 响应（`Media`）

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | string | 媒体类型 |
| `docType` | string | 文档类型 |
| `url` | string | 可访问的资源 URL |
| `fileName` | string | 文件名 |
| `size` | int | 字节大小 |
| `width` | int | 宽度（非图片可为 0） |
| `height` | int | 高度（非图片可为 0） |

将该对象放入聊天请求的 `multimedia` 数组即可实现多模态提问。

---

### 4.3 错误码（常见）

| HTTP | 场景 |
|------|------|
| 401 | 缺少 Bearer token |
| 403 | API Key 不在 `API_KEYS` 中 |
| 400 | `model` 非法等参数校验失败 |
| 500 | 上游调用失败、未登录无法取头等 |

---

## 5. 支持的模型

对外 `model` → 元宝 `chatModelId` / 可选能力：

| model | 元宝 chatModelId | 额外能力 |
|-------|------------------|----------|
| `deepseek-v3` | `deep_seek_v3` | — |
| `deepseek-r1` | `deep_seek` | — |
| `deepseek-v3-search` | `deep_seek_v3` | 联网搜索 |
| `deepseek-r1-search` | `deep_seek` | 联网搜索 |
| `hunyuan` | `hunyuan_gpt_175B_0404` | — |
| `hunyuan-t1` | `hunyuan_t1` | — |
| `hunyuan-search` | `hunyuan_gpt_175B_0404` | 联网搜索 |
| `hunyuan-t1-search` | `hunyuan_t1` | 联网搜索 |

带 `-search` 的模型会在上游 body 中设置 `supportFunctions: ["supportInternetSearch"]`。

---

## 6. 内部调用的元宝 / COS 接口

用户 **不直接调用**；由服务在拿到浏览器 headers 后发起。

| 用途 | 方法 | URL | 触发时机 |
|------|------|-----|----------|
| 创建会话 | POST | `https://yuanbao.tencent.com/api/user/agent/conversation/create` | 聊天未传 `chat_id` |
| 流式聊天 | POST | `https://yuanbao.tencent.com/api/chat/{chat_id}` | 每次聊天 |
| 删除会话 | POST | `https://yuanbao.tencent.com/api/user/agent/conversation/v1/clear` | `should_remove_conversation=true` |
| 获取上传凭证 | POST | `https://yuanbao.tencent.com/api/resource/genUploadInfo` | 上传前 |
| 上传文件 | PUT | `https://{UPLOAD_HOST}{location}` | 拿到凭证后写入 COS |

### 6.1 创建会话（摘要）

```http
POST /api/user/agent/conversation/create
Content-Type: application/json

{ "agentId": "<AGENT_ID>" }
```

响应 JSON 中的 `id` 即 `chat_id`。

### 6.2 流式聊天（摘要）

```http
POST /api/chat/{chat_id}
```

主要 body 字段：

- `prompt` / `displayPrompt`：由 `messages` 拼出
- `agentId`：配置项 `AGENT_ID`（默认 `naQivTmsDa`）
- `chatModelId`：由对外 model 映射
- `multimedia`：可选附件
- `supportFunctions`：联网搜索等
- 其它固定字段：`model`、`plugin`、`version` 等（见 `completion.py`）

响应为 SSE（`data: {...}`），本服务再包装为 OpenAI chunk。

### 6.3 删除会话（摘要）

```http
POST /api/user/agent/conversation/v1/clear

{
  "conversationIds": ["<chat_id>"],
  "uiOptions": { "noToast": true }
}
```

### 6.4 上传凭证（摘要）

```http
POST /api/resource/genUploadInfo

{
  "fileName": "<name>",
  "docFrom": "localDoc",
  "docOpenId": ""
}
```

返回中的 `location`、`resourceUrl` 及签名字段用于 COS PUT。

---

## 7. 配置项

来自 `.env`（见 `.env.example`）：

| 变量 | 必填 | 说明 |
|------|------|------|
| `API_KEYS` | 是 | 本服务访问密钥，逗号分隔；Bearer 校验用 |
| `COOKIES` | 否 | 元宝 Cookie；优先登录，未配则扫码 |
| `AGENT_ID` | 否 | 默认 `naQivTmsDa` |
| `PAGE_URL` | 否 | 浏览器打开的元宝页面 |
| `UPLOAD_HOST` | 否 | COS 加速域名 |
| `PAGE_TIMEOUT` / `LOGIN_TIMEOUT` / `HEADER_TIMEOUT` 等 | 否 | 超时相关 |

---

## 8. 端到端数据流（含上传的聊天）

```
1. 客户端 POST /v1/upload（Bearer + base64 文件）
2. 服务取浏览器 headers → genUploadInfo → PUT COS → 返回 Media
3. 客户端 POST /v1/chat/completions（Bearer + messages + multimedia）
4. 服务取浏览器 headers
5. 如无 chat_id → create conversation
6. 组装 YuanBao body → stream /api/chat/{id}
7. SSE 转 OpenAI chunk 推给客户端
8. 可选 clear conversation
```

更完整的可运行示例见仓库根目录 `test.py`。

---

## 9. 设计要点小结

1. **代理而非官方 SDK**：依赖 Web 登录态与请求头拦截，存在账号风控与页面改版风险。
2. **Cookie 优先、扫码兜底**：适合无人值守部署时预置 Cookie；本地调试可扫码。
3. **API_KEYS 仅护栏**：保护代理入口；真正调元宝靠浏览器会话。
4. **会话可复用**：传入同一 `chat_id` 可延续上下文；也可用完即删。
5. **流式唯一路径**：当前聊天接口只返回 SSE，无非流式 JSON 完整响应。
