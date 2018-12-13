# -------------------------------------------------------------------------------
# Name:        create_3D_catenary_tbx.py
# Purpose:     wrapper for create_3D_catenary.py
#
# Author:      Gert van Maren
#
# Created:     04/04/12/2018
# Copyright:   (c) Esri 2018
# updated:
# updated:
# updated:

# Required:
#

# -------------------------------------------------------------------------------

import os
import arcpy
import sys
import importlib
import create_3D_swaysurface
if 'create_3D_swaysurface' in sys.modules:
    importlib.reload(create_3D_swaysurface)
import common_lib
if 'common_lib' in sys.modules:
    importlib.reload(common_lib)  # force reload of the module
import time
from common_lib import create_msg_body, msg, trace


# debugging switches
debugging = 0
if debugging == 1:
    enableLogging = True
    DeleteIntermediateData = False
    verbose = 1
    in_memory_switch = False
else:
    enableLogging = False
    DeleteIntermediateData = True
    verbose = 0
    in_memory_switch = False


# constants
ERROR = "error"
TOOLNAME = "Adjust3DCatenary"
WARNING = "warning"

# error classes
class MoreThan1Selected(Exception):
    pass


class NoLayerFile(Exception):
    pass


class NoPointLayer(Exception):
    pass


class NoCatenaryLayer(Exception):
    pass


class NoCatenaryOutput(Exception):
    pass


class NoSwaySurfaceOutput(Exception):
    pass


class NoGuideLinesLayer(Exception):
    pass


class NoGuideLinesOutput(Exception):
    pass


class LicenseError3D(Exception):
    pass


class LicenseErrorSpatial(Exception):
    pass


class SchemaLock(Exception):
    pass


class NotSupported(Exception):
    pass


class FunctionError(Exception):

    """
    Raised when a function fails to run.
    """

    pass


# ----------------------------Main Function---------------------------- #

