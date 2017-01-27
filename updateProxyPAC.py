#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function
import sys
import argparse
import hashlib
import gzip
import difflib
import StringIO

import requests
import pacparser


#Create an argument parser and add our arguments
parser = argparse.ArgumentParser(description="Utility to retrieve, update, and test the PAC file")
parser.add_argument("-v", "--verbose", dest="verbose", help="Turn on debug output", action="store_true")
parser.add_argument("-U", "--url", dest="url", help="URL from which to retrieve the PAC file")
parser.add_argument("-O", "--outfile", dest="outfile", help="Change output file location.", default="testProxy.pac")
parser.add_argument("-n", "--noout", dest="noout", help="Do not write the resulting output file", action="store_false")
args=parser.parse_args()

#If verbose flag is specified, print verbose messages, otherwise make it a null function
verboseprint = print if args.verbose else lambda *a, **k: None

#Set the URL of the master PAC file and URL for PAC testing
url = args.url
outputFile = args.outfile

verboseprint("Retrieving PAC file: {}".format(url))
#Attempt to retrieve the current PAC file, break if it doesn't work
requestHeaders = {'User-Agent': 'pacupdater','Connection':'close'}

try:
    r = requests.get(url, headers=requestHeaders)
except requests.exceptions.RequestException as e:
    print("Error retrieving PAC file:")
    print(e)
    sys.exit(1)
else:
    verboseprint("Retrieved {} bytes from: {}".format(len(r.content),url))

verboseprint("Status code: {} Content type: {}".format(r.status_code, r.headers["content-type"]))

#Check response from webserver before attempting to parse PAC file
if r.status_code == 200 and r.headers["content-type"] == "application/x-ns-proxy-autoconfig":
    verboseprint("Status code and content type match expected values...")
    if len(r.content) >= 0:
        parsePAC = True
elif len(r.content) == 0:
    print("ERROR: File not found. Exiting...")
    parsePAC = False
elif r.status_code == 404:
    print("ERROR: File not found. Exiting...")
    parsePAC = False
else:
    print("Undefined Error. Exiting...")
    parsePAC = False

if not parsePAC:
    sys.exit(1)

#Attempt to parse retrieved PAC file
try:
    pacparser.init()
    pacparser.parse_pac_string(r.content)
except Exception as e:
    print("Unable to parse PAC file.  Exiting...")
    print(e)
    sys.exit(1)
else:
    verboseprint("PAC Parsing Successful.")
finally:
    pacparser.cleanup()

#Optionally write the output file
if args.noout:
    #Function for writing the output file
    def writeOutputFile(filePath, contents):
        try:
            with open(filePath, "w") as f:
                print("Writing output file: {}".format(filePath))
                f.write(contents)
        except Exception as e:
            print("ERROR: Unable to write output: {}".format(e))
            sys.exit(1)

    #Function for compressing the old file
    def archiveOldFile(filePath):
        print("Compressing old file: {0} to: {0}.gz".format(filePath))
        with open(filePath) as f_in, gzip.open(filePath + ".gz", 'wb') as f_out:
            f_out.writelines(f_in)

    #Function for diffing changes to local PAC
    def diffPAC(oldPACfile, newPACcontents):
        print("Generating diff from changes: ")
        try:
            with open(oldPACfile) as file_to_diff:
                oldPACcontents = file_to_diff.read()
        except:
            print("Unable to diff")
        else:
            buffNew = StringIO.StringIO(newPACcontents)
            buffOld = StringIO.StringIO(oldPACcontents)
            diff = difflib.context_diff(buffOld.readlines(), buffNew.readlines())
            print("".join(diff))

    #If old file exists, hash it to compare to current download
    try:
        with open(outputFile) as file_to_hash:
            data = file_to_hash.read()
    except IOError as e:
        verboseprint("Error opening file, must not exist")
        oldPAC = False
        updatePAC = True
    else:
        oldPAC = True
        md5Old = hashlib.md5(data).hexdigest()
        md5New = hashlib.md5(r.content).hexdigest()
        verboseprint("Hash of old PAC: {}".format(md5Old))
        verboseprint("Hash of new PAC: {}".format(md5New))
        if md5Old == md5New:
            updatePAC = False
        else:
            updatePAC = True

    #Check conditions and handle accordingly
    if oldPAC and not updatePAC:
        verboseprint("Hashes match, exiting...")
    elif oldPAC and updatePAC:
        print("Hashes do not match, will update local copy...")
        diffPAC(outputFile, r.content)
        archiveOldFile(outputFile)
        writeOutputFile(outputFile, r.content)
    elif not oldPAC and updatePAC:
        print("Creating local copy...")
        writeOutputFile(outputFile, r.content)

#Finally, we made it!
sys.exit(0)
