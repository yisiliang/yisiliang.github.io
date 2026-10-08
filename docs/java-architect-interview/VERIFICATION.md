# 构建与验收范围

本目录独立于首页目录、导航、已有 CSS/JavaScript 和文章，不更新 sitemap/RSS。仓库 GitHub Pages 从 master:/docs 构建（legacy Jekyll），本目录不使用 Front Matter，index.html 是直接复制的静态 HTML。页面显式载入现有 Umami 网站记录脚本；没有访问权限控制。

十个专题、60 道三层问答、15 张 Mermaid 图、源码连续节选和模拟故障。官方源码下载记录见 sources.json，补充联网记录见 research-checks.json。所有事故均为教学模拟，未实际运行 Java、数据库、Redis、RocketMQ 故障实验，不声称有真实生产测量。

读者不需要 npm、Python、Node.js 或后端。源码高亮使用本地 Prism；Mermaid 在构建时渲染成 SVG，正文和图表禁用 JavaScript 仍可阅读。运行时只有 Umami 使用外部请求，阻断它不影响核心功能。许可证在 licenses/ 与 vendor/，源码声明在 source-notices.txt。

维护时安装 markdown、beautifulsoup4、playwright（仅维护环境）；运行 build.py 后，从仓库 docs 目录启动静态服务器，再运行 render-diagrams.py、verify.py。当前构建辅助脚本默认本地 8000 端口、Chromium /usr/bin/chromium；部署产物不调用这些脚本。验证结果见 validation-results.json 与 diagram-validation.json。

发布仅需提交本目录，沿用已有 GitHub Pages 设置。公开地址为 https://yisiliang.github.io/java-architect-interview/。
