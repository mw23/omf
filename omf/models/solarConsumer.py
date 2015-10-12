''' Calculate solar costs and benefits for consumers. '''

import json, os, sys, webbrowser, shutil, subprocess
from matplotlib import pyplot as plt
from datetime import datetime as dt
from datetime import timedelta as td
from os.path import join as pJoin
from jinja2 import Template
import __metaModel__
from __metaModel__ import *
import traceback
# OMF imports
sys.path.append(__metaModel__._omfDir)
import feeder
from solvers import nrelsam2013
from weather import zipCodeToClimateName

# Our HTML template for the interface:
with open(pJoin(__metaModel__._myDir,"solarConsumer.html"),"r") as tempFile:
	template = Template(tempFile.read())

def renderTemplate(template, modelDir="", absolutePaths=False, datastoreNames={}):
	return __metaModel__.renderTemplate(template, modelDir, absolutePaths, datastoreNames)

def quickRender(template, modelDir="", absolutePaths=False, datastoreNames={}):
	''' Presence of this function indicates we can run the model quickly via a public interface. '''
	return __metaModel__.renderTemplate(template, modelDir, absolutePaths, datastoreNames, quickRender=True)

def run(modelDir, inputDict):
	try:
		''' Run the model in its directory. '''
		# Check whether model exist or not
		if not os.path.isdir(modelDir):
			os.makedirs(modelDir)
			inputDict["created"] = str(dt.now())
		# MAYBEFIX: remove this data dump. Check showModel in web.py and renderTemplate()
		with open(pJoin(modelDir, "allInputData.json"),"w") as inputFile:
			json.dump(inputDict, inputFile, indent = 4)
		# Copy spcific climate data into model directory
		inputDict["climateName"], latforpvwatts = zipCodeToClimateName(inputDict["zipCode"])
		shutil.copy(pJoin(__metaModel__._omfDir, "data", "Climate", inputDict["climateName"] + ".tmy2"),
			pJoin(modelDir, "climate.tmy2"))
		# Ready to run
		startTime = dt.now()
		# Set up SAM data structures.
		ssc = nrelsam2013.SSCAPI()
		dat = ssc.ssc_data_create()
		# Required user inputs.
		ssc.ssc_data_set_string(dat, "file_name", modelDir + "/climate.tmy2")
		ssc.ssc_data_set_number(dat, "system_size", float(inputDict["SystemSize"]))
		# SAM options where we take defaults.
		ssc.ssc_data_set_number(dat, "derate", 0.97)
		ssc.ssc_data_set_number(dat, "track_mode", 0)
		ssc.ssc_data_set_number(dat, "azimuth", 180)
		ssc.ssc_data_set_number(dat, "tilt_eq_lat", 1)
		# Run PV system simulation.
		mod = ssc.ssc_module_create("pvwattsv1")
		ssc.ssc_module_exec(mod, dat)
		# Set the timezone to be UTC, it won't affect calculation and display, relative offset handled in pvWatts.html
		startDateTime = "2013-01-01 00:00:00 UTC"
		# Timestamp output.
		outData = {}
		outData["timeStamps"] = [dt.strftime(
			dt.strptime(startDateTime[0:19],"%Y-%m-%d %H:%M:%S") +
			td(**{"hours":x}),"%Y-%m-%d %H:%M:%S") + " UTC" for x in range(int(8760))]
		# HACK: makes it easier to calculate some things later.
		outData["pythonTimeStamps"] = [dt(2012,1,1,0) + x*td(hours=1) for x in range(8760)]
		# Geodata output.
		outData["city"] = ssc.ssc_data_get_string(dat, "city")
		outData["state"] = ssc.ssc_data_get_string(dat, "state")
		outData["lat"] = ssc.ssc_data_get_number(dat, "lat")
		outData["lon"] = ssc.ssc_data_get_number(dat, "lon")
		outData["elev"] = ssc.ssc_data_get_number(dat, "elev")
		# Weather output.
		outData["climate"] = {}
		outData["climate"]["Global Horizontal Radiation (W/m^2)"] = ssc.ssc_data_get_array(dat, "gh")
		outData["climate"]["Plane of Array Irradiance (W/m^2)"] = ssc.ssc_data_get_array(dat, "poa")
		outData["climate"]["Ambient Temperature (F)"] = ssc.ssc_data_get_array(dat, "tamb")
		outData["climate"]["Cell Temperature (F)"] = ssc.ssc_data_get_array(dat, "tcell")
		outData["climate"]["Wind Speed (m/s)"] = ssc.ssc_data_get_array(dat, "wspd")
		# Power generation.
		outData["powerOutputAc"] = ssc.ssc_data_get_array(dat, "ac")

		# TODO: INSERT TJ CODE BELOW
		tjCode(inputDict, outData)
		del outData["pythonTimeStamps"]
		# TODO: INSERT TJ CODE ABOVE

		# Stdout/stderr.
		outData["stdout"] = "Success"
		outData["stderr"] = ""
		# Write the output.
		with open(pJoin(modelDir,"allOutputData.json"),"w") as outFile:
			json.dump(outData, outFile, indent=4)
		# Update the runTime in the input file.
		endTime = dt.now()
		inputDict["runTime"] = str(td(seconds=int((endTime - startTime).total_seconds())))
		with open(pJoin(modelDir,"allInputData.json"),"w") as inFile:
			json.dump(inputDict, inFile, indent=4)
	except:
		# If input range wasn't valid delete output, write error to disk.
		cancel(modelDir)
		thisErr = traceback.format_exc()
		print 'ERROR IN MODEL', modelDir, thisErr
		inputDict['stderr'] = thisErr
		with open(os.path.join(modelDir,'stderr.txt'),'w') as errorFile:
			errorFile.write(thisErr)
		with open(pJoin(modelDir,"allInputData.json"),"w") as inFile:
			json.dump(inputDict, inFile, indent=4)

