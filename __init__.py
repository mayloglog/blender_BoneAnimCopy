# SPDX-License-Identifier: GPL-3.0-or-later
bl_info = {
    "name": "Bone Animation Copy Tool",
    "author": "Kumopult (optimized), maylog",
    "description": "Copy animation between armatures using bone constraints.",
    "blender": (4, 2, 0),
    "version": (1, 1, 0),
    "location": "View 3D > UI > BoneAnimCopy",
    "category": "Animation",
    "tracker_url": "https://space.bilibili.com/1628026",
}

import bpy
from bl_operators.presets import AddPresetBase
from math import pi
from mathutils import Euler
import difflib, subprocess, sys
from typing import Optional

# --- Utilities --------------------------------------------------------------

def safe_get_state() -> Optional["BAC_State"]:
    scene = bpy.context.scene
    owner = getattr(scene, "kumopult_bac_owner", None)
    if owner and getattr(owner, "type", None) == 'ARMATURE':
        return getattr(owner.data, "kumopult_bac", None)
    return None

def set_constraint_enabled(con: bpy.types.Constraint, state: bool):
    if hasattr(con, "enabled"):
        con.enabled = state
    elif hasattr(con, "mute"):
        con.mute = not state

def alert_error(title: str, msg: str):
    def draw(self, context):
        self.layout.label(text=msg)
    bpy.context.window_manager.popup_menu(draw, title=title, icon='ERROR')

def open_folder(path: str):
    try:
        bpy.ops.wm.path_open(filepath=path)
    except Exception:
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", path])
        elif sys.platform.startswith("darwin"):
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

# Tag constraints created by addon
BAC_CONSTRAINT_TAG = "bac_addon_marker"

# Simple reentrancy guard decorator
def guard(name="_in_update"):
    def dec(fn):
        def wrapper(self, context):
            if getattr(self, name, False):
                return None
            setattr(self, name, True)
            try:
                return fn(self, context)
            finally:
                setattr(self, name, False)
        return wrapper
    return dec

# --- PropertyGroups --------------------------------------------------------

