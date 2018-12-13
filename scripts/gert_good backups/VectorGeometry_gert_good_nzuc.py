"""
Created on Jun 7, 2017
@author: cwilkins@esri.com
"""


import arcpy
import math
import sys

import ToolsUtilities as utils
if 'ToolsUtilities' in sys.modules:
    import importlib
    importlib.reload(utils)

##############################################
# Constants.

proxyForInfinity = 1000000000
proxyForInfinitesimal = 0.000001
zToleranceForFlatSlope = 0.001


class MultipartInputNotSupported(Exception): pass


###################################
# debugging and notifications

# For auditing results:
printAuditTrail = True
# For debugging:
debugMode = True

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

def pList(listName,listObjects):
    if debugMode is True:
        p("listName:", listName)
        for index in range(0,len(listObjects)):
            p("index("+str(index)+") ",listObjects[index])

def pintA(text):
    if printAuditTrail is True:
        arcpy.AddMessage(str(text))

def pA(someString, text):
    if printAuditTrail is True:
        if text is None:
            arcpy.AddMessage(someString + " is None")
        else:
            arcpy.AddMessage(someString + " " + str(text))


##################################################
##################################################
##################################################
##################################################
##################################################

# Copied from Stairway.py:
def bufferSingleLine(singleLine, width, extend):
    lineVector = singleLine.vector
    halfWidth = width / 2
    lineVectorHalfWidth = setVectorMagnitude(lineVector, halfWidth)
    rightVector = setVectorMagnitude(crossProduct(lineVector, unitZVector()), halfWidth)
    leftVector = reverseVector(rightVector)
    if extend is True:
        vectorARight = addVectors(reverseVector(lineVectorHalfWidth), rightVector)
        vectorALeft = addVectors(reverseVector(lineVectorHalfWidth), leftVector)
        vectorBRight = addVectors(lineVectorHalfWidth, rightVector)
        vectorBLeft = addVectors(lineVectorHalfWidth, leftVector)
    else:
        vectorARight = rightVector
        vectorALeft = leftVector
        vectorBRight = rightVector
        vectorBLeft = leftVector

    nodeARight = copyNode(singleLine.nodeA, vectorARight)
    nodeALeft = copyNode(singleLine.nodeA, vectorALeft)
    nodeBRight = copyNode(singleLine.nodeB, vectorBRight)
    nodeBLeft = copyNode(singleLine.nodeB, vectorBLeft)

    buffered = Polygon([nodeALeft, nodeBLeft, nodeBRight, nodeARight])
    return buffered







def reverseWindingOrder(nodeList):
    # Use new list. Don't reverse original list.
    returnList = nodeList.copy()
    returnList.reverse()
    utils.shiftListBackwardsAndWrap(utils.shiftListBackwardsAndWrap(returnList))
    return returnList


def funPointToArcpyPoint(funPoint):
    if funPoint is None:
        pintA("Error: funPointToArcpyPooint: input is None")
        return None
    else:
        newArcpyPoint = arcpy.Point(funPoint.x, funPoint.y, funPoint.z, None, 0)
        return newArcpyPoint


# Below will write a list of FunPolygon to a multi-part arcpy Polygon.
def funPolylineToArcpyPolyline(funPolylines):
    if funPolylines is None:
        pintA("Error: funPolylineToArcpyPolyline: input is None")
        return None
    elif len(funPolylines) == 0:
        pintA("Error: funPolylineToArcpyPolyline: polyline count is zero.")
        return None
    else:
        polylineArray = arcpy.Array()
        partCount = 0
        for funPolyline in funPolylines:
            if funPolyline is not None:
                funPoints = funPolyline.getNodes()
                newArcpyPoints = []
                for funPoint in funPoints:
                    newArcpyPoint = arcpy.Point(funPoint.x, funPoint.y, funPoint.z, None, 0)
                    newArcpyPoints.append(newArcpyPoint)
                    pointArray = arcpy.Array(newArcpyPoints)
                polylineArray.append(pointArray)
            else:
                pintA("Error: funPolylineToArcpyPolyline: polyline is None.")
            partCount += 1
        multipartFeature = arcpy.Polyline(polylineArray, None, True, False)
        return multipartFeature

# Below will write a list of FunPolygons to a multi-part arcpy Polygon.
def funPolygonToArcpyPolygon(funPolygons):
    if funPolygons is None:
        pintA("Error: funPolygonToArcpyPolygon: input is None")
        return None
    elif len(funPolygons) == 0:
        pintA("Error: funPolygonToArcpyPolygon: polygon count is zero.")
        return None
    else:
        polygonArray = arcpy.Array()
        partCount = 0
        for funPolygon in funPolygons:
            if funPolygon is not None:
                funPoints = funPolygon.getNodes()
                newArcpyPoints = []
                for funPoint in funPoints:
                    newArcpyPoint = arcpy.Point(funPoint.x, funPoint.y, funPoint.z, None, 0)
                    newArcpyPoints.append(newArcpyPoint)
                    pointArray = arcpy.Array(newArcpyPoints)
                polygonArray.append(pointArray)
            else:
                pintA("Error: funPolygonToArcpyPolygon: polygon is None.")
            partCount += 1
        multipartFeature = arcpy.Polygon(polygonArray, None, True, False)
        return multipartFeature

# def funPolygonToArcpyPolygonWithHoles(funPolygonOuter,funPolygonHoles):
#     if funPolygonOuter is None:
#         pintA("Error: funPolygonToArcpyPolygon: input is None")
#         return None
#     elif len(funPolygons) == 0:
#         pintA("Error: funPolygonToArcpyPolygon: polygon count is zero.")
#         return None
#     else:
#         polygonArray = arcpy.Array()
#         for funPolygon in funPolygons:
#             if funPolygon is not None:
#                 funPoints = funPolygon.nodes
#                 newArcpyPoints = []
#                 for funPoint in funPoints:
#                     newArcpyPoint = arcpy.Point(funPoint.x, funPoint.y, funPoint.z, None, 0)
#                     newArcpyPoints.append(newArcpyPoint)
#                     pointArray = arcpy.Array(newArcpyPoints)
#                 polygonArray.append(pointArray)
#             else:
#                 pintA("Error: funPolygonToArcpyPolygon: polygon is None.")
#         multipartFeature = arcpy.Polygon(polygonArray, None, True, False)
#         return multipartFeature


def arcpyPolygonToFunPolygon(arcpyPolygon):
    if arcpyPolygon is None:
        pintA("Input polygon is Null.")
        raise Exception
    pint(arcpyPolygon.pointCount)
    polygonNodes = []
    partCount = 0
    for part in arcpyPolygon:
        partCount += 1
        for pnt in part:
            if pnt:
                node = Node(pnt.X, pnt.Y, pnt.Z)
                polygonNodes.append(node)
                p("node",node)
    p("partCount",partCount)
    if partCount > 1:
        pintA("Multipart input shape not supported.")
        raise MultipartInputNotSupported
    firstPoint = polygonNodes[0]
    p("firstPoint",firstPoint)
    lastPoint = polygonNodes[-1]
    p("lastPoint",lastPoint)

    # XX, if data has repeated first and last node produced by GP tools, such as Simplify Polygon, then add a pop() here.
    if pointsAreCoincident(firstPoint, lastPoint, 0.0000000001):
        #pintA("Warning: Polygon has repeated end node. Node is ignored for tool output, but original feature still has it.")
        p("len(polygonNodes)", len(polygonNodes))
        polygonNodes.pop()
    p("len(polygonNodes)", len(polygonNodes))

    firstPoint2 = polygonNodes[0]
    p("firstPoint2",firstPoint2)
    lastPoint2 = polygonNodes[-1]
    p("lastPoint2",lastPoint2)

    # XX, if data has repeated first and last node produced by GP tools, such as Simplify Polygon, then add a pop() here.
    if pointsAreCoincident(firstPoint2, lastPoint2, 0.0000000001):
        #pintA("Warning: Polygon has repeated end node. Node is ignored for tool output, but original feature still has it.")
        polygonNodes.pop()

    p("len(polygonNodes)",len(polygonNodes))
    return Polygon(polygonNodes)

