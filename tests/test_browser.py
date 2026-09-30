"""Protocol checks for the P06 actual-browser evidence helper, no browser or GPU."""
import importlib.util
from pathlib import Path
import json,struct,unittest

path=Path(__file__).resolve().parents[1]/"scripts"/"browser_check.py"
spec=importlib.util.spec_from_file_location("p06_browser_check",path)
browser=importlib.util.module_from_spec(spec);spec.loader.exec_module(browser)

class FakeSocket:
    def __init__(self,chunks):self.data=bytearray(b"".join(chunks));self.sent=[]
    def recv(self,size):
        result=bytes(self.data[:min(size,3)]);del self.data[:len(result)];return result
    def sendall(self,payload):self.sent.append(payload)

def server_frame(payload,opcode=1,final=True):
    size=len(payload);first=(128 if final else 0)|opcode
    if size<126:return bytes((first,size))+payload
    if size<65536:return bytes((first,126))+struct.pack("!H",size)+payload
    return bytes((first,127))+struct.pack("!Q",size)+payload

class BrowserTransportTests(unittest.TestCase):
    def test_client_masks_utf8_and_extended_payloads(self):
        for payload in ("한국어 인용".encode(),b"x"*126,b"x"*70000):
            with self.subTest(size=len(payload)):
                packet=browser.frame(payload)
                self.assertEqual(packet[0],129)
                self.assertTrue(packet[1]&128)
                length=packet[1]&127;offset=2
                if length==126:length=struct.unpack("!H",packet[2:4])[0];offset=4
                elif length==127:length=struct.unpack("!Q",packet[2:10])[0];offset=10
                mask=packet[offset:offset+4]
                decoded=bytes(x^mask[i%4] for i,x in enumerate(packet[offset+4:]))
                self.assertEqual(length,len(payload));self.assertEqual(decoded,payload)
    def test_fragmented_json_and_ping_do_not_corrupt_receipt(self):
        body=json.dumps({"id":7,"result":{"text":"원문 인용"}}).encode()
        client=browser.CDP.__new__(browser.CDP)
        client.buffer=bytearray();client.sock=FakeSocket([
            server_frame(body[:10],final=False),server_frame(b"ping",opcode=9),
            server_frame(body[10:],opcode=0)])
        self.assertEqual(client.message(),json.loads(body));self.assertEqual(len(client.sock.sent),1)
    def test_closed_socket_and_oversized_frame_fail_explicitly(self):
        client=browser.CDP.__new__(browser.CDP);client.buffer=bytearray()
        client.sock=FakeSocket([])
        with self.assertRaisesRegex(RuntimeError,"connection closed"):client.read(1)
        client.sock=FakeSocket([bytes((129,127))+struct.pack("!Q",33*1024*1024)])
        with self.assertRaisesRegex(RuntimeError,"budget"):client.message()

    def test_policy_receipt_reports_no_model_or_validation(self):
        receipt={"generation_status":"policy_abstained","rule_gate":{"code":"live_state_not_in_catalog","reason":"현재 상태 미확인","owner_question":"운영 담당자에게 확인","model_called":False},"facts":[],"model_metrics":None,"citation_check":{"raw_span_checked":False,"semantic_entailment_verified":False}}
        gate=browser.validate_policy_receipt(receipt,"live_state_not_in_catalog")
        self.assertFalse(gate["model_called"])
    def test_policy_checker_rejects_model_or_fact_validation(self):
        import copy
        baseline={"generation_status":"policy_abstained","rule_gate":{"code":"live_state_not_in_catalog","reason":"이유","owner_question":"확인 질문","model_called":False},"facts":[],"model_metrics":None,"citation_check":{"raw_span_checked":False,"semantic_entailment_verified":False}}
        cases=[]
        value=copy.deepcopy(baseline);value["rule_gate"]["model_called"]=True;cases.append(value)
        value=copy.deepcopy(baseline);value["facts"]=[{"claim":"확정"}];cases.append(value)
        value=copy.deepcopy(baseline);value["citation_check"]["semantic_entailment_verified"]=True;cases.append(value)
        value=copy.deepcopy(baseline);value["citation_check"]["raw_span_checked"]=True;cases.append(value)
        value=copy.deepcopy(baseline);value["model_metrics"]={"eval_count":1};cases.append(value)
        for value in cases:
            with self.subTest(receipt=value),self.assertRaises(AssertionError):
                browser.validate_policy_receipt(value,"live_state_not_in_catalog")

if __name__=="__main__":unittest.main()