def cancel(modelDir):
	''' solarConsumer runs so fast it's pointless to cancel a run. '''
	pass

def tjCode(inputs, outData):
	# Make inputs the right types.
	for k in inputs.keys():
		if k not in ['quickRunEmail','modelType','meteringType','modelName', 'monthlyDemand','user','created','runTime','climateName']:
			inputs[k] = float(inputs[k])
	inputs['years'] = int(inputs['years'])
	inputs['monthlyDemand'] = [float(x) for x in inputs['monthlyDemand'].split(',')]
	# Associate solar output with time
	monthlySolarOutput = zip(outData["powerOutputAc"],outData["pythonTimeStamps"])
	outData["monthlySolarGen"] = []
	for y in range(1,13):
		monthSum = sum([x[0] for x in monthlySolarOutput if x[1].month == y])
		#convert to kWh
		monthSum = monthSum / 1000
		outData["monthlySolarGen"].append(monthSum)
	# Calculate monthly energy use for all cases.
	totalEnergyUse=[]
	totalSolarGen=[]
	for z in range(inputs['years']):
		totalEnergyUse.extend([x-y for x,y in zip(inputs["monthlyDemand"],outData["monthlySolarGen"])])
		totalSolarGen.extend(outData["monthlySolarGen"])
		outData["monthlySolarGen"] = [.995*x for x in outData["monthlySolarGen"]]
	# Calculating monthly bills for all cases.
	monthlyBillsBaseCase = []
	monthlyBillsComS = []
	monthlyBillsRoof = []
	monthlyBillsGrid3rdParty = []
	monthlyBillsSolar3rdParty = []
	monthlyBills3rdParty = []
	# Variables for goal seeking on.
	retailRate = inputs["retailRate"]
	PartyRate = inputs["3rdPartyRate"]
	#Calculate Net Energy Metering Scenario:
	if inputs["meteringType"]=='netEnergyMetering':
		for x in range(inputs['years']):
			for y in range(1,13):
				monthlyBillsBaseCase.append(retailRate * inputs['monthlyDemand'][y-1])
				monthlyBillsComS.append(retailRate * totalEnergyUse[x*12+y-1]+inputs["comMonthlyCharge"])
				monthlyBillsRoof.append(retailRate * totalEnergyUse[x*12+y-1]+inputs["utilitySolarMonthlyCharge"])
				monthlyBills3rdParty.append(retailRate * totalEnergyUse[x*12+y-1]+PartyRate * totalSolarGen[x*12+y-1]+inputs["utilitySolarMonthlyCharge"])
			retailRate = retailRate*(1+inputs["rateIncrease"]/100)
			PartyRate = PartyRate*(1+inputs["3rdPartyRateIncrease"]/100)
	#Calculate Production Metering Scenario
	elif inputs["meteringType"]=='production':
		for x in range(inputs['years']):
			for y in range(1,13):
				monthlyBillsBaseCase.append(retailRate * inputs['monthlyDemand'][y-1])
				monthlyBillsComS.append(retailRate * inputs['monthlyDemand'][y-1]+inputs["comMonthlyCharge"] - inputs['valueOfSolarRate']*totalSolarGen[x*12+y-1])
				monthlyBillsRoof.append(retailRate * inputs['monthlyDemand'][y-1]+inputs["utilitySolarMonthlyCharge"] - inputs['valueOfSolarRate']*totalSolarGen[x*12+y-1])
				monthlyBills3rdParty.append(retailRate * totalEnergyUse[x*12+y-1]+PartyRate * totalSolarGen[x*12+y-1]+inputs["utilitySolarMonthlyCharge"])
			retailRate = retailRate*(1+inputs["rateIncrease"]/100)
			PartyRate = PartyRate*(1+inputs["3rdPartyRateIncrease"]/100)
	#Calculate Excess Metering Scenario
	elif inputs["meteringType"]=='excessEnergyMetering':
		for x in range(inputs['years']):
			for y in range(1,13):
				if totalEnergyUse[x*12+y-1]>0:
					monthlyBillsBaseCase.append(retailRate * inputs['monthlyDemand'][y-1])
					monthlyBillsComS.append(retailRate * inputs['monthlyDemand'][y-1]+inputs["comMonthlyCharge"] - inputs['valueOfSolarRate']*totalSolarGen[x*12+y-1])
					monthlyBillsRoof.append(retailRate * inputs['monthlyDemand'][y-1]+inputs["utilitySolarMonthlyCharge"] - inputs['valueOfSolarRate']*totalSolarGen[x*12+y-1])
					monthlyBills3rdParty.append(retailRate * totalEnergyUse[x*12+y-1]+PartyRate * totalSolarGen[x*12+y-1]+inputs["utilitySolarMonthlyCharge"])
				else:
					excessSolar=abs(totalEnergyUse[x*12+y-1])
					monthlyBillsBaseCase.append(retailRate * inputs['monthlyDemand'][y-1])
					monthlyBillsComS.append(retailRate * inputs['monthlyDemand'][y-1]+inputs["comMonthlyCharge"] - inputs['valueOfSolarRate']*excessSolar)
					monthlyBillsRoof.append(retailRate * inputs['monthlyDemand'][y-1]+inputs["utilitySolarMonthlyCharge"] - inputs['valueOfSolarRate']*excessSolar)
					monthlyBills3rdParty.append(retailRate * totalEnergyUse[x*12+y-1]+PartyRate * totalSolarGen[x*12+y-1]+inputs["utilitySolarMonthlyCharge"])
			retailRate = retailRate*(1+inputs["rateIncrease"]/100)
			PartyRate = PartyRate*(1+inputs["3rdPartyRateIncrease"]/100)
	# Add upfront costs to the first month.
	monthlyBillsComS[0]+= inputs["comUpfrontCosts"]
	monthlyBillsRoof[0]+= inputs["roofUpfrontCosts"]
	# Average monthly bill calculation:
	outData["avgMonthlyBillBaseCase"] = sum(monthlyBillsBaseCase)/len(monthlyBillsBaseCase)
	outData["avgMonthlyBillComS"] = sum(monthlyBillsComS)/len(monthlyBillsComS)
	outData["avgMonthlyBillRoof"] = sum(monthlyBillsRoof)/len(monthlyBillsRoof)
	outData["avgMonthlyBill3rdParty"] = sum(monthlyBills3rdParty)/len(monthlyBills3rdParty)
	# Total energy cost calculation:
	outData["totalCostBaseCase"] = sum(monthlyBillsBaseCase)
	outData["totalCostComS"] = sum(monthlyBillsComS)
	outData["totalCostRoof"] = sum(monthlyBillsRoof)
	outData["totalCost3rdParty"] = sum(monthlyBills3rdParty)
	#Cost per kWh
	outData["kWhCostBaseCase"]=outData["totalCostBaseCase"]/sum(inputs["monthlyDemand"]*inputs["years"])
	outData["kWhCostComS"]=outData["totalCostComS"]/sum(inputs["monthlyDemand"]*inputs["years"])
	outData["kWhCost3rdParty"]=outData["totalCost3rdParty"]/sum(inputs["monthlyDemand"]*inputs["years"])
	outData["kWhCostRoof"]=outData["totalCostRoof"]/sum(inputs["monthlyDemand"]*inputs["years"])
	# Total Savings Money saved compared to base case:
	outData["totalSavedByComS"] = outData["totalCostBaseCase"] - outData["totalCostComS"]
	outData["totalSavedBy3rdParty"] = outData["totalCostBaseCase"] - outData["totalCost3rdParty"]
	outData["totalSavedByRoof"] = outData["totalCostBaseCase"] - outData["totalCostRoof"]
	#Lists of cumulative Costs
	outData['cumulativeBaseCase'] = cumulativeBaseCase = [sum(monthlyBillsBaseCase[0:i+1]) for i,d in enumerate(monthlyBillsBaseCase)]
	outData['cumulativeComS'] = cumulativeComS = [sum(monthlyBillsComS[0:i+1]) for i,d in enumerate(monthlyBillsComS)]
	outData['cumulative3rdParty'] = cumulative3rdParty = [sum(monthlyBills3rdParty[0:i+1]) for i,d in enumerate(monthlyBills3rdParty)]
	outData['cumulativeRoof'] = cumulativeRoof = [sum(monthlyBillsRoof[0:i+1]) for i,d in enumerate(monthlyBillsRoof)]
	#When does communtiy solar and others beat the base case?
	#Calculate Simple Payback of solar options
	def spp(cashflow):
		''' Years to pay back the initial investment. Or -1 if it never pays back. '''
		for i, val in enumerate(cashflow):
				net = sum(cashflow[0:i+1])
				if net >= 0:
						return i + (abs(float(cashflow[i-1]))/val)
		return -1
	outData["sppComS"] = spp([x-y for x,y in zip(monthlyBillsBaseCase, monthlyBillsComS)])/12
	outData["spp3rdParty"] = spp([x-y for x,y in zip(monthlyBillsBaseCase, monthlyBills3rdParty)])/12
	outData["sppRoof"] = spp([x-y for x,y in zip(monthlyBillsBaseCase, monthlyBillsRoof)])/12
	# Green electron calculations:
	sumDemand = sum(inputs["monthlyDemand"])*inputs['years']
	sumSolarGen = sum(totalSolarGen)
	sumSolarDemandDif = sumDemand - sumSolarGen
	if sumSolarGen>= sumDemand:
		outData["greenElectrons"]=100
	else:
		outData["greenElectrons"]=(sumSolarDemandDif/sumDemand)*inputs["greenFuelMix"]+(sumSolarGen/sumDemand)*100
	# Lifetime costs to the consumer graph:
	plt.figure()
	plt.title('Lifetime Energy Costs')
	plt.bar([1,2,3,4],[outData["totalCostBaseCase"],outData["totalCostComS"],outData["totalCost3rdParty"],outData["totalCostRoof"]])
	plt.ylabel('Cost ($)')
	plt.xticks([1.4,2.4,3.4,4.4], ['No Solar','Community Solar','Leased Rooftop','Purchased Rooftop'])
	# # Monthly bills graph:
	# plt.figure()
	# plt.title('Monthly Bills')
	# plt.plot(monthlyBillsBaseCase, color ="black")
	# plt.plot(monthlyBillsComS, color ="blue")
	# plt.plot(monthlyBills3rdParty, color ="red")
	# plt.plot(monthlyBillsRoof, color ="yellow")
	# Cumulative consumer costs over time graph:
	plt.figure()
	plt.title('Cumulative Costs')
	plt.plot(cumulativeBaseCase, color='black', label='No Solar')
	plt.plot(cumulativeComS, color='blue', label='Community Solar')
	plt.plot(cumulative3rdParty, color='red', label='Leased Rooftop')
	plt.plot(cumulativeRoof, color='orange', label='Purchased Rooftop')
	plt.legend(loc='upper left')
	# All other outputs in data table:
	plt.figure()
	plt.title('Costs By Purchase Type')
	plt.axis('off')
	plt.table(
		loc='center',
		rowLabels=["Base Case", "Community Solar", "Rooftop Solar", "3rd Party Solar"],
		colLabels=["Total Cost","Total Saved", "Average Monthly Cost", "$/kWh", "Simple Payback Period", "Green Electrons"],
		cellText=[
			[outData["totalCostBaseCase"],"Not Available", outData["avgMonthlyBillBaseCase"],outData["kWhCostBaseCase"], "Not Available",inputs["greenFuelMix"]],
			[outData["totalCostComS"],outData["totalSavedByComS"], outData["avgMonthlyBillComS"],outData["kWhCostComS"], outData["sppComS"], outData["greenElectrons"]],
			[outData["totalCostRoof"],outData["totalSavedByRoof"], outData["avgMonthlyBillRoof"],outData["kWhCostRoof"], outData["sppRoof"], outData["greenElectrons"]],
			[outData["totalCost3rdParty"],outData["totalSavedBy3rdParty"], outData["avgMonthlyBill3rdParty"],outData["kWhCost3rdParty"], outData["spp3rdParty"], outData["greenElectrons"]]])
	# plt.show()

