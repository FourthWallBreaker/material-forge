import json, threading, http.server, time, sys, types
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

src = (ROOT / "tests" / "smoke_test.py").read_text(encoding="utf-8")
marker = "from material_forge import"
i = src.index(marker)
exec(src[:i], {"__name__": "__stub__", "__file__": str(ROOT / "tests" / "smoke_test.py")})

import material_forge
from material_forge import llm, builder, compat
from material_forge.compat import BuildError

VALID_SPEC = {
    "name": "Forged Brushed Aluminum (LLM)",
    "nodes": [
        {"id": "coord", "type": "texcoord", "inputs": {}, "params": {}},
        {"id": "noise", "type": "noise", "inputs": {}, "params": {"Scale": 12.0, "Detail": 6.0}},
        {"id": "ramp", "type": "ramp", "inputs": {}, "params": {}},
        {"id": "bump", "type": "bump", "inputs": {"Strength": 0.4}, "params": {}},
    ],
    "links": [
        "coord.Object -> noise.Vector",
        "noise.Fac -> ramp.Fac",
        "noise.Fac -> bump.Height",
        "bump.Normal -> bsdf.Normal",
    ],
    "bsdf": {"Base Color": [0.78, 0.78, 0.8, 1.0], "Metallic": 1.0, "Roughness": 0.25},
}

BAD_SPEC = {
    "name": "bad",
    "nodes": [{"id": "x", "type": "not_a_real_node", "inputs": {}, "params": {}}],
    "links": [],
    "bsdf": {"Base Color": 0.5},
}

class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        if length:
            self.rfile.read(length)
        self.server.counter += 1
        content = json.dumps(BAD_SPEC if self.server.counter == 1 else VALID_SPEC)
        resp = {"choices": [{"message": {"content": content}}]}
        data = json.dumps(resp).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def log_message(self, *a):
        pass

httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
httpd.counter = 0
threading.Thread(target=httpd.serve_forever, daemon=True).start()
port = httpd.server_address[1]
time.sleep(0.2)

prefs = types.SimpleNamespace(
    base_url=f"http://127.0.0.1:{port}/v1",
    api_key="",
    model="mock-model",
    temperature=0.2,
    timeout=10,
    json_mode=True,
)

# 1. first attempt (bad) -> build fails -> repair loop -> valid
spec = llm.generate_spec("brushed aluminum", prefs)
print("first spec node types:", [n["type"] for n in spec["nodes"]])
try:
    builder.validate(spec)
    print("first build validated (unexpected)")
except BuildError as e:
    print("first build failed as expected:", e)
    spec2 = llm.generate_spec("brushed aluminum", prefs, feedback=str(e))
    print("repaired spec node types:", [n["type"] for n in spec2["nodes"]])
    v = builder.validate(spec2)
    print("repaired spec validates OK ->", v[0].get("name"), "| nodes:", len(v[1]), "| links:", len(v[2]))

# 2. direct happy path
httpd.counter = 100
spec3 = llm.generate_spec("brushed aluminum", prefs)
v3 = builder.validate(spec3)
print("direct path validates OK ->", v3[0].get("name"), "| nodes:", len(v3[1]))

httpd.shutdown()
print("OK: LLM client + repair loop + builder validation all functional against a mock OpenAI endpoint")