class BAC_BoneMapping(bpy.types.PropertyGroup):
    selected_owner: bpy.props.StringProperty(name="Owner Bone", update=lambda s, c: s._on_owner(c))
    owner: bpy.props.StringProperty()
    target: bpy.props.StringProperty(name="Target Bone", update=lambda s, c: s._on_target(c))

    has_rotoffs: bpy.props.BoolProperty(name="Rotation Offset", update=lambda s, c: s._apply(c))
    has_loccopy: bpy.props.BoolProperty(name="Copy Location", update=lambda s, c: s._apply(c))
    has_ik: bpy.props.BoolProperty(name="IK", update=lambda s, c: s._apply(c))

    offset: bpy.props.FloatVectorProperty(name="Rotation Offset", subtype='EULER', size=3, min=-pi, max=pi, update=lambda s, c: s._apply(c))
    loc_axis: bpy.props.BoolVectorProperty(name="Location Axes", size=3, default=(True, True, True), update=lambda s, c: s._apply(c))
    ik_influence: bpy.props.FloatProperty(name="IK Influence", default=1.0, min=0.0, max=1.0, update=lambda s, c: s._apply(c))

    selected: bpy.props.BoolProperty(update=lambda s, c: s._on_selected(c))

    _in_update: bool = False

    def _state(self):
        return safe_get_state()

    @guard("_in_update")
    def _on_owner(self, context):
        self.clear_constraints()
        self.owner = self.selected_owner
        state = self._state()
        if state and self.get_owner_pose_bone() and len(self.get_owner_pose_bone().constraints) > 0:
            alert_error("Bone has other constraints",
                        "Mapped bone already has other constraints; mixing them may affect baking.")
        self._apply(context)

    @guard("_in_update")
    def _on_target(self, context):
        state = self._state()
        if state and self.is_valid() and state.calc_offset and state.target and state.owner:
            ob = self.get_owner_pose_bone(); tb = self.get_target_pose_bone()
            if ob and tb:
                try:
                    e = ((state.target.matrix_world @ tb.matrix).inverted() @ (state.owner.matrix_world @ ob.matrix)).to_euler()
                    if state.ortho_offset:
                        step = pi * 0.5
                        e[0] = round(e[0]/step) * step
                        e[1] = round(e[1]/step) * step
                        e[2] = round(e[2]/step) * step
                    if e != Euler((0,0,0)):
                        self.offset = (e[0], e[1], e[2])
                        self.has_rotoffs = True
                except Exception:
                    pass
        self._apply(context)

    def _on_selected(self, context):
        state = self._state()
        if state:
            state.selected_count = sum(1 for m in state.mappings if m.selected)

    def get_owner_pose_bone(self):
        s = self._state()
        if not s or not s.owner: return None
        return s.owner.pose.bones.get(self.owner)

    def get_target_pose_bone(self):
        s = self._state()
        if not s or not s.target: return None
        return s.target.pose.bones.get(self.target)

    def is_valid(self):
        return self.get_owner_pose_bone() is not None and self.get_target_pose_bone() is not None

    def _new_constraint(self, owner_pb, ctype: str, name: str):
        con = owner_pb.constraints.get(name)
        if con:
            return con
        con = owner_pb.constraints.new(ctype)
        con.name = name
        con[BAC_CONSTRAINT_TAG] = True
        try:
            con.show_expanded = False
        except Exception:
            pass
        return con

    def get_constraint(self, kind: str):
        owner_pb = self.get_owner_pose_bone()
        if not owner_pb: return None
        if kind == 'rot': return owner_pb.constraints.get("BAC_ROT_COPY") or self._new_constraint(owner_pb, 'COPY_ROTATION', "BAC_ROT_COPY")
        if kind == 'roll': 
            rr = owner_pb.constraints.get("BAC_ROT_ROLL") or self._new_constraint(owner_pb, 'TRANSFORM', "BAC_ROT_ROLL")
            try:
                rr.map_to = 'ROTATION'; rr.owner_space = 'CUSTOM'
            except Exception: pass
            return rr
        if kind == 'loc': return owner_pb.constraints.get("BAC_LOC_COPY") or self._new_constraint(owner_pb, 'COPY_LOCATION', "BAC_LOC_COPY")
        if kind == 'ik':
            ik = owner_pb.constraints.get("BAC_IK") or self._new_constraint(owner_pb, 'IK', "BAC_IK")
            try:
                ik.chain_count = 2; ik.use_tail = False
            except Exception: pass
            return ik
        return None

    def _apply(self, context):
        state = self._state()
        if not state or not self.get_owner_pose_bone(): return
        # rotation copy
        cr = self.get_constraint('rot')
        if cr:
            try:
                cr.target = state.target; cr.subtarget = self.target
                set_constraint_enabled(cr, self.is_valid() and state.preview)
            except Exception: pass
        # rotation offset
        rr = self.get_constraint('roll')
        if rr:
            if self.has_rotoffs and self.is_valid():
                try:
                    rr.to_min_x_rot = self.offset[0]; rr.to_min_y_rot = self.offset[1]; rr.to_min_z_rot = self.offset[2]
                    rr.target = rr.space_object = state.target; rr.subtarget = rr.space_subtarget = self.target
                    set_constraint_enabled(rr, state.preview)
                except Exception: pass
            else:
                self._remove_constraint(rr)
        # location copy
        cp = self.get_constraint('loc')
        if cp:
            if self.has_loccopy and self.is_valid():
                try:
                    cp.use_x = self.loc_axis[0]; cp.use_y = self.loc_axis[1]; cp.use_z = self.loc_axis[2]
                    cp.target = state.target; cp.subtarget = self.target
                    set_constraint_enabled(cp, state.preview)
                except Exception: pass
            else:
                self._remove_constraint(cp)
        # IK
        ik = self.get_constraint('ik')
        if ik:
            if self.has_ik and self.is_valid():
                try:
                    ik.influence = self.ik_influence; ik.target = state.target; ik.subtarget = self.target
                    set_constraint_enabled(ik, state.preview)
                except Exception: pass
            else:
                self._remove_constraint(ik)

    def _remove_constraint(self, con):
        if not con or not self.get_owner_pose_bone(): return
        if con.get(BAC_CONSTRAINT_TAG):
            try:
                self.get_owner_pose_bone().constraints.remove(con)
            except Exception: pass

    def clear_constraints(self):
        pb = self.get_owner_pose_bone()
        if not pb: return
        for con in list(pb.constraints):
            if con.get(BAC_CONSTRAINT_TAG):
                try: pb.constraints.remove(con)
                except Exception: pass