##############################################################################
##############################################################################
##############################################################################
##############################################################################
##############################################################################
##############################################################################
##############################################################################



def arcpyPolylineToVGPolyline(arcpyPolyline):
    try:
        if arcpyPolyline is None:
            pintA("Input polyline is Null.")
            raise Exception
        #pint(arcpyPolyline.pointCount)
        polylineNodes = []
        partCount = 0
        for part in arcpyPolyline:
            partCount += 1
            for pnt in part:
                if pnt:
                    node = Node(pnt.X, pnt.Y, pnt.Z)
                    polylineNodes.append(node)
                    #p("node",node)
        #p("partCount",partCount)
        if partCount > 1:
            pintA("Multipart input shape not supported.")
            return None
        else:
            return Polyline(polylineNodes)

    except MultipartInputNotSupported:
        print("Multipart features are not supported. Exiting...")
        arcpy.AddError("Multipart features are not supported. Exiting...")

    except arcpy.ExecuteWarning:
        print((arcpy.GetMessages(1)))
        arcpy.AddWarning(arcpy.GetMessages(1))

    except arcpy.ExecuteError:
        print((arcpy.GetMessages(2)))
        arcpy.AddError(arcpy.GetMessages(2))

    # Return any other type of error
    except:
        # By default any other errors will be caught here
        #
        e = sys.exc_info()[1]
        print((e.args[0]))
        arcpy.AddError(e.args[0])

def lineIsFlat(line):
    deltaZ = abs(line.nodeB.z - line.nodeA.z)
    return deltaZ < zToleranceForFlatSlope



def lengthInXYPlaneProjection(line):
    deltaX = abs(line.nodeB.x - line.nodeA.x)
    deltaY = abs(line.nodeB.y - line.nodeA.y)
    return math.sqrt(pow(deltaX,2) + pow(deltaY,2))

def lengthIn3D(line):
    deltaX = abs(line.nodeB.x - line.nodeA.x)
    deltaY = abs(line.nodeB.y - line.nodeA.y)
    deltaZ = abs(line.nodeB.z - line.nodeA.z)
    return math.sqrt(pow(deltaX, 2) + pow(deltaY, 2) + pow(deltaZ, 2))

def slope(line):
    run = lengthInXYPlaneProjection(line)
    rise = line.nodeB.z - line.nodeA.z
    if run == 0:
        return None
    else:
        return rise/run

def slopeAngle(line):
    the_slope = slope(line)
    if the_slope is None:
        return None
    else:
        return math.atan(slope(line))

class NavLine(object):
    def __init__(self, nodeA, nodeB):
        self.nodeA = nodeA
        self.nodeB = nodeB
        # Direction of travel.
        self.vector = getVectorFromTwoPoints(self.nodeA, self.nodeB)
        self.type = None

    #def midPoint(self):
    #    copyNode(Node(self.nodeA, setVectorMagnitude(self.vector, 0.5 * ))

    def shrinkTowardsCenter(self, distance):
        return NavLine(copyNode(self.nodeA, setVectorMagnitude(self.vector, distance)),copyNode(self.nodeB, reverseVector(setVectorMagnitude(self.vector, distance))))



class Polyline(object):
    def __init__(self, listOfNodes):
        self.nodes = listOfNodes
        self.edges = []
        for nodeIndex in range(0,len(self.nodes) - 1):
            self.edges.append(NavLine(self.nodes[nodeIndex], self.nodes[nodeIndex + 1]))
        #self.edgeVectors = []
        #self.zMin = None
        #self.zMax = None

    def getNodes(self):
        return self.nodes

# XX unify nodes points lines navlines...

def getPolyineFromLineList(lineList):
    pointList = []
    for index in range(0, len(lineList)):
        line = lineList[index]
        if index == 0:
            pointList.append(line.nodeA)
        pointList.append(line.nodeB)
    return Polygon(pointList)




class Polygon(object):
    def __init__(self, listOfNodes):
        self.nodes = listOfNodes
        self.edges = []
        self.edgeVectors = []
        self.zMin = None
        self.zMax = None

    def setMinAndMaxZ(self):
        zMin = proxyForInfinity
        zMax = -proxyForInfinity
        for node in self.nodes:
            if node.z < zMin:
                zMin = node.z
        for node in self.nodes:
            if node.z > zMax:
                zMax = node.z
        self.zMin = zMin
        self.zMax = zMax


    def setFlatZ(self, zValue):
        for node in self.nodes:
            node.z = zValue

    def appendNode(self,node):
        self.nodes.append(node)

    def getNodes(self):
        return self.nodes

    def getArea(self):
        # Thanks to this web page for most simple area algorithm I could find:
        #  http://www.mathopenref.com/coordpolygonarea.html
        nodesWrapped = []
        nodesWrapped.extend(self.nodes)
        nodesWrapped.append(self.nodes[0])
        nodeCount = len(self.nodes)
        sum = 0
        for index in range(0,nodeCount):
            thisX = nodesWrapped[index].x
            nextX = nodesWrapped[index + 1].x
            thisY = nodesWrapped[index].y
            nextY = nodesWrapped[index + 1].y
            thisX_nextY = thisX * nextY
            nextX_thisY = nextX * thisY
            sum += (thisX_nextY - nextX_thisY)
        return abs(sum / 2)


    def makeEdges(self):
        self.edges = []
        self.edgeVectors = []
        # This will rebuild edge list when called.
        for index in range(0,len(self.nodes)):
            if index > len(self.nodes) - 2:
                nextIndex = 0
            else: 
                nextIndex = index + 1
            node1 = self.nodes[index]
            node2 = self.nodes[nextIndex]
            newEdge = Edge(node1, node2)
            self.edges.append(newEdge)
            self.edgeVectors.append(newEdge.vector)
        pass

    def __str__(self):
        ret = "Polygon: " 
        for node in self.nodes:
            ret += str(node) + ","
        return ret

def drawRectangleOnPoint(point, xDim, yDim):
    x = point.x
    y = point.y
    z = point.z
    halfX = xDim / 2
    halfY = yDim / 2
    x0 = x - halfX
    x1 = x + halfX
    y0 = y - halfY
    y1 = y + halfY
    polygonPoints = [Point(x0,y0,z), Point(x0,y1,z), Point(x1,y1,z), Point(x1,y0,z)]
    return Polygon(polygonPoints)

# XX check if this is still useful:
def drawRectangleWithTwoPoints(pointA, pointB, thickness):
    directionVector = getVectorFromTwoPoints(pointA, pointB)
    normalVector = normalVector2D(directionVector)
    halfThickness = thickness / 2
    upVector = setVectorMagnitude(normalVector, halfThickness)
    downVector = reverseVector(upVector)
    point0 = movePoint(pointA, downVector)
    point1 = movePoint(pointA, upVector)
    point2 = movePoint(pointB, upVector)
    point3 = movePoint(pointB, downVector)
    polygonPoints = [point0, point1, point2, point3]
    return Polygon(polygonPoints)



def normalVector2D(vector):
    return crossProduct(vector, Vector(0,0,1))

class Node(object):
    def __init__(self, x,y,z):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.turnCode = 0 # XX remove this attribute and attach it when needed. No functions use it except skeleton.

    def __str__(self):
        return "(" + str(self.x) + "," + str(self.y) + "," + str(self.z) + ")"

class Edge(object):
    def __init__(self, nodeA, nodeB):
        self.nodeA = nodeA
        self.nodeB = nodeB
        self.setback = 0
        self.vector = getVectorFromTwoPoints(self.nodeA, self.nodeB)

    def getMidpoint(self):
        halfVector = multiplyVector(self.vector, 0.5)
        midNode = copyNode(self.nodeA, halfVector)
        return midNode

    def __str__(self):
        return "Edge: PointA: " + str(self.nodeA) + " PointB: " + str(self.nodeB) + " Setback: "+ str(self.setback) 


class Point(object):
    def __init__(self, x,y,z):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        #self.coordinates = [x,y,z]

    def __str__(self):
        return "(" + str(self.x) + "," + str(self.y) + "," + str(self.z) + ")"

