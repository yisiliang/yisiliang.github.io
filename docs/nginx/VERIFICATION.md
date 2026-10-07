# NGINX手册核验记录

核验日期：2026年10月7日（Asia/Shanghai）。

## 固定基线

- 官方仓库：https://github.com/nginx/nginx
- 标签：release-1.28.0
- annotated tag对象：f6f8d515885fcda20f09b83583d576337fbabe0a
- 解引用commit：481d28cb4e04c8096b9b6134856891dc52ecc68f
- 范围：开源NGINX、Unix、多进程、HTTP/1.x反向代理主线；必要处明确HTTP/2、HTTP/3、Windows、SSL和商业功能差异。

## 已执行

1. 从官方release标签浅克隆，读取实际C源码；正文固定链接全部用commit，非移动分支。
2. 24章、24幅机制图、24段连续C节选按实际Markdown/HTML统计。source-evidence.json记录每段路径、起止行、SHA256。逐字与基线checkout比较，无伪代码替代原文。
3. HTML章节锚点、目录目标、页内ID唯一、SVG title/desc/marker唯一、图片XML、下载/附属文件存在性核验通过。
4. HTML图全部内联，主题/检索/复制脚本全部内联，未引入CDN渲染器、远程字体或图片。移动端通过媒体查询布局，图横向滚动；本agent尚未执行真实浏览器截图，父agent可继续做视觉验收。
5. 在线index.html含一份Umami（8c64c0bf-97e7-4af5-a5bf-f090c52fc4d3）；离线index.html无tracker、无外部script资源、无站点根导航依赖。
6. 离线ZIP完整性检查通过，内含HTML、Markdown、24幅SVG、实验配置/后端、许可、来源与核验记录。未分发NGINX二进制或完整上游源码。
7. Python实验后端语法与本地HTTP响应核验：cache端点200且Cache-Control public,max-age=2；slow gap0返回48字节；blob size32返回32字节；echo返回received_bytes=4。此测试只证明虚构后端材料可运行，**不是NGINX集成实验**。
8. git diff --check对本目录检查通过。父agent负责统一提交、推送、部署和线上验收，本agent未执行这些操作。

## 未执行与限制

- 环境没有nginx命令。未安装/编译NGINX，未执行nginx -t/-T、curl经NGINX代理、reload/QUIT/USR2、缓存/限流运行、TLS、DNS、并发/压测或strace。
- experiments.md中的状态/日志为基于固定源码推导的预期，不能视为实测结果。CLI是否接受lab配置取决于匹配构建的模块和系统。
- 实验后端仅支持带Content-Length的POST；chunked body不是它的覆盖范围。
- 官网文档为滚动页，生产版本、安全公告和升级行为必须重新查证。源码学习基线不等于生产部署推荐。
- 24幅图表达具体状态/分支/所有权，省略实现细节；不构成严格时序或性能保证。

## 复核方法

```sh
python3 verify.py /path/to/nginx-release-1.28.0-checkout
```

不传源码路径时仍可核对节选自身哈希、章图数量、HTML资源和离线包；传入匹配checkout才能确认原文。上游LICENSE完整保留于nginx-license.txt。

主任务已验证浏览器全文检索与主题控件；390px手机视口下长源码路径溢出已修复，公开与离线页面同步。
