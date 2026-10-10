# 03 Special Reports｜专题研究

每周日发布全球战略、能源资源、地缘政治与产业深度研究。专题独立位于 `/special-reports/`；不修改 Website Skill，也不调用或修改其他栏目的发布工具。

## 上传 FINAL.md 后的流程

Codex 读取完整 FINAL.md，归档原稿，默认生成仓库外待发布预览与 review.json。保留标题、作者、来源、正文、脚注、表格、附录、版权说明与原始日期。FINAL 文件名本身不表示授权公开；文件中的 pending 标记和核验事项优先。

依赖：`python3 -m pip install -r tools/special_reports_requirements.txt`。预览：

```sh
python3 tools/publish_special_report.py /absolute/path/FINAL.md --slug report-slug --date YYYY-MM-DD --preview-dir /absolute/path/private-preview
```

支持 YAML front matter：title、slug、authors（数组）或 author、source、original_date、publication_date（或 date）、description、status。也可用正文一级标题推导标题，通过 CLI 指定日期、slug，因此原稿不必重写才能预览。正式发布要求作者、来源和 status: FINAL；复杂元数据使用标准 YAML。正文使用 Markdown Extra（包括脚注、表格、附录、引用、代码块），不自动删改或翻译正文。未定义脚注与危险 HTML/URL 拒绝处理。

正式发布日期按北京时间选择当次周日，`original_date` 保留原报告日期；不要把旧报告日期当作网站发布日期。历史回填亦按正式发布日期倒序排列；稳定 slug 防止重复发布和覆盖历史文章。无需 cron；每周日用户上传文件触发本流程。

## 正式发布门槛

完成版权、图片授权或不使用图片、文件内所有发布前核验后，制作和最终原稿 SHA-256、发布日期绑定的私有 JSON 核验记录。不要替用户编造授权，不把记录和待发布原文放入公开 Git 仓库。

```json
{
  "source_sha256": "SHA256_OF_EXACT_FINAL_FILE",
  "publication_date": "YYYY-MM-DD",
  "rights_cleared": true,
  "image_rights_cleared_or_no_image": true,
  "file_checks_completed": true,
  "publish_approved": true,
  "reviewer": "实际核验人",
  "evidence": ["版权授权证据路径", "核验记录路径"]
}
```

原稿仍含 pending 状态、未链接的来源占位符、未完成的发布前核验说明或缺失表1时拒绝发布。已完成的历史核验说明可以保留，但需设置 verification_status 为 completed 或 completed-with-disclosed-limitations，verification_notes_section 指向正文中实际存在的出版核验完成记录；披露数据局限不代表将原文全部数据确认为正确。先按证据完成修订，归档修订稿，再生成相应记录。修订需保留原译文与编者附录的归属，不擅自改写数据。每份文章都需要有效授权依据；对于已获得覆盖未来文章的授权，可引用同一授权证据。

```sh
python3 tools/publish_special_report.py /absolute/path/FINAL.md --date YYYY-MM-DD --publish --approval /absolute/path/private-review.json
```

工具仅生成文章 HTML，更新 intelligence.html 的 Special Reports 区块、专题目录、首页 Special Reports 最新文章卡片与 sitemap.xml。验证桌面/手机排版、正文/脚注/附录、链接、最新置顶及其他栏目未变化，审查 `git diff --check`。按官网现有方式 fetch 最新 main、提交精确文件、push；确认部署 commit 并访问线上页面。不要发布尚未过门槛的文章。


## 用户指定配图

提供 `--image /absolute/path/authorized.jpg --image-alt "图片描述" --image-width 1400 --image-height 600`（宽高必须为实际原图尺寸）。工具原样复制 JPEG 到 `/special-reports/assets/`，在主标题后、正文前居中显示，最大宽度980px，按原始比例适配手机。核验记录需增加 image_sha256，将图片授权绑定到实际文件。不得从原文网站下载第三方配图替代用户授权图。

首篇文章允许用户指定日期直接发布；后续默认每周日由用户上传触发，不创建自动调度，不把原始报告日期当网站发布日期。


## 首页同步

正式发布时同一工具更新 index.html 中独立的 SPECIAL REPORTS HOME 区块，只显示最新一篇的标题、网站发布日期、简短摘要、阅读链接与全部专题入口。模块始终位于 Weekly Outlook 下方。优先使用 FINAL.md 的 summary 或 description；缺省时截取正文首个普通段落（最多140字），不另写研究内容。历史回填不会替换首页较新的文章。原有《环球脉搏》、Daily Headlines、Weekly Outlook 的 HTML、样式和脚本不变；无需新增自动化或修改 Website Skill。发布提交必须包含 index.html。
