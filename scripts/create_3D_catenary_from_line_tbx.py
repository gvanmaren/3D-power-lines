# -------------------------------------------------------------------------------
# Name:        create_3D_catenary_from_line_tbx.py
# Purpose:     wrapper for create_3D_catenary_from_line.py
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
import create_3D_catenary_from_line

if 'create_3D_catenary_from_line' in sys.modules:
    importlib.reload(create_3D_catenary_from_line)
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


def pint(text):
    arcpy.AddMessage(text)

def p(label, text):
    if text is None:
        arcpy.AddMessage(label + " is None")
    else:
        arcpy.AddMessage(label + " " + str(text))




# constants
CONDUCTORTABLE = "ConductorInfo"
CONDUCTORTABLENAME = "ConductorLUTable.xlsx"
CONDUCTORINSHEET = "ConductorLUTable$"
TOWERTABLE = "TowerInfo"
TOWERTABLENAME = "TowerLUTable.xlsx"
TOWERINSHEET = "TowerLUTable$"
TOOLNAME = "Create3DCatenaryFromLine"
WARNING = "warning"
ERROR = "error"

# error classes
class MoreThan1Selected(Exception):
    pass


class NoneSelected(Exception):
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
def unit_conv(from_unit, to_unit):
    try:
        metersPerFoot = 0.3048

        if from_unit == "Meters" and to_unit == "Feet":
            return metersPerFoot
        elif from_unit == "Feet" and to_unit == "Meters":
            return 1/metersPerFoot

    except arcpy.ExecuteWarning:
        print((arcpy.GetMessages(1)))
        arcpy.AddWarning(arcpy.GetMessages(1))

    except arcpy.ExecuteError:
        print((arcpy.GetMessages(2)))
        arcpy.AddError(arcpy.GetMessages(2))


def main():
    try:
        # Get Attributes from User
        if debugging == 0:
            ## User input
            input_features = arcpy.GetParameterAsText(0)
            voltage = arcpy.GetParameterAsText(1)
            do_sag_to_span = arcpy.GetParameter(2)
            conductor_name = arcpy.GetParameterAsText(3)
            horizontal_tension = arcpy.GetParameter(6)
            output_features = arcpy.GetParameterAsText(7)
            structure_type = arcpy.GetParameterAsText(12)
            circuits = arcpy.GetParameterAsText(13)
            alignment = arcpy.GetParameterAsText(14)
            insulator_hang_type = arcpy.GetParameterAsText(15)
            shield_wires = arcpy.GetParameterAsText(16)

            line_type = arcpy.GetParameterAsText(18)
            tower_material = arcpy.GetParameterAsText(19)

            # script variables
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            home_directory = aprx.homeFolder
            layer_directory = home_directory + "\\layer_files"
            rule_directory = aprx.homeFolder + "\\rule_packages"
            table_directory = home_directory + "\\tables"
            log_directory = aprx.homeFolder + "\\Logs"
            project_ws = aprx.defaultGeodatabase

        else:
            # debug
            input_features = r'D:\Gert\Work\Esri\Solutions\Utilities\Electric\work2.2.3\Transmission_Lines\Testing.gdb\test_line_feet1'
