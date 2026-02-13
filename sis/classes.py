# vim:set et sw=4 ts=4:
import logging
import sys

import jmespath

from . import sis, enrollments, classes

# logging
logging.basicConfig(stream=sys.stdout, level=logging.WARNING)
logger = logging.getLogger(__name__)

# SIS endpoint
classes_uri = "https://gateway.api.berkeley.edu/sis/v1/classes"
classes_sections_uri = "https://gateway.api.berkeley.edu/sis/v1/classes/sections"


async def get_classes_by_subject_area(app_id, app_key, term_id, subject_area):
    """Given a term and subject area, return class data."""
    headers = {"Accept": "application/json", "app_id": app_id, "app_key": app_key}
    params = {
        "subject-area-code": subject_area,
        "term-id": term_id,
    }
    uri = classes_uri
    logger.debug(f"get_classes_by_subject_area: {uri} {params}")
    classes = await sis.get_items(uri, params, headers, "classes")
    course_ids = jmespath.search(
        "[].course.identifiers[?type=='cs-course-id'].id[]", classes
    )
    return sorted(list(set(course_ids)))


async def get_sections_by_id(
    app_id, app_key, term_id, class_section_id, include_secondary="true"
):
    """Given a term and class section ID, return section data."""
    headers = {"Accept": "application/json", "app_id": app_id, "app_key": app_key}
    params = {
        "class-section-id": class_section_id,
        "term-id": term_id,
        "include-secondary": include_secondary,
    }
    uri = f"{classes_sections_uri}/{class_section_id}"
    logger.debug(f"get_sections_by_id: {uri} {params}")
    sections = await sis.get_items(uri, params, headers, "classSections")

    if len(sections) == 0:
        return []
    elif len(sections) > 1 and include_secondary == "false":
        logger.warning(f"Multiple sections for {term_id} {class_section_id}")
    return sections


async def get_sections(
    app_id, app_key, term_id, subject_area, catalog_number, include_secondary="true"
):
    """Given a term, subject, and SIS catalog number, returns a list of
    sections."""
    logger.info(f"{term_id} {subject_area} {catalog_number}")
    headers = {"Accept": "application/json", "app_id": app_id, "app_key": app_key}
    params = {
        "subject-area-code": subject_area.upper(),
        "catalog-number": catalog_number.upper(),
        "term-id": term_id,
        "include-secondary": include_secondary,
        "page-size": 400,
        "page-number": 1,
    }

    # Retrieve the sections associated with the course which includes
    # both lecture and sections. (because of include_secondary)
    sections = await sis.get_items(
        classes_sections_uri, params, headers, "classSections"
    )
    return sections


async def get_instructors(
    app_id,
    app_key,
    term_id,
    class_number,
    include_secondary="false",
    identifier="campus-uid",
    return_raw=False,
    role_filter="staff",
):
    """Given a term and class section number, return the instructor ids.

    If return_raw is True, returns the instructor objects with all details instead of just extracted identifiers.
    role_filter can be:
    - "instructors": only professors/lecturers (role code PI)
    - "gsis": only GSIs/TAs (role code TNIC)
    - "staff": all teaching staff (both instructors and GSIs)
    """

    # get the data for the specified sections
    sections = await classes.get_sections_by_id(
        app_id, app_key, term_id, class_number, include_secondary
    )
    logger.debug(f"sections: {sections}")

    # When the include_secondary attribute was not functional in SIS we had
    # to search for all sections with a subject area and catalog number,
    # e.g. STAT C8. This would return all lectures, labs, discussions, etc.
    # We'd then get the instructors for all of those sections.
    # subject_area   = enrollments.section_subject_area(section)
    # catalog_number = enrollments.section_catalog_number(section)
    # logger.info(f"{subject_area} {catalog_number}")
    # sections = await classes.get_sections(
    #    app_id, app_key, term_id, subject_area, catalog_number
    # )

    logger.info(f"num sections: {len(sections)}")

    if return_raw:
        # Return full instructor objects instead of just IDs
        instructors = []
        for section in sections:
            instructors.extend(section_instructor_objects(section, role_filter))
        return instructors

    instructors = set()
    for section in sections:
        instructors |= section_instructors(section, identifier, role_filter)

    return instructors


