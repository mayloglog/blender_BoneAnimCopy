# SPDX-License-Identifier: GPL-2.0-or-later
import bpy
from bpy.types import Panel, Operator
from bpy.props import StringProperty
from .data import BAC_BoneMapping  # 引用 data.py 中的 BAC_BoneMapping
from .mapping import BAC_MappingManager  # 引用 mapping.py 中的 BAC_MappingManager
from .utilfuncs import BAC_Utils  # 引用 utilfuncs.py 中的工具函数

bl_info = {
    "name": "Bone Animation Copy Tool",
    "author": "Kumopult <kumopult@qq.com>",
    "description": "A Blender add-on to copy animations between armatures using bone constraints.",
    "blender": (3, 3, 0),
    "version": (1, 0, 1),  # 版本号与 __init__.py 一致
    "location": "View3D > Toolshelf > BoneAnimCopy",
    "category": "Animation",
    "doc_url": "https://github.com/kumopult/blender_BoneAnimCopy",
    "tracker_url": "https://space.bilibili.com/1628026",
}

class BAC_OT_AddMapping(Operator):
    """Operator to add a new bone mapping between source and target armatures."""
    bl_idname = "bac.add_mapping"
    bl_label = "Add Bone Mapping"
    bl_options = {'REGISTER', 'UNDO'}

    source_bone: StringProperty(
        name="Source Bone",
        description="Name of the source bone to map."
    )
    target_bone: StringProperty(
        name="Target Bone",
        description="Name of the target bone to map."
    )

    def execute(self, context: bpy.types.Context) -> set:
        state = context.scene.bac_state
        if not state.owner or not state.target:
            self.report({'ERROR'}, "Please select both source and target armatures.")
            return {'CANCELLED'}

        if not self.source_bone or not self.target_bone:
            self.report({'ERROR'}, "Please specify both source and target bones.")
            return {'CANCELLED'}

        if BAC_MappingManager.create_mapping(state, self.source_bone, self.target_bone):
            self.report({'INFO'}, f"Added mapping: {self.source_bone} -> {self.target_bone}")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Failed to add mapping. Check bone names.")
            return {'CANCELLED'}

class BAC_OT_RemoveMapping(Operator):
    """Operator to remove the active bone mapping."""
    bl_idname = "bac.remove_mapping"
    bl_label = "Remove Bone Mapping"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: bpy.types.Context) -> set:
        state = context.scene.bac_state
        if state.active_mapping < 0 or state.active_mapping >= len(state.mappings):
            self.report({'ERROR'}, "No active mapping to remove.")
            return {'CANCELLED'}

        if BAC_MappingManager.remove_mapping(state, state.active_mapping):
            self.report({'INFO'}, "Removed active bone mapping.")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Failed to remove mapping.")
            return {'CANCELLED'}

class BAC_OT_ApplyMappings(Operator):
    """Operator to apply all bone mappings."""
    bl_idname = "bac.apply_mappings"
    bl_label = "Apply Mappings"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: bpy.types.Context) -> set:
        state = context.scene.bac_state
        if not state.mappings:
            self.report({'ERROR'}, "No mappings to apply.")
            return {'CANCELLED'}

        valid_owner, error_owner = BAC_Utils.validate_armature(state.owner)
        valid_target, error_target = BAC_Utils.validate_armature(state.target)
        if not valid_owner or not valid_target:
            self.report({'ERROR'}, error_owner or error_target)
            return {'CANCELLED'}

        if BAC_MappingManager.apply_all_mappings(state, context):
            self.report({'INFO'}, "Applied all bone mappings.")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Failed to apply mappings. Check mappings for errors.")
            return {'CANCELLED'}

class BAC_OT_ClearMappings(Operator):
    """Operator to clear all bone mappings and their constraints."""
    bl_idname = "bac.clear_mappings"
    bl_label = "Clear Mappings"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: bpy.types.Context) -> set:
        state = context.scene.bac_state
        if not state.mappings:
            self.report({'ERROR'}, "No mappings to clear.")
            return {'CANCELLED'}

        if BAC_MappingManager.clear_all_mappings(state):
            self.report({'INFO'}, "Cleared all bone mappings and constraints.")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Failed to clear mappings.")
            return {'CANCELLED'}

class BAC_PT_Panel(Panel):
    """UI panel for Bone Animation Copy Tool."""
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BoneAnimCopy'
    bl_label = 'Bone Animation Copy'

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        state = context.scene.bac_state

        # Armature Selection
        box = layout.box()
        box.label(text="Armature Selection", icon='ARMATURE_DATA')
        if context.object and context.object.type == 'ARMATURE':
            box.label(text=f"Target: {context.object.name}", icon='OBJECT_DATA')
            context.scene.bac_owner = context.object
        else:
            box.label(text="Select a target armature in 3D View.", icon='INFO')
        box.prop(state, "selected_target", text="Source Armature")

        # Bone Mappings
        if state.owner and state.target:
            box = layout.box()
            box.label(text="Bone Mappings", icon='BONE_DATA')
            box.prop(state, "sync_select", text="Sync Bone Selection")
            box.prop(state, "preview", text="Preview Animation")
            box.prop(state, "calc_offset", text="Auto Calculate Offset")
            box.prop(state, "ortho_offset", text="Orthogonal Offset")

            # Display Invalid Mappings
            invalid_mappings = BAC_MappingManager.validate_mappings(state)
            if invalid_mappings:
                box.label(text="Invalid mappings detected:", icon='ERROR')
                for mapping, error in invalid_mappings:
                    box.label(text=error, icon='CANCEL')

            # Mapping List
            for i, mapping in enumerate(state.mappings):
                row = box.row(align=True)
                row.prop_search(mapping, "owner", state.owner.data, "bones", text="Source")
                row.prop_search(mapping, "target", state.target.data, "bones", text="Target")
                row.prop(mapping, "selected", text="")
                if i == state.active_mapping:
                    row.label(icon='CHECKMARK')

            # Mapping Controls
            row = box.row(align=True)
            row.operator("bac.add_mapping", text="Add Mapping", icon='PLUS')
            row.operator("bac.remove_mapping", text="Remove Mapping", icon='MINUS')
            row = box.row(align=True)
            row.operator("bac.apply_mappings", text="Apply Mappings", icon='PLAY')
            row.operator("bac.clear_mappings", text="Clear Mappings", icon='X')

        else:
            box.label(text="Select source and target armatures to continue.", icon='INFO')

def register():
    """Register UI panel and operators."""
    try:
        bpy.utils.register_class(BAC_OT_AddMapping)
        bpy.utils.register_class(BAC_OT_RemoveMapping)
        bpy.utils.register_class(BAC_OT_ApplyMappings)
        bpy.utils.register_class(BAC_OT_ClearMappings)
        bpy.utils.register_class(BAC_PT_Panel)
    except Exception as e:
        print(f"Error registering UI components: {e}")

def unregister():
    """Unregister UI panel and operators."""
    try:
        bpy.utils.unregister_class(BAC_OT_AddMapping)
        bpy.utils.unregister_class(BAC_OT_RemoveMapping)
        bpy.utils.unregister_class(BAC_OT_ApplyMappings)
        bpy.utils.unregister_class(BAC_OT_ClearMappings)
        bpy.utils.unregister_class(BAC_PT_Panel)
    except Exception as e:
        print(f"Error unregistering UI components: {e}")

if __name__ == "__main__":
    register()