import os

import bpy
import mathutils
import bpy_extras.io_utils

from progress_report import ProgressReport, ProgressReportSubstep


def mesh_triangulate(mesh):
    import bmesh
    temp_mesh = bmesh.new()
    temp_mesh.from_mesh(mesh)
    bmesh.ops.triangulate(temp_mesh, faces=temp_mesh.faces)
    temp_mesh.to_mesh(mesh)
    temp_mesh.free()


def write_file(filepath, objects, scene,
               EXPORT_TRI=False,
               EXPORT_NORMALS=False,
               EXPORT_APPLY_MODIFIERS=True,
               EXPORT_APPLY_MODIFIERS_RENDER=False,
               EXPORT_GLOBAL_MATRIX=None,
               EXPORT_PATH_MODE='AUTO',
               progress=ProgressReport(),
              ):
    """
    Basic write function. The context and options must be already set
    This can be accessed externaly
    eg.
    write( 'c:\\test\\foobar.obj', Blender.Object.GetSelected() ) # Using default options.
    """
    if EXPORT_GLOBAL_MATRIX is None:
        EXPORT_GLOBAL_MATRIX = mathutils.Matrix()

    def veckey3d(vec):
        return round(vec.x, 4), round(vec.y, 4), round(vec.z, 4)

    with ProgressReportSubstep(
        progress,
        2,
        "Wiresterizer Export path: %r" % filepath,
        "Wiresterizer Export Finished"
        ) as subprogress1:

        with open(filepath, "w", encoding="utf8", newline="\n") as file_object:
            file_write = file_object.write

            # Write Header
            str_version = bpy.app.version_string
            str_filepath = os.path.basename(bpy.data.filepath)
            file_write('# Blender v%s Wiresterizer File: %r\n' % (str_version, str_filepath))
            file_write('# www.blender.org\n')

            # Initialize totals, these are updated each object
            totverts = totno = 1

            copy_set = set()

            # Get all meshes
            subprogress1.enter_substeps(len(objects))
            for _i, ob_main in enumerate(objects):
                # ignore dupli children
                if ob_main.parent and ob_main.parent.dupli_type in {'VERTS', 'FACES'}:
                    subprogress1.step("Ignoring %s, dupli child..." % ob_main.name)
                    continue

                collected_objects = [(ob_main, ob_main.matrix_world)]
                if ob_main.dupli_type != 'NONE':
                    print('creating dupli_list on', ob_main.name)
                    ob_main.dupli_list_create(scene)

                    collected_objects += [(dob.object, dob.matrix) for dob in ob_main.dupli_list]

                    print(ob_main.name, 'has', len(collected_objects) - 1, 'dupli children')

                subprogress1.enter_substeps(len(collected_objects))
                for obj, obj_mat in collected_objects:
                    with ProgressReportSubstep(subprogress1, 5) as subprogress2:
                        no_unique_count = 0

                        try:
                            convert_settings = 'PREVIEW'
                            if EXPORT_APPLY_MODIFIERS_RENDER:
                                convert_settings = 'RENDER'

                            mesh = obj.to_mesh(scene,
                                               EXPORT_APPLY_MODIFIERS,
                                               calc_tessface=False,
                                               settings=convert_settings
                                              )
                        except RuntimeError:
                            mesh = None

                        if mesh is None:
                            continue

                        # _must_ do this before applying transformation,
                        # else tessellation may differ
                        if EXPORT_TRI:
                            # _must_ do this first since it re-allocs arrays
                            mesh_triangulate(mesh)

                        mesh.transform(EXPORT_GLOBAL_MATRIX * obj_mat)
                        # If negative scaling, we have to invert the normals...
                        if obj_mat.determinant() < 0.0:
                            mesh.flip_normals()

                        me_verts = mesh.vertices[:]

                        # Make our own list so it can be sorted to reduce context switching
                        face_index_pairs = [(face, index) for
                                            index, face in enumerate(mesh.polygons)]
                        # faces = [ f for f in me.tessfaces ]

                        # Make sure there is something to write
                        if (len(face_index_pairs) + len(mesh.vertices)) <= 0:
                            # clean up
                            bpy.data.meshes.remove(mesh)
                            continue  # dont bother with this mesh.

                        if EXPORT_NORMALS and face_index_pairs:
                            mesh.calc_normals_split()
                            # No need to call me.free_normals_split later,
                            # as this mesh is deleted anyway!

                        loops = mesh.loops

                        subprogress2.step()

                        # Vert
                        for vert in me_verts:
                            file_write('v %.6f %.6f %.6f\n' % vert.co[:])

                        subprogress2.step()

                        # NORMAL, Smooth/Non smoothed.
                        if EXPORT_NORMALS:
                            no_key = no_val = None
                            normals_to_idx = {}
                            no_get = normals_to_idx.get
                            loops_to_normals = [0] * len(loops)
                            for face, _f_index in face_index_pairs:
                                for l_idx in face.loop_indices:
                                    no_key = veckey3d(loops[l_idx].normal)
                                    no_val = no_get(no_key)
                                    if no_val is None:
                                        no_val = normals_to_idx[no_key] = no_unique_count
                                        file_write('vn %.4f %.4f %.4f\n' % no_key)
                                        no_unique_count += 1
                                    loops_to_normals[l_idx] = no_val
                            del normals_to_idx, no_get, no_key, no_val
                        else:
                            loops_to_normals = []

                        subprogress2.step()

                        for face, _f_index in face_index_pairs:
                            f_v = [(vi, me_verts[v_idx], l_idx)
                                   for vi, (v_idx, l_idx) in
                                   enumerate(zip(face.vertices, face.loop_indices))]

                            file_write('f')

                            if EXPORT_NORMALS:
                                for _vi, vert, loop_idx in f_v:
                                    vert_idx = totverts + vert.index
                                    normal_idx = totno + loops_to_normals[loop_idx]
                                    file_write(" %d//%d" % (vert_idx, normal_idx))
                            else: # No Normals
                                for _vi, vert, _loop_idx in f_v:
                                    vert_idx = totverts + vert.index
                                    file_write(" %d" % (vert_idx))

                            file_write('\n')

                        subprogress2.step()

                        # Make the indices global rather then per mesh
                        totverts += len(me_verts)
                        totno += no_unique_count

                        # clean up
                        bpy.data.meshes.remove(mesh)

                if ob_main.dupli_type != 'NONE':
                    ob_main.dupli_list_clear()

                subprogress1.leave_substeps("Finished writing geometry of '%s'." % ob_main.name)
            subprogress1.leave_substeps()

        subprogress1.step("Finished exporting geometry")

        # copy all collected files.
        bpy_extras.io_utils.path_reference_copy(copy_set)