class Line(object):
    def __init__(self, pointA, pointB):
        self.pointA = pointA
        self.pointB = pointB

    def __str__(self):
        return "Line from: " + str(self.pointA) + " to  " + str(self.pointB)

class Vector(object):
    def __init__(self, x,y,z):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def __str__(self):
        return "(" + str(self.x) + "," + str(self.y) + "," + str(self.z) + ")"

class Ray2D(object):
    def __init__(self, point, vector):
        self.point = point
        self.vector = vector

    def __str__(self):
        return "Ray: Start: " + self.point + " Direction: " + self.vector  






############################
# Vector and ray functions:

def getBisectingVector2D(A, B):
    unitA = unitizeVector(A)
    unitB = unitizeVector(B)
    return addVectors(unitA, unitB)


# XX This hasn't been tested.
def rotateVector2D(A, angle):
    rotatedX = A.x * math.cos(angle) - A.y * math.sin(angle)
    rotatedY = A.x * math.sin(angle) + A.y * math.cos(angle)
    return Vector(rotatedX, rotatedY, 0)

def normalizeDegrees(degrees):
    if degrees < 0: return degrees + 360
    elif degrees > 360: return degrees - 360
    else: return degrees


def getCardinalDirectionFromVector2D(vector2D):
    cardinalDirection = (math.atan2(vector2D.x, vector2D.y) * (180 / math.pi))
    return normalizeDegrees(cardinalDirection)


# Goes from input we use (N=0, CW rotation), to that used by trig (E=0, CCW), and back again, too.
def angleCardinalSystemSwap(trigDegrees):
    return (450 - trigDegrees) % 360

def vectorByDirection2D(direction):
    trigDegrees = angleCardinalSystemSwap(direction)
    trigRadians = math.radians(trigDegrees)
    return Vector(math.cos(trigRadians), math.sin(trigRadians), 0)

def dotProduct(A,B):
    return (A.x * B.x) + (A.y * B.y) + (A.z * B.z)

def scalarProjection(A,B):
    # Projects A onto B.
    # XX This does not use dot product, which is how I've seen it done... but it works, I think because the
    #    dot is in the angleBetweenTwoVectors part maybe.
    angle = angleBetweenTwoVectors(A,B)
    scalar = magnitude(A) * math.cos(angle)
    return scalar

def setVectorMagnitude(A, magnitude):
    unit = unitizeVector(A)
    return Vector(unit.x * magnitude, unit.y * magnitude, unit.z * magnitude)

def unitizeVector(A):
    mag = magnitude(A) 
    return Vector(A.x/mag, A.y/mag, A.z/mag)

def unitZVector():
    return Vector(0,0,1)

def reverseVector(A):
    return Vector(-A.x, -A.y, -A.z)

def crossProduct(A, B):
    cross = [A.y*B.z - A.z*B.y, A.z*B.x - A.x*B.z, A.x*B.y - A.y*B.x]
    return Vector(cross[0],cross[1],cross[2])

def magnitude(A):
    return math.sqrt(pow(A.x,2) + pow(A.y,2) + pow(A.z,2))

def angleBetweenTwoVectors(A,B):
    dotAB = dotProduct(A,B)
    productOfMagnitudes = magnitude(A) * magnitude(B)
    if productOfMagnitudes == 0:
        pintA("Angle between two vectors has division by zero.")
    # Handle floating point error where acos evaluates number outside of valid domain of -1 to 1.
    dotOverMagProduct = dotAB/productOfMagnitudes
    if dotOverMagProduct > 1:
        dotOverMagProduct = 1
    elif dotOverMagProduct < -1:
        dotOverMagProduct = -1

    angle = math.acos(dotOverMagProduct)
    return angle




def getVectorFromTwoPoints(pointA, pointB):
    # PointA is start. PointB is end.
    return Vector(pointB.x - pointA.x, pointB.y - pointA.y, pointB.z - pointA.z)

def pointsAreCoincident(pointA, pointB, tolerance):
    if abs(pointB.x - pointA.x) > tolerance or abs(pointB.y - pointA.y) > tolerance or abs(pointB.z - pointA.z) > tolerance:
        return False
    else:
        return True

# XX shorten vector is weird. should be relative or just a multiply vector. later.
def shortenVector(vector, percent):
    return Vector(vector.x * percent, vector.y * percent, vector.z * percent)
# XX deprecate shortenVector above, later, and use below
def multiplyVector(vector, multiple):
    return Vector(vector.x * multiple, vector.y * multiple, vector.z * multiple)


def addVectors(A, B):
    return Vector(A.x + B.x, A.y + B.y, A.z + B.z)



def movePoint(point, vector):
    return Point(point.x + vector.x, point.y + vector.y, point.z + vector.z) 

# XX This is not moving anything. It is same as copy below. Later.
# XX And Point and Node... same thing mostly.
def moveNode(node, vector):
    return Node(node.x + vector.x, node.y + vector.y, node.z + vector.z) 

def copyNode(node, vector):
    return Node(node.x + vector.x, node.y + vector.y, node.z + vector.z)

def movePolygon(polygon,vector):
    # XX Will this affect the edges?
    # XX This moves the polygon, and doesn't create a copy.
    for node in polygon.nodes:
        node.x += vector.x
        node.y += vector.y
        node.z += vector.z
    pass

# This is a deep copy.
def copyPolygon(previousPolygon):
    newPolygon = Polygon([])
    for node in previousPolygon.nodes:
        newX = node.x
        newY = node.y
        newZ = node.z
        newNode = Node(newX, newY, newZ)
        newPolygon.appendNode(newNode)
    # XX I wasn't needing min and max on the copies, so this is turned off:
    #newPolygon.zMin = previousPolygon.zMin
    #newPolygon.zMax = previousPolygon.zMax
    return newPolygon

##############################################################
# Visual aids:



def wrapIndexBackward(index, length):
    newIndex = index - 1
    if index == 0:
        newIndex = length - 1
    return newIndex

def wrapIndexForward(index, length):
    newIndex = index + 1
    if index == length - 1:
        newIndex = 0
    return newIndex




def isWithinTolerance(valueFound, valueTarget, tolerance):
    if valueTarget == 0:
        # For zero, you cannot multiply by the tolerance by zero, so we add the tolerance as absolute.
        return abs(valueFound - valueTarget) < (valueTarget + tolerance)
    else:
        # Multiply by tolerance for relativity to large numbers.
        return abs(valueFound - valueTarget) < (valueTarget * tolerance)



