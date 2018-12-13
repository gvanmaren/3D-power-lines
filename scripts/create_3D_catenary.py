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
import common_lib
if 'common_lib' in sys.modules:
    importlib.reload(common_lib)  # force reload of the module

from common_lib import create_msg_body, msg, trace

############################################################################################### Chris continues...................

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

class Span(object):
    def __init__(self, fromPoint, toPoint):
        # Shape of polyline feature (in VG module format).
        self.polyline = None
        # Attachment Points and line number are the primary key for the span features, at least for now.
        self.fromPoint = fromPoint
        self.toPoint = toPoint
        self.lineNumber = toPoint.lineNumber
        # Tower numbers come from AttachmentPoints.
        self.fromTower = fromPoint.towerNumber
        self.toTower = toPoint.towerNumber
        # This is the increment that sway lines and sway surfaces are gridded in the direction of the sway.
        self.swayIncrements = 10 # degrees
        # Storage of sway lines and surfaces, to be entered into their own feature classes.
        self.swayLines = []
        self.surfacePanels = []
        self.lineGuide = None
        # These are reports to be written to fields in Spans feature class.
        self.sagDistance = None
        self.horizontalTension = None
        self.lineLength = None
        self.weightPerUnitLength = None


'''
NOTE: Formulas used are from document epdf.tips_electric-power-generation-transmission-and-distrib.pdf,
except that one misprinted formula. We moved parenthesis to correct that.
'''

