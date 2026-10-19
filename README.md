# 專科考題詳解

急診、外科專科醫師甄審考古題＋詳解的靜態網站（GitHub Pages）。

- 題目與官方答案：取自各學會公告的考古題／題庫
- 詳解：AI 撰寫；標 ⚠️（答案爭議）與信心「中／低」的題目請自行查證
- 作答紀錄：只存在你的瀏覽器，請定期在網站 ⚙︎ 匯出備份

## 怎麼運作

```
sources/*.pdf ──ingest──▶ banks/<id>/questions.json
                          banks/<id>/exp/*.md   ◀── Claude 寫詳解
                                   │ git push 到 main
                                   ▼
                GitHub Actions：build → 檢查（★ 對答案、格式）→ 部署 Pages
```

## 日常使用（在 claude.ai/code 或手機 Claude app 的 Code 分頁）

開新 session、選這個 repo，然後說：

| 想做的事 | 說法範例 |
|---|---|
| 看進度 | 「現在進度？」 |
| 繼續寫 | 「做 gs-m 下一批」、「把 gs-m 寫完」 |
| 新題庫 | 「我把 一般外科_複.pdf 放進 sources 了，匯入成 gs-m」 |
| 處理回報 | 「處理回報的 issue」 |
| 查證 | 「查證 gs-m 的 ⚠️ 和信心中低的題」 |

規則與流程都寫在 `CLAUDE.md`，每個 session 會自己讀，不需要重講。

- **新增 PDF**：GitHub 網頁 → `sources/` → Add file → Upload files。
- **回報錯誤**：網站每題詳解右下角「回報錯誤」→ 開 GitHub issue；下次 session 說「處理回報」。
- **本機預覽**：`python pipeline/build.py` 後，直接雙擊 `site/index.html`。

## 檔案
| 路徑 | 內容 |
|---|---|
| `banks/<id>/` | 每個題庫：`meta.json`、`questions.json`、`exp/`（詳解）、`img/` |
| `sources/` | 原始 PDF |
| `pipeline/` | build／check／status／show／ingest 與 PDF parser |
| `site/` | 網站前端（`site/data`、`site/img` 由 build 產生） |
| `docs/` | 寫作規範、決定與進度 |