#            input_features = r'D:\Gert\Work\Esri\Solutions\Utilities\Electric\demo241018\Transmisionline_demo1\Testing.gdb\test_line_meters_transpower'
            voltage = "400kV"
            do_sag_to_span = True
            conductor_name = "Sample Conductor 400"
            line_type = "Transmission"
            horizontal_tension = 4500
            output_features = r'D:\Gert\Work\Esri\Solutions\Utilities\Electric\work2.2.3\Transmission_Lines\Testing.gdb\test_line_feet_3D'
            structure_type = "Lattice"
            circuits = 2
            alignment = "Horizontal"
            insulator_hang_type = "Single"
            shield_wires = 0
            tower_material = "Steel"

            home_directory = r'D:\Gert\Work\Esri\Solutions\Utilities\Electric\work2.2.3\Transmission_Lines'
            layer_directory = home_directory + "\\layer_files"
            rule_directory = home_directory + "\\rule_packages"
            table_directory = home_directory + "\\tables"
            log_directory = home_directory + "\\Logs"
            project_ws = home_directory + "\\\Transmission_Lines.gdb"

        scratch_ws = common_lib.create_gdb(home_directory, "Intermediate.gdb")
        arcpy.env.workspace = scratch_ws
        arcpy.env.overwriteOutput = True

        default_SagToSpanRatio = 0.035  # This number is used in the book. TODO make this user variable

        start_time = time.clock()

        # check if input exists
        if arcpy.Exists(input_features):
            # test input type
            # current support 3D line only. TODO 2D line, 2D/3D points

            # set units
            input_z_unit = common_lib.get_z_unit(input_features, verbose)

            desc = arcpy.Describe(input_features)
            if desc.shapeType in ["Polyline", "Line"]:
                zValues = arcpy.Describe(input_features).hasZ
                if zValues:
                    # make a copy to grab the selection
                    input_source_copy = os.path.join(scratch_ws, "line_copy")
                    if arcpy.Exists(input_source_copy):
                        arcpy.Delete_management(input_source_copy)

                    arcpy.CopyFeatures_management(input_features, input_source_copy)

                    # check number of selected features
                    num_features = int(arcpy.GetCount_management(input_source_copy).getOutput(0))

                    if num_features == 0:
                        raise NoneSelected
                    else:

                        # check if conductor table exists...
                        haveTables= False
                        haveTower = False
                        haveConductor = False

                        inTowerTable = os.path.join(table_directory, TOWERTABLENAME)
                        inConductorTable = os.path.join(table_directory, CONDUCTORTABLENAME)
                        if arcpy.Exists(inTowerTable) and arcpy.Exists(inConductorTable):
                            arcpy.AddMessage("Reading tower and conductor tables: " + inTowerTable+ ", " + inConductorTable + ".")
                            inTowerSpreadsheet = inTowerTable + "\\" + TOWERINSHEET
                            inConductorSpreadsheet = inConductorTable + "\\" + CONDUCTORINSHEET

                            # table fields for Tower LU table.
                            voltageField = "Voltage"
                            minVField = "MinVSeparation"
                            minHField = "MinHSeparation"
                            minimumGroundClearanceField = "MinimumGroundClearance"
                            beamColorField = "BeamColor"
                            tableUnitsField = "Units"

                            tower_field_list = [voltageField, minVField, minHField, minimumGroundClearanceField,
                                                beamColorField, tableUnitsField]
                            
                            # table fields for Conductor LU table.
                            nameField = "ConductorName"
                            weightField = "WeightPerUnitLength"
                            rbsField = "RBS"

                            conductor_field_list = [nameField, weightField, rbsField, voltageField]

                            # read tower table
                            code, tower_gdb_table = common_lib.import_table_with_required_fields(inTowerSpreadsheet,
                                                                                                project_ws,
                                                                                                TOWERTABLE,
                                                                                                tower_field_list,
                                                                                                verbose)

                            if code == 0:
                                haveTower = True
                            else:
                                msg_body = create_msg_body("Failed to import " + inTowerSpreadsheet + "!", 0, 0)
                                msg(msg_body, WARNING)
                                haveTables = False

                            # import conductor table
                            code, conductor_gdb_table = common_lib.import_table_with_required_fields(inConductorSpreadsheet,
                                                                                                project_ws,
                                                                                                CONDUCTORTABLE,
                                                                                                conductor_field_list,
                                                                                                verbose)

                            if code == 0:
                                haveConductor = True
                            else:
                                msg_body = create_msg_body("Failed to import " + inConductorSpreadsheet + "!", 0, 0)
                                msg(msg_body, WARNING)
                                haveTables = False

                            if haveTower and haveConductor:
                                haveTables = True
                                pass
                            else:
                                msg_body = create_msg_body("Failed to import necessary LUT tables!", 0, 0)
                                msg(msg_body, ERROR)
                                haveTables = False
                        else:
                            msg_body = create_msg_body("Can't find: " + inTowerTable + " and/or " + inConductorTable + "!", 0, 0)
                            msg(msg_body, WARNING)
                            haveTables = False

                        if haveTables:
                            tower_configuration = create_3D_catenary_from_line.TowerConfiguration()

                            # set parameters from UI
                            tower_configuration.line_type = line_type
                            tower_configuration.structure_type = structure_type
                            tower_configuration.circuits = int(circuits)
                            tower_configuration.alignment = alignment
                            tower_configuration.shield_wires = int(shield_wires)
                            tower_configuration.insulator_hang_type = insulator_hang_type
                            tower_configuration.tower_material = tower_material

                            msg_body = ("Retrieving values for " + voltage + " in " + TOWERTABLENAME)
                            msg(msg_body)

                            if do_sag_to_span == False:
                                msg_body = ("Retrieving values for " + conductor_name + " in " + CONDUCTORTABLENAME)
                                msg(msg_body)

                            expression = """{} = '{}'""".format(arcpy.AddFieldDelimiters(tower_gdb_table, tower_field_list[0]), voltage)

                            # read additional parameters from tower table
                            with arcpy.da.SearchCursor(tower_gdb_table, tower_field_list, expression) as s_cursor:
                                count = 0
                                for s_row in s_cursor:
                                    # read clearances and attachment height etc from TOWER table
                                    tower_configuration.voltage = "{0}".format(s_row[0])

                                    tower_configuration.conductor_vertical_clearance = float("{:.2f}".format(s_row[1]))
                                    tower_configuration.conductor_horizontal_clearance = float("{:.2f}".format(s_row[2]))
                                    tower_configuration.minimum_ground_clearance = float("{:.2f}".format(s_row[3]))
                                    tower_configuration.beam_color = "{0}".format(s_row[4])
                                    tower_configuration.units = "{0}".format(s_row[5])

                            if do_sag_to_span is False and len(conductor_name) > 0:
                                    # read additional parameters from conductor table
                                    expression = """{} = '{}'""".format(arcpy.AddFieldDelimiters(conductor_gdb_table, conductor_field_list[0]), conductor_name)

                                    with arcpy.da.SearchCursor(conductor_gdb_table, conductor_field_list, expression) as s_cursor:
                                        count = 0
                                        for s_row in s_cursor:
                                            # read clearances and attachment height etc from CONDUCTOR table
                                            line_weight = "{:.4f}".format(s_row[1])
                                    sag_to_span_ratio = None
                                    arcpy.AddMessage("Creating catenaries with a horizontal tension of: "
                                                    + str(horizontal_tension) + " pounds and " + str(line_weight) +
                                                    " pound weight per unit length.")
                            else:
                                if line_type == "Transmission":
                                    line_weight = 1.096
                                else:
                                    line_weight = 0.5
                                horizontal_tension = None
                                sag_to_span_ratio = default_SagToSpanRatio

                                arcpy.AddMessage("Creating catenaries with a sagToSpan ratio of: " + str(sag_to_span_ratio)
                                                 + " and " + str(line_weight) + " pound weight per unit length.")

                            fields_from_towerconfiguration = vars(tower_configuration).keys()

                            catenary, TowerModels, JunctionPoints, TowerPlacementPoints = create_3D_catenary_from_line.makeTowersAndJunctions(
                                                                                                            lc_scratch_ws=scratch_ws,
                                                                                                            lc_rule_dir=rule_directory,
                                                                                                            lc_input_features=input_features,
                                                                                                            lc_testLineWeight=float(line_weight),
                                                                                                            lc_sag_to_span_ratio=sag_to_span_ratio,
                                                                                                            lc_horizontal_tension=horizontal_tension,
                                                                                                            lc_tower_configuration=tower_configuration,
                                                                                                            lc_fields_towerconfig=fields_from_towerconfiguration,
                                                                                                            lc_output_features=output_features,
                                                                                                            lc_debug=verbose,
                                                                                                            lc_use_in_memory=in_memory_switch)

                            if catenary and TowerModels and JunctionPoints and TowerPlacementPoints:
                                if arcpy.Exists(catenary) and arcpy.Exists(TowerModels) and\
                                                arcpy.Exists(TowerPlacementPoints) and arcpy.Exists(JunctionPoints):

                                    arcpy.SetParameter(8, TowerPlacementPoints)
                                    arcpy.SetParameter(9, JunctionPoints)
                                    arcpy.SetParameter(10, TowerModels) # reordered these lines just for good chi.

                                    # create layer, set layer file
                                    # apply transparency here // checking if symbology layer is present
                                    z_unit = common_lib.get_z_unit(catenary, verbose)

                                    if z_unit == "Feet":
                                        if line_type == "Transmission":
                                            catenarySymbologyLayer = layer_directory + "\\transmission3Dfeet.lyrx"
                                        else:
                                            catenarySymbologyLayer = layer_directory + "\\distribution3Dfeet.lyrx"
                                    else:
                                        if line_type == "Distribution":
                                            catenarySymbologyLayer = layer_directory + "\\transmission3Dmeter.lyrx"
                                        else:
                                            catenarySymbologyLayer = layer_directory + "\\distribution3Dmeter.lyrx"

                                    output_layer4 = common_lib.get_name_from_feature_class(catenary)
                                    arcpy.MakeFeatureLayer_management(catenary, output_layer4)

                                    if arcpy.Exists(catenarySymbologyLayer):
                                        arcpy.ApplySymbologyFromLayer_management(output_layer4, catenarySymbologyLayer)
                                    else:
                                        msg_body = create_msg_body("Can't find" + catenarySymbologyLayer + " in " + layer_directory,
                                                                   0, 0)
                                        msg(msg_body, WARNING)

                                    if output_layer4:
                                        arcpy.SetParameter(11, output_layer4)
                                    else:
                                        raise NoCatenaryOutput
                                else:
                                    end_time = time.clock()
                                    msg_body = create_msg_body("Can't find 3D catenaries or towers. Exiting...", start_time,
                                                               end_time)
                                    msg(msg_body, WARNING)
                            else:
                                end_time = time.clock()
                                msg_body = create_msg_body("No 3D catenaries or towers created. Exiting...", start_time, end_time)
                                msg(msg_body, WARNING)
                else:
                    end_time = time.clock()
                    msg_body = create_msg_body("Input feature class: " + input_features + " does not have Z values. Exiting...", start_time, end_time)
                    msg(msg_body, WARNING)
            else:
                end_time = time.clock()
                msg_body = create_msg_body("Only input feature type: " + desc.shapeType + " supported currently. Exiting...", start_time, end_time)
                msg(msg_body, WARNING)


            arcpy.ClearWorkspaceCache_management()

            if DeleteIntermediateData:
                fcs = common_lib.listFcsInGDB(scratch_ws)

                msg_prefix = "Deleting intermediate data..."

                msg_body = common_lib.create_msg_body(msg_prefix, 0, 0)
                common_lib.msg(msg_body)

                for fc in fcs:
                    arcpy.Delete_management(fc)
        else:
            end_time = time.clock()
            msg_body = create_msg_body("Input: " + input_features + " not found. Exiting...", start_time, end_time)
            msg(msg_body, WARNING)

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

    except NoneSelected:
        print("No features found. Exiting...")
        arcpy.AddError("No features found. Exiting...")

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