def _tests():
	# Variables
	workDir = pJoin(__metaModel__._omfDir,"data","Model")
	inData = {
		'modelType':'solarConsumer',
		'zipCode':64735,
		'SystemSize':9,
		'meteringType':
			'netEnergyMetering', # Total cost reduced by total solar gen * retail rate.
			#'production', # Total cost reduced by total solar gen * wholesale rate.
			#'excessEnergyMetering', # Total cost reduced by total solar gen * retail rate; but, if generation exceeds demand (over the life of the system), only get paid wholesale rate for the excess.
		'years':25,
		'retailRate':0.11,
		'valueOfSolarRate':.07,
		'monthlyDemand':'3000,3000,3000,3000,3000,3000,3000,3000,3000,3000,3000,3000',
		'rateIncrease':2.5,
		'roofUpfrontCosts':17500,
		'utilitySolarMonthlyCharge':0,
		'3rdPartyRate':0.09,
		'3rdPartyRateIncrease':3.5,
		'comUpfrontCosts':10000,
		'comMonthlyCharge':10,
		'comRate':0,
		'comRateIncrease':0,
		'greenFuelMix':12}
	modelLoc = pJoin(workDir,"admin","Automated solarConsumer Testing")
	# Blow away old test results if necessary.
	try:
		shutil.rmtree(modelLoc)
	except:
		# No previous test results.
		pass
	# No-input template.
	# renderAndShow(template)
	# Run the model.
	run(modelLoc, inData)
	# Show the output.
	renderAndShow(template, modelDir = modelLoc)
	# # Delete the model.
	# time.sleep(2)
	# shutil.rmtree(modelLoc)

if __name__ == '__main__':
	_tests()