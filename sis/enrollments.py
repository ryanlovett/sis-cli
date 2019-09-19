# vim:set et sw=4 ts=4:
import logging
import sys

import jmespath

from . import sis, classes

# logging
logging.basicConfig(stream=sys.stdout, level=logging.WARNING)
logger = logging.getLogger(__name__)

# SIS endpoint
enrollments_uri = "https://apis.berkeley.edu/sis/v2/enrollments"

# apparently some courses have LAB without LEC (?)
section_codes = ['LEC', 'SES', 'WBL', 'LAB']

async def get_student_enrollments(app_id, app_key, identifier, term_id,
    id_type='campus-uid', enrolled_only='true', primary_only='true',
    course_attr='course-id'):
    '''Gets a students enrollments.'''
    uri = enrollments_uri + f"/students/{identifier}"
    headers = {
        "Accept": "application/json",
        "app_id": app_id,
        "app_key": app_key
    }
    params = {
        "page-number": 1,
        "page-size": 100, # maximum
        "id-type": id_type,
        "term-id": term_id,
        "enrolled-only": enrolled_only,
        "primary-only": primary_only,
    }
    enrollments = await sis.get_items(uri, params, headers, 'studentEnrollments')
    logger.debug(f"enrollments: {enrollments}")
    if course_attr == 'course-id':
        flt = '[].classSection.class.course.identifiers[?type == `cs-course-id`].id[]'
    elif course_attr == 'display-name':
        flt = '[].classSection.class.course.displayName'
    return jmespath.search(flt, enrollments)

async def get_section_enrollments(app_id, app_key, term_id, section_id):
    '''Gets a course section's enrollments.'''
    uri = enrollments_uri + f"/terms/{term_id}/classes/sections/{section_id}"
    headers = {
        "Accept": "application/json",
        "app_id": app_id,
        "app_key": app_key
    }
    params = {
        "page-number": 1,
        "page-size": 100, # maximum
    }
    enrollments = await sis.get_items(uri, params, headers, 'classSectionEnrollments')
    logger.info(f"{section_id}: {len(enrollments)}")
    return enrollments

def section_id(section):
    '''Return a section's course ID, e.g. "15807".'''
    return section['id']

def section_subject_area(section):
    '''Return a section's subject area, e.g. "STAT".'''
    return jmespath.search('class.course.subjectArea.code', section)

def section_catalog_number(section):
    '''Return a section's formatted catalog number, e.g. "215B".'''
    return jmespath.search('class.course.catalogNumber.formatted', section)

def section_display_name(section):
    '''Return a section's displayName, e.g. "STAT 215B".'''
    return jmespath.search('class.course.displayName', section)

def section_is_primary(section):
    '''Return a section's primary status.'''
    return jmespath.search('association.primary', section)

def enrollment_campus_uid(enrollment):
    '''Return an enrollent's campus UID.'''
    expr = "student.identifiers[?disclose && type=='campus-uid'].id | [0]"
    return jmespath.search(expr, enrollment)

def enrollment_campus_email(enrollment):
    '''Return an enrollment's campus email if found, otherwise
       return any other email.'''
    expr = "student.emails[?type.code=='CAMP'].emailAddress | [0]"
    email = jmespath.search(expr, enrollment)
    if email: return email
    expr = "student.emails[?type.code=='OTHR'].emailAddress | [0]"
    return jmespath.search(expr, enrollment)

def get_enrollment_uids(enrollments):
    '''Given an SIS enrollment, return the student's campus UID.'''
    return list(map(lambda x: enrollment_campus_uid(x), enrollments))

def get_enrollment_emails(enrollments):
    '''Given an SIS enrollment, return the student's campus email.'''
    return list(map(lambda x: enrollment_campus_email(x), enrollments))

def enrollment_status(enrollment):
    '''Return an enrollment's status, e.g. 'E', 'W', or 'D'.'''
    return jmespath.search('enrollmentStatus.status.code', enrollment)

def filter_enrollment_status(enrollments, status):
    return list(filter(lambda x: enrollment_status(x) == status, enrollments))

def status_code(constituents):
    return {'enrolled':'E', 'waitlisted':'W', 'dropped':'D'}[constituents]

async def get_students(term_id, class_number, constituents, credentials, exact, identifier='campus-uid'):
    '''Given a term and class section number, return the student ids.'''

    if exact:
        # get all enrollments for this section
        enrollments = await get_section_enrollments(
            credentials['enrollments_id'], credentials['enrollments_key'],
            term_id, class_number
        )

    else:
        # get the data for the specified section
        section = await classes.get_sections_by_id(
            credentials['classes_id'], credentials['classes_key'],
            term_id, class_number, include_secondary='true'
        )

        # extract the subject area and catalog number, e.g. STAT C8
        subject_area   = section_subject_area(section)
        catalog_number = section_catalog_number(section)
        logger.info(f"{subject_area} {catalog_number}")

        # get enrollments in all matching sections
        enrollments = await get_enrollments(
            credentials['enrollments_id'], credentials['enrollments_key'],
            term_id, subject_area, catalog_number
        )

    if constituents == 'students':
        constituent_enrollments = enrollments
    else:
        # filter for those enrollments with a specific status code
        constituent_enrollments = filter_enrollment_status(
            enrollments, status_code(constituents))

    # function to extract an enrollment attribute
    if identifier == 'campus-uid':
        enrollment_attr_fn = enrollment_campus_uid
    else:
        enrollment_attr_fn = enrollment_campus_email

    # we convert to a set to collapse overlapping enrollments between
    # lectures and labs (if not exact)
    return set(map(lambda x: enrollment_attr_fn(x), constituent_enrollments))

def filter_lectures(sections, relevant_codes=section_codes):
    '''
    Given a list of SIS sections:
       [{'code': '32227', 'description': '2019 Spring ASTRON 128 001 LAB 001'}]
    return only the section codes which are lectures.
    '''
    codes = []
    for section in sections:
        if 'description' not in section: continue
        desc_words = set(section['description'].split())
        if len(set(desc_words) & set(relevant_codes)) > 0:
            codes.append(section['code'])
    return codes

async def get_lecture_section_ids(app_id, app_key, term_id, subject_area, catalog_number):
    '''
      Given a term, subject, and course number, return the lecture section ids.
      We only care about the lecture enrollments since they contain a superset
      of the enrollments of all other section types (lab, dis).
    '''
    uri = enrollments_uri + f'/terms/{term_id}/classes/sections/descriptors'
    headers = {
        "Accept": "application/json",
        "app_id": app_id,
        "app_key": app_key
    }
    params = {
        'page-number': 1,
        "subject-area-code": subject_area,
        "catalog-number": catalog_number,
    }
    # Retrieve the sections associated with the course which includes
    # both lecture and sections.
    sections = await sis.get_items(uri, params, headers, 'fieldValues')
    return filter_lectures(sections)

async def get_enrollments(app_id, app_key, term_id, subject_area, catalog_number):
    '''Gets a course's enrollments from the SIS.'''
    logger.info(f"get_enrollments: {subject_area} {catalog_number}")

    # get the lectures
    lecture_codes = await get_lecture_section_ids(app_id, app_key, term_id,
                        subject_area, catalog_number)

    # get the enrollments in each lecture
    enrollments = []
    for section_id in lecture_codes:
        enrollments += await get_section_enrollments(app_id, app_key, term_id, section_id)
    logger.info(f'enrollments: {len(enrollments)}')
    return enrollments
