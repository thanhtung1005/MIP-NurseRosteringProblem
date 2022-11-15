import sys
import xml.etree.ElementTree as ET

from datetime import datetime
from itertools import product
from pathlib import Path

import gurobipy as gp

from gurobipy import GRB
from utils import Contracts, Employees,Shifts

from utils import getFixAssignments, getRequests, getCoverRequirementsDict

instancePath = sys.argv[1]
shiftSchedulingDataPath = Path(instancePath)
shiftSchedulingData = ET.parse(shiftSchedulingDataPath).getroot()

# Get total day of schedule
startDayNode = 0
endDayNode = 1
shiftTypesNode = 2
contractsNode = 3
employeesNode = 4
fixAssignmentsNode = 5
shiftOnRequestsNode = 6
shiftOffRequestsNode = 7
coverRequirementsNode = 8

# Get total days
startDay = datetime.strptime(shiftSchedulingData[startDayNode].text, '%Y-%m-%d').date()
endDay = datetime.strptime(shiftSchedulingData[endDayNode].text, '%Y-%m-%d').date()
numberOfDays = (endDay - startDay).days + 1

# Get min rest time
minRestTime = int(shiftSchedulingData[contractsNode][0][0].text)

# Get shifts object
shiftTree = shiftSchedulingData[shiftTypesNode]
shifts = Shifts(shiftTree, minRestTime)

# Get contracts object
contractsTree = shiftSchedulingData[contractsNode]
contracts = Contracts(contractsTree=contractsTree)

# Get emplyees object
employeesTree = shiftSchedulingData[employeesNode]
employees = Employees(employeesTree=employeesTree)

model = gp.Model('EmployeeTimetabling')
model.setParam('DisplayInterval', 500)
model.setParam('Method', 1)

numberOfEmployees = len(employees.ids)
numberOfShifts = len(shifts.ids)
x = model.addMVar(shape=(len(employees.ids), len(shifts.ids), numberOfDays), vtype=GRB.BINARY)

# An employee cannot be assigned  more than one shift on a single day
for e, d in product(range(numberOfEmployees), range(numberOfDays)):
    model.addConstr(gp.quicksum(x[e, s, d] for s in range(numberOfShifts)) <= 1)

# Shift Rotation
for i in range(len(shifts.shiftRotationList)):
    if shifts.shiftRotationList[i]:
        for e, d in product(range(numberOfEmployees), range(numberOfDays - 1)):
            leftHandSide = x[e, i, d] + gp.quicksum(x[e, j, d + 1] for j in shifts.shiftRotationList[i])
            model.addConstr(leftHandSide <= 1)