def makeSpan(fromPoint, toPoint, lc_includedTransmissionLineGuides, lc_testLineWeight, sagToSpanRatio, sagDistance, horizontalTension):
    try:
        span = Span(fromPoint, toPoint)
        # Define span shape here, then set polyline on Span object.
        spanVector3D = vg.getVectorFromTwoPoints(fromPoint, toPoint)
        spanLength3D = vg.magnitude(spanVector3D)
        spanVector2DNoZ = vg.Vector(spanVector3D.x, spanVector3D.y, 0)
        spanLength2D = vg.magnitude(spanVector2DNoZ)
        fromTower = fromPoint.towerNumber
        toTower = toPoint.towerNumber
        lineNumber = fromPoint.lineNumber
        attachmentPointHeightDifference = abs(toPoint.z - fromPoint.z)
        lineWeightPerUnitLength = lc_testLineWeight

        # NOTE: The logic below depends on which script calls the function.
        # When called from create_3D_catenary(this script), inside makeSpans() function,
        # new spans are created based on horizontal tension, and sagDistance is calculated.

        # When called from adjust_3D:
        # It is called once with sagDistance of None which triggers use of line guide.
        # Once sagDistance is known, if "adjust all" tool option is used, then sagDistance is used to
        # make the matching spans, so sagDistance is not None.

        w = lineWeightPerUnitLength
        H = None
        # When called from create_3D_catenary_from_line, GP tool might send sagToSpanRatio:
        if sagToSpanRatio is not None:
            D = sagToSpanRatio * spanLength2D

        # When called from create_3D_catenary_from_line, GP tool might send horizontal tension:
        elif horizontalTension is not None:
            # Using sag approximation until I find better formula.
            # XX This method doesn't work with the degree of accuracy needed, but is close enough and will be visually corrected.
            H = horizontalTension
            catenaryConstant = H/w
            sOver2 = spanLength3D/2
            inverseCatenaryConstant = w/H
            coshValue = math.cosh(sOver2 * inverseCatenaryConstant)
            coshValueMinusOne = coshValue - 1
            sagApproximation = catenaryConstant * coshValueMinusOne
            D = sagApproximation

        # When called from adjust_3D_catenary the first time sagDistance is None:
        elif sagDistance is None and lc_includedTransmissionLineGuides is not None:

            # Query LineGuides for line with matching from, to, and line.
            fieldListLineGuides = ["SHAPE@", "FromTower", "ToTower", "LineNumber"]
            fieldAccessLineGuides = utils.FieldAccess(fieldListLineGuides)
            whereClauseLineGuides = "FromTower = " + str(fromTower) + " and ToTower = " + str(
                toTower) + " and LineNumber = " + str(lineNumber)
            cursor = arcpy.da.SearchCursor(lc_includedTransmissionLineGuides, fieldListLineGuides, whereClauseLineGuides)

            msg_body = create_msg_body("Creating span for line number " + str(lineNumber) + " from tower " + str(
                                                                    fromTower) + " to tower " + str(toTower) + ".", 0, 0)
            msg(msg_body)

            # default lineGuideZ for when none exists. This ensures no square root of zero causes error.
            #  XX In what part? The calculation of D, I guess.
            #  XX This brings up a question... Will this entire function work if both points are at same z? That would be very unlikely.
            lineGuideZ = None
            if fromPoint.z > toPoint.z:
                defaultLineGuideZ = toPoint.z - 10
            else:
                defaultLineGuideZ = fromPoint.z - 10

            for row in cursor:
                fieldAccessLineGuides.setRow(row)
                lineGuideShape = fieldAccessLineGuides.getValue("SHAPE@")
                lineGuide = vg.arcpyPolylineToVGPolyline(lineGuideShape)
                lineGuideZ = lineGuide.nodes[0].z
            if cursor:
                del cursor

            # If no user line exists, this span has not been run yet, so use default.
            # Only issue warning if user-adjusted line is above either attachment point.
            if lineGuideZ is None:
                lineGuideZ = defaultLineGuideZ
            elif lineGuideZ > fromPoint.z or lineGuideZ > toPoint.z:
                arcpy.AddWarning("Warning: Match line placed above lowest point.")
                lineGuideZ = defaultLineGuideZ

            # Redundant with Tension case above:
            if fromPoint.z > toPoint.z:
                dLow = toPoint.z - lineGuideZ
                hSign = 1
            else:
                dLow = fromPoint.z - lineGuideZ
                hSign = -1

            h = attachmentPointHeightDifference
            dHigh = dLow + h

            h_over4 = (h / 4) * hSign
            sqrtDLow = math.sqrt(dLow)
            sqrtDHigh = math.sqrt(dHigh)
            lowPlusHigh = sqrtDLow + sqrtDHigh
            lowMinusHigh = sqrtDLow - sqrtDHigh
            lowPlusHigh_over_lowMinusHigh = lowPlusHigh / lowMinusHigh
            D = h_over4 * lowPlusHigh_over_lowMinusHigh

        else:
            # When called from adjust_3D_catenary the second time, sagDistance is supplied:
            D = sagDistance


        #############################################################
        #############################################################
        # Sag is determined now.
        # The next part creates a function to calculate the catenary height (z-value) along a 2D line from tower to tower.

        # variables from the diagram:
        S = spanLength2D
        h = attachmentPointHeightDifference
        w = lineWeightPerUnitLength  # lb/ft

        xHigh = (S / 2) * (1 + (h / (4 * D)))
        xLow = (S / 2) * (1 - (h / (4 * D)))


        dHigh = D * pow((1 + (h / (4 * D))), 2) # D sub L in book.
        dLow = D * pow((1 - (h / (4 * D))), 2)  # D sub R in book. # XX This is reversed, because the book chose left and right, rather than high and low.

        if H is None: # else horizontal tension was supplied.
            hLow = (w * pow(xLow, 2)) / (2 * dLow)
            #hHigh = (w * pow(xHigh, 2)) / (2 * dHigh)
            H = hLow  # or hHigh, because they must be equal.


        # Use external function for 3D polyline (below).
        makeSpanPolylineShapeAndLineGuide(span, xHigh, xLow, dHigh, dLow, H, w)


        # LineLength (uses these values from above calculations):
        # S = spanLength2D
        # xLow, xHigh
        # w = lineWeightPerUnitLength
        # H = Horizontal tension
        xRcubed_plus_xLcubed = pow(abs(xLow), 3) + pow(xHigh, 3) #XX note the abs!
        wSquared_over_6HSquared = pow(w, 2) / (6 * pow(H, 2))
        L = S + (xRcubed_plus_xLcubed * wSquared_over_6HSquared)

        # Save span data for span feature class.
        span.sagDistance = D
        span.horizontalTension = H
        span.lineLength = L
        span.weightPerUnitLength = w

        return span

    except arcpy.ExecuteError:
        # Get the tool error messages
        msgs = arcpy.GetMessages(2)
        arcpy.AddError(msgs)
    except Exception:
        e = sys.exc_info()[1]
        arcpy.AddMessage("Unhandled exception: " + str(e.args[0]))
    pass

