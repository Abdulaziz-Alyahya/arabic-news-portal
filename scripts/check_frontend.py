"""Local CDP smoke checks; requires FastAPI :8000 and isolated Chrome :9222.
The test fires the registered 60-second timer instead of waiting a minute.
"""
import json, urllib.request, socket, base64, os, struct, time, hashlib
from pathlib import Path
base='http://127.0.0.1:8000'
def get(url):
    with urllib.request.urlopen(url) as r: return r.status,r.read()
stories=json.loads(get(base+'/stories')[1])
assert len(stories)>0
for path in ['/', '/compare?id='+str(stories[0]['cluster_id']), '/static/style.css','/static/theme.js','/static/ui.js','/static/app.js','/static/story.js']:
    assert get(base+path)[0]==200
articles=json.loads(get(base+'/stories/'+str(stories[0]['cluster_id']))[1])['articles']
assert articles and all(all(k in a for k in ['source','headline','political_alignment','ideological_tendency','confidence','url']) for a in articles)
print('PASS: pages, static assets, and real API data;',len(stories),'stories')
tabs=json.loads(get('http://127.0.0.1:9222/json/list')[1])
ws=next(t['webSocketDebuggerUrl'] for t in tabs if t['type']=='page')
from urllib.parse import urlparse
u=urlparse(ws); s=socket.create_connection((u.hostname,u.port)); s.settimeout(15)
key=base64.b64encode(os.urandom(16)).decode()
s.sendall(f'GET {u.path} HTTP/1.1\r\nHost: {u.netloc}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nOrigin: http://localhost:9222\r\n\r\n'.encode())
buf=b''
while b'\r\n\r\n' not in buf: buf+=s.recv(4096)
assert b'101' in buf.split(b'\r\n',1)[0],buf
buf=buf.split(b'\r\n\r\n',1)[1]
def read(n):
    global buf
    while len(buf)<n: buf+=s.recv(65536)
    out,buf=buf[:n],buf[n:]; return out
def recv():
    a,b=read(2); n=b&127
    if n==126:n=struct.unpack('!H',read(2))[0]
    if n==127:n=struct.unpack('!Q',read(8))[0]
    mask=read(4) if b&128 else None
    data=read(n)
    if mask:data=bytes(v^mask[i%4] for i,v in enumerate(data))
    return json.loads(data)
seq=0; errors=[]
def call(method,params={}):
    global seq
    seq+=1; payload=json.dumps({'id':seq,'method':method,'params':params}).encode(); n=len(payload); mask=os.urandom(4)
    head=bytes([129,128|n]) if n<126 else bytes([129,254])+struct.pack('!H',n)
    s.sendall(head+mask+bytes(v^mask[i%4] for i,v in enumerate(payload)))
    while True:
        msg=recv()
        if msg.get('method')=='Runtime.exceptionThrown':errors.append(msg)
        if msg.get('id')==seq:
            assert 'error' not in msg,msg
            return msg.get('result',{})
def ev(expr):
    r=call('Runtime.evaluate',{'expression':expr,'returnByValue':True,'awaitPromise':True})
    assert 'exceptionDetails' not in r,r
    return r.get('result',{}).get('value')
def wait(expr):
    for _ in range(60):
        if ev(expr):return
        time.sleep(.1)
    raise AssertionError('Timed out: '+expr)
def nav(path):
    call('Page.navigate',{'url':base+path}); wait("document.readyState==='complete' && document.querySelector('section[aria-busy]')?.getAttribute('aria-busy')==='false'")

call('Runtime.enable'); call('Page.enable')
call('Page.addScriptToEvaluateOnNewDocument', {'source': """
(() => {
    const schedule = window.setTimeout, cancel = window.clearTimeout;
    window.pollTimers = new Map();
    window.setTimeout = (callback, delay, ...args) => {
        const id = schedule(callback, delay, ...args);
        if (delay === 60000) pollTimers.set(id, callback);
        return id;
    };
    window.clearTimeout = id => { pollTimers.delete(id); cancel(id); };
    window.advancePoll = async () => {
        const next = pollTimers.entries().next().value;
        if (!next) throw new Error('No 60-second poll scheduled');
        window.clearTimeout(next[0]);
        await next[1]();
    };
})();
"""})
nav('/')
wait('window.pollTimers.size===1')
assert ev("document.querySelectorAll('.story-card').length")==len(stories)
assert get(base+'/stories')[0]==200
with urllib.request.urlopen(base+'/stories') as response:
    assert response.headers['Cache-Control']=='no-store'
