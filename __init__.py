# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name": "Bone Animation Copy Tool",
    "author": "Kumopult <kumopult@qq.com>,maylog",
    "description": "Copy animation between different armature by bone constrain",
    "blender": (4, 2, 0),
    "version": (1, 0, 1),
    "location": "View 3D > Toolshelf",
    "category": "Animation",
    "doc_url": "https://github.com/kumopult/blender_BoneAnimCopy",
    "tracker_url": "https://space.bilibili.com/1628026",
}

import bpy
from math import pi
from mathutils import Euler
import difflib
import os
from fnmatch import translate
from bl_operators.presets import AddPresetBase

# =============================================
# Utility Functions
# =============================================

def get_state():
    return bpy.context.scene.kumopult_bac_owner.data.kumopult_bac

def set_enable(con: bpy.types.Constraint, state):
    if bpy.app.version >= (3, 0, 0):
        con.enabled = state
    else:
        con.mute = not state

def alert_error(title, message):
    def draw(self, context):
        self.layout.label(text=message)
    bpy.context.window_manager.popup_menu(draw, title=title, icon='ERROR')

# =============================================
# Property Groups
# =============================================

class BAC_BoneMapping(bpy.types.PropertyGroup):
    def update_owner(self, context):
        self.clear()
        self.owner = self.selected_owner
        if self.get_owner() and len(self.get_owner().constraints) > 0:
            alert_error('所选骨骼上包含其它约束', '本插件所生成的约束(名称以BAC开头)若与其它约束混用，可能导致烘焙效果出现偏差。建议避免映射这根骨骼')
        self.apply()

    def update_target(self, context):
        s = get_state()
        if self.is_valid() and s.calc_offset:
            euler_offset = ((s.target.matrix_world @ self.get_target().matrix).inverted() @ 
                          (s.owner.matrix_world @ self.get_owner().matrix)).to_euler()
            if s.ortho_offset:
                step = pi * 0.5
                euler_offset[0] = round(euler_offset[0] / step) * step
                euler_offset[1] = round(euler_offset[1] / step) * step
                euler_offset[2] = round(euler_offset[2] / step) * step
            if euler_offset != Euler((0, 0, 0)):
                self.offset[0] = euler_offset[0]
                self.offset[1] = euler_offset[1]
                self.offset[2] = euler_offset[2]
                self.has_rotoffs = True
        self.apply()
    
    def update_rotcopy(self, context):
        s = get_state()
        cr = self.get_cr()
        cr.target = s.target
        cr.subtarget = self.target
        set_enable(cr, self.is_valid() and s.preview)
    
    def update_rotoffs(self, context):
        s = get_state()
        rr = self.get_rr()
        if self.has_rotoffs:
            rr.to_min_x_rot = self.offset[0]
            rr.to_min_y_rot = self.offset[1]
            rr.to_min_z_rot = self.offset[2]
            rr.target = rr.space_object = s.target
            rr.subtarget = rr.space_subtarget = self.target
            set_enable(rr, self.is_valid() and s.preview)
        else:
            self.remove(rr)
        
    def update_loccopy(self, context):
        s = get_state()
        cp = self.get_cp()
        if self.has_loccopy:
            cp.use_x = self.loc_axis[0]
            cp.use_y = self.loc_axis[1]
            cp.use_z = self.loc_axis[2]
            cp.target = s.target
            cp.subtarget = self.target
            set_enable(cp, self.is_valid() and s.preview)
        else:
            self.remove(cp)
    
    def update_ik(self, context):
        s = get_state()
        ik = self.get_ik()
        if self.has_ik:
            ik.influence = self.ik_influence
            ik.target = s.target
            ik.subtarget = self.target
            set_enable(ik, self.is_valid() and s.preview)
        else:
            self.remove(ik)

    selected_owner: bpy.props.StringProperty(
        name="自身骨骼", 
        description="将对方骨骼的旋转复制到自身的哪根骨骼上？", 
        update=update_owner
    )
    owner: bpy.props.StringProperty()
    target: bpy.props.StringProperty(
        name="约束目标", 
        description="从对方骨架中选择哪根骨骼作为约束目标？", 
        update=update_target
    )

    has_rotoffs: bpy.props.BoolProperty(
        name="旋转偏移", 
        description="附加额外约束，从而在原变换结果的基础上进行额外的旋转", 
        update=update_rotoffs
    )
    has_loccopy: bpy.props.BoolProperty(
        name="位置映射", 
        description="附加额外约束，从而使目标骨骼跟随原骨骼的世界坐标运动，通常应用于根骨骼、武器等", 
        update=update_loccopy
    )
    has_ik: bpy.props.BoolProperty(
        name="IK",
        description="附加额外约束，从而使目标骨骼跟随原骨骼进行IK矫正，通常应用于手掌、脚掌",
        update=update_ik
    )

    offset: bpy.props.FloatVectorProperty(
        name="旋转偏移量", 
        description="世界坐标下复制旋转方向后，在那基础上进行的额外旋转偏移。通常只需要调整Y旋转", 
        min=-pi,
        max=pi,
        subtype='EULER',
        update=update_rotoffs
    )
    loc_axis: bpy.props.BoolVectorProperty(
        name="位置映射轴向",
        default=[True, True, True],
        update=update_loccopy
    )
    ik_influence: bpy.props.FloatProperty(
        name="IK影响权重",
        default=1,
        min=0,
        max=1,
        update=update_ik
    )

    def update_selected(self, context):
        get_state().selected_count += 1 if self.selected else -1
    
    selected: bpy.props.BoolProperty(update=update_selected)

    def get_owner(self):
        return get_state().get_owner_pose().bones.get(self.owner)

    def get_target(self):
        return get_state().get_target_pose().bones.get(self.target)

    def is_valid(self):
        return (self.get_owner() is not None and self.get_target() is not None)

    def apply(self):
        if not self.get_owner():
            return
        self.update_rotcopy(bpy.context)
        self.update_rotoffs(bpy.context)
        self.update_loccopy(bpy.context)
        self.update_ik(bpy.context)

    def clear(self):
        self.remove(self.get_cr())
        self.remove(self.get_rr())
        self.remove(self.get_cp())
        self.remove(self.get_ik())
    
    def remove(self, constraint):
        if not self.get_owner():
            return
        if constraint in self.get_owner().constraints:
            self.get_owner().constraints.remove(constraint)

    def get_cr(self) -> bpy.types.Constraint:
        if not self.get_owner():
            return None
        
        con = self.get_owner().constraints
        cr = con.get('BAC_ROT_COPY')
        if cr:
            return cr
        
        cr = con.new(type='COPY_ROTATION')
        cr.name = 'BAC_ROT_COPY'
        cr.show_expanded = False
        return cr
        
    def get_rr(self) -> bpy.types.Constraint:
        if not self.get_owner():
            return None
        
        con = self.get_owner().constraints
        rr = con.get('BAC_ROT_ROLL')
        if rr:
            return rr
        
        rr = con.new(type='TRANSFORM')
        rr.name = 'BAC_ROT_ROLL'
        rr.map_to = 'ROTATION'
        rr.owner_space = 'CUSTOM'
        rr.show_expanded = False
        return rr
        
    def get_cp(self) -> bpy.types.Constraint:
        if not self.get_owner():
            return None

        con = self.get_owner().constraints
        cp = con.get('BAC_LOC_COPY')
        if cp:
            return cp
        
        cp = con.new(type='COPY_LOCATION')
        cp.name = 'BAC_LOC_COPY'
        cp.show_expanded = False
        return cp

    def get_ik(self) -> bpy.types.Constraint:
        if not self.get_owner():
            return None
        
        con = self.get_owner().constraints
        ik = con.get('BAC_IK')
        if ik:
            return ik
        
        ik = con.new(type='IK')
        ik.name = 'BAC_IK'
        ik.show_expanded = False
        ik.chain_count = 2
        ik.use_tail = False
        return ik

