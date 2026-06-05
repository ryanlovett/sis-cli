# vim:set et sw=4 ts=4:
import logging
import sys

import jmespath

from . import sis

# logging
logging.basicConfig(stream=sys.stdout, level=logging.WARNING)
logger = logging.getLogger(__name__)

# Various SIS endpoints
students_url = "https://gateway.api.berkeley.edu/sis/v2/students"


async def get_student(app_id, app_key, identifier, id_type, item_key):
    """Given a term and class section ID, return section data."""
    uri = f"{students_url}/{identifier}"

    headers = {"Accept": "application/json", "app_id": app_id, "app_key": app_key}
    params = {
        "id-type": id_type,
        "affiliation-status": "ACT",
        "inc-acad": "true",
        "inc-attr": "true",
        "inc-cntc": "false",
        "inc-completed-programs": "true",
        "inc-dmgr": "false",
        "inc-dob": "false",
        "inc-gndr": "false",
        "inc-regs": "false",
        "inc-work": "false",
    }
    logger.debug(f"status for {identifier}")
    items = await sis.get_items(uri, params, headers, item_key)
    logger.debug(f"items: {items}")
    return items


async def get_academic_statuses(app_id, app_key, identifier, id_type):
    """Given a student identifier, return student academic statuses."""
    items = await get_student(app_id, app_key, identifier, id_type, "academicStatuses")
    return items


async def get_name(app_id, app_key, identifier, id_type, code="Preferred"):
    """Given a student identifier, return student names."""
    items = await get_student(app_id, app_key, identifier, id_type, "names")
    for item in items:
        if jmespath.search("type.description", item) != code:
            continue
        sn = jmespath.search("familyName", item)
        givenName = jmespath.search("givenName", item)
        return f"{sn},{givenName}"


def get_academic_plans(status):
    logger.debug(f"status: {status}")
    return jmespath.search("studentPlans[?academicPlan].academicPlan.plan", status)


async def get_emails(app_id, app_key, identifier, id_type="campus-id"):
    """Given a identifier, return the student's email address."""
    uri = f"{students_url}/{identifier}"
    item_key = "emails"

    headers = {"Accept": "application/json", "app_id": app_id, "app_key": app_key}
    params = {
        "id-type": id_type,
        "inc-cntc": "true",
        "affiliation-status": "ACT",
    }
    items = await sis.get_items(uri, params, headers, item_key)
    logger.debug(f"items: {items}")

    # return disclosed campus emails
    expr = "[?disclose && type.code=='CAMP'].emailAddress"
    return jmespath.search(expr, items)


async def get_students_by_plan_code(
    app_id,
    app_key,
    plan_code,
    affiliation_status="ACT",
    inc_acad=False,
    inc_completed_programs=False,
    inc_cntc=False,
    term_id=None,
):
    """Get students by academic plan code, paginating through all results.

    Calls GET /v2/students?plan-code={code}&page-size=100 with page-number
    pagination. Returns a list of raw student objects.
    """
    headers = {"Accept": "application/json", "app_id": app_id, "app_key": app_key}
    params = {
        "plan-code": plan_code,
        "affiliation-status": affiliation_status,
        "page-size": 100,
        "page-number": 1,
    }
    if inc_acad:
        params["inc-acad"] = "true"
    if inc_completed_programs:
        params["inc-completed-programs"] = "true"
    if inc_cntc:
        params["inc-cntc"] = "true"
    if term_id is not None:
        params["term-id"] = term_id

    logger.debug(f"Getting students for plan code: {plan_code}")
    items = await sis.get_items(students_url, params, headers, "students")
    logger.debug(f"Got {len(items)} students for plan code {plan_code}")
    return items


async def get_students_by_id_list(
    app_id,
    app_key,
    id_list,
    id_type="student-id",
    inc_acad=False,
    inc_completed_programs=False,
):
    """Get students by a comma-separated list of IDs.

    Calls GET /v2/students/list with id-list and id-type parameters.
    Returns a list of raw student objects.
    """
    url = f"{students_url}/list"
    headers = {"Accept": "application/json", "app_id": app_id, "app_key": app_key}
    params = {
        "id-list": id_list,
        "id-type": id_type,
        "page-size": 100,
        "page-number": 1,
    }
    if inc_acad:
        params["inc-acad"] = "true"
    if inc_completed_programs:
        params["inc-completed-programs"] = "true"

    logger.debug("Getting students by id list")
    items = await sis.get_items(url, params, headers, "students")
    logger.debug(f"Got {len(items)} students from id list")
    return items


def deduplicate_students(students):
    """Deduplicate a list of student objects by campus-uid (first wins)."""
    seen = {}
    for student in students:
        uid = extract_campus_uid(student)
        if uid and uid not in seen:
            seen[uid] = student
    return list(seen.values())


def extract_campus_uid(student):
    """Extract campus-uid from a student object."""
    return jmespath.search("identifiers[?type=='campus-uid'].id | [0]", student)


def extract_student_id(student):
    """Extract student-id from a student object."""
    return jmespath.search("identifiers[?type=='student-id'].id | [0]", student)


def extract_name(student):
    """Extract preferred name formatted as 'Last, First'."""
    name = jmespath.search("names[?type.code=='PRF'] | [0]", student)
    if name:
        sn = name.get("familyName", "")
        given = name.get("givenName", "")
        if sn and given:
            return f"{sn}, {given}"
    return None


def extract_email(student):
    """Extract disclosed campus email from a student object."""
    expr = "emails[?disclose && type.code=='CAMP'].emailAddress | [0]"
    return jmespath.search(expr, student)
