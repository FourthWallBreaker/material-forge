"""Preferences, scene properties and the sidebar panel."""

import bpy

from . import presets

PROVIDER_PRESETS = {
    "OPENAI": ("https://api.openai.com/v1", "gpt-4o-mini"),
    "OPENROUTER": ("https://openrouter.ai/api/v1", "openai/gpt-4o-mini"),
    "ANTHROPIC": ("https://api.anthropic.com/v1", "claude-3-5-sonnet-latest"),
    "OLLAMA": ("http://localhost:11434/v1", "llama3.1"),
    "LMSTUDIO": ("http://localhost:1234/v1", "local-model"),
    "CUSTOM": (None, None),
}


def _apply_provider(self, context):
    url, model = PROVIDER_PRESETS.get(self.provider, (None, None))
    if url is not None:
        self.base_url = url
    if model is not None:
        self.model = model
    return None


def get_prefs(context=None):
    context = context or bpy.context
    try:
        addon = context.preferences.addons.get(__package__)
    except AttributeError:
        return None
    return addon.preferences if addon else None


class MaterialForgePreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    provider: bpy.props.EnumProperty(
        name="Provider",
        description="Choose where your AI comes from; base URL and model are filled in",
        items=(
            ("OPENAI", "OpenAI", "api.openai.com"),
            ("OPENROUTER", "OpenRouter", "openrouter.ai"),
            ("ANTHROPIC", "Anthropic (Claude)", "api.anthropic.com"),
            ("OLLAMA", "Ollama (local)", "localhost:11434"),
            ("LMSTUDIO", "LM Studio (local)", "localhost:1234"),
            ("CUSTOM", "Custom endpoint", "Enter your own URL"),
        ),
        default="OPENAI",
        update=_apply_provider,
    )
    base_url: bpy.props.StringProperty(
        name="API Base URL",
        description="OpenAI-compatible endpoint, e.g. https://api.openai.com/v1 "
        "or http://localhost:1234/v1 for LM Studio",
        default="https://api.openai.com/v1",
    )
    api_key: bpy.props.StringProperty(
        name="API Key",
        description="Bearer token. Leave empty to stay fully offline",
        subtype="PASSWORD",
        default="",
    )
    model: bpy.props.StringProperty(
        name="Model",
        description="Model name as the endpoint expects it",
        default="gpt-4o-mini",
    )
    temperature: bpy.props.FloatProperty(
        name="Temperature",
        description="Higher values give more varied node graphs",
        default=0.7,
        min=0.0,
        max=2.0,
    )
    timeout: bpy.props.IntProperty(
        name="Timeout",
        description="Seconds to wait for the model",
        default=60,
        min=5,
        max=600,
    )
    json_mode: bpy.props.BoolProperty(
        name="Request JSON mode",
        description="Ask the server to constrain output to JSON. Disabled automatically "
        "if the server rejects it",
        default=True,
    )

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Model endpoint (optional)", icon="URL")
        box.prop(self, "provider")
        box.prop(self, "base_url")
        box.prop(self, "api_key")
        box.prop(self, "model")
        row = box.row()
        row.prop(self, "temperature")
        row.prop(self, "timeout")
        box.prop(self, "json_mode")
        if not self.api_key:
            box.label(
                text="Please connect your AI using your key",
                icon="LOCKED",
            )
            box.label(
                text="Your key is stored only in this Blender's add-on",
                icon="INFO",
            )
            box.label(
                text="preferences on your own machine; Material Forge",
                icon="BLANK1",
            )
            box.label(
                text="never sends it anywhere except to the provider you choose.",
                icon="BLANK1",
            )


class MATERIALFORGE_PT_panel(bpy.types.Panel):
    bl_label = "Material Forge"
    bl_idname = "MATERIALFORGE_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Forge"

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        prefs = get_prefs(context)

        col = layout.column(align=True)
        col.label(text="Describe a material")
        col.prop(scene, "mf_prompt", text="")

        row = layout.row(align=True)
        row.prop(scene, "mf_engine", expand=True)
        if scene.mf_engine == "PRESET":
            layout.prop(scene, "mf_preset", text="")

        layout.operator("material_forge.generate", icon="NODETREE")
        layout.operator("material_forge.surprise", icon="ADD")

        if scene.mf_status:
            layout.separator()
            layout.label(text=scene.mf_status[:90], icon="INFO")

        if scene.mf_engine != "PRESET" and prefs is not None and not prefs.api_key:
            layout.label(text="Please connect your AI using your key", icon="LOCKED")
            layout.label(text="Key stored only on your machine", icon="INFO")


CLASSES = (
    MaterialForgePreferences,
    MATERIALFORGE_PT_panel,
)


# --------------------------------------------------------------------------
# Scene properties
# --------------------------------------------------------------------------
def register_props():
    bpy.types.Scene.mf_prompt = bpy.props.StringProperty(
        name="Prompt",
        description="What material do you want?",
        default="",
    )
    bpy.types.Scene.mf_engine = bpy.props.EnumProperty(
        name="Engine",
        description="How the material is chosen",
        items=(
            ("AUTO", "Auto", "Presets first, model for anything unfamiliar"),
            ("PRESET", "Preset", "Force a built-in preset"),
            ("LLM", "Model", "Always ask the model"),
        ),
        default="AUTO",
    )
    bpy.types.Scene.mf_preset = bpy.props.EnumProperty(
        name="Preset",
        items=presets.preset_labels(),
        default=presets.PRESETS[0]["key"],
    )
    bpy.types.Scene.mf_status = bpy.props.StringProperty(
        name="Status",
        default="",
    )


def unregister_props():
    for prop in ("mf_prompt", "mf_engine", "mf_preset", "mf_status"):
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)
