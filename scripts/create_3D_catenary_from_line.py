"""
Created on Jun 7, 2017
@author: cwilkins@esri.com
"""


import arcpy
import sys
import time
import math
import importlib
import os

import ToolsUtilities as utils
if 'ToolsUtilities' in sys.modules:
    importlib.reload(utils)

import VectorGeometry as vg
if 'VectorGeometry' in sys.modules:
    importlib.reload(vg)

import create_3D_catenary
if 'create_3D_catenary' in sys.modules:
    importlib.reload(create_3D_catenary)

import common_lib
if 'common_lib' in sys.modules:
    importlib.reload(common_lib)
from common_lib import create_msg_body, msg, trace

TOOLNAME = "Create3Dcatenaryfromline"

###################################
# debugging and notifications


class MultipartInputNotSupported(Exception): pass

# Feedback functions (print to GP tool output):

def pint(text):
    arcpy.AddMessage(text)

def p(label, text):
    if text is None:
        arcpy.AddMessage(label + " is None")
    else:
        arcpy.AddMessage(label + " " + str(text))


###########################################################
# Tool parameters, inputs, and outputs.
###############################################################################################


# Note: Tower Placement Line's init handles lots of setup of objects contained within.
class TowerPlacementLine(object):
    def __init__(self, polyline, towerConfiguration, sagToSpanRatio, horizontalTension, lineWeight, endPoints):
        # Gert, I think TowerConfiguration was made to hold all of the GP inputs and those go into
        # the TowerBasePoints feature layer, along with a few others, to drive the RPK.
        # I considered adding sagToSpanRatio, horizontalTension, lineWeight to that layer,
        # for reference when inspecting the tower base points, but that would require new fields
        # (and I don't know your code that well),
        # so I just sent them into this function as args, instead of adding them into
        # TowerConfiguration object, which is a good place to store them, with all of the other GP inputs.
        self.polyline = polyline
        self.nodes = self.polyline.nodes
        self.towerBasePoints = []

        towerCount = len(polyline.nodes)
        for nodeIndex in range(0, towerCount):
            node = self.nodes[nodeIndex]
            towerBasePoint = TowerBasePoint(node)
            # For 1-based tower indexing.
            towerIndex = nodeIndex + 1
            towerBasePoint.towerNumber = towerIndex


            self.towerBasePoints.append(towerBasePoint)

        # Find tower directions, and max sag allowed per tower based on adjacent spans.
        # Note: there is one less span than there are towers.
        cardinalDirection = None
        greaterOfAdjacentSpanMaximumSags = None

        endPointGertArgument = endPoints

        for nodeIndex in range(0, towerCount):
            towerBasePoint = self.towerBasePoints[nodeIndex]
            towerBasePoint.structure_type = towerConfiguration.structure_type
            towerBasePoint.endPointGertArgument = endPointGertArgument
            # Note: Using 3D length here with sagRatio, so that steep lines get similar sag to flat lines.

            if nodeIndex == 0:
                # The first node's direction is pointing to the second node.
                thisTowerBasePoint = self.towerBasePoints[0]
                nextTowerBasePoint = self.towerBasePoints[1]
                fromPoint = thisTowerBasePoint.point
                toPoint = nextTowerBasePoint.point

                spanDirectionVector = vg.getVectorFromTwoPoints(fromPoint, toPoint)
                cardinalDirection = vg.getCardinalDirectionFromVector2D(spanDirectionVector)
                #spanVector3D = vg.getVectorFromTwoPoints(fromPoint, toPoint)
                #spanLength3D = vg.magnitude(spanVector3D)

                # Find max sag.
                # to get max_sag, we need AttachmentPoint objects for the makeSpan() function.
                thisFakeAttachmentPoint = create_3D_catenary.AttachmentPoint(thisTowerBasePoint.point,0,0)
                nextFakeAttachmentPoint = create_3D_catenary.AttachmentPoint(nextTowerBasePoint.point,0,0)

                nextSpan = create_3D_catenary.makeSpan(thisFakeAttachmentPoint, nextFakeAttachmentPoint, None, lineWeight, sagToSpanRatio, None, horizontalTension)
                greaterOfAdjacentSpanMaximumSags = nextSpan.sagDistance

                # Find endpoint type.
                if endPointGertArgument == "Both" or endPointGertArgument == "Start":
                    towerBasePoint.structure_type = "Substation"

            elif nodeIndex == towerCount - 1:
                # The last node takes its direction from previous node.
                thisTowerBasePoint = self.towerBasePoints[nodeIndex]
                previousTowerBasePoint = self.towerBasePoints[nodeIndex - 1]
                spanDirectionVector = vg.getVectorFromTwoPoints(previousTowerBasePoint.point, thisTowerBasePoint.point)
                cardinalDirection = vg.getCardinalDirectionFromVector2D(spanDirectionVector)

                # find max sag.
                thisFakeAttachmentPoint = create_3D_catenary.AttachmentPoint(thisTowerBasePoint.point,0,0)
                previousFakeAttachmentPoint = create_3D_catenary.AttachmentPoint(previousTowerBasePoint.point,0,0)

                previousSpan = create_3D_catenary.makeSpan(previousFakeAttachmentPoint, thisFakeAttachmentPoint, None, lineWeight, sagToSpanRatio, None, horizontalTension)
                greaterOfAdjacentSpanMaximumSags = previousSpan.sagDistance


                # Find endpoint type.
                if endPointGertArgument == "Both" or endPointGertArgument == "End":
                    towerBasePoint.structure_type = "Substation"

            else:
                # This node is in between first and last, and must handle direction changes.
                previousTowerBasePoint = self.towerBasePoints[nodeIndex - 1]
                thisTowerBasePoint = self.towerBasePoints[nodeIndex]
                nextTowerBasePoint = self.towerBasePoints[nodeIndex + 1]

                spanDirectionPrevious = vg.getVectorFromTwoPoints(previousTowerBasePoint.point, thisTowerBasePoint.point)
                spanDirectionThis = vg.getVectorFromTwoPoints(thisTowerBasePoint.point, nextTowerBasePoint.point)
                spanDirectionBisector = vg.getBisectingVector2D(spanDirectionPrevious, spanDirectionThis)
                cardinalDirection = vg.getCardinalDirectionFromVector2D(spanDirectionBisector)

                # find max sag.
                previousFakeAttachmentPoint = create_3D_catenary.AttachmentPoint(previousTowerBasePoint.point,0,0)
                thisFakeAttachmentPoint = create_3D_catenary.AttachmentPoint(thisTowerBasePoint.point,0,0)
                nextFakeAttachmentPoint = create_3D_catenary.AttachmentPoint(nextTowerBasePoint.point,0,0)

                previousSpan = create_3D_catenary.makeSpan(previousFakeAttachmentPoint, thisFakeAttachmentPoint, None, lineWeight, sagToSpanRatio, None, horizontalTension)
                nextSpan = create_3D_catenary.makeSpan(thisFakeAttachmentPoint, nextFakeAttachmentPoint, None, lineWeight, sagToSpanRatio, None, horizontalTension)

                greaterOfAdjacentSpanMaximumSags = greaterOf(previousSpan.sagDistance, nextSpan.sagDistance)

                # XX how could it have worked without the line below?
                towerBasePoint.structure_type = towerConfiguration.structure_type

            # Fields set for each tower.
            towerBasePoint.cardinalDirection = cardinalDirection
            towerBasePoint.maximum_sag_allowance = greaterOfAdjacentSpanMaximumSags
            # start and end structures are also set for each base point. That is done in above code.
        # End for node loop.
    pass

