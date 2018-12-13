"""
@author: cwilkins@esri.com
"""

import os
import arcpy
import sys
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
    importlib.reload(common_lib)  # force reload of the module

from common_lib import create_msg_body, msg, trace

############################################################################################### Chris continues...................

###################################
# debugging and notifications


# Feedback functions (print to GP tool output):

def pint(text):
    arcpy.AddMessage(text)

def p(label, value):
    if value is None:
        arcpy.AddMessage(label + " is None")
    else:
        arcpy.AddMessage(label + " " + str(value))

###############################################################################################
###############################################################################################
###############################################################################################
###############################################################################################
###############################################################################################
###############################################################################################
###############################################################################################
###############################################################################################

def makeSurfacePanels(span):
    surfacePanels = []
    swaysLines = span.swayLines
    swayLineCount = len(swaysLines)
    for swayIndex in range(0, swayLineCount - 1):
        thisSway = swaysLines[swayIndex]
        nextSway = swaysLines[swayIndex + 1]
        thisSwayNodes = thisSway.nodes
        nextSwayNodes = nextSway.nodes

        nodeCount = len(thisSwayNodes)
        lastNextNodeIndex = nodeCount - 2
        for nodeIndex in range(0, nodeCount - 1):
            thisSway_thisNode = thisSwayNodes[nodeIndex]
            thisSway_nextNode = thisSwayNodes[nodeIndex + 1]
            nextSway_thisNode = nextSwayNodes[nodeIndex]
            nextSway_nextNode = nextSwayNodes[nodeIndex + 1]
            if nodeIndex == 0:
                n0 = thisSway_thisNode
                # no n1 as this is triangle.
                n2 = nextSway_nextNode
                n3 = thisSway_nextNode
                panel = vg.Polygon([n0, n2, n3])
            elif nodeIndex == lastNextNodeIndex:
                n0 = thisSway_thisNode
                n1 = nextSway_thisNode
                n2 = nextSway_nextNode
                # no n3 as this is triangle.
                panel = vg.Polygon([n0, n1, n2])
            else:
                n0 = thisSway_thisNode
                n1 = nextSway_thisNode
                n2 = nextSway_nextNode
                n3 = thisSway_nextNode
                panel = vg.Polygon([n0, n1, n2, n3])

            surfacePanels.append(panel)
        # END FOR nodeIndex
    # END FOR swayIndex
    span.surfacePanels = surfacePanels
    pass


def makeSways(span, max_angle):

    total_range = 2*max_angle
    angles = []

    if max_angle <= 45:
        nr_steps = 6
        step_size = int(total_range / nr_steps)
    else:
        step_size = 15

    if step_size > max_angle:
        step_size = max_angle

    for i in range(-max_angle, max_angle, step_size):
        angles.append(i)

    angles.append(max_angle)

    # Span was constructed in new 2D XZ plane, and we'll keep that convention here.
    # Some of this is redundant from makeSpan, but best option is make generic function in VG library
    # to rotate points/geometry around arbitrary 3D axis.
    spanVector3D = vg.getVectorFromTwoPoints(span.fromPoint, span.toPoint)
    spanVector2DNoZ = vg.Vector(spanVector3D.x, spanVector3D.y,0)
    spanLength2D = vg.magnitude(spanVector2DNoZ)
    spanVector3DNormalToSpanPlane = vg.crossProduct(spanVector3D, vg.Vector(0,0,1))
    spanVector3DNormalInSpanPlane = vg.crossProduct(spanVector3D, spanVector3DNormalToSpanPlane)
    attachmentPointHeightDifference = span.toPoint.z - span.fromPoint.z

    # Still using XZ for span plane.
    spanVector2DNoY = vg.Vector(spanLength2D, 0, attachmentPointHeightDifference)

    # Build point vectors.
    pointVectors = []
    spanPolyline = span.polyline
    points = spanPolyline.nodes
    firstPoint = points[0]
    for pointIndex in range(0, len(points)):
        thisPoint = points[pointIndex]
        vectPoint3D = vg.getVectorFromTwoPoints(firstPoint,thisPoint)
        vectPoint2DNoZ = vg.Vector(vectPoint3D.x, vectPoint3D.y,0)
        vectZ = vg.Vector(0,0,vectPoint3D.z)
        vectPoint2DMag = vg.magnitude(vectPoint2DNoZ)
        xMag = vectPoint2DMag
        vectX = vg.Vector(xMag,0,0)
        thisVect = vg.addVectors(vectX, vectZ)
        pointVectors.append(thisVect)
    pointVectorsInSpanPlane = pointVectors

    ################
    swayLines = []
    for angle in angles:
        # These vectors are in 2D XZ plane.
        swayPoints = []
        lastPointIndex = len(pointVectorsInSpanPlane) - 1
        for pointIndex in range(0, lastPointIndex + 1):
            pointVector = pointVectorsInSpanPlane[pointIndex]
            if pointIndex == 0:
                thisPoint = span.fromPoint
            elif pointIndex == lastPointIndex:
                thisPoint = span.toPoint
            else:
                pointVectorLength = vg.magnitude(pointVector)
                h = pointVectorLength
                t = vg.scalarProjection(pointVector, spanVector2DNoY)
                r = math.sqrt(pow(h,2) - pow(t,2))
                alpha = 90 - angle
                alphaRadians = math.radians(alpha)
                u = r * math.cos(alphaRadians)
                v = r * math.sin(alphaRadians)

                tVector = vg.setVectorMagnitude(spanVector3D, t)
                uVector = vg.setVectorMagnitude(spanVector3DNormalToSpanPlane, u)
                vVector = vg.setVectorMagnitude(spanVector3DNormalInSpanPlane, v)
                uvVector = vg.addVectors(uVector,vVector)
                tuvVector = vg.addVectors(tVector, uvVector)
                thisPoint = vg.copyNode(span.fromPoint, tuvVector)
            swayPoints.append(thisPoint)
        # END FOR pointIndex.
        thisSwayLine = vg.Polyline(swayPoints)
        swayLines.append(thisSwayLine)
    # END FOR angles
    span.swayLines = swayLines
    ################
    pass


