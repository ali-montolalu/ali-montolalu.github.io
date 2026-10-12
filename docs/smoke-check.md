# 部署后冒烟检查 / Post-deploy smoke check

`scripts/smoke_check.py`（仅用 Python 标准库）由 `.github/workflows/smoke.yml` 对线上站点运行，有三种触发：每次 Pages 部署成功后（`workflow_run`）、手动（`workflow_dispatch`），以及每天 07:15 SGT 的定时巡查（`schedule`，cron `15 23 * * *` UTC）。

**定时巡查**：每天 07:15 SGT 跑一次，不依赖当天有没有部署，用来发现漏发的日报。日报规则从 2026-10-12T07:00 SGT 起生效（`daily_min_effective_from`，见下），所以第一次真正检查日报的定时运行是 2026-10-12 07:15 SGT；此前的定时运行只做其他检查，允许站上没有日报。部署后触发的运行会先等 30 秒让 CDN 更新；定时和手动运行检查的是已经在线的版本，不等 CDN。下文中的“站点路径”都相对于 `--base` 的路径（`--base` 可带子路径，如 `https://example.test/site/`）。

## 部署 SHA
报告（控制台与 JSON 的 `deploy_sha` / `deploy_sha_source`）记录被检查的部署提交：优先用 `--deploy-sha`；未给时读 `$GITHUB_EVENT_PATH` 中的 `workflow_run.head_sha`；都没有时记为 unknown（不判失败）。CI 中传入 `${{ github.event.workflow_run.head_sha }}`；手动触发时该值为空，因此记为 unknown。脚本只记录这个 SHA，不核对线上页面确实来自该提交。

## 检查哪些页面
页面发现（日报列表、首页与 sitemap 中的链接）用 HTML 解析器取 `<a href>`：注释、脚本中的文字不算，`<template>` 和 `<noscript>` 内的链接也不算（链接检查同样忽略这两类元素中的链接与资源）。不用正则匹配原始 HTML。