def main():
    try:
        # Get Attributes from User
        if debugging == 0:
            ## User input
            input_source = arcpy.GetParameter(0)
            angle = arcpy.GetParameterAsText(1)
            output_features = arcpy.GetParameterAsText(2)

            # script variables
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            home_directory = aprx.homeFolder
            layer_directory = home_directory + "\\layer_files"
            rule_directory = aprx.homeFolder + "\\rule_packages"
            log_directory = aprx.homeFolder + "\\Logs"
            project_ws = aprx.defaultGeodatabase

        else:
            # debug
            input_source = r'D:\Gert\Work\Esri\Solutions\Utilities\Electric\work2.2\Transmission_Lines\Testing.gdb\Cat_test_LineGuides_3D'
            angle = 45
            output_features = r'D:\Gert\Work\Esri\Solutions\Utilities\Electric\work2.2\Transmission_Lines\Testing.gdb\sway_surfaces'

            home_directory = r'D:\Gert\Work\Esri\Solutions\Utilities\Electric\work2.2\Transmission_Lines'
            layer_directory = home_directory + "\\layer_files"
            rule_directory = home_directory + "\\rule_packages"
            log_directory = home_directory + "\\Logs"
            project_ws = home_directory + "\\\Transmission_Lines.gdb"

        scratch_ws = common_lib.create_gdb(home_directory, "Intermediate.gdb")
        arcpy.env.workspace = scratch_ws
        arcpy.env.overwriteOutput = True

        start_time = time.clock()

        # check if input exists
        if arcpy.Exists(input_source):
            # make a copy to grab the selection
            input_source_copy = os.path.join(scratch_ws, "catenary_copy")
            if arcpy.Exists(input_source_copy):
                arcpy.Delete_management(input_source_copy)

            arcpy.CopyFeatures_management(input_source, input_source_copy)

            # check number of selected features
            num_features = int(arcpy.GetCount_management(input_source_copy).getOutput(0))

            if num_features == 1:
                arcpy.AddMessage("Creating sway surface for selected catenary: " + common_lib.get_name_from_feature_class(input_source))
            else:
                arcpy.AddMessage("Creating multiple sway surfaces for catenaries: " + common_lib.get_name_from_feature_class(input_source))

            sway_lines, sway_surfaces = create_3D_swaysurface.makeSwayLinesAndSurfaces(lc_scratch_ws=scratch_ws,
                                                                         lc_catenary=input_source_copy,
                                                                         lc_angle=int(angle),
                                                                         lc_output_features=output_features,
                                                                         lc_debug=verbose,
                                                                         lc_use_in_memory=False)
            end_time = time.clock()

            if sway_lines and sway_surfaces:
                if arcpy.Exists(sway_lines) and arcpy.Exists(sway_surfaces):

                    # create layer, set layer file
                    # apply transparency here // checking if symbology layer is present
                    z_unit = common_lib.get_z_unit(sway_surfaces, verbose)

                    if z_unit == "Feet":
                        swaysurfaceSymbologyLayer = layer_directory + "\\swaysurface3Dfeet_mp.lyrx"
                    else:
                        swaysurfaceSymbologyLayer = layer_directory + "\\swaysurface3Dmeter_mp.lyrx"

                    sway_layer = common_lib.get_name_from_feature_class(sway_surfaces)
                    arcpy.MakeFeatureLayer_management(sway_surfaces, sway_layer)

                    sway_surfaces_mp = output_features + "_3D"

                    if arcpy.Exists(sway_surfaces_mp):
                        arcpy.Delete_management(sway_surfaces_mp)

                    arcpy.Layer3DToFeatureClass_3d(sway_layer, sway_surfaces_mp, "LineNumber")

                    output_layer3 = common_lib.get_name_from_feature_class(sway_surfaces_mp)
                    arcpy.MakeFeatureLayer_management(sway_surfaces_mp, output_layer3)

                    if arcpy.Exists(swaysurfaceSymbologyLayer):
                        arcpy.ApplySymbologyFromLayer_management(output_layer3, swaysurfaceSymbologyLayer)
                    else:
                        msg_body = create_msg_body(
                            "Can't find" + swaysurfaceSymbologyLayer + " in " + layer_directory, 0, 0)
                        msg(msg_body, WARNING)

                    if output_layer3:
                        if z_unit == "Feet":
                            arcpy.SetParameter(3, output_layer3)
                        else:
                            arcpy.SetParameter(4, output_layer3)

                            msg_body = create_msg_body("Adding sway surface layer: " + common_lib.get_name_from_feature_class(output_features) + " TO toc.", 0, 0)
                            msg(msg_body)
                    else:
                        raise NoSwaySurfaceOutput
                else:
                    end_time = time.clock()
                    msg_body = create_msg_body("No sway lines or surfaces created. Exiting...", start_time,
                                               end_time)
                    msg(msg_body, WARNING)
            else:
                end_time = time.clock()
                msg_body = create_msg_body("No sway lines or surfaces created. Exiting...", start_time,
                                           end_time)
                msg(msg_body, WARNING)

            arcpy.ClearWorkspaceCache_management()

            if DeleteIntermediateData:
                fcs = common_lib.listFcsInGDB(scratch_ws)

                msg_prefix = "Deleting intermediate data..."

                msg_body = common_lib.create_msg_body(msg_prefix, 0, 0)
                common_lib.msg(msg_body)

                for fc in fcs:
                    arcpy.Delete_management(fc)

            # end main code

    except LicenseError3D:
        print("3D Analyst license is unavailable")
        arcpy.AddError("3D Analyst license is unavailable")

    except NoPointLayer:
        print("Can't find attachment points layer. Exiting...")
        arcpy.AddError("Can't find attachment points layer. Exiting...")

    except NoPointLayer:
        print("None or more than 1 guide line selected. Please select only 1 guide line. Exiting...")
        arcpy.AddError("None or more than 1 guide line selected. Please select only 1 guide line. Exiting...")

    except NoCatenaryLayer:
        print("Can't find Catenary layer. Exiting...")
        arcpy.AddError("Can't find Catenary layer. Exiting...")

    except NoCatenaryOutput:
        print("Can't create Catenary output. Exiting...")
        arcpy.AddError("Can't create Catenary output. Exiting...")

    except NoSwaySurfaceOutput:
        print("Can't find SwaySurface output. Exiting...")
        arcpy.AddError("Can't find SwaySurface. Exiting...")

    except NoGuideLinesLayer:
        print("Can't find GuideLines output. Exiting...")
        arcpy.AddError("Can't find GuideLines. Exiting...")

    except MoreThan1Selected:
        print("More than 1 line selected. Please select 1 guide line only. Exiting...")
        arcpy.AddError("More than 1 line selected. Please select 1 guide line only. Exiting...")

    except NoGuideLinesOutput:
        print("Can't create GuideLines output. Exiting...")
        arcpy.AddError("Can't create GuideLines. Exiting...")

    except arcpy.ExecuteError:
        line, filename, synerror = trace()
        msg("Error on %s" % line, ERROR)
        msg("Error in file name:  %s" % filename, ERROR)
        msg("With error message:  %s" % synerror, ERROR)
        msg("ArcPy Error Message:  %s" % arcpy.GetMessages(2), ERROR)

    except FunctionError as f_e:
        messages = f_e.args[0]
        msg("Error in function:  %s" % messages["function"], ERROR)
        msg("Error on %s" % messages["line"], ERROR)
        msg("Error in file name:  %s" % messages["filename"], ERROR)
        msg("With error message:  %s" % messages["synerror"], ERROR)
        msg("ArcPy Error Message:  %s" % messages["arc"], ERROR)

    except:
        line, filename, synerror = trace()
        msg("Error on %s" % line, ERROR)
        msg("Error in file name:  %s" % filename, ERROR)
        msg("with error message:  %s" % synerror, ERROR)

    finally:
        arcpy.CheckInExtension("3D")

if __name__ == '__main__':

    main()
