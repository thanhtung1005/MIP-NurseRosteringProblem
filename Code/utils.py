import xml.etree.ElementTree as ET

import numpy as np

from datetime import timedelta


def getTreeAttribute(attrib: str, tree: ET.Element, attributeType = str) -> list:
    """
        Arg:
            tree: a data tree
            attrib: attribute want to get
            attributeType: data type of attribute
        Return:
            a list of attribute in data tree
    """
    attribList = [attributeType(node.attrib[attrib]) for node in tree]
    return attribList

def getFixAssignments(fixAssignmentsTree: ET.Element) -> list:
    fixAssignmentsList = []
    for fixAssignment in fixAssignmentsTree:
        employee = fixAssignment[0].text
        day = int(fixAssignment[1][1].text)
        fixAssignmentsList.append((employee, day))
    return fixAssignmentsList

def getRequests(requestsTree: ET.Element) -> list:
    shiftOnRequestsList = []
    for shiftOnRequest in requestsTree:
        employee = shiftOnRequest[1].text
        shift = shiftOnRequest[0].text
        day = int(shiftOnRequest[2].text)
        weight = int(shiftOnRequest.get('weight'))
        shiftOnRequestsList.append((employee, shift, day, weight))
    return shiftOnRequestsList

def getCoverRequirementsDict(coverRequirementsTree: ET.Element) -> dict:
    coverRequirementsDict = {}
    for coverRequirements in coverRequirementsTree:
        day = int(coverRequirements[0].text)
        coverRequirementsDict[day] = {}
        for coverRequirement in coverRequirements.findall('Cover'):
            shift = coverRequirement[0].text
            belowPreferredCoverWeight = int(coverRequirement[1].get('weight'))
            abovePreferredCoverWeight = int(coverRequirement[2].get('weight'))
            preferredCover = int(coverRequirement[1].text)
            coverRequirementsDict[day][shift] = (belowPreferredCoverWeight,
                                                 abovePreferredCoverWeight,
                                                 preferredCover)
    return coverRequirementsDict


class Employees:

    def __init__(self, employeesTree: ET.Element) -> None:
        self.ids = getTreeAttribute(attrib='ID', tree=employeesTree)


class Shifts:

    def __init__(self, shiftTree: ET.Element, minRestTime: int) -> None:
        self.ids = getTreeAttribute(attrib='ID', tree=shiftTree)
        self.duration = []
        startTimeList = []
        for shift in shiftTree:
            self.duration.append(int(shift[2].text))
            hour, minute = shift[1].text.split(':')
            startTimeList.append(timedelta(hours=int(hour), minutes=int(minute)))
        self.getShiftRotationList(startTimeList, minRestTime)

    def getShiftRotationList(self, startTimeList, minRestTime: int) -> None:
        self.shiftRotationList = []
        for i in range(len(self.ids)):
            totalTimeToNextShift = minRestTime + self.duration[i]
            timeToStartNextShift = startTimeList[i] + timedelta(minutes=totalTimeToNextShift)
            shiftRotation = []
            for j in range(i + 1):
                if i != j:
                    if timeToStartNextShift > startTimeList[j]:
                        shiftRotation.append(j)
            self.shiftRotationList.append(shiftRotation)


class Contracts:

    def __init__(self, contractsTree: ET.Element) -> None:
        self.ids = getTreeAttribute(attrib='ID', tree=contractsTree)
        self.getConstraintsDict(contractsTree)
        self.constraintsDict.pop('All')

    def getConstraintsDict(self, contractsTree: ET.Element) -> None:

        self.constraintsDict = {}
        for id in self.ids:
            self.constraintsDict[id] = {}

        for i in range(len(self.ids)):
            # Get max number of consecutive working days
            for maxSeq in contractsTree[i].findall('MaxSeq'):
                value = int(maxSeq.get('value'))
                shiftType = maxSeq.get('shift')
                self.constraintsDict[self.ids[i]]['maxConsecutiveShift'] = value
            for minSeq in contractsTree[i].findall('MinSeq'):
                value = int(minSeq.get('value'))
                shiftType = minSeq.get('shift')
                # Get min number of consecutive working days
                if shiftType == '$':
                    self.constraintsDict[self.ids[i]]['minConsecutiveShift'] = value
                # Get min number of consecutive day-offs
                elif shiftType == '-':
                    self.constraintsDict[self.ids[i]]['minConsecutiveDayOff'] = value
                else:
                    raise ValueError('Unknow shift type')

            # Get max number of each shift of each type
            if len(contractsTree[i].findall('MaxTot')) > 0:
                self.constraintsDict[self.ids[i]]['maxTot'] = []
            for maxTot in contractsTree[i].findall('MaxTot'):
                value = int(maxTot.get('value'))
                shiftType = maxTot.get('shift')
                self.constraintsDict[self.ids[i]]['maxTot'].append((shiftType, value))

            # Get min and max working time
            for workload in contractsTree[i].findall('Workload'):
                self.constraintsDict[self.ids[i]]['maxWorkTime'] = int(workload[0][0][0].text)
                self.constraintsDict[self.ids[i]]['minWorkTime'] = int(workload[1][0][0].text)

            # Get max working weekend
            for pattern in contractsTree[i].findall('Patterns'):
                self.constraintsDict[self.ids[i]]['maxWeekend'] = int(pattern[0][0][0].text)

            # Get valid shift
            for validShifts in contractsTree[i].findall('ValidShifts'):
                self.constraintsDict[self.ids[i]]['validShifts'] = validShifts.get('shift').split(',')[:-1]

def getSolutionFromFile(solutionTree: ET.Element, employees: Employees, shifts: Shifts, numberOfDays: int):
    solution = np.zeros(shape=(len(employees.ids), len(shifts.ids), numberOfDays))
    for e in solutionTree.findall('Employee'):
        employeeId = employees.ids.index(e.get('ID'))
        for a in e.findall('Assign'):
            d = int(a[0].text.strip())
            s = int(shifts.ids.index(a[1].text.strip()))
            solution[employeeId, s, d] = 1
    return solution