class BAC_State(bpy.types.PropertyGroup):
    def update_target(self, context):
        self.owner = bpy.context.scene.kumopult_bac_owner
        self.target = self.selected_target
        for m in self.mappings:
            m.apply()
    
    def update_preview(self, context):
        for m in self.mappings:
            m.apply()
    
    def update_active(self, context):
        if self.sync_select:
            self.update_select(bpy.context)
            owner_active = self.owner.data.bones.get(self.mappings[self.active_mapping].owner)
            if owner_active:
                self.owner.data.bones.active = owner_active
            target_active = self.target.data.bones.get(self.mappings[self.active_mapping].target)
            if target_active:
                self.target.data.bones.active = target_active
    
    def update_select(self, context):
        if self.sync_select:
            owner_selection = []
            target_selection = []
            for m in self.mappings:
                if m.selected:
                    owner_selection.append(m.owner)
                    target_selection.append(m.target)
            for bone in self.owner.data.bones:
                bone.select = bone.name in owner_selection
            for bone in self.target.data.bones:
                bone.select = bone.name in target_selection
    
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
    
    editing_type: bpy.props.IntProperty(description="用于记录面板类型")
    preview: bpy.props.BoolProperty(
        default=True, 
        description="开关所有约束以便预览烘培出的动画之类的",
        update=update_preview
    )

    sync_select: bpy.props.BoolProperty(default=False, name='同步选择', description="点击列表项时会自动激活相应骨骼\n勾选列表项时会自动选中相应骨骼")
    calc_offset: bpy.props.BoolProperty(default=True, name='自动旋转偏移', description="设定映射目标时自动计算旋转偏移")
    ortho_offset: bpy.props.BoolProperty(default=True, name='正交', description="将计算结果近似至90°的倍数")
    
    def get_target_armature(self):
        return self.target.data if self.target else None

    def get_owner_armature(self):
        return self.owner.data if self.owner else None
    
    def get_target_pose(self):
        return self.target.pose if self.target else None

    def get_owner_pose(self):
        return self.owner.pose if self.owner else None

    def get_active_mapping(self):
        if 0 <= self.active_mapping < len(self.mappings):
            return self.mappings[self.active_mapping]
        return None
    
    def get_mapping_by_target(self, name):
        if name:
            for i, m in enumerate(self.mappings):
                if m.target == name:
                    return m, i
        return None, -1

    def get_mapping_by_owner(self, name):
        if name:
            for i, m in enumerate(self.mappings):
                if m.owner == name:
                    return m, i
        return None, -1

    def get_selection(self):
        indices = []
        if self.selected_count == 0 and 0 <= self.active_mapping < len(self.mappings):
            indices.append(self.active_mapping)
        else:
            for i in range(len(self.mappings)):
                if self.mappings[i].selected:
                    indices.append(i)
        return indices
    
    def add_mapping(self, owner, target, index=-1):
        if index == -1:
            index = self.active_mapping + 1 if self.active_mapping != -1 else 0
        
        m, i = self.get_mapping_by_owner(owner)
        if m:
            m.target = target
            self.active_mapping = i
            return m, i
        else:
            m = self.mappings.add()
            m.selected_owner = owner
            m.target = target
            if index < len(self.mappings):
                self.mappings.move(len(self.mappings) - 1, index)
            self.active_mapping = index
            return self.mappings[index], index
    
    def remove_mapping(self):
        for i in sorted(self.get_selection(), reverse=True):
            self.mappings[i].clear()
            self.mappings.remove(i)
        self.active_mapping = min(self.active_mapping, len(self.mappings) - 1)
        self.selected_count = 0

