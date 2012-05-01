Cut/Copy/Paste
==============

This addon makes it possible to cut/copy/paste objects and elements across different layers, scenes and Blender files.

When enabled, it would add a Copy/Paste panel to the Tool Shelf, and register Ctrl+X, Ctrl+C, Ctrl+V shortcuts for 3D view.

Options:
* External: if enabled, Copy in Object mode would save current .blend file (so that it can be accessed from other instances of Blender).
* Append: if enabled, pasted objects would be appended (fully copied); otherwise, they would be linked (similarly to "Link from Library" and "Duplicate Linked").
* Paste at Cursor: if enabled, pasted selection's pivot would be aligned with the 3D Cursor; otherwise, the selection would be pasted in the same coordinates as the original data.
* Move to mouse: if enabled, pasted selection's pivot would be aligned to match mouse screen position.
* Align to view: if enabled, the pasted selection would be rotated to match the original orientation relative to the view.
* Coordinate System: depending on this setting, geometry/bones would be pasted either in the absolute coordinates, or relative to the active object/bone.

NOTE: currently cut/copy/paste operations are implemented only for objects.

Installing
----------

Hit `Ctrl+Alt+u` to load up the User Preferences (or `File` menu -> `Save User Settings`).
Click the `Install Addon...` button at the bottom, then navigate to your `space_view3d_cut_copy_paste.py` script.

Checking the little box on the right of the Addon entry in the list to enable it.
If, for some reason, you have a hard time finding it, you can search for `Cut/Copy/Paste`, or click on the `3D View` button on the left.

If you want to keep this addon available at all times, follow the above steps on a fresh `.blend` (one you `Ctrl+n`d), then hit `Ctrl+u` at this point. The next time you run Blender, you won't have to repeat the above.

Contact information
-------------------

Upload Tracker:
http://projects.blender.org/tracker/index.php?func=detail&aid=31214
