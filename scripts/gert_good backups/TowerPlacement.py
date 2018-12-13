"""
Created on Jun 7, 2017
@author: cwilkins@esri.com
"""


import arcpy
import sys
import time
import math
import importlib

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

###################################
# debugging and notifications

# For auditing results:
printAuditTrail = True
# For debugging:
debugMode = True
proxyForInfinity = 1000000000



# Feedback functions (print to GP tool output):

def pint(text):
    if debugMode is True:
        arcpy.AddMessage(text)

def p(label, text):
    if debugMode is True:
        if text is None:
            arcpy.AddMessage(label + " is None")
        else:
            arcpy.AddMessage(label + " " + str(text))


###########################################################
# Tool parameters, inputs, and outputs.


aprx = arcpy.mp.ArcGISProject("CURRENT")
gdb = aprx.defaultGeodatabase

home_directory = aprx.homeFolder
rule_directory = home_directory + "\\rule_packages"
scratch_ws = common_lib.create_gdb(home_directory, "Intermediate.gdb")
arcpy.env.workspace = scratch_ws
arcpy.env.overwriteOutput = True

# Note, These tower points should become polygons that can be rotated by user to set a direction attribute on. But not today.

inTowerPlacementLine = arcpy.GetParameterAsText(0)

outTowerPlacementPoints = gdb + "\\" + "TowerPlacementPoints" # Multipatch feature class to have tower models placed on input line.
outTowerModels = gdb + "\\" + "TowerModels"
outJunctionPointsIntoFFCER = gdb + "\\" + "JunctionPoints" # Point feature class
outJunctionPointsFromFFCER = gdb + "\\" + "JunctionPoints_Points" # Point feature class
outSpansIntoScript = gdb + "\\" + "Spans"
outSpansFromScript = gdb + "\\" + "Spans_3D"

exportPointsRPK = rule_directory + "\\" + "TransmissionTower_ExportPoints.rpk"
exportModelsRPK = rule_directory + "\\" + "TransmissionTower_ExportModel.rpk"

###############################################################################################
###############################################################################################
###############################################################################################
###############################################################################################
###############################################################################################
###############################################################################################
###############################################################################################
###############################################################################################


# XX redundant copy from other scripts.
class AttachmentPoint(object):
    def __init__(self, point, lineNumber, towerNumber):
        self.point = point
        self.x = point.x
        self.y = point.y
        self.z = point.z
        self.lineNumber = lineNumber
        self.towerNumber = towerNumber

    def __str__(self):
        return "AttachmentPoint: " + str(self.point) + ",  " + str(self.lineNumber) + ",  " + str(self.towerNumber)

# XX Tower Placement Line's init handles lots of setup of objects contained within.
class TowerPlacementLine(object):
    def __init__(self, polyline):
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

        # Find default tower directions.
        cardinalDirection = None
        for nodeIndex in range(0, towerCount):
            towerBasePoint = self.towerBasePoints[nodeIndex]
            if nodeIndex == 0:
                thisTowerBasePoint = self.towerBasePoints[0]
                nextTowerBasePoint = self.towerBasePoints[1]
                spanDirectionVector = vg.getVectorFromTwoPoints(thisTowerBasePoint.point, nextTowerBasePoint.point)
                cardinalDirection = vg.getCardinalDirectionFromVector2D(spanDirectionVector)

            elif nodeIndex == towerCount - 1:
                thisTowerBasePoint = self.towerBasePoints[nodeIndex]
                previousTowerBasePoint = self.towerBasePoints[nodeIndex - 1]
                spanDirectionVector = vg.getVectorFromTwoPoints(previousTowerBasePoint.point, thisTowerBasePoint.point)
                cardinalDirection = vg.getCardinalDirectionFromVector2D(spanDirectionVector)
            else:
                # This node is in between first and last, and must handle direction changes.
                previousTowerBasePoint = self.towerBasePoints[nodeIndex - 1]
                thisTowerBasePoint = self.towerBasePoints[nodeIndex]
                nextTowerBasePoint = self.towerBasePoints[nodeIndex + 1]
                spanDirectionPrevious = vg.getVectorFromTwoPoints(previousTowerBasePoint.point, thisTowerBasePoint.point)
                spanDirectionThis = vg.getVectorFromTwoPoints(thisTowerBasePoint.point, nextTowerBasePoint.point)
                spanDirectionBisector = vg.getBisectingVector2D(spanDirectionPrevious, spanDirectionThis)
                cardinalDirection = vg.getCardinalDirectionFromVector2D(spanDirectionBisector)


            towerBasePoint.cardinalDirection = cardinalDirection
        # End for node loop.
    pass



