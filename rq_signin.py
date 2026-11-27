#!/usr/bin/env python3
"""
RQrun 自动签到脚本 (新版 www.rq.run 接口)
支持验证码自动识别与签到。

用法:
    python rq_signin.py

环境变量:
    RQ_EMAIL    - RQrun 账号邮箱
    RQ_PASSWORD - RQrun 账号密码
"""

import os
import re
import sys
import time
import json
import random
import ssl
import http.cookiejar
import urllib.request
import urllib.parse
import urllib.error

# ============================================================
# 配置
# ============================================================
RQ_EMAIL = os.environ.get("RQ_EMAIL", "")
RQ_PASSWORD = os.environ.get("RQ_PASSWORD", "")

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
)
APP_UA = "RQ Run/2.9.4 (cn.runningquotient.RQ-Run; build:12; iOS 14.6.0) Alamofire/2.9.4"
AUTH_HEADER = "PtCNFNv2FrKVmWuKzALA"

# 忽略 SSL 证书校验
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE


def new_opener():
    """创建带 Cookie 管理 + 忽略证书的 opener（自动跟随跨域重定向）"""
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        urllib.request.HTTPSHandler(context=ssl_ctx),
    )
    opener.addheaders = [("User-Agent", MOBILE_UA)]
    return opener, cj


# ============================================================
# 步骤 1: 登录获取 Token (api.rq.run)
# ============================================================
def login(email, password):
    print("[1/4] 登录 RQrun ...")
    url = "https://api.rq.run/Api/User/submit_login"
    headers = {
        "Host": "api.rq.run",
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "authorization": AUTH_HEADER,
        "user-agent": APP_UA,
        "accept-language": "zh-Hans-HK;q=1.0, en-HK;q=0.9, en-GB;q=0.8, yue-Hant-HK;q=0.7",
    }
    data = urllib.parse.urlencode({"email": email, "password": password}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl_ctx))
    try:
        resp = opener.open(req, timeout=30)
    except urllib.error.HTTPError as e:
        print(f"  ✗ 登录失败，HTTP {e.code}")
        return None
    result = json.loads(resp.read())
    if result.get("syscode") != 200:
        print(f"  ✗ 登录失败: {result.get('message', '未知错误')}")
        return None
    user_id = result["data"]["user_id"]
    token = result["data"]["access_token"]
    print(f"  ✓ 登录成功, userId={user_id}")
    return user_id, token


# ============================================================
# 步骤 2: 建立签到会话 (www.rq.run)
# ============================================================
def open_signin_session(opener, user_id, token):
    print("[2/4] 建立签到会话 ...")
    url = f"https://www.rq.run/user/SignIn/?userId={user_id}&token={token}"
    resp = opener.open(url, timeout=30)
    html = resp.read().decode("utf-8", "ignore")
    m = re.search(r'is_show_verify="(\d)"', html)
    is_show_verify = int(m.group(1)) if m else 0
    print(f"  ✓ 会话建立, 需要验证码={'是' if is_show_verify == 1 else '否'}")
    return is_show_verify


# ============================================================
# 步骤 3: 获取验证码并 OCR
# ============================================================
def _get_ocr():
    """初始化 ddddocr，兼容新版 Pillow"""
    try:
        import PIL.Image as _Image
        if not hasattr(_Image, "ANTIALIAS"):
            _Image.ANTIALIAS = _Image.Resampling.LANCZOS
    except Exception:
        pass
    import ddddocr
    try:
        return ddddocr.DdddOcr(show_ad=False)
    except TypeError:
        return ddddocr.DdddOcr()


def fetch_captcha_code(opener):
    print("[3/4] 识别验证码 ...")
    url = "https://www.rq.run/User/SignIn/sign_verify_code"
    resp = opener.open(url, timeout=30)
    image = resp.read()
    if image[:4] != b"\x89PNG" and image[:2] != b"\xff\xd8":
        print(f"  ✗ 验证码返回异常 (前4字节: {image[:4]})")
        return ""
    try:
        ocr = _get_ocr()
        code = ocr.classification(image)
        print(f"  ✓ 验证码识别结果: {code}")
        return code
    except ImportError:
        path = "/tmp/rqrun_captcha.png"
        with open(path, "wb") as f:
            f.write(image)
        print(f"  ⚠ ddddocr 未安装，验证码已保存至 {path}")
        return input("  请输入验证码: ").strip()


# ============================================================
# 步骤 4: 提交签到
# ============================================================
def submit_signin(opener, user_id, token, codes):
    print("[4/4] 执行签到 ...")
    url = "https://www.rq.run/User/SignIn/sign_in"
    data = urllib.parse.urlencode({"codes": codes}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("X-Requested-With", "XMLHttpRequest")
    req.add_header("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")
    req.add_header("Referer", f"https://www.rq.run/user/SignIn/?userId={user_id}&token={token}")
    resp = opener.open(req, timeout=30)
    result = json.loads(resp.read())
    status = result.get("status", -1)

    if status == 1:
        print("  ✓ 签到成功！")
        return "success"
    elif status == 10009:
        print("  ⚠ 今日已签到，无需重复操作")
        return "already"
    elif status == 10011:
        print("  ✗ 验证码错误")
        return "captcha_error"
    else:
        print(f"  ✗ 签到失败: {result}")
        return "fail"


# ============================================================
# 主流程
# ============================================================
def main():
    if not RQ_EMAIL or not RQ_PASSWORD:
        print("请设置环境变量 RQ_EMAIL 和 RQ_PASSWORD")
        print("示例: RQ_EMAIL=xxx@xxx.com RQ_PASSWORD=xxx python rq_signin.py")
        sys.exit(1)

    login_result = login(RQ_EMAIL, RQ_PASSWORD)
    if not login_result:
        sys.exit(1)
    user_id, token = login_result

    opener, _ = new_opener()
    is_verify = open_signin_session(opener, user_id, token)

    # 不需要验证码：直接签到
    if is_verify != 1:
        status = submit_signin(opener, user_id, token, "")
        if status in ("success", "already"):
            return
        # 若意外要求验证码，则回退到验证码流程

    # 需要验证码：最多重试 10 次
    for i in range(10):
        code = fetch_captcha_code(opener)
        if not code:
            continue
        status = submit_signin(opener, user_id, token, code)
        if status in ("success", "already"):
            return
        if i < 9:
            print(f"  重试 ({i + 2}/10)...")
            time.sleep(1)

    print("签到失败，超过最大重试次数")
    sys.exit(1)


if __name__ == "__main__":
    main()
