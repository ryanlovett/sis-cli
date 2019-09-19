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
import sys

from sis import sis, classes, enrollments, student, terms

# We use f-strings from python >= 3.6.
assert sys.version_info >= (3, 6)

# logging
logging.basicConfig(stream=sys.stdout, level=logging.WARNING)
logger = logging.getLogger('sis')
#logger.setLevel(logging.DEBUG)

secret_keys = [
    'enrollments_id',  'classes_id',  'terms_id', 'students_id',
    'enrollments_key', 'classes_key', 'terms_key', 'students_key',
]


def has_all_keys(d, keys):
    return all (k in d for k in keys)

def read_json_data(filename, required_keys):
    '''Read and validate data from a json file.'''
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
    '''Read credentials from {filename}. Returns a dict.'''
    return read_json_data(filename, required_keys)

def valid_term(string):
    valid_terms = ['Current', 'Next', 'Previous']
    if string.isdigit() or string in valid_terms:
        return string
    msg = f"{string} is not a term id or one of {valid_terms}"
    raise argparse.ArgumentTypeError(msg)

def csv_list(string):
   return string.split(',')

## main
async def main():
    parser = argparse.ArgumentParser(
        description="Get data from UC Berkeley's SIS")
    parser.add_argument('-f', dest='credentials', default='sis.json',
        help='credentials file.')
    parser.add_argument('-v', dest='verbose', action='store_true',
        help='set info log level')
    parser.add_argument('-d', dest='debug', action='store_true',
        help='set debug log level')

    subparsers = parser.add_subparsers(dest='command')

    people_parser = subparsers.add_parser('people',
        help='Get lists of people.')
    people_parser.add_argument('-y', dest='year', required=True,
        help='course year, e.g. 2019')
    people_parser.add_argument('-s', dest='semester', required=True,
        choices=['spring', 'summer', 'fall'], type=str.lower,
        help='semester')
    #people_parser.add_argument('-t', dest='sis_term_id', type=valid_term,
    #    default='Current',
    #    help='SIS term id or position, e.g. 2192. Default: Current')
    people_parser.add_argument('-n', dest='class_number', required=True,
        type=int, help='class section number, e.g. 14720')
    people_parser.add_argument('-c', dest='constituents', default='enrolled',
        choices=['enrolled', 'waitlisted', 'students', 'instructors'],
        type=str.lower, help='course constituents')
    people_parser.add_argument('-i', dest='identifier', default='campus-uid',
        choices=['campus-uid', 'email'], type=str.lower,
        help='course constituents')
    people_parser.add_argument('--exact', dest='exact', action='store_true',
        help='exclude data from sections with matching subject and code.')

    section_parser = subparsers.add_parser('section',
        help='Get information about a section.')
    section_parser.add_argument('-y', dest='year', required=True,
        help='course year, e.g. 2019')
    section_parser.add_argument('-s', dest='semester', required=True,
        choices=['spring', 'summer', 'fall'], type=str.lower,
        help='semester')
    section_parser.add_argument('-n', dest='class_number', required=True,
        type=int, help='class section number, e.g. 14720')
    section_parser.add_argument('-a', dest='attribute', required=True,
        choices=['subject_area', 'catalog_number', 'display_name', 'is_primary'],
        type=str.lower, help='attribute')

    students_parser = subparsers.add_parser('student',
        help='Get academic programs.')
    students_parser.add_argument('-i', dest='identifier', required=True,
        help='id of student')
    students_parser.add_argument('-t', dest='id_type', metavar='type',
        required=True, choices=['campus-id', 'student-id'], type=str.lower,
        default='campus-id', help='id type')
    students_parser.add_argument('-a', dest='attribute', required=True,
        choices=[ 'plans', 'email' ], type=str.lower, help='attribute')

    courses_parser = subparsers.add_parser('courses',
        help='Get student courses.')
    courses_parser.add_argument('-i', dest='identifier', required=True,
        help='id of student')
    courses_parser.add_argument('-t', dest='id_type', metavar='type',
        required=True, choices=['campus-uid', 'student-id'], type=str.lower,
        default='campus-uid', help='id type')
    courses_parser.add_argument('-y', dest='year', required=True,
        help='term year, e.g. 2019')
    courses_parser.add_argument('-s', dest='semester', required=True,
        choices=['spring', 'summer', 'fall'], type=str.lower,
        help='semester')
    courses_parser.add_argument('-a', dest='attribute', required=False,
        choices=['course-id', 'display-name'], type=str.lower,
        default='course-id', help='course descriptor')

    term_parser = subparsers.add_parser('term',
        help='Get term identifier.')
    term_parser.add_argument('-y', dest='year', required=True,
        help='term year, e.g. 2019')
    term_parser.add_argument('-s', dest='semester', required=True,
        choices=['spring', 'summer', 'fall'], type=str.lower,
        help='semester')

    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.INFO)
    elif args.debug:
        logger.setLevel(logging.DEBUG)
    
    # read credentials from credentials file
    credentials = read_credentials(args.credentials)
    
    if args.command == 'people':
        # determine the numeric term id (e.g. 2192) from the year and semester
        term_id = await terms.get_term_id_from_year_sem(
            credentials['terms_id'], credentials['terms_key'],
            args.year, args.semester
        )

        include_secondary = 'false' if args.exact else 'true'
        if args.constituents in ['enrolled', 'waitlisted', 'students']:
            uids = await enrollments.get_students(term_id, args.class_number,
                args.constituents, credentials, include_secondary, args.identifier)
        elif args.constituents == 'instructors':
            uids = await classes.get_instructors(
                credentials['classes_id'], credentials['classes_key'],
                term_id, args.class_number,
                include_secondary, args.identifier)
        if uids:
            for uid in uids: print(uid)
    elif args.command == 'section':
        term_id = await terms.get_term_id_from_year_sem(
            credentials['terms_id'], credentials['terms_key'],
            args.year, args.semester
        )
        sections = await classes.get_sections_by_id(
            credentials['classes_id'], credentials['classes_key'],
            term_id, args.class_number, include_secondary='false'
        )
        if len(sections) != 1:
            raise Exception(f"Unexpected number of sections: {len(sections)}")
        section = sections[0]
        if args.attribute == 'subject_area':
            print(enrollments.section_subject_area(section))
        elif args.attribute == 'catalog_number':
            print(enrollments.section_catalog_number(section))
        elif args.attribute == 'display_name':
            print(enrollments.section_display_name(section))
        elif args.attribute == 'is_primary':
            print({ True:'1', False:'0' }[enrollments.section_display_name(section)])
    elif args.command == 'student':
        if args.attribute == 'plans':
            statuses = await student.get_academic_statuses(
                credentials['students_id'], credentials['students_key'],
                args.identifier, args.id_type
            )
            plans = []
            for status in statuses:
                plans += student.get_academic_plans(status)
            for plan in plans: print(plan['code'])
        elif args.attribute == 'email':
            emails = await student.get_emails(
                credentials['students_id'], credentials['students_key'],
                args.identifier, args.id_type
            )
            for email in emails: print(email)
    elif args.command == 'courses':
        term_id = await terms.get_term_id_from_year_sem(
            credentials['terms_id'], credentials['terms_key'],
            args.year, args.semester
        )
        class_sections = await enrollments.get_student_enrollments(
            credentials['enrollments_id'], credentials['enrollments_key'],
            args.identifier, term_id, args.id_type,
            course_attr=args.attribute)
        if class_sections:
            for class_section in class_sections: print(class_section)
    elif args.command == 'term':
        # determine the numeric term id (e.g. 2192) from the year and semester
        term_id = await terms.get_term_id_from_year_sem(
            credentials['terms_id'], credentials['terms_key'],
            args.year, args.semester
        )
        print(term_id)

def run():
    asyncio.run(main())