class OrientedBoundingBox2D(object):
    def __init__(self, polygon, direction):
        self.polygon = polygon
        self.guestPolygon = None
        self.direction = direction # direction is clockwise, N=0, E=90, S=180, W=270, in degrees.

        # U,V are like X,Y.
        self.uAxis = vectorByDirection2D(self.direction)
        self.vAxis = vectorByDirection2D(self.direction - 90)

        # for shorthand
        nodes = polygon.nodes

        # get reference point.
        node0 = nodes[0]
        node1 = nodes[1]
        vector0to1 = getVectorFromTwoPoints(node0,node1)
        midpointVector = shortenVector(vector0to1, 0.5)
        referencePoint = movePoint(node0,midpointVector)

        # Scalar projection of reference vector onto U and V axes.
        referenceVectors = []
        uDeltas = []
        vDeltas = []
        for node in nodes:
            referenceVector = getVectorFromTwoPoints(referencePoint, node)
            referenceVectors.append(referenceVector)
            uDelta = scalarProjection(referenceVector, self.uAxis)
            uDeltas.append(uDelta)
            vDelta = scalarProjection(referenceVector, self.vAxis)
            vDeltas.append(vDelta)

        uMin = min(uDeltas)
        uMax = max(uDeltas)
        vMin = min(vDeltas)
        vMax = max(vDeltas)

        self.uDistance = uMax - uMin
        self.vDistance = vMax - vMin

        # Distance from minimum value to zero, to offset all points to make UV origin at (0,0)
        uOffset = 0 - uMin
        vOffset = 0 - vMin

        # Attach UV coordinates to nodes.
        index = 0
        for node in nodes:
            node.u = uDeltas[index] + uOffset
            node.v = vDeltas[index] + vOffset
            index += 1

        # Get four corner points, clockwise.
        uMinVec = setVectorMagnitude(self.uAxis, uMin)
        uMaxVec = setVectorMagnitude(self.uAxis, uMax)
        vMinVec = setVectorMagnitude(self.vAxis, vMin)
        vMaxVec = setVectorMagnitude(self.vAxis, vMax)

        v0minUminV = addVectors(uMinVec,vMinVec)
        v1minUmaxV = addVectors(uMinVec,vMaxVec)
        v2maxUmaxV = addVectors(uMaxVec,vMaxVec)
        v3maxUminV = addVectors(uMaxVec,vMinVec)

        self.p0 = copyNode(referencePoint,v0minUminV)
        self.p1 = copyNode(referencePoint,v1minUmaxV)
        self.p2 = copyNode(referencePoint,v2maxUmaxV)
        self.p3 = copyNode(referencePoint,v3maxUminV)

        self.boundingBoxPolygon = Polygon([self.p0,self.p1,self.p2,self.p3])

        # For storing results of split.
        self.polygonsAboveSplit = None
        self.polygonsBelowSplit = None

    def getPolygonsBelowSplit(self): return self.polygonsBelowSplit

    def getPolygonsAboveSplit(self): return self.polygonsAboveSplit

    def projectPolygonIntoUV(self, polygon):
        self.guestPolygon = polygon
        self.guestHighestV = 0
        self.guestLowestV = proxyForInfinity
        for node in self.guestPolygon.nodes:
            self.addUVCoordinates(node)
            if node.v > self.guestHighestV:
                self.guestHighestV = node.v
            if node.v < self.guestLowestV:
                self.guestLowestV = node.v
        pass

    #Assumptions: No self crossing polygons, no holes, no zero-length edges (coincident nodes).

    def split(self, polygon, axis, splitDistance):
        #Reset lists.
        self.polygonsBelowSplit = []
        self.polygonsAboveSplit = []

        # First, check if the guest is completely above or below the split line.
        allNodesAreAbove = True
        allNodesAreBelow = True
        for node in polygon.nodes:
            nodeIsAbove = node.v > splitDistance
            if nodeIsAbove is True:
                allNodesAreBelow = False

            nodeIsBelow = node.v < splitDistance
            if nodeIsBelow is True:
                allNodesAreAbove = False


        if allNodesAreBelow is True:
            self.polygonsAboveSplit.append(polygon)
        elif allNodesAreAbove is True:
            self.polygonsBelowSplit.append(polygon)
        else:

            # Traverse nodes in sets of three.
            theseNodes = polygon.nodes
            previousNodes = utils.shiftListBackwardsAndWrap(theseNodes)
            nextNodes = utils.shiftListForwardsAndWrap(theseNodes)

            # List for existing and additional nodes.
            newNodes = []
            i = 0
            for thisNode in theseNodes:
                # Init to False, or else would be None.
                thisNode.isSplitNode = False
                previousNode = previousNodes[i]
                nextNode = nextNodes[i]
                i += 1

                thisNodeIsAbove = thisNode.v > splitDistance
                thisNodeIsEqual = thisNode.v == splitDistance
                thisNodeIsBelow = thisNode.v < splitDistance

                previousNodeIsAbove = previousNode.v > splitDistance
                previousNodeIsEqual = previousNode.v == splitDistance
                previousNodeIsBelow = previousNode.v < splitDistance

                nextNodeIsAbove = nextNode.v > splitDistance
                nextNodeIsEqual = nextNode.v == splitDistance
                nextNodeIsBelow = nextNode.v < splitDistance

                # If node is on split line, then it either just entered, or has already been on the line, and it may exit.
                if thisNodeIsEqual:

                    # Entry and exit on node lying on the split.
                    if (previousNodeIsAbove and nextNodeIsBelow) or (previousNodeIsBelow and nextNodeIsAbove):
                        # This is simply crossing on a node.
                        thisNode.isSplitNode = True

                    # Entry onto parallel from below.
                    elif (nextNodeIsEqual and previousNodeIsBelow):
                        # Entering parallel and coincident line, from below.
                        leftTurn = thisNode.u > nextNode.u
                        if leftTurn :
                            thisNode.isSplitNode = True
                    # Entry onto parallel from above.
                    elif (nextNodeIsEqual and previousNodeIsAbove):
                        # Entering parallel and coincident line, from above.
                        leftTurn = thisNode.u < nextNode.u
                        if leftTurn :
                            thisNode.isSplitNode = True
                    # Entry from previous parallel does not create event.
                    # elif (previousNodeIsEqual and nextNodeIsEqual):

                    # Exit from parallel with left turn to above.
                    elif (previousNodeIsEqual and nextNodeIsAbove):
                        leftTurn = thisNode.v < nextNode.v
                        if leftTurn:
                            thisNode.isSplitNode = True

                    # Exit from parallel with left turn to below.
                    elif (previousNodeIsEqual and nextNodeIsAbove):
                        leftTurn = thisNode.v > nextNode.v
                        if leftTurn:
                            thisNode.isSplitNode = True

                    newNodes.append(thisNode)
                else:
                    newNodes.append(thisNode)
                    if (thisNodeIsBelow and nextNodeIsAbove) or (thisNodeIsAbove and nextNodeIsBelow):
                        # Need to get point of intersection.
                        vectorThisToNext = getVectorFromTwoPoints(thisNode, nextNode)
                        vDistToNext = abs(thisNode.v - nextNode.v)
                        vDistToSplit = abs(thisNode.v - splitDistance)
                        # XX This will fail on coincident nodes. (stated in assumptions)
                        ratioToNewSplitPoint = (vDistToSplit/vDistToNext)
                        vectorThisToCrossingPoint = shortenVector(vectorThisToNext, ratioToNewSplitPoint)
                        newSplitNode = copyNode(thisNode, vectorThisToCrossingPoint)
                        self.addUVCoordinates(newSplitNode)
                        newSplitNode.isSplitNode = True
                        # XX Would be nice to have a convert world to UV function available here.
                        newNodes.append(newSplitNode)


            # Order the split nodes from lowest to highest, if there is not an even number of splits, indicate an error.
            splitDict = {}
            nodeIndex = 0
            for newNode in newNodes:
                newNode.nodeIndex = nodeIndex
                if newNode.isSplitNode:
                    splitDict[newNode.u] = newNode
                    newNode.hasBeenJumpedFrom = False
                nodeIndex += 1

            # Sort the split nodes by U value.
            splitNodes = []
            sortedSplits = sorted(splitDict)
            for splitKey in sortedSplits:
                splitNodes.append(splitDict[splitKey])

            # Assign split node pairs.
            for index in range(0,len(sortedSplits),2):
                # Each pair of split nodes jumps to each other.
                splitNodes[index].isAboveSplit = True
                splitNodes[index + 1].isAboveSplit = False
                splitNodes[index].jumpsTo = splitNodes[index + 1].nodeIndex
                splitNodes[index + 1].jumpsTo = splitNodes[index].nodeIndex

            #self.polygonsBelowSplit = []
            #self.polygonsAboveSplit = []

            for splitNode in splitNodes:
                isAboveSplit = splitNode.isAboveSplit
                if not splitNode.hasBeenJumpedFrom:
                    splitNode.hasBeenJumpedFrom = True
                    index = splitNode.nodeIndex

                    # Process a loop, starting with this jump point.
                    loopNodes = []
                    loopCompleted = False
                    bailout = 0
                    while not loopCompleted:
                        # Check if index has wrapped.
                        if index > len(newNodes) - 1:
                            index = 0

                        newNode = newNodes[index]
                        loopNodes.append(newNode)

                        if newNode.isSplitNode:
                            newNode.hasBeenJumpedFrom = True
                            index = newNode.jumpsTo
                            loopNodes.append(newNodes[index])

                        index += 1

                        if (len(loopNodes) > 2) and (newNode is loopNodes[0]):
                            # Remove last repeated node.
                            loopNodes.pop()
                            loopCompleted = True

                        # prevent infinite.
                        bailout += 1
                        if bailout > 1000:
                            loopCompleted = True
                            exit()
                    # END while loop

                if isAboveSplit:
                    self.polygonsAboveSplit.append(Polygon(loopNodes))
                else:
                    self.polygonsBelowSplit.append(Polygon(loopNodes))

            # End Else.
        pass




    def addUVCoordinates(self, node):
        origin = self.p0
        originToNodeVector = getVectorFromTwoPoints(origin, node)
        node.u = scalarProjection(originToNodeVector, self.uAxis)
        node.v = scalarProjection(originToNodeVector, self.vAxis)
        pass

    def __str__(self):
        return "BBOX!"







