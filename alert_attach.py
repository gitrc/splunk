#!/usr/bin/python
#
# alert_attach.py - This script is intended to be called from the 'Run a script' feature in Splunk Alerts
#		    The script will take a search parameter from the 'description' field of the Splunk Alert
#		    and perform another search whose output will be included as an attachment in the email
#
#                   Requires splunk-python-sdk
#
# Rod Cordova  (@gitrc)
#

import os
import sys
import subprocess
import smtplib
import gzip
import re
import csv
from StringIO import StringIO

from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText

# gather the variables passed by splunk
splunk_scriptname = sys.argv[0]
splunk_eventcount = sys.argv[1]
splunk_searchterm = sys.argv[2]
splunk_fqs	  = sys.argv[3]
splunk_reportname = sys.argv[4]
splunk_trigger    = sys.argv[5]
splunk_url	  = sys.argv[6]
splunk_deprecated = sys.argv[7]
splunk_filepath   = sys.argv[8]

# populate the email_to and secondary search from saved search parameters
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from splunklib.client import connect

try:
    from utils import parse
except ImportError:
    raise Exception("Add the SDK repository to your PYTHONPATH to run the examples "
                    "(e.g., export PYTHONPATH=~/splunk-sdk-python.")


opts = parse(sys.argv[1:], {}, ".splunkrc")
service = connect(**opts.kwargs)

# Retrieve the saved search
mysavedsearch = service.saved_searches[splunk_reportname]

# Retrieve individual parameters to feed our script
email_recipients = mysavedsearch["action.email.to"]
email_to = re.split(r"\s*[,;]\s*", email_recipients.strip())
new_search = mysavedsearch["description"]
earliest_time = mysavedsearch["dispatch.earliest_time"]
latest_time = "now"

email_from = "splunk@example.com"

# Create message container - the correct MIME type is multipart/alternative.
msg = MIMEMultipart('mixed')
msg['Subject'] = "Splunk Alert: " + splunk_reportname
msg['From'] = email_from
msg['To'] = ", ".join(email_to)

# Create the body of the message
csv_file = gzip.open(splunk_filepath,"rb").read()

# generate table contents
html = '<table border=1>'
reader = csv.DictReader(StringIO(csv_file))

# setup the list of columns we care about
columns = '_raw,host'.split(',')

# start processing
rownum = 0
for row in reader:
	# write header row. assumes first row in csv contains header
	if rownum == 0:
		html += ('<tr>') # write <tr> tag
		for column in columns:
			html += '<th>' + column + '</th>'
  		html += '</tr>'

  	#write all other rows	
  	else:
		html += '<tr>'
		for column in columns:
			html += '<td>' + row[column] + '</td>'
		html += '</tr>'
	
	#increment row count	
	rownum += 1

html += '</table>'

# Record the MIME types of part1
part1 = MIMEText(html, 'html')

# Attach parts into message container
msg.attach(part1)

# This is the logfile attachment which will be generated from the secondary search

# Set the parameters for the search:
# - Display the first 10 results
kwargs_oneshot = {"earliest_time": earliest_time,
                  "latest_time": latest_time,
                  "output_mode": "raw"}
searchquery_oneshot = "search " + new_search
oneshotsearch_results = service.jobs.oneshot(searchquery_oneshot, **kwargs_oneshot)

# Record the MIME types of part2
part2 = MIMEApplication(str(oneshotsearch_results))
part2.add_header('Content-Disposition', 'attachment', filename="log.txt")

# Attach parts into message container
msg.attach(part2)

# Send the message via local SMTP server
s = smtplib.SMTP('localhost')
s.sendmail(email_from, email_to, msg.as_string())
s.quit()