def makeSpanPolylineShapeAndLineGuide(span, xHigh, xLow, dHigh, dLow, H, w):
    fromPoint = span.fromPoint
    toPoint = span.toPoint
    spanVector3D = vg.getVectorFromTwoPoints(fromPoint, toPoint)
    spanVector2DNoZ = vg.Vector(spanVector3D.x, spanVector3D.y, 0)
    spanLength2D = vg.magnitude(spanVector2DNoZ)
    # Make a list of values along the length of the span.
    # listZ holds the calculated z-values of each point on the line (relative to a flat 2D line between the towers).
    listZ = []
    # listT
    listT = []
    #Function z(t) is parameterized from 0 to 1 in X direction.
    def zAsAFunctionOfX(_x, _h, _w):
        a = _h / _w
        coshXoverA = math.cosh(_x / a)
        coshXoverA_MinusOne = coshXoverA - 1
        a_times_coshXoverA_MinusOne = a * coshXoverA_MinusOne
        z = a_times_coshXoverA_MinusOne
        return z

    for xStep in range(0, 101, 1):
        # T is moving from fromTower to toTower.
        T = (xStep * spanLength2D) / 100
        listT.append(T)
        # X origin is at lowest point in span, and x is positive in both directions.
        if fromPoint.z > toPoint.z:
            sagOriginDrop = dHigh
            # XX This condition is to handle a condition when an X value is negative... not sure about it. (uplift)
            if xHigh < 0:
                xAsFunctionOfT = abs(xHigh) + T
            else:
                xAsFunctionOfT = abs(T - xHigh)
        else:
            sagOriginDrop = dLow
            # XX This condition is to handle a condition when an X value is negative... not sure about it. (uplift)
            if xLow < 0:
                xAsFunctionOfT = abs(xLow) + T
            else:
                xAsFunctionOfT = abs(T - xLow)

        x = xAsFunctionOfT
        zValue = zAsAFunctionOfX(x, H, w)
        listZ.append(zValue)

    # XX Visual correction code is here!!!  This is just a fix, until we have someone with math or industry knowledge.

    firstZCalced = listZ[0] # z-relative to sag origin
    lastZCalced = listZ[-1] # z-relative to sag origin
    fromPointZ = span.fromPoint.z # feature z-value
    toPointZ = span.toPoint.z # feature z-value
    firstZCalcedPlusSagOriginDrop = firstZCalced + sagOriginDrop #CW TODO ref before init (maybe this was fixed?) maybe I got a runtime error for this? Too many weeks back.
    firstFixZ  = sagOriginDrop - firstZCalced
    firstElevDiff = fromPointZ - firstZCalcedPlusSagOriginDrop
    lastZCalcedPlusSagOriginDrop = lastZCalced + sagOriginDrop
    lastElevDiff = toPointZ - lastZCalcedPlusSagOriginDrop
    totalShearZ = lastElevDiff - firstElevDiff
    shearZIncrement = (totalShearZ / 100)


    # The is where we are calculating the line shape based on the known z-values determined above.
    # Start at fromPoint, and drop it by sag.
    sagDropVector = vg.Vector(0, 0, -sagOriginDrop)
    sagOriginPoint = vg.copyNode(fromPoint, sagDropVector)
    pointsForSpanPolyline = []
    for index in range(0, len(listT)):
        xAlongSpanVector = vg.setVectorMagnitude(spanVector2DNoZ, listT[index])
        shearZ = shearZIncrement * index # shearZ is part of visual fix
        zMoveUpValue = listZ[index] + firstFixZ + shearZ # firstFixZ is part of visual fix.
        zMoveUpVector = vg.Vector(0, 0, zMoveUpValue)
        originPointMoveVector = vg.addVectors(xAlongSpanVector, zMoveUpVector)
        thisPoint = vg.copyNode(sagOriginPoint, originPointMoveVector)
        pointsForSpanPolyline.append(thisPoint)


    # Make line shape from points.
    span.polyline = vg.Polyline(pointsForSpanPolyline)

    # Make lineGuide.
    lineGuideEndPoint = vg.copyNode(sagOriginPoint, spanVector2DNoZ)
    lineGuide = vg.Polyline([sagOriginPoint, lineGuideEndPoint])
    span.lineGuide = lineGuide

    pass