**发现范围配置**：`scripts/smoke_discovery.json`（可用 `--discovery-config` 指定）。
- `expected_sitemaps`：每次部署都必须提供的 sitemap，当前是 `/sitemap.xml`、`/zh/sitemap.xml`、`/en/sitemap.xml`。每个都用 XML 解析器读取 `<loc>`（不认命名空间前缀）。以下情况都判失败，报告 “sources (sitemap error / retired link)” 并写明原因：非 200（**包括 404**）、空响应体、XML 无法解析、根元素不是 `<urlset>` 或 `<sitemapindex>`、没有任何 `<loc>`。理由是：sitemap 是已下架网址是否仍被列出的检查来源之一，缺失时无法证明。
- `min_pages`：每类页面的最少发现数，当前只有 daily ≥ 1（按中文日报列表或 sitemap 中的不同日报计数）。不足时判失败（“daily (too few)”）。
- **日报的定义**：路径为 `/posts/daily/<YYYY-MM-DD>/`（或 `/en/` 形式）、slug **恰好是日期**的页面。slug 带后缀的页面不是日报，不计入日报数量，也不参与“最新日报”中英配对。欢迎文 `/posts/daily/2026-10-10-welcome/` 及其英文版已按王总 2026-10-12 08:20 决定删除，列入 retired_paths，须返回 404。
- `daily_min_effective_from`（当前 `2026-10-12T07:00`，SGT，格式 `YYYY-MM-DDTHH:MM`）：日报规则的生效时点。最早为 2026-10-12T07:00（首份日报发布截止，`FLOOR_DAILY_EFFECTIVE_EARLIEST`），配置可以改晚、不能改早；为防止无限期推迟，最晚只能到 2026-10-19T07:00（`CAP_DAILY_EFFECTIVE_LATEST`，一周上限）。超出范围的配置判 DISCOVERY CONFIG ERROR；代码在使用时也把生效时点夹在这两个时点之间。**生效前**不要求日报：站上一篇日报都没有时不判失败，报告的 “daily rule:” 一行写明“0 dailies allowed”；但只要发现了中文日报，照常做最新日报的中英配对和逐页检查；只有英文日报而没有中文日报时仍判失败。**生效后**按当天日期巡查：SGT 07:00 及以后，当天（`/posts/daily/<当天日期>/`）的中文日报和英文日报（`/en/posts/daily/<当天日期>/`）都必须存在并成对通过逐页检查（报告中为 “due daily”，与 “latest daily” 一样按 daily 类型检查，套用 800 字母的样本下限和固定免责声明检查）；07:00 之前巡查的是前一天的日报。同时 `min_pages.daily`（1）照常适用，欢迎文不能顶替。这样某天漏发，当天 07:00 之后的任何一次巡查都会失败，而不只是看“站上至少有一份”。该项缺省时按 2026-10-12T07:00。运行时机：每次部署后、手动触发，以及每天 07:15 SGT 的定时巡查（`.github/workflows/smoke.yml` 的 `schedule`，cron `15 23 * * *` UTC），所以没有部署的日子漏发日报也会被发现。
- **规则变更依据**（2026-10-11 23:01）：王总 2026-10-11 23:01 决定（经 Grok Bot 转达，quote_ref t217u）：“删除已发表的两份日报，明天开始正式发布”。合并后到 2026-10-12 07:00（SGT）首份日报发布截止前站上没有日报，因此加上述生效时点；`/posts/daily/2026-10-10/`、`/posts/daily/2026-10-11/` 及其 `/en/` 形式列入 `retired_prefixes` 与 `retired_paths`（必须 404、不得被链接或列入 sitemap）。
- **固定免责声明**（检查项 `disclaimer`）：**目前只对日报生效**。代码里页面类型 daily、macro、cards 都会做这项检查，但发现流程目前只列出首页、日报和关于页，从不发现宏观稿和信号卡，所以这两类实际上没有被检查；等这两类有了页面再接入发现流程，并会开 Issue 跟进。已知局限（同样开 Issue 跟进）：解析器只看最后一个 `<p>`，可能把 `visibility:hidden` 的声明算作可见；声明后接不含 `<p>` 的脚注或列表时仍可能把声明认作末段；包在列表里的声明也可能判错。检查规则：页面 `<article>`（没有时取 `<main>`）中最后一个非空、可见段落必须逐字等于固定句：中文「本文不含投资建议。」，英文 "This article does not constitute investment advice."（只合并空白，其他字符不做归一）。缺失、不在末尾、措辞不同或被隐藏都判失败。关于页、首页不检查。
- `retired_prefixes`：已下架的栏目前缀，当前 `/posts/tongyi/`、`/framework/`、两份已删日报和已删欢迎文 `/posts/daily/2026-10-10-welcome/`（zh 与 `/en` 形式都算）。zh/en 首页、每份预期 sitemap、以及每个被检查页面的站内链接与资源，凡指向这些前缀下的网址，一律判失败（来源中报告 “retired path(s) still listed/linked”，页面中为 `internal_links` 失败）。
- `retired_paths`：已下架的具体网址，每个都必须返回 HTTP 404，否则判失败（“retired <path>”）。当前为统一系统观栏目页与第 1–4 篇、`/framework/`、`/framework/macro/`、`/en/framework/`、`/en/framework/macro/`、`/en/posts/tongyi/`，两份已删日报的四个中英网址，以及已删欢迎文的两个中英网址。不设 aliases 跳转；检查时**不跟随重定向**，旧网址自身必须返回 404，301/302 即使最终落到 404 也判失败。
- **规则变更依据**（2026-10-11）：王总 22:39 决定统一系统观系列和宏观框架相关文章下架保存、不再对外公开（经 Grok Bot 转达，quote_ref t212u）。据此删去“至少 1 个 framework 页”的下限、`/framework/` 发现来源和框架页检查，关于页词组删去一项已下架的框架表述（about 词组下限由 3 降为 2），about 最少字母数由 150 降为 100，并新增上面两项下架检查。
- 配置文件无法读取或格式不对时，报告 “DISCOVERY CONFIG ERROR”，整体 FAIL（发现仍按内置默认值进行）。
- 每次报告都列出**每一个**发现来源（控制台 “discovery sources:” 下逐行列出，JSON 为 `discovery_sources`）。每个来源记录：角色、URL、HTTP 状态、链接或 `<loc>` 数、站内有效路径数、新发现的页面数，以及错误原因。角色包括：种子页（zh/en 首页）、每份预期 sitemap、zh 与 en 日报列表，以及日报 sitemap 回退。预期 sitemap 中的 `<loc>` 若全部不在站点 base 内（站内有效路径为 0），也判失败。
- 日报列表为空、回退到 `zh/`、`en/` sitemap 时，sitemap 解析错误写入日报来源说明。