# =============================================
# UI List and Operators
# =============================================

class BAC_UL_mappings(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index, flt_flag):
        s = get_state()
        layout.alert = not item.is_valid()
        layout.active = item.selected or s.selected_count == 0
        row = layout.row(align=True)

        def mapping():
            row.prop(item, 'selected', text='', emboss=False, icon='CHECKBOX_HLT' if item.selected else 'CHECKBOX_DEHLT')
            row.prop_search(item, 'selected_owner', s.get_owner_armature(), 'bones', text='', translate=False, icon='BONE_DATA')
            row.label(icon='BACK')
            row.prop_search(item, 'target', s.get_target_armature(), 'bones', text='', translate=False, icon='BONE_DATA')
        
        def rotation():
            row.prop(item, 'has_rotoffs', icon='CON_ROTLIKE', icon_only=True)
            layout.label(text=item.selected_owner, translate=False)
            if item.has_rotoffs:
                layout.prop(item, 'offset', text='')
        
        def location():
            row.prop(item, 'has_loccopy', icon='CON_LOCLIKE', icon_only=True)
            layout.label(text=item.selected_owner, translate=False)
            if item.has_loccopy:
                layout.prop(item.get_cp(), 'use_x', text='X', toggle=True)
                layout.prop(item.get_cp(), 'use_y', text='Y', toggle=True)
                layout.prop(item.get_cp(), 'use_z', text='Z', toggle=True)
        
        def ik():
            row.prop(item, 'has_ik', icon='CON_KINEMATIC', icon_only=True)
            layout.label(text=item.selected_owner, translate=False)
            if item.has_ik:
                layout.prop(item.get_ik(), 'influence')
        
        draw_funcs = {
            0: mapping,
            1: rotation,
            2: location,
            3: ik
        }
        
        draw_funcs[s.editing_type]()