###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################

# FloorPlate is return type from SetbackPerEdge.
# It can only take 1 Floor Plate, but can return multiple.
# If multiple are returned, then they will carry their own lists of who was dropped,
# but can that be used to find cumulative setbacks?

class FloorPlate(object):
    def __init__(self, polygon):
        self.polygon = polygon
        self.edgeDataList = []

class EdgeData(object):
    def __init__(self, segmentID, edgeType, stepback):
        self.segmentID = segmentID
        self.edgeType = edgeType
        self.stepback = stepback

    def __str__(self):
        return "EdgeData: segmentID: " + str(self.segmentID) + ", edgeType: " + str(self.edgeType) +", stepback: " + str(self.stepback)


def zeroCleaner(value):
    if value <= 0:
        return proxyForInfinitesimal
    else:
        return value

class SetbackPerEdge(object):
    def __init__(self, floorPlate, ringIndex, subPolyIndex):
        pintA("New SetbackPerEdge, ring# " + str(ringIndex))
        # For tracking and debugging only.
        self.subPolyIndex = subPolyIndex
        self.ringIndex = ringIndex
        # New FloorPlate object, which only has one polygon.
        self.floorPlate = floorPlate
        # Get polygon from floorPlate.
        self.polygon = floorPlate.polygon
        # For use in existing algorithm, without heavy recoding, populating local edgeDataList and stepbackValueList here.
        # And it uses new Lists, leaving the old ones alone.
        self.edgeDataList = []
        self.stepbackValueList = []
        self.inputStepbackValueList = []
        for edgeIndex in range(0,len(self.polygon.nodes)):
            edgeData = floorPlate.edgeDataList[edgeIndex]
            self.edgeDataList.append(edgeData)
            self.stepbackValueList.append(zeroCleaner(edgeData.stepback))
            self.inputStepbackValueList.append(zeroCleaner(edgeData.stepback))
        # New return type:
        self.returnFloorPlates = []

        # Old return types.
        #self.returnEventSetbackValueList = []
        # XX Check if these are still referenced.
        self.returnDroppedEdgeData = []
        self.returnDroppedEdgeDistances = []

        # For algorithm geometry:
        self.edgesA = None
        self.edgesB = None
        self.vectorsA = None
        self.vectorsB = None
        self.turnList = None
        self.nodeBetweenAandBList = None
        if len(self.polygon.nodes) > 2:
            self.make()
        else:
            pass

    def __str__(self):
        return "SetbackPerEdge."

    def getReturnFloorPlates(self):
        return self.returnFloorPlates

    def getReturnDroppedEdgeData(self):
        return self.returnDroppedEdgeData

    def getReturnDroppedEdgeDistances(self):
        return self.returnDroppedEdgeDistances

    #def getStepbackValueList(self):
        #return self.stepbackValueList

    def getInputStepbackValueList(self):
        return self.inputStepbackValueList

    #def getReturnEventSetbackValueList(self): ######## XX I'm not sure when/how this came about. Is it reduncant?
    #    return self.returnEventSetbackValueList ####



    def getArea(self):
        area = 0
        if self.returnFloorPlates is not None and len(self.returnFloorPlates) > 0:
            for floorPlateIndex in range(0, len(self.returnFloorPlates)):
                polygon = self.returnFloorPlates[floorPlateIndex].polygon
                if polygon is not None:
                    area += polygon.getArea()
        return area

    def make(self):
        pintA("Make SetbackPerEdge")
        poly = self.polygon
        originalPolygonNodeCount = len(poly.nodes)
        poly.makeEdges()
        # EdgeA is previous edge.
        self.edgesA = utils.shiftListBackwardsAndWrap(poly.edges)
        # EdgeB is current edge.
        self.edgesB = poly.edges
        self.vectorsA = utils.shiftListBackwardsAndWrap(poly.edgeVectors)
        self.vectorsB = poly.edgeVectors
        self.turnList = []
        self.skeletonEdgeVectorList = []
        self.nodeBetweenAandBList = []
        # Put setback values onto edges.
        index = 0
        for edge in poly.edges:
            edge.setback = self.stepbackValueList[index]
            index += 1
        # SKELETON CONSTRUCTION:

        # First check if polygon has collapsed to a point or line.
        pointTolerance = 0.000000001
        if originalPolygonNodeCount == 3:
            # If any two nodes are the same...
            if pointsAreCoincident(poly.nodes[0], poly.nodes[1], pointTolerance) or \
                pointsAreCoincident(poly.nodes[0], poly.nodes[2], pointTolerance) or \
                pointsAreCoincident(poly.nodes[1], poly.nodes[2], pointTolerance):
                return None
        if originalPolygonNodeCount <= 2:
            return None


        # This will hold resultant points of setback polygon.
        pointsForPolygon = []
        # Find components for skeleton.
        pintA("Find components for skeleton.")

        for index in range(0,len(self.vectorsA)):
            vA = self.vectorsA[index]
            vB = self.vectorsB[index]
            crossAB = crossProduct(vA, vB)

            # Turn angle.
            turnAngle = angleBetweenTwoVectors(vA,vB)

            turn = "convex" # right turn going clockwise.
            if turnAngle == 0:
                turn = "convex"
            elif crossAB.z > 0:
                turn = "concave" # CW, left turn. concave node.
            else: #crossAB.z <= 0:
                turn = "convex" # CW, right turn. convex node.
            self.turnList.append(turn)


            if turnAngle == 0:
                eA = self.edgesA[index]
                skeletonNodeOnStraightLineVector = normalVector2D(eA.vector)
                skeletonEdgeVector = setVectorMagnitude(skeletonNodeOnStraightLineVector, eA.setback)
                pint("NODE ON STRAIGHT LINE")
                pA("index",index)

            else:
                angleAlpha = (math.pi / 2) - turnAngle
                pA("angleAlpha",angleAlpha)
                cosineForBothVectors = math.cos(angleAlpha)
                pA("cosineForBothVectors",cosineForBothVectors)
                # XX I think this cosine is where a node on a straight line will fail. Fix this soon.

                eA = self.edgesA[index]
                eB = self.edgesB[index]
                setbackA = eA.setback
                setbackB = eB.setback
                # Notice transposition of A and B here.
                littleA = setbackB / cosineForBothVectors
                littleB = setbackA / cosineForBothVectors
                reversedVectorA = reverseVector(vA)
                magnifiedVectorA = setVectorMagnitude(reversedVectorA, littleA)
                magnifiedVectorB = setVectorMagnitude(vB, littleB)
                vectorsAdded = addVectors(magnifiedVectorA, magnifiedVectorB)
                skeletonEdgeVector = vectorsAdded  # This should now be the first point's skeleton vector
                # Flip skeleton edge vector on concave nodes.
                turn = self.turnList[index]
                if turn == "concave": # Left turn.
                    skeletonEdgeVector = reverseVector(skeletonEdgeVector)


            self.skeletonEdgeVectorList.append(skeletonEdgeVector)
            nodeBetweenAandB = eA.nodeB
            self.nodeBetweenAandBList.append(nodeBetweenAandB)



            pointForPolygon = movePoint(nodeBetweenAandB, skeletonEdgeVector)
            pointsForPolygon.append(pointForPolygon)
        ###################################################
        testPoints = []
        for indio in range(0, len(self.edgesB)):
            # Show skeleton hip edges.
            edgeB = self.edgesB[indio]
            skeletonVectorForwards = self.skeletonEdgeVectorList[indio]
            testPoint = moveNode(edgeB.nodeA, skeletonVectorForwards)
            testPoints.append(testPoint)
            turn = self.turnList[indio]

        ###################################################

        pintA("Edge collapse test")
        ##########################################
        # Edge collapse test
        skeletonVectorsForwards = self.skeletonEdgeVectorList
        skeletonVectorsBackwards = utils.shiftListForwardsAndWrap(self.skeletonEdgeVectorList)
        distancePerSetbackLowest = proxyForInfinity
        indexOfCollapse = -1
        for index in range(0, len(self.edgesA)):
            #p("len(self.edgesA)",len(self.edgesA))
            testEdge = self.edgesB[index]
            edgeVectorForwards = testEdge.vector
            edgeVectorBackwards = reverseVector(testEdge.vector)
            edgeLength = magnitude(edgeVectorForwards)
            skeletonVectorForwards = skeletonVectorsForwards[index]
            skeletonVectorBackwards = skeletonVectorsBackwards[index]
            # XX ? Should vector below use turn code? Not sure why, but it occured to me.
            edgeNormalVector = normalVector2D(edgeVectorForwards)
            # scalar project skeletonVectorForwards onto on edgeVecForwards, and then for backwards direction.
            #p("magnitude(skeletonVectorForwards)",magnitude(skeletonVectorForwards))
            #p("magnitude(skeletonVectorBackwards)",magnitude(skeletonVectorBackwards))
            #p("magnitude(edgeVectorForwards)",magnitude(edgeVectorForwards))
            #p("magnitude(edgeVectorBackwards)",magnitude(edgeVectorBackwards))

            lengthOfForwardsSkeletonProjectedOntoEdge = scalarProjection(skeletonVectorForwards, edgeVectorForwards)
            lengthOfBackwardsSkeletonProjectedOntoEdge = scalarProjection(skeletonVectorBackwards, edgeVectorBackwards)
            #p("lengthOfForwardsSkeletonProjectedOntoEdge",lengthOfForwardsSkeletonProjectedOntoEdge)
            #p("lengthOfBackwardsSkeletonProjectedOntoEdge",lengthOfBackwardsSkeletonProjectedOntoEdge)
            #p("lengthOfBackwardsSkeletonProjectedOntoEdge",lengthOfBackwardsSkeletonProjectedOntoEdge)
            #pint(22)# XX Can the above statements be combined by using dot product?
            sumOfEdgeAlignedSkeletonVectors = lengthOfForwardsSkeletonProjectedOntoEdge + lengthOfBackwardsSkeletonProjectedOntoEdge
            #p("sumOfEdgeAlignedSkeletonVectors", sumOfEdgeAlignedSkeletonVectors)
            #pint(23)
            if sumOfEdgeAlignedSkeletonVectors == 0:
                # This means the 2 rays are parallel.
                # Their distancePerSetback is infinite.
                distancePerSetback = proxyForInfinity
            else:
                edgeLengthPerSumOfEdgeAlignedSkeletonVectors = edgeLength / sumOfEdgeAlignedSkeletonVectors
                #pint(24)
                finalSkeletonVectorForwards = multiplyVector(skeletonVectorForwards, edgeLengthPerSumOfEdgeAlignedSkeletonVectors)
                #pint(25)
                #finalSkeletonVectorBackwards = multiplyVector(skeletonVectorBackwards, edgeLengthPerSumOfEdgeAlignedSkeletonVectors)
                # Two above vectors will meet at collapse point, except second is not used. I left it there for clarity.
                # Project either one onto the normal to get the t distance.
                #pint(3)
                finalDistance = scalarProjection(finalSkeletonVectorForwards, edgeNormalVector)
                distancePerSetback = finalDistance / testEdge.setback
                #pint(4)
            # Remember the lowest distance per setback.
            if distancePerSetback < distancePerSetbackLowest and distancePerSetback > 0:
                distancePerSetbackLowest = distancePerSetback
                indexOfCollapse = index


        ##########################################
        # NODE POKE test
        pintA("Node Poke test")

        pokeEventAtLowest = proxyForInfinity
        pokeEventIndex = -1
        pokedEdgeIndex = -1

        edgeCount = len(self.edgesA)
        for pokeIndex in range(0, edgeCount):
            # Check if node is concave.
            pokeNode = self.nodeBetweenAandBList[pokeIndex]

            turn = self.turnList[pokeIndex]
            pint("self.turnList[pokeIndex] = " + str(self.turnList[pokeIndex]) + " at pokeIndex " + str(pokeIndex))
            if turn == "concave":
                pokerVector = self.skeletonEdgeVectorList[pokeIndex]

                for edgeIndex in range(0, edgeCount):
                    #eA = self.edgesA[edgeIndex]
                    eB = self.edgesB[edgeIndex]
                    previousEdgeIndex = wrapIndexBackward(edgeIndex, edgeCount)
                    thisEdgeIndex = edgeIndex
                    nextEdgeIndex = wrapIndexForward(edgeIndex, edgeCount)
                    doubleNextEdgeIndex = wrapIndexForward(nextEdgeIndex, edgeCount)


                    # Above is test code.
                    edgeNormalVector = normalVector2D(eB.vector)
                    angleBetweenPokerAndEdgeNormal = angleBetweenTwoVectors(pokerVector,edgeNormalVector)

                    if (angleBetweenPokerAndEdgeNormal > (math.pi / 2)) and not (pokeIndex == previousEdgeIndex or pokeIndex == thisEdgeIndex or pokeIndex == nextEdgeIndex or pokeIndex == doubleNextEdgeIndex):
                        # Testing happens here. All other edges, minus 2 adjacent edges, will test against the poker, unless I find that some others can be ruled out.
                        # This edge has a chance of being hit by the poker.
                        # Vector from edge to poker:
                        edgeNode = self.nodeBetweenAandBList[edgeIndex]
                        edgeNodeToPokerVector = getVectorFromTwoPoints(edgeNode, pokeNode)

                        # Edge Skeleton vector
                        edgeSkeletonVector = self.skeletonEdgeVectorList[edgeIndex]

                        # Project edgeNormalTestVector onto
                        vB = self.vectorsB[edgeIndex]
                        edgeNormalToProjectOnto = crossProduct(vB, Vector(0,0,1))

                        # D = Distance to travel between Edge and Poker
                        distanceBetweenEdgeToPoker = abs(scalarProjection(edgeNodeToPokerVector, edgeNormalToProjectOnto))

                        # N = Skeleton Projected onto Normal (velocity of edge movement)
                        velocityOfEdgeMovement = abs(scalarProjection(edgeSkeletonVector, edgeNormalToProjectOnto))
                        # P = Poker Projected onto Normal (velocity of poker normal to edge)
                        velocityOfPokerNormalToEdge = abs(scalarProjection(pokerVector, edgeNormalToProjectOnto))

                        D = distanceBetweenEdgeToPoker
                        N = velocityOfEdgeMovement
                        P = velocityOfPokerNormalToEdge

                        P_per_N = P / N
                        P_per_N_timesEdgeSetback = P_per_N * eB.setback
                        P_per_N_timesEdgeSetback_plusEdgeSetback = P_per_N_timesEdgeSetback + eB.setback

                        pokeEventAt = D / P_per_N_timesEdgeSetback_plusEdgeSetback

                        # Remember the lowest distance per setback.
                        if pokeEventAt < pokeEventAtLowest and pokeEventAt > 0:
                            pokeEventAtLowest = pokeEventAt
                            pokeEventIndex = pokeIndex
                            pokedEdgeIndex = edgeIndex
                            pint("Edge " + str(edgeIndex) + " got poked at " + str(pokeEventAt) + " by node " + str(pokeIndex))
                edgeIndex += 1



        ###########################################################
        # Handle event outcomes here.
        pintA("Handle Setback Ring Events")
        #pA("pokeEventAtLowest",pokeEventAtLowest)
        #pA("distancePerSetbackLowest",distancePerSetbackLowest)

        lowestEventPerSetback = utils.lesserOf(pokeEventAtLowest, distancePerSetbackLowest)

        # First check if NO event occurs within the setback!
        if lowestEventPerSetback > 1:
            # The next event being greater than 1 means that the event is beyond the setback amount.
            # What if the setback is beyond the final collapse? How is that known?
            # I mean the setbacks can go beyond, and we don't check that now. Chris. Doesn't the first sentence answer the question? Chris, stop talking to yourself in third person.

            pintA("Return Final Polygon")
            finalPolygonPoints = []
            for index in range(0, len(self.edgesB)):
                # Show skeleton hip edges.
                edgeB = self.edgesB[index]
                skeletonVectorForwards = skeletonVectorsForwards[index]
                finalPolygonPoint = moveNode(edgeB.nodeA, skeletonVectorForwards)
                finalPolygonPoints.append(finalPolygonPoint)

            finalPolygon = Polygon(finalPolygonPoints)

            thisFloorPlate = FloorPlate(finalPolygon)
            thisFloorPlate.edgeDataList = self.edgeDataList

            self.returnFloorPlates.append(thisFloorPlate)  # Append on final FloorPlate,

        else:
            # Since lowestEventPerSetback < 1, then this is not the final polygon.
            #################################################
            # INTERMEDIATE EVENT POLYGON FOR EDGE COLLAPSE
            pintA("Edge Collapse on Ring # " + str(self.ringIndex))
            if distancePerSetbackLowest < pokeEventAtLowest:
            #if distancePerSetbackLowest < 1 and originalPolygonNodeCount > 3:
                # An event has happened. If this is the final triangle, that is not handled here.
                # Draw skeleton to point of event.
                # Make that polygon and pass into new Skeleton object.
                for index in range(0, len(self.edgesB)):
                    # Show skeleton hip edges.
                    edgeB = self.edgesB[index]
                    skeletonVectorForwards = skeletonVectorsForwards[index]
                    skeletonVectorForwardsToEventPoint = multiplyVector(skeletonVectorForwards,
                                                                        distancePerSetbackLowest)
                    skeletonPolygonPoint = moveNode(edgeB.nodeA, skeletonVectorForwardsToEventPoint)

                droppedEdgeDistance = distancePerSetbackLowest * self.stepbackValueList[index]
                droppedEdgeData = self.edgeDataList[indexOfCollapse]
                self.returnDroppedEdgeData.append(droppedEdgeData)
                self.returnDroppedEdgeDistances.append(droppedEdgeDistance)
                # Remove collapsed edge.
                self.edgeDataList.pop(indexOfCollapse)
                self.edgesB.pop(indexOfCollapse)
                self.stepbackValueList.pop(indexOfCollapse)
                skeletonVectorsForwards.pop(indexOfCollapse)

                eventPolygonPoints = []

                # Adjust setbacks and position of event points.
                for index in range(0, len(self.edgesB)):
                    edgeB = self.edgesB[index]
                    skeletonVectorForwards = skeletonVectorsForwards[index]
                    eventSkeletonVector = multiplyVector(skeletonVectorForwards, distancePerSetbackLowest)
                    eventPolygonPoint = moveNode(edgeB.nodeA, eventSkeletonVector)
                    eventPolygonPoints.append(eventPolygonPoint)
                # Make new event polygon with blank edges.
                eventPolygon = Polygon(eventPolygonPoints)
                eventPolygon.makeEdges()
                # Put setback values onto edges, using list to send into next skeleton.
                remainingDistancePerSetback = (1 - distancePerSetbackLowest)
                for index in range(0, len(eventPolygon.edges)):
                    self.edgeDataList[index].stepback = self.stepbackValueList[index] * remainingDistancePerSetback


                eventFloorPlate = FloorPlate(eventPolygon)
                eventFloorPlate.edgeDataList = self.edgeDataList


                setbackPerEdge = SetbackPerEdge(eventFloorPlate, self.ringIndex + 1, 0)

                self.returnFloorPlates = setbackPerEdge.getReturnFloorPlates()
                # XX Do we need these?
                self.returnDroppedEdgeData.extend(setbackPerEdge.getReturnDroppedEdgeData())
                self.returnDroppedEdgeDistances.extend(setbackPerEdge.getReturnDroppedEdgeDistances())

            #################################################
            # INTERMEDIATE EVENT POLYGON SPLIT
            elif pokeEventAtLowest < distancePerSetbackLowest:
                pintA("Poke event on Ring # " + str(self.ringIndex))
                pokeEdgeCount = len(self.edgesB)
                # Divide into two polygons here.
                # First get sequence of nodes for each.
                # Start at poke node.
                # Edge index of N starts with node N and ends with node N+1.
                # Edge index of 3 starts with node 3 and ends with node 4.
                # So we want to continue 1,2,3.
                # start with pokeEventIndex, stop at edgeIndex + 1 (keep edge number 3) (stop at 4)

                pokeEventPolygonPoints = []
                for index in range(0, pokeEdgeCount):
                    # Skeleton edges.
                    edgeB = self.edgesB[index]
                    skeletonVectorForwards = skeletonVectorsForwards[index]
                    skeletonVectorForwardsToEventPoint = multiplyVector(skeletonVectorForwards, pokeEventAtLowest)
                    pokeEventPolygonPoint = moveNode(edgeB.nodeA, skeletonVectorForwardsToEventPoint)
                    pokeEventPolygonPoints.append(pokeEventPolygonPoint)
                    # Skeleton vector lines:

                # This is remaining setback amount for all.
                remainingDistancePerSetback = (1 - pokeEventAtLowest)

                # Make polygonA.
                # Start with edge after pokeEventIndex.
                firstPointA = pokeEventPolygonPoints[pokeEventIndex]
                polygonPointsA = []
                polygonPointsA.append(firstPointA)
                firstEdgeDataA = self.edgeDataList[pokeEventIndex]
                firstSegmentIDA = firstEdgeDataA.segmentID
                firstEdgeTypeA = firstEdgeDataA.edgeType
                firstSetbackA = self.edgesB[pokeEventIndex].setback  * remainingDistancePerSetback
                firstEdgeDataA = EdgeData(firstSegmentIDA, firstEdgeTypeA, firstSetbackA)
                edgeDataA = []
                edgeDataA.append(firstEdgeDataA)

                startLoopAt = pokeEventIndex + 1
                loopDex = startLoopAt
                complete = False

                while not complete:
                    # This will wrap it. If poke node was last (6 for example), then if loopDex starts 7, it gets wrapped to 0.
                    if loopDex >= pokeEdgeCount:
                        loopDex = 0
                    # Add point.
                    thisPointA = pokeEventPolygonPoints[loopDex]
                    polygonPointsA.append(thisPointA)

                    existingEdgeDataA = self.edgeDataList[loopDex]
                    existingSegmentIDA = existingEdgeDataA.segmentID
                    existingEdgeTypeA = existingEdgeDataA.edgeType
                    thisSetbackA = self.edgesB[loopDex].setback * remainingDistancePerSetback

                    thisEdgeDataA = EdgeData(existingSegmentIDA, existingEdgeTypeA, thisSetbackA)
                    edgeDataA.append(thisEdgeDataA)

                    # When loopDex gets to edgeIndex of poke, then finish polyA, and exit loop.
                    if loopDex == pokedEdgeIndex:
                        complete = True
                    else:
                        loopDex += 1

                # New Stuff:
                pokeFloorPlateA = FloorPlate(Polygon(polygonPointsA))
                pokeFloorPlateA.edgeDataList = edgeDataA

                setbackPerEdgeA = SetbackPerEdge(pokeFloorPlateA, self.ringIndex + 1, 1)
                returnFloorPlatesA = setbackPerEdgeA.getReturnFloorPlates()
                if returnFloorPlatesA != None and len(returnFloorPlatesA) > 0:
                    self.returnFloorPlates.extend(returnFloorPlatesA)

                    # Is below needed? Will need to embed in FloorPlate probably.
                    self.returnDroppedEdgeData.extend(setbackPerEdgeA.getReturnDroppedEdgeData())
                    self.returnDroppedEdgeDistances.extend(setbackPerEdgeA.getReturnDroppedEdgeDistances())


                # Make polygonB.
                # Start with edge after event node.
                firstPointB = pokeEventPolygonPoints[pokeEventIndex]
                polygonPointsB = []
                polygonPointsB.append(firstPointB)

                firstEdgeDataB = self.edgeDataList[pokedEdgeIndex]
                firstSegmentIDB = firstEdgeDataB.segmentID
                firstEdgeTypeB = firstEdgeDataB.edgeType
                firstSetbackB = self.edgesB[pokedEdgeIndex].setback  * remainingDistancePerSetback
                firstEdgeDataB = EdgeData(firstSegmentIDB, firstEdgeTypeB, firstSetbackB)
                edgeDataB = []
                edgeDataB.append(firstEdgeDataB)

                complete = False
                startLoopAt = pokedEdgeIndex + 1
                loopDex = startLoopAt

                while not complete:
                    # This will wrap it. Even if poke node was last (6 in this case), then loopDex starts 7, and gets wrapped to 0.
                    if loopDex >= pokeEdgeCount:
                        loopDex = 0

                    # When loopDex gets to edgeIndex of poke, then finish polyB, and exit loop.
                    if loopDex == pokeEventIndex:
                        complete = True
                    else:
                        thisPointB = pokeEventPolygonPoints[loopDex]
                        polygonPointsB.append(thisPointB)

                        existingEdgeDataB = self.edgeDataList[loopDex]
                        existingSegmentIDB = existingEdgeDataB.segmentID
                        existingEdgeTypeB = existingEdgeDataB.edgeType
                        thisSetbackB = self.edgesB[loopDex].setback * remainingDistancePerSetback
                        thisEdgeDataB = EdgeData(existingSegmentIDB, existingEdgeTypeB, thisSetbackB)
                        edgeDataB.append(thisEdgeDataB)

                        loopDex += 1


                # Send event polygons into new Skeletons.


                # New Stuff:
                pokeFloorPlateB = FloorPlate(Polygon(polygonPointsB))
                pokeFloorPlateB.edgeDataList = edgeDataB

                setbackPerEdgeB = SetbackPerEdge(pokeFloorPlateB, self.ringIndex + 1, 2)
                returnFloorPlatesB = setbackPerEdgeB.getReturnFloorPlates()
                if returnFloorPlatesB != None and len(returnFloorPlatesB) > 0:
                    self.returnFloorPlates.extend(returnFloorPlatesB)

                    # Is below needed? Will need to embed in FloorPlate probably.
                    self.returnDroppedEdgeData.extend(setbackPerEdgeB.getReturnDroppedEdgeData())
                    self.returnDroppedEdgeDistances.extend(setbackPerEdgeB.getReturnDroppedEdgeDistances())


            else:
                pintA("Warning: WEIRD: unhandled SetbackPerEdge event.")
        pintA("End SetbackPerEdge")
        pass