############################################################################################### Chris ends...................

def doInsert_SwayLinesSurfaces(lc_includedSwayLinesFC, includedSwaySurfacesFC,  lc_listOfSpans):
    try:

        # Delete and Insert features into 4 tables.
        fieldListBothLinesAndPoints = ['SHAPE@', 'FromTower', 'ToTower', 'LineNumber']
        deleteFieldList = ["FromTower", "ToTower", "LineNumber"]

        newRow = utils.NewRow()
        newRow.setFieldNames(fieldListBothLinesAndPoints)

        for span in lc_listOfSpans:
            fromTower = span.fromTower
            toTower = span.toTower
            lineNumber = span.lineNumber
            deleteWhereClause = "FromTower = " + str(fromTower) + " and ToTower = " + \
                                str(toTower) + " and LineNumber = " + str(lineNumber)
            # All new rows have these fields/values.
            newRow.set('FromTower', fromTower)
            newRow.set('ToTower', toTower)
            newRow.set('LineNumber', lineNumber)

            ####################################

            # Insert new sway lines.
            cursorInsertLine = arcpy.da.InsertCursor(lc_includedSwayLinesFC, newRow.getFieldNamesList())
            for swayLine in span.swayLines:
                lineShape = vg.funPolylineToArcpyPolyline([swayLine])
                newRow.set('SHAPE@', lineShape)
                cursorInsertLine.insertRow(newRow.getFieldValuesList())

            del cursorInsertLine

            # Insert new sway surface panels.
            cursorInsertPolygon = arcpy.da.InsertCursor(includedSwaySurfacesFC, newRow.getFieldNamesList())
            for panel in span.surfacePanels:
                polygonShape = vg.funPolygonToArcpyPolygon([panel])
                newRow.set('SHAPE@', polygonShape)
                cursorInsertPolygon.insertRow(newRow.getFieldValuesList())
            del cursorInsertPolygon

    except arcpy.ExecuteError:
        # Get the tool error messages
        msgs = arcpy.GetMessages(2)
        arcpy.AddError(msgs)
    except Exception:
        e = sys.exc_info()[1]
        arcpy.AddMessage("Unhandled exception: " + str(e.args[0]))
    pass