ev("""(async () => {
    window.fixture = await (await fetch('/stories')).json();
    window.nativeFetch = window.fetch;
    window.fetchCount = 0;
    window.fetch = async (url, options) => {
        fetchCount++;
        if (options.cache !== 'no-store') throw new Error('Missing no-store');
        if (window.failFetch) throw new TypeError('Simulated network failure');
        if (window.blockFetch) await new Promise(resolve => { window.releaseFetch = resolve; });
        return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(fixture)) };
    };
    window.originalCard = document.querySelector('.story-card');
    window.scrollTo(0, 300);
    document.querySelectorAll('.story-link')[1].focus({preventScroll:true});
    window.focusedURL = document.activeElement.href;
    window.beforeScroll = scrollY;
})()""")
ev('advancePoll()')
assert ev('fetchCount')==1
assert ev("document.querySelector('.story-card') === originalCard")
assert ev('scrollY===beforeScroll && document.activeElement.href===focusedURL')
assert ev('pollTimers.size')==1
print('PASS: scheduled 60-second refresh, no-store requests, unchanged nodes/scroll/focus')
ev("fixture.push({...fixture[0],cluster_id:99999,representative_title:'قصة اختبار جديدة',last_published_at:'2099-01-01T00:00:00Z'}); fixture.push({...fixture[0],cluster_id:99998,last_published_at:'invalid'})")
ev('advancePoll()')
assert ev("document.querySelector('.story-card').dataset.key")=='99999'
assert ev("document.querySelector('.story-card:last-child').dataset.key")=='99998'
assert ev("new Set([...document.querySelectorAll('.story-card')].map(x=>x.dataset.key)).size===document.querySelectorAll('.story-card').length")
assert ev('originalCard.isConnected && scrollY===beforeScroll && document.activeElement.href===focusedURL')
assert ev("getComputedStyle(document.querySelector('.story-card')).animationName")=='none'
print('PASS: new stories, newest-first/invalid-date sorting, no duplicate cards, no replayed entrance, preserved scroll/focus')
ev('window.failFetch=true; advancePoll()')
assert ev('originalCard.isConnected')
assert ev("document.querySelector('.refresh-status').hidden") is False
ev('window.failFetch=false; advancePoll()')
assert ev("document.querySelector('.refresh-status').hidden") is True
# Hold one fetch open and attempt another refresh; only one request may begin.
ev('window.blockFetch=true; window.pendingRefresh=refreshStories(); true')
count=ev('fetchCount')
ev('refreshStories()')
assert ev('fetchCount')==count
ev('window.blockFetch=false; releaseFetch(); pendingRefresh')
print('PASS: graceful background errors, recovery, no overlapping refreshes')
ev("Object.defineProperty(document,'hidden',{configurable:true,get:()=>window.testHidden}); window.testHidden=true; document.dispatchEvent(new Event('visibilitychange'))")
assert ev('pollTimers.size')==0
count=ev('fetchCount')
ev('refreshStories()')
assert ev('fetchCount')==count
ev("window.testHidden=false; document.dispatchEvent(new Event('visibilitychange'))")
wait('fetchCount>'+str(count))
wait('pollTimers.size===1')
ev("window.dispatchEvent(new PageTransitionEvent('pagehide')); ")
assert ev('pollTimers.size')==0
ev("window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}))")
wait('pollTimers.size===1')
print('PASS: hidden-tab pause, visible-tab resume, page lifecycle cleanup/resume')
ev("document.getElementById('theme-toggle').click(); window.selectedTheme=document.documentElement.dataset.theme")
selected=ev('selectedTheme')
nav('/')
assert ev('document.documentElement.dataset.theme')==selected
link=ev("document.querySelector('.story-link').getAttribute('href')")
nav(link)
wait('pollTimers.size===1')
assert ev('document.documentElement.dataset.theme')==selected
assert ev("[...document.querySelectorAll('.original-link')].every(x=>x.rel.includes('noopener') && /^https?:/.test(x.href))")
ev("""(async () => {
    window.fixture = await (await fetch(location.search.replace('?id=','/stories/'))).json();
    window.nativeFetch=window.fetch; window.fetchCount=0;
    window.fetch=async(url, options)=> {
        fetchCount++;
        if(options.cache!=='no-store') throw new Error('Missing no-store');
        if(url==='/stories') return nativeFetch(url,options);
        return {ok:true,status:200,json:async()=>JSON.parse(JSON.stringify(fixture))};
    };
    window.originalArticle=document.querySelector('.article-card');
})()""")
ev('advancePoll()')
assert ev("document.querySelector('.article-card')===originalArticle")
ev("fixture.articles.push({...fixture.articles[0],article_id:99999,headline:'مقال جديد للاختبار',political_alignment:'unclear',confidence:'low'})")
ev('advancePoll()')
assert ev("document.querySelector('.article-card:last-child').dataset.key")=='99999'
assert ev("document.querySelector('.article-card:last-child dd').textContent")=='غير واضح'
assert ev("getComputedStyle(document.querySelector('.article-card:last-child')).animationName")=='none'
assert ev('originalArticle.isConnected')
print('PASS: comparison polling, retained unchanged articles, new articles, uncertainty, original links, theme persistence')
for path in ['/',link]:
    for width,cols in [(1280,3),(900,2),(390,1),(320,1)]:
        call('Emulation.setDeviceMetricsOverride', {'width':width,'height':850,'deviceScaleFactor':1,'mobile':width<680})
        nav(path)
        assert ev('document.documentElement.scrollWidth <= innerWidth')
        assert ev("getComputedStyle(document.documentElement).direction")=='rtl'
        assert ev("getComputedStyle(document.querySelector('.stories,.articles')).gridTemplateColumns.split(' ').length")==cols
call('Emulation.setEmulatedMedia',{'features':[{'name':'prefers-reduced-motion','value':'reduce'}]})
assert ev("getComputedStyle(document.querySelector('.article-card')).animationName")=='none'
assert not errors,errors
print('PASS: RTL/mobile/desktop layout, reduced motion, no uncaught JavaScript exceptions')
s.close()
