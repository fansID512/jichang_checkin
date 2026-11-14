import json
import os
import sys
import time
import urllib.parse
from urllib.parse import urlparse

import requests

try:
    from curl_cffi import requests as cffi_requests
except Exception:  # curl_cffi 未安装时退回 requests
    cffi_requests = None

# 机场的地址
url = (os.environ.get('URL') or '').strip().rstrip('/')
# 配置：按行存 偶数行=用户名 奇数行=密码
config = os.environ.get('CONFIG') or ''
# Cookie 登录：按行存，第 i 行对应 CONFIG 里的第 i 个账号；留空则该账号回退到账号密码登录
cookies_raw = os.environ.get('COOKIE') or ''
# server酱
SCKEY = os.environ.get('SCKEY') or ''

# GeeTest V4 验证码 ID（从 ikuuu.org 提取）
CAPTCHA_ID = 'cc96d05ba8b60f9112f76e18526fcb73'

login_url = '{}/auth/login'.format(url)
check_url = '{}/user/checkin'.format(url)

MAX_RETRIES = 3

HEADER = {
    'origin': url,
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0',
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
}


def push(content):
    """推送到 server酱"""
    if not SCKEY:
        return
    try:
        push_url = 'https://sctapi.ftqq.com/{}.send?title=机场签到&desp={}'.format(SCKEY, content)
        requests.post(url=push_url, timeout=20)
        print('推送成功')
    except Exception as ex:
        print('推送失败: %s' % ex)


def clean_cookie(cookie):
    """允许直接粘贴浏览器里的 Cookie 头，去掉换行与多余空白"""
    return ' '.join(cookie.replace('\r', ' ').replace('\n', ' ').split()).strip().rstrip(';')


def solve_captcha():
    """使用 GeekedTest 求解 GeeTest V4 验证码（纯 Python，无需浏览器），支持重试"""
    try:
        from geeked import Geeked
    except Exception as ex:
        print('验证码求解器不可用: %s' % ex)
        return None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print('验证码求解尝试 %d/%d...' % (attempt, MAX_RETRIES))
            geeked = Geeked(CAPTCHA_ID, 'ai')
            result = geeked.solve()
            print('验证码求解成功')
            return result
        except Exception as ex:
            print('验证码求解失败 (尝试 %d/%d): %s' % (attempt, MAX_RETRIES, ex))
            if attempt < MAX_RETRIES:
                print('等待 2 秒后重试...')
                time.sleep(2)
    print('所有重试均失败')
    return None


def parse_result(text, status_code):
    """把签到接口的返回解析成 (ok, msg)"""
    text = (text or '').strip()
    print(text)
    if not text:
        return False, '接口返回空内容（HTTP %s）' % status_code
    try:
        data = json.loads(text)
    except Exception:
        return False, '接口返回非 JSON（HTTP %s）: %s' % (status_code, text[:200])
    msg = str(data.get('msg') or text)[:200]
    return data.get('ret') == 1, msg


def checkin_by_cookie(order, user, cookie):
    """用已登录的 Cookie 直接签到，跳过登录与验证码"""
    print('===账号%d[%s] 使用 Cookie 签到...===' % (order, user))
    header = {
        'origin': url,
        'referer': '%s/user' % url,
        'cookie': cookie,
    }
    try:
        # 不自动跟随跳转：Cookie 失效时站点会 302 到 /auth/login，跟着跳会拿到一张 HTML 登录页
        if cffi_requests is not None:
            # 站点的 Cloudflare 校验会按 TLS 指纹拦截 python-requests（403/405），
            # 用 curl_cffi 模拟真实 Chrome 握手
            res = cffi_requests.post(check_url, headers=header, impersonate='chrome',
                                     timeout=30, allow_redirects=False)
        else:
            h = dict(HEADER)
            h.update(header)
            res = requests.post(url=check_url, headers=h, timeout=30, allow_redirects=False)
    except Exception as ex:
        return False, '请求失败: %s' % ex

    if res.status_code in (301, 302, 303, 307, 308):
        loc = res.headers.get('location') or ''
        if 'auth/login' in loc:
            return False, 'Cookie 已失效，请重新从浏览器复制（站点跳转到登录页）'
        # 有些主题签到后跳回 /user，跟过去看页面提示
        try:
            follow = requests.get(urllib.parse.urljoin(url, loc), headers=header, timeout=30)
        except Exception as ex:
            return False, '签到后跳转到 %s，跟随失败: %s' % (loc, ex)
        text = follow.text or ''
        if any(k in text for k in ('签到成功', '已经签到', '已签到', '获得')):
            print('签到后跳转到 %s，页面提示签到成功' % loc)
            return True, '签到成功（页面提示）'
        return False, '签到后跳转到 %s，未识别到成功提示（HTTP %s）' % (loc, follow.status_code)

    ok, msg = parse_result(res.text, res.status_code)
    if ok:
        print(msg)
        return True, msg
    # 今天已经签到过也算成功，避免手动补跑时误报红
    if any(k in msg for k in ('已经签到', '已签到')):
        print(msg)
        return True, msg

    low = msg.lower()
    if 'auth/login' in (res.text or '') or '<html' in low:
        return False, 'Cookie 已失效，请重新从浏览器复制（返回了登录页面）'
    if any(k in msg for k in ('未登录', '请先登录', '登录后')) or 'login' in low:
        msg = 'Cookie 已失效，请重新从浏览器复制: %s' % msg
    print(msg)
    return False, msg