- 首页：`/` 与 `/en/`。
- 最新每日信号：先取中文最新一篇（从 `/posts/daily/` 列表页取日期最大的一篇，找不到时回退到 `zh/sitemap.xml`），再检查同一日期（同一 slug）的英文页 `/en/posts/daily/<日期>/`。英文同日页面缺失（非 200）即判失败；英文列表的最新日期与中文不同时只记 note，不改变配对。中文日报一篇都找不到时判失败（生效日期前的宽限见上文 `daily_min_effective_from`）。
- 关于页：`/about/` 与 `/en/about/`。
- **规则变更依据**（2026-10-12）：王总 2026-10-12 06:28 在对话里决定：「关于页只留一句定位，原则和联系方式都删掉」。据此关于页只留定位句，删去目标小标题、证据优先原则（含时间表）和联系邮箱；smoke 取消 about 的事件下限和最少字母数；about 的语言比例仍照常检查（2026-10-12 审查意见）。
- （已删除）framework 页：原为在以下来源中找到的、站点路径匹配 `/framework/<一层或多层>/` 的页面（en 路径映射到对应 zh 路径）：zh 与 en 首页、`/framework/` 与 `/en/framework/` 索引页、`sitemap.xml`、`zh/sitemap.xml`、`en/sitemap.xml`，以及已发现的 framework 页（zh 与 en 版）中的链接（广度优先，最多处理 200 页的链接）。不在这些来源中出现的页面不会被检查。该类检查已随框架页下架删除，见上文“规则变更依据”。

## 每页检查
- `status_200`：HTTP 200。
- `visible_text`：响应体为空、`<body>` 中没有 `<main>` 元素（报告 “no <main> element”）、`<body>` 中 `<main>` 不止一个（含嵌套；须恰好一个；`<template>` 或 `<noscript>` 内的 `<main>` 不渲染，不计入也不参与统计），或 `<main>` 中没有可计字符时判失败（首页同样适用）。规则如下，`body_language` 与 Markdown 检查使用同一个解析器和同一套可见性规则：
  - 只计 `<body>` 内 `<main>` 中的文字，页头、导航、页脚不计；HTML 省略 `<body>` 标签时没有可计字符，因此判失败。
  - 以下元素连同全部子孙不计（也适用于 `<html>`、`<body>`、`<main>` 本身）：head/title/script/style/template/noscript；带 `hidden` 属性；`aria-hidden="true"`；行内样式 `display: none`。
  - `visibility: hidden`（或 `collapse`）向下继承，但子孙元素写 `visibility: visible` 会重新显示，与 CSS 一致。
  - 行内样式按声明解析，不做子串匹配：属性名不分大小写、去掉注释、忽略自定义属性（`--x`）；同一属性后写的声明覆盖先写的，但带 `!important` 的先写声明不被后写的普通声明覆盖。只看元素自身的 `style` 属性，不解析 `<style>` 表或外部 CSS。
  - 字符口径（两个函数，`visible_text` 与 `body_language` 共用同一套定义）：`is_letter` = Unicode 类别以 L 开头的字符（字母，含中日韩汉字），排除已知显示为空白的填充字符 U+3164、U+115F、U+1160、U+FFA0、U+2800、U+17B4/U+17B5、U+1CBB/U+1CBC；`is_counted_char` = `is_letter` 或类别以 N 开头的字符（数字）。**语言比例和最少字母数只用 `is_letter`，数字不计**；数字只在 `visible_text`（“页面有可见文字”）中计入。空白、标点、符号以及 U+200B–U+200F、U+2060、U+FEFF 等格式字符都不计。这只是按字符类别和已知字符表判断，不能保证每个被计的字符都有可见字形。