def greaterOf(value1, value2):
    if value1 > value2: return value1
    else: return value2

# This is used so that the signature of makeTowersAndJunctions won't have to change if schema changes.
class TowerConfiguration(object):
    def __init__(self):
        self.line_type = None
        self.structure_type = None #Gert, same message as below, to deal with Substation structure type.
        self.voltage = None
        self.circuits = None
        self.alignment = None
        self.conductor_vertical_clearance = None
        self.conductor_horizontal_clearance = None
        self.minimum_ground_clearance = None
        self.maximum_sag_allowance = None # Gert, CW moved this to TowerBasePoint object, but left it in this object
        # because I'm not wanting to mess with the feature class creation code.
        self.shield_wires = None
        self.insulator_hang_type = None
        self.beam_color = None # not TODO CW: nothing: leave for now
        self.units = None
        self.tower_material = None

class TowerBasePoint(object):
    def __init__(self, point):
        # These are fields that can change per tower.
        self.point = point
        self.cardinalDirection = None
        self.towerNumber = None
        self.maximum_sag_allowance = None #Gert, I added this.
        self.structure_type = None #Gert, I added this.

def InsertTowerBasePoints(towerBasePoints, tower_configuration, lc_tower_placement_points, lc_fields):
    for index in range(0, len(towerBasePoints)):
        towerBasePoint = towerBasePoints[index]
        arcpyPoint = vg.funPointToArcpyPoint(towerBasePoint.point)
        newRow = utils.NewRow()

        newRow.set('SHAPE@', arcpyPoint)
        newRow.set('Cardinal_Direction', towerBasePoint.cardinalDirection)
        newRow.set('TowerNumber', towerBasePoint.towerNumber)
        towerConfigIndex = 2
        for k, v in vars(tower_configuration).items():
            newRow.set(lc_fields[towerConfigIndex], v)
            towerConfigIndex += 1
        # Gert I did this after that loop, because I needed to update the value of these keys maximum_sag_allowance, and structure_type
        # and those values are being set on tower base points now (not tower config), but lc_fields has those keys already.
        newRow.set('maximum_sag_allowance', towerBasePoint.maximum_sag_allowance)
        newRow.set('structure_type', towerBasePoint.structure_type)

        ####################################
        # Insert
        cursorInsert = arcpy.da.InsertCursor(lc_tower_placement_points, newRow.getFieldNamesList())
        cursorInsert.insertRow(newRow.getFieldValuesList())
        del cursorInsert
        pass