class BAC_State(bpy.types.PropertyGroup):
    _in_update: bool = False

    @guard("_in_update")
    def update_target(self, context):
        self.owner = bpy.context.scene.kumopult_bac_owner
        self.target = self.selected_target
        for m in self.mappings: m._apply(context)

    @guard("_in_update")
    def update_preview(self, context):
        for m in self.mappings: m._apply(context)

    @guard("_in_update")
    def update_active(self, context):
        if self.sync_select:
            self.update_select(context)
            if 0 <= self.active_mapping < len(self.mappings):
                owner_active = self.owner.data.bones.get(self.mappings[self.active_mapping].owner)
                if owner_active: self.owner.data.bones.active = owner_active
                if self.target:
                    target_active = self.target.data.bones.get(self.mappings[self.active_mapping].target)
                    if target_active: self.target.data.bones.active = target_active

    @guard("_in_update")
    def update_select(self, context):
        if self.sync_select and self.owner and self.target:
            owner_sel = {m.owner for m in self.mappings if m.selected}
            target_sel = {m.target for m in self.mappings if m.selected}
            for b in self.owner.data.bones: b.select = b.name in owner_sel
            for b in self.target.data.bones: b.select = b.name in target_sel

    selected_target: bpy.props.PointerProperty(
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE' and obj != bpy.context.scene.kumopult_bac_owner,
        update=update_target
    )
    target: bpy.props.PointerProperty(type=bpy.types.Object)
    owner: bpy.props.PointerProperty(type=bpy.types.Object)

    mappings: bpy.props.CollectionProperty(type=BAC_BoneMapping)
    active_mapping: bpy.props.IntProperty(default=-1, update=update_active)
    selected_count: bpy.props.IntProperty(default=0, update=update_select)

    editing_type: bpy.props.IntProperty(description="0 mapping,1 rotation,2 location,3 IK")
    preview: bpy.props.BoolProperty(default=True, update=update_preview)

    sync_select: bpy.props.BoolProperty(default=False)
    calc_offset: bpy.props.BoolProperty(default=True)
    ortho_offset: bpy.props.BoolProperty(default=True)

    def get_target_armature(self): return self.target.data if self.target else None
    def get_owner_armature(self): return self.owner.data if self.owner else None
    def get_target_pose(self): return self.target.pose if self.target else None
    def get_owner_pose(self): return self.owner.pose if self.owner else None

    def get_selection(self):
        if self.selected_count == 0 and 0 <= self.active_mapping < len(self.mappings):
            return [self.active_mapping]
        return [i for i in range(len(self.mappings)-1, -1, -1) if self.mappings[i].selected]

    def add_mapping(self, owner: str, target: str, index: int = -1):
        if index == -1: index = self.active_mapping + 1
        m, i = self.get_mapping_by_owner(owner)
        if m:
            m.target = target; self.active_mapping = i; return m, i
        m = self.mappings.add()
        m.selected_owner = owner; m.target = target
        final = max(0, min(index, len(self.mappings)-1))
        self.mappings.move(len(self.mappings)-1, final); self.active_mapping = final
        return self.mappings[final], final

    def remove_mapping(self):
        for i in self.get_selection():
            try: self.mappings[i].clear_constraints()
            except Exception: pass
            try: self.mappings.remove(i)
            except Exception: pass
        self.active_mapping = min(self.active_mapping, max(0, len(self.mappings)-1))
        self.selected_count = 0

    def get_mapping_by_owner(self, name):
        if name:
            for i, m in enumerate(self.mappings):
                if m.owner == name: return m, i
        return None, -1

