"""Swim Opt 2.31 walk-through in test mode (Playwright): two carnivals in one year (decisions 197 to 199, S1.49 version 3).
  Which carnival cards, Add a carnival, open the other carnival, the morning question, the running carnival box
  in 1. Carnival details, job PINs following the running carnival, each carnival keeping its own races.
Run: python3 tests/flow231.py "http://127.0.0.1:8102/?mode=local"   (from a scratch folder: it writes flow231-shots/)"""
import asyncio, sys, os, datetime
from playwright.async_api import async_playwright
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8102/?mode=local"
os.makedirs("flow231-shots", exist_ok=True)
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
        await p.wait_for_timeout(200)
    ev = lambda p, js: p.evaluate(js)
    async def shot(p, n): await p.screenshot(path=f"flow231-shots/{n}.png", full_page=True)
    async def reloaded(p, carn):
        try: await p.wait_for_function(f"typeof A!=='undefined'&&A.store&&A.carn==='{carn}'", timeout=10000)
        except Exception:
            print("STATE", await p.evaluate("[A.carn, A.role, A.running, sessionStorage.getItem('swim_carn'), location.href]")); raise
        await p.wait_for_timeout(300)

    # one carnival: one clear card, and the Add link
    O = await page("org"); await pin(O, "9999")
    cards = await O.locator(".stack.carns .tile").all_inner_texts()
    check(len(cards) == 1 and "2027 SECONDARY" in cards[0].upper() and "Running now" in cards[0], "one carnival: one card, 2027 Secondary, Running now")
    bd = await ev(O, "getComputedStyle(document.querySelector('.stack.carns .tile')).borderTopWidth")
    bg = await ev(O, "getComputedStyle(document.querySelector('.stack.carns .tile')).backgroundColor")
    check(bd == "3px" and bg != "rgba(0, 0, 0, 0)", "the card has its outline and fill without the mouse (197)")
    check(await O.locator("[data-act=addcarn]").count() == 1, "Add a carnival link shows")
    await shot(O, "1-one-carnival")
    await O.click('[data-act=year][data-v=current]'); await O.click('.tile[data-job=organiser]')
    await O.click('[data-act=osec][data-v=students]'); await O.click('[data-act=otest]'); await O.click('[data-act=oimport]'); await O.wait_for_timeout(200)
    check("2027" in await O.locator(".ttl b").inner_text() and "Change year" in await O.locator("header").inner_text(), "one carnival: the header keeps Change year")

    # the Marshal sends race 1 in the Secondary carnival
    M = await page("marshal", 1180, 820); await pin(M, "1111")
    await M.click('[data-act=mpick][data-v=back50]'); await M.click('[data-act=mpick][data-v=F]'); await M.click('[data-act=mpick][data-f=g][data-v="14"]'); await M.click('[data-act=mgo]')
    for _ in range(3): await M.click('.picklist button[data-act=mset]:not([disabled]) >> nth=0')
    await M.click('[data-act=mnew]'); await M.click('[data-act=mconfirm]'); await M.wait_for_timeout(300)
    check(await ev(M, "A.heats.length") == 1 and await ev(M, "A.carn") == "", "Secondary: race 1 sent")

    # add the Primary carnival
    O2 = await page("org2"); await pin(O2, "9999")
    await O2.click("[data-act=addcarn]"); await O2.wait_for_timeout(100)
    check("Add a 2027 Primary carnival?" in await O2.locator(".modal").inner_text(), "Add asks first, naming 2027 Primary")
    await O2.click("[data-act=addcarn1]"); await O2.wait_for_timeout(400)
    cards = await O2.locator(".stack.carns .tile.carn").all_inner_texts()
    check(len(cards) == 2 and "PRIMARY" in cards[1].upper() and "Not running" in cards[1], "two cards: 2027 Primary, Not running")
    check(await O2.locator("[data-act=addcarn]").count() == 0, "no Add link once there are two")
    await shot(O2, "2-two-carnivals")

    # open Primary: the page loads again on it; its own (empty) races; the not running box
    await O2.click('[data-act=year][data-v=carnb_]'); await reloaded(O2, "b_")
    check(await ev(O2, "A.yearPicked") == "current" and await ev(O2, "A.heats.length") == 0, "Primary opens with no races of its own")
    await O2.click('.tile[data-job=organiser]'); await O2.click('[data-act=osec][data-v=details]')
    check("Primary" in await O2.locator(".ttl b").inner_text() and "Change carnival" in await O2.locator("header").inner_text(), "header names 2027 Primary, with Change carnival")
    box = await O2.locator(".msg.warn").first.inner_text()
    check("2027 Primary is not running." in box and await O2.locator("[data-act=mkrunask]").count() == 1, "details: not running box with its button")
    await shot(O2, "3-primary-details")
    # its date set to today (the morning question needs it)
    # a date before the first carnival's year is refused
    await O2.fill("#cDate", "2026-11-20"); await O2.click("[data-act=osavedetails]"); await O2.wait_for_timeout(300)
    check(await ev(O2, "A.cfg.date") != "2026-11-20", "a Primary date in 2026 (before 2027 Secondary) is refused")
    # Primary on 11 February 2027; the page's clock is set to that day for the morning question
    await O2.fill("#cDate", "2027-02-11"); await O2.click("[data-act=osavedetails]"); await O2.wait_for_timeout(300)

    # sign in again as the organiser: the morning question
    await ev(O2, "todayIso=()=>'2027-02-11'")
    await ev(O2, "signOut()"); await O2.wait_for_timeout(200); await pin(O2, "9999"); await O2.wait_for_timeout(300)
    mod = await O2.locator(".modal").inner_text() if await O2.locator(".modal").count() else ""
    check("Today is the 2027 Primary carnival" in mod, "morning question on Primary's date " + repr(mod[:80]))
    await shot(O2, "4-morning")
    await O2.click("[data-act=mkrun]"); await O2.wait_for_timeout(300)
    check(await ev(O2, "A.running") == "b_", "Primary is now the running carnival")
    run_card = await O2.locator(".stack.carns .tile.run").inner_text()
    check("PRIMARY" in run_card.upper() and "Running now" in run_card, "the Primary card says Running now")
    # once per sign-in
    await O2.click('[data-act=year][data-v=current]'); await O2.wait_for_timeout(200)
    check(await O2.locator(".modal").count() == 0, "the morning question is not asked again")

    # the Marshal follows the running carnival by itself
    await reloaded(M, "b_")
    check(await ev(M, "A.heats.length") == 0 and await ev(M, "A.job") == "marshal", "Marshal moved to Primary by itself, no races there")
    # a fresh job PIN opens the running carnival
    J = await page("judge", 390, 844); await pin(J, "2222")
    await J.wait_for_function("A.carn==='b_'", timeout=10000)
    check(await ev(J, "A.carn") == "b_", "Place Judge PIN opens 2027 Primary")

    # back to Secondary with the details button; race 1 is still there
    await O2.click('[data-act=year][data-v=carna]') if await O2.locator('[data-act=year][data-v=carna]').count() else await ev(O2, "openCarn('')")
    await reloaded(O2, "")
    check(await ev(O2, "A.heats.length") == 1, "Secondary still has its race 1")
    await O2.click('.tile[data-job=organiser]'); await O2.click('[data-act=osec][data-v=details]')
    await O2.click("[data-act=mkrunask]"); await O2.wait_for_timeout(100)
    check("Make 2027 Secondary the running carnival?" in await O2.locator(".modal").inner_text(), "the button asks first")
    await O2.click("[data-act=mkrun]"); await O2.wait_for_timeout(300)
    check("2027 Secondary is running now." in await O2.locator(".msg.ok").first.inner_text(), "details: running line")
    await reloaded(M, "")
    check(await ev(M, "A.heats.length") == 1, "Marshal back on Secondary with race 1")

    # the PIN table in Primary shows and changes the shared PINs
    await ev(O2, "openCarn('b_')"); await reloaded(O2, "b_")
    await O2.click('.tile[data-job=organiser]')
    # the level switch cannot make both carnivals Secondary (Primary has no races, so the switch is open)
    await O2.click('[data-act=osec][data-v=program]'); await O2.wait_for_timeout(100)
    await O2.click('[data-act=olevel][data-v=secondary]'); await O2.wait_for_timeout(200)
    check(await ev(O2, "carnLevel(A.cfg)") == "primary", "Primary cannot be switched to Secondary while a Secondary carnival exists")
    await O2.click('[data-act=osec][data-v=details]')
    await O2.fill("#pin-announcer", "5656"); await O2.click('[data-act=opin][data-v=announcer]'); await O2.wait_for_timeout(300)
    A2 = await page("announcer2", 390, 844); await pin(A2, "5656")
    check(await ev(A2, "A.role") == "announcer", "a PIN changed in Primary works for every carnival (198)")

    # Start a new carnival in Primary keeps it as its own kept year; Secondary is not touched
    yr = await ev(O2, "carnYear('b_')")
    await O2.click('[data-act=osec][data-v=lock]'); await O2.click('[data-act=onew]'); await O2.fill('#ncPin', '9999')
    await O2.click('[data-act=onew1]'); await O2.wait_for_timeout(150); await O2.click('[data-act=onew2][data-v=yes]'); await O2.wait_for_timeout(1500)
    ys = await ev(O2, "A.years.map(y=>[y._id,y.key,y.level])")
    check(["b_" + yr, "b_", "primary"] in ys, "Primary kept as b_" + yr + " " + str(ys))
    check(await ev(O2, "carnYear('b_')") == str(int(yr) + 1), "Primary moves to the next year")
    await O2.click('[data-act=changeyear]'); await O2.wait_for_timeout(200)
    past = await O2.locator(f'[data-act=year][data-v="b_{yr}"]').inner_text()
    check(f"{yr} PRIMARY" in past.upper() and "Look only" in past, "Which carnival: the kept Primary year, look only")
    await shot(O2, "5-kept-primary")
    await O2.click(f'[data-act=year][data-v="b_{yr}"]'); await O2.wait_for_timeout(500)
    check(await ev(O2, "A.past") == "b_" + yr and f"{yr} PRIMARY" in (await O2.locator(".ttl b").inner_text()).upper(), "the kept Primary year opens, look only " + str(await ev(O2, "[A.past, hdrTitle(), A.yearPicked]")))
    check(await ev(M, "A.heats.length") == 1, "Secondary still has its race 1")

    check(not errs, "no console errors " + str(errs[:3]))
    await b.close()
  print(f"\n{len(fails)} failed" if fails else "\nall passed"); sys.exit(1 if fails else 0)
asyncio.run(main())