def SetbackPerEdgeToArea(floorPlate, targetArea, stepbackVariabilityList):
    pintA("Start SetbackPerEdgeToArea search function")
    try:
        completed = False
        maxLoopCount = 30
        areaTolerance = 1/proxyForInfinity
        #originalArea = floorPlate.polygon.getArea()
        #if originalArea < targetArea:
        #    pintA("Error: SetbackPerEdge cannot grow in area. It can only decrease.")
        #    raise Exception
        if len(floorPlate.edgeDataList) != len(stepbackVariabilityList):
            pintA("Error: SetbackPerEdgeToArea has mismatched variability filter for scaling.")
            raise Exception


        # Pull stepbackValueList from floor plate, for ease of integration with old code.
        stepbackValueList = []
        requestedStepbackList = [] # Cannot be shallower values (or bigger floor plate that is).
        edgeDataList = floorPlate.edgeDataList

        for edgeIndex in range(0, len(edgeDataList)):
            edgeData = edgeDataList[edgeIndex]
            stepbackValueList.append(edgeData.stepback)
            requestedStepbackList.append(edgeData.stepback)


        # First run the shape with input stepbacks.
        # If that is smaller than target area already, then keep it.
        try:
            firstSetbackPerEdge = SetbackPerEdge(floorPlate, 0, 0)
        except arcpy.ExecuteError:
            msgs = arcpy.GetMessages(2)
            arcpy.AddError(msgs)
        except Exception:
            e = sys.exc_info()[1]
            arcpy.AddMessage(e.args[0])
            pintA("FAILURE INSIDE SetbackPerEdge", "")
            setbackPerEdge = None

        if firstSetbackPerEdge is None:
            # How many conditions can lead to this?
            pintA("Unhandled Error inside Area Search.")
        elif firstSetbackPerEdge.getArea() < targetArea:
            pintA("No scaling needed.")
            return firstSetbackPerEdge
        else:

            # Else: Need to teach this not to end on area that is slightly larger than target.
            index = 0
            multiplier = 1
            stepSizeToFindUpperRange = 1.5
            previousMultiplier = 0
            setbackPerEdge = None
            upperRangeFound = False
            while not completed and index < maxLoopCount:
                testValueList = []
                for valueIndex in range(0,len(stepbackValueList)):
                    value = stepbackValueList[valueIndex]
                    # Apply variability filter here.
                    if stepbackVariabilityList[valueIndex] is True:
                        testValue = value + multiplier
                    else:
                        testValue = value
                    # Test against min deepness.
                    if testValue < requestedStepbackList[valueIndex]:
                        testValue = requestedStepbackList[valueIndex]

                    testValueList.append(testValue)
                    valueIndex += 1

                # Now add test values back into FloorPlate edgeData.
                # Yes, this does seem like an extra step that could be done above.
                for valueIndex in range(0,len(stepbackValueList)):
                    edgeData = edgeDataList[valueIndex]
                    edgeData.stepback = testValueList[valueIndex]

                try:
                    p("targetArea",targetArea)
                    setbackPerEdge = SetbackPerEdge(floorPlate, 0, 0)
                except arcpy.ExecuteError:
                    msgs = arcpy.GetMessages(2)
                    arcpy.AddError(msgs)
                except Exception:
                    e = sys.exc_info()[1]
                    arcpy.AddMessage(e.args[0])
                    p("FAILURE INSIDE SetbackPerEdge", "")
                    setbackPerEdge = None


                # XX I'm not sure if this is handling None result.
                testArea = 0
                if setbackPerEdge is None: # it either had an unhandled exception, or was too deep a stepback.
                    pint("setbackPerEdge is None.")
                    upperRangeFound = True
                    multiplier = multiplier - (stepSizeToFindUpperRange * 0.5)  # Half of the previous step.
                else:
                    testArea = setbackPerEdge.getArea()
                    p("setbackPerEdge.getArea()",setbackPerEdge.getArea())
                    floorPlatesReturned = setbackPerEdge.getReturnFloorPlates()

                    if floorPlatesReturned is None or len(floorPlatesReturned) == 0:
                        # Must setback less.
                        upperRangeFound = True
                        multiplier = multiplier - (stepSizeToFindUpperRange * 0.5)  # Half of the previous step.
                    elif isWithinTolerance(testArea, targetArea, areaTolerance):
                        completed = True
                    else:
                        stepSize = abs(previousMultiplier - multiplier)
                        # Save previous before altering current for next round.
                        previousMultiplier = multiplier
                        if testArea > targetArea:
                            # Must setback more.
                            if not upperRangeFound:
                                # Here we are climbing faster because we have not past the target yet
                                multiplier = multiplier * stepSizeToFindUpperRange
                            else:
                                multiplier = multiplier + (stepSize * 0.5)
                        else:  # testArea < TARGET:
                            # Must setback less.
                            upperRangeFound = True
                            multiplier = multiplier - (stepSize * 0.5)  # Half of the previous step.
                    index += 1
                    if index > maxLoopCount:
                        completed = True
                        pintA("Max loop count hit in SetbackPerEdge Area.")

            pintA("End getSetbackPerEdgeByArea search function")
            return setbackPerEdge
            # End While.

    except Exception:
        pintA("Failure in SetbackPerEdgeToArea")
        e = sys.exc_info()[1]
        arcpy.AddMessage(e.args[0])
        # After loop, the last value tried is as close as we can get (based on maxloops and tolerance)

