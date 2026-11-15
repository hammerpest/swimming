"""Swim Opt 2.30: tests js/store-supabase.js against a stand-in Supabase (no network, no Supabase project).
Covers the half-day simulation fixes that live in the store:
  problem 26: at most 4 presence updates in 30 seconds (Supabase closes the channel after 5), and a closed
              channel is joined again by itself, with every table read again; "live" is false while it is down
  problem 27: a late slip or multitimer send is merged with the server's copy as it goes (typed time kept)
  problem 28: Clear practice data is one server call, then only this carnival's slip photos are removed
  finding 6:  saves of one record arrive in the order they were made, however slow the first one is
Run (server on 8102): ../.venv/bin/python tests/store230.py "http://127.0.0.1:8102/?mode=local"
Takes about 40 seconds (it waits out one 30 second presence window)."""
import asyncio, sys
from playwright.async_api import async_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8102/?mode=local"
fails = []
def check(ok, name):
    print(("ok  " if ok else "FAIL"), name); ok or fails.append(name)

MOCK = r"""
(() => {
  const M = window.MOCK = {db: {}, tracks: [], subs: 0, selects: 0, rpcs: [], removed: [], delays: [], channels: [], role: 'judge',
    files: ['r0001.jpg', 'r0002.jpg', 'y2026-r0001.jpg']};
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const tbl = t => M.db[t] || (M.db[t] = {});
  function q(t) {
    let id = null;
    const o = {
      select() { return o }, eq(k, v) { id = v; return o },
      async maybeSingle() { M.selects++; await wait(5); const d = tbl(t)[id]; return {data: d ? {doc: JSON.parse(JSON.stringify(d))} : null, error: null} },
      then(ok, no) { M.selects++; return Promise.resolve({data: Object.entries(tbl(t)).map(([id, doc]) => ({id, doc})), error: null}).then(ok, no) },
      async upsert(row) { const ms = M.delays.length ? M.delays.shift() : 5; await wait(ms); tbl(t)[row.id] = JSON.parse(JSON.stringify(row.doc)); return {error: null} },
      delete() { return {eq: async (k, v) => { delete tbl(t)[v]; return {error: null} }} }
    };
    return o;
  }
  function channel(name) {
    const cbs = {}; let cb = null;
    const ch = {topic: 'realtime:' + name, n: ++M.subs,
      on(ev, f, g) { return ch }, subscribe(f) { cb = f; setTimeout(() => cb('SUBSCRIBED'), 20); return ch },
      track(body) { const now = Date.now(); M.tracks.push({at: now, body, ch: ch.n});
        /* Supabase: more than 5 in 30 seconds and the channel is closed */
        if (M.tracks.filter(x => x.ch === ch.n && now - x.at < 30000).length > 5) setTimeout(() => cb && cb('CLOSED'), 10);
        return Promise.resolve('ok') },
      presenceState() { return {} }, teardown() {}, close() { cb && cb('CLOSED') }};
    M.channels.push(ch); M.last = ch; return ch;
  }
  window.supabase = {createClient() {
    const sb = {
      auth: {async getSession() { return {data: {session: {}}} }, async signInAnonymously() { return {} }},
      from: q,
      async rpc(name, args) { M.rpcs.push([name, args]);
        if (name === 'my_role') return {data: M.role, error: null};
        if (name === 'clear_practice') { for (const t of ['heats', 'times', 'finish', 'slips', 'extras']) M.db[t] = {}; return {data: 3, error: null} }
        return {data: null, error: null} },
      channel, getChannels() { return M.channels.filter(c => !c.gone) },
      async removeChannel(c) { c.gone = true; return 'ok' },
      realtime: {async setAuth() {}, _remove(c) { c.gone = true }},
      storage: {from() { return {
        async list() { return {data: M.files.map(name => ({name})), error: null} },
        async remove(names) { M.removed.push(...names); M.files = M.files.filter(f => !names.includes(f)); return {data: [], error: null} },
        async upload() { return {error: null} }, async download() { return {error: {statusCode: '404'}} }}}}
    };
    return sb;
  }};
  window.SWIM_CONFIG = {url: 'https://mock.invalid', key: 'mock'};
  history.replaceState(null, '', location.pathname);
})();
"""

