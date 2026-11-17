"""Operators: prompt -> material."""

import random
import threading
import time as _time

import bpy

from . import builder, compat, llm, presets
from .compat import BuildError
from .ui import get_prefs

LLM_MIN_SCORE = 2
LLM_RETRIES = 3


def _from_llm(prompt, prefs):
    """Ask the model, build, and repair up to LLM_RETRIES times."""
    last_error = None
    for attempt in range(1, LLM_RETRIES + 1):
        spec = llm.generate_spec(prompt, prefs, feedback=str(last_error) if last_error else None)
        try:
            builder.validate(spec)
            mat = builder.build(spec)
            label = "LLM" if attempt == 1 else "LLM (repaired x%d)" % (attempt - 1)
            return mat, spec, label
        except BuildError as exc:
            last_error = exc
            if attempt < LLM_RETRIES:
                _time.sleep(2 ** (attempt - 1))
    raise last_error


_BUSY = False
_PENDING = {"result": None, "error": None, "done": False}
_LOCK = threading.Lock()


def _worker(context, prompt, engine, preset_key):
    global _BUSY
    try:
        mat, source = generate(context, prompt, engine, preset_key)
        with _LOCK:
            _PENDING["result"] = (mat, source)
    except Exception as exc:  # noqa: BLE001 - surface any failure to UI
        with _LOCK:
            _PENDING["error"] = exc
    finally:
        with _LOCK:
            _PENDING["done"] = True
            _BUSY = False


def _poll():
    with _LOCK:
        done = _PENDING["done"]
    if not done:
        return 0.2
    with _LOCK:
        result = _PENDING["result"]
        error = _PENDING["error"]
        _PENDING["result"] = None
        _PENDING["error"] = None
        _PENDING["done"] = False

    # Apply on the main thread (bpy is not thread-safe).
    try:
        if error is not None:
            try:
                bpy.context.scene.mf_status = "Failed: %s" % error
            except Exception:  # noqa: BLE001
                pass
            print("Material Forge async error:", error)
            return None
        mat, source = result
        # Update the active scene if still available
        for window in bpy.context.window_manager.windows:
            scene = window.screen.areas and None
        # Find a scene to update status on
        try:
            scn = bpy.context.scene
            scn.mf_status = "%s  ::  %s" % (mat.name, source)
            obj = bpy.context.object
            if obj is not None:
                compat.assign_to_object(obj, mat)
        except Exception as exc:  # noqa: BLE001
            print("Material Forge apply failed:", exc)
    except Exception as exc:  # noqa: BLE001
        print("Material Forge poll failed:", exc)
    return None


def generate_async(context, prompt, engine, preset_key=None):
    global _BUSY
    with _LOCK:
        if _BUSY:
            return False
        _BUSY = True
        _PENDING["result"] = None
        _PENDING["error"] = None
        _PENDING["done"] = False
    t = threading.Thread(target=_worker, args=(context, prompt, engine, preset_key), daemon=True)
    t.start()
    if not bpy.app.timers.is_registered(_poll):
        bpy.app.timers.register(_poll, persistent=True)
    return True
    """Return ``(material, source_label)`` for the given request."""
    scene = context.scene
    prefs = get_prefs(context)
    if prefs is None:
        raise BuildError("Add-on preferences are unavailable; re-enable Material Forge")

    if engine == "PRESET":
        spec = presets.preset_spec(preset_key)
        if spec is None:
            raise BuildError(f"Unknown preset {preset_key!r}")
        return builder.build(spec), f"preset {preset_key}"

    if engine == "LLM":
        if not prefs.api_key:
            raise BuildError("No API key set in the add-on preferences")
        mat, spec, label = _from_llm(prompt, prefs)
        return mat, label

    # AUTO: vocabulary first, model as fallback for unfamiliar requests.
    preset, score = presets.best_match(prompt)
    if preset is not None and score >= LLM_MIN_SCORE:
        mat = builder.build(presets.preset_spec(preset["key"]))
        return mat, f"preset {preset['key']} (score {score})"

    if prefs.api_key and prompt:
        mat, spec, label = _from_llm(prompt, prefs)
        return mat, label

    if preset is not None:
        mat = builder.build(presets.preset_spec(preset["key"]))
        return mat, f"preset {preset['key']} (weak match)"

    # Last resort so the button always does something useful.
    return builder.build(presets.preset_spec("STONE")), "fallback stone"


def generate(context, prompt, engine, preset_key=None):
    """Return ``(material, source_label)`` for the given request."""
    scene = context.scene
    prefs = get_prefs(context)
    if prefs is None:
        raise BuildError("Add-on preferences are unavailable; re-enable Material Forge")

    if engine == "PRESET":
        spec = presets.preset_spec(preset_key)
        if spec is None:
            raise BuildError("Unknown preset %r" % preset_key)
        return builder.build(spec), "preset %s" % preset_key

    if engine == "LLM":
        if not prefs.api_key:
            raise BuildError("No API key set in the add-on preferences")
        mat, spec, label = _from_llm(prompt, prefs)
        return mat, label

    preset, score = presets.best_match(prompt)
    if preset is not None and score >= LLM_MIN_SCORE:
        mat = builder.build(presets.preset_spec(preset["key"]))
        return mat, "preset %s (score %d)" % (preset["key"], score)

    if prefs.api_key and prompt:
        mat, spec, label = _from_llm(prompt, prefs)
        return mat, label

    if preset is not None:
        mat = builder.build(presets.preset_spec(preset["key"]))
        return mat, "preset %s (weak match)" % preset["key"]

    return builder.build(presets.preset_spec("STONE")), "fallback stone"

class MATERIALFORGE_OT_generate(bpy.types.Operator):
    """Generate a procedural material from the prompt"""

    bl_idname = "material_forge.generate"
    bl_label = "Forge Material"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        prompt = (scene.mf_prompt or "").strip()

        if scene.mf_engine != "PRESET" and not prompt:
            self.report({"WARNING"}, "Type what material you want first")
            return {"CANCELLED"}

        try:
            if not generate_async(context, prompt, scene.mf_engine, scene.mf_preset):
                self.report({"WARNING"}, "Material Forge is already generating")
                return {"CANCELLED"}
            scene.mf_status = "Generating..."
            self.report({"INFO"}, "Material Forge: generating...")
        except Exception as exc:  # noqa: BLE001
            scene.mf_status = "Failed: %s" % exc
            self.report({"ERROR"}, "Material Forge: %s" % exc)
            return {"CANCELLED"}

        return {"FINISHED"}


class MATERIALFORGE_OT_surprise(bpy.types.Operator):
    """Build a random preset material"""

    bl_idname = "material_forge.surprise"
    bl_label = "Surprise Me"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        key = random.choice([p["key"] for p in presets.PRESETS])
        mat = builder.build(presets.preset_spec(key))
        obj = context.object
        if obj is not None:
            compat.assign_to_object(obj, mat)
        context.scene.mf_status = f"{mat.name}  ::  preset {key}"
        self.report({"INFO"}, f"Built {mat.name}")
        return {"FINISHED"}


CLASSES = (
    MATERIALFORGE_OT_generate,
    MATERIALFORGE_OT_surprise,
)

