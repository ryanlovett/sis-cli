sis
===
Query the UC Berkeley Student Information System (SIS) for enrollment and
instructor data.

Requires SIS API credentials.

People
------
```
usage: sis people [-h] -y YEAR -s {spring,summer,fall} -n CLASS_NUMBER
                  [-c {enrolled,waitlisted,instructors,gsis}] [--exact]

optional arguments:
  -h, --help            show this help message and exit
  -y YEAR               course year, e.g. 2019
  -s {spring,summer,fall}
                        semester
  -n CLASS_NUMBER       class section number, e.g. 14720
  -c {enrolled,waitlisted,instructors,gsis}
                        course constituents
  --exact               exclude data from sections with matching subject and
                        code.
```

Sections
--------
```
usage: sis section [-h] -y YEAR -s {spring,summer,fall} -n CLASS_NUMBER -a
                   {subject_area,catalog_number,display_name,is_primary}

optional arguments:
  -h, --help            show this help message and exit
  -y YEAR               course year, e.g. 2019
  -s {spring,summer,fall}
                        semester
  -n CLASS_NUMBER       class section number, e.g. 14720
  -a {subject_area,catalog_number,display_name,is_primary}
                        semester
```

Example
-------
Get waitlisted IDs for a lab section in summer 2019:

`sis people -y 2019 -s summer -n 14024 -c waitlisted --exact`

Get all GSI IDs for a lecture in spring 2019. We omit `--exact` so that we match
all sections with the same subject area and catalog number, e.g. STAT C8:

`sis people -y 2019 -s spring -n 14035 -c gsis`

Credentials
-----------
sis authenticates to various SIS endpoints. Supply the credentials in a
JSON file of the form:
```
{
	"enrollments_id": "...",
	"enrollments_key": "...",
	"classes_id": "...",
	"classes_key": "...",
	"terms_id": "...",
	"terms_key": "...",
}
```
Request credentials for the SIS Enrollments, Classes, and Terms APIs through
[API Central](https://api-central.berkeley.edu).