async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); p = await b.new_page()
        errs = []; p.on("pageerror", lambda e: errs.append(str(e)))
        await p.goto(URL); await p.wait_for_function("typeof supabaseStore==='function'&&!!A.store")
        await p.evaluate("localStorage.removeItem('swim_queue')")
        await p.evaluate(MOCK)
        await p.evaluate("(async()=>{window.S=await supabaseStore(()=>{window.QN=(window.QN||0)+1})})()")
        await p.wait_for_function("MOCK.tracks.length>=1", timeout=5000)
        check(await p.evaluate("S.live"), "store: live once the channel is joined")

        # problem 26: ten presence changes in a row (a Recorder going through races fast)
        await p.evaluate("for(let i=0;i<10;i++)S.presence({rec:i,recSince:i})")
        await asyncio.sleep(1.5)
        n1 = await p.evaluate("MOCK.tracks.length")
        check(n1 <= 4, f"presence: at most 4 updates in 30 seconds ({n1} sent)")
        check(await p.evaluate("MOCK.subs") == 1 and await p.evaluate("S.live"), "presence: the channel is not closed by the rate limit")
        await p.evaluate("S.presence({rec:9,recSince:9})")
        check(await p.evaluate("MOCK.tracks.length") == n1, "presence: an update that changes nothing is not sent")

        # the server closes the channel anyway: the store joins again by itself and reads every table again
        sel0 = await p.evaluate("(S.onCol('heats',()=>{}),MOCK.selects)"); await asyncio.sleep(0.3)
        sel0 = await p.evaluate("MOCK.selects")
        await p.evaluate("MOCK.last.close()")
        await asyncio.sleep(0.05)
        check(not await p.evaluate("S.live"), "rejoin: live is false while the channel is closed")
        ok = False
        for _ in range(40):
            await asyncio.sleep(0.1)
            if await p.evaluate("MOCK.subs>=2&&S.live"): ok = True; break
        check(ok, "rejoin: a closed channel is joined again within about a second")
        await asyncio.sleep(0.3)
        check(await p.evaluate("MOCK.selects") > sel0, "rejoin: the tables are read again after joining, so missed changes arrive")
        check(await p.evaluate("(window.QN||0)>=2"), "rejoin: the page is told when live updates stop and start (header)")

        # the newest presence waits for room in the 30 second window, then goes
        await asyncio.sleep(31)
        last = await p.evaluate("MOCK.tracks[MOCK.tracks.length-1].body")
        check(last.get("rec") == 9, "presence: the newest update is sent once there is room")
        win = await p.evaluate("(()=>{const t=MOCK.tracks.map(x=>x.at);let m=0;for(const a of t)m=Math.max(m,t.filter(b=>b>=a&&b-a<30000).length);return m})()")
        check(win <= 5, f"presence: never more than 5 in any 30 seconds ({win})")

        # finding 6: four fast taps; the first save is the slowest
        await p.evaluate("MOCK.delays=[400,200,100,10]")
        await p.evaluate("""Promise.all([1,2,3,4].map(n=>S.set('finish/r0004',{order:[1,2,3,4].slice(0,n).map(l=>[l])})))""")
        got = await p.evaluate("MOCK.db.finish.r0004.order.length")
        check(got == 4, f"order: four fast taps all kept, however slow the first save ({got} places)")

        # problem 27: the Recorder typed lane 4 while the multitimer send waited on the phone
        await p.evaluate("""MOCK.db.times={r0043:{lanes:{4:{t:8193,st:'ok',src:'typed',keep:false,chk:false,slip:null}},checked:false,gen:0}}""")
        await p.evaluate("""(()=>{const raw={lanes:{2:{t:8038,st:'ok',src:'multi'},4:{t:8156,st:'ok',src:'multi'}},src:'multi',checked:false,gen:0};
          return S.set('times/r0043',lateSlip(null,raw),{raw})})()""")
        d = await p.evaluate("MOCK.db.times.r0043.lanes")
        check(d["4"]["t"] == 8193 and d["4"]["src"] == "typed" and d["4"].get("slip") == 8156 and d["2"]["t"] == 8038,
              "late multitimer: the typed time stays and the multitimer time shows as Slip differs")

        # problem 28: Clear practice data
        await p.evaluate("MOCK.role='org';MOCK.db.heats={r0001:{race:1}}")
        n = await p.evaluate("S.clearPractice('run9')")
        rp = await p.evaluate("MOCK.rpcs.filter(r=>r[0]==='clear_practice')")
        check(n == 3 and rp and rp[-1][1]["run_id"] == "run9" and not await p.evaluate("Object.keys(MOCK.db.heats).length"),
              "clear: one server call clears the races")
        check(sorted(await p.evaluate("MOCK.removed")) == ["r0001.jpg", "r0002.jpg"], "clear: this carnival's photos removed, a kept year's photo stays")
        check(not errs, "no page errors " + "; ".join(errs[:3]))
        await b.close()

asyncio.run(main())
print(f"\n{len(fails)} failed" if fails else "\nall passed")
sys.exit(1 if fails else 0)
