#!/usr/bin/env python3
"""CPU-only P06 browser checks using native Chrome CDP and Python stdlib.

Creates and closes its own page target. Real model-arm POSTs are allowed only when health confirms model_enabled=false.
Fault/citation renderer examples are explicit browser mocks, never model runs.
"""
from __future__ import annotations
import argparse,base64,hashlib,json,os,socket,struct,time,urllib.request
from pathlib import Path

def frame(payload: bytes, opcode=1):
    mask=os.urandom(4); size=len(payload)
    head=bytes((0x80|opcode,0x80|size)) if size<126 else (
        bytes((0x80|opcode,0x80|126))+struct.pack("!H",size) if size<65536 else
        bytes((0x80|opcode,0x80|127))+struct.pack("!Q",size))
    return head+mask+bytes(value^mask[index%4] for index,value in enumerate(payload))

class CDP:
    def __init__(self,url):
        from urllib.parse import urlsplit
        parsed=urlsplit(url);self.sock=socket.create_connection((parsed.hostname,parsed.port),20)
        self.sock.settimeout(30);self.buffer=bytearray();self.counter=0
        key=base64.b64encode(os.urandom(16)).decode()
        request=("GET "+parsed.path+" HTTP/1.1\r\nHost: "+parsed.netloc+
                 "\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: "+key+
                 "\r\nSec-WebSocket-Version: 13\r\n\r\n").encode()
        self.sock.sendall(request);response=b""
        while b"\r\n\r\n" not in response:response+=self.sock.recv(4096)
        header,extra=response.split(b"\r\n\r\n",1)
        expected=base64.b64encode(hashlib.sha1((key+"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
        if not header.startswith(b"HTTP/1.1 101") or expected not in header:raise RuntimeError("CDP handshake failed")
        self.buffer.extend(extra)
    def read(self,size):
        while len(self.buffer)<size:
            chunk=self.sock.recv(max(4096,size-len(self.buffer)))
            if not chunk:raise RuntimeError("CDP connection closed")
            self.buffer.extend(chunk)
        result=bytes(self.buffer[:size]);del self.buffer[:size];return result
    def message(self):
        accumulated=bytearray()
        while True:
            first,second=self.read(2);final=bool(first&128);opcode=first&15;size=second&127
            if size==126:size=struct.unpack("!H",self.read(2))[0]
            elif size==127:size=struct.unpack("!Q",self.read(8))[0]
            if size>32*1024*1024:raise RuntimeError("CDP frame budget exceeded")
            mask=self.read(4) if second&128 else None
            payload=self.read(size)
            if mask:payload=bytes(value^mask[index%4] for index,value in enumerate(payload))
            if opcode==8:raise RuntimeError("CDP closed")
            if opcode==9:self.sock.sendall(frame(payload,10));continue
            if opcode==10:continue
            accumulated.extend(payload)
            if final:return json.loads(accumulated)
    def call(self,method,params=None):
        self.counter+=1;identity=self.counter
        self.sock.sendall(frame(json.dumps({"id":identity,"method":method,"params":params or {}}).encode()))
        while True:
            result=self.message()
            if result.get("id")==identity:
                if "error" in result:raise RuntimeError("CDP error: "+json.dumps(result["error"]))
                return result.get("result",{})
    def js(self,expression):
        result=self.call("Runtime.evaluate",{"expression":expression,"awaitPromise":True,"returnByValue":True})
        if "exceptionDetails" in result:raise RuntimeError("Browser JS exception: "+json.dumps(result["exceptionDetails"]))
        return result.get("result",{}).get("value")
    def wait(self,expression,timeout=20):
        start=time.monotonic()
        while time.monotonic()-start<timeout:
            if self.js(expression):return
            time.sleep(.08)
        raise AssertionError("Browser wait timed out: "+expression)
    def shot(self,path):
        result=self.call("Page.captureScreenshot",{"format":"png","captureBeyondViewport":False})
        path.write_bytes(base64.b64decode(result["data"]))
    def close(self):self.sock.close()

def check(value,message):
    if not value:raise AssertionError(message)

def validate_policy_receipt(receipt,expected_code):
    check(receipt.get("generation_status")=="policy_abstained","actual policy status")
    gate=receipt.get("rule_gate") or {}
    check(gate.get("code")==expected_code,"actual policy reason code")
    check(gate.get("model_called") is False,"policy must explicitly report no model call")
    check(bool(gate.get("reason")) and bool(gate.get("owner_question")),"reason and owner question")
    check(receipt.get("facts")==[],"policy must have no model facts")
    check(receipt.get("model_metrics") is None,"policy must have no model metrics")
    check(receipt.get("citation_check",{}).get("raw_span_checked") is False,"policy cannot claim citation validation")
    check(receipt.get("citation_check",{}).get("semantic_entailment_verified") is False,"policy cannot claim semantic validation")
    return gate

def policy_checks(page,out):
    cases=[
        ("live-state","E8363B 장비의 현재 예약과 교정 상태, 방문 권한을 확인해 주세요.","live_state_not_in_catalog"),
        ("physical-identity","E8363B의 자료 기록 두 행은 동일한 물리 장비인가요?","physical_identity_not_in_preview")]
    checks=[];receipts=[]
    for label,question,code in cases:
        for method in ("rag","all"):
            health=page.js("(async()=>await (await fetch('/api/health')).json())()")
            check(health.get("model_enabled") is False,"policy browser CPU-only health guard")
            page.js("document.getElementById('question').value="+json.dumps(question)+";document.querySelector('input[name=method][value="+method+"]').click();document.getElementById('query-form').requestSubmit()")
            page.wait("!document.getElementById('query-submit').disabled")
            receipt=page.js("(async()=>await (await fetch('/api/receipts/'+document.getElementById('receipt-id').value)).json())()")["receipt"]
            gate=validate_policy_receipt(receipt,code)
            body=page.js("document.querySelector('[data-method="+method+"]').textContent")
            check("공개 목록으로 확인 불가 · 모델 미호출" in body,"explicit Korean policy status")
            check(gate["reason"] in body and gate["owner_question"] in body,"visible reason and owner question")
            check("후보일 뿐" in body and "입증하지 않습니다" in body,"candidates not proof")
            check(not page.js("!!document.querySelector('[data-method="+method+"] .citation-button')"),"no fabricated citations")
            check("검색 후보" in page.js("document.getElementById('result-summary').textContent"),"candidate table distinction")
            receipts.append({"case":label,"method":method,"receipt_id":receipt["receipt_id"],"generation_status":receipt["generation_status"],"rule_gate":gate,"candidate_count":len(receipt["selected_document_ids"])})
            checks.append({"name":label+" "+method+" actual policy receipt and UI","status":"passed"})
        page.js("document.getElementById('receipts-panel').scrollIntoView({block:'start',behavior:'auto'})")
        page.shot(out/("policy-"+label+"-desktop.png"))
    page.call("Emulation.setDeviceMetricsOverride",{"width":390,"height":844,"deviceScaleFactor":1,"mobile":True})
    page.js("document.querySelector('[data-panel=receipts]').click();document.querySelector('[data-method=rag]').scrollIntoView({block:'start',behavior:'auto'})")
    check(page.js("document.documentElement.scrollWidth<=390"),"policy badge mobile reflow")
    page.shot(out/"policy-physical-identity-mobile.png")
    checks.append({"name":"390px policy badge and reason reflow","status":"passed"})
    return {"checks":checks,"passed":len(checks),"actual_receipts":receipts,"new_model_requests":0,"real_requests":"CPU-disabled health GET, rag/all policy query POST, stored receipt GET","mocks":[],"screenshots":[p.name for p in sorted(out.glob("policy-*.png"))],"limitations":["Public catalog policy abstention, no model inference or semantic evaluation"]}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=19090)
    parser.add_argument("--cdp-port",type=int,default=19086)
    parser.add_argument("--output",default="docs/ui/captures")
    parser.add_argument("--policy-only",action="store_true",help="Actual CPU policy follow-up, no baseline captures overwritten")
    args=parser.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    root="http://127.0.0.1:"+str(args.cdp_port)
    request=urllib.request.Request(root+"/json/new?about:blank",method="PUT")
    with urllib.request.urlopen(request,timeout=10) as response:target=json.load(response)
    page=CDP(target["webSocketDebuggerUrl"]);results=[]
    def passed(name):results.append({"name":name,"status":"passed"})
    def js(expression):return page.js(expression)
    try:
        page.call("Page.enable");page.call("Runtime.enable")
        page.call("Emulation.setDeviceMetricsOverride",{"width":1440,"height":1080,"deviceScaleFactor":1,"mobile":False})
        page.call("Page.navigate",{"url":"http://127.0.0.1:"+str(args.port)})
        page.wait("document.getElementById('equipment-rows')?.children.length===8 && !document.getElementById('query-submit').disabled")
        if args.policy_only:
            report=policy_checks(page,out)
            (out/"policy-check.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
            print(json.dumps({"policy_checks_passed":report["passed"],"new_model_requests":0,"screenshots":len(report["screenshots"])}))
            return
        check(js("document.documentElement.lang==='ko'"),"Korean document language")
        check(js("document.getElementById('catalog-date').textContent==='2026-04-17'"),"catalog date")
        check(js("getComputedStyle(document.body).backgroundColor==='rgb(241, 244, 246)' && getComputedStyle(document.querySelector('.primary')).backgroundColor==='rgb(23, 63, 96)'"),"approved P09 v2 page and primary colors")
        check(js("(()=>{const heading=document.querySelector('h1');const style=getComputedStyle(heading);return heading.textContent==='한국어 장비 근거 데스크' && style.whiteSpace==='nowrap' && document.querySelector('.desk').getBoundingClientRect().width<=1120})()"),"single-line Korean title and bounded desk")
        check(js("document.getElementById('evidence-dialog').getAttribute('aria-labelledby')==='evidence-title'"),"named dialog")
        check(js("!document.body.innerText.includes('예약 가능')"),"no booking claim")
        passed("initial admitted 8 rows, source date, named native dialog")
        page.shot(out/"01-source-desktop.png")
        js("document.getElementById('question').value='E8363B 모델명과 주파수 원문';document.getElementById('query-form').requestSubmit()")
        page.wait("document.querySelector('[data-method=source] .badge').textContent==='원문 조회 완료' && !document.getElementById('query-submit').disabled")
        receipt=js("document.getElementById('receipt-id').value")
        check(len(receipt)==24,"actual stored receipt")
        check(js("document.querySelector('[data-method=rag] .badge').textContent==='미실행' && document.querySelector('[data-method=all] .badge').textContent==='미실행'"),"independent method states")
        check(js("document.querySelector('[data-method=all]').textContent.includes('캐시 재사용 검증 안 됨')"),"no unverified KV reuse claim")
        passed("actual source receipt and independent unexecuted model arms")
        page.shot(out/"02-query-source.png")
        js("document.querySelector('.raw-button').click()")
        page.wait("document.getElementById('evidence-dialog').open")
        check(js("document.getElementById('evidence-meta').textContent.includes('SHA256')"),"source hashes")
        check(js("document.querySelector('.raw-field pre').textContent.length>0"),"raw fields")
        check(js("document.activeElement.id==='evidence-close'"),"dialog focus")
        page.shot(out/"03-original-drawer.png")
        page.call("Input.dispatchKeyEvent",{"type":"keyDown","key":"Escape","code":"Escape","windowsVirtualKeyCode":27})
        page.call("Input.dispatchKeyEvent",{"type":"keyUp","key":"Escape","code":"Escape","windowsVirtualKeyCode":27})
        page.wait("!document.getElementById('evidence-dialog').open")
        check(js("document.activeElement.classList.contains('raw-button')"),"Escape returns row focus")
        passed("raw drawer provenance and keyboard Escape focus return")
        js("document.getElementById('restore-receipt').click()")
        page.wait("!document.getElementById('query-submit').disabled")
        check(js("document.getElementById('receipt-id').value")==receipt,"stored receipt GET")
        passed("stored actual source receipt reload")
        js("(async()=>{window.__actualSource=await (await fetch(\'/api/receipts/\'+document.getElementById(\'receipt-id\').value)).json();return true})()")
        js("window.__realFetch=window.fetch;window.__postCount=0;window.fetch=(url,options)=>{if(url==='/api/query'){window.__postCount++;return new Promise(resolve=>setTimeout(()=>window.__realFetch(url,options).then(resolve),350));}return window.__realFetch(url,options)};document.getElementById('question').value='4294A 원문';document.getElementById('query-form').requestSubmit();document.getElementById('query-form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}))")
        page.wait("!document.getElementById('query-submit').disabled && window.__postCount===1")
        js("window.fetch=window.__realFetch")
        passed("one real source POST despite duplicate submit (delayed transport mock)")
        js("document.getElementById('corpus').value='preview50';document.getElementById('corpus').dispatchEvent(new Event('change'))")
        page.wait("document.getElementById('equipment-rows').children.length===50 && !document.getElementById('query-submit').disabled")
        check(js("document.querySelector('input[name=method][value=rag]').disabled && document.querySelector('input[name=method][value=all]').disabled"),"preview50 retrieval only")
        passed("50-row separate retrieval-only corpus")
        page.shot(out/"04-preview50-source.png")
        js("document.querySelector('input[name=scope][value=external]').click()")
        page.wait("!document.getElementById('query-submit').disabled")
        check(js("Array.from(document.querySelectorAll('.row-scope')).every(x=>x.textContent.includes('外部')||x.textContent.includes('외부'))"),"external raw filter")
        passed("external scope raw-label filter")
        js("document.querySelector('input[name=scope][value=all]').click()")
        page.wait("!document.getElementById('query-submit').disabled")
        js("document.getElementById('corpus').value='small8';document.getElementById('corpus').dispatchEvent(new Event('change'))")
        page.wait("document.getElementById('equipment-rows').children.length===8 && !document.getElementById('query-submit').disabled")
        # Explicit fault mock: no model requests and no invented saved model result.
        js("window.__realFetch=window.fetch;window.fetch=(url,options)=>url.startsWith('/api/receipts/')?Promise.resolve(new Response(JSON.stringify({code:'unknown_receipt'}),{status:400,headers:{'Content-Type':'application/json'}})):window.__realFetch(url,options);document.getElementById('receipt-id').value='0123456789abcdef01234567';document.getElementById('restore-receipt').click()")
        page.wait("!document.getElementById('query-submit').disabled")
        check(js("document.getElementById('notice').textContent.includes('서버 재시작') && document.getElementById('notice').textContent.includes('다시 실행하지')"),"restart missing receipt")
        js("window.fetch=window.__realFetch")
        passed("missing stored receipt after restart, explicitly mocked GET failure")
        # Explicit model-response mocks test renderer only; never call a model endpoint.
        js("""window.__realFetch=window.fetch;window.__mockPacket=structuredClone(window.__actualSource);let r=window.__mockPacket.receipt;let record=r.selected_records[0];let field='구성 및 성능';let quote=Array.from(record.fields[field]).slice(0,20).join('');r.method='rag';r.question='브라우저 모의 검증 · 실제 모델 요청 없음';r.generation_status='model_validated_citations_only';r.answer_state='SOURCE_NOTATION_DIFFERENCE';r.citation_check.raw_span_checked=true;r.facts=[{document_id:record.document_id,field,quote,claim:'<img src=x onerror=window.__unsafeExecuted=true>',quantity_label:'frequency_range',value:null,unit:null,context:'조건 확인 필요',span:[0,20],citation_validated:true,record_hash:r.source.record_hashes[record.document_id],source_hash:r.source.catalog_sha256}];r.unknowns=['<script>window.__unsafeExecuted=true</script>'];window.fetch=(url,options)=>url==='/api/query'?Promise.resolve(new Response(JSON.stringify(window.__mockPacket),{status:200,headers:{'Content-Type':'application/json'}})):window.__realFetch(url,options);document.querySelector('input[name=method][value=rag]').click();document.getElementById('question').value=r.question;document.getElementById('query-form').requestSubmit()""")
        page.wait("!document.getElementById('query-submit').disabled")
        check(js("document.querySelector('[data-method=rag]').textContent.includes('원문 표기 차이') && !window.__unsafeExecuted && !document.querySelector('[data-method=rag] img')"),"safe untrusted model text")
        js("document.querySelector('[data-method=rag] .citation-button').click()")
        page.wait("document.getElementById('evidence-dialog').open")
        check(js("document.querySelector('#active-quote mark').textContent===window.__mockPacket.receipt.facts[0].quote"),"exact quote highlight")
        tree=page.call("Accessibility.getFullAXTree")["nodes"]
        check(any(x.get("role",{}).get("value")=="dialog" and x.get("name",{}).get("value") for x in tree),"accessible dialog name")
        page.call("Emulation.setEmulatedMedia",{"features":[{"name":"prefers-reduced-motion","value":"reduce"}]})
        js("document.getElementById('return-to-claim').click()")
        check(js("document.activeElement.classList.contains('citation-button')"),"citation focus return")
        passed("explicit model mock: safe text, source notation state, named dialog, quote highlight and reduced-motion focus return")
        js("window.__mockPacket.receipt.facts[0].record_hash='0'.repeat(64);document.getElementById('query-form').requestSubmit()")
        page.wait("!document.getElementById('query-submit').disabled")
        js("document.querySelector('[data-method=rag] .citation-button').click()")
        check(js("document.getElementById('evidence-dialog').open && !document.getElementById('evidence-notice').hidden && document.getElementById('evidence-notice').getAttribute('role')==='alert' && !document.querySelector('#evidence-fields mark')"),"open-modal error visibility")
        js("document.getElementById('evidence-close').click()")
        passed("explicit citation-hash fault mock: visible accessible error inside open modal")
        js("window.__mockPacket.receipt.facts=[];window.__mockPacket.receipt.generation_status='model_unavailable';window.__mockPacket.receipt.answer_state='NOT_GENERATED';window.__mockPacket.receipt.error='model_not_enabled_until_token_preflight';document.getElementById('query-form').requestSubmit()")
        page.wait("!document.getElementById('query-submit').disabled")
        check(js("document.querySelector('[data-method=rag] .badge').textContent==='모델 사용 불가' && document.querySelector('[data-method=rag]').textContent.includes('모델 답변은 없습니다')"),"degraded state")
        js("window.__mockPacket.receipt.method='source';window.__mockPacket.receipt.question='브라우저 모의 빈 결과';window.__mockPacket.receipt.generation_status='source_lookup_only';window.__mockPacket.receipt.selected_records=[];window.__mockPacket.receipt.selected_document_ids=[];window.__mockPacket.receipt.unknowns=[];window.__mockPacket.receipt.owner_questions=[];window.__mockPacket.receipt.error=null;document.querySelector('input[name=method][value=source]').click();document.getElementById('query-form').requestSubmit()")
        page.wait("!document.getElementById('query-submit').disabled")
        check(js("!document.getElementById('equipment-empty').hidden && document.getElementById('equipment-empty').textContent.includes('선택된 원문이 없습니다') && document.getElementById('equipment-rows').children.length===0"),"explicit empty source result")
        passed("explicit empty-source receipt mock, no fabricated equipment")
        js("window.fetch=window.__realFetch;document.getElementById('receipt-id').value=window.__actualSource.receipt.receipt_id;document.getElementById('restore-receipt').click()")
        page.wait("!document.getElementById('query-submit').disabled")
        passed("explicit unavailable-model mock, then actual source receipt restored")
        contrast=js("""(()=>{const parse=x=>{const a=x.match(/[\\d.]+/g).map(Number);return [a[0],a[1],a[2],a[3]??1]};const blend=(a,b)=>[0,1,2].map(i=>a[i]*a[3]+b[i]*(1-a[3])).concat(1);const bg=n=>n?blend(parse(getComputedStyle(n).backgroundColor),bg(n.parentElement)):[255,255,255,1];const lum=c=>c.slice(0,3).map(x=>x/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);let values=[];for(const n of document.body.querySelectorAll('*')){if(!n.getClientRects().length||n.closest('button:disabled,input:disabled,textarea:disabled,select:disabled')||!Array.from(n.childNodes).some(t=>t.nodeType===3&&t.textContent.trim()))continue;const s=getComputedStyle(n);if(s.visibility==='hidden')continue;const back=bg(n),fore=blend(parse(s.color),back);const a=lum(back),b=lum(fore);values.push({ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05),tag:n.tagName,cls:n.className});}return values.sort((a,b)=>a.ratio-b.ratio)[0]})()""")
        check(contrast["ratio"]>=4.5,"computed actual text contrast target")
        passed("computed rendered text contrast >=4.5; disabled controls excluded")
        disabled_arm_count=0
        health=js("(async()=>await (await fetch('/api/health')).json())()")
        if health.get("model_enabled") is False:
            for method in ("rag","all"):
                check(js("(async()=>(await (await fetch('/api/health')).json()).model_enabled===false)()"),"CPU model-disabled guard")
                js("document.querySelector('input[name=method][value="+method+"]').click();document.getElementById('query-form').requestSubmit()")
                page.wait("!document.getElementById('query-submit').disabled")
                check(js("document.querySelector('[data-method="+method+"] .badge').textContent==='모델 사용 불가'"),"actual unavailable receipt")
                disabled_arm_count+=1
            passed("actual RAG and All-context unavailable receipts; model-disabled health guarded")
            js("document.getElementById('receipts-panel').scrollIntoView({block:'start',behavior:'auto'})")
            page.shot(out/"07-model-disabled-comparison.png")
        page.call("Emulation.setDeviceMetricsOverride",{"width":390,"height":844,"deviceScaleFactor":1,"mobile":True})
        js("window.scrollTo(0,0)")
        check(js("document.documentElement.scrollWidth<=390"),"mobile page overflow")
        check(js("(()=>{const title=document.querySelector('h1');return title.getBoundingClientRect().right<=390 && getComputedStyle(title).whiteSpace==='nowrap'})()"),"390px title remains one line without clipping")
        check(js("getComputedStyle(document.getElementById('question')).fontSize==='16px'"),"16px controls")
        passed("390px reflow and readable question controls")
        page.shot(out/"05-mobile-query.png")
        js("document.querySelector('[data-panel=receipts]').click();document.getElementById('receipts-panel').scrollIntoView({block:'start',behavior:'auto'})")
        check(js("!document.getElementById('receipts-panel').classList.contains('mobile-inactive') && document.getElementById('equipment-panel').classList.contains('mobile-inactive')"),"mobile task tabs")
        page.shot(out/"06-mobile-receipts.png")
        passed("mobile task tabs")
        page.call("Emulation.setDeviceMetricsOverride",{"width":720,"height":540,"deviceScaleFactor":1,"mobile":False})
        check(js("document.documentElement.scrollWidth<=720"),"200-percent equivalent reflow")
        passed("720px viewport reflow equivalent to 200-percent desktop zoom")
        report={"checks":results,"passed":len(results),"new_model_requests":0,
                "real_requests":"catalog GET, source query POST, stored source receipt GET; optional rag/all POST only with model_enabled=false",
                "actual_model_disabled_receipts":disabled_arm_count,
                "mocks":["350ms source transport delay","unknown_receipt 400 on GET","validated citation renderer only","citation hash mismatch","model unavailable renderer only","empty source receipt"],
                "minimum_computed_text_contrast":contrast,
                "screenshots":[x.name for x in sorted(out.glob("*.png"))],
                "limitations":["No actual model invocation or successful-model capture",
                    "720px reflow is a viewport equivalent, not native browser zoom",
                    "Automated checks do not replace complete accessibility review"]}
        (out/"browser-check.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps({"passed":len(results),"new_model_requests":0,"screenshots":len(report["screenshots"])}))
    finally:
        page.close()
        try:urllib.request.urlopen(root+"/json/close/"+target["id"],timeout=10).close()
        except Exception:pass
if __name__=="__main__":main()
