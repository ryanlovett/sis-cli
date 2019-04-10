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
import json
import logging
import os
import sys

from sis import sis

# We use f-strings from python >= 3.6.
assert sys.version_info >= (3, 6)

# logging
logging.basicConfig(stream=sys.stdout, level=logging.WARNING)
logger = logging.getLogger('sis')
#logger.setLevel(logging.DEBUG)

secret_keys = [
    'enrollments_id',  'classes_id',  'terms_id',
    'enrollments_key', 'classes_key', 'terms_key',
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

def filter_instructors(section, constituents):
    is_primary = sis.section_is_primary(section)
    if (is_primary and constituents == 'instructors') or \
       (not is_primary and constituents == 'gsis'):
        return sis.section_instructors(section)
        logger.info(f"exact: uids {uids}")
    return set()

def get_students(term_id, class_number, constituents, credentials, exact):
    '''Given a term and class section number, return the student ids.'''

    if exact:
        # get all enrollments for this section
        enrollments = sis.get_section_enrollments(
            credentials['enrollments_id'], credentials['enrollments_key'],
            term_id, class_number
        )

    else:
        # get the data for the specified section
        section = sis.get_section_by_id(
            credentials['classes_id'], credentials['classes_key'],
            term_id, class_number, include_secondary='true'
        )

        # extract the subject area and catalog number, e.g. STAT C8
        subject_area   = sis.section_subject_area(section)
        catalog_number = sis.section_catalog_number(section)
        logger.info(f"{subject_area} {catalog_number}")

        # get enrollments in all matching sections
        enrollments = sis.get_enrollments(
            credentials['enrollments_id'], credentials['enrollments_key'],
            term_id, subject_area, catalog_number
        )

    # sis codes for enrollment status
    enrollment_statuses = {'enrolled':'E', 'waitlisted':'W', 'dropped':'D'} 
    status_code = enrollment_statuses[constituents] # E, W, or D

    # extract uids from enrollments
    uids = sis.get_enrollment_uids(
        # filter enrollments by sis status code
        sis.filter_enrollment_status(enrollments, status_code)
    )

    # we convert to a set to collapse overlapping enrollments between
    # lectures and labs (if not exact)
    return set(uids)

def get_instructors(term_id, class_number, constituents, credentials, exact):
    '''Given a term and class section number, return the instructor ids.'''

    # get the data for the specified section
    section = sis.get_section_by_id(
        credentials['classes_id'], credentials['classes_key'],
        term_id, class_number, include_secondary='true'
    )

    if exact:
        uids = filter_instructors(section, constituents)
    else:
        # e.g. STAT C8
        subject_area   = sis.section_subject_area(section)
        catalog_number = sis.section_catalog_number(section)
        logger.info(f"{subject_area} {catalog_number}")

        # we search by subject area and catalog number which will return
        # all lectures, labs, discussions, etc.
        all_sections = sis.get_sections(
            credentials['classes_id'], credentials['classes_key'],
            term_id, subject_area, catalog_number
        )
        logger.info(f"num sections: {len(all_sections)}")

        uids = set()
        for section in all_sections:
            # fetch the uids of this section's instructors
            uids |= filter_instructors(section, constituents)
    return uids

def valid_term(string):
    valid_terms = ['Current', 'Next', 'Previous']
    if string.isdigit() or string in valid_terms:
        return string
    msg = f"{string} is not a term id or one of {valid_terms}"
    raise argparse.ArgumentTypeError(msg)

def csv_list(string):
   return string.split(',')

## main
def main():
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
        choices=['enrolled', 'waitlisted', 'instructors', 'gsis'],
        type=str.lower, help='course constituents')
    people_parser.add_argument('--exact', dest='exact', action='store_true',
        help='exclude data from sections with matching subject and code.')

    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.INFO)
    elif args.debug:
        logger.setLevel(logging.DEBUG)
    
    # read credentials from credentials file
    credentials = read_credentials(args.credentials)
    
    if args.command == 'people':
        # determine the numeric term id (e.g. 2192) from the year and semester
        term_id = sis.get_term_id_from_year_sem(
            credentials['terms_id'], credentials['terms_key'],
            args.year, args.semester
        )

        if args.constituents in ['enrolled', 'waitlisted']:
            uids = get_students(term_id, args.class_number,
                args.constituents, credentials, args.exact)
        elif args.constituents in ['instructors', 'gsis']:
            uids = get_instructors(term_id, args.class_number,
                args.constituents, credentials, args.exact)
        if uids:
            for uid in uids: print(uid)
