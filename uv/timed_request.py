import asyncio
import time
import httpx

async def timed_request(url: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        start = time.perf_counter()
        try:
            response = await client.get(url)
            response.raise_for_status()
            elapsed = time.perf_counter() - start
            print(f"状态码: {response.status_code}")
            print(f"耗时: {elapsed * 1000:.2f} ms")
            print(f"响应预览: {str(response.json())[:200]}")
        except httpx.TimeoutException:
            elapsed = time.perf_counter() - start
            print(f"请求超时，耗时: {elapsed * 1000:.2f} ms")
        except httpx.HTTPStatusError as e:
            elapsed = time.perf_counter() - start
            print(f"HTTP 错误 {e.response.status_code}，耗时: {elapsed * 1000:.2f} ms")
        except httpx.RequestError as e:
            elapsed = time.perf_counter() - start
            print(f"请求失败: {type(e).__name__}，耗时: {elapsed * 1000:.2f} ms")

asyncio.run(timed_request("https://httpbin.org/delay/1"))