# SPDX-License-Identifier: GPL-2.0-or-later
import bpy
from bpy.props import StringProperty, BoolProperty
from typing import Optional
from .utilfuncs import BAC_Utils  # 引用 utilfuncs.py 中的工具函数

class BAC_BoneMapping(bpy.types.PropertyGroup):
    """Property group for managing a single bone mapping between source and target armatures."""
    
    name: StringProperty(
        name="Mapping Name",
        description="Name of the bone mapping.",
        default="Bone Mapping"
    )
    
    owner: StringProperty(
        name="Source Bone",
        description="Name of the source bone in the source armature."
    )
    
    target: StringProperty(
        name="Target Bone",
        description="Name of the target bone in the target armature."
    )
    
    selected: BoolProperty(
        name="Selected",
        description="Whether this mapping is selected for synchronization.",
        default=False
    )
    
    _constraint_cache = None  # Internal cache for constraints

    def apply(self, owner: bpy.types.Object, target: bpy.types.Object, constraint_type: str = 'COPY_ROTATION') -> bool:
        """Apply the bone mapping by setting up constraints.

        Args:
            owner: The source armature object.
            target: The target armature object.
            constraint_type: Type of constraint to apply (default: 'COPY_ROTATION').

        Returns:
            bool: True if the constraint was applied successfully, False otherwise.
        """
        if not self.owner or not self.target:
            print(f"Warning: Invalid mapping parameters for {self.name}")
            return False

        valid_owner, error_owner = BAC_Utils.validate_armature(owner)
        valid_target, error_target = BAC_Utils.validate_armature(target)
        if not valid_owner or not valid_target:
            print(f"Error: {error_owner or error_target}")
            return False

        owner_bone = BAC_Utils.get_bone(owner, self.owner)
        target_pose_bone = target.pose.bones.get(self.target)
        if not owner_bone or not target_pose_bone:
            print(f"Error: Bone not found - Source: {self.owner}, Target: {self.target}")
            return False

        try:
            # Remove existing constraints with the same name
            BAC_Utils.remove_constraints(target, self.target, constraint_prefix="BAC_")

            # Add new constraint
            constraint = target_pose_bone.constraints.new(constraint_type)
            constraint.name = f"BAC_{self.target}"
            constraint.target = owner
            constraint.subtarget = self.owner
            constraint.mix_mode = 'ADD' if constraint_type == 'COPY_ROTATION' else 'REPLACE'
            constraint.target_space = 'WORLD'
            constraint.owner_space = 'WORLD'

            # Cache the constraint
            self._constraint_cache = constraint
            print(f"Applied {constraint_type} constraint: {self.owner} -> {self.target}")
            return True
        except Exception as e:
            print(f"Error applying mapping {self.name}: {e}")
            return False

    def clear_cache(self) -> bool:
        """Clear cached constraints for this mapping.

        Returns:
            bool: True if constraints were cleared successfully, False otherwise.
        """
        try:
            if self._constraint_cache:
                target_obj = bpy.data.objects.get(self._constraint_cache.target.name)
                if target_obj and self.target in target_obj.pose.bones:
                    BAC_Utils.remove_constraints(target_obj, self.target, constraint_prefix="BAC_")
                self._constraint_cache = None
                print(f"Cleared constraints for mapping: {self.name}")
            return True
        except Exception as e:
            print(f"Error clearing cache for mapping {self.name}: {e}")
            return False

    def validate(self) -> bool:
        """Validate the mapping by checking if bones exist in their respective armatures.

        Returns:
            bool: True if the mapping is valid, False otherwise.
        """
        owner_obj = bpy.context.scene.get("bac_owner")
        target_obj = bpy.context.scene.bac_state.target
        if not owner_obj or not target_obj:
            return False
        return (
            BAC_Utils.get_bone(owner_obj, self.owner) is not None and
            BAC_Utils.get_bone(target_obj, self.target) is not None
        )

def register():
    """Register the BAC_BoneMapping class."""
    try:
        bpy.utils.register_class(BAC_BoneMapping)
    except Exception as e:
        print(f"Error registering BAC_BoneMapping: {e}")

def unregister():
    """Unregister the BAC_BoneMapping class."""
    try:
        bpy.utils.unregister_class(BAC_BoneMapping)
    except Exception as e:
        print(f"Error unregistering BAC_BoneMapping: {e}")

if __name__ == "__main__":
    register()