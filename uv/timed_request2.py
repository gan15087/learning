import asyncio
import time
import httpx

CASES = [
    # (描述, URL, 超时秒数, 是否 raise_for_status)
    ("正常 200",            "https://httpbin.org/get",          10.0, True),
    ("404 但不检查状态",     "https://httpbin.org/status/404",   10.0, False),
    ("404 且检查状态",       "https://httpbin.org/status/404",   10.0, True),
    ("500 且检查状态",       "https://httpbin.org/status/500",   10.0, True),
    ("读超时（服务端延迟）", "https://httpbin.org/delay/5",      1.0, True),
    ("连接被拒绝（端口无服务）", "http://127.0.0.1:1/",          5.0, True),
    ("DNS 解析失败",         "http://no-such-host.invalid/",    5.0, True),
    ("不支持的协议",         "ftp://example.com/file",          5.0, True),
]

async def run_case(desc: str, url: str, timeout: float, check_status: bool) -> None:
    print(f"\n=== {desc} ===")
    print(f"URL: {url}  timeout={timeout}s  raise_for_status={check_status}")
    async with httpx.AsyncClient(timeout=timeout) as client:
        start = time.perf_counter()
        try:
            response = await client.get(url)
            if check_status:
                response.raise_for_status()
            elapsed = time.perf_counter() - start
            print(f"✅ 成功  status={response.status_code}  耗时={elapsed*1000:.2f} ms")
        except httpx.HTTPStatusError as e:
            elapsed = time.perf_counter() - start
            print(f"❌ HTTPStatusError  status={e.response.status_code}  耗时={elapsed*1000:.2f} ms")
        except httpx.TimeoutException as e:
            elapsed = time.perf_counter() - start
            print(f"⏱️ {type(e).__name__}  耗时={elapsed*1000:.2f} ms")
        except httpx.ConnectError as e:
            elapsed = time.perf_counter() - start
            print(f"🔌 ConnectError  {e}  耗时={elapsed*1000:.2f} ms")
        except httpx.UnsupportedProtocol as e:
            elapsed = time.perf_counter() - start
            print(f"🚫 UnsupportedProtocol  {e}  耗时={elapsed*1000:.2f} ms")
        except httpx.RequestError as e:
            elapsed = time.perf_counter() - start
            print(f"⚠️ 其他 RequestError: {type(e).__name__}  {e}  耗时={elapsed*1000:.2f} ms")

async def main():
    for case in CASES:
        await run_case(*case)

asyncio.run(main())