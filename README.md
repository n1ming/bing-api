# 🔍 Bing Search API

[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![API Key](https://img.shields.io/badge/API%20Key-不需要-success)]()

免密钥的 Bing 搜索接口。支持**国内版 / 国际版**双引擎、**HTML / RSS** 双协议、
**真实翻页**、搜索语法，提供 HTTP API、Python 客户端与 CLI 三种使用方式。

## ✨ 特性

- 🔑 **无需 API Key**，无需登录，开箱即用
- 🌏 **双引擎**：国内版 `cn.bing.com`（直连）/ 国际版 `www.bing.com`（需海外代理，或用 `ensearch` 直连取国际结果）
- 📄 **真实翻页**：`page` 参数直达任意页码
- 🧭 **搜索语法**：`intitle:` `"短语"` `-排除` `OR` …
- 🔗 结果含真实 URL（自动解码国际版跳转链接）、摘要、日期、来源域名
- 🎭 自动模拟浏览器 TLS 指纹（`site:` 等高级语法需要）
- ⚡ 内置 60s 结果缓存与自动重试

## 📦 安装

```bash
pip install -r requirements.txt
# 若需 site: 语法完整生效, 确保安装浏览器指纹库:
pip install curl_cffi
```

## 🚀 快速开始

### 启动 HTTP 服务

```bash
python api.py --port 8000
```

启动后访问 `http://127.0.0.1:8000/docs` 查看交互式文档。

### CLI

```bash
python bing_search.py "python 教程"                          # 国内版
python bing_search.py "openai gpt" --engine global          # 国际版
python bing_search.py "openai gpt" --engine cn --ensearch   # 国内直连取国际结果
```

### Python

```python
from bing_search import BingSearch

bs = BingSearch("cn")
data = bs.search("python 教程", count=10)

for r in data["results"]:
    print(r.rank, r.title, r.url, r.date)
```

## 📡 HTTP API

### `GET /search`

执行一次搜索。

#### 请求参数

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `q` | string | **必填** | 搜索词 |
| `engine` | string | `cn` | `cn` 国内版 / `global` 国际版 |
| `protocol` | string | `html` | `html`（字段全）/ `rss`（轻量） |
| `count` | int | `10` | 返回条数，1–25 |
| `page` | int | `1` | 页码，1–20 |
| `ensearch` | bool | `false` | 仅 `engine=cn`：强制返回国际结果（无需代理） |
| `mkt` | string | 引擎默认 | 市场覆盖，如 `en-US`、`zh-CN`（国际版默认 `en-US`） |
| `safe` | string | - | 安全搜索：`off` / `moderate` / `strict` |
| `proxy` | string | - | 本次请求使用的代理地址 |
| `cache` | bool | `true` | 是否使用 60s 结果缓存 |

#### 请求头

| Header | 说明 |
|---|---|
| `X-Bing-Cookie` | 可选。注入浏览器 Cookie（复用登录态/自定义会话） |

#### 请求示例

```bash
# 国内版第一页
curl "http://127.0.0.1:8000/search?q=python%20%E6%95%99%E7%A8%8B&engine=cn&count=10"

# 国际版第 2 页（需设置环境变量 BING_PROXY）
curl "http://127.0.0.1:8000/search?q=openai%20gpt&engine=global&page=2"

# 国内直连拿国际结果
curl "http://127.0.0.1:8000/search?q=openai%20gpt&engine=cn&ensearch=true&protocol=rss"
```

#### 响应示例

```json
{
  "query": "python 教程",
  "engine": "cn",
  "protocol": "html",
  "count": 10,
  "total_count": "174,000",
  "page": 1,
  "results": [
    {
      "rank": 1,
      "title": "Python 基础教程 | 菜鸟教程",
      "url": "https://www.runoob.com/python/python-tutorial.html",
      "raw_link": "https://www.runoob.com/python/python-tutorial.html",
      "snippet": "本教程适合想从零开始学习 Python 编程语言的开发人员…",
      "display_url": "https://www.runoob.com",
      "source": "www.runoob.com",
      "date": "2026年9月9日",
      "pub_date": null,
      "engine": "cn",
      "protocol": "html"
    }
  ],
  "meta": {
    "took_ms": 210,
    "mkt": "zh-CN",
    "ensearch": false,
    "channel": "html",
    "note": "…"
  }
}
```

#### 响应字段

| 字段 | 说明 |
|---|---|
| `results[].url` | 真实结果 URL（国际版跳转链接已自动解码） |
| `results[].snippet` | 摘要（日期已剥离至 `date` 字段） |
| `results[].display_url` | 页面展示用的站点 URL |
| `results[].source` | 结果来源域名 |
| `results[].date` | 结果日期（HTML 协议，可能为空） |
| `results[].pub_date` | RSS 发布时间（仅 RSS 协议） |
| `meta.channel` | 实际数据通道：`html` / `html-activated` / `snrjson-xhr` / `rss-fallback` |
| `meta.fallback` | 存在时表示国际版代理不可用，已自动降级 |

### `GET /compare`

同一查询同时请求两个引擎并对比结果差异。

| 参数 | 类型 | 说明 |
|---|---|---|
| `q` | string | **必填**，搜索词 |
| `protocol` | string | `html` / `rss`，默认 `html` |
| `mkt` | string | 国际版市场覆盖 |

```bash
curl "http://127.0.0.1:8000/compare?q=openai%20gpt"
```

响应在 `cn` / `global` 下分别给出结果集，以及 `overlap_urls`（两版重叠链接）、
`cn_only` / `global_only`（各自独有数量）。

### `GET /meta`

返回两版引擎的配置说明与使用限制（自我描述接口，无需参数）。

## 🐍 Python 客户端

### `BingSearch`

```python
BingSearch(
    engine="cn",          # "cn" 国内版 / "global" 国际版
    proxy=None,           # 代理地址；global 缺省读环境变量 BING_PROXY
    timeout=25,           # 单请求超时（秒）
    mkt=None,             # 市场，缺省 cn→zh-CN / global→en-US
    language=None,        # Accept-Language，缺省按引擎
    cookies=None,         # 注入 Cookie："K1=V1; K2=V2" / @cookies.txt / dict
)
```

### `search()`

```python
bs.search(
    query,                # 搜索词
    count=10,             # 返回条数（1–50）
    protocol="html",      # "html" 或 "rss"
    ensearch=None,        # cn 版强制国际结果
    safe_search=None,     # "off" / "moderate" / "strict"
    first=None,           # 结果起始序号（翻页偏移）
)
```

返回 `dict`：`query` / `engine` / `protocol` / `count` / `total_count` / `results` / `meta`；
`results` 为 `BingResult` 列表，字段同上方响应表，`.as_dict()` 可直接序列化。

### `set_cookies()`

动态注入/更新 Cookie，三种形式均可：

```python
bs.set_cookies({"SRCHHPGUSR": "..."})   # dict
bs.set_cookies("K1=V1; K2=V2")          # 浏览器复制的字符串
bs.set_cookies("@cookies.txt")          # cookies.txt 文件（Netscape 格式亦可）
```

## 🧭 搜索语法

语法直接写在 `q` 里即可，客户端自动处理会话：

| 语法 | 示例 | 状态 |
|---|---|---|
| `site:` | `site:zhihu.com python 教程` | ✅ 国内版+国际版均可（见下方 GEC 配置；亦存在服务端可用性波动，建议 `source` 过滤兜底） |
| `intitle:词` | `intitle:量子计算` | ✅ 符合率 100% |
| `inbody:词` | `inbody:碳中和 site:gov.cn` | ✅ 正文过滤真实生效 |
| `"精确短语"` | `"large language model hallucination"` | ✅ 真精确匹配 |
| `-词` 排除 | `苹果 -手机` | ✅ |
| `OR` / `AND` / `NOT` | `CUDA OR ROCm 教程` | ✅ |
| `language:en` | `quantum computing language:en` | ✅ |
| `contains:` | `报告 contains:pdf` | 🟡 影响极弱 |
| `filetype:` / `ext:` | - | ❌ cn 索引不支持 |
| `feed:` | - | ❌ 忽略 |
| `related:` | `related:python.org` | 🟡 返回相似站点(含自身) |

> 以上矩阵在国内版 `cn.bing.com` + `curl_cffi` 浏览器指纹会话下实测。
> **国际版 `site:` 额外配置**：www.bing.com 的语法门要求 Edge 全家桶（客户端已内置 UAgent/UA/`sec-ch-ua` 三件套），
> 仅 `sec-ms-gec` token 需要用户提供——从你本机 Edge 的任意请求里复制 `sec-ms-gec` 请求头值，然后：
> ```bash
> export BING_GEC_TOKEN=9974759AC621...   # Edge 的 sec-ms-gec 头值(时效宽松, 过期后重新复制)
> ```
> 未配置时国际版仍可正常搜索/翻页/RSS，仅 `site:` 类高级语法会被服务端忽略。
> 国内版无需任何配置，`site:` 即全生效。**依赖 `site:` 的业务建议加 `source` 过滤兜底**。**依赖说明**：高级语法要求"浏览器 TLS 指纹 + HVE 会话激活"，
> 客户端已全自动处理；未安装 `curl_cffi` 时退回 requests 指纹，`site:` / `inbody:` 等高级语法会被服务端忽略。
> 带语法的查询建议主要使用第一页；翻页页码上部分语法可能被服务端忽略（自动回退通道会尽力补齐）。

## ⚙️ 配置

### 环境变量

| 变量 | 说明 |
|---|---|
| `BING_PROXY` | 国际版代理地址，如 `http://127.0.0.1:7890`。国内版无需设置 |

### 引擎说明

| 引擎 | 网络 | 默认市场 | 说明 |
|---|---|---|---|
| `cn` | 大陆直连 | `zh-CN` | 结果含合规过滤提示 |
| `global` | 需海外出口 | `en-US` | 大陆直连会被服务端重定向至国内版 |

代理不可用时 `engine=global` 自动降级为 `cn + ensearch`（结果≈国际索引但不完全等同，
响应 `meta.fallback` 会注明）。

## ⚠️ 注意事项

- 每页结果条数由 Bing 服务端决定（约 6–10 条），`count` 为本地截断上限
- 结果仅供个人非商业用途，请控制请求频率（建议 ≤1 QPS），遵守 Bing 服务条款
- 仅支持 Python 3.8+；Windows / Linux / macOS 均可运行
