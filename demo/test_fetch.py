import urllib.request
import re

# 腾讯财经实时行情接口（免 key，返回简洁）
codes = "sh000001,sz399001,sz399006,sh000688,sz002506,sz159516,sh603618"
url = "https://qt.gtimg.cn/q=" + codes
req = urllib.request.Request(url, headers={
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://gu.qq.com/",
})
try:
    raw = urllib.request.urlopen(req, timeout=15).read().decode("gbk")
    print("=== RAW ===")
    print(raw)
    print("=== PARSED ===")
    # 每条: v_sh000001="1~名称~代码~当前价~昨收~今开~成交量(手)~外盘~内盘~最高~最低~..."
    pat = re.compile(r'v_(\w+)="([^"]+)"')
    for m in pat.finditer(raw):
        code = m.group(1)
        f = m.group(2).split("~")
        name = f[1]
        price = f[3]
        prev = f[4]
        # 涨跌幅
        try:
            chg = (float(price) - float(prev)) / float(prev) * 100
        except Exception:
            chg = 0.0
        print(f"{code} {name} 现价={price} 昨收={prev} 涨跌={chg:+.2f}%")
except Exception as e:
    print("ERROR:", repr(e))