class BAC_MT_SettingMenu(bpy.types.Menu):
    bl_label = "Setting"
    def draw(self, context):
        s = get_state()
        layout = self.layout
        layout.prop(s, 'sync_select')
        layout.separator()
        layout.prop(s, 'calc_offset')
        layout.prop(s, 'ortho_offset')

class BAC_MT_presets(bpy.types.Menu):
    bl_label = "映射表预设"
    preset_subdir = "kumopult_bac"
    preset_operator = "script.execute_preset"
    draw = bpy.types.Menu.draw_preset

class AddPresetBACMapping(AddPresetBase, bpy.types.Operator):
    bl_idname = "kumopult_bac.mappings_preset_add"
    bl_label = "添加预设 Add BAC Mappings Preset"
    bl_description = "将当前骨骼映射表保存为预设，以供后续直接套用"
    preset_menu = "BAC_MT_presets"
    preset_defines = ["s = bpy.context.scene.kumopult_bac_owner.data.kumopult_bac"]
    preset_values = ["s.mappings", "s.selected_count"]
    preset_subdir = "kumopult_bac"

class BAC_OT_OpenPresetFolder(bpy.types.Operator):
    bl_idname = 'kumopult_bac.open_preset_folder'
    bl_label = '打开预设文件夹'
    def execute(self, context):
        os.system('explorer ' + bpy.utils.resource_path('USER') + '\scripts\presets\kumopult_bac')
        return {'FINISHED'}

class BAC_OT_SelectEditType(bpy.types.Operator):
    bl_idname = 'kumopult_bac.select_edit_type'
    bl_label = ''
    bl_description = '选择编辑列表类型'
    bl_options = {'UNDO'}
    selected_type: bpy.props.IntProperty()
    def execute(self, context):
        s = get_state()
        s.editing_type = self.selected_type
        return {'FINISHED'}

class BAC_OT_SelectAction(bpy.types.Operator):
    bl_idname = 'kumopult_bac.select_action'
    bl_label = '列表选择操作'
    bl_description = '全选/弃选/反选'
    bl_options = {'UNDO'}
    action: bpy.props.StringProperty()
    def execute(self, context):
        s = get_state()
        if self.action == 'ALL':
            for m in s.mappings:
                m.selected = True
            s.selected_count = len(s.mappings)
        elif self.action == 'INVERSE':
            for m in s.mappings:
                m.selected = not m.selected
            s.selected_count = len(s.mappings) - s.selected_count
        elif self.action == 'NONE':
            for m in s.mappings:
                m.selected = False
            s.selected_count = 0
        return {'FINISHED'}

