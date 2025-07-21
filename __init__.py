# SPDX-License-Identifier: GPL-2.0-or-later
import bpy
from bpy.props import PointerProperty, CollectionProperty, IntProperty, BoolProperty
from typing import Optional, Tuple
from .data import BAC_BoneMapping  # 假设 BAC_BoneMapping 已移至 data.py

bl_info = {
    "name": "Bone Animation Copy Tool",
    "author": "Kumopult <kumopult@qq.com>","maylog",
    "description": "A Blender add-on to copy animations between armatures using bone constraints.",
    "blender": (4, 2, 0),
    "version": (1, 0, 1),  
    "location": "View3D > Toolshelf > BoneAnimCopy",
    "category": "Animation",
    "doc_url": "https://github.com/kumopult/blender_BoneAnimCopy",
    "tracker_url": "https://space.bilibili.com/1628026",
}

class BAC_State(bpy.types.PropertyGroup):
    """Manages the state of bone animation copying, including source and target armatures."""

    def update_target(self, context: bpy.types.Context) -> None:
        """Update the target armature and apply mappings."""
        if not self.selected_target or self.selected_target == self.owner:
            self.target = None
            self._clear_mappings_cache()
            return
        try:
            self.owner = context.scene.get("bac_owner")
            self.target = self.selected_target
            self._apply_mappings(context)
        except Exception as e:
            print(f"Error updating target armature: {e}")

    def update_preview(self, context: bpy.types.Context) -> None:
        """Update constraints for animation preview."""
        if self.preview:
            self._apply_mappings(context)

    def update_active(self, context: bpy.types.Context) -> None:
        """Sync active bone selection between owner and target armatures."""
        if not self.sync_select or self.active_mapping < 0:
            return
        try:
            mapping = self.mappings[self.active_mapping]
            owner_bone = self.get_owner_armature().bones.get(mapping.owner)
            target_bone = self.get_target_armature().bones.get(mapping.target)
            if owner_bone and target_bone:
                self.get_owner_armature().bones.active = owner_bone
                self.get_target_armature().bones.active = target_bone
            else:
                print(f"Warning: Bone not found - Owner: {mapping.owner}, Target: {mapping.target}")
        except IndexError:
            print("Warning: Invalid active mapping index")

    def update_select(self, context: bpy.types.Context) -> None:
        """Sync bone selection between owner and target armatures."""
        if not self.sync_select:
            return
        owner_selections = []
        target_selections = []
        for mapping in self.mappings:
            if mapping.selected:
                owner_selections.append(mapping.owner)
                target_selections.append(mapping.target)

        # Batch update selections for performance
        owner_armature = self.get_owner_armature()
        target_armature = self.get_target_armature()
        if owner_armature and target_armature:
            for bone in owner_armature.bones:
                bone.select = bone.name in owner_selections
            for bone in target_armature.bones:
                bone.select = bone.name in target_selections

    def _apply_mappings(self, context: bpy.types.Context) -> None:
        """Apply all bone mappings efficiently with caching."""
        if not self.owner or not self.target:
            return
        try:
            for mapping in self.mappings:
                mapping.apply(self.owner, self.target)
        except Exception as e:
            print(f"Error applying mappings: {e}")

    def _clear_mappings_cache(self) -> None:
        """Clear cached mappings to prevent stale data."""
        for mapping in self.mappings:
            mapping.clear_cache()

    def get_target_armature(self) -> Optional[bpy.types.Armature]:
        """Return the target armature data."""
        return self.target.data if self.target and self.target.type == 'ARMATURE' else None

    def get_owner_armature(self) -> Optional[bpy.types.Armature]:
        """Return the owner armature data."""
        return self.owner.data if self.owner and self.owner.type == 'ARMATURE' else None

    def get_mapping_by_target(self, name: str) -> Tuple[Optional[BAC_BoneMapping], int]:
        """Find a mapping by target bone name."""
        if not name:
            return None, -1
        for i, mapping in enumerate(self.mappings):
            if mapping.target == name:
                return mapping, i
        return None, -1

    selected_target: PointerProperty(
        type=bpy.types.Object,
        name="Target Armature",
        description="Select the target armature to copy animations to.",
        poll=lambda self, obj: obj.type == 'ARMATURE' and obj != bpy.context.scene.get("bac_owner"),
        update=update_target
    )
    target: PointerProperty(
        type=bpy.types.Object,
        name="Active Target",
        description="The currently active target armature."
    )
    owner: PointerProperty(
        type=bpy.types.Object,
        name="Source Armature",
        description="The source armature to copy animations from."
    )
    mappings: CollectionProperty(
        type=BAC_BoneMapping,
        name="Bone Mappings",
        description="Collection of bone mappings between source and target armatures."
    )
    active_mapping: IntProperty(
        name="Active Mapping",
        default=-1,
        description="Index of the active bone mapping.",
        update=update_active
    )
    selected_count: IntProperty(
        name="Selected Mappings",
        default=0,
        description="Number of selected bone mappings.",
        update=update_select
    )
    preview: BoolProperty(
        default=True,
        name="Preview Animation",
        description="Toggle constraints to preview the animation on the target armature.",
        update=update_preview
    )
    sync_select: BoolProperty(
        default=False,
        name="Synchronize Selection",
        description="Sync bone selection between source and target armatures when clicking mappings.",
    )
    calc_offset: BoolProperty(
        default=True,
        name="Auto Calculate Rotation Offset",
        description="Automatically calculate rotation offset for bone mappings."
    )
    ortho_offset: BoolProperty(
        default=True,
        name="Orthogonal Offset",
        description="Approximate rotation offset to multiples of 90 degrees."
    )

def register():
    """Register the add-on classes and properties."""
    try:
        bpy.utils.register_class(BAC_State)
        bpy.types.Scene.bac_state = PointerProperty(type=BAC_State)
    except Exception as e:
        print(f"Error registering add-on: {e}")

def unregister():
    """Unregister the add-on classes and properties."""
    try:
        bpy.utils.unregister_class(BAC_State)
        del bpy.types.Scene.bac_state
    except Exception as e:
        print(f"Error unregistering add-on: {e}")

if __name__ == "__main__":
    register()