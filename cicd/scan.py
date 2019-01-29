#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import sys
import logging
import json
import re
import xlsxwriter
import datetime
import os
import requests

#################################################################################################
class Scan:
    def __init__(self, scmUrl, token, project, repository, exclude, outputFile, verbose):
        self.scmUrl = scmUrl
        self.token = token
        self.project = project
        self.repository= repository
        self.outputFile= outputFile
        self.verbose = verbose
        if exclude != None:
            self.exclude = exclude.split(",")
        else:
            self.exclude = []
        if self.verbose:
            logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.DEBUG)
        else:
            logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)
    def _getRepositories(self):
        bitbucket = Bitbucket(self.token, self.scmUrl, self.project, self.repository)
        return (bitbucket._getRepositories())
    def _executeTruffleHog(self, repositories):
        truffleHogOutputFiles = {}
        for repositoryName in repositories:
            repository = repositories[repositoryName]
            logging.info("Executing truffleHog for " + repository + " ...")
            if not os.path.exists("truffleHog"):
                os.makedirs("truffleHog")
            os.system("truffleHog --regex --json " + repository + " > truffleHog/" + repositoryName + ".json")
            truffleHogOutputFiles[repositoryName] = "truffleHog/" + repositoryName + ".json"
        return truffleHogOutputFiles
    def _readInputFile(self, inputJson):
        truffleHogResults = []
        logging.debug("Reading file - " + inputJson)
        with open(inputJson, 'r') as f:
            for line in f:
                truffleHogResults.append(json.loads(line))
        return truffleHogResults
    def _parseResult(self, truffleHogResults):
        truffleHogResultFiltered = {}
        logging.debug("Parsing result")
        for truffleHogResult in truffleHogResults:
            excludeMatch = False
            for excludePatternString in self.exclude:
                excludePattern = re.compile(excludePatternString)
                if excludePattern.match(truffleHogResult["path"]):
                    excludeMatch = True
            if excludeMatch:
                continue
            if truffleHogResult["path"] not in truffleHogResultFiltered:
                truffleHogResultFiltered[truffleHogResult["path"]] = {}
            if truffleHogResult["reason"] not in truffleHogResultFiltered[truffleHogResult["path"]]:
                truffleHogResultFiltered[truffleHogResult["path"]][truffleHogResult["reason"]] = {}
            if truffleHogResult["stringsFound"][0] not in truffleHogResultFiltered[truffleHogResult["path"]][truffleHogResult["reason"]]:
                truffleHogResultFiltered[truffleHogResult["path"]][truffleHogResult["reason"]][truffleHogResult["stringsFound"][0]] = {
                    "commitCount" : 0,
                    "commitHash" : truffleHogResult["commitHash"],
                    "commit" : truffleHogResult["commit"],
                    "branch" : truffleHogResult["branch"],
                }
            else:
                truffleHogResultFiltered[truffleHogResult["path"]][truffleHogResult["reason"]][truffleHogResult["stringsFound"][0]]["commitCount"] += 1
        return truffleHogResultFiltered
    def _print(self, repositoryName, truffleHogResultFiltered):
        logging.debug("Printing result")
        truffleHogExceldata = list()
        reasonsFound = []
        totalFiles = 0
        for path in truffleHogResultFiltered:
            totalFiles += 1
            logging.warning(repositoryName + " : secret found in - " + path)
            for reason in truffleHogResultFiltered[path]:
                logging.debug("  reason - " + reason)
                if reason not in reasonsFound:
                    reasonsFound.append(reason)
                for secret in truffleHogResultFiltered[path][reason]:
                    secretDetails = truffleHogResultFiltered[path][reason][secret]
                    logging.debug("    secret - " + secret)
                    logging.debug("      commitCount - " + str(secretDetails["commitCount"]))
                    logging.debug("      lastCommitHash - " + secretDetails["commitHash"])
                    logging.debug("      branch - " + secretDetails["branch"])
                    truffleHogExceldata.append([self.project, repositoryName, path, reason, secret, secretDetails["commitCount"], secretDetails["commitHash"], secretDetails["branch"]])
        print("======================================================")
        print("Total files having secret information - ", str(totalFiles))
        print("Secret types:", ", ".join(reasonsFound))
        print("\"git rm\" comand will not help to clean as it will present in history")
        print("Follow to remove from history - https://help.github.com/articles/removing-sensitive-data-from-a-repository")
        print("======================================================")
        return truffleHogExceldata
    def _excelReportInitiator(self):
        workbook = xlsxwriter.Workbook(self.outputFile.name, {'strings_to_formulas': False, 'strings_to_urls': False})
        worksheetAllDefect = workbook.add_worksheet(self.project)
        logging.debug("Writting report to - " + self.outputFile.name )
        formatText = workbook.add_format()
        formatText.set_text_wrap()
        formatText.set_align('top')
        merge_format = workbook.add_format({'font_size': 15, 'bold': 1, 'border': 1, 'valign': 'vcenter', 'fg_color': 'silver'})
        todaysDate = datetime.date.today().strftime("%B %d, %Y")
        worksheetAllDefect.set_tab_color('#339966')
        worksheetAllDefect.set_column('A:A', 8, formatText)
        worksheetAllDefect.set_column('B:B', 15, formatText)
        worksheetAllDefect.set_column('C:C', 50, formatText)
        worksheetAllDefect.set_column('D:D', 20, formatText)
        worksheetAllDefect.set_column('E:E', 20, formatText)
        worksheetAllDefect.set_column('F:F', 12, formatText)
        worksheetAllDefect.set_column('G:G', 40, formatText)
        worksheetAllDefect.set_column('H:H', 20, formatText)
        worksheetAllDefect.merge_range('A1:H1', "Secrets found in below files    Report Generated: "+todaysDate, merge_format)
        return workbook, worksheetAllDefect

    def _excelReport(self, workbook, worksheetAllDefect, truffleHogExceldata):
        dataRangeDefect = "A2:H" + str(len(truffleHogExceldata) + 2)
        worksheetAllDefect.add_table(
            dataRangeDefect, 
            {'data': truffleHogExceldata,
				'columns': [
                    {'header': 'Project'},
                    {'header': 'Repository'},
                    {'header': 'File'},
                    {'header': 'Secret Type'},
                    {'header': 'Secret'},
                    {'header': 'Commit Count'},
                    {'header': 'Last Commit'},
                    {'header': 'Branch'},
                ]
            }
        )
        return workbook

    def scan(self):
        if self.outputFile != None:
            workbook, worksheetAllDefect = self._excelReportInitiator()
            truffleHogExceldataSets = []
        repositories = self._getRepositories()
        truffleHogOutPutFiles = self._executeTruffleHog(repositories)
        for repositoryName in truffleHogOutPutFiles:
            truffleHogOutPutFile = truffleHogOutPutFiles[repositoryName]
            truffleHogResults = self._readInputFile(truffleHogOutPutFile)
            truffleHogResultFiltered = self._parseResult(truffleHogResults)
            truffleHogExceldata = self._print(repositoryName, truffleHogResultFiltered)
            if self.outputFile != None:
                truffleHogExceldataSets = truffleHogExceldataSets + truffleHogExceldata
        if self.outputFile != None:
            workbook = self._excelReport(workbook, worksheetAllDefect, truffleHogExceldataSets)
            workbook.close()
            logging.info("Report saved to - " + self.outputFile.name )