class BAC_OT_ListAction(bpy.types.Operator):
    bl_idname = 'kumopult_bac.list_action'
    bl_label = '列表基本操作'
    bl_description = '依次为新建、删除、上移、下移\n其中在姿态模式下选中骨骼并点击新建的话，\n可以自动填入对应骨骼'
    bl_options = {'UNDO'}
    action: bpy.props.StringProperty()
    def execute(self, context):
        s = get_state()
        if self.action == 'ADD':
            s.add_mapping('', '')
        elif self.action == 'ADD_SELECT':
            bone_names = [b.name for b in s.owner.data.bones if b.select]
            if bone_names:
                for name in bone_names:
                    s.add_mapping(name, '')
            else:
                s.add_mapping('', '')
        elif self.action == 'ADD_ACTIVE':
            owner = s.owner.data.bones.active
            target = s.target.data.bones.active
            s.add_mapping(owner.name if owner else '', target.name if target else '')
        elif self.action == 'REMOVE':
            if s.mappings:
                s.remove_mapping()
        elif self.action == 'UP':
            if s.selected_count == 0 and 0 < s.active_mapping < len(s.mappings):
                s.mappings.move(s.active_mapping, s.active_mapping - 1)
                s.active_mapping -= 1
            else:
                for i in sorted([i for i in range(1, len(s.mappings)) if s.mappings[i].selected], reverse=True):
                    if not s.mappings[i-1].selected:
                        s.mappings.move(i, i-1)
        elif self.action == 'DOWN':
            if s.selected_count == 0 and 0 <= s.active_mapping < len(s.mappings)-1:
                s.mappings.move(s.active_mapping, s.active_mapping + 1)
                s.active_mapping += 1
            else:
                for i in sorted([i for i in range(len(s.mappings)-1) if s.mappings[i].selected]):
                    if not s.mappings[i+1].selected:
                        s.mappings.move(i, i+1)
        return {'FINISHED'}

class BAC_OT_ChildMapping(bpy.types.Operator):
    bl_idname = 'kumopult_bac.child_mapping'
    bl_label = '子级映射'
    bl_description = '如果选中映射的目标骨骼和自身骨骼都有且仅有唯一的子级，则在那两个子级间建立新的映射'
    bl_options = {'UNDO'}
    execute_flag: bpy.props.BoolProperty(default=False)
    
    @classmethod
    def poll(cls, context):
        s = get_state()
        return all(s.mappings[i].is_valid() for i in s.get_selection())
    
    def execute(self, context):
        s = get_state()
        self.execute_flag = False
        
        for i in s.get_selection():
            m = s.mappings[i]
            if m.selected:
                m.selected = False
            
            target_children = s.get_target_armature().bones[m.target].children
            owner_children = s.get_owner_armature().bones[m.owner].children
            
            if len(target_children) == len(owner_children) == 1:
                new_mapping = s.add_mapping(owner_children[0].name, target_children[0].name, i + 1)[0]
                new_mapping.selected = True
                self.execute_flag = True
            elif owner_children:
                for j, child in enumerate(owner_children):
                    new_mapping = s.add_mapping(child.name, '', i + j + 1)[0]
                    new_mapping.selected = True
                    self.execute_flag = True
        
        if not self.execute_flag:
            self.report({"ERROR"}, "所选项中没有可建立子级映射的映射")
        return {'FINISHED'}

class BAC_OT_NameMapping(bpy.types.Operator):
    bl_idname = 'kumopult_bac.name_mapping'
    bl_label = '名称映射'
    bl_description = '按照名称的相似程度来给自身骨骼自动寻找最接近的目标骨骼'
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(cls, context):
        s = get_state()
        return all(s.mappings[i].get_owner() is not None for i in s.get_selection())
    
    def get_similar_bone(self, owner_name, target_bones):
        similar_name = ''
        similar_ratio = 0
        for target in target_bones:
            r = difflib.SequenceMatcher(None, owner_name, target.name).quick_ratio()
            if r > similar_ratio:
                similar_ratio = r
                similar_name = target.name
        return similar_name
    
    def execute(self, context):
        s = get_state()
        target_bones = s.get_target_armature().bones
        for i in s.get_selection():
            m = s.mappings[i]
            m.target = self.get_similar_bone(m.owner, target_bones)
        return {'FINISHED'}

