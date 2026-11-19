"""Sync the public Google Maps list into data/places.json (runs on GitHub Actions)."""
import json, math, datetime, sys, pathlib
from playwright.sync_api import sync_playwright

LIST_URL = "https://maps.app.goo.gl/qUWm2NDYa2iVeVUS8"
LIST_ID = "aKVuiiTUC53ykjW079PrsA"
OUT = pathlib.Path("data/places.json")
JS = """(()=>{let raw=null;(function f(a){if(raw)return;if(typeof a==='string'){if(a.includes('%s')&&a.length>2000&&a.startsWith(")]}'"))raw=a;return}if(Array.isArray(a))a.forEach(f);else if(a&&typeof a==='object')Object.values(a).forEach(f)})(window.APP_INITIALIZATION_STATE);
if(!raw)return null;const data=JSON.parse(raw.replace(/^\\)\\]\\}'\\n/,''));const out=[],seen=new Set();(function walk(a){if(!Array.isArray(a))return;if(a.length>2&&Array.isArray(a[1])&&Array.isArray(a[1][5])&&typeof a[1][5][2]==='number'&&typeof a[2]==='string'){const id=(a[1][6]||[])[1]||a[2];if(!seen.has(id)){seen.add(id);out.push({id,name:a[2],note:a[3]||'',lat:+a[1][5][2].toFixed(5),lng:+a[1][5][3].toFixed(5),addr:a[1][4]||''})}return}a.forEach(walk)})(data);return out})()""" % LIST_ID

def hav(a, b):
    t = math.pi / 180
    h = math.sin((b["lat"]-a["lat"])*t/2)**2 + math.cos(a["lat"]*t)*math.cos(b["lat"]*t)*math.sin((b["lng"]-a["lng"])*t/2)**2
    return 12742 * math.asin(math.sqrt(h))

def fetch():
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(locale="iw-IL")
        pg.goto(LIST_URL, wait_until="domcontentloaded", timeout=60000)
        for _ in range(20):
            pg.wait_for_timeout(1500)
            if "consent." in pg.url:
                for sel in ['button[aria-label*="Accept"]', 'button:has-text("Accept all")', 'form[action*="consent"] button']:
                    try: pg.click(sel, timeout=2000); break
                    except Exception: pass
                continue
            res = pg.evaluate(JS)
            if res: b.close(); return res
        b.close()
    return None

def main():
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    old = json.loads(OUT.read_text()) if OUT.exists() else {"items": []}
    items = fetch()
    if not items:
        old["status"] = "סנכרון אחרון נכשל"; old["lastAttempt"] = now
        OUT.write_text(json.dumps(old, ensure_ascii=False)); print("FAILED"); return
    prev = {p["id"]: p for p in old.get("items", [])}
    new = []; added = []
    for g in items:
        if g["id"] in prev:
            p = dict(prev[g["id"]]); p.update(lat=g["lat"], lng=g["lng"])
            if not p.get("he"): p["name"] = g["name"]
            if g["note"]: p["note"] = g["note"]
        else:
            near = min(prev.values(), key=lambda q: hav(q, g), default=None)
            area = near["area"] if near and hav(near, g) < 1.5 else "אחר"
            p = {"id": g["id"], "name": g["name"], "lat": g["lat"], "lng": g["lng"], "note": g["note"],
                 "cat": "sight", "area": area, "dur": 45, "best": "", "tip": "", "desc": g.get("addr", ""), "new": True}
            added.append(g["name"])
        new.append(p)
    removed = [p["name"] for i, p in prev.items() if i not in {g["id"] for g in items}]
    OUT.write_text(json.dumps({"items": new, "syncedAt": now, "count": len(new), "status": "ok"}, ensure_ascii=False))
    print(f"{len(new)} places; added {added}; removed {removed}")

main()