def doInsertSpanAndGuideLine(lc_includedTransmissionLinesFC, lc_includedTransmissionLineGuides,  lc_listOfSpans):
    try:
        # Insert features into 2 tables.

        fieldListSpans = ['SHAPE@', 'FromTower', 'ToTower', 'LineNumber', 'SagDistance', 'HorizontalTension', 'LineLength', 'WeightPerUnitLength']
        fieldListGuideLines = ['SHAPE@', 'FromTower', 'ToTower', 'LineNumber', 'FromX', 'FromY', 'FromZ', 'ToX', 'ToY', 'ToZ', 'SagDistance', 'WeightPerUnitLength']

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
            # XX Added extra reporting fields here:
            newRow.set('SagDistance', span.sagDistance)
            newRow.set('HorizontalTension', span.horizontalTension)
            newRow.set('LineLength', span.lineLength)
            newRow.set('WeightPerUnitLength', span.weightPerUnitLength)


            ####################################



            # Insert new transmission line.
            cursorInsertLine = arcpy.da.InsertCursor(lc_includedTransmissionLinesFC, newRow.getFieldNamesList())
            lineShape = vg.funPolylineToArcpyPolyline([span.polyline])
            newRow.set('SHAPE@', lineShape)
            cursorInsertLine.insertRow(newRow.getFieldValuesList())
            del cursorInsertLine

            if lc_includedTransmissionLineGuides is not None:
                # Insert new lineGuide.
                newRowGuideLines = utils.NewRow()

                fromX = span.fromPoint.x
                fromY = span.fromPoint.y
                fromZ = span.fromPoint.z

                toX = span.toPoint.x
                toY = span.toPoint.y
                toZ = span.toPoint.z

                # guideLineFieldList = fieldListSpans
                # guideLineFieldList.extend(["FromX", "FromY", "FromZ", "ToX", "ToY", "ToZ", "SagDistance"])
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



############################################################################################### Chris ends...................