class BAC_OT_MirrorMapping(bpy.types.Operator):
    bl_idname = 'kumopult_bac.mirror_mapping'
    bl_label = '镜像映射'
    bl_description = '如果选中映射的目标骨骼和自身骨骼都有与之对称的骨骼，则在那两个对称骨骼间建立新的映射'
    bl_options = {'UNDO'}
    execute_flag: bpy.props.BoolProperty(default=False)
    
    @classmethod
    def poll(cls, context):
        s = get_state()
        return all(s.mappings[i].is_valid() for i in s.get_selection())
    
    def execute(self, context):
        s = get_state()
        self.execute_flag = False
        
        for i in s.get_selection():
            m = s.mappings[i]
            if m.selected:
                m.selected = False
            
            owner_mirror = s.get_owner_pose().bones.get(bpy.utils.flip_name(m.owner))
            target_mirror = s.get_target_pose().bones.get(bpy.utils.flip_name(m.target))
            
            if owner_mirror and target_mirror:
                new_mapping = s.add_mapping(owner_mirror.name, target_mirror.name, i + 1)[0]
                new_mapping.selected = True
                self.execute_flag = True
        
        if not self.execute_flag:
            self.report({"ERROR"}, "所选项中没有可镜像的映射")
        return {'FINISHED'}

class BAC_OT_Bake(bpy.types.Operator):
    bl_idname = 'kumopult_bac.bake'
    bl_label = '烘培动画'
    bl_description = '根据来源骨架上动作的帧范围将约束效果烘培为新的动作片段'
    bl_options = {'UNDO'}
    
    def execute(self, context):
        s = get_state()
        if not s.target or not s.target.animation_data or not s.target.animation_data.action:
            alert_error('源骨架上没有动作！', '确保有动作的情况下才能自动判断烘培的帧范围')
            return {'FINISHED'}
        
        # 备份非BAC约束状态
        non_bac_con = []
        for pb in s.owner.pose.bones:
            for con in pb.constraints:
                if not con.name.startswith('BAC'):
                    non_bac_con.append((con, con.enabled if bpy.app.version >= (3, 0, 0) else (not con.mute)))
                    set_enable(con, False)
        
        # 执行烘焙
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = s.owner
        s.owner.select_set(True)
        
        s.preview = True
        action = s.target.animation_data.action
        bpy.ops.nla.bake(
            frame_start=int(action.frame_range[0]),
            frame_end=int(action.frame_range[1]),
            only_selected=False,
            visual_keying=True,
            bake_types={'POSE'}
        )
        s.preview = False
        
        # 恢复非BAC约束状态
        for con, enabled in non_bac_con:
            set_enable(con, enabled)
        
        # 重命名动作
        s.owner.animation_data.action.name = s.target.name + "_baked"
        s.owner.animation_data.action.use_fake_user = True
        
        return {'FINISHED'}

# =============================================
# Main Panel
# =============================================

