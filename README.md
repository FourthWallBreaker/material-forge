# Material Forge

Blender 5.x add-on that generates procedural shader node graphs from a text prompt.

**Hybrid engine:** 12 offline presets handle common requests instantly; an
OpenAI-compatible model is used as a fallback for anything the vocabulary does
not know. The model never emits raw `bl_idname`s — every node type goes through
a whitelist registry, so out-of-scope requests fail closed.

## Install
1. Download `material_forge-0.2.0.zip` from the
   [latest release](https://github.com/FourthWallBreaker/material-forge/releases/latest).
2. In Blender: **Edit → Preferences → Add-ons → ⌄ → Install from Disk** →
   select the zip → enable **Material Forge**.
3. The panel lives in the 3D Viewport sidebar (**N** key) under the **Forge** tab.

## Using it
- **Presets (offline):** set Engine to *Preset*, pick one, click *Forge Material*.
  Works with no API key.
- **Auto:** presets first; the model is used only for unfamiliar prompts.
- **Model:** always ask the model (requires an API key in preferences).

## Connecting your AI
Preferences → Add-ons → Material Forge → pick a **Provider**
(OpenAI, OpenRouter, Anthropic/Claude, Ollama, LM Studio, or Custom), paste your
key, choose a model. Your key is stored only in this Blender's add-on
preferences on your own machine; Material Forge sends it only to the provider you
choose. For a fully local, key-free setup use the **Ollama (local)** or
**LM Studio (local)** preset.

## License
GPL-3.0-or-later (see `LICENSE`).
