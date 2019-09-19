sis
===
Query the UC Berkeley Student Information System (SIS).

Requires SIS API credentials.

Please submit issues to this repository since this software is not maintained by the SIS team.

People
------
```
usage: sis people [-h] -y YEAR -s {spring,summer,fall} -n CLASS_NUMBER
                  [-c {enrolled,waitlisted,students,instructors}]
                  [-i {campus-uid,email}] [--exact]

optional arguments:
  -h, --help            show this help message and exit
  -y YEAR               course year, e.g. 2019
  -s {spring,summer,fall}
                        semester
  -n CLASS_NUMBER       class section number, e.g. 14720
  -c {enrolled,waitlisted,students,instructors}
                        course constituents
  -i {campus-uid,email}
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
                        attribute
```

Students
--------
```
usage: sis student [-h] -i IDENTIFIER -t type -a {plans}

optional arguments:
  -h, --help     show this help message and exit
  -i IDENTIFIER  id of student
  -t type        id type
  -a {plans}     attribute
```

Courses
-------
```
usage: sis courses [-h] -i IDENTIFIER -t type -y YEAR -s {spring,summer,fall}
                   [-a {course-id,display-name}]

optional arguments:
  -h, --help            show this help message and exit
  -i IDENTIFIER         id of student
  -t type               id type
  -y YEAR               term year, e.g. 2019
  -s {spring,summer,fall}
                        semester
  -a {course-id,display-name}
                        course descriptor
```

Examples
--------
Get waitlisted IDs for a lab section in summer 2019:

`sis people -y 2019 -s summer -n 14024 -c waitlisted --exact`

Get all student emails for a lecture in summer 2019. We omit `--exact` so that
we match all sections with the same subject area and catalog number,
e.g. STAT C8:

`sis people -y 2019 -s summer -n 14035 -c students -i email`

Get a student's courses in fall 2019:

`sis courses -i 123456 -t campus-uid -y 2019 -s fall`

API Access
----------
This application requires access to the following SIS APIs:

 - Enrollments: acquire course enrollments
 - Classes:
   - lookup course instructor
   - resolve course subject and number from section ID
 - Terms: lookup term id from date
 - Student: get student's academic programs
 - Employee: resolve instructor campus email from campus uid

Request credentials for these APIs through
[API Central](https://api-central.berkeley.edu).

Supply the credentials in a JSON file of the form:
```
{
	"classes_id": "...",
	"classes_key": "...",
	"employee_id": "...",
	"employee_key": "...",
	"enrollments_id": "...",
	"enrollments_key": "...",
	"students_id": "...",
	"students_key": "...",
	"terms_id": "...",
	"terms_key": "..."
}
```