class BAC_PT_Panel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BoneAnimCopy"
    bl_label = "Bone Animation Copy Tool"
    
    def draw(self, context):
        layout = self.layout
        split = layout.row().split(factor=0.2)
        left = split.column()
        right = split.column()
        
        left.label(text='映射骨架:')
        left.label(text='约束目标:')
        right.prop(context.scene, 'kumopult_bac_owner', text='', icon='ARMATURE_DATA', translate=False)
        
        if context.scene.kumopult_bac_owner and context.scene.kumopult_bac_owner.type == 'ARMATURE':
            s = get_state()
            right.prop(s, 'selected_target', text='', icon='ARMATURE_DATA', translate=False)
            
            if not s.target:
                layout.label(text='选择另一骨架对象作为约束目标以继续操作', icon='INFO')
            else:
                self.draw_mapping_panel(layout.row())
                row = layout.row()
                row.prop(s, 'preview', text='预览约束', icon='HIDE_OFF' if s.preview else 'HIDE_ON')
                row.operator('kumopult_bac.bake', text='烘培动画', icon='NLA')
        else:
            right.label(text='未选中映射骨架对象', icon='ERROR')
    
    def draw_mapping_panel(self, layout):
        s = get_state()
        row = layout.row()
        left = row.column_flow(columns=1, align=True)
        
        # 选择/编辑类型按钮
        box = left.box().row()
        if s.editing_type == 0:
            box_left = box.row(align=True)
            if s.selected_count == len(s.mappings):
                box_left.operator('kumopult_bac.select_action', text='', emboss=False, icon='CHECKBOX_HLT').action = 'NONE'
            else:
                box_left.operator('kumopult_bac.select_action', text='', emboss=False, icon='CHECKBOX_DEHLT').action = 'ALL'
                if s.selected_count != 0:
                    box_left.operator('kumopult_bac.select_action', text='', emboss=False, icon='UV_SYNC_SELECT').action = 'INVERSE'
        
        box_right = box.row(align=False)
        box_right.alignment = 'RIGHT'
        box_right.operator('kumopult_bac.select_edit_type', text='' if s.editing_type!=0 else '映射', icon='PRESET', emboss=True, depress=s.editing_type==0).selected_type = 0
        box_right.operator('kumopult_bac.select_edit_type', text='' if s.editing_type!=1 else '旋转', icon='CON_ROTLIKE', emboss=True, depress=s.editing_type==1).selected_type = 1
        box_right.operator('kumopult_bac.select_edit_type', text='' if s.editing_type!=2 else '位移', icon='CON_LOCLIKE', emboss=True, depress=s.editing_type==2).selected_type = 2
        box_right.operator('kumopult_bac.select_edit_type', text='' if s.editing_type!=3 else 'ＩＫ', icon='CON_KINEMATIC', emboss=True, depress=s.editing_type==3).selected_type = 3
        
        # 映射列表
        left.template_list('BAC_UL_mappings', '', s, 'mappings', s, 'active_mapping', rows=7)
        
        # 预设菜单
        box = left.box().row(align=True)
        box.menu('BAC_MT_presets', text='BAC_MT_presets', translate=False, icon='PRESET')
        box.operator('kumopult_bac.mappings_preset_add', text="", icon='ADD')
        box.operator('kumopult_bac.mappings_preset_add', text="", icon='REMOVE').remove_active = True
        box.separator()
        box.operator('kumopult_bac.open_preset_folder', text="", icon='FILE_FOLDER')
        
        right = row.column(align=True)
        right.separator()
        right.menu('BAC_MT_SettingMenu', text='', icon='DOWNARROW_HLT')
        right.separator()
        
        # 列表操作按钮
        if s.owner.mode != 'POSE':
            right.operator('kumopult_bac.list_action', icon='ADD', text='').action = 'ADD'
        elif s.target.mode != 'POSE':
            right.operator('kumopult_bac.list_action', icon='PRESET_NEW', text='').action = 'ADD_SELECT'
        else:
            right.operator('kumopult_bac.list_action', icon='PLUS', text='').action = 'ADD_ACTIVE'
        
        right.operator('kumopult_bac.list_action', icon='REMOVE', text='').action = 'REMOVE'
        right.operator('kumopult_bac.list_action', icon='TRIA_UP', text='').action = 'UP'
        right.operator('kumopult_bac.list_action', icon='TRIA_DOWN', text='').action = 'DOWN'
        right.separator()
        right.operator('kumopult_bac.child_mapping', icon='CON_CHILDOF', text='')
        right.operator('kumopult_bac.name_mapping', icon='CON_TRANSFORM_CACHE', text='')
        right.operator('kumopult_bac.mirror_mapping', icon='MOD_MIRROR', text='')

# =============================================
# Registration
# =============================================

classes = (
    BAC_BoneMapping,
    BAC_State,
    BAC_UL_mappings,
    BAC_MT_SettingMenu,
    BAC_MT_presets,
    AddPresetBACMapping,
    BAC_OT_OpenPresetFolder,
    BAC_OT_SelectEditType,
    BAC_OT_SelectAction,
    BAC_OT_ListAction,
    BAC_OT_ChildMapping,
    BAC_OT_NameMapping,
    BAC_OT_MirrorMapping,
    BAC_OT_Bake,
    BAC_PT_Panel
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.kumopult_bac_owner = bpy.props.PointerProperty(
        type=bpy.types.Object, 
        poll=lambda self, obj: obj.type == 'ARMATURE'
    )
    bpy.types.Armature.kumopult_bac = bpy.props.PointerProperty(type=BAC_State)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    del bpy.types.Scene.kumopult_bac_owner
    del bpy.types.Armature.kumopult_bac

if __name__ == "__main__":
    register()