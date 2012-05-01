#  ***** BEGIN GPL LICENSE BLOCK *****
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#  ***** END GPL LICENSE BLOCK *****

# <pep8-80 compliant>

bl_info = {
    "name": "Cut/Copy/Paste objects and elements",
    "author": "dairin0d",
    "version": (0, 5),
    "blender": (2, 6, 3),
    "location": "View3D -> Ctrl+X, Ctrl+C, Ctrl+V",
    "description": "Cut/Copy/Paste objects and elements",
    "warning": "",
    "wiki_url": "http://wiki.blender.org/index.php/Extensions:2.6/Py/"\
                "Scripts/3D_interaction/CutCopyPaste3D",
    "tracker_url": "http://projects.blender.org/tracker/"\
                   "?func=detail&aid=31214",
    "category": "3D View"}
#============================================================================#

import bpy

from mathutils import Vector, Matrix, Quaternion

from bpy_extras.view3d_utils import (region_2d_to_vector_3d,
                                     region_2d_to_location_3d,
                                     location_3d_to_region_2d)

import os
import glob
import time
import json

# Blender ~bugs:
# - Transform operator should revert to default snap mode if Ctrl status
#   is released (if Ctrl was held when the operator was called, it would
#   think that Ctrl is still pressed even when it's not)
# - When appending from file, objects with parent-child relations update
#   strangely (when moving the parent, the child does not update)

# TODO: save copy/paste preferences?

# There is already a built-in copy/paste pose operator.
# Text edit mode also has copy/paste (plain text).
# There seems to be no meaningful copy/paste for particles/lattice
# Surface copy/paste is quite limited, since only whole patches can
# be safely pasted.
copy_paste_modes = {'OBJECT', 'EDIT_MESH', 'EDIT_CURVE', 'EDIT_SURFACE',
                    'EDIT_ARMATURE', 'EDIT_METABALL'}

def is_view3d(context):
    return ((context.area.type == 'VIEW_3D') and
            (context.region.type == 'WINDOW'))

def get_view_rotation(context):
    v3d = context.space_data
    rv3d = context.region_data
    if rv3d.view_perspective == 'CAMERA':
        return v3d.camera.matrix_world.to_quaternion()
    else:
        return rv3d.view_rotation

# We can't use the same clipboard file, because Blender keeps reference
# to a library after appending from it (-> forbids to save files with
# that filepath).
def make_clipboard_path():
    # LOCAL is blender's executable location,
    # and Blender must always start from ASCII path
    # (at least until non-ASCII problems are fixed)
    resource_path = bpy.utils.resource_path('LOCAL') # USER SYSTEM
    
    lib_paths = set(os.path.normcase(bpy.path.abspath(lib.filepath))
                    for lib in bpy.data.libraries)
    
    startkey = str(int(time.clock())).replace(".", "_") + "_"
    i = 0
    while True:
        name = "clipboard.%s.blend" % (startkey + str(i))
        path = os.path.normcase(os.path.join(resource_path, name))
        if path not in lib_paths:
            return path
        i += 1

def remove_clipboard_files():
    resource_path = bpy.utils.resource_path('LOCAL') # USER SYSTEM
    
    filemask = os.path.join(resource_path, "clipboard.*.blend")
    for path in glob.glob(filemask):
        os.remove(path)

def is_clipboard_path(path):
    resource_path = bpy.utils.resource_path('LOCAL') # USER SYSTEM
    
    resource_path = os.path.normcase(resource_path)
    path = os.path.normcase(bpy.path.abspath(path))
    
    if path.startswith(resource_path):
        path = path[len(resource_path):]
        if path.startswith(os.path.sep):
            path = path[1:]
        if path.startswith("clipboard.") and path.endswith(".blend"):
            return True
    
    return False

class CopyPasteOptions(bpy.types.PropertyGroup):
    external = bpy.props.BoolProperty(
        name="External",
        description="Allow copy/paste to/from other file(s)",
        default=True,
        )
    append = bpy.props.BoolProperty(
        name="Append",
        description="Append new objects (instead of link)",
        default=True,
        )
    paste_at_cursor = bpy.props.BoolProperty(
        name="Paste at Cursor",
        description="Paste at the Cursor "\
            "(instead of the coordinate system origin)",
        default=True,
        )
    move_to_mouse = bpy.props.BoolProperty(
        name="Move to mouse",
        description="Align pivot of pasted objects to the mouse location",
        default=True,
        )
    align_to_view = bpy.props.BoolProperty(
        name="Align to view",
        description="Rotate pasted objects to match their orientation "\
            "relative to view when they were copied",
        default=False,
        )
    coordinate_system = bpy.props.EnumProperty(
        name="Coordinate System",
        description="A coordinate system to copy/paste in "\
            "(ignored in Object mode)",
        default='CONTEXT',
        items=[
            ('CONTEXT', "Context", "Local in Edit mode, Global otherwise"),
            ('GLOBAL', "Global", "Global"),
            ('LOCAL', "Local", "Local"),
        ]
        )
    
    def actual_coordsystem(self, context=None):
        if self.coordinate_system == 'CONTEXT':
            if 'EDIT' in (context or bpy.context).mode:
                return 'LOCAL'
            else:
                return 'GLOBAL'
        return self.coordinate_system