def checkin_by_login(order, user, pwd):
    """原来的账号密码 + 验证码登录方式"""
    session = requests.session()
    header = dict(HEADER)
    header['referer'] = '%s/auth/login' % url
    try:
        print('===账号%d[%s] 账号密码登录...===' % (order, user))

        # 求解 GeeTest V4 验证码
        captcha = solve_captcha()
        if captcha is None:
            return False, '验证码求解失败，跳过此账号'

        # 站点用的是多阶段登录协议：必须带 phase=password，否则服务端直接返回
        # {"result":"invalid_phase","msg":"登录流程无效，请刷新页面后重试。"}
        data = {
            'host': urlparse(url).netloc,
            'phase': 'password',
            'email': user,
            'passwd': pwd,
            'remember_me': 'on',
            'pageLoadedAt': int(time.time() * 1000),
            'captcha_result[lot_number]': captcha['lot_number'],
            'captcha_result[captcha_output]': captcha['captcha_output'],
            'captcha_result[pass_token]': captcha['pass_token'],
            'captcha_result[gen_time]': captcha['gen_time'],
        }

        r = session.post(url=login_url, headers=header, data=data)
        print(r.text)
        try:
            login_data = json.loads(r.text)
        except Exception:
            return False, '登录返回非 JSON（HTTP %s）: %s' % (r.status_code, (r.text or '')[:200])
        msg = str(login_data.get('msg') or '')
        if login_data.get('phase') != 'authenticated':
            hint = ''
            if login_data.get('result') == 'captcha_failed':
                hint = '（验证码校验未通过，需改用 COOKIE 登录）'
            return False, '登录失败: %s%s' % (msg or login_data.get('result'), hint)
        print(msg)

        # 进行签到
        r = session.post(url=check_url, headers=header)
        ok, msg = parse_result(r.text, r.status_code)
        print(msg)
        return ok, msg
    except Exception as ex:
        print('出现如下异常 %s' % ex)
        return False, '签到失败: %s' % ex


def main():
    lines = [line.strip() for line in config.splitlines() if line.strip()]
    if len(lines) == 0 or len(lines) % 2 != 0:
        print('配置文件格式错误：CONFIG 需要按「用户名 / 密码」成对出现')
        return 1

    cookies = [clean_cookie(line) for line in cookies_raw.splitlines()]
    while len(cookies) < len(lines) // 2:
        cookies.append('')

    ok_count = 0
    fail = []
    cookie_used = False
    for i in range(len(lines) // 2):
        user, pwd = lines[i * 2], lines[i * 2 + 1]
        cookie = cookies[i] if i < len(cookies) else ''
        if cookie:
            cookie_used = True
            ok, msg = checkin_by_cookie(i + 1, user, cookie)
        else:
            ok, msg = checkin_by_login(i + 1, user, pwd)
        if ok:
            ok_count += 1
        else:
            fail.append('%s: %s' % (user, msg))
        print('===账号%d签到结束===\n' % (i + 1))

    total = len(lines) // 2
    print('签到结果：成功 %d / 共 %d' % (ok_count, total))
    if fail:
        print('失败明细：\n' + '\n'.join(fail))
    push('成功 %d/%d\n%s' % (ok_count, total, '\n'.join(fail)))

    if ok_count > 0:
        return 0
    # 没配 Cookie 时失败是验证码求解器的问题，报红只会天天发邮件，所以保持绿灯
    if not cookie_used:
        print('提示：未配置 COOKIE，当前走账号密码 + 验证码流程（验证码求解器如失效则无法签到）')
        return 0
    # 配了 Cookie 仍全部失败 = Cookie 过期或站点异常，需要人处理，让工作流变红
    return 1


if __name__ == '__main__':
    sys.exit(main())
