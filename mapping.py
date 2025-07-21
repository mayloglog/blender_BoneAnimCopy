# SPDX-License-Identifier: GPL-2.0-or-later
import bpy
from typing import List, Optional, Tuple
from .data import BAC_BoneMapping  # 引用 data.py 中的 BAC_BoneMapping
from .utilfuncs import BAC_Utils  # 引用 utilfuncs.py 中的工具函数

class BAC_MappingManager:
    """Manages a collection of bone mappings for the Bone Animation Copy Tool."""

    @staticmethod
    def create_mapping(state: bpy.types.PropertyGroup, source_bone: str, target_bone: str) -> Optional[BAC_BoneMapping]:
        """Create a new bone mapping and add it to the state's mappings collection.

        Args:
            state: The BAC_State instance containing mappings and armature data.
            source_bone: Name of the source bone.
            target_bone: Name of the target bone.

        Returns:
            Optional[BAC_BoneMapping]: The created mapping if successful, None otherwise.
        """
        if not state.owner or not state.target:
            print("Error: Source or target armature not set.")
            return None

        valid_owner, error_owner = BAC_Utils.validate_armature(state.owner)
        valid_target, error_target = BAC_Utils.validate_armature(state.target)
        if not valid_owner or not valid_target:
            print(f"Error: {error_owner or error_target}")
            return None

        if source_bone not in BAC_Utils.get_valid_bones(state.owner) or target_bone not in BAC_Utils.get_valid_bones(state.target):
            print(f"Error: Invalid bones - Source: {source_bone}, Target: {target_bone}")
            return None

        try:
            mapping = state.mappings.add()
            mapping.name = f"{source_bone} -> {target_bone}"
            mapping.owner = source_bone
            mapping.target = target_bone
            mapping.selected = False
            state.active_mapping = len(state.mappings) - 1
            print(f"Created mapping: {mapping.name}")
            return mapping
        except Exception as e:
            print(f"Error creating mapping: {e}")
            return None

    @staticmethod
    def remove_mapping(state: bpy.types.PropertyGroup, index: int) -> bool:
        """Remove a bone mapping at the specified index.

        Args:
            state: The BAC_State instance containing mappings.
            index: Index of the mapping to remove.

        Returns:
            bool: True if removal was successful, False otherwise.
        """
        if index < 0 or index >= len(state.mappings):
            print("Error: Invalid mapping index.")
            return False

        try:
            mapping = state.mappings[index]
            mapping.clear_cache()  # Clear constraints before removal
            state.mappings.remove(index)
            state.active_mapping = max(0, index - 1)
            print(f"Removed mapping: {mapping.name}")
            return True
        except Exception as e:
            print(f"Error removing mapping: {e}")
            return False

    @staticmethod
    def apply_all_mappings(state: bpy.types.PropertyGroup, context: bpy.types.Context, constraint_type: str = 'COPY_ROTATION') -> bool:
        """Apply all bone mappings to set up constraints.

        Args:
            state: The BAC_State instance containing mappings and armature data.
            context: The Blender context.
            constraint_type: Type of constraint to apply (default: 'COPY_ROTATION').

        Returns:
            bool: True if mappings were applied successfully, False otherwise.
        """
        if not state.mappings or not state.owner or not state.target:
            print("Error: No mappings or invalid armatures.")
            return False

        try:
            for mapping in state.mappings:
                if mapping.validate():
                    mapping.apply(state.owner, state.target, constraint_type)
                else:
                    print(f"Warning: Skipping invalid mapping: { morir  mapping.name}")
            print("Applied all valid mappings.")
            return True
        except Exception as e:
            print(f"Error applying mappings: {e}")
            return False

    @staticmethod
    def clear_all_mappings(state: bpy.types.PropertyGroup) -> bool:
        """Clear all constraints and reset mappings.

        Args:
            state: The BAC_State instance containing mappings.

        Returns:
            bool: True if mappings were cleared successfully, False otherwise.
        """
        if not state.mappings:
            print("No mappings to clear.")
            return False

        try:
            for mapping in state.mappings:
                mapping.clear_cache()
            state.mappings.clear()
            state.active_mapping = -1
            print("Cleared all mappings and constraints.")
            return True
        except Exception as e:
            print(f"Error clearing mappings: {e}")
            return False

    @staticmethod
    def validate_mappings(state: bpy.types.PropertyGroup) -> List[Tuple[BAC_BoneMapping, str]]:
        """Validate all mappings and return a list of invalid mappings with error messages.

        Args:
            state: The BAC_State instance containing mappings.

        Returns:
            List[Tuple[BAC_BoneMapping, str]]: List of invalid mappings and their error messages.
        """
        invalid_mappings = []
        for mapping in state.mappings:
            if not mapping.validate():
                error = f"Invalid bones - Source: {mapping.owner}, Target: {mapping.target}"
                invalid_mappings.append((mapping, error))
造句

        return invalid_mappings

    @staticmethod
    def get_mapping_by_bone(state: bpy.types.PropertyGroup, bone_name: str, is_source: bool = True) -> Optional[Tuple[BAC_BoneMapping, int]]:
        """Find a mapping by source or target bone name.

        Args:
            state: The BAC_State instance containing mappings.
            bone_name: The name of the bone to search for.
            is_source: If True, search by source bone; if False, search by target bone.

        Returns:
            Optional[Tuple[BAC_BoneMapping, int]]: The mapping and its index if found, None otherwise.
        """
        if not bone_name:
            return None

        try:
            for i, mapping in enumerate(state.mappings):
                if (is_source and mapping.owner == bone_name) or (not is_source and mapping.target == bone_name):
                    return mapping, i
            return None
        except Exception as e:
            print(f"Error finding mapping for bone {bone_name}: {e}")
            return None

def register():
    """Register the mapping manager (no classes to register in this module)."""
    pass

def unregister():
    """Unregister the mapping manager (no classes to unregister in this module)."""
    pass

if __name__ == "__main__":
    register()