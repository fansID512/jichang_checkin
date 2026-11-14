# 通用机场签到😍<br/>
>只要机场网站''' Powered by SSPANEL ''',就可以进行签到。要确认是否是''' Powered by SSPANEL '''，在机场首页滑倒最底端就可以看到。例如：
![Y0}SY$J`8837H8T5GXM1DZY](https://user-images.githubusercontent.com/21276183/214764546-4f66333a-cb9b-420e-8260-697d26fb4547.png)
## 作用
>每天进行签到，获取额外的流量奖励

## 推送方式
  🚀🚀该脚本采用的是<a href = 'https://sct.ftqq.com/r/5126'>Server酱</a>的推送方式，如果不需要推送，就下面的SCKEY参数的值设置为<b>空</b>就行

# 部署过程
 
1. 右上角Fork此仓库
2. 然后到`Settings`→`Secrets and variables`→`Actions` 新建以下机密：

| 参数   | 是否必须  | 内容  | 
| ------------ | ------------ | ------------ |
| URL | 是  | 机场地址，例如 `https://ikuuu.one`，尾部不要加 `/` |
| CONFIG| 是  | 账号密码  |
| COOKIE | 否  | 已登录状态的 Cookie（推荐，绕过验证码） |
| SCKEY  | 否  | Sever酱秘钥  |
<br/>
<b>其中URL的值必须是机场网站的地址，例如：https://example.com</b>,尾部不要加''' / '''号 config写法：一行账号一行密码

3. 到`Actions`中创建一个workflow，运行一次，以后每天项目都会自动运行。<br/>
4. 最后，可以到Run sign查看签到情况，同时也会也会将签到详情推送到Sever酱。

### 关于 COOKIE（推荐）

站点登录用的是 GeeTest V4 验证码，社区的纯 Python 求解器在站点升级成「九宫格」题型后已失效，
表现为日志里 `验证码求解失败，跳过此账号`。此时改用 Cookie 登录：

1. 浏览器登录机场网站，按 F12 → Application/应用 → Cookies，或 Network 里任意请求的 `Cookie` 请求头
2. 把整串 Cookie（形如 `uid=1234; email=a@b.com; key=xxxx; ip=1.2.3.4`）贴进 `COOKIE` 机密
3. 多账号时**按行填写**，第 i 行对应 CONFIG 里的第 i 个账号；某行留空则该账号回退到账号密码登录

COOKIE 有效期内直接签到，不再求解验证码。Cookie 过期后工作流会变红提醒你重新复制。