def makeTowersAndJunctions(lc_scratch_ws, lc_rule_dir, lc_input_features, lc_testLineWeight, lc_sag_to_span_ratio, lc_horizontal_tension,
                                    lc_tower_configuration, lc_ends, lc_output_features,
                                    lc_debug, lc_use_in_memory):

    try:
        # Making Tower configuration object to hold fields for TowerBasePoints layer.
        towerConfiguration = lc_tower_configuration

        geometry_type = "POINT"
        has_m = "DISABLED"
        has_z = "ENABLED"

        in_memory = "in_memory"
        tower_placement_points_name = "TowerLocations"
        out_tower_models_name = "TowerModels"
        junction_intoFFCER = "JunctionPoints"
        junction_points_name = "JunctionPoints"
        CE_additionP = "_Points"
        CE_additionMP = "_MPoints"
        CE_additionL = "_Lines"
        spans_name = "Spans"

        exportPointsRPK = lc_rule_dir + "\\" + "TransmissionTower_ExportPoints.rpk"
        exportModelsRPK = lc_rule_dir + "\\" + "TransmissionTower_ExportModel.rpk"

        spatial_reference = arcpy.Describe(lc_input_features).spatialReference

        # create empty feature class with required fields
        msg_body = create_msg_body("Preparing output feature classes...", 0, 0)
        msg(msg_body)

        # create / check out features classes
        # tower placement points
        outTowerPlacementPoints = lc_output_features + "_" + tower_placement_points_name

        if arcpy.Exists(outTowerPlacementPoints):
            arcpy.Delete_management(outTowerPlacementPoints)

        # tower models: multipatches generated from tower placement points
        outTowerModels = lc_output_features + "_" + out_tower_models_name

        if arcpy.Exists(outTowerModels):
            arcpy.Delete_management(outTowerModels)

        outJunctionPointsFromFFCER = lc_output_features + "_" + junction_points_name

        if arcpy.Exists(outJunctionPointsFromFFCER):
            arcpy.Delete_management(outJunctionPointsFromFFCER)

        # output spans
        outSpansIntoScript = lc_output_features + "_" + spans_name

        if arcpy.Exists(outSpansIntoScript):
            arcpy.Delete_management(outSpansIntoScript)

        # NOTE: these items are used to create attributes and values must correspond to
        # TowerConfiguration attributes. If this list changes you must update TowerConfiguration object class

        # Tower RPK Fields, in TowerBasePoints layer.
        tower_number_field = "TowerNumber"
        units_field = "Units"
        cardinal_direction_field = "Cardinal_Direction"
        line_type_field = "Line_Type"
        structure_type_field = "Structure_Type"
        voltage_field = "Voltage"
        circuits_field = "Circuits"
        alignment_field = "Alignment"
        conductor_vertical_clearance_field = "Conductor_Vertical_Clearance"
        conductor_horizontal_clearance_field = "Conductor_Horizontal_Clearance"
        minimum_ground_clearance_field = "Minimum_Ground_Clearance"
        maximum_sag_allowance_field = "Maximum_Sag_Allowance"
        shield_wires_field = "Shield_Wires"
        insulator_hang_type_field = "Insulator_Hang_Type"
        beam_color_field = "Beam_Color"
        tower_material = "DistPole_Material"

        tower_base_point_field_dict = {cardinal_direction_field:"DOUBLE",
                                            tower_number_field:"LONG",
                                            line_type_field:"TEXT",
                                            structure_type_field:"TEXT",
                                            voltage_field:"TEXT",
                                            circuits_field:"LONG",
                                            alignment_field:"TEXT",
                                            conductor_vertical_clearance_field:"FLOAT",
                                            conductor_horizontal_clearance_field:"FLOAT",
                                            minimum_ground_clearance_field:"FLOAT",
                                            maximum_sag_allowance_field:"FLOAT",
                                            shield_wires_field:"LONG",
                                            insulator_hang_type_field:"TEXT",
                                            beam_color_field:"TEXT",
                                            units_field:"TEXT",
                                            tower_material: "TEXT"
                                       }

        catenary = None
        fieldList = ["SHAPE@"]
        fieldAccess = utils.FieldAccess(fieldList)

        num_features = int(arcpy.GetCount_management(lc_input_features).getOutput(0))

        lineCursor = arcpy.da.SearchCursor(lc_input_features, fieldList)
        i = 1

        for row in lineCursor:
            if lc_use_in_memory:
                arcpy.AddMessage("Using in memory for processing")

                # junctions points needed for FFCER
                outJunctionPointsIntoFFCER = in_memory + "/" + junction_intoFFCER

            else:
                # junctions points needed for makeSpans: FFCER generates 3D points with _Points in name
                outJunctionPointsIntoFFCER = os.path.join(lc_scratch_ws, junction_intoFFCER)

            if arcpy.Exists(outJunctionPointsIntoFFCER):
                arcpy.Delete_management(outJunctionPointsIntoFFCER)

            # delete additional CE output
            if arcpy.Exists(outJunctionPointsIntoFFCER + CE_additionP):
                arcpy.Delete_management(outJunctionPointsIntoFFCER + CE_additionP)

            if arcpy.Exists(outJunctionPointsIntoFFCER + CE_additionMP):
                arcpy.Delete_management(outJunctionPointsIntoFFCER + CE_additionMP)

            if arcpy.Exists(outJunctionPointsIntoFFCER + CE_additionL):
                arcpy.Delete_management(outJunctionPointsIntoFFCER + CE_additionL)

                # create temporary per line feature classes
                # temp tower placement points
            if lc_use_in_memory:
                arcpy.AddMessage("Using in memory for processing")

                temp_outTowerPlacementPoints = in_memory + "/" + tower_placement_points_name + "_temp"

            else:
                temp_outTowerPlacementPoints = os.path.join(lc_scratch_ws, tower_placement_points_name + "_temp")

            # first time delete just to be sure
            if i == 1 and arcpy.Exists(temp_outTowerPlacementPoints):
                arcpy.Delete_management(temp_outTowerPlacementPoints)

            if arcpy.Exists(temp_outTowerPlacementPoints):
                arcpy.TruncateTable_management(temp_outTowerPlacementPoints)
            else:
                temp_outtowerPlacementPoints_dirname = os.path.dirname(temp_outTowerPlacementPoints)
                temp_outtowerPlacementPoints_basename = os.path.basename(temp_outTowerPlacementPoints)

                arcpy.CreateFeatureclass_management(temp_outtowerPlacementPoints_dirname,
                                                    temp_outtowerPlacementPoints_basename,
                                                    geometry_type, "", has_m, has_z,
                                                    spatial_reference)
                # add required fields for towerPlacementPoints
                arcpy.AddMessage("Adding required fields to tower placement points...")

                start_time = time.clock()

