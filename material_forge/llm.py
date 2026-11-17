"""OpenAI-compatible chat completions client.

Works with OpenAI, OpenRouter, LM Studio, Ollama (/v1), vLLM, llama.cpp server
and anything else exposing ``POST {base_url}/chat/completions``. Uses urllib so
the add-on has no third-party dependencies.
"""

import json
import urllib.error
import urllib.request

from . import node_lib

SYSTEM_PROMPT = """You are a Blender shader node graph generator.

You output ONE JSON object describing a procedural material. No prose, no
markdown fences.

Schema:
{
  "name": "short material name",
  "nodes": [
    {"id": "unique_snake_case", "type": "<one of the node types below>",
     "inputs": {"Socket Name": value},
     "params": {"property": value}}
  ],
  "links": ["source_node.OutputSocket -> target_node.InputSocket"],
  "bsdf": {"Base Color": 0.5}
}

Rules:
1. Only use the node types listed below. Never invent types.
2. The Principled BSDF already exists and is addressed as "bsdf". The Material
   Output exists as "output" and is already connected - do not reference it.
   Link shading into "bsdf" sockets instead, e.g. "ramp.Color -> bsdf.Base Color".
3. "bsdf" holds literal values only (numbers or [r,g,b,a] lists). Socket
   references belong in "links".
4. Colours are 4-component lists of 0..1 floats in linear-ish sRGB.
5. Scalar inputs take numbers. Vector inputs take 3-float lists.
6. Node ids must be unique and must not be "bsdf" or "output".
7. Use 3 to 10 nodes. Prefer Texture Coordinate -> noise/wave/voronoi ->
   ColorRamp -> Principled, with a Bump chain for relief. Chain Bump Normal
   into bsdf.Normal when the surface has texture.
8. Materials must be physically plausible: metals get Metallic 1 and low
   roughness, glass gets Transmission 1 and IOR 1.45, fabric gets high
   roughness and Sheen, and so on.
9. No image textures and no texture files - everything must be procedural.



Example output (a brushed metal):
{"name": "Brushed Aluminum", "nodes": [{"id": "coord", "type": "texcoord", "inputs": {}, "params": {}}, {"id": "noise", "type": "noise", "inputs": {}, "params": {"Scale": 12.0, "Detail": 6.0}}, {"id": "ramp", "type": "ramp", "inputs": {}, "params": {}}, {"id": "bump", "type": "bump", "inputs": {"Strength": 0.35}, "params": {}}], "links": ["coord.Object -> noise.Vector", "noise.Fac -> ramp.Fac", "noise.Fac -> bump.Height", "bump.Normal -> bsdf.Normal"], "bsdf": {"Base Color": [0.78, 0.78, 0.80, 1.0], "Metallic": 1.0, "Roughness": 0.25}}
Node types:
%s
""" % node_lib.prompt_reference()

# Extra guidance appended when a previous attempt failed to build.
FIX_PROMPT = """Your previous JSON failed with this error:
%s

Return a corrected JSON object. Keep it simpler if necessary."""


class LLMError(Exception):
    """Network, HTTP or JSON failure while talking to the model."""


def _endpoint(base_url):
    base = (base_url or "").strip().rstrip("/")
    if not base:
        raise LLMError("No API base URL configured (add-on preferences)")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def _post(url, payload, api_key, timeout):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    request.add_header("Content-Type", "application/json")
    if api_key:
        request.add_header("Authorization", f"Bearer {api_key}")

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:400]
        except Exception:  # noqa: BLE001 - best effort error text
            pass
        raise LLMError(f"HTTP {exc.code}: {detail or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise LLMError(f"Cannot reach {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise LLMError(f"Request timed out after {timeout}s") from exc
    except json.JSONDecodeError as exc:
        raise LLMError(f"Server returned non-JSON response: {exc}") from exc


def _extract_json(text):
    """Pull a JSON object out of a possibly-chatty response."""
    text = (text or "").strip()
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        raise LLMError("Model response contained no JSON object")
    snippet = text[start : end + 1]

    try:
        return json.loads(snippet)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Model returned invalid JSON: {exc}") from exc


def generate_spec(prompt, prefs, *, feedback=None):
    """Ask the model for a material spec and return it as a dict."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    if feedback:
        messages.append({"role": "assistant", "content": "(previous attempt omitted)"})
        messages.append({"role": "user", "content": FIX_PROMPT % feedback})

    payload = {
        "model": prefs.model,
        "messages": messages,
        "temperature": float(prefs.temperature),
        "stream": False,
    }
    if getattr(prefs, "json_mode", True):
        payload["response_format"] = {"type": "json_object"}

    url = _endpoint(prefs.base_url)

    try:
        response = _post(url, payload, prefs.api_key, int(prefs.timeout))
    except LLMError:
        # Many local servers reject response_format; retry once without it.
        if "response_format" in payload:
            payload.pop("response_format")
            response = _post(url, payload, prefs.api_key, int(prefs.timeout))
        else:
            raise

    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"Unexpected response shape: {str(response)[:300]}") from exc

    if isinstance(content, list):
        # Some providers return content parts instead of a string.
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))

    return _extract_json(content)