class VIEW3D_PT_copy_paste(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_label = "Copy/Paste"
    
    coordsystem_icons = {'GLOBAL':'WORLD', 'LOCAL':'MANIPUL'}
    
    def draw(self, context):
        layout = self.layout
        
        opts = context.window_manager.copy_paste_options
        
        row = layout.row(True)
        row.enabled = (context.mode in copy_paste_modes)
        
        row.prop(opts, "external", text="", icon='URL')
        row.prop(opts, "append", text="", icon='LINK_BLEND')
        row.prop(opts, "paste_at_cursor", text="", icon='CURSOR')
        row.prop(opts, "move_to_mouse", text="", icon='RESTRICT_SELECT_OFF')
        row.prop(opts, "align_to_view", text="", icon='CAMERA_DATA')
        
        coordsystem = opts.actual_coordsystem(context)
        icon = self.coordsystem_icons[coordsystem]
        row.prop_menu_enum(opts, "coordinate_system", text="", icon=icon)

class OperatorCopy(bpy.types.Operator):
    '''Copy objects/elements'''
    bl_idname = "view3d.copy"
    bl_label = "Copy objects/elements"
    
    force_copy = bpy.props.BoolProperty(default=False, options={'HIDDEN'})
    
    @classmethod
    def poll(cls, context):
        if context.mode not in copy_paste_modes:
            return False
        return context.selected_objects
    
    def write_object(self, json_data, context):
        wm = context.window_manager
        opts = wm.copy_paste_options
        
        self_is_clipboard = False
        
        # Cut operation deletes objects from the scene after copying,
        # so we have to store them somewhere else (-> force_copy=True).
        if opts.external or self.force_copy:
            path = bpy.data.filepath
            if (not path) or self.force_copy:
                path = make_clipboard_path()
                self_is_clipboard = True
            self_library = path
        else:
            self_library = ""
        
        libraries = {}
        libraries_inv = {}
        
        def library_id(obj):
            if obj.library:
                path = bpy.path.abspath(obj.library.filepath)
            else:
                path = self_library
            
            if path in libraries:
                return libraries[path]
            # JSON turns all keys into strings anyway
            id = str(len(libraries))
            libraries[path] = id
            libraries_inv[id] = path
            return id
        
        objects = {}
        parents = {}
        active_obj = context.object
        
        for obj in context.selected_objects:
            if obj == active_obj:
                json_data["active_object"] = obj.name
                json_data["active_object_library"] = library_id(obj)
            
            objects[obj.name] = library_id(obj)
            
            if obj.parent:
                parents[obj.name] = (obj.parent.name, obj.parent_bone)
        
        json_data["objects"] = objects
        json_data["parents"] = parents
        
        json_data["libraries"] = libraries_inv
        
        if self_library and (self_library in libraries):
            if self_is_clipboard:
                remove_clipboard_files()
                bpy.ops.wm.save_as_mainfile(filepath=self_library,
                    check_existing=False, copy=True)
            else:
                # make sure the file is up-to-date
                bpy.ops.wm.save_mainfile(check_existing=False)
    
    def execute(self, context):
        wm = context.window_manager
        opts = wm.copy_paste_options
        
        json_data = {"content":"Blender 3D-clipboard"}
        
        json_data["cursor"] = tuple(context.space_data.cursor_location)
        
        if is_view3d(context):
            json_data["view"] = tuple(get_view_rotation(context))
        
        if 'EDIT' in context.mode:
            obj = bpy.context.object
            
            json_data["type"] = obj.type
            json_data["matrix"] = [tuple(v) for v in obj.matrix_world]
        else:
            json_data["type"] = 'OBJECT'
            json_data["matrix"] = [tuple(v) for v in Matrix()]
            
            self.write_object(json_data, context)
        
        wm.clipboard = json.dumps(json_data)
        
        return {'FINISHED'}

class OperatorPaste(bpy.types.Operator):
    '''Paste objects/elements'''
    bl_idname = "view3d.paste"
    bl_label = "Paste objects/elements"
    
    data_types = {'OBJECT', 'MESH', 'CURVE', 'SURFACE', 'META', 'ARMATURE'}
    
    @classmethod
    def poll(cls, context):
        return context.mode in copy_paste_modes
    
    def read_clipboard_object(self, json_data, context):
        self.active_object = json_data.get("active_object", "")
        assert isinstance(self.active_object, str)
        
        active_object_library = json_data.get("active_object_library", "")
        active_object_library = str(active_object_library)
        
        self.parents = json_data.get("parents", {})
        assert isinstance(self.parents, dict)
        for k, v in self.parents.items():
            assert len(v) == 2
            assert isinstance(v[0], str) and isinstance(v[1], str)
        
        objects = json_data["objects"]
        assert isinstance(objects, dict) and objects
        
        libraries = json_data["libraries"]
        assert isinstance(libraries, dict) and libraries
        
        # Make sure library paths are absolute and
        # that this file is marked a special way
        this_path = os.path.normcase(bpy.data.filepath)
        for id, lib_path in list(libraries.items()):
            assert isinstance(lib_path, str)
            if not lib_path:
                continue
            lib_path = os.path.normcase(bpy.path.abspath(lib_path))
            libraries[id] = ("" if lib_path == this_path else lib_path)
        
        self.active_object_library = \
            libraries.get(active_object_library, None)
        
        # Gather all objects under their respective libraries
        self.libraries = {}
        for obj_name, id in objects.items():
            assert isinstance(obj_name, str)
            lib_path = libraries[str(id)]
            obj_names = self.libraries.get(lib_path)
            if not obj_names:
                obj_names = set()
                self.libraries[lib_path] = obj_names
            obj_names.add(obj_name)
    
    def read_clipboard(self, context):
        wm = context.window_manager
        
        json_data = json.loads(wm.clipboard)
        assert json_data["content"] == "Blender 3D-clipboard"
        
        self.data_type = json_data["type"]
        assert self.data_type in self.data_types
        
        self.matrix = Matrix(json_data["matrix"])
        assert len(self.matrix) == 4
        
        self.cursor = Vector(json_data.get("cursor", (0, 0, 0)))
        assert len(self.cursor) == 3
        
        self.view = Quaternion(json_data.get("view", Quaternion()))
        
        if self.data_type == 'OBJECT':
            self.read_clipboard_object(json_data, context)
        else:
            pass # TODO
    
    def add_pivot(self, p, active):
        p = p.to_3d()
        if self.pivot_count == 0:
            self.pivot_min = list(p)
            self.pivot_max = list(p)
        else:
            for i in range(3):
                self.pivot_min[i] = min(self.pivot_min[i], p[i])
                self.pivot_max[i] = max(self.pivot_max[i], p[i])
        self.pivot_average += p
        self.pivot_count += 1
        if active:
            self.pivot_active = p
    
    def process_object(self, context):
        if context.mode != 'OBJECT':
            self.report({'WARNING'},
                        "To paste objects, you must be in the Object mode")
            return {'CANCELLED'}
        
        wm = context.window_manager
        opts = wm.copy_paste_options
        
        scene = context.scene
        
        old_to_new = {}
        new_to_old = {}
        
        def add_obj(new_obj, obj_name, lib_path):
            scene.objects.link(new_obj)
            
            new_obj.select = True
            
            is_active = False
            
            if self.active_object_library is not None:
                if ((obj_name == self.active_object) and
                    (lib_path == self.active_object_library)):
                        scene.objects.active = new_obj
                        is_active = True
            
            self.add_pivot(new_obj.matrix_world.translation, is_active)
            
            old_to_new[obj_name] = new_obj
            new_to_old[new_obj] = obj_name
        
        load = bpy.data.libraries.load
        
        for lib_path, obj_names in self.libraries.items():
            if not lib_path:
                link = not opts.append
                for obj_name in obj_names:
                    try:
                        obj = scene.objects[obj_name]
                    except KeyError:
                        continue
                    new_obj = obj.copy()
                    if opts.append and obj.data:
                        new_obj.data = obj.data.copy()
                    add_obj(new_obj, obj_name, lib_path)
                continue
            
            if not os.path.isfile(lib_path):
                continue # report a warning?
            
            link = not (opts.append or is_clipboard_path(lib_path))
            
            obj_names = list(obj_names)
            
            with load(lib_path, link) as (data_from, data_to):
                data_to.objects = list(obj_names) # <-- ALWAYS COPY!
            
            for i, new_obj in enumerate(data_to.objects):
                if new_obj is not None:
                    add_obj(new_obj, obj_names[i], lib_path)
        
        scene.update()
        
        # Restore parent relations
        for obj, old_name in new_to_old.items():
            parent_info = self.parents.get(old_name, None)
            if parent_info:
                parent = old_to_new.get(parent_info[0])
                if parent:
                    obj.parent = parent
                    obj.parent_bone = parent_info[1]
        
        # In Object mode the coordsystem option is not used
        # (ambiguous and the same effects can be achieved
        # relatively easily)
    
    def execute(self, context):
        try:
            self.read_clipboard(context)
        except (TypeError, KeyError, ValueError, AssertionError):
            self.report({'WARNING'},
                        "Incompatible format of clipboard data")
            return {'CANCELLED'}
        
        wm = context.window_manager
        opts = wm.copy_paste_options
        
        pivot_mode = context.space_data.pivot_point
        self.pivot_count = 0
        self.pivot_min = None
        self.pivot_max = None
        self.pivot_average = Vector()
        self.pivot_active = None
        
        scene = context.scene
        
        bpy.ops.ed.undo_push(message="Paste")
        
        bpy.ops.object.select_all(action='DESELECT')
        
        if self.data_type == 'OBJECT':
            self.process_object(context)
        else:
            coordsystem = opts.actual_coordsystem(context)
            
            pass # TODO
        
        if self.pivot_count == 0:
            # No objects were added %)
            return {'CANCELLED'}
        
        pivot = (Vector(self.pivot_min) + Vector(self.pivot_max)) * 0.5
        if pivot_mode == 'ACTIVE_ELEMENT':
            if self.pivot_active:
                pivot = self.pivot_active
        elif pivot_mode in ('MEDIAN_POINT', 'INDIVIDUAL_ORIGINS'):
            pivot = self.pivot_average * (1.0 / self.pivot_count)
        elif pivot_mode == 'CURSOR':
            pivot = self.cursor
        
        if is_view3d(context):
            if opts.paste_at_cursor:
                v3d = context.space_data
                cursor = v3d.cursor_location
                bpy.ops.transform.translate(value=(cursor - pivot),
                                            proportional='DISABLED')
                pivot = cursor
            
            if opts.align_to_view:
                view = get_view_rotation(context)
                dq = view * self.view.inverted()
                axis, angle = dq.to_axis_angle()
                bpy.ops.transform.rotate('EXEC_SCREEN',
                                         value=(angle,), axis=axis,
                                         proportional='DISABLED')
            
            if opts.move_to_mouse:
                region = context.region
                rv3d = context.region_data
                coord = self.mouse_coord
                dest = region_2d_to_location_3d(region, rv3d, coord, pivot)
                bpy.ops.transform.translate(value=(dest - pivot),
                                            proportional='DISABLED')
        
        return bpy.ops.transform.transform('INVOKE_DEFAULT')
    
    def invoke(self, context, event):
        self.mouse_coord = Vector((event.mouse_region_x, event.mouse_region_y))
        return self.execute(context)

class OperatorCut(bpy.types.Operator):
    '''Cut objects/elements'''
    bl_idname = "view3d.cut"
    bl_label = "Cut objects/elements"
    
    @classmethod
    def poll(cls, context):
        return bpy.ops.view3d.copy.poll()
    
    def execute(self, context):
        bpy.ops.ed.undo_push(message="Cut")
        bpy.ops.view3d.copy(force_copy=True)
        
        if 'EDIT' in context.mode:
            obj = bpy.context.object
            
            # TODO
        else:
            for obj in list(context.selected_objects):
                context.scene.objects.unlink(obj)
                # Also: totally remove if they have zero users?
                if obj.users == 0:
                    bpy.data.objects.remove(obj)
        
        return {'FINISHED'}

def register():
    bpy.utils.register_class(CopyPasteOptions)
    
    bpy.utils.register_class(VIEW3D_PT_copy_paste)
    
    bpy.utils.register_class(OperatorCopy)
    bpy.utils.register_class(OperatorPaste)
    bpy.utils.register_class(OperatorCut)
    
    bpy.types.WindowManager.copy_paste_options = \
        bpy.props.PointerProperty(type=CopyPasteOptions)
    
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new('view3d.copy', 'C', 'PRESS', ctrl=True)
        kmi = km.keymap_items.new('view3d.paste', 'V', 'PRESS', ctrl=True)
        kmi = km.keymap_items.new('view3d.cut', 'X', 'PRESS', ctrl=True)

def unregister():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps['3D View']
        for kmi in km.keymap_items:
            if kmi.idname in ('view3d.copy', 'view3d.paste', 'view3d.cut'):
                km.keymap_items.remove(kmi)
    
    if hasattr(bpy.types.Scene, "copy_paste_options"):
        del bpy.types.Scene.copy_paste_options
    
    bpy.utils.unregister_class(OperatorCut)
    bpy.utils.unregister_class(OperatorPaste)
    bpy.utils.unregister_class(OperatorCopy)
    
    bpy.utils.unregister_class(VIEW3D_PT_copy_paste)
    
    bpy.utils.unregister_class(CopyPasteOptions)

if __name__ == "__main__":
    register()
