#!/usr/bin/python3
# vim: set et sw=4 ts=4:

# Given a base folder within CalGroups, and a course specified by an academic
# term, department, and course number:
#  - fetch the course roster from sis
#  - create a folder structure and groups in CalGroups under the base folder
#  - replace members of the calgroup roster with those from the sis

# Requires SIS and CalGroups API credentials.

# CalGroups API
# https://calnetweb.berkeley.edu/calnet-technologists/calgroups-integration/calgroups-api-information

import argparse
import asyncio
import json
import logging
import os
import pathlib
import pprint
import sys

from sis import sis, classes, course, enrollments, student, terms

# We use f-strings from python >= 3.6.
assert sys.version_info >= (3, 6)

# logging
logging.basicConfig(stream=sys.stdout, level=logging.WARNING)
logger = logging.getLogger("sis")
# logger.setLevel(logging.DEBUG)

secret_keys = [
    "enrollments_id",
    "classes_id",
    "course_id",
    "terms_id",
    "students_id",
    "enrollments_key",
    "classes_key",
    "course_key",
    "terms_key",
    "students_key",
]


def has_all_keys(d, keys):
    return all(k in d for k in keys)


def read_json_data(filename, required_keys):
    """Read and validate data from a json file."""
    if not os.path.exists(filename):
        raise Exception(f"No such file: {filename}")
    data = json.loads(open(filename).read())
    # check that we've got all of our required keys
    if not has_all_keys(data, required_keys):
        missing = set(required_keys) - set(data.keys())
        s = f"Missing parameters in {filename}: {missing}"
        raise Exception(s)
    return data


def read_credentials(filename, required_keys=secret_keys):
    """Read credentials from {filename}. Returns a dict."""
    return read_json_data(filename, required_keys)


def credentials_file():
    """Default path to credentials file."""
    return pathlib.PurePath.joinpath(pathlib.Path.home(), ".sis.json")


def valid_term(string):
    valid_terms = ["Current", "Next", "Previous"]
    if string.isdigit() or string in valid_terms:
        return string
    msg = f"{string} is not a term id or one of {valid_terms}"
    raise argparse.ArgumentTypeError(msg)


def csv_list(string):
    return string.split(",")


