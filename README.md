sis
===
Query the UC Berkeley Student Information System (SIS).

Requires SIS API credentials.

Please submit issues to this repository since this software is not maintained by the SIS team.

```
usage: sis [-h] [-f CREDENTIALS] [-v] [-d] [--json]
           {people,classes,section,student,courses,term} ...

Get data from UC Berkeley's SIS

positional arguments:
  {people,classes,section,student,courses,term}
    people              Get lists of people.
    classes             Get classes.
    section             Get information about a section.
    student             Get information about a student.
    courses             Get student courses.
    term                Get term identifier.

optional arguments:
  -h, --help            show this help message and exit
  -f CREDENTIALS        credentials file.
  -v                    set info log level
  -d                    set debug log level
  --json                output JSON from all subcommands (indent=4)
```

By default, `sis` will read credentials from `~/.sis.json`.

**Global `--json` flag:**
The `--json` flag is available for all subcommands and must be specified **before** the subcommand name. It changes the output format from line-by-line text to structured JSON. The JSON content varies by subcommand:
- `people`: Returns person objects (instructor/student details) filtered by constituent type
- `section`: Returns section data (when used with `-a all`)
- `student`: Returns student attribute data (plans, email, or name)
- `classes`: Returns list of class identifiers
- `courses`: Returns student enrollment data
- `term`: Returns term identifier

Example: `sis --json people -y 2026 -s spring -n 31203 -c instructors`

People
------
```
usage: sis people [-h] [-t SIS_TERM_ID | -y YEAR] [-s {spring,summer,fall}] -n
                  CLASS_NUMBER [-c {enrolled,waitlisted,students,instructors,gsis,staff}]
                  [-i {campus-uid,email,name}] [--exact]

optional arguments:
  -h, --help            show this help message and exit
  -t SIS_TERM_ID        SIS term id or position, e.g. 2192. Default: the
                        current term.
  -y YEAR               course year, e.g. 2019
  -s {spring,summer,fall}
                        semester
  -n CLASS_NUMBER       class section number, e.g. 14720
  -c {enrolled,waitlisted,students,instructors,gsis,staff}
                        course constituents
  -i {campus-uid,email,name}
                        identifier type to extract
  --exact               exclude data from sections with matching subject and
                        code.
```

**Constituent types (`-c`):**
- `enrolled`: Students with enrolled status
- `waitlisted`: Students on the waitlist
- `students`: All students (enrolled + waitlisted)
- `instructors`: Only professors/lecturers (role code PI)
- `gsis`: Only GSIs/TAs (role code TNIC)
- `staff`: All teaching staff (instructors + GSIs)

**Identifier types (`-i`):**
- `campus-uid`: CalNet UID (default)
- `email`: Email address (if disclosed)
- `name`: Formatted name

Sections
--------
```
usage: sis section [-h] [-t SIS_TERM_ID | -y YEAR] [-s {spring,summer,fall}]
                   -n CLASS_NUMBER -a
                   {subject_area,catalog_number,display_name,is_primary,all}
                   [--exact]

optional arguments:
  -h, --help            show this help message and exit
  -t SIS_TERM_ID        SIS term id or position, e.g. 2192. Default: the
                        current term.
  -y YEAR               course year, e.g. 2019
  -s {spring,summer,fall}
                        semester
  -n CLASS_NUMBER       class section number, e.g. 14720
  -a {subject_area,catalog_number,display_name,is_primary,all}
                        attribute
  --exact               exclude secondary sections (labs, discussions, etc.)
```

Students
--------
```
usage: sis student [-h] -i IDENTIFIER -t type -a {plans,email}

optional arguments:
  -h, --help     show this help message and exit
  -i IDENTIFIER  id of student
  -t type        id type
  -a {plans,email}     attribute
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
Get waitlisted student UIDs for a lab section in summer 2019:

```bash
sis people -y 2019 -s summer -n 14024 -c waitlisted --exact
```

Get all student emails for a lecture in summer 2019 (includes all sections with the same subject area and catalog number, e.g., STAT C8):

```bash
sis people -y 2019 -s summer -n 14035 -c students -i email
```

Get instructor names for a class in spring 2026:

```bash
sis people -y 2026 -s spring -n 31203 -c instructors -i name
```

Get only GSI/TA names for a class:

```bash
sis people -y 2026 -s spring -n 31203 -c gsis -i name
```

Get all teaching staff (instructors + GSIs) with detailed JSON output:

```bash
sis --json people -y 2026 -s spring -n 31203 -c staff
```

Get complete section data including all secondary sections (labs, discussions):

```bash
sis --json section -y 2026 -s spring -n 31203 -a all
```

Get a student's courses in fall 2019:

```bash
sis courses -i 123456 -t campus-uid -y 2019 -s fall
```

API Access
----------
This application requires access to the following SIS APIs:

 - Enrollments: acquire course enrollments
 - Classes:
   - lookup course instructor
   - resolve course subject and number from section ID
 - Terms: lookup term id from date
 - Student: get student's academic programs or email
 - Employee: resolve instructor campus email from campus uid

Request credentials for these APIs through
[API Central](https://api-central.berkeley.edu).

Supply the credentials in a JSON file of the form:
```json
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

Installation
------------
Install in editable mode for development:

```bash
pip install -e .
```

Or in production:

```bash
pip install .
```
