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


def doSpanRemoveAndInsert(lc_includedTransmissionLinesFC, lc_includedTransmissionLineGuides, lc_listOfSpans):
    try:
        # Delete and Insert features into 4 tables.
        fieldListSpans = ['SHAPE@', 'FromTower', 'ToTower', 'LineNumber', 'SagDistance', 'HorizontalTension', 'LineLength', 'WeightPerUnitLength']
        fieldListGuideLines = ['SHAPE@', 'FromTower', 'ToTower', 'LineNumber', 'FromX', 'FromY', 'FromZ', 'ToX', 'ToY', 'ToZ', 'SagDistance', 'WeightPerUnitLength']
        deleteFieldList = ["FromTower", "ToTower", "LineNumber"]

        newRow = utils.NewRow()
        newRow.setFieldNames(fieldListSpans)

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

            # Delete existing TransmissionLines.
            deleteCursor = arcpy.da.UpdateCursor(lc_includedTransmissionLinesFC, deleteFieldList, deleteWhereClause)
            for row in deleteCursor:
                deleteCursor.deleteRow()
            if deleteCursor:
                del deleteCursor

            # Delete existing LineGuides.
            deleteCursor = arcpy.da.UpdateCursor(lc_includedTransmissionLineGuides, deleteFieldList, deleteWhereClause)
            for row in deleteCursor:
                deleteCursor.deleteRow()
            if deleteCursor:
                del deleteCursor

            ####################################

            # Insert new transmisson line.
            cursorInsertLine = arcpy.da.InsertCursor(lc_includedTransmissionLinesFC, newRow.getFieldNamesList())
            lineShape = vg.funPolylineToArcpyPolyline([span.polyline])
            newRow.set('SHAPE@', lineShape)
            newRow.set('FromTower', span.fromTower)
            newRow.set('ToTower', span.toTower)
            newRow.set('LineNumber', span.lineNumber)
            # XX Added extra reporting fields here:
            newRow.set('SagDistance', span.sagDistance)
            newRow.set('HorizontalTension', span.horizontalTension)
            newRow.set('LineLength', span.lineLength)
            newRow.set('WeightPerUnitLength', span.weightPerUnitLength)

            cursorInsertLine.insertRow(newRow.getFieldValuesList())
            del cursorInsertLine

            # Insert new lineGuide.
            newRowGuideLines = utils.NewRow()

            fromX = span.fromPoint.x
            fromY = span.fromPoint.y
            fromZ = span.fromPoint.z

            toX = span.toPoint.x
            toY = span.toPoint.y
            toZ = span.toPoint.z

            newRowGuideLines.setFieldNames(fieldListGuideLines)
            cursorInsertLineGuide = arcpy.da.InsertCursor(lc_includedTransmissionLineGuides, newRowGuideLines.getFieldNamesList())
            polylineShape = vg.funPolylineToArcpyPolyline([span.lineGuide])
            newRowGuideLines.set('SHAPE@', polylineShape)
            newRowGuideLines.set('FromTower', fromTower)
            newRowGuideLines.set('ToTower', toTower)
            newRowGuideLines.set('LineNumber', lineNumber)
            newRowGuideLines.set('FromX', fromX)
            newRowGuideLines.set('FromY', fromY)
            newRowGuideLines.set('FromZ', fromZ)
            newRowGuideLines.set('ToX', toX)
            newRowGuideLines.set('ToY', toY)
            newRowGuideLines.set('ToZ', toZ)
            newRowGuideLines.set('SagDistance', span.sagDistance)
            newRowGuideLines.set('WeightPerUnitLength', span.weightPerUnitLength)
            cursorInsertLineGuide.insertRow(newRowGuideLines.getFieldValuesList())
            del cursorInsertLineGuide

    except arcpy.ExecuteError:
        # Get the tool error messages
        msgs = arcpy.GetMessages(2)
        arcpy.AddError(msgs)
    except Exception:
        e = sys.exc_info()[1]
        arcpy.AddMessage("Unhandled exception: " + str(e.args[0]))
    pass