def makeSpans(lc_scratch_ws, lc_inPoints, lc_testLineWeight, lc_sag_to_span_ratio, lc_horizontal_tension, lc_output_features, lc_debug, lc_use_in_memory):
    try:
        geometry_type = "POLYLINE"
        has_m = "DISABLED"
        has_z = "ENABLED"
        from_tower_field = "FromTower"
        to_tower_field = "ToTower"
        line_number_field = "LineNumber"
        count_field = "COUNT"

        from_X_field = "FromX"
        from_Y_field = "FromY"
        from_Z_field = "FromZ"
        To_X_field = "ToX"
        To_Y_field = "ToY"
        To_Z_field = "ToZ"
        sag_distance = "SagDistance"
        horizontal_tension = "HorizontalTension"
        line_lenght = "LineLength"
        weight_per_unit_length = "WeightPerUnitLength"

        transmission_line_name = "TransmissionLines3D"
        transmission_guide_name = "TransmissionLineGuide"
        in_memory = "in_memory"

        spatial_reference = arcpy.Describe(lc_inPoints).spatialReference

        # create empty feature class with required fields

        msg_body = create_msg_body("Preparing output feature classes...", 0, 0)
        msg(msg_body)

        if lc_use_in_memory:
            arcpy.AddMessage("Using in memory for processing")
            includedTransmissionLinesFC = in_memory + "/" + transmission_line_name

            arcpy.CreateFeatureclass_management(in_memory, transmission_line_name, geometry_type, "", has_m, has_z, spatial_reference)
        else:
            includedTransmissionLinesFC = lc_output_features + "_3D"

            includedTransmissionLinesFC_dirname = os.path.dirname(includedTransmissionLinesFC)
            includedTransmissionLinesFC_basename = os.path.basename(includedTransmissionLinesFC)

            if arcpy.Exists(includedTransmissionLinesFC):
                arcpy.Delete_management(includedTransmissionLinesFC)

            arcpy.CreateFeatureclass_management(includedTransmissionLinesFC_dirname, includedTransmissionLinesFC_basename, geometry_type, "", has_m, has_z,
                                                    spatial_reference)

        common_lib.delete_add_field(includedTransmissionLinesFC, from_tower_field, "LONG")
        common_lib.delete_add_field(includedTransmissionLinesFC, to_tower_field, "LONG")
        common_lib.delete_add_field(includedTransmissionLinesFC, line_number_field, "LONG")
        common_lib.delete_add_field(includedTransmissionLinesFC, count_field, "LONG")
        common_lib.delete_add_field(includedTransmissionLinesFC, sag_distance, "DOUBLE")
        common_lib.delete_add_field(includedTransmissionLinesFC, horizontal_tension, "DOUBLE")
        common_lib.delete_add_field(includedTransmissionLinesFC, line_lenght, "DOUBLE")
        common_lib.delete_add_field(includedTransmissionLinesFC, weight_per_unit_length, "DOUBLE")

        if lc_sag_to_span_ratio is None and lc_horizontal_tension is None:
            create_guidelines = True
        else:
            create_guidelines = False

        if create_guidelines:
            if lc_use_in_memory:
                includedTransmissionLineGuides = in_memory + "/" + transmission_guide_name

                arcpy.CreateFeatureclass_management(in_memory, transmission_guide_name, geometry_type, "", has_m, has_z, spatial_reference)
            else:
                includedTransmissionLineGuides = lc_output_features + "_LineGuides_3D"

                includedTransmissionLinesGuides_dirname = os.path.dirname(includedTransmissionLineGuides)
                includedTransmissionLinesGuides_basename = os.path.basename(includedTransmissionLineGuides)

                if arcpy.Exists(includedTransmissionLineGuides):
                    arcpy.Delete_management(includedTransmissionLineGuides)

                arcpy.CreateFeatureclass_management(includedTransmissionLinesGuides_dirname, includedTransmissionLinesGuides_basename, geometry_type, "", has_m, has_z,
                                                    spatial_reference)

            common_lib.delete_add_field(includedTransmissionLineGuides, from_tower_field, "LONG")
            common_lib.delete_add_field(includedTransmissionLineGuides, to_tower_field, "LONG")
            common_lib.delete_add_field(includedTransmissionLineGuides, line_number_field, "LONG")
            common_lib.delete_add_field(includedTransmissionLineGuides, from_X_field, "DOUBLE")
            common_lib.delete_add_field(includedTransmissionLineGuides, from_Y_field, "DOUBLE")
            common_lib.delete_add_field(includedTransmissionLineGuides, from_Z_field, "DOUBLE")
            common_lib.delete_add_field(includedTransmissionLineGuides, To_X_field, "DOUBLE")
            common_lib.delete_add_field(includedTransmissionLineGuides, To_Y_field, "DOUBLE")
            common_lib.delete_add_field(includedTransmissionLineGuides, To_Z_field, "DOUBLE")
            common_lib.delete_add_field(includedTransmissionLineGuides, sag_distance, "DOUBLE")
            common_lib.delete_add_field(includedTransmissionLineGuides, weight_per_unit_length, "DOUBLE")
        else:
            includedTransmissionLineGuides = None

        ############################################################################################### Chris continues...................
        attachmentPointList = []

        fieldList = ["SHAPE@X", "SHAPE@Y", "SHAPE@Z", "Line", "Tower"]
        fieldAccess = utils.FieldAccess(fieldList)
        cursor = arcpy.da.SearchCursor(lc_inPoints, fieldList)
        for row in cursor:
            fieldAccess.setRow(row)
            x = fieldAccess.getValue("SHAPE@X")
            y = fieldAccess.getValue("SHAPE@Y")
            z = fieldAccess.getValue("SHAPE@Z")
            lineNumber = fieldAccess.getValue("Line")
            towerNumber = fieldAccess.getValue("Tower")
            point = vg.Point(x, y, z)
            attachmentPoint = AttachmentPoint(point, lineNumber, towerNumber)
            attachmentPointList.append(attachmentPoint)
        if cursor:
            del cursor

        # Organize points into lists per line.
        dictionaryOfListsOfAttachmentPointsPerLine = {}
        for attachmentPoint in attachmentPointList:
            lineNumber = attachmentPoint.lineNumber
            if lineNumber in dictionaryOfListsOfAttachmentPointsPerLine.keys():
                listOfAttachmentPointsPerLine = dictionaryOfListsOfAttachmentPointsPerLine[lineNumber]
            else:
                listOfAttachmentPointsPerLine = []
                dictionaryOfListsOfAttachmentPointsPerLine[lineNumber] = listOfAttachmentPointsPerLine
            listOfAttachmentPointsPerLine.append(attachmentPoint)

        # Sort attachment points in each line list.
        # And make a list of line numbers for use in another dictionary.
        dictionaryOfSpanListsPerLine = {}
        lineNumberList = []
        for lineNumber in dictionaryOfListsOfAttachmentPointsPerLine.keys():
            lineNumberList.append(lineNumber)
            listOfAttachmentPointsPerLine = dictionaryOfListsOfAttachmentPointsPerLine[lineNumber]
            listOfAttachmentPointsPerLineSorted = sorted(listOfAttachmentPointsPerLine, key=lambda attachmentPoint: attachmentPoint.towerNumber)
            spanListPerThisLine = []
            for index in range(0, len(listOfAttachmentPointsPerLineSorted) - 1):
                fromPoint = listOfAttachmentPointsPerLineSorted[index]
                toPoint = listOfAttachmentPointsPerLineSorted[index + 1]

                # This is to give shield wires less sag, but only works when using the Easy Way.
                sagToSpanRatioForMakeSpan = None
                if lc_sag_to_span_ratio is not None:
                    sagToSpanRatioForMakeSpan = lc_sag_to_span_ratio
                    if lineNumber < 0:
                        sagToSpanRatioForMakeSpan = sagToSpanRatioForMakeSpan * 0.5

                span = makeSpan(fromPoint, toPoint, includedTransmissionLineGuides, lc_testLineWeight, sagToSpanRatio=sagToSpanRatioForMakeSpan,sagDistance=None, horizontalTension=lc_horizontal_tension)
                spanListPerThisLine.append(span)
            dictionaryOfSpanListsPerLine[lineNumber] = spanListPerThisLine

        msg_body = create_msg_body("Writing all span lines to " + includedTransmissionLinesFC_basename + ".", 0, 0)
        msg(msg_body)

        for index in range(0,len(lineNumberList)):
            lineNumber = lineNumberList[index]
            spanListPerThisLine = dictionaryOfSpanListsPerLine[lineNumber]
            # not TODO: CW, yes is has to run: switch is driven by includedTransmissionLineGuides inside the function.
            doInsertSpanAndGuideLine(includedTransmissionLinesFC, includedTransmissionLineGuides, spanListPerThisLine)

        if includedTransmissionLineGuides is not None:  # not TODO: CW, nope: see inside doInsertSpanAndGuideLine but could be coded more elegantly
            msg_body = create_msg_body(
                "Created helper Guide Lines feature class " + common_lib.get_name_from_feature_class(includedTransmissionLineGuides) + ".", 0, 0)
            msg(msg_body)

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

        return includedTransmissionLinesFC, includedTransmissionLineGuides

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
    input_source = r'D:\Gert\Work\Esri\Solutions\Utilities\Electric\work2.2\Transmission_Lines\Seattle_Utility_Sample.gdb\Attachment_Points'
    weight_per_unit = 1  # lb/ft
    horizontal_tension = 4500
    output_features = r'D:\Gert\Work\Esri\Solutions\Utilities\Electric\work2.2\Transmission_Lines\Testing.gdb\catenary_2'
    home_directory = r'D:\Gert\Work\Esri\Solutions\Utilities\Electric\work2.2\Transmission_Lines'
    project_ws = home_directory + "\\\Transmission_Lines.gdb"
    home_directory = r'D:\Gert\Work\Esri\Solutions\Utilities\Electric\work2.2\Transmission_Lines'
    debug = 1
    scratch_ws = common_lib.create_gdb(home_directory, "Intermediate.gdb")
    in_memory_switch = False

    catenary, guide_lines = makeSpans(lc_scratch_ws=scratch_ws,
                                lc_inPoints=input_source,
                                lc_testLineWeight=weight_per_unit,
                                lc_horizontal_tension=horizontal_tension,
                                lc_output_features=output_features,
                                lc_debug=debug,
                                lc_use_in_memory=in_memory_switch)


#    arcpy.SetParameter(1, output_lines)
    pass