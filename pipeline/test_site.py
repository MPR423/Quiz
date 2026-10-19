"""Smoke-test the static site in headless Chromium at phone size; screenshots go to build/shots/.

    python pipeline/build.py && python pipeline/test_site.py
Needs: pip install playwright (and a Chromium that Playwright can launch). Optional; CI does not run it.
"""
import subprocess, time, sys, os
from playwright.sync_api import sync_playwright

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root
OUT = os.path.abspath("build/shots")
os.makedirs(OUT, exist_ok=True)
srv = subprocess.Popen([sys.executable, "-m", "http.server", "8765", "--directory", "site"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
errors = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        pg.goto("http://localhost:8765/")
        pg.wait_for_selector(".bank")
        pg.screenshot(path=f"{OUT}/01_home.png", full_page=True)
        # select EM bank, start quiz
        pg.click('[data-bank="em114a"]')
        pg.click("#start")
        pg.wait_for_selector(".opt")
        pg.screenshot(path=f"{OUT}/02_q1.png", full_page=True)
        pg.click('[data-opt="B"]')  # wrong answer (official C)
        pg.wait_for_selector(".result")
        pg.screenshot(path=f"{OUT}/03_q1_answered.png", full_page=True)
        # go to Q7 (figure + flag)
        for _ in range(6):
            pg.click("#next")
        pg.wait_for_selector(".imgs img")
        pg.click('[data-opt="B"]')
        pg.screenshot(path=f"{OUT}/04_q7.png", full_page=True)
        # home -> NS multi bank
        pg.click('[data-go="#/"]')
        pg.click('[data-bank="em114a"]')
        pg.click('[data-bank="ns-m"]')
        pg.click("#start")
        pg.wait_for_selector(".opt")
        pg.click('[data-opt="A"]'); pg.click('[data-opt="C"]')
        pg.screenshot(path=f"{OUT}/05_ns1_selecting.png", full_page=True)
        pg.click("#submit")
        pg.wait_for_selector(".result")
        pg.screenshot(path=f"{OUT}/06_ns1_answered.png", full_page=True)
        # review mode toggle
        pg.click("#modeBtn")
        pg.click("#next")
        pg.screenshot(path=f"{OUT}/07_ns2_review.png", full_page=True)
        # stats + settings + search
        pg.goto("http://localhost:8765/#/stats"); pg.wait_for_selector("table.stats")
        pg.screenshot(path=f"{OUT}/08_stats.png", full_page=True)
        pg.goto("http://localhost:8765/#/search?q=dopamine"); pg.wait_for_selector(".li")
        pg.screenshot(path=f"{OUT}/09_search.png", full_page=True)
        pg.goto("http://localhost:8765/#/settings"); pg.wait_for_selector("#exp")
        # dark mode render of a question
        ctx2 = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, color_scheme="dark", is_mobile=True, has_touch=True)
        pg2 = ctx2.new_page()
        pg2.on("pageerror", lambda e: errors.append(str(e)))
        pg2.goto("http://localhost:8765/")
        pg2.wait_for_selector(".bank")
        pg2.click('[data-bank="ns-m"]'); pg2.click('[data-mode="review"]'); pg2.click("#start")
        pg2.wait_for_selector(".exp")
        pg2.screenshot(path=f"{OUT}/10_dark_review.png", full_page=True)
        # progress persisted?
        prog = pg.evaluate("localStorage.getItem('bx.progress.v1')")
        print("progress:", prog[:300])
        # opened straight from disk (file://): must load the banks and run a question
        site_abs = os.path.abspath("site")
        ctx3 = b.new_context(viewport={"width": 390, "height": 844})
        pg3 = ctx3.new_page()
        ferr = []
        pg3.on("pageerror", lambda e: ferr.append(str(e)))
        pg3.on("console", lambda m: ferr.append(m.text) if m.type == "error" and "anifest" not in m.text else None)
        pg3.goto(f"file://{site_abs}/index.html")
        pg3.wait_for_selector(".bank", timeout=5000)
        nb = pg3.eval_on_selector_all(".bank", "els => els.length")
        pg3.screenshot(path=f"{OUT}/11_file_home.png", full_page=True)
        pg3.click('[data-bank="em114a"]'); pg3.click("#start"); pg3.wait_for_selector(".opt")
        pg3.click('[data-opt="C"]'); pg3.wait_for_selector(".result")
        print("file:// ok, banks:", nb, "errors:", ferr)
        errors.extend(ferr)
        # broken copies: no data folder -> explicit hint; no app.js -> static fallback text
        import shutil, tempfile
        tmp = tempfile.mkdtemp()
        shutil.copytree("site", f"{tmp}/nodata"); shutil.rmtree(f"{tmp}/nodata/data")
        shutil.copytree("site", f"{tmp}/nojs"); os.remove(f"{tmp}/nojs/app.js")
        pg3.goto(f"file://{tmp}/nodata/index.html"); pg3.wait_for_timeout(800)
        t = pg3.inner_text("#app"); print("no-data msg:", t.replace("\n", " ")[:90])
        assert "解壓縮" in t and "載入失敗" in t
        pg3.goto(f"file://{tmp}/nojs/index.html"); pg3.wait_for_timeout(500)
        t = pg3.inner_text("#app"); print("no-js msg:", t.replace("\n", " ")[:60])
        assert "解壓縮" in t
        shutil.rmtree(tmp)
        b.close()
finally:
    srv.terminate()
print("errors:", errors)
sys.exit(1 if errors else 0)