def filter_instructors_by_role(all_instructors, role_filter="staff"):
    """Filter instructors by role code.

    role_filter can be:
    - "instructors": only professors/lecturers (role code PI)
    - "gsis": only GSIs/TAs (role code TNIC)
    - "staff": all teaching staff (excludes only APRX - administrative proxy)

    Returns an iterator of filtered instructor objects.
    """
    # Map role_filter to (codes_to_include, codes_to_exclude)
    # If codes_to_include is not None, only those codes are included
    # Otherwise, codes_to_exclude are excluded
    role_filter_map = {
        "gsis": (["TNIC"], None),
        "instructors": (["PI"], None),
        "staff": (None, ["APRX"]),
    }

    codes_to_include, codes_to_exclude = role_filter_map.get(
        role_filter, role_filter_map["staff"]
    )

    if codes_to_include is not None:
        return filter(
            lambda x: "role" in x and x["role"]["code"] in codes_to_include,
            all_instructors,
        )
    else:
        return filter(
            lambda x: "role" in x and x["role"]["code"] not in codes_to_exclude,
            all_instructors,
        )


def section_instructor_objects(section, role_filter="staff"):
    """Extract full instructor objects from a section.

    Returns a list of instructor objects with all details (identifiers, names, role, etc.)
    role_filter can be:
    - "instructors": only professors/lecturers (role code PI)
    - "gsis": only GSIs/TAs (role code TNIC)
    - "staff": all teaching staff (excludes only APRX - administrative proxy)
    """
    # get all instructors
    all_instructors = jmespath.search("meetings[].assignedInstructors[]", section)
    if all_instructors is None:
        return []

    filtered = filter_instructors_by_role(all_instructors, role_filter)
    return list(filtered)


def section_instructors(section, id_attr="campus-uid", role_filter="staff"):
    """Extract disclosed identifiers of section instructors.

    role_filter can be:
    - "instructors": only professors/lecturers (role code PI)
    - "gsis": only GSIs/TAs (role code TNIC)
    - "staff": all teaching staff (excludes only APRX - administrative proxy)
    """
    # get all instructors
    all_instructors = jmespath.search("meetings[].assignedInstructors[]", section)
    if all_instructors is None:
        return set()

    filtered = filter_instructors_by_role(all_instructors, role_filter)

    # handle email vs campus-uid vs name differently since they're stored in different places
    if id_attr == "email":
        # emails are in instructor.emails array, similar to student emails
        # first try campus email (CAMP), then other email (OTHR)
        ids = []
        for instructor in list(filtered):
            camp_email = jmespath.search(
                "instructor.emails[?type.code=='CAMP'].emailAddress | [0]", instructor
            )
            if camp_email:
                ids.append(camp_email)
            else:
                othr_email = jmespath.search(
                    "instructor.emails[?type.code=='OTHR'].emailAddress | [0]",
                    instructor,
                )
                if othr_email:
                    ids.append(othr_email)
        return set(ids)
    elif id_attr == "name":
        # names are in instructor.names array - get the preferred or first formattedName
        ids = []
        for instructor in list(filtered):
            # Try to get preferred name first
            preferred_name = jmespath.search(
                "instructor.names[?preferred].formattedName | [0]", instructor
            )
            if preferred_name:
                ids.append(preferred_name)
            else:
                # Fall back to first available name
                any_name = jmespath.search(
                    "instructor.names[].formattedName | [0]", instructor
                )
                if any_name:
                    ids.append(any_name)
        return set(ids)
    else:
        # search for disclosed identifiers of type campus-uid
        ids = jmespath.search(
            f"[].instructor.identifiers[?disclose && type=='{id_attr}'].id[]",
            list(filtered),
        )
        if ids is None:
            return set()
        return set(ids)


def filter_instructors(section, constituents, identifier):
    """Old function to get instructors of either primary or non-primary
    courses."""
    is_primary = enrollments.section_is_primary(section)
    if (is_primary and constituents == "instructors") or (
        not is_primary and constituents == "gsis"
    ):
        return section_instructors(section, identifier)
        logger.info(f"exact: uids {uids}")
    return set()
