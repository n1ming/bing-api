# -*- coding: utf-8 -*-
"""
Bing 搜索 API 服务 (FastAPI)

启动:
    python api.py                       # 默认 127.0.0.1:8000
    python api.py --host 0.0.0.0 --port 8001

接口:
    GET /search?q=python+教程&engine=cn&protocol=html&count=10
    GET /search?q=test&engine=global            -> 走代理(环境变量 BING_PROXY)
    GET /search?q=test&engine=cn&ensearch=true  -> 国内直连拿国际结果
    GET /compare?q=...                          -> 同查询两版对比
    GET /meta                                   -> 两版机制差异说明
"""
from __future__ import annotations

import argparse
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from bing_search import BingSearch, BingResult, BingSearchError

app = FastAPI(title="Bing Search API", version="1.0.0",
              description="免密钥 Bing 搜索接口: 国内版(cn) / 国际版(global)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# 简单 TTL 结果缓存(避免穿透 + 限流保护)
_CACHE: Dict[str, tuple] = {}
_CACHE_TTL = 60.0
_SESSIONS: Dict[str, BingSearch] = {}

GLOBAL_PROXY_ENV = os.environ.get("BING_PROXY", "")  # 本机代理经环境变量注入, 不入库


def _get_session(engine: str, proxy: Optional[str], ensearch: bool,
                 cookie: Optional[str] = None) -> BingSearch:
    # ensearch 模式的 cn 会话复用同一个(参数仅影响 query 构造)
    key = f"{engine}|{proxy or ''}|{hash(cookie or '')}"
    if key not in _SESSIONS:
        _SESSIONS[key] = BingSearch(engine, proxy=proxy, cookies=cookie or None)
    elif cookie:
        # 同 key 会话刷新 cookie (登录态可能更新)
        try:
            _SESSIONS[key].set_cookies(cookie)
        except Exception:
            pass
    return _SESSIONS[key]


def _cache_get(key: str):
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < _CACHE_TTL:
        return hit[1]
    return None


def _cache_put(key: str, payload: Dict):
    _CACHE[key] = (time.time(), payload)
    # 轻度淘汰
    if len(_CACHE) > 500:
        for k in list(_CACHE.keys())[:200]:
            _CACHE.pop(k, None)


def _serialize(data: Dict, results: List[BingResult]) -> Dict:
    out = dict(data)
    out["results"] = [r.as_dict() for r in results]
    return out


@app.get("/search")
def search_endpoint(
    q: str = Query(..., min_length=1, description="搜索词"),
    engine: str = Query("cn", pattern="^(cn|global)$"),
    protocol: str = Query("html", pattern="^(html|rss)$"),
    count: int = Query(10, ge=1, le=25),
    page: int = Query(1, ge=1, le=20, description="页码(见 meta.note 的翻页限制)"),
    ensearch: bool = Query(False, description="仅 engine=cn: 强制国际结果(直连)"),
    mkt: Optional[str] = Query(None, max_length=20),
    safe: Optional[str] = Query(None, pattern="^(off|moderate|strict)$"),
    proxy: Optional[str] = Query(None, max_length=200),
    cache: bool = Query(True),
    x_bing_cookie: Optional[str] = Header(None, convert_underscores=True),
):
    key = repr((q, engine, protocol, count, page, ensearch, mkt, safe))
    if cache:
        hit = _cache_get(key)
        if hit:
            payload = dict(hit)
            payload["meta"]["cached"] = True
            return payload
    try:
        bs = _get_session(engine, proxy, ensearch, cookie=x_bing_cookie)
        if mkt:
            bs._mkt = mkt
        data = bs.search(
            q,
            count=count,
            protocol=protocol,
            ensearch=ensearch,
            safe_search=safe,
            first=(page - 1) * count + 1,
        )
        payload = _serialize(data, data["results"])
        payload["page"] = page
    except (BingSearchError, ValueError) as e:
        # 国际版代理不可用时降级: cn + ensearch 直连国际结果
        if engine == "global" and not ensearch:
            try:
                bs = _get_session("cn", None, False)
                data = bs.search(q, count=count, protocol=protocol,
                                 ensearch=True, safe_search=safe)
                payload = _serialize(data, data["results"])
                payload["page"] = page
                payload["meta"]["fallback"] = (
                    f"global 代理不可用({e}) -> 已降级为 cn+ensearch 国际结果(实测与真 www.bing.com+mkt=en-US 结果几乎不重叠)"
                )
            except (BingSearchError, ValueError) as e2:
                return JSONResponse(status_code=502, content={
                    "error": f"global 失败: {e}; 降级也失败: {e2}",
                    "hint": "设置环境变量 BING_PROXY=你的代理地址, 或直接 engine=cn&ensearch=true",
                })
        else:
            return JSONResponse(status_code=502, content={"error": str(e)})
    if cache:
        _cache_put(key, payload)
    return payload


@app.get("/compare")
def compare_endpoint(
    q: str = Query(..., min_length=1),
    protocol: str = Query("html", pattern="^(html|rss)$"),
    mkt: Optional[str] = Query(None, max_length=20),
):
    try:
        cn = _get_session("cn", None, False)
        a = cn.search(q, count=10, protocol=protocol)
    except (BingSearchError, ValueError) as e:
        return JSONResponse(status_code=502, content={"error": f"cn 失败: {e}"})
    global_block: Dict[str, Any]
    try:
        gl = _get_session("global", GLOBAL_PROXY_ENV, False)
        if mkt:
            gl._mkt = mkt
        b = gl.search(q, count=10, protocol=protocol)
        global_block = {"count": b["count"], "total_count": b["total_count"],
                        "results": [r.as_dict() for r in b["results"]]}
        ub = {r.url for r in b["results"]}
        ub_failed = False
    except BingSearchError as e:
        global_block = {"error": str(e), "hint": "代理不可用; 也可用 /search?engine=cn&ensearch=true 直连国际结果"}
        ub = set()
        ub_failed = True
    ua = {r.url for r in a["results"]}
    out = {
        "query": q,
        "cn": {"count": a["count"], "total_count": a["total_count"],
               "results": [r.as_dict() for r in a["results"]]},
        "global": global_block,
        "cn_only": len(ua - ub),
    }
    if not ub_failed:
        out["overlap_urls"] = sorted(ua & ub)
        out["global_only"] = len(ub - ua)
    return out


@app.get("/meta")
def meta_endpoint():
    return {
        "engines": {
            "cn": {
                "host": "https://cn.bing.com",
                "default_mkt": "zh-CN",
                "requires_proxy": False,
                "note": "国内版: 直连即可; 结果受合规过滤(页面注明'部分结果未予显示'); 链接为明文直链。",
            },
            "global": {
                "host": "https://www.bing.com",
                "default_mkt": "en-US",
                "requires_proxy": "大陆网络必需(实测 www.bing.com 对大陆 IP 302 强跳 cn.bing.com)",
                "default_proxy": GLOBAL_PROXY_ENV,
                "note": "国际版: 必须 mkt/setlang 显式声明, 否则 RSS 可能返回不相关结果; HTML 链接为 bing.com/ck/a 跳转链接, 接口已自动 base64url 解码为真实 URL。",
            },
        },
        "ensearch": "engine=cn + ensearch=true => 国内直连强制返回国际结果(官方隐藏开关, 结果与真国际版≈但不完全等同)",
        "pagination_limit": "Bing 2026 对匿名会话每页固定~10条: count/first 参数(HTML/RSS/浏览器实测一致)重复返回第一页。page>pin 语义保留",
        "protocols": {
            "html": "SERP 页解析: 丰富的 date/snippet/display_url; 国际版自动解码 ck 跳转链接",
            "rss": "?format=rss 机器友好 XML: title/link/description/pubDate, 无需会话 cookie",
        },
        "auth": "无需 API Key / 登录",
    }


def main():
    ap = argparse.ArgumentParser("Bing Search API")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    import uvicorn
    uvicorn.run(app, host=a.host, port=a.port, log_level="info")


if __name__ == "__main__":
    main()
