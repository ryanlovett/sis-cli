# vim:set et sw=4 ts=4:
import logging
import sys

import jmespath

from . import sis, enrollments, classes

# logging
logging.basicConfig(stream=sys.stdout, level=logging.WARNING)
logger = logging.getLogger(__name__)

# SIS endpoint
classes_sections_uri = "https://apis.berkeley.edu/sis/v1/classes/sections"

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
        #"page-size": 400,
        #"page-number": 1
    }
    uri = f'{classes_sections_uri}/{class_section_id}'
    logger.debug(f"get_section_by_id: {uri} {params}")
    sections = await sis.get_items(uri, params, headers, 'classSections')

    if len(sections) == 0:
        return []
    elif len(sections) > 1:
        raise Exception(f"Ambiguous sections for {term_id} {class_section_id}")
    return sections[0]


async def get_sections(app_id, app_key, term_id, subject_area, catalog_number):
    '''Given a term, subject, and SIS catalog number, returns a list of
       instructors and a list of GSIs.'''
    logger.info(f'{term_id} {subject_area} {catalog_number}')
    headers = { "Accept": "application/json", "app_id": app_id, "app_key": app_key }
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
    sections = await sis.get_items(classes_sections_uri, params, headers, 'classSections')
    return sections

async def get_instructors(app_id, app_key, term_id, class_number, exact, identifier='campus-uid'):
    '''Given a term and class section number, return the instructor ids.'''

    # get the data for the specified section
    section = await classes.get_section_by_id(
        app_id, app_key, term_id, class_number, include_secondary='true'
    )
    logger.debug(f"section: {section}")

    if exact:
        instructors = section_instructors(section, identifier)
    else:
        # e.g. STAT C8
        subject_area   = enrollments.section_subject_area(section)
        catalog_number = enrollments.section_catalog_number(section)
        logger.info(f"{subject_area} {catalog_number}")

        # we search by subject area and catalog number which will return
        # all lectures, labs, discussions, etc.
        all_sections = await classes.get_sections(
            app_id, app_key, term_id, subject_area, catalog_number
        )
        logger.info(f"num sections: {len(all_sections)}")

        instructors = set()
        for section in all_sections:
            # fetch the uids of this section's instructors
            instructors |= section_instructors(section, identifier)
    return instructors

def section_instructors(section, id_attr='campus-uid'):
    '''Extract disclosed identifiers of section instructors.'''
    # search for disclosed identifiers of type {id_attr}
    ids = jmespath.search(f"meetings[].assignedInstructors[].instructor.identifiers[?disclose && type=='{id_attr}'].id[]", section)
    if ids is None:
        return set()
    return set(ids)

def filter_instructors(section, constituents, identifier):
    '''Old function to get instructors of either primary or non-primary
       courses.'''
    is_primary = enrollments.section_is_primary(section)
    if (is_primary and constituents == 'instructors') or \
       (not is_primary and constituents == 'gsis'):
        return section_instructors(section, identifier)
        logger.info(f"exact: uids {uids}")
    return set()
