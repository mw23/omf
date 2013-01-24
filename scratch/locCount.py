#!/usr/bin/env python


''' 
Count the number of lines of code in this project. Ignores the data stores and libraries, etc.
I was at 2.5 kLOC as of 2012-10-24.
At 12kLOC as of 2013-01-24. Wow!
'''

import os

def cleanList(inList):
	goodSuffixes = ['py','js','htm','html']
	libraries = ['d3.v2.js','highcharts.min.js','jquery-1.8.3.min.js']
	return [x for x in inList if (x.split('.')[-1] in goodSuffixes and x not in libraries)]

def lineCount(fileName):
	with open(fileName) as openFile:
		for x, y in enumerate(openFile):
			pass
	return x + 1

def recursiveFileList(direct):
	fileList = []
	for x in os.walk(direct):
		fileList = fileList + [x[0] + '\\' + fPath for fPath in x[2]]
	return fileList

allSource = cleanList(recursiveFileList('..'))
lineCountList = map(lineCount, allSource)

print sum(lineCountList)
