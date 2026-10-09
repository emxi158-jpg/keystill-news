# Keystill weekly news

This repository contains public news data and its small updater only. The Keystill website and all training records remain outside this repository.

每周更新三条简短双语资讯：世界热点、文化、艺术各一条。采用 BBC World 和 The Guardian 的公开 RSS 标题及短摘要，保留原文链接、来源和发布日期，不抓取文章全文。

## 自动运行

- 每周一北京时间约 09:17 运行，GitHub 的定时运行可能延迟。
- 也可以在 Actions → Weekly Keystill news → Run workflow 手动触发。
- 默认分支需要包含 `.github/workflows/weekly-news.yml`，并允许 GitHub Actions 运行。
- 使用标准 Linux 运行环境，公开仓库的此类运行免费，不调用 Codex、OpenAI 或其他收费 AI 接口。
- 任务最多运行五分钟，不上传 Actions 制品，不使用缓存，也无需设置个人访问令牌。
- 自动提交权限仅用于这个资讯仓库的文件，不需要访问 Keystill 私有仓库。
- GitHub 可能暂停长期无活动的公开仓库定时任务；如出现暂停，可在 Actions 页面重新启用。

## 翻译与内容

使用 MyMemory 的匿名免费翻译接口，仅发送公开标题和短摘要，不发送任何训练记录、账号信息或密钥。每次运行最多提交 1,400 个字符，接口限额、质量和可用性由服务方决定。机器翻译可能有错误，内容始终标注机器翻译，原文链接可用于核对。

这是自动筛选的 RSS 简讯，不是人工核实或 AI 撰写的长文章。优先选最新内容，仅接受最近 31 天的内容，同一批次不会重复来源链接。无法保证每周都有合适的新内容；来源、翻译或运行失败时保留上一批，不编造新闻，不用旧日期冒充新日期。

## 网页读取地址

`https://raw.githubusercontent.com/emxi158-jpg/keystill-news/main/news.json`

Keystill 的“更新时事”按钮读取这一个公开 JSON 地址并缓存到浏览器本地。首次使用需要已有一批成功生成的数据，且当前网络允许访问 raw.githubusercontent.com。GitHub 原始文件可能有短暂缓存延迟。

## 手动运行与停用

有 Python 3 的环境可运行 `python3 update_news.py --output news.json`。不需要安装 Python 依赖。

在 Actions 页面选择 Disable workflow 即可停用定时更新，也可删除工作流文件。现有本地资讯缓存仍然可用。

参考：[GitHub Actions 计费](https://docs.github.com/en/billing/concepts/product-billing/github-actions)、[MyMemory 免费额度](https://mymemory.translated.net/doc/usagelimits.php)、[接口说明](https://mymemory.translated.net/doc/spec.php)。