def adjustSpans(lc_scratch_ws, lc_catenary, lc_guide_lines, lc_adjust_all, lc_debug, lc_use_in_memory):
    try:
        # First, find the from and to points, and line number for this guide line.
        fieldList = ["FromTower", "ToTower", "LineNumber", "FromX", "FromY", "FromZ", "ToX", "ToY", "ToZ", "SagDistance", "WeightPerUnitLength"]
        fieldAccess = utils.FieldAccess(fieldList)

        # lc_guide_lines can be a layer. There is only 1 feature (selected)
        cursor = arcpy.da.SearchCursor(lc_guide_lines, fieldList)
        # Process selected guidelines.
        # XX Pretend for now that only one guideline is selected.
        index = 0
        for row in cursor:
            # only one guideline is selected.
            if index == 0:
                fieldAccess.setRow(row)
                lineNumber = fieldAccess.getValue("LineNumber")
                fromTower = fieldAccess.getValue("FromTower")
                toTower = fieldAccess.getValue("ToTower")
                fromX = fieldAccess.getValue("FromX")
                fromY = fieldAccess.getValue("FromY")
                fromZ = fieldAccess.getValue("FromZ")
                toX = fieldAccess.getValue("ToX")
                toY = fieldAccess.getValue("ToY")
                toZ = fieldAccess.getValue("ToZ")
                sagDistance = fieldAccess.getValue("SagDistance")
                weightPerUnitLength = fieldAccess.getValue("WeightPerUnitLength")
                fromPointXYZ = vg.Point(fromX, fromY, fromZ)
                toPointXYZ = vg.Point(toX, toY, toZ)
                # Change to attachment point objects.
                fromPoint = create_3D_catenary.AttachmentPoint(fromPointXYZ, lineNumber, fromTower)
                toPoint = create_3D_catenary.AttachmentPoint(toPointXYZ, lineNumber, toTower)

                p("Initial sagDistance on feature:", sagDistance)

                # sag distance is None because we need to calculate it from the lineGuide
                # horizontal tension is not supplied.
                adjustedSpan = create_3D_catenary.makeSpan(fromPoint, toPoint, lc_guide_lines, weightPerUnitLength, None, None, None)
                newSpanDistance = adjustedSpan.sagDistance
                p("new sagDistance on feature:", newSpanDistance)

        if cursor:
            del cursor

        if lc_adjust_all:
            # We have already created the span with a sag distance.
            # For simplicity, we'll throw out that span object and make all six using that sag.
            adjustedSpans = []
            fieldList = ["FromTower", "ToTower", "LineNumber", "FromX", "FromY", "FromZ", "ToX", "ToY", "ToZ"]
            fieldAccess = utils.FieldAccess(fieldList)
            whereClause = "FromTower = " + str(fromTower) + " and ToTower = " + str(toTower)

            p("sagDistance for all lines", newSpanDistance)

            # search in full feature class, not just selection
            i = 0
            cursor = arcpy.da.SearchCursor(common_lib.get_full_path_from_layer(lc_guide_lines), fieldList, whereClause)
            for row in cursor:
                fieldAccess.setRow(row)
                lineNumber = fieldAccess.getValue("LineNumber")
                fromTower = fieldAccess.getValue("FromTower")
                toTower = fieldAccess.getValue("ToTower")
                fromX = fieldAccess.getValue("FromX")
                fromY = fieldAccess.getValue("FromY")
                fromZ = fieldAccess.getValue("FromZ")
                toX = fieldAccess.getValue("ToX")
                toY = fieldAccess.getValue("ToY")
                toZ = fieldAccess.getValue("ToZ")
                fromPointXYZ = vg.Point(fromX, fromY, fromZ)
                toPointXYZ = vg.Point(toX, toY, toZ)
                # Change to attachment point objects.
                fromPoint = create_3D_catenary.AttachmentPoint(fromPointXYZ, lineNumber, fromTower)
                toPoint = create_3D_catenary.AttachmentPoint(toPointXYZ, lineNumber, toTower)

                p("newSpanDistance in loop", newSpanDistance)
                adjustedSpan = create_3D_catenary.makeSpan(fromPoint, toPoint, common_lib.get_full_path_from_layer(lc_guide_lines), weightPerUnitLength, newSpanDistance, None)
                adjustedSpans.append(adjustedSpan)

                i+=1
                # arcpy.AddMessage(str(i))

            doSpanRemoveAndInsert(lc_catenary, common_lib.get_full_path_from_layer(lc_guide_lines), adjustedSpans)
        else:
            doSpanRemoveAndInsert(lc_catenary, common_lib.get_full_path_from_layer(lc_guide_lines), [adjustedSpan])

        if lc_use_in_memory:
            arcpy.Delete_management("in_memory")

        if lc_debug == 0:
            fcs = common_lib.listFcsInGDB(lc_scratch_ws)

            msg_prefix = "Deleting intermediate data..."

            msg_body = common_lib.create_msg_body(msg_prefix, 0, 0)
            common_lib.msg(msg_body)

            for fc in fcs:
                arcpy.Delete_management(fc)

        arcpy.ClearWorkspaceCache_management()

        return lc_catenary, common_lib.get_full_path_from_layer(lc_guide_lines)

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
    input_source2 = r'D:\Gert\Work\Esri\Solutions\Utilities\Electric\work2.1\Transmission_Lines\Testing.gdb\Catenary_3D_GuideLines_1'
    adjust_all = False

    home_directory = r'D:\Gert\Work\Esri\Solutions\Utilities\Electric\work2.2\Transmission_Lines'
    project_ws = home_directory + "\\\Transmission_Lines.gdb"
    debug = 1
    scratch_ws = common_lib.create_gdb(home_directory, "Intermediate.gdb")
    in_memory_switch = False

    catenary_full_path = common_lib.get_full_path_from_layer(input_source2)
    catenary_full_path = catenary_full_path.replace("_LineGuides_", "_")

    catenary, guide_lines  = adjustSpans(lc_scratch_ws=scratch_ws,
                             lc_catenary=catenary_full_path,
                             lc_guide_lines=input_source2,
                             lc_adjust_all=adjust_all,
                             lc_debug=debug,
                             lc_use_in_memory=False)
    pint("Done")

#    arcpy.SetParameter(1, output_lines)
    pass