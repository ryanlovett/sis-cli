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
    '''Given a term and class section ID, return section data.'''
    uri = f'{students_url}/{identifier}'

    headers = {
        "Accept": "application/json",
        "app_id": app_id,
        "app_key": app_key
    }
    params = {
        "id-type": id_type,
        "inc-acad": "true", "inc-attr": "true",
        "inc-regs": "false", "inc-cntc": "false", "inc-regs": "false",
        "inc-dmgr": "false", "inc-work": "false", "inc-dob": "false",
        "inc-gndr": "false",
        "affiliation-status": "ACT", "inc-completed-programs": "true",
    }
    logger.debug(f"status for {identifier}")
    items = await sis.get_items(uri, params, headers, item_key)
    logger.debug(f"items: {items}")
    return items

async def get_academic_statuses(app_id, app_key, identifier, id_type):
    '''Given a student identifier, return student academic statuses.'''
    items = await get_student(app_id, app_key, identifier, id_type, 'academicStatuses')
    return items

async def get_name(app_id, app_key, identifier, id_type, code='Preferred'):
    '''Given a student identifier, return student names.'''
    items = await get_student(app_id, app_key, identifier, id_type, 'names')
    names = []
    for item in items:
        if jmespath.search('type.description', item) != code:
            continue
        sn = jmespath.search('familyName', item)
        givenName = jmespath.search('givenName', item)
        return f"{sn},{givenName}"

def get_academic_plans(status):
    logger.debug(f"status: {status}")
    plans = status.get('studentPlans', [])
    logger.debug(f"plans: {plans}")

    return list(map(lambda x: x['academicPlan']['plan'], plans))

async def get_emails(app_id, app_key, identifier, id_type='campus-id'):
    '''Given a identifier, return the student's email address.'''
    uri = f'{students_url}/{identifier}'
    item_key = 'emails'

    headers = {
        "Accept": "application/json",
        "app_id": app_id,
        "app_key": app_key
    }
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