numberOfWeeks = int(numberOfDays / 7)
k = model.addMVar(shape=(numberOfEmployees, numberOfWeeks), vtype=GRB.BINARY)
for i, e in enumerate(employees.ids):
    for key, value in contracts.constraintsDict[e].items():
        if key == 'maxConsecutiveShift':
            for d in range(numberOfDays - value):
                leftHandSide = gp.quicksum(x[i, s, d + gap]
                                           for s in range(numberOfShifts)
                                           for gap in range(value + 1))
                model.addConstr(leftHandSide <= value)

        elif key == 'minConsecutiveShift':
            for d in range(numberOfDays - value):
                sum1 = (value - 1) * gp.quicksum(x[i, s, d + 1] for s in range(numberOfShifts))
                sum2 = gp.quicksum(x[i, s, k]
                                   for s in range(numberOfShifts)
                                   for k in range(d + 2, d + value + 1))
                leftHandSide = sum1 - sum2
                rightHandSide = (value - 1) * gp.quicksum(x[i, s, d] for s in range(numberOfShifts))
                model.addConstr(leftHandSide <= rightHandSide)
            # If employees start working on the last days
            for d in range(numberOfDays - value, numberOfDays - 1):
                gap = numberOfDays - d - 1
                sum1 = (gap - 1) * gp.quicksum(x[i, s, d + 1] for s in range(numberOfShifts))
                sum2 = gp.quicksum(x[i, s, k] for s in range(numberOfShifts) for k in range(d + 2, d + gap + 1))
                leftHandSide = sum1 - sum2
                rightHandSide = (gap - 1) * gp.quicksum(x[i, s, d] for s in range(numberOfShifts))
                model.addConstr(leftHandSide <= rightHandSide)

        elif key == 'minConsecutiveDayOff':
            for d in range(numberOfDays - value):
                sum1 = (value - 1) * gp.quicksum(x[i, s, d + 1] for s in range(numberOfShifts))
                sum2 =  gp.quicksum(x[i, s, k] for s in range(numberOfShifts) for k in range(d + 2, d + value + 1))
                leftHandSide = sum1 - sum2
                rightHandSide = (value - 1) * gp.quicksum(x[i, s, d] for s in range(numberOfShifts))
                model.addConstr(leftHandSide + value -1 >= rightHandSide)

            for d in range(numberOfDays - value, numberOfDays - 1):
                gap = numberOfDays - d - 1
                sum1 = (gap - 1) * gp.quicksum(x[i, s, d + 1] for s in range(numberOfShifts))
                sum2 = gp.quicksum(x[i, s, k] for s in range(numberOfShifts) for k in range(d + 2, d + gap + 1))
                leftHandSide = sum1 - sum2
                rightHandSide = (gap - 1) * gp.quicksum(x[i, s, d] for s in range(numberOfShifts))
                model.addConstr(leftHandSide + gap - 1>= rightHandSide)

        elif key == 'maxWorkTime':
            leftHandSide = gp.quicksum(shifts.duration[s] * x[i, s, d]
                                       for s in range(numberOfShifts)
                                       for d in range(numberOfDays))
            model.addConstr(leftHandSide <= value)
        elif key == 'minWorkTime':
            leftHandSide = gp.quicksum(shifts.duration[s] * x[i, s, d]
                                       for s in range(numberOfShifts)
                                       for d in range(numberOfDays))
            model.addConstr(leftHandSide >= value)
        elif key == 'maxWeekend':
            for w in range(1, numberOfWeeks + 1):
                sumWorkingSaturday = gp.quicksum(x[i, s, 7 * w-2] for s in range(numberOfShifts))
                sumWorkingSunday = gp.quicksum(x[i, s, 7 * w-1] for s in range(numberOfShifts))
                model.addConstr(sumWorkingSaturday + sumWorkingSunday >= k[i, w-1])
                model.addConstr(sumWorkingSaturday + sumWorkingSunday <= 2 * k[i, w-1])
            model.addConstr(gp.quicksum(k[i, w] for w in range(numberOfWeeks)) <= value)
        elif key == 'validShifts':
            unvalidShift = [shifts.ids.index(shift)
                            for shift in shifts.ids
                            if shift not in value]
            if unvalidShift:
                for s, d in product(unvalidShift, range(numberOfDays)):
                    model.addConstr(x[i, s, d] == 0)
        elif key == 'maxTot':
            for shift, maxShifts in value:
                leftHandSide = gp.quicksum(x[i, shifts.ids.index(shift), d]
                                           for d in range(numberOfDays))
                model.addConstr(leftHandSide <= maxShifts)
        else:
            raise ValueError('Invalid key')

# Get fix assignments
fixAssignmentsTree = shiftSchedulingData[fixAssignmentsNode]
fixAssignmentsList = getFixAssignments(fixAssignmentsTree)

for e, d in fixAssignmentsList:
    for s in range(numberOfShifts):
        model.addConstr(x[employees.ids.index(e), s, d] == 0)

# Get shift on requests
shiftOnRequestsTree = shiftSchedulingData[shiftOnRequestsNode]
shiftOnRequestsList = getRequests(shiftOnRequestsTree)
shiftOnRequestsObjective = gp.quicksum(w*x[employees.ids.index(e), shifts.ids.index(s), d]
                                      for e, s, d, w in shiftOnRequestsList)

# Get shift off requests
shiftOffRequestsTree = shiftSchedulingData[shiftOffRequestsNode]
shiftOffRequestsList = getRequests(shiftOffRequestsTree)
shiftOffRequestsObjective = gp.quicksum(w*(1 - x[employees.ids.index(e), shifts.ids.index(s), d])
                                      for e, s, d, w in shiftOffRequestsList)

# Get cover requirements
coverRequirementsTree = shiftSchedulingData[coverRequirementsNode]
coverRequirementsDict = getCoverRequirementsDict(coverRequirementsTree)

y = model.addMVar(shape=(numberOfShifts, numberOfDays), vtype=GRB.INTEGER, name='y')
z = model.addMVar(shape=(numberOfShifts, numberOfDays), vtype=GRB.INTEGER, name='z')

# Represen y, x
for d in range(numberOfDays):
    for s in range(numberOfShifts):
        leftHandSide = gp.quicksum(x[e, s, d] for e in range(numberOfEmployees)) + y[s, d] - z[s, d]
        model.addConstr(leftHandSide == coverRequirementsDict[d][shifts.ids[s]][-1])

belowPreferredObjective = gp.quicksum(coverRequirementsDict[d][shifts.ids[s]][0]*y[s, d]
                                      for s in range(numberOfShifts) for d in range(numberOfDays))

abovePreferredObjective = gp.quicksum(coverRequirementsDict[d][shifts.ids[s]][1]*z[s, d]
                                      for s in range(numberOfShifts) for d in range(numberOfDays))

model.setObjective(shiftOnRequestsObjective + shiftOffRequestsObjective + belowPreferredObjective + abovePreferredObjective, GRB.MINIMIZE)

model.optimize()