## main
async def main():
    default_creds_file = str(credentials_file())

    parser = argparse.ArgumentParser(description="Get data from UC Berkeley's SIS")
    parser.add_argument(
        "-f", dest="credentials", default=default_creds_file, help="credentials file."
    )
    parser.add_argument(
        "-v", dest="verbose", action="store_true", help="set info log level"
    )
    parser.add_argument(
        "-d", dest="debug", action="store_true", help="set debug log level"
    )
    parser.add_argument(
        "--json",
        dest="json",
        action="store_true",
        help="output JSON from subcommands (indent=4)",
    )

    subparsers = parser.add_subparsers(dest="command")

    people_parser = subparsers.add_parser("people", help="Get lists of people.")
    people_term_group = people_parser.add_mutually_exclusive_group()
    people_term_group.add_argument(
        "-t",
        dest="sis_term_id",
        type=valid_term,
        help="SIS term id or position, e.g. 2192. Default: the current term.",
    )
    people_term_group.add_argument("-y", dest="year", help="course year, e.g. 2019")
    people_parser.add_argument(
        "-s",
        dest="semester",
        choices=["spring", "summer", "fall"],
        type=str.lower,
        help="semester",
    )
    people_parser.add_argument(
        "-n",
        dest="class_number",
        required=True,
        type=int,
        help="class section number, e.g. 14720",
    )
    people_parser.add_argument(
        "-c",
        dest="constituents",
        default="enrolled",
        choices=["enrolled", "waitlisted", "students", "instructors"],
        type=str.lower,
        help="course constituents",
    )
    people_parser.add_argument(
        "-i",
        dest="identifier",
        default="campus-uid",
        choices=["campus-uid", "email"],
        type=str.lower,
        help="course constituents",
    )
    people_parser.add_argument(
        "--exact",
        dest="exact",
        action="store_true",
        help="exclude data from sections with matching subject and code.",
    )

    classes_parser = subparsers.add_parser("classes", help="Get classes.")
    classes_parser.add_argument(
        "-s", dest="subject_area", help='Subject area. e.g. "STAT"'
    )
    classes_parser.add_argument("-t", dest="term_id", help="Term ID")
    classes_parser.add_argument(
        "-i",
        dest="identifier",
        required=True,
        choices=["cs-course-id", "class-number"],
        type=str.lower,
        help="class identifier",
    )

    section_parser = subparsers.add_parser(
        "section", help="Get information about a section."
    )
    section_term_group = section_parser.add_mutually_exclusive_group()
    section_term_group.add_argument(
        "-t",
        dest="sis_term_id",
        type=valid_term,
        help="SIS term id or position, e.g. 2192. Default: the current term.",
    )
    section_term_group.add_argument("-y", dest="year", help="course year, e.g. 2019")
    section_parser.add_argument(
        "-s",
        dest="semester",
        choices=["spring", "summer", "fall"],
        type=str.lower,
        help="semester",
    )
    section_parser.add_argument(
        "-n",
        dest="class_number",
        required=True,
        type=int,
        help="class section number, e.g. 14720",
    )
    section_parser.add_argument(
        "-a",
        dest="attribute",
        required=True,
        choices=["subject_area", "catalog_number", "display_name", "is_primary", "all"],
        type=str.lower,
        help="attribute",
    )

    students_parser = subparsers.add_parser(
        "student", help="Get information about a student."
    )
    students_parser.add_argument(
        "-i", dest="identifier", required=True, help="id of student"
    )
    students_parser.add_argument(
        "-t",
        dest="id_type",
        metavar="type",
        required=True,
        choices=["campus-id", "student-id"],
        type=str.lower,
        default="campus-id",
        help="id type",
    )
    students_parser.add_argument(
        "-a",
        dest="attribute",
        required=True,
        choices=["plans", "email", "name"],
        type=str.lower,
        help="attribute",
    )

    course_parser = subparsers.add_parser("course", help="Get courses.")
    course_parser.add_argument(
        "-j", dest="json", action="store_true", help="Return JSON"
    )
    course_parser.add_argument(
        "-S",
        dest="status-code",
        choices=["active", "future", "historical", "inactive"],
        type=str.lower,
        help="status code",
    )
    course_parser.add_argument(
        "-s", dest="subject-area-code", default=None, help='Subject area. e.g. "STAT"'
    )
    course_parser.add_argument(
        "-n", dest="catalog-number", default=None, help='Catalog number. e.g. "C123AC"'
    )
    course_parser.add_argument(
        "-p",
        dest="course-prefix",
        default=None,
        help='Course prefix. e.g. "C in C123AC"',
    )
    course_parser.add_argument(
        "-N",
        dest="course-number",
        default=None,
        help='Course number. e.g. "123 in C123AC"',
    )
    course_parser.add_argument(
        "-a",
        dest="academic-career-code",
        default=None,
        help='Academic career code. e.g. "UGRD", "GRAD"',
    )
    # subject_area=None, catalog_number=None, course_prefix=None, course_number=None

    courses_parser = subparsers.add_parser("courses", help="Get student courses.")
    courses_term_group = courses_parser.add_mutually_exclusive_group()
    courses_term_group.add_argument(
        "-t",
        dest="sis_term_id",
        type=valid_term,
        help="SIS term id or position, e.g. 2192. Default: the current term.",
    )
    courses_term_group.add_argument("-y", dest="year", help="course year, e.g. 2019")
    courses_parser.add_argument(
        "-s",
        dest="semester",
        choices=["spring", "summer", "fall"],
        type=str.lower,
        help="semester",
    )
    courses_parser.add_argument(
        "-i", dest="identifier", required=True, help="id of student"
    )
    courses_parser.add_argument(
        "-T",
        dest="id_type",
        metavar="type",
        required=True,
        choices=["campus-uid", "student-id"],
        type=str.lower,
        default="campus-uid",
        help="id type",
    )
    courses_parser.add_argument(
        "-a",
        dest="attribute",
        required=False,
        choices=["course-id", "display-name", "all"],
        type=str.lower,
        default="course-id",
        help="course descriptor",
    )
    courses_parser.add_argument(
        "-w", dest="include_waitlisted", action="store_true", help="include waitlisted"
    )

    term_parser = subparsers.add_parser("term", help="Get term identifier.")
    term_parser.add_argument(
        "-p",
        dest="position",
        type=str.lower,
        choices=["next", "current", "previous"],
        default="current",
        help="term year, e.g. 2019",
    )
    term_parser.add_argument("-y", dest="year", help="term year, e.g. 2019")
    term_parser.add_argument(
        "-s",
        dest="semester",
        choices=["spring", "summer", "fall"],
        type=str.lower,
        help="semester",
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.INFO)
    elif args.debug:
        logger.setLevel(logging.DEBUG)

    # read credentials from credentials file
    credentials = read_credentials(args.credentials)

    if args.command == "people":
        # determine the numeric term id (e.g. 2192) from the year and semester
        if args.year:
            term_id = await terms.get_term_id_from_year_sem(
                credentials["terms_id"],
                credentials["terms_key"],
                args.year,
                args.semester,
            )
        elif args.sis_term_id:
            term_id = args.sis_term_id
        else:
            # default is position='Current'
            term_id = await terms.get_term_id(
                credentials["terms_id"], credentials["terms_key"]
            )

        if not term_id:  # e.g. we are between semesters
            # another strategy is to pretend we're 30 days in the future and retry
            # to get the term id
            return

        include_secondary = "false" if args.exact else "true"
        data = None
        if args.constituents in ["enrolled", "waitlisted", "students"]:
            data = await enrollments.get_students(
                term_id,
                args.class_number,
                args.constituents,
                credentials,
                include_secondary,
                args.identifier,
                return_raw=args.json,
            )
        elif args.constituents == "instructors":
            data = await classes.get_instructors(
                credentials["classes_id"],
                credentials["classes_key"],
                term_id,
                args.class_number,
                include_secondary,
                args.identifier,
                return_raw=args.json,
            )
        if args.json:
            # Convert sets to lists for JSON serialization
            if isinstance(data, set):
                data = list(data)
            print(json.dumps(data or [], indent=4))
        else:
            if data:
                for item in data:
                    print(item)
    elif args.command == "classes":
        if args.subject_area:
            if args.term_id:
                term_id = args.term_id
            else:
                term_id = await terms.get_term_id(
                    credentials["terms_id"],
                    credentials["terms_key"],
                )
            if args.identifier == "cs-course-id":
                course_ids = await classes.get_classes_by_subject_area(
                    credentials["classes_id"],
                    credentials["classes_key"],
                    term_id,
                    args.subject_area,
                )
            elif args.identifier == "class-number":
                course_ids = await enrollments.get_lecture_section_ids(
                    credentials["enrollments_id"],
                    credentials["enrollments_key"],
                    term_id,
                    args.subject_area,
                )
            if args.json:
                print(json.dumps(course_ids or [], indent=4))
            else:
                for course_id in course_ids:
                    print(course_id)
    elif args.command == "section":
        if args.year:
            term_id = await terms.get_term_id_from_year_sem(
                credentials["terms_id"],
                credentials["terms_key"],
                args.year,
                args.semester,
            )
        elif args.sis_term_id:
            term_id = args.sis_term_id
        else:
            # default is position='Current'
            term_id = await terms.get_term_id(
                credentials["terms_id"], credentials["terms_key"]
            )

        if not term_id:  # e.g. we are between semesters
            # another strategy is to pretend we're 30 days in the future and retry
            # to get the term id
            return

        sections = await classes.get_sections_by_id(
            credentials["classes_id"],
            credentials["classes_key"],
            term_id,
            args.class_number,
            include_secondary="false",
        )
        if args.attribute == "all":
            if args.json:
                print(json.dumps(sections or [], indent=4))
            else:
                for section in sections:
                    pprint.pprint(section)
        else:
            # non-json behavior prints one value per section line-by-line
            for section in sections:
                if args.attribute == "subject_area":
                    print(enrollments.section_subject_area(section))
                elif args.attribute == "catalog_number":
                    print(enrollments.section_catalog_number(section))
                elif args.attribute == "display_name":
                    print(enrollments.section_display_name(section))
                elif args.attribute == "is_primary":
                    print(
                        {True: "1", False: "0"}[
                            enrollments.section_display_name(section)
                        ]
                    )
    elif args.command == "student":
        if args.attribute == "plans":
            statuses = await student.get_academic_statuses(
                credentials["students_id"],
                credentials["students_key"],
                args.identifier,
                args.id_type,
            )
            plans = []
            for status in statuses:
                plans += student.get_academic_plans(status)
            if args.json:
                print(json.dumps(plans, indent=4))
            else:
                for plan in plans:
                    print(plan["code"])
        elif args.attribute == "email":
            emails = await student.get_emails(
                credentials["students_id"],
                credentials["students_key"],
                args.identifier,
                args.id_type,
            )
            if args.json:
                print(json.dumps(emails or [], indent=4))
            else:
                for email in emails:
                    print(email)
        elif args.attribute == "name":
            code = "Preferred"  # support others
            name = await student.get_name(
                credentials["students_id"],
                credentials["students_key"],
                args.identifier,
                args.id_type,
                code,
            )
            if args.json:
                print(json.dumps(name, indent=4))
            else:
                print(name)
    elif args.command == "course":
        params = {}
        for a in [
            "status-code",
            "subject-area-code",
            "catalog-number",
            "course_prefix",
            "course-number",
        ]:
            v = getattr(args, a, None)
            if v is not None:
                params[a] = v
        data = await course.get_courses(
            credentials["course_id"], credentials["course_key"], **params
        )
        if args.json:
            print(json.dumps(data, indent=4))
        else:
            course.print_courses(data)
    elif args.command == "courses":
        # determine the numeric term id (e.g. 2192) from the year and semester
        if args.year:
            term_id = await terms.get_term_id_from_year_sem(
                credentials["terms_id"],
                credentials["terms_key"],
                args.year,
                args.semester,
            )
        elif args.sis_term_id:
            term_id = args.sis_term_id
        else:
            # default is position='Current'
            term_id = await terms.get_term_id(
                credentials["terms_id"], credentials["terms_key"]
            )

        if not term_id:  # e.g. we are between semesters
            # another strategy is to pretend we're 30 days in the future and retry
            # to get the term id
            return

        # enrolled only is the opposite of include waitlisted,
        # and must be a string
        enrolled_only = {False: "true", True: "false"}[args.include_waitlisted]
        class_sections = await enrollments.get_student_enrollments(
            credentials["enrollments_id"],
            credentials["enrollments_key"],
            args.identifier,
            term_id,
            args.id_type,
            enrolled_only=enrolled_only,
            course_attr=args.attribute,
        )
        if class_sections:
            if args.json:
                print(json.dumps(class_sections, indent=4))
            else:
                for class_section in class_sections:
                    print(class_section)
    elif args.command == "term":
        if (not args.year and args.semester) or (args.year and not args.semester):
            print("Specify both year and semester, or neither.")
            sys.exit(1)
        # determine the numeric term from the temporal position
        if not args.year:
            term_id = await terms.get_term_id(
                credentials["terms_id"], credentials["terms_key"], args.position
            )
        # determine the numeric term id (e.g. 2192) from the year and semester
        else:
            term_id = await terms.get_term_id_from_year_sem(
                credentials["terms_id"],
                credentials["terms_key"],
                args.year,
                args.semester,
            )
        if args.json:
            print(json.dumps(term_id, indent=4))
        else:
            print(term_id)


def run():
    asyncio.run(main())