# --- UI list and operators -------------------------------------------------

class BAC_UL_mappings(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        state = safe_get_state()
        if not state: return
        layout.alert = not item.is_valid()
        layout.active = item.selected or state.selected_count == 0
        row = layout.row(align=True)
        if state.editing_type == 0:
            row.prop(item, "selected", text="", emboss=False, icon='CHECKBOX_HLT' if item.selected else 'CHECKBOX_DEHLT')
            row.prop_search(item, "selected_owner", state.get_owner_armature(), "bones", text="", translate=False, icon='BONE_DATA')
            row.label(icon='BACK')
            row.prop_search(item, "target", state.get_target_armature(), "bones", text="", translate=False, icon='BONE_DATA')
        elif state.editing_type == 1:
            row.prop(item, "has_rotoffs", icon='CON_ROTLIKE', icon_only=True)
            layout.label(text=item.selected_owner, translate=False)
            if item.has_rotoffs: layout.prop(item, "offset", text="")
        elif state.editing_type == 2:
            row.prop(item, "has_loccopy", icon='CON_LOCLIKE', icon_only=True)
            layout.label(text=item.selected_owner, translate=False)
            if item.has_loccopy:
                cp = item.get_constraint('loc')
                if cp:
                    layout.prop(cp, "use_x", text="X", toggle=True)
                    layout.prop(cp, "use_y", text="Y", toggle=True)
                    layout.prop(cp, "use_z", text="Z", toggle=True)
        else:
            row.prop(item, "has_ik", icon='CON_KINEMATIC', icon_only=True)
            layout.label(text=item.selected_owner, translate=False)
            if item.has_ik:
                ik = item.get_constraint('ik')
                if ik: layout.prop(ik, "influence")

class BAC_MT_SettingMenu(bpy.types.Menu):
    bl_label = "Settings"
    def draw(self, context):
        state = safe_get_state()
        if not state: return
        layout = self.layout
        layout.prop(state, "sync_select"); layout.separator()
        layout.prop(state, "calc_offset"); layout.prop(state, "ortho_offset"); layout.separator()

class BAC_MT_presets(bpy.types.Menu):
    bl_label = "Mapping Presets"; preset_subdir = "kumopult_bac"; preset_operator = "script.execute_preset"
    draw = bpy.types.Menu.draw_preset

class AddPresetBACMapping(AddPresetBase, bpy.types.Operator):
    bl_idname = "kumopult_bac.mappings_preset_add"; bl_label = "Add BAC Mappings Preset"
    preset_menu = "BAC_MT_presets"
    preset_defines = ["s = bpy.context.scene.kumopult_bac_owner.data.kumopult_bac"]
    preset_values = ["s.mappings", "s.selected_count"]; preset_subdir = "kumopult_bac"

class BAC_OT_OpenPresetFolder(bpy.types.Operator):
    bl_idname = "kumopult_bac.open_preset_folder"; bl_label = "Open Preset Folder"
    def execute(self, context):
        path = bpy.path.abspath(bpy.utils.resource_path('USER') + "/scripts/presets/kumopult_bac")
        open_folder(path); return {"FINISHED"}

class BAC_OT_SelectEditType(bpy.types.Operator):
    bl_idname = "kumopult_bac.select_edit_type"; bl_label = "Select Edit Type"
    selected_type: bpy.props.IntProperty()
    def execute(self, context):
        s = safe_get_state()
        if not s: return {"CANCELLED"}
        s.editing_type = self.selected_type; return {"FINISHED"}

class BAC_OT_SelectAction(bpy.types.Operator):
    bl_idname = "kumopult_bac.select_action"; bl_label = "List Select Action"
    action: bpy.props.StringProperty()
    def execute(self, context):
        s = safe_get_state()
        if not s: return {"CANCELLED"}
        if self.action == 'ALL': 
            for m in s.mappings: m.selected = True; s.selected_count = len(s.mappings)
        elif self.action == 'INVERSE':
            for m in s.mappings: m.selected = not m.selected
            s.selected_count = sum(1 for m in s.mappings if m.selected)
        else:
            for m in s.mappings: m.selected = False; s.selected_count = 0
        return {"FINISHED"}

class BAC_OT_ListAction(bpy.types.Operator):
    bl_idname = "kumopult_bac.list_action"; bl_label = "List Basic Actions"
    action: bpy.props.StringProperty()
    def execute(self, context):
        s = safe_get_state(); 
        if not s: return {"CANCELLED"}
        if self.action == 'ADD': s.add_mapping('', '')
        elif self.action == 'ADD_SELECT':
            names = [b.name for b in s.owner.data.bones if b.select]
            [s.add_mapping(n, '') for n in names] if names else s.add_mapping('', '')
        elif self.action == 'ADD_ACTIVE':
            owner = s.owner.data.bones.active if s.owner else None
            target = s.target.data.bones.active if s.target else None
            s.add_mapping(owner.name if owner else '', target.name if target else '')
        elif self.action == 'REMOVE': s.remove_mapping()
        elif self.action == 'UP':
            if s.selected_count == 0:
                if len(s.mappings) > s.active_mapping > 0: s.mappings.move(s.active_mapping, s.active_mapping-1); s.active_mapping -= 1
            else:
                idxs = [i for i in range(1, len(s.mappings)) if s.mappings[i].selected]
                for i in idxs:
                    if not s.mappings[i-1].selected: s.mappings.move(i, i-1)
        elif self.action == 'DOWN':
            if s.selected_count == 0:
                if len(s.mappings) > s.active_mapping+1 > 0: s.mappings.move(s.active_mapping, s.active_mapping+1); s.active_mapping += 1
            else:
                idxs = [i for i in range(len(s.mappings)-2, -1, -1) if s.mappings[i].selected]
                for i in idxs:
                    if not s.mappings[i+1].selected: s.mappings.move(i, i+1)
        return {"FINISHED"}

class BAC_OT_ChildMapping(bpy.types.Operator):
    bl_idname = "kumopult_bac.child_mapping"; bl_label = "Child Mapping"
    def execute(self, context):
        s = safe_get_state(); 
        if not s: return {"CANCELLED"}
        flag = False
        for i in s.get_selection():
            m = s.mappings[i]
            if m.selected:
                m.selected = False
            tc = s.get_target_armature().bones[m.target].children
            oc = s.get_owner_armature().bones[m.owner].children
            if len(tc) == len(oc) == 1:
                newm, _ = s.add_mapping(oc[0].name, tc[0].name, i+1); newm.selected = True; flag = True
        if not flag: self.report({"ERROR"}, "No eligible child mapping found")
        return {"FINISHED"}

class BAC_OT_NameMapping(bpy.types.Operator):
    bl_idname = "kumopult_bac.name_mapping"; bl_label = "Name Mapping"
    def execute(self, context):
        s = safe_get_state(); 
        if not s: return {"CANCELLED"}
        for i in s.get_selection():
            m = s.mappings[i]
            best = ''
            best_r = 0.0
            for tb in s.get_target_armature().bones:
                r = difflib.SequenceMatcher(None, m.owner, tb.name).quick_ratio()
                if r > best_r: best_r = r; best = tb.name
            m.target = best
        return {"FINISHED"}

class BAC_OT_MirrorMapping(bpy.types.Operator):
    bl_idname = "kumopult_bac.mirror_mapping"; bl_label = "Mirror Mapping"
    def execute(self, context):
        s = safe_get_state(); 
        if not s: return {"CANCELLED"}
        flag = False
        for i in s.get_selection():
            m = s.mappings[i]
            if m.selected: m.selected = False
            om = s.get_owner_pose().bones.get(bpy.utils.flip_name(m.owner))
            tm = s.get_target_pose().bones.get(bpy.utils.flip_name(m.target))
            if om and tm:
                newm, _ = s.add_mapping(om.name, tm.name, i+1); newm.selected = True; flag = True
        if not flag: self.report({"ERROR"}, "No mirrored mapping created")
        return {"FINISHED"}

class BAC_OT_Bake(bpy.types.Operator):
    bl_idname = "kumopult_bac.bake"; bl_label = "Bake Animation"
    def execute(self, context):
        scene = context.scene; owner_obj = getattr(scene, "kumopult_bac_owner", None)
        s = safe_get_state()
        if not owner_obj or not s or not s.target:
            alert_error("Bake failed", "Owner or target not set"); return {"CANCELLED"}
        bpy.ops.object.mode_set(mode='OBJECT'); bpy.ops.object.select_all(action='DESELECT')
        context.view_layer.objects.active = owner_obj; owner_obj.select_set(True)
        a = s.target.animation_data
        if not a or not getattr(a, "action", None):
            alert_error("No source action", "Source armature has no action"); return {"FINISHED"}
        non_bac = []
        for pb in owner_obj.pose.bones:
            for con in list(pb.constraints):
                if not con.get(BAC_CONSTRAINT_TAG):
                    try:
                        prev = con.enabled if hasattr(con, "enabled") else (not con.mute if hasattr(con, "mute") else True)
                        non_bac.append((con, prev)); set_constraint_enabled(con, False)
                    except Exception: pass
        s.preview = True
        try:
            bpy.ops.nla.bake(frame_start=int(a.action.frame_range[0]), frame_end=int(a.action.frame_range[1]),
                             only_selected=False, visual_keying=True, clear_constraints=False,
                             use_current_action=True, bake_types={'POSE'})
        except Exception:
            try:
                bpy.ops.nla.bake(frame_start=int(a.action.frame_range[0]), frame_end=int(a.action.frame_range[1]),
                                 only_selected=False, visual_keying=True, bake_types={'POSE'})
            except Exception as e:
                alert_error("Bake error", str(e))
        finally:
            s.preview = False
        for con, val in non_bac:
            try: set_constraint_enabled(con, val)
            except Exception: pass
        if owner_obj.animation_data and owner_obj.animation_data.action:
            try: owner_obj.animation_data.action.name = s.target.name; owner_obj.animation_data.action.use_fake_user = True
            except Exception: pass
        return {"FINISHED"}

# Panel draw
def draw_panel(layout):
    s = safe_get_state()
    if not s: return
    row = layout.row(); left = row.column_flow(columns=1, align=True); box = left.box().row()
    if s.editing_type == 0:
        box_left = box.row(align=True)
        if s.selected_count == len(s.mappings) and len(s.mappings) > 0:
            box_left.operator('kumopult_bac.select_action', text='', emboss=False, icon='CHECKBOX_HLT').action = 'NONE'
        else:
            box_left.operator('kumopult_bac.select_action', text='', emboss=False, icon='CHECKBOX_DEHLT').action = 'ALL'
            if s.selected_count != 0:
                box_left.operator('kumopult_bac.select_action', text='', emboss=False, icon='UV_SYNC_SELECT').action = 'INVERSE'
    box_right = box.row(align=False); box_right.alignment = 'RIGHT'
    box_right.operator('kumopult_bac.select_edit_type', text='' if s.editing_type!=0 else 'Mapping', icon='PRESET').selected_type = 0
    box_right.operator('kumopult_bac.select_edit_type', text='' if s.editing_type!=1 else 'Rotation', icon='CON_ROTLIKE').selected_type = 1
    box_right.operator('kumopult_bac.select_edit_type', text='' if s.editing_type!=2 else 'Location', icon='CON_LOCLIKE').selected_type = 2
    box_right.operator('kumopult_bac.select_edit_type', text='' if s.editing_type!=3 else 'IK', icon='CON_KINEMATIC').selected_type = 3
    left.template_list('BAC_UL_mappings', '', s, 'mappings', s, 'active_mapping', rows=7)
    box = left.box().row(align=True)
    box.menu(BAC_MT_presets.__name__, text=BAC_MT_presets.bl_label, translate=False, icon='PRESET')
    box.operator(AddPresetBACMapping.bl_idname, text="", icon='ADD')
    box.operator(AddPresetBACMapping.bl_idname, text="", icon='REMOVE').remove_active = True
    box.separator(); box.operator('kumopult_bac.open_preset_folder', text="", icon='FILE_FOLDER')
    right = row.column(align=True); right.separator(); right.menu(BAC_MT_SettingMenu.__name__, text='', icon='DOWNARROW_HLT'); right.separator()
    if s.owner and s.owner.mode != 'POSE': right.operator('kumopult_bac.list_action', icon='ADD', text='').action = 'ADD'
    elif s.target and s.target.mode != 'POSE': right.operator('kumopult_bac.list_action', icon='PRESET_NEW', text='').action = 'ADD_SELECT'
    else: right.operator('kumopult_bac.list_action', icon='PLUS', text='').action = 'ADD_ACTIVE'
    right.operator('kumopult_bac.list_action', icon='REMOVE', text='').action = 'REMOVE'
    right.operator('kumopult_bac.list_action', icon='TRIA_UP', text='').action = 'UP'
    right.operator('kumopult_bac.list_action', icon='TRIA_DOWN', text='').action = 'DOWN'
    right.separator(); right.operator('kumopult_bac.child_mapping', icon='CON_CHILDOF', text=''); right.operator('kumopult_bac.name_mapping', icon='CON_TRANSFORM_CACHE', text=''); right.operator('kumopult_bac.mirror_mapping', icon='MOD_MIRROR', text='')

class BAC_PT_Panel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"; bl_region_type = "UI"; bl_category = "BoneAnimCopy"; bl_label = "Bone Animation Copy Tool"
    def draw(self, context):
        layout = self.layout; scene = context.scene
        split = layout.row().split(factor=0.2); left = split.column(); right = split.column()
        left.label(text='Source Armature:'); left.label(text='Target Armature:')
        right.prop(scene, 'kumopult_bac_owner', text='', icon='ARMATURE_DATA', translate=False)
        s = safe_get_state()
        if scene.kumopult_bac_owner and scene.kumopult_bac_owner.type == 'ARMATURE' and s:
            right.prop(s, 'selected_target', text='', icon='ARMATURE_DATA', translate=False)
            if not s.target: layout.label(text='Select a different armature object as target to continue', icon='INFO')
            else:
                draw_panel(layout.row()); row = layout.row(); row.prop(s, 'preview', text='Preview Constraints', icon='HIDE_OFF' if s.preview else 'HIDE_ON'); row.operator('kumopult_bac.bake', text='Bake Animation', icon='NLA')
        else:
            right.label(text='No source armature selected', icon='ERROR')

# --- Registration -----------------------------------------------------------

classes = (
    BAC_BoneMapping, BAC_State, BAC_UL_mappings, BAC_MT_SettingMenu, BAC_MT_presets,
    AddPresetBACMapping, BAC_OT_OpenPresetFolder, BAC_OT_SelectEditType, BAC_OT_SelectAction,
    BAC_OT_ListAction, BAC_OT_ChildMapping, BAC_OT_NameMapping, BAC_OT_MirrorMapping,
    BAC_OT_Bake, BAC_PT_Panel,
)

def register():
    for cls in classes: bpy.utils.register_class(cls)
    bpy.types.Scene.kumopult_bac_owner = bpy.props.PointerProperty(type=bpy.types.Object, poll=lambda self, obj: obj.type == 'ARMATURE')
    bpy.types.Armature.kumopult_bac = bpy.props.PointerProperty(type=BAC_State)
    print("BAC registered")

def unregister():
    try: del bpy.types.Scene.kumopult_bac_owner
    except Exception: pass
    try: del bpy.types.Armature.kumopult_bac
    except Exception: pass
    for cls in reversed(classes):
        try: bpy.utils.unregister_class(cls)
        except Exception: pass
    print("BAC unregistered")

if __name__ == "__main__":
    register()
