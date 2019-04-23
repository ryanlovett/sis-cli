# vim:set et sw=4 ts=4:
import logging
import sys

import aiohttp

# logging
logging.basicConfig(stream=sys.stdout, level=logging.WARNING)
logger = logging.getLogger(__name__)

# Various SIS endpoints
enrollments_uri = "https://apis.berkeley.edu/sis/v2/enrollments"
descriptors_uri = enrollments_uri + '/terms/{}/classes/sections/descriptors'
sections_uri = enrollments_uri + "/terms/{}/classes/sections/{}"
classes_sections_uri = "https://apis.berkeley.edu/sis/v1/classes/sections"
terms_uri = "https://apis.berkeley.edu/sis/v1/terms"

# apparently some courses have LAB without LEC (?)
section_codes = ['LEC', 'SES', 'WBL', 'LAB']

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

async def get_items(uri, params, headers, item_type):
    '''Recursively get a list of items (enrollments, ) from the SIS.'''
    logger.info(f"getting {item_type}")
    data = []
    async with aiohttp.ClientSession() as session:
        async with session.get(uri, headers=headers, params=params) as r:
            if r.status == 404:
                return []
            data = await r.json()
    # Return if there is no response (e.g. 404)
    if 'apiResponse' not in data or 'response' not in data['apiResponse']:
        logger.debug('404 No response')
        return data
    # Return if the UID has no items
    elif item_type not in data['apiResponse']['response']:
        logger.debug(f'No {item_type}')
        return data
    # Get this page's items
    items = data['apiResponse']['response'][item_type]
    # If we are not paginated, just return the items
    if 'page-number' not in params:
        return items
    # Get the next page's items
    params['page-number'] += 1
    items += await get_items(uri, params, headers, item_type)
    num = len(items)
    logger.debug(f'There are {num} items of type {item_type}')
    return items

async def get_term_name(app_id, app_key, term_id):
    '''Given a term id, return the term's friendly name.'''
    headers = {
        "Accept": "application/json",
        "app_id": app_id, "app_key": app_key
    }
    uri = f'{terms_uri}/{term_id}'
    terms = await get_items(uri, params, headers, 'terms')
    return terms[0]['name']

async def get_term_id(app_id, app_key, position='Current'):
    '''Given a temporal position of Current, Previous, or Next, return
       the corresponding term's ID.'''
    headers = {
        "Accept": "application/json",
        "app_id": app_id, "app_key": app_key
    }
    params = { "temporal-position": position }
    uri = terms_uri
    terms = await get_items(uri, params, headers, 'terms')
    return terms[0]['id']

async def get_term_id_from_year_sem(app_id, app_key, year, semester):
    '''Given a year and Berkeley semester, return the corresponding
       term's ID.'''
    headers = {
        "Accept": "application/json",
        "app_id": app_id, "app_key": app_key
    }
    if semester == 'spring':
        mm_dd = '02-01'
    elif semester == 'summer':
        mm_dd = '07-01'
    elif semester == 'fall':
        mm_dd = '10-01'
    else:
        raise Exception(f"No such semester: {semester}")
    params = { "as-of-date": f"{year}-{mm_dd}" }
    uri = terms_uri
    terms = await get_items(uri, params, headers, 'terms')
    return terms[0]['id']

async def normalize_term_id(app_id, app_key, term_id):
    '''Convert temporal position (current, next, previous) to a numeric term id,
       or passthrough a numeric term id.'''
    if term_id.isalpha():
        term_id = await get_term_id(app_id, app_key, term_id)
    return term_id

async def get_lecture_section_ids(app_id, app_key, term_id, subject_area, catalog_number):
    '''
      Given a term, subject, and course number, return the lecture section ids.
      We only care about the lecture enrollments since they contain a superset
      of the enrollments of all other section types (lab, dis).
    '''
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
    uri = descriptors_uri.format(term_id)
    sections = await get_items(uri, params, headers, 'fieldValues')
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

