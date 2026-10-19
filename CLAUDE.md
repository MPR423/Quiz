# 專科考題詳解網站 — 工作說明（每個 session 先讀）

這個 repo 是唯一的真實來源：題目、官方答案、詳解、網站程式都在這裡。
push 到 main → GitHub Actions 跑 build＋檢查 → 通過才部署到 GitHub Pages（約 1–2 分鐘）。檢查失敗時網站停在上一版。

讀者是準備台灣急診／外科專科考試的醫師。用繁體中文、術語保留英文；不迎合，邏輯與證據優先，不確定就直說。

## 結構
| 路徑 | 內容 |
|---|---|
| `banks/<id>/meta.json` | 題庫設定：標題、單選/複選、次專科分類（taxonomy）、預設次專科、PDF 來源、parser、亂碼修正 `fixes` |
| `banks/<id>/questions.json` | 題目與官方答案（parser 產生，**不要手改**） |
| `banks/<id>/exp/NNN-NNN.md` | 詳解，一批一檔（主要工作） |
| `banks/<id>/img/` | 題目附圖 |
| `sources/` | 原始 PDF |
| `taxonomy.json` | 次專科封閉清單（`em`、`surg`…） |
| `pipeline/` | `build.py` `check.py` `status.py` `show.py` `ingest.py` `parse_*.py` |
| `site/` | 前端；`site/data`、`site/img` 由 build 產生，不進版控 |
| `docs/style.md` | **詳解寫作規範（寫詳解前必讀）** |
| `docs/decisions.md` | 使用者做過的決定與進度紀錄 |

## 開場
1. `git fetch origin`，確認目前工作基於最新的 `origin/main`（`git merge-base --is-ancestor origin/main HEAD`）；不是的話先 `git rebase origin/main`。session 分支可能是舊版本，不要把落後的 commit merge 回 main。
2. 若 repo 根目錄有 `MIGRATION.md`，先照它做完（一次性）。
3. `python pipeline/status.py` 看進度。
4. 列出使用者回報：`gh api "repos/<owner>/<repo>/issues?labels=回報&state=open"`（owner/repo 從 `git remote get-url origin` 解析）。有的話先告訴使用者，照使用者指示決定要不要先處理。

進度以 `status.py` 為準；`docs/decisions.md` 只記里程碑與決定。
5. 照使用者指示做；指示不清楚就問。

## A. 寫詳解（最常見）
1. `python pipeline/status.py <bank>` → 列出未寫題號，並建議下一批（最多 10 題連續題號）與檔名；`python pipeline/show.py <bank> --next 10` 印出同一批題目（有圖就用 Read 打開 `banks/<bank>/img/...`）。使用者指定題號時照指定，用 `show.py <bank> <起> <迄>`。
2. 照 `docs/style.md` 寫進 `banks/<bank>/exp/<起>-<迄>.md`：檔名＝這個檔案實際涵蓋的題號（三位數，如 `001-003.md`）；一檔只放連續題號，一批不一定剛好 10 題。
3. `python pipeline/build.py && python pipeline/check.py`，兩者都要 0 problems。有改到 `site/` 時另跑 `node --check site/app.js && node --check site/sw.js`（CI 也會跑），可選 `python pipeline/test_site.py`。
4. 每批一個 commit，訊息格式 `<bank>: Q1–Q10 詳解`（en dash，兩端都寫 Q）→ `git pull --rebase` → `git push origin HEAD:main`。不要攢很多批才 commit：session 中斷時，已 commit 的都不會丟。
5. 題量大時用 subagent 平行：每個 subagent 負責一個不重疊題號範圍的檔案，告訴它讀 `docs/style.md`、用 `show.py` 看題目、只寫自己的檔案。主 session 負責分派、跑 build＋check、修正、commit。同一題庫不要兩個 session 同時寫同一段題號。
6. 一個題庫寫完後做 C（查證），並更新 `docs/decisions.md` 的進度。

## B. 匯入新題庫
1. 使用者把 PDF 放進 `sources/`（或在對話中提供）。先 `pip install -r pipeline/requirements.txt`。
2. `python pipeline/ingest.py --pdf sources/<file>.pdf --id <id> --title "<標題>" --short "<簡稱>" --group 外科 --taxonomy surg --sub-default <科>`（`--help` 有完整說明）。
   - id 命名：科別縮寫-類型，例如 `gs-m`（一般外科複選）、`gs-s`（單選）；急診年度卷 `em<年><卷>`，例如 `em113b`。
   - 次專科清單不夠用時，先跟使用者確認再改 `taxonomy.json`。
3. 對照 PDF 檢查 ingest 印出的摘要：題數、缺號、答案分布、範例題、亂碼（有就在 `meta.json` 的 `fixes` 加 `[原字串, 修正]`）。版面跟現有 parser 不同時，複製最接近的 `parse_*.py` 改欄位規則，不要硬套。
4. build＋check 通過 → commit → push → 向使用者回報題數與疑點。

## C. 查證（每個題庫寫完後一次）
用全新 context 的 subagent 重看所有 ⚠️ 與信心中／低的題：查最新指引、確認每個引用真實存在、數值與劑量正確。修正內容或調整信心度後 commit。

## D. 處理回報（label「回報」的 issue）
讀 issue → 查證 → 修改對應詳解，或確認原本正確 → build＋check → commit 訊息含 `fixes #<編號>`（issue 會自動關閉）→ push。回報本身有誤時，在 issue 留言說明依據，不要照改。

## 硬規則
- 不改官方答案、題號、題目 id（使用者的作答紀錄綁定 id `<bank>-NNN`）。PDF 擷取的錯字用 `meta.json` 的 `fixes` 修，不改 `questions.json`。
- ★ 永遠標在官方答案上；與現行證據衝突時仍照官方標 ★，另寫 `flag:`（⚠️）。`check.py` 會擋。
- 引用只用真實存在、查得到的指引或教科書（名稱＋版次／年份，不寫頁碼）。查不到就不寫，絕不編造。
- 不要改 `.github/workflows/`（GitHub App 可能沒有權限；需要改時請使用者在 GitHub 網頁上改）。
- 不要 commit `build/`、`site/data/`、`site/img/`（`.gitignore` 已排除）。
- push 前一定 build＋check 通過。push 後若 Actions 失敗，立刻修。