#################################################################################################
class Bitbucket:
    def __init__(self, token, scmUrl, project, repository):
        self.token = token
        self.scmUrl = scmUrl
        self.apiUrl = scmUrl + "/rest/api/latest/"
        self.project = project
        self.repository = repository
    def _getRepositories(self):
        repositories = {}
        if self.repository != None:
            repository = self.scmUrl + "/scm/" + self.project + "/" + self.repository + ".git"
            repositories[self.repository] = repository
            return repositories
        logging.debug("Getting all repositories for - " + self.scmUrl + " for project " + self.project)
        header = {'Authorization': 'Bearer ' + self.token}
        response = requests.get(self.apiUrl + "projects/" + self.project + "/repos?limit=500", headers=header)
        rawRepositoryData = response.json()
        for entry in rawRepositoryData["values"]:
            repositories[entry["slug"]] = self.scmUrl + "/scm/" + self.project + "/" + entry["slug"] + ".git"
        return repositories

#################################################################################################
def main(args):
    scmUrl, token, project, repository, exclude, outputFile, verbose = get_args()
    scan = Scan(scmUrl, token, project, repository, exclude, outputFile, verbose)
    scan.scan()

#################################################################################################
def get_args():
    '''This function parses and return arguments passed in'''
    parser = argparse.ArgumentParser(description='scan.py: Execute and parse report of truffleHog')
    parser.add_argument('-s', '--scm', type=str, help='SCM parent URL for scaning', required=True)
    parser.add_argument('-t', '--token', type=str, help='SCM OAuth Token', required=True)
    parser.add_argument('-p', '--project', type=str, help='Project/Owner Name', required=True)
    parser.add_argument('-r', '--repository', type=str, help='Repository Name, if not mentioned all repositories will be scanned', required=False)
    parser.add_argument('-e', '--exclude', type=str, help='Excluded files patterns coma (,) separated', required=False)
    parser.add_argument('-o', '--output', type=argparse.FileType('w', encoding='UTF-8'), help='Store result to mentioned report file (Microsoft Excel)', required=False)
    parser.add_argument('-v', '--verbose', help='Verbose output for debug', required=False, action='store_true')
    parser.set_defaults(summary=True)
    parser.set_defaults(verbose=False)
    args = parser.parse_args()
    scmUrl = args.scm
    token = args.token
    project = args.project
    repository = args.repository
    exclude = args.exclude
    outputFile = args.output
    verbose = args.verbose
    return scmUrl,token,project,repository,exclude,outputFile,verbose

#################################################################################################
#################################################################################################
if __name__ == '__main__':
	main(sys.argv[1:])