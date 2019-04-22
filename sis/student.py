# vim:set et sw=4 ts=4:
import logging
import sys

from . import sis

# logging
logging.basicConfig(stream=sys.stdout, level=logging.WARNING)
logger = logging.getLogger(__name__)

# Various SIS endpoints
students_url = "https://apis.berkeley.edu/sis/v2/students"

def get_academic_statuses(app_id, app_key, identifier, id_type):
    '''Given a term and class section ID, return section data.'''
    uri = f'{students_url}/{identifier}'
    item_key = 'academicStatuses'

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
    items = sis.get_items(uri, params, headers, item_key)
    
    return items

def get_academic_plans(status):
    plans = status.get('studentPlans', [])
    return list(map(lambda x: x['academicPlan']['plan'], plans))