#                for k, v in tower_base_point_field_dict.items():
#                    common_lib.delete_add_field(temp_outTowerPlacementPoints, k, v)

                listoffields = []
                for k, v in tower_base_point_field_dict.items():
                    field = []
                    field.append(k)
                    field.append(v)
                    listoffields.append(field)

                arcpy.management.AddFields(temp_outTowerPlacementPoints, listoffields)

                end_time = time.clock()
                msg_body = create_msg_body("Time to create fields...", start_time,
                                           end_time)
                msg(msg_body)

            # temp tower models: multipatches generated from tower placement points
            if lc_use_in_memory:
                arcpy.AddMessage("Using in memory for processing")

                temp_outTowerModels = in_memory + "/" + out_tower_models_name + "_temp"
            else:
                temp_outTowerModels = os.path.join(lc_scratch_ws, out_tower_models_name + "_temp")

            if arcpy.Exists(temp_outTowerModels):
                arcpy.Delete_management(temp_outTowerModels)

            if lc_use_in_memory:
                arcpy.AddMessage("Using in memory for processing")

                temp_outJunctionPointsFromFFCER = in_memory + "/" + out_tower_models_name + "_temp"

            else:
                temp_outJunctionPointsFromFFCER = os.path.join(lc_scratch_ws, junction_points_name + "_temp")

            if arcpy.Exists(temp_outJunctionPointsFromFFCER):
                arcpy.Delete_management(temp_outJunctionPointsFromFFCER)

            # output temp spans
            if lc_use_in_memory:
                arcpy.AddMessage("Using in memory for processing")

                temp_outSpansIntoScript = in_memory + "/" + spans_name + "_temp"

            else:
                temp_outSpansIntoScript = os.path.join(lc_scratch_ws, spans_name + "_temp")

            if arcpy.Exists(temp_outSpansIntoScript):
                arcpy.Delete_management(temp_outSpansIntoScript)

            # multiple lines are now supported...
            if i >= 0:
                fieldAccess.setRow(row)

                arcpyPolyline = fieldAccess.getValue("SHAPE@")

                # read the line
                vgPolyline = vg.arcpyPolylineToVGPolyline(arcpyPolyline)
                if vgPolyline:
                    # get tower point objects here. Initializing TowerPlacementLine builds the TowerBasePoints.
                    # from towerConfiguration
                    pint("Preparing tower base points for feature: " + str(i) + " out of " + str(num_features) + ".")

                    towerPlacementLine = TowerPlacementLine(vgPolyline, towerConfiguration, lc_sag_to_span_ratio, lc_horizontal_tension, lc_testLineWeight, lc_ends)
                    towerBasePoints = towerPlacementLine.towerBasePoints
                    # put the tower base points into the scene.
                    InsertTowerBasePoints(towerBasePoints, towerConfiguration, temp_outTowerPlacementPoints, list(tower_base_point_field_dict.keys()))
                    arcpy.ddd.FeaturesFromCityEngineRules(temp_outTowerPlacementPoints, exportPointsRPK,
                                                          outJunctionPointsIntoFFCER, "DROP_EXISTING_FIELDS",
                                                          "INCLUDE_REPORTS", "FEATURE_PER_LEAF_SHAPE")

                    # TODO built in check when FFCER fails XX Gert

                    # copy _Points fc to input gdb
                    arcpy.CopyFeatures_management(outJunctionPointsIntoFFCER + CE_additionP, temp_outJunctionPointsFromFFCER)

                    arcpy.ddd.FeaturesFromCityEngineRules(temp_outTowerPlacementPoints, exportModelsRPK,
                                                          temp_outTowerModels, "INCLUDE_EXISTING_FIELDS",
                                                          "EXCLUDE_REPORTS", "FEATURE_PER_SHAPE")

                    pint("Making spans for feature: " + str(i) + " out of " + str(num_features) + ".")

                    catenary, guide_lines = create_3D_catenary.makeSpans(lc_scratch_ws=lc_scratch_ws,
                                                        lc_inPoints=temp_outJunctionPointsFromFFCER,
                                                        lc_testLineWeight=lc_testLineWeight,
                                                        lc_sag_to_span_ratio=lc_sag_to_span_ratio,
                                                        lc_horizontal_tension=lc_horizontal_tension,
                                                        lc_output_features=temp_outSpansIntoScript,
                                                        lc_debug=lc_debug,
                                                        lc_use_in_memory=False,
                                                        lc_cleanup=False,
                                                        lc_caller=TOOLNAME)

                    # append features to output feature classes

                    # catenary, outTowerModels, outJunctionPointsFromFFCER, outTowerPlacementPoints
                    schemaType = "NO_TEST"
                    if arcpy.Exists(outSpansIntoScript):
                        arcpy.Append_management(catenary, outSpansIntoScript, schemaType)
                    else:
                        arcpy.Copy_management(catenary, outSpansIntoScript)

                    pint("Made spans for feature: " + str(i) + " out of " + str(num_features) + ".")

                    if arcpy.Exists(outTowerModels):
                        arcpy.Append_management(temp_outTowerModels, outTowerModels, schemaType)
                    else:
                        arcpy.Copy_management(temp_outTowerModels, outTowerModels)

                    pint("Made towers for feature: " + str(i) + " out of " + str(num_features) + ".")

                    if arcpy.Exists(outJunctionPointsFromFFCER):
                        arcpy.Append_management(temp_outJunctionPointsFromFFCER, outJunctionPointsFromFFCER, schemaType)
                    else:
                        arcpy.Copy_management(temp_outJunctionPointsFromFFCER, outJunctionPointsFromFFCER)

                    pint("Made junctions for feature: " + str(i) + " out of " + str(num_features) + ".")

                    if arcpy.Exists(outTowerPlacementPoints):
                        arcpy.Append_management(temp_outTowerPlacementPoints, outTowerPlacementPoints, schemaType)
                    else:
                        arcpy.Copy_management(temp_outTowerPlacementPoints, outTowerPlacementPoints)
                else:
                    raise MultipartInputNotSupported

            i += 1

        return outSpansIntoScript, outTowerModels, outJunctionPointsFromFFCER, outTowerPlacementPoints

    except MultipartInputNotSupported:
        print("Multipart features are not supported. Exiting...")
        arcpy.AddError("Multipart features are not supported. Exiting...")

    except arcpy.ExecuteError:
        # Get the tool error messages
        msgs = arcpy.GetMessages(2)
        arcpy.AddError(msgs)
    except Exception:
        e = sys.exc_info()[1]
        arcpy.AddMessage("Unhandled exception: " + str(e.args[0]))
    pass