- `html_lang`：`<html lang>` 的主语言与页面语言一致。
- `final_url`（非首页）：请求的 URL 不得被重定向到别的 URL；首页的最终 URL 见下文首页例外。
- `lang_switch`：只看**可见的** `<span class="lang">` 中的链接（隐藏的切换控件不计），须至少有一个，且全部等于期望 URL。比较完整 URL（scheme、host、`--base` 子路径、路径、查询串，不含片段）。期望值为另一语言的对应页；对应页不是 200 或被重定向到别处时，期望值为另一语言首页。
- `body_language`（首页除外）：正文 CJK 比例，取自页面唯一的可见 `<main>`（与 `visible_text` 同一解析器、同一可见性规则和同一字母过滤；不用正则提取，`<main>` 缺失或不止一个时判失败，不会退回整页）。剥离前后各算一次并都报告。剥离：script/style、code/pre、链接文字；en 页另去掉 blockquote；zh 页只去掉“原文/译文”对中的原文行，即每个以“译文：”开头的行的前一行。剥离前后两个比例都须满足 zh ≥ 0.30、en ≤ 0.05。剥离掉的字母超过 60% 判失败；剥离后无正文判失败。每类页面有最少字母数（只计字母，不计数字）：daily 800（about 原为 100；2026-10-12 起关于页只留一句定位，不设最少字母数；语言比例仍照常检查；依据见“规则变更依据（2026-10-12）”）。不足时报告 “sample too small” 并标为 REVIEW 需人工复核，不算通过。
- `markdown_rendered` / `table_styled`：有限的静态规则，只能发现明显问题。Markdown 检查的文字是 `<body>` 中按上述规则可见、且不在 code/pre 内的文字（含页头、页脚，不含 `<head>` 和隐藏内容）：其中不得有 `**`、`__`，也不得有以 `# ` 开头的标题残留。有 `<table>` 时，须每个 table 都有 class，或页内 `<style>` 中有以 `table` 开头的选择器规则（只识别这种写法）。不检查实际渲染效果。
- `internal_links`：主机名比较不分大小写。检查的链接与资源：`<a href>`、`<link href>`；`img`/`script`/`source`/`iframe`/`video`/`audio`/`track`/`embed`/`input` 的 `src`；`img`/`source` 的 `srcset`（按 HTML 规范的 srcset 解析：候选项以逗号分隔，每项是一个不含空白的 URL（URL 本身可含逗号）加可选描述符；URL 末尾的逗号结束该候选项；描述符中括号内的逗号不分隔）；`video poster`；`object data`；行内 `style` 和 `<style>` 中的 `url(...)`。不检查外部 CSS 文件里引用的资源。站内的须返回 200（跟随重定向后），且重定向后不得落到站外；同站重定向报告为 `redirect (warn)`，不算失败。站外链接非 200 只报告（`external (warn)`）。

## 中英页对的关键信息一致（zh+en）
每个同时有 zh、en 两个版本的页面（首页、关于、最新日报），在两页各自的检查之外，再加一条 `zh+en` 结果，任一项不一致即 FAIL（王总 t179u 反馈，经 Grok Bot 转达）。取值范围见下。

