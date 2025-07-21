# SPDX-License-Identifier: GPL-2.0-or-later
import bpy
from typing import Optional, List, Tuple

class BAC_Utils:
    """Static utility functions for the Bone Animation Copy Tool."""

    @staticmethod
    def validate_armature(obj: Optional[bpy.types.Object]) -> Tuple[bool, str]:
        """Validate if the object is a valid armature.

        Args:
            obj: The Blender object to validate.

        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        if not obj:
            return False, "No object provided."
        if obj.type != 'ARMATURE':
            return False, f"Object '{obj.name}' is not an armature."
        if not obj.data or not isinstance(obj.data, bpy.types.Armature):
            return False, f"Object '{obj.name}' has invalid armature data."
        return True, ""

    @staticmethod
    def get_bone(obj: bpy.types.Object, bone_name: str) -> Optional[bpy.types.Bone]:
        """Retrieve a bone from an armature by name.

        Args:
            obj: The armature object.
            bone_name: The name of the bone to find.

        Returns:
            Optional[bpy.types.Bone]: The bone if found, else None.
        """
        if not bone_name:
            return None
        valid, error = BAC_Utils.validate_armature(obj)
        if not valid:
            print(f"Error getting bone: {error}")
            return None
        try:
            return obj.data.bones.get(bone_name)
        except Exception as e:
            print(f"Error getting bone '{bone_name}': {e}")
            return None

    @staticmethod
    def select_bones(armature: bpy.types.Object, bone_names: List[str], deselect_others: bool = True) -> bool:
        """Select specified bones in an armature.

        Args:
            armature: The armature object.
            bone_names: List of bone names to select.
            deselect_others: If True, deselect all other bones.

        Returns:
            bool: True if selection was successful, False otherwise.
        """
        valid, error = BAC_Utils.validate_armature(armature)
        if not valid:
            print(f"Error selecting bones: {error}")
            return False

        try:
            if deselect_others:
                for bone in armature.data.bones:
                    bone.select = False
            for bone_name in bone_names:
                bone = armature.data.bones.get(bone_name)
                if bone:
                    bone.select = True
            return True
        except Exception as e:
            print(f"Error selecting bones: {e}")
            return False

    @staticmethod
    def remove_constraints(armature: bpy.types.Object, bone_name: str, constraint_prefix: str = "BAC_") -> bool:
        """Remove constraints with a specific prefix from a pose bone.

        Args:
            armature: The armature object.
            bone_name: The name of the pose bone.
            constraint_prefix: Prefix of constraints to remove (default: 'BAC_').

        Returns:
            bool: True if constraints were removed, False otherwise.
        """
        valid, error = BAC_Utils.validate_armature(armature)
        if not valid or not bone_name:
            print(f"Error removing constraints: {error or 'No bone name provided.'}")
            return False

        try:
            pose_bone = armature.pose.bones.get(bone_name)
            if not pose_bone:
                print(f"Error: Pose bone '{bone_name}' not found.")
                return False

            constraints_to_remove = [c for c in pose_bone.constraints if c.name.startswith(constraint_prefix)]
            for constraint in constraints_to_remove:
                pose_bone.constraints.remove(constraint)
            return True
        except Exception as e:
            print(f"Error removing constraints for '{bone_name}': {e}")
            return False

    @staticmethod
    def synchronize_selection(state: bpy.types.PropertyGroup) -> bool:
        """Synchronize bone selection between source and target armatures based on mappings.

        Args:
            state: The BAC_State instance containing mappings and armature data.

        Returns:
            bool: True if synchronization was successful, False otherwise.
        """
        if not state.sync_select or not state.owner or not state.target:
            return False

        try:
            owner_bones = []
            target_bones = []
            for mapping in state.mappings:
                if mapping.selected:
                    owner_bones.append(mapping.owner)
                    target_bones.append(mapping.target)

            # Select bones in source and target armatures
            BAC_Utils.select_bones(state.owner, owner_bones, deselect_others=True)
            BAC_Utils.select_bones(state.target, target_bones, deselect_others=True)
            return True
        except Exception as e:
            print(f"Error synchronizing selection: {e}")
            return False

    @staticmethod
    def get_valid_bones(armature: bpy.types.Object) -> List[str]:
        """Get a list of valid bone names in an armature.

        Args:
            armature: The armature object.

        Returns:
            List[str]: List of bone names.
        """
        valid, error = BAC_Utils.validate_armature(armature)
        if not valid:
            print(f"Error getting valid bones: {error}")
            return []

        try:
            return [bone.name for bone in armature.data.bones]
        except Exception as e:
            print(f"Error listing bones: {e}")
            return []

def register():
    """Register the utility module (no classes to register)."""
    pass

def unregister():
    """Unregister the utility module (no classes to unregister)."""
    pass

if __name__ == "__main__":
    register()