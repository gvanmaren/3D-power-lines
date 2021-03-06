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
import adjust_3D_catenary
if 'adjust_3D_catenary' in sys.modules:
    importlib.reload(adjust_3D_catenary)
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
            input_source2 = arcpy.GetParameter(0)
            adjust_all = arcpy.GetParameter(1)

            # script variables
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            home_directory = aprx.homeFolder
            layer_directory = home_directory + "\\layer_files"
            rule_directory = aprx.homeFolder + "\\rule_packages"
            log_directory = aprx.homeFolder + "\\Logs"
            project_ws = aprx.defaultGeodatabase

        else:
            # debug
            input_source2 = r'D:\Gert\Work\Esri\Solutions\Utilities\Electric\work2.2.3\Transmission_Lines\Testing.gdb\test_adjust_line_feet1'
            adjust_all = False

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
        if arcpy.Exists(input_source2):
            # find associated catenary
            catenary_full_path = common_lib.get_full_path_from_layer(input_source2)
            catenary_full_path = catenary_full_path.replace("_LineGuides_", "_")

            if arcpy.Exists(catenary_full_path):
                # make a copy to grab the selection
                arcpy.AddMessage("Adjusting catenary: " + catenary_full_path)
                arcpy.AddMessage("Adjusting with selection of guide lines: " + common_lib.get_name_from_feature_class(input_source2))

                input_source2_copy = os.path.join(scratch_ws, "guide_lines_copy")
                if arcpy.Exists(input_source2_copy):
                    arcpy.Delete_management(input_source2_copy)

                msg_body = create_msg_body("Making copy of " + common_lib.get_name_from_feature_class(input_source2) + " in " + scratch_ws, 0, 0)
                msg(msg_body)

                arcpy.CopyFeatures_management(input_source2, input_source2_copy)

                # check number of selected features
                num_features = int(arcpy.GetCount_management(input_source2_copy).getOutput(0))

                if num_features != 1:
                    raise MoreThan1Selected
                else:
                    catenary, guide_lines = adjust_3D_catenary.adjustSpans(lc_scratch_ws=scratch_ws,
                                                                         lc_catenary=catenary_full_path,
                                                                         lc_guide_lines=input_source2,
                                                                         lc_adjust_all=adjust_all,
                                                                         lc_debug=verbose,
                                                                         lc_use_in_memory=False)
                    end_time = time.clock()

                    if catenary and guide_lines:
                        if arcpy.Exists(catenary) and arcpy.Exists(guide_lines):

                            # create layer, set layer file
                            # apply transparency here // checking if symbology layer is present
                            z_unit = common_lib.get_z_unit(catenary, verbose)

                            if z_unit == "Feet":
                                catenarySymbologyLayer = layer_directory + "\\catenary3Dfeet.lyrx"
                            else:
                                catenarySymbologyLayer = layer_directory + "\\catenary3Dmeter.lyrx"

                            output_layer1 = common_lib.get_name_from_feature_class(catenary)
                            arcpy.MakeFeatureLayer_management(catenary, output_layer1)

                            if arcpy.Exists(catenarySymbologyLayer):
                                arcpy.ApplySymbologyFromLayer_management(output_layer1, catenarySymbologyLayer)
                            else:
                                msg_body = create_msg_body(
                                    "Can't find" + catenarySymbologyLayer + " in " + layer_directory, 0, 0)
                                msg(msg_body, WARNING)

                            if z_unit == "Feet":
                                guidelinesSymbologyLayer = layer_directory + "\\guidelines3Dfeet.lyrx"
                            else:
                                guidelinesSymbologyLayer = layer_directory + "\\guidelines3Dmeter.lyrx"

                            output_layer2 = common_lib.get_name_from_feature_class(guide_lines)

                            arcpy.MakeFeatureLayer_management(guide_lines, output_layer2)

                            if arcpy.Exists(guidelinesSymbologyLayer):
                                arcpy.ApplySymbologyFromLayer_management(output_layer2, guidelinesSymbologyLayer)
                            else:
                                msg_body = create_msg_body(
                                    "Can't find" + guidelinesSymbologyLayer + " in " + layer_directory, 0, 0)
                                msg(msg_body, WARNING)

                            if output_layer1:
                                if z_unit == "Feet":
                                    arcpy.SetParameter(2, output_layer1)
                                else:
                                    arcpy.SetParameter(3, output_layer1)
                            else:
                                raise NoCatenaryOutput

                            if output_layer2:
                                if z_unit == "Feet":
                                    arcpy.SetParameter(4, common_lib.get_full_path_from_layer(output_layer2))
                                else:
                                    arcpy.SetParameter(5, output_layer2)
                            else:
                                raise NoGuideLinesOutput

                            end_time = time.clock()
                            msg_body = create_msg_body("create_3D_catenary_tbx completed successfully.", start_time,
                                                       end_time)
                            msg(msg_body)
                        else:
                            end_time = time.clock()
                            msg_body = create_msg_body("No catenary or guide_lines created. Exiting...", start_time,
                                                       end_time)
                            msg(msg_body, WARNING)
                    else:
                        end_time = time.clock()
                        msg_body = create_msg_body("No catenary or guide_lines created. Exiting...", start_time,
                                                   end_time)
                        msg(msg_body, WARNING)

                    arcpy.ClearWorkspaceCache_management()

                    # end main code

                    msg(msg_body)
            else:
                NoCatenaryLayer
        else:
            raise NoGuideLinesLayer


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
