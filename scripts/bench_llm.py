import json
import time
import urllib.request


def gen(model, prompt, n=32):
    body = json.dumps({"model": model, "prompt": prompt, "stream": False,
                       "options": {"num_predict": n}}).encode()
    req = urllib.request.Request("http://localhost:11434/api/generate",
                                 data=body, headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read().decode())
    dt = time.perf_counter() - t0
    return dt, d


def fmt(label, dt, d):
    pe = d.get("prompt_eval_duration", 0) / 1e9
    ev = d.get("eval_duration", 0) / 1e9
    print(f"{label}: wall {dt:.2f}s prompt_eval {d.get('prompt_eval_count')} tok {pe:.2f}s "
          f"eval {d.get('eval_count')} tok {ev:.2f}s")


dt, d = gen("llama3.2", "The capital of France is")
fmt("llama3.2 plain", dt, d)

tool_prompt = ('{"tools": [{"function": {"name": "open_path", "description": "Open a folder", '
               '"parameters": {"properties": {"path": {"type": "string"}}}}}], '
               '"user": "open the project folder"}')
dt, d = gen("llama3.2", tool_prompt, n=64)
fmt("llama3.2 tool-probe", dt, d)
print("  reply:", d.get("response", "")[:120])
