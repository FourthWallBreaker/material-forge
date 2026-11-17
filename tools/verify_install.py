import bpy
result = bpy.ops.preferences.addon_install(filepath=r"C:\Users\dorro\dev\material-forge\dist\material_forge-0.2.0.zip", overwrite=True)
print("install result:", result)
bpy.ops.preferences.addon_enable(module="material_forge")
print("enabled:", "material_forge" in bpy.context.preferences.addons)
import material_forge
print("import ok, version", material_forge.bl_info["version"])