async def get_section_enrollments(app_id, app_key, term_id, section_id):
    '''Gets a course section's enrollments from the SIS.'''
    headers = {
        "Accept": "application/json",
        "app_id": app_id,
        "app_key": app_key
    }
    params = {
        "page-number": 1,
        "page-size": 100, # maximum
    }
    uri = sections_uri.format(term_id, section_id)
    enrollments = await get_items(uri, params, headers, 'classSectionEnrollments')
    logger.info(f"{section_id}: {len(enrollments)}")
    return enrollments

def section_instructors(section):
    '''Extract the campus-uid of instructors from a section.'''
    uids = set()
    if 'meetings' not in section: return uids
    meetings = section['meetings']
    for meeting in meetings:
        if 'assignedInstructors' not in meeting: continue
        instructors = meeting['assignedInstructors']
        for instructor in instructors:
            if 'identifiers' not in instructor['instructor']: continue
            identifiers = instructor['instructor']['identifiers']
            for identifier in identifiers:
                # {'disclose': True, 'id': '1234', 'type': 'campus-uid'}
                if 'disclose' not in identifier: continue
                if not identifier['disclose']: continue
                if identifier['type'] != 'campus-uid': continue
                uids.add(identifier['id'])
    return uids

async def get_sections(c_id, c_key, term_id, subject_area, catalog_number):
    '''Given a term, subject, and SIS catalog number, returns a list of
       instructors and a list of GSIs.'''
    logger.info(f'{term_id} {subject_area} {catalog_number}')
    headers = { "Accept": "application/json", "app_id": c_id, "app_key": c_key }
    params = {
        "subject-area-code": subject_area.upper(),
        "catalog-number": catalog_number.upper(),
        "term-id": term_id,
        "page-size": 400,
        "page-number": 1
    }

    # Retrieve the sections associated with the course which includes
    # both lecture and sections.
    logger.debug(f'{classes_sections_uri}')
    logger.debug(f'{params}')
    logger.debug(f'{headers}')
    sections = await get_items(classes_sections_uri, params, headers, 'classSections')
    return sections


async def get_section_by_id(app_id, app_key, term_id, class_section_id, include_secondary='true'):
    '''Given a term and class section ID, return section data.'''
    headers = {
        "Accept": "application/json",
        "app_id": app_id,
        "app_key": app_key
    }
    params = {
        "class-section-id": class_section_id,
        "term-id": term_id,
        "include-secondary": include_secondary,
        "page-size": 400,
        "page-number": 1
    }
    uri = f'{classes_sections_uri}/{class_section_id}'
    sections = await get_items(uri, params, headers, 'classSections')
    
    if len(sections) == 0:
        return []
    elif len(sections) > 1:
        raise Exception(f"Ambiguous sections for {term_id} {class_section_id}")
    return sections[0]

def section_subject_area(section):
    '''Given a section, return the subject area, e.g. "STAT".'''
    assert 'class' in section
    return section['class']['course']['subjectArea']['code']

def section_catalog_number(section):
    '''Given a section, return the formatted catalog number.
       e.g. "215B".'''
    return section['class']['course']['catalogNumber']['formatted']

def section_display_name(section):
    '''Given a section, return the displayName, e.g. "STAT 215B".'''
    return section['class']['course']['displayName']

def section_is_primary(section):
    return section['association']['primary']

def get_enrollment_uids(enrollments):
    '''Given an SIS enrollment, return the student's campus UID.'''
    def campus_uid(enrollment):
        for identifier in enrollment['student']['identifiers']:
            if identifier['type'] == 'campus-uid':
                return identifier['id']
    return list(map(lambda x: campus_uid(x), enrollments))

def get_enrollment_emails(enrollments):
    '''Given an SIS enrollment, return the student's campus email.'''
    def campus_email(enrollment):
        emails = {}
        for email in enrollment['student'].get('emails', []):
            if email['type']['code'] == 'CAMP': return email['emailAddress']
        return None
    return list(map(lambda x: campus_email(x), enrollments))

def enrollment_status(enrollment):
    '''Given an SIS enrollment, returns 'E', 'W', or 'D'.'''
    return str(enrollment['enrollmentStatus']['status']['code'])

def filter_enrollment_status(enrollments, status):
    return list(filter(lambda x: enrollment_status(x) == status, enrollments))