def makeSwayLinesAndSurfaces(lc_scratch_ws, lc_catenary, lc_angle, lc_output_features, lc_debug, lc_use_in_memory):
    try:
        includedSwayLinesFC = None
        includedSwaySurfacesFC = None
        sr = arcpy.Describe(lc_catenary).spatialReference

        geometry_type = "POLYLINE"
        has_m = "DISABLED"
        has_z = "ENABLED"
        from_tower_field = "FromTower"
        to_tower_field = "ToTower"
        tower_field = "Tower"
        line_number_field = "LineNumber"
        count_field = "COUNT"

        swaylines = "SwayLines"
        swaysurfaces = "SwaySurfaces"
        in_memory = "in_memory"

        spatial_reference = arcpy.Describe(lc_catenary).spatialReference

        includedSwayLinesFC = lc_output_features + "_swaylines"

        includedSwayLinesFC_dirname = os.path.dirname(includedSwayLinesFC)
        includedSwayLinesFC_basename = os.path.basename(includedSwayLinesFC)

        if arcpy.Exists(includedSwayLinesFC):
            arcpy.Delete_management(includedSwayLinesFC)

        arcpy.CreateFeatureclass_management(includedSwayLinesFC_dirname, includedSwayLinesFC_basename, geometry_type, "", has_m, has_z,
                                                    spatial_reference)

        common_lib.delete_add_field(includedSwayLinesFC, from_tower_field, "LONG")
        common_lib.delete_add_field(includedSwayLinesFC, to_tower_field, "LONG")
        common_lib.delete_add_field(includedSwayLinesFC, line_number_field, "LONG")
        common_lib.delete_add_field(includedSwayLinesFC, count_field, "LONG")

        geometry_type = "POLYGON"

        includedSwaySurfacesFC= os.path.join(lc_scratch_ws, "temp_sway_surfaces")

        includedSwaySurfacesFC_dirname = os.path.dirname(includedSwaySurfacesFC)
        includedSwaySurfacesFC_basename = os.path.basename(includedSwaySurfacesFC)

        if arcpy.Exists(includedSwaySurfacesFC):
            arcpy.Delete_management(includedSwaySurfacesFC)

        arcpy.CreateFeatureclass_management(includedSwaySurfacesFC_dirname, includedSwaySurfacesFC_basename, geometry_type, "", has_m, has_z,
                                                spatial_reference)

        common_lib.delete_add_field(includedSwaySurfacesFC, from_tower_field, "LONG")
        common_lib.delete_add_field(includedSwaySurfacesFC, to_tower_field, "LONG")
        common_lib.delete_add_field(includedSwaySurfacesFC, line_number_field, "LONG")
        common_lib.delete_add_field(includedSwaySurfacesFC, count_field, "LONG")

        arcpy.AddMessage("Creating sway surfaces...")

        # cycle through catenaries
        with arcpy.da.SearchCursor(lc_catenary, ['SHAPE@', 'FromTower', 'ToTower', 'LineNumber']) as cursor:
            for row in cursor:
                polyline = row[0]
                fromPoint = None
                toPoint = None

                # get start and end points from line, we assume 1 part
                for part in polyline:
                    for pnt in part:
                        if pnt:
                            ptGeom = arcpy.PointGeometry(pnt, sr)
                            line_length = polyline.length
                            chainage = polyline.measureOnLine(ptGeom)

                            if chainage == 0:  # start point
                                point = vg.Point(pnt.X, pnt.Y, pnt.Z)
                                fromPoint = create_3D_catenary.AttachmentPoint(point, row[3], row[1])

                            elif chainage - line_length == 0:  # end point
                                point = vg.Point(pnt.X, pnt.Y, pnt.Z)
                                toPoint = create_3D_catenary.AttachmentPoint(point, row[3], row[2])
                            else:  # in between points
                                continue
                # fill span object
                if fromPoint and toPoint:
                    span = create_3D_catenary.Span(fromPoint, toPoint)
                    catenary_line = vg.arcpyPolylineToVGPolyline(polyline)
                    span.polyline = catenary_line

                    makeSways(span, lc_angle)
                    makeSurfacePanels(span)

                    doInsert_SwayLinesSurfaces(includedSwayLinesFC, includedSwaySurfacesFC, [span])

                else:
                    arcpy.AddError("Error finding start and end points for catenary")

        if lc_use_in_memory:
            arcpy.Delete_management("in_memory")

        arcpy.ClearWorkspaceCache_management()

        return includedSwayLinesFC, includedSwaySurfacesFC

    except arcpy.ExecuteError:
        # Get the tool error messages
        msgs = arcpy.GetMessages(2)
        arcpy.AddError(msgs)
    except Exception:
        e = sys.exc_info()[1]
        arcpy.AddMessage("Unhandled exception: " + str(e.args[0]))
    pass



############################################################################################### Chris ends...................

# for debug only!
if __name__ == "__main__":
    input_source1 = r'D:\Gert\Work\Esri\Solutions\Utilities\Electric\work2.2\Transmission_Lines\Testing.gdb\Catenary_new_3D'
    angle = 45

    home_directory = r'D:\Gert\Work\Esri\Solutions\Utilities\Electric\work2.2\Transmission_Lines'
    project_ws = home_directory + "\\\Transmission_Lines.gdb"
    home_directory = r'D:\Gert\Work\Esri\Solutions\Utilities\Electric\work2.2\Transmission_Lines'
    debug = 1
    scratch_ws = common_lib.create_gdb(home_directory, "Intermediate.gdb")
    in_memory_switch = False

    output_lines = makeSwayLinesAndSurfaces(lc_scratch_ws=scratch_ws,
                             lc_catenary=input_source1,
                             lc_angle=angle,
                             lc_debug=debug,
                             lc_use_in_memory=False)
    pint("Done")

#    arcpy.SetParameter(1, output_lines)
    pass