def _write(context, filepath,
           EXPORT_TRI,  # ok
           EXPORT_NORMALS,  # ok
           EXPORT_APPLY_MODIFIERS,  # ok
           EXPORT_APPLY_MODIFIERS_RENDER,  # ok
           EXPORT_SEL_ONLY,  # ok
           EXPORT_GLOBAL_MATRIX,
           EXPORT_PATH_MODE,  # Not used
          ):

    with ProgressReport(context.window_manager) as progress:
        base_name, ext = os.path.splitext(filepath)
        context_name = [base_name, '', '', ext]  # Base name, scene name, frame number, extension

        scene = context.scene

        # Exit edit mode before exporting, so current object states are exported properly.
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode='OBJECT')

        orig_frame = scene.frame_current

        scene_frames = [orig_frame]  # Dont export an animation.

        # Loop through all frames in the scene and export.
        progress.enter_substeps(len(scene_frames))
        for frame in scene_frames:
            scene.frame_set(frame, 0.0)
            if EXPORT_SEL_ONLY:
                objects = context.selected_objects
            else:
                objects = scene.objects

            full_path = ''.join(context_name)

            # erm... bit of a problem here, this can overwrite files when exporting frames.
            # not too bad.
            # EXPORT THE FILE.
            progress.enter_substeps(1)
            write_file(full_path, objects, scene,
                       EXPORT_TRI,
                       EXPORT_NORMALS,
                       EXPORT_APPLY_MODIFIERS,
                       EXPORT_APPLY_MODIFIERS_RENDER,
                       EXPORT_GLOBAL_MATRIX,
                       EXPORT_PATH_MODE,
                       progress,
                      )
            progress.leave_substeps()

        scene.frame_set(orig_frame, 0.0)
        progress.leave_substeps()


def save(context,
         filepath,
         *,
         use_triangles=False,
         use_normals=False,
         use_mesh_modifiers=True,
         use_mesh_modifiers_render=False,
         use_selection=True,
         global_matrix=None,
         path_mode='AUTO'
        ):

    _write(context, filepath,
           EXPORT_TRI=use_triangles,
           EXPORT_NORMALS=use_normals,
           EXPORT_APPLY_MODIFIERS=use_mesh_modifiers,
           EXPORT_APPLY_MODIFIERS_RENDER=use_mesh_modifiers_render,
           EXPORT_SEL_ONLY=use_selection,
           EXPORT_GLOBAL_MATRIX=global_matrix,
           EXPORT_PATH_MODE=path_mode,
          )

    return {'FINISHED'}