if __name__ == "__main__":
    input_source = r'D:\Gert\Work\Esri\Solutions\Utilities\Electric\work2.2.3\Transmission_Lines\Testing.gdb\test_line_feet'
    output_features = r'D:\Gert\Work\Esri\Solutions\Utilities\Electric\work2.2.3\Transmission_Lines\Testing.gdb\feet_model'
    home_directory = r'D:\Gert\Work\Esri\Solutions\Utilities\Electric\work2.2.3\Transmission_Lines'
    project_ws = home_directory + "\\\Transmission_Lines.gdb"
    home_directory = r'D:\Gert\Work\Esri\Solutions\Utilities\Electric\work2.2.3\Transmission_Lines'
    layer_directory = home_directory + "\\layer_files"
    rule_directory = home_directory + "\\rule_packages"

    line_weight = 1.096
    horizontal_tension = 4500
    line_type = "Transmission"
    structure_type = "Lattice"
    voltage = "66kV"
    # IEEE conductor_load = arcpy.GetParameterAsText(10)
    circuits = 2
    alignment = "Vertical"
    shield_wires = 1
    # IEEE ambient_temperature = arcpy.GetParameterAsText(14)

    debug = 1
    scratch_ws = common_lib.create_gdb(home_directory, "Intermediate.gdb")
    in_memory_switch = False

    tower_configuration = TowerConfiguration()
    tower_configuration.line_type = line_type
    tower_configuration.structure_type = structure_type
    tower_configuration.voltage = voltage
    tower_configuration.circuits = circuits
    tower_configuration.alignment = alignment
    tower_configuration.shield_wires = shield_wires


    initTime = time.time()
    arcpy.AddMessage("Tower placement started at " + time.asctime(time.localtime(initTime)))
    catenary, outTowerModels, outJunctionPointsFromFFCER, outTowerPlacementPoints = makeTowersAndJunctions(
                                                                            lc_scratch_ws=scratch_ws,
                                                                            lc_rule_dir=rule_directory,
                                                                            lc_input_features=input_source,
                                                                            lc_testLineWeight=float(line_weight),
                                                                            lc_sag_to_span_ratio=0.035,
                                                                            lc_horizontal_tension=float(horizontal_tension),
                                                                            lc_tower_configuration=tower_configuration,
                                                                            lc_output_features=output_features,
                                                                            lc_debug=debug,
                                                                            lc_use_in_memory=in_memory_switch)

    arcpy.AddMessage("Tower placement completed in " + str(round(time.time() - initTime, 3)) + " seconds.")



########################################################################
########################################################################
########################################################################
########################################################################