class TowerBasePoint(object):
    def __init__(self, point):
        self.point = point
        self.towerNumber = None
        self.cardinalDirection = None
        # Array of AttachmentPoints
        #self.attachmentPoints = []



def GERTInsertTowerBasePoints(towerBasePoints):
    #fieldList = ['SHAPE@']
    #newRow = utils.NewRow()
    #newRow.setFieldNames(fieldList)

    for index in range(0, len(towerBasePoints)):
        towerBasePoint = towerBasePoints[index]
        arcpyPoint = vg.funPointToArcpyPoint(towerBasePoint.point)
        newRow = utils.NewRow()
        newRow.set('SHAPE@', arcpyPoint)
        newRow.set('CardinalDirection', towerBasePoint.cardinalDirection)
        newRow.set('TowerNumber', towerBasePoint.towerNumber)

        ####################################
        # Insert
        cursorInsert = arcpy.da.InsertCursor(outTowerPlacementPoints, newRow.getFieldNamesList())
        cursorInsert.insertRow(newRow.getFieldValuesList())
        del cursorInsert
        pass







def makeTowersAndJunctions(inTowerPlacementLine, lc_output_features, lc_use_in_memory):

    try:
        geometry_type = "POINT"
        has_m = "DISABLED"
        has_z = "ENABLED"
        cardinal_direction_field = "CardinalDirection"
        tower_number_field = "TowerNumber"
        insulator_lenght_field = "InsulatorLength"
        point_height1_field = "PointHeight1"
        point_offset1_field = "PointOffset1"
        point_height2_field = "PointHeight2"
        point_offset2_field = "PointOffset2"
        point_height3_field = "PointHeight3"
        point_offset3_field = "PointOffset3"
        beam_color_field = "BeamColor"

        temp_field = "TEMPSag"
        fieldList = ["SHAPE@", temp_field]
        fieldAccess = utils.FieldAccess(fieldList)

        spatial_reference = arcpy.Describe(inTowerPlacementLine).spatialReference

        msg_body = create_msg_body("Preparing output feature classes...", 0, 0)
        msg(msg_body)

        if lc_use_in_memory:
            arcpy.AddMessage("Using in memory for processing")
            towerPlacementPoints = in_memory + "/" + tower_placement_points

            arcpy.CreateFeatureclass_management(in_memory, towerPlacementPoints, geometry_type, "", has_m, has_z, spatial_reference)
        else:
#            includedTransmissionLinesFC = os.path.join(lc_scratch_ws, transmission_line_name)

            # ??????????????????? what is the output
            towerPlacementPoints = inTowerPlacementLine + "_3D"

            towerPlacementPoints_dirname = os.path.dirname(inTowerPlacementLine)
            towerPlacementPoints_basename = os.path.basename(inTowerPlacementLine)

            if arcpy.Exists(towerPlacementPoints):
                arcpy.Delete_management(towerPlacementPoints)

            arcpy.CreateFeatureclass_management(towerPlacementPoints_dirname, towerPlacementPoints_basename, geometry_type, "", has_m, has_z,
                                                    spatial_reference)

        common_lib.delete_add_field(towerPlacementPoints, cardinal_direction_field, "DOUBLE")
        common_lib.delete_add_field(towerPlacementPoints, tower_number_field, "LONG")
        common_lib.delete_add_field(towerPlacementPoints, insulator_lenght_field, "DOUBLE")
        common_lib.delete_add_field(towerPlacementPoints, point_height1_field, "LONG")
        common_lib.delete_add_field(towerPlacementPoints, point_offset1_field, "DOUBLE")
        common_lib.delete_add_field(towerPlacementPoints, point_height2_field, "DOUBLE")
        common_lib.delete_add_field(towerPlacementPoints, point_offset2_field, "DOUBLE")
        common_lib.delete_add_field(towerPlacementPoints, point_height3_field, "DOUBLE")
        common_lib.delete_add_field(towerPlacementPoints, point_offset3_field, "DOUBLE")
        common_lib.delete_add_field(towerPlacementPoints, beam_color_field, "TEXT")

        arcpy.management.TruncateTable("TowerPlacementPoints")

        common_lib.delete_add_field(inTowerPlacementLine, temp_field, "DOUBLE")

        lineCursor = arcpy.da.SearchCursor(inTowerPlacementLine, fieldList)

        i = 0 # XX I am assuming at this point that only one tower line is selected, so remove i variable below when assumption is met.
        for row in lineCursor:
            if i == 0:
                fieldAccess.setRow(row)

                arcpyPolyline = fieldAccess.getValue("SHAPE@")
                #TEMPSag = fieldAccess.getValue("TEMPSag")
                vgPolyline = vg.arcpyPolylineToVGPolyline(arcpyPolyline)

                # get tower point objects here. Initializing TowerPlacementLine builds the TowerBasePoints.
                towerPlacementLine = TowerPlacementLine(vgPolyline)
                towerBasePoints = towerPlacementLine.towerBasePoints

                # put the tower base points into the scene.
                GERTInsertTowerBasePoints(towerBasePoints)
                pint("Inserted Tower base points")

                ##### FFCER tower models with Tower RPK.
                #####towerModels = makeTowerModels(towerBasePoints)
                '''
                if arcpy.Exists(exportPointsRPK):
                    arcpy.ddd.FeaturesFromCityEngineRules(outTowerPlacementPoints, exportPointsRPK, outJunctionPoints,"DROP_EXISTING_FIELDS", "INCLUDE_REPORTS", "FEATURE_PER_LEAF_SHAPE")
                #if arcpy.Exists(exportModelsRPK):
                #    arcpy.ddd.FeaturesFromCityEngineRules(outTowerPlacementPoints, exportModelsRPK, outTowerModels)#,
                                                          #"DROP_EXISTING_FIELDS", "INCLUDE_REPORTS",
                                                          #"FEATURE_PER_LEAF_SHAPE")
                '''

                pint("beforeFFCER")
                arcpy.ddd.FeaturesFromCityEngineRules(outTowerPlacementPoints,exportPointsRPK,outJunctionPointsIntoFFCER,"DROP_EXISTING_FIELDS","INCLUDE_REPORTS","FEATURE_PER_LEAF_SHAPE")

                pint("afterFFCER")
                pint("Made Junctions.")
                '''
                outJunctionPointsIntoFFCER = gdb + "\\" + "JunctionPoints" # Point feature class
                outJunctionPointsFromFFCER = gdb + "\\" + "JunctionPoints_Points" # Point feature class

                '''
                pint("beforeFFCERTowers")
                arcpy.ddd.FeaturesFromCityEngineRules(outTowerPlacementPoints, exportModelsRPK, outTowerModels,"INCLUDE_EXISTING_FIELDS", "EXCLUDE_REPORTS", "FEATURE_PER_SHAPE")
                pint("afterFFCERTowers")
                pint("Made towers.")

                pint("Making spans")


                create_3D_catenary.makeSpans(lc_scratch_ws=scratch_ws,
                    lc_inPoints = outJunctionPointsFromFFCER,
                    lc_testLineWeight = 1,
                    lc_output_features = outSpansIntoScript,
                    lc_debug = 0,
                    lc_use_in_memory = False)
                pint("Made Spans")

        # End single-polyline cursor.

    except arcpy.ExecuteError:
        # Get the tool error messages
        msgs = arcpy.GetMessages(2)
        arcpy.AddError(msgs)
    except Exception:
        e = sys.exc_info()[1]
        arcpy.AddMessage("Unhandled exception: " + str(e.args[0]))
    pass




if __name__ == '__main__':

    in_memory_switch = False

    initTime = time.time()
    arcpy.AddMessage("Tower placement started at "+ time.asctime( time.localtime(initTime)))
    makeTowersAndJunctions(inTowerPlacementLine, in_memory_switch)
    arcpy.SetParameter(1, outTowerPlacementPoints)
    arcpy.SetParameter(2, outJunctionPointsFromFFCER)
    arcpy.SetParameter(3, outTowerModels)
    arcpy.SetParameter(4, outSpansFromScript)
    arcpy.AddMessage("Tower placement completed in " + str(round(time.time() - initTime, 3)) + " seconds.")



########################################################################
########################################################################
########################################################################
########################################################################








