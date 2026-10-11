# 来源图片规则 / Source images

王总在 t172u 中说：“以后可以适当放一些能发布的资讯源照片”。以下具体规则由 Grok Bot 根据这句话制定。适用范围：2026-10-12 起的每日信号。

## 规则
1. 每日信号和文章可以在合适时使用**可公开发布的来源图片**。
2. 允许的图片：许可明确允许再使用的图片（例如 CC BY 论文图表）；或发布方明确允许再使用的新闻稿图片。许可不清楚的，不用。
3. 每张图片下方注明：来源、作者、许可、原始链接。
4. 存档（逐张核实许可）：
   - 原图文件只有在逐张核实其许可**同时**允许 (a) 在本站展示，和 (b) 在公开仓库中再发布原图文件之后，才放入 markjin-data 新仓库（公开）当天的 `raw/<日期>/`，sha256 登记进当天的 `MANIFEST.sha256`。
   - 许可证据同时存档：许可页面 URL，以及该页面保存快照的 sha256。
   - (a) 在本站展示的许可未核实的：该图片完全不得在本站使用。
   - (a) 已核实允许展示、但 (b) 在公开仓库再发布原图文件不允许或未核实的：公开仓库只记录原始 URL 和 sha256，原图文件只保留在本机，保留 90 天。
   - 所有 `MANIFEST` 文件只追加，不修改、不删除已有行。
5. “修改”的界定：
   - 允许：为网页显示做等比例缩放、格式转换或质量重新压缩——前提是原图文件按第 4 条原样存档，并且同时记录实际显示的派生文件的 sha256。
   - 不允许：裁剪、修图、加标注、调色、拼合多图。
   - 不得把 AI 生成的图片当作来源图片使用。
6. zh 和 en 两个版本都带同样的图片。
7. 图片与稿件一起送 Codex 审查。
8. **门禁：任何一张图片不符合以上规则，稿件不得发布**（去掉该图片或补齐后重新审查）。

## Rules (English)
王总 said in t172u: "以后可以适当放一些能发布的资讯源照片" ("from now on we can, where appropriate, include some publishable source photos"). Grok Bot set the specific rules below on the basis of that sentence. Applies to daily posts from 2026-10-12.
1. Daily posts and articles may include, where appropriate, publicly publishable source images.
2. Allowed: images whose license explicitly permits reuse (e.g. CC BY paper figures), or press-release images whose publisher explicitly permits reuse. Unclear license: don't use it.
3. Under each image: source, author, license, link to the original.
4. Archiving (license checked per image): the original goes into the new public markjin-data repository `raw/<date>/` (sha256 in that day's `MANIFEST.sha256`) only after checking, for each image, that its license allows both (a) display on the site and (b) republishing the original file in a public repository. Archive the license evidence: the license page URL plus the sha256 of a saved snapshot of that page. If (a) display permission is not verified, the image must not be used on the site at all. Only when (a) display is allowed but (b) republishing the original in a public repository is not allowed or not verified: record only the URL and sha256 publicly and keep the original on the local machine for 90 days. All MANIFEST files are append-only.
5. Editing: proportional resizing and format/quality recompression for web display are allowed only if the original is archived unchanged and the displayed derivative's sha256 is recorded too. Cropping, retouching, annotation, colour changes and composites are not allowed. No AI-generated images passed off as source images.
6. Both the zh and en versions carry the images.
7. Images go through Codex review together with the post.
8. Gate: any image that fails these rules blocks publication.

## 门禁 / 校验说明（暂无代码改动）
- Codex 审查清单：每张图片的来源/作者/许可/原始链接四项是否齐全；许可是否明确允许再使用；存档方式是否与许可相符（(a) 展示许可未核实的图片一律不得使用；(a)(b) 均已核实才放公开 raw/；(a) 已核实而 (b) 不允许或未核实的仅记 URL+sha256、原图本机保留 90 天）；许可证据（许可页 URL + 快照 sha256）是否存档；派生文件 sha256 是否记录；zh/en 图片是否一致。任一项不符即判不通过，稿件不得发布。
- 后续可在校验脚本中自动检查上述各项；本 PR 只写规则，不改代码。