**取值范围（可见内容）**：四项检查只看**可见**的文字和链接，范围是 `<main>`、`<header>`（含其中的导航）和 `<footer>` 内部；使用与 `visible_text` 同一个解析器和同一套可见性规则（`hidden`、`aria-hidden="true"`、`display:none`、继承的 `visibility:hidden`、`<template>` 等都不计）。不读原始 HTML。选这个范围，是因为联系方式和站点定位可能写在页头或页脚；`<header>`/`<footer>`/`<main>` 之外的内容（如 `<aside>`、独立的 `<nav>`）不计。因此隐藏的正确链接或文字不能掩盖缺失的可见内容；隐藏的错误链接也不会造成误报。
- `pair_times`（附加检查）：抽取全部 HH:MM 时间（`H:MM`、全角冒号 `：` 也认，统一成两位小时），两页的集合须相同。例：en 页写 11:00、zh 写 06:30 → FAIL。
- `pair_event_times`：按事件比较时间。配置 `event_times` 按页面名列出事件，每个事件为每种语言给出一个或多个标签模式（正则，`{T}` 表示时间的位置），例如“开审”/“review starts at {T}”、“发布”/“published at {T}”、“每周一 {T}”/“every Monday at {T}”。脚本取每种语言第一个命中的模式里的时间，两页同一事件的时间须相同；任一边找不到该事件也判失败。因此即使两页时间的集合和出现顺序都一样，“开审”和“发布”的时间互换也会 FAIL。关于页自 2026-10-12 起不再列时间，不再要求配置事件（`event_times` 可为空对象）。
- `pair_emails`：可见文字中的邮箱和可见的 `mailto:` 链接，集合须相同。邮箱地址不分大小写。`mailto:` 先去掉 `?` 之后的查询部分，再对收件人部分整体做百分号解码，最后按逗号拆分多个地址（所以 `%2C` 与字面逗号等价）。查询参数中的收件人（如 `?cc=`）不参与比较。
- `pair_profiles`：指向外部个人主页的链接（主机在配置 `profile_hosts` 中，如 x.com、github.com，且路径最多一段，如 `https://x.com/<name>`；仓库文件链接不算；忽略 `www.`、末尾 `/` 与片段），集合须相同。其他站外链接（数据来源等）不比。
  - 比较前先规范化每个链接：相对页面 URL 解析（`//x.com/markjin` 这类协议相对链接也能识别）；host 小写并去掉 `www.`；先只去掉与**原始 scheme** 对应的默认端口（http 去 80，https 去 443），然后把 http 统一为 https（**http 与 https 视为同一个主页**）。其他任何端口组合，包括 `https://x.com:80/…` 和 `http://x.com:443/…`，都保留原 scheme 和端口，视为不同链接。末尾斜杠和片段去掉，查询串保留。
- `pair_phrases`：配置 `required_phrases` 按页面名（报告中的名字，如 `home`、`about`）列出必需词组。`home` 和 `about` 必须有词组，这条写在代码里，配置无法删掉。
  - 每项是 `{"zh": …, "en": …}`（一对），或 `{"pairs": [[zh1, en1], [zh2, en2], …]}`（可接受的译法变体，**按对登记**）。只有某一对 i 的 zh_i 出现在 zh 页、**同一对**的 en_i 出现在 en 页时才算命中；zh 与 en 各自命中、但不是同一对时判失败（报告 “not a registered pair”）。不接受空列表，也不接受 zh、en 各自独立的变体列表。
  - 最短长度：含汉字的词组至少 4 个汉字，否则至少 8 个字母；更短的会被配置校验拒绝。
  - 比较时 zh 忽略空白，en 把连续空白视为一个空格并且不分大小写。
- 配置文件：`scripts/smoke_pairs.json`，可用 `--pair-config` 指定别的文件。
- 配置文件无法读取、不是合法 JSON，或格式不对时，报告开头显示 “PAIR CONFIG ERROR”，JSON 中有 `pair_config_error`；每个页对记为 `pair_config` 失败，整体 FAIL。格式不对包括：`profile_hosts` 为空或不是字符串列表；缺少 `required_phrases` 或 `event_times`；`home`/`about` 没有词组；某项为空、过短，或变体没有按对登记；事件模式不含恰好一个 `{T}`、不是合法正则，或除 `{T}` 外还有捕获组（只允许非捕获组 `(?:...)`；匹配时也按命名组取时间，不会因模式异常而崩溃）。

## 写在代码里的下限（配置不能降低）
配置低于以下任何一条，都按配置错误（PAIR CONFIG ERROR / DISCOVERY CONFIG ERROR）处理，整体 FAIL：
- 词组页面：`home`、`about` 必须有词组；条目数至少 home 2 项、about 2 项（`MIN_PHRASES`；about 由 3 降为 2，依据见“规则变更依据”）。
- 事件：无下限（`REQUIRED_EVENTS` 为空；原要求 `about` 含 `review starts`、`publish`、`Monday proposal review`，2026-10-12 随关于页删去时间表而取消）。
- `profile_hosts` 必须包含 `x.com`、`github.com`（`REQUIRED_PROFILE_HOSTS`）。
- 预期 sitemap 必须包含 `/sitemap.xml`、`/zh/sitemap.xml`、`/en/sitemap.xml`（`FLOOR_SITEMAPS`）。
- 发现下限：daily ≥ 1（`FLOOR_MIN_PAGES`），必须是整数，布尔值不算；日报规则生效时点不得早于 2026-10-12T07:00、不得晚于 2026-10-19T07:00 SGT（`FLOOR_DAILY_EFFECTIVE_EARLIEST`、`CAP_DAILY_EFFECTIVE_LATEST`）。framework 下限已删除（依据见上）。
- 下架下限：`retired_prefixes` 必须包含 `/posts/tongyi/`、`/framework/`、`/posts/daily/2026-10-10/`、`/posts/daily/2026-10-11/`（`FLOOR_RETIRED_PREFIXES`）；`retired_paths` 必须包含 `/posts/tongyi/`、`/framework/macro/`、`/en/framework/macro/`、`/posts/daily/2026-10-10/`、`/posts/daily/2026-10-11/`、`/en/posts/daily/2026-10-10/`、`/en/posts/daily/2026-10-11/`（`FLOOR_RETIRED_PATHS`），且每项都须位于某个下架前缀之下。
- 同一词组条目不能同时写 `pairs` 和 `zh`/`en`。

提高这些下限可以直接改配置；降低下限须修改代码中的常量，并经同一 PR 的审查。

- 页对两边不是都返回非空 200 时，页对结果明确记为 `pair_not_run` 失败，并写明两边的状态。
- 词组表维护：`scripts/smoke_pairs.json` 的 `required_phrases` 由 markjin 生产与发布负责维护（Grok Bot 决定）。zh 与 en 词组成对登记；只有改到已登记词组（zh 或 en 任一侧）的 PR，才须在同一 PR 中同步更新该表；未改到已登记词组的文案改动不需要更新。

## 首页例外（审查 bot 选择方案 (a)）
只有确切的首页才按首页处理，而且按跟随重定向后的最终 URL 判断。条件：
- scheme 和 host 与 `--base` 相同；
- 路径等于 base 路径加 `/`（zh）或加 `/en/`（en）；
- 不带查询串或片段；
- 检查的语言和页面 `<html lang>` 都与路径一致。

满足条件的页面不做 `body_language` 判定：报告写 “not checked: home page exemption”，并附剥离前的比例供参考，不影响结果。其余检查照常进行，包括 `visible_text`。以 page_type=home 检查任何不满足条件的 URL，`body_language` 判失败。

## 输出与退出码
- 每页标为 PASS、FAIL、REVIEW（只有 “sample too small” 未通过）或 FAIL+REVIEW（两者都有），控制台和 JSON（每页结果的 `label` 字段）都有。控制台中检查项标为 ok / BAD / REV。
- 退出码：0 = 所有页面全部通过；1 = 至少一项失败，或有页面被标为 REVIEW。
- 本地运行：`python3 scripts/smoke_check.py [--base URL] [--deploy-sha SHA] [--json-out report.json] [--pair-config scripts/smoke_pairs.json] [--discovery-config scripts/smoke_discovery.json]`。输出可读报告 + JSON；CI 中 JSON 作为 `smoke-report` artifact 上传。

## 测试
`python3 -m unittest discover -s tests -v`（fixture：`tests/fixtures/sample-daily.{zh,en}.html`，合成的中英日报样例；其余用例用模拟站点）。
