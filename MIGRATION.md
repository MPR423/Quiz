# 一次性遷移（第一個 Claude Code session 執行，完成後刪除本檔）

舊版網站是把網站檔案直接放在 repo 根目錄；新版的網站在 `site/`，由 GitHub Actions 部署。

1. 刪掉根目錄的舊網站檔（只刪根目錄，**不要動 `site/` 底下的同名檔**）：
   ```
   git rm -r --ignore-unmatch index.html app.js style.css sw.js manifest.webmanifest data img icons
   ```
2. 建立 issue label「回報」（網站的「回報錯誤」按鈕會用）：
   ```
   gh api repos/{owner}/{repo}/labels -f name=回報 -f color=d93f0b -f description="網站回報的詳解錯誤"
   ```
   （label 已存在會回 422，忽略即可。）
3. 確認 `.github/workflows/deploy.yml` 與 `.gitignore` 存在（Mac 上傳時可能漏掉隱藏檔）。缺的話告訴使用者，請他在 GitHub 網頁上補（GitHub App 可能沒有建立 workflow 的權限）。
4. `python pipeline/build.py && python pipeline/check.py` 通過。
5. `git rm MIGRATION.md`，commit（`遷移到 banks/ 結構，刪除舊網站檔`），push 到 main。
6. 請使用者到 repo 的 Actions 分頁確認 build-and-deploy 成功（綠勾），再打開網站確認題庫正常。
