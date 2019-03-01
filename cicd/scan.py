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
import shutil

#################################################################################################
class Scan:
    def __init__(self, scmUrl, token, userName, project, repository, exclude, excludeRepositories, outputFile, pullRequest, inputCommitDepth, entropy, verbose, exitWithError):
        self.scmUrl = scmUrl
        self.token = token
        self.userName = userName
        self.project = project
        self.repository= repository
        self.outputFile= outputFile
        self.pullRequest = pullRequest
        self.inputCommitDepth = inputCommitDepth
        self.entropy = entropy
        self.verbose = verbose
        self.exitWithError = exitWithError
        if exclude != None:
            self.exclude = exclude.split(",")
        else:
            self.exclude = []
        if excludeRepositories != None:
            self.excludeRepositories = excludeRepositories.split(",")
        else:
            self.excludeRepositories = []
        if self.verbose:
            logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.DEBUG)
        else:
            logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)
    def _getRepositories(self):
        bitbucket = Bitbucket(self.scmUrl, self.token, self.userName, self.project, self.repository, self.pullRequest)
        return (bitbucket._getRepositories())
    def _getPRCommitDepth(self):
        if self.inputCommitDepth != None:
            return self.inputCommitDepth
        elif self.pullRequest != None:
            bitbucket = Bitbucket(self.scmUrl, self.token, self.userName, self.project, self.repository, self.pullRequest)
            return (bitbucket._getPRCommitDepth())
        else:
            return ""
    def _executeTruffleHog(self, repositories, commitDepth):
        if os.path.exists("truffleHog"):
            shutil.rmtree("truffleHog", ignore_errors=True)
        os.makedirs("truffleHog")
        truffleHogOutputFiles = {}
        logging.info("Total repositories found - " + str(len(repositories)))
        for index, repositoryName in enumerate(repositories):
            repository = repositories[repositoryName]
            if repositoryName in self.excludeRepositories:
                logging.info("["+str(index)+"]" + " Skipping execution for " + repositoryName)
                continue
            if commitDepth != "":
                logging.info("Setting Commit Depth to - " + commitDepth)
                logging.info("Setting branch to - refs/pull-requests/" + self.pullRequest + "/merge")
                logging.info("["+str(index+1)+"]" + " Executing truffleHog for " + repositoryName + " ...")
                os.system("/usr/local/bin/trufflehog --regex --json --branch=refs/pull-requests/" + self.pullRequest + "/merge --max_depth=" + commitDepth + " --entropy=" + self.entropy + " " + repository + " > truffleHog/" + repositoryName + ".json")
            else:
                logging.info("["+str(index+1)+"]" + " Executing truffleHog for " + repositoryName + " ...")
                os.system("/usr/local/bin/trufflehog --regex --json --entropy=" + self.entropy + " " + repository + " > truffleHog/" + repositoryName + ".json")
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
        truffleHogExcelSummarydata = list()
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
        if totalFiles > 0:
            truffleHogExcelSummarydata.append([self.project, repositoryName, totalFiles, ", ".join(reasonsFound)])
            print("======================================================")
            print("Total files having secret information - ", str(totalFiles))
            print("Secret types:", ", ".join(reasonsFound))
            print("\"git rm\" comand will not help to clean as it will present in history")
            print("Follow to remove from history - https://help.github.com/articles/removing-sensitive-data-from-a-repository")
            print("======================================================")
        else:
            print("======================================================")
            print("[PASSED] There are no files having secrets")
            print("======================================================")
        return truffleHogExceldata, truffleHogExcelSummarydata
    def _excelReportInitiator(self):
        workbook = xlsxwriter.Workbook(self.outputFile.name, {'strings_to_formulas': False, 'strings_to_urls': False})
        worksheetSummary = workbook.add_worksheet("Summary")
        worksheetDetails = workbook.add_worksheet("Details")
        logging.debug("Writting report to - " + self.outputFile.name )
        formatText = workbook.add_format()
        formatText.set_text_wrap()
        formatText.set_align('top')
        merge_format = workbook.add_format({'font_size': 15, 'bold': 1, 'border': 1, 'valign': 'vcenter', 'fg_color': 'silver'})
        todaysDate = datetime.date.today().strftime("%B %d, %Y")
        
        worksheetSummary.set_tab_color('#339966')
        worksheetSummary.set_column('A:A', 15, formatText)
        worksheetSummary.set_column('B:B', 25, formatText)
        worksheetSummary.set_column('C:C', 10, formatText)
        worksheetSummary.set_column('D:D', 60, formatText)
        worksheetSummary.merge_range('A1:D1', "Secrets found in below files    Report Generated: "+todaysDate, merge_format)
        
        worksheetDetails.set_tab_color('#339966')
        worksheetDetails.set_column('A:A', 8, formatText)
        worksheetDetails.set_column('B:B', 15, formatText)
        worksheetDetails.set_column('C:C', 50, formatText)
        worksheetDetails.set_column('D:D', 20, formatText)
        worksheetDetails.set_column('E:E', 20, formatText)
        worksheetDetails.set_column('F:F', 12, formatText)
        worksheetDetails.set_column('G:G', 40, formatText)
        worksheetDetails.set_column('H:H', 20, formatText)
        worksheetDetails.merge_range('A1:H1', "Secrets found in below files    Report Generated: "+todaysDate, merge_format)
        return workbook, worksheetSummary, worksheetDetails

    def _excelReport(self, workbook, worksheetDetails, truffleHogExceldata, worksheetSummary, truffleHogExcelSummarydata):
        dataRangeDefect = "A2:H" + str(len(truffleHogExceldata) + 2)
        worksheetDetails.add_table(
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

        dataRangeSummary = "A2:D" + str(len(truffleHogExcelSummarydata) + 2)
        worksheetSummary.add_table(
            dataRangeSummary, 
            {'data': truffleHogExcelSummarydata,
				'columns': [
                    {'header': 'Project'},
                    {'header': 'Repository'},
                    {'header': 'File Count'},
                    {'header': 'Secret Type'},
                ]
            }
        )
        return workbook

    def scan(self):
        truffleHogExceldataSets = []
        if self.outputFile != None:
            workbook, worksheetSummary, worksheetDetails = self._excelReportInitiator()
        repositories = self._getRepositories()
        commitDepth = self._getPRCommitDepth()
        truffleHogOutPutFiles = self._executeTruffleHog(repositories, commitDepth)
        for repositoryName in truffleHogOutPutFiles:
            truffleHogOutPutFile = truffleHogOutPutFiles[repositoryName]
            truffleHogResults = self._readInputFile(truffleHogOutPutFile)
            truffleHogResultFiltered = self._parseResult(truffleHogResults)
            truffleHogExceldata, truffleHogExcelSummarydata = self._print(repositoryName, truffleHogResultFiltered)
            truffleHogExceldataSets = truffleHogExceldataSets + truffleHogExceldata
        if self.outputFile != None:
            workbook = self._excelReport(workbook, worksheetDetails, truffleHogExceldataSets, worksheetSummary, truffleHogExcelSummarydata)
            workbook.close()
            logging.info("Report saved to - " + self.outputFile.name )
        if len(truffleHogExceldataSets) > 0:
            if self.exitWithError:
                print("======================================================")
                print("[FAILED] There are files having secrets")
                print("======================================================")
                sys.exit(2)

#################################################################################################
class Bitbucket:
    def __init__(self, scmUrl, token, userName, project, repository, pullRequest):
        self.scmUrl = scmUrl
        self.token = token
        self.userName = userName
        self.apiUrl = scmUrl + "/rest/api/latest/"
        self.project = project
        self.repository = repository
        self.pullRequest = pullRequest
    def _getRepositories(self):
        repositories = {}
        urlWithoutHttps = self.scmUrl
        if urlWithoutHttps.startswith("https://"):
            urlWithoutHttps = urlWithoutHttps.replace("https://", "")
        if self.repository != None:
            repository = "https://"+self.userName+":"+self.token+"@"+urlWithoutHttps+"/scm/"+self.project+"/"+self.repository+".git"
            repositories[self.repository] = repository
            return repositories
        logging.debug("Getting all repositories for - " + self.scmUrl + " for project " + self.project)
        header = {'Authorization': 'Bearer ' + self.token}
        response = requests.get(self.apiUrl + "projects/" + self.project + "/repos?limit=500", headers=header)
        rawRepositoryData = response.json()
        for entry in rawRepositoryData["values"]:
            repositories[entry["slug"]] = "https://"+self.userName+":"+self.token+"@"+urlWithoutHttps+"/scm/"+self.project+"/"+entry["slug"]+".git"
        return repositories
    def _getPRCommitDepth(self):
        logging.debug("Getting commit depth for - " + self.scmUrl + " for project - " + self.project + " Pull Request ID - " + self.pullRequest)
        header = {'Authorization': 'Bearer ' + self.token}
        response = requests.get(self.apiUrl + "projects/" + self.project + "/repos/" + self.repository + "/pull-requests/" + self.pullRequest + "/commits?limit=500", headers=header)
        return str(response.json()["size"])

#################################################################################################
def main(args):
    scmUrl, token, userName, project, repository, exclude, excludeRepositories, outputFile, pullRequest, inputCommitDepth, entropy, verbose, exitWithError = get_args()
    scan = Scan(scmUrl, token, userName, project, repository, exclude, excludeRepositories, outputFile, pullRequest, inputCommitDepth, entropy, verbose, exitWithError)
    scan.scan()

#################################################################################################
def get_args():
    '''This function parses and return arguments passed in'''
    parser = argparse.ArgumentParser(description='scan.py: Execute and parse report of truffleHog')
    parser.add_argument('-s', '--scm', type=str, help='SCM parent URL for scaning (Mandatory) ENV: SCM_URL', required=False)
    parser.add_argument('-t', '--token', type=str, help='SCM OAuth Token (Mandatory) ENV: BITBUCKET_LOGIN', required=False)
    parser.add_argument('-u', '--userName', type=str, help='SCM User Name (Mandatory) ENV: DRONE_NETRC_USERNAME', required=False)
    parser.add_argument('-p', '--project', type=str, help='Project/Owner Name (Mandatory) ENV: DRONE_REPO_OWNER', required=False)
    parser.add_argument('-r', '--repository', type=str, help='Repository Name, if not mentioned all repositories will be scanned ENV: DRONE_REPO_NAME', required=False)
    parser.add_argument('-e', '--exclude', type=str, help='Excluded files patterns coma (,) separated ENV: EXCLUDE_FILE_PATTERN', required=False)
    parser.add_argument('-er', '--excludeRepositories', type=str, help='Excluded repositories coma (,) separated ENV: EXCLUDED_REPOSITORIES', required=False)
    parser.add_argument('-o', '--output', type=argparse.FileType('w'), help='Store result to mentioned report file (Microsoft Excel)', required=False)
    parser.add_argument('-pr', '--pullRequest', type=str, help='Enable diff based scan for Pull Request ENV: CI_PULL_REQUEST', required=False)
    parser.add_argument('-cd', '--commitDepth', type=str, help='Enable diff based scan for commit depth ENV: DRONE_BUILD_EVENT', required=False)
    parser.add_argument('-en', '--entropy',type=str, help='Enable (default) or disable entropy ENV: TRUFFLEHOG_ENTROPY', required=False)
    parser.add_argument('-v', '--verbose', help='Verbose output for debug', required=False, action='store_true')
    parser.add_argument('-ex', '--exit', help='Exit with error if any secrets found ENV: RAISE_ERROR', required=False, action='store_true')
    parser.set_defaults(entropy="True")
    parser.set_defaults(verbose=False)
    parser.set_defaults(exit=False)

    args = parser.parse_args()
    scmUrl = args.scm
    token = args.token
    userName = args.userName
    project = args.project
    repository = args.repository
    exclude = args.exclude
    excludeRepositories = args.excludeRepositories
    outputFile = args.output
    pullRequest = args.pullRequest
    inputCommitDepth = args.commitDepth
    entropy = args.entropy
    verbose = args.verbose
    exitWithError = args.exit

    # Take env variables for Drone
    if scmUrl == None:
        scmUrl = os.getenv('SCM_URL')
    if exclude == None:
        exclude == os.getenv('EXCLUDE_FILE_PATTERN')
    if excludeRepositories == None:
        excludeRepositories = os.getenv('EXCLUDED_REPOSITORIES')
    if entropy == None:
        entropy = os.getenv('TRUFFLEHOG_ENTROPY')
    if token == None:
        token = os.getenv('BITBUCKET_LOGIN')
    if userName == None:
        userName = os.getenv('DRONE_NETRC_USERNAME')
    if project == None:
        project = os.getenv('DRONE_REPO_OWNER')
    if repository == None:
        repository = os.getenv('DRONE_REPO_NAME')
    if pullRequest == None:
        pullRequest = os.getenv('CI_PULL_REQUEST')
    if inputCommitDepth == None:
        if os.getenv('DRONE_BUILD_EVENT') == "push":
            inputCommitDepth = "1"
    if exitWithError == False:
        exitWithError = (os.getenv('RAISE_ERROR', default="False") == "True")
    
    # Validate mandatory parameters
    if scmUrl == None:
        print("Missing mandatory parameter: --scm")
        sys.exit(1)
    if token == None:
        print("Missing mandatory parameter: --token")
        sys.exit(1)
    if userName == None:
        print("Missing mandatory parameter: --userName")
        sys.exit(1)
    if project == None:
        print("Missing mandatory parameter: --project")
        sys.exit(1)

    return scmUrl,token,userName,project,repository,exclude,excludeRepositories,outputFile,pullRequest,inputCommitDepth,entropy,verbose,exitWithError

#################################################################################################
#################################################################################################
if __name__ == '__main__':
	main(sys.argv[1:])