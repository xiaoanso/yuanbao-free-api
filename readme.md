# YuanBao-Free-API ✨

一个允许您通过 OpenAI 兼容接口访问腾讯元宝的服务。

## ✨ 核心特性

✅ **完整兼容 OpenAI API 规范**
🚀 **支持主流元宝大模型**（DeepSeek/HunYuan系列）
⚡️ **流式输出 & 网络搜索功能**
🖼️ **支持上传图片或文件**
🔐 **支持 Cookie / 扫码登录**（优先 Cookie，未配置时自动扫码）
📦 **开箱即用的部署方案**（本地/Docker）

## ⚠️ 使用须知

- 本项目仅限**学习研究用途，请勿用于商业用途**
- **本项目可能导致账号被封禁风险**
- 请严格遵守腾讯元宝的[使用条款](https://yuanbao.tencent.com/)

## 🚀 快速开始

### 环境准备

```bash
# 克隆项目
git clone https://github.com/chenwr727/yuanbao-free-api.git
cd yuanbao-free-api

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium
```

### 配置环境变量

```bash
# 复制环境变量示例文件
cp .env.example .env

# 编辑 .env 文件，配置 API Keys（可选配置 COOKIES）
# 支持多个 key，用逗号分隔
# API_KEYS=sk-your-api-key-here,sk-another-api-key
# COOKIES=hy_source=web; hy_user=xxx; hy_token=yyy
```

## 🖥️ 服务端部署

### 本地运行

```bash
# 启动服务（已配置 COOKIES 则直接登录；否则终端扫码登录）
python app.py

# 服务地址：http://localhost:8000
```

### Docker 部署

```bash
# 准备配置
cp .env.example .env
# 可在 .env 中修改 PORT（默认 8300）

# 构建镜像并启动容器（名称：yuanbao-free-api）
docker compose up -d --build

# 查看日志
docker compose logs -f
```

## 🧠 支持模型

| 模型名称              | 特性说明                    |
|----------------------|-----------------------------|
| deepseek-v3          | 深度求索 V3 基础模型         |
| deepseek-r1          | 深度求索 R1 增强模型         |
| deepseek-v3-search   | 深度求索 V3 模型（带搜索功能）|
| deepseek-r1-search   | 深度求索 R1 模型（带搜索功能）|
| hunyuan              | 腾讯混元基础模型             |
| hunyuan-t1           | 腾讯混元 T1 模型             |
| hunyuan-search       | 腾讯混元模型（带搜索功能）    |
| hunyuan-t1-search    | 腾讯混元 T1 模型（带搜索功能）|

## 🔧 配置说明

### 环境变量配置

在 `.env` 文件中配置以下变量：

```bash
# 本服务访问密钥（调用 API 时 Bearer Token 校验用，非元宝登录凭证；可自定义，多个用逗号分隔）
API_KEYS=sk-your-api-key-here,sk-another-api-key

# 元宝登录 Cookie（推荐；优先于扫码登录）
# 登录 yuanbao.tencent.com 后，从 DevTools > Application > Cookies 复制
# 至少包含 hy_user、hy_token
# COOKIES=hy_source=web; hy_user=xxx; hy_token=yyy

# Agent ID（默认为 naQivTmsDa，一般无需修改）
# AGENT_ID=naQivTmsDa

# 腾讯元宝页面 URL（默认为固定地址，一般无需修改）
# PAGE_URL=https://yuanbao.tencent.com/chat/naQivTmsDa

# 文件上传域名（默认为固定地址，一般无需修改）
# UPLOAD_HOST=hunyuan-prod-1258344703.cos.accelerate.myqcloud.com
```

### 认证机制

本项目使用浏览器自动化方式获取认证参数，登录优先级如下：

1. **Cookie 登录（优先）**：`.env` 中配置了 `COOKIES` 时，启动后注入 Cookie 并验证登录态
2. **扫码登录（回退）**：未配置 Cookie，或 Cookie 无效/过期时，在终端展示二维码扫码登录
3. 登录成功后自动拦截认证请求头（x-uskey 等）

**获取 Cookie**：打开 [腾讯元宝](https://yuanbao.tencent.com/)，登录后按 F12 → Application → Cookies，复制 `hy_user`、`hy_token`（建议一并带上 `hy_source=web`）。

## 🌟 应用案例

[FinVizAI](https://github.com/chenwr727/FinVizAI) 实现多步骤金融分析工作流：
- 实时资讯搜索分析
- 市场趋势数据集成
- 结构化报告生成

[AI-Short-Video-Engine](https://github.com/chenwr727/AI-Short-Video-Engine) 一个基于 AI 的智能视频生成平台：
- 支持文章链接或主题文本输入（支持联网搜索）
- 自动完成内容理解与脚本生成
- 素材匹配、语音合成与视频剪辑一体化输出

## 📜 开源协议

MIT License © 2025

## 🤝 参与贡献

欢迎通过以下方式参与项目：
1. 提交 Issue 报告问题
2. 创建 Pull Request 贡献代码
3. 分享你的集成案例

## 🙏 致谢

- [Tencent YuanBao](https://yuanbao.tencent.com/) - 提供强大的 AI 能力
- [FastAPI](https://fastapi.tiangolo.com/) - 现代化的 Python Web 框架
- [Playwright](https://playwright.dev/) - 强大的浏览器自动化工具
