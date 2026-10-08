# Transformer通俗解读：原文基线与验证记录

版本日期：2026年10月8日。本文作为AI与大模型基础分类的第一篇论文解读接入首页；公共页面配置Umami，离线包保留本地计算器并剥离统计。

## 文件

- index.html：独立阅读页，16节、4张教学流程图、逐页原文定位、注意力交互计算器。
- style.css：从distributed阅读视觉复制并局部扩展，未共享或修改原CSS。
- attention.js：两维查询滑块、因果mask开关，固定手设K/V。
- verify.py：Python标准库计算Q/K/V、softmax、causal mask、两头拼接、位置编码、FFN、LayerNorm、词表概率与交叉熵；校验目录锚点、ID和资源。
- build_offline.py：确定性离线打包，不含统计或外部渲染依赖。
- transformer-offline.zip：HTML/CSS/JS/数值核验脚本；PDF使用固定外链，不复制论文全文。

## 原文基线

- Vaswani等，Attention Is All You Need，arXiv:1706.03762v5。
- 固定地址：https://arxiv.org/pdf/1706.03762v5
- 版本日期：2017-12-06；15页，主文与参考资料至12页，附录可视化13—15页。
- 下载PDF SHA-256：bfaaec89262875f927cf1b38b2da2d775f3309b7bea3537f29b606ca67e79065。
- 本次下载到/tmp/transformer-1706.03762v5.pdf，全文抽取到/tmp/transformer-v5.txt。通过pypdf提取，pdfplumber渲染架构页并目视核对；web PDF同时核对公式与实验表。
- 已阅读全文，含训练、结果、结论、参考文献与三页附录。v5摘要与表2的英法BLEU=41.8，§6.1正文=41.0；文章保留差异，表格明确依据表2。

## 内容证据与教学补充

- §1—2，第1—2页：循环的顺序依赖、注意力的动机。
- 图1/§3.1，第3页：Encoder—Decoder、右移、mask、Post-LN。
- 公式(1)/§3.2，第4—5页：缩放点积、多头与三种Attention路径。
- §3.3—3.5，第5—6页：FFN、embedding、正弦位置编码。
- §4/表1，第6—7页：交互路径与复杂度；文章补充完整块投影和FFN成本。
- §5，第7—8页：训练设置；文章用教学例子说明teacher forcing与损失，不宣称完整训练复现。
- §6/表2—4，第8—10页：翻译、开发集变体、句法分析与边界。
- 图3—5，第13—15页：可视化不自动等于因果解释。
- 后续边界参考：Layer Normalization原论文、2018年GPT原论文、2019年Attention is not Explanation；明确是补充资料。

所有中文场景、小矩阵、数值运算、图解和交互都明确标为教学构造。Q/K/V解释为学习投影，未指定人工语义；对注意力权重不作最终贡献百分比的解释。

## 已完成的验证

1. python3 docs/transformer/verify.py通过；主要默认输出第一行[1.6044483707,0.5988879073]，两头拼接后[0.8446375965,1.5113042632]。
2. 本地HTTP页面1440×1000与390×844检查：页面无横向溢出；公式块各自支持横向滚动。
3. Playwright实际勾选第一位置因果mask，得到权重[1,0,0]、输出[2,0]，与Python结果一致。
4. 桌面首屏与手机数值段截图目视核验通过。截图位于本地.playwright-cli，未纳入交付目录。
5. git diff --check通过；离线ZIP包含4项，HTML只引用本地CSS/JS。

## 发布与维护约定

- 原文定义、实验报告、教学矩阵与后续演进分开说明，当前不声称复现完整模型或训练实验。
- 首页catalog与根README指向本篇文章；保持六分类。目录kind为paper，共享源码阅读器脚本跳过本篇。
- 公共页包含一份Umami；build_offline.py在打包时剥离统计脚本。
- 更新正文后重新构建离线包，运行verify.py；发布时等待Pages built并核对线上HTML、CSS、JS和ZIP。
- 当前交付为单篇基础论文解析；BERT/GPT/RAG/LoRA均未创建。

## 深入解读增补（2026年10月8日）

- 增加innovation、learning、to-chatgpt三节，保持旧锚点可访问。
- 前史与创新：Bahdanau论文、原文§2/§3/§4及表1/表3；区分已有构件与架构组合贡献。
- 后续演进：GPT（2018）、GPT-2（2019）、GPT-3（2020）、Scaling Laws（2020）、Chinchilla（2022）、InstructGPT（2022）、ChatGPT首次发布资料（2022-11-30）。正文逐段提供主来源链接。
- 公布的历史事实与本文工程分析分开；不推测GPT-3.5参数量或实际训练预算，不把时间线视为必然因果证明。
- verify.py增加参数量、复杂度代入、FP16显存计算及交叉熵梯度的有限差分检验。RLHF目标明确为教学简式，省略额外预训练项，不宣称实现完整PPO。
