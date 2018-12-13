'''
Created on Jun 7, 2017

@author: chri7180
'''

import time
import arcpy




class Timer(object):
    def __init__(self):
        self.events = []
        self.startTime = time.time()

    class TimerEvent(object):
        def __init__(self, name):
            self.name = name
            self.startTime = time.time()
            self.endTime = None

    def startEvent(self, eventName):
        event = self.TimerEvent(eventName)
        self.events.append(event)
        eventCount = len(self.events)
        if eventCount > 1:
            previousEventIndex = eventCount - 2
            previousEvent = self.events[previousEventIndex]
            # Add end time to previous event.
            previousEvent.endTime = time.time()

    def __str__(self):
        eventCount = len(self.events)
        if eventCount > 1:
            lastEventIndex = eventCount - 1
            lastEvent = self.events[lastEventIndex]
            # Add end time to previous event.
            lastEvent.endTime = time.time()
        # Finish final event
        output = "Event Timer:\r"
        for eventIndex in range(0,len(self.events)):
            event = self.events[eventIndex]
            eventName = event.name
            startTime = event.startTime
            endTime = event.endTime
            timeElapsed = str(round(endTime - startTime, 5))
            output += (eventName + ": \t" + timeElapsed + "\r")

        output += "Total time: " + str(time.time() - self.startTime)
        return output


#############################################
# List utilities

# XX Will need a variable length version of these:
def shiftListForwardsAndWrap(list):
    return list[1:] + list[:1]

def shiftListBackwardsAndWrap(list):
    return list[-1:] + list[:-1]

def listMulti(item,times):
    list = []
    for x in range(0,times):
        list.append(item)
    return list

def pythonListFromStringList(stringList, delimiter):
    stringArray = stringList[:-1].split(delimiter)
    ret = []
    for string in stringArray:
        ret.append(string)
    return ret

def padZeros(number, totalDigits):
    strNumber = "00000000000" + str(number)
    return strNumber[-totalDigits:]

def cgaStringListFromPythonList(pythonList):
    cgaStringList = ""
    for string in pythonList:
        cgaStringList += str(string) + ";"
    return cgaStringList

# In case of equality, first value is returned.
def lesserOf(value1, value2):
    if value1 <= value2: return value1
    else: return value2

# In case of equality, first value is returned.
def greaterOf(value1, value2):
    if value1 >= value2: return value1
    else: return value2








############################################
# Numbers

def nothingLessThanZero(number): 
    if number < 0: 
        return 0
    else: 
        return number



################################################
# Databases
#

def lowerMe(fieldName):
    return fieldName.lower() if "@" not in fieldName else fieldName









##############################################################
# Data access helpers for tables and feature classes.


# FieldAccess: This object is used for building search queries, and accessing field values.
# init - fieldList is all of the fields you want in the search cursor. 
# setRow - use during cursor to access that cursor's values.
# getValue - used during cursor to access value by field name (rather than by row number).


class FieldAccess(object):

    def __init__(self, fieldList):
        self.row = None
        self.fieldList = [field.lower() if "@" not in field else field for field in fieldList]
        self.fieldDictionary = {}
        fieldIndex = 0
        for fieldName in self.fieldList:
            self.fieldDictionary[fieldName] = fieldIndex
            fieldIndex += 1

    def setRow(self, row):
        self.row = row


    def getValue(self, fieldName):
        fieldName = fieldName.lower() if "@" not in fieldName else fieldName
        if fieldName in self.fieldList:
            return self.row[self.fieldDictionary[fieldName]]
        else:
            return None


class NewRow(object):

    def __init__(self):
        self.fieldInsertDictionary = {}

    def setFieldNames(self, fieldNameList):
        for fieldName in fieldNameList:
            self.fieldInsertDictionary[lowerMe(fieldName)] = None

    def set(self, fieldName, fieldValue):
        self.fieldInsertDictionary[lowerMe(fieldName)] = fieldValue

    def getFieldNamesList(self):
        return list(self.fieldInsertDictionary.keys())

    # Note: below use of dictionary is not affected by unordered nature of dictionary.
    def getFieldValuesList(self):
        ret = []
        fieldNamesList = list(self.fieldInsertDictionary.keys())
        for fieldName in fieldNamesList:
            ret.append(self.fieldInsertDictionary.get(fieldName))
        return ret

    def addFields(self, fieldInsertDictionary):
        self.fieldInsertDictionary.update(fieldInsertDictionary)

