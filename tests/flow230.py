"""Swim Opt 2.30 walk-through in test mode (Playwright): the half-day simulation fixes that show on screen.
  decision 193 (problem 5): two Place Judges on one race see a note, and the one whose places were replaced is told
  decision 194 (problem 8): after refused photos, a race the Recorder typed in full shows Next race on Time Slips
  decision 192 (problem 11): "Clearing..." stays until Clear practice data is done
Run: python3 tests/flow230.py "http://127.0.0.1:8102/?mode=local"   (from a scratch folder: it writes flow230-shots/)"""
import asyncio, sys, os
from playwright.async_api import async_playwright
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8102/?mode=local"
os.makedirs("flow230-shots", exist_ok=True)
fails, errs = [], []
def check(ok, name):
    print(("ok  " if ok else "FAIL"), name); ok or fails.append(name)

async def main():
  async with async_playwright() as pw:
    b = await pw.chromium.launch()
    ctx = await b.new_context(viewport={"width": 1512, "height": 982})
    async def page(name, w=1512, h=982):
        p = await ctx.new_page(); await p.set_viewport_size({"width": w, "height": h})
        p.on("pageerror", lambda e: errs.append((name, str(e))))
        p.on("console", lambda m: errs.append((name, m.text)) if m.type == "error" else None)
        await p.goto(URL); await p.wait_for_function("!!A.store"); return p
    async def pin(p, c):
        for k in c: await p.click(f'[data-act=key][data-k="{k}"]')
        await p.wait_for_timeout(150)
    ev = lambda p, js: p.evaluate(js)
    async def shot(p, n): await p.screenshot(path=f"flow230-shots/{n}.png", full_page=True)

    O = await page("org"); await pin(O, "9999"); await O.click('[data-act=year][data-v=current]'); await O.click('.tile[data-job=organiser]')
    await O.click('[data-act=osec][data-v=students]'); await O.click('[data-act=otest]'); await O.click('[data-act=oimport]'); await O.wait_for_timeout(200)
    M = await page("marshal", 1180, 820); await pin(M, "1111")
    async def group(k, x, g):
        await M.click(f'[data-act=mpick][data-v={k}]'); await M.click(f'[data-act=mpick][data-v={x}]'); await M.click(f'[data-act=mpick][data-f=g][data-v="{g}"]'); await M.click('[data-act=mgo]')
    async def fill(n):
        for _ in range(n): await M.click('.picklist button[data-act=mset]:not([disabled]) >> nth=0')
    await group("back50", "F", "14"); await fill(4); await M.click('[data-act=mnew]'); await M.click('[data-act=mconfirm]'); await M.wait_for_timeout(150)
    await group("free50", "F", "14"); await fill(3); await M.click('[data-act=mnew]'); await M.click('[data-act=mconfirm]'); await M.wait_for_timeout(150)
    check(await ev(M, "A.heats.length") == 2, "two races sent")

    # decision 193: two Place Judges on race 1
    J1 = await page("judge1", 390, 844); await pin(J1, "2222")
    J2 = await page("judge2", 390, 844); await pin(J2, "2222"); await J2.wait_for_timeout(400)
    note = "Another Place Judge is on Race 1"
    check(note in await J1.inner_text("main") and note in await J2.inner_text("main"), "193: both judges on race 1 see the note")
    await shot(J2, "193-two-judges-note")
    for l in [1, 2, 3, 4]: await J1.click(f'[data-act=jtap][data-l="{l}"]'); await J1.wait_for_timeout(60)
    await J2.wait_for_timeout(300)
    await J2.click('[data-act=jreset]'); await J2.click('[data-act=jresetok]'); await J2.wait_for_timeout(100)
    for l in [2, 1, 4, 3]: await J2.click(f'[data-act=jtap][data-l="{l}"]'); await J2.wait_for_timeout(60)
    await J2.wait_for_timeout(300)
    t1 = await ev(J1, "document.getElementById('toast').hidden?'':document.getElementById('toast').textContent")
    check("Another Place Judge changed the places for Race 1" in t1, "193: the judge whose places were replaced is told (toast)")
    await shot(J1, "193-replaced-toast")
    t2 = await ev(J2, "document.getElementById('toast').hidden?'':document.getElementById('toast').textContent")
    check("Another Place Judge changed" not in t2, "193: no toast for the judge's own save")
    await J1.click('[data-act=jnext]'); await J1.wait_for_timeout(400)
    check(note not in await J2.inner_text("main") and "Another Place Judge is on Race" not in await J1.inner_text("main"),
          "193: the note goes once the judges are on different races")

    # decision 194: Time Slips, two refused photos, then the Recorder types race 2 in full
    S = await page("slips", 390, 844); await pin(S, "4444"); await S.wait_for_timeout(200)
    await ev(S, "A.s.race=2;render()")
    await S.click('[data-act=stest][data-v=bad]')
    for _ in range(2):
        await S.set_input_files("#camin", os.path.join(os.path.dirname(os.path.abspath(__file__)), "slip.jpg")); await S.wait_for_timeout(600)
    check("take again" in (await S.inner_text("main")).lower() and await S.locator('[data-act=snext]').count() == 0, "194: refused photos show Take again")
    R = await page("recorder"); await pin(R, "3333"); await R.wait_for_timeout(150)
    await R.click('[data-act=rgoto]'); await R.click('[data-act=pickrace][data-race="2"]'); await R.wait_for_timeout(100)
    for l, t in [(1, "3550"), (2, "3650")]:
        await R.fill(f"#t-2-{l}", t); await R.press(f"#t-2-{l}", "Enter"); await R.wait_for_timeout(150)
    await S.wait_for_timeout(300)
    check("take again" in (await S.inner_text("main")).lower(), "194: part typed: still Take again")
    await R.fill("#t-2-3", "3750"); await R.press("#t-2-3", "Enter"); await R.wait_for_timeout(150); await S.wait_for_timeout(400)
    txt = await S.inner_text("main")
    check("Race 2 times are in from the Recorder. No photo needed." in txt and "Could not read" not in txt, "194: all typed: the green line shows, the red message goes")
    check(await S.locator('[data-act=snext]').count() == 0 and "Waiting for marshal" in txt, "194: last race: Waiting for marshal shows in place of Next race")
    await shot(S, "194-times-from-recorder")

    # decision 192: Clearing... stays until done (test mode clears record by record)
    await O.click('[data-act=osec][data-v=run]') if await O.locator('[data-act=osec][data-v=run]').count() else None
    await ev(O, "window.__t=[];const o=toast;window.toast=(m,ms)=>{__t.push([m,ms||3000]);o(m,ms)}")
    await ev(O, "clearPractice()"); await O.wait_for_timeout(800)
    seen = [x for x in await ev(O, "__t") if x[0]]
    check(seen and seen[0][0] == "Clearing..." and seen[0][1] >= 60000 and seen[-1][0] == "Practice data cleared", "192: Clearing... stays until Practice data cleared replaces it")
    check(await ev(O, "A.heats.length") == 0 and await ev(O, "A.counter") == 1, "clear: no races, race number 1")

    check(not errs, "no page or console errors " + str(errs[:3]))
    await b.close()

asyncio.run(main())
print(f"\n{len(fails)} failed" if fails else "\nall passed")
sys.exit(1 if fails else 0)
