# vim:set et sw=4 ts=4:
import logging
import sys

from . import sis

# logging
logging.basicConfig(stream=sys.stdout, level=logging.WARNING)
logger = logging.getLogger(__name__)

# SIS endpoint
terms_uri = "https://apis.berkeley.edu/sis/v1/terms"

async def get_term_name(app_id, app_key, term_id):
    '''Given a term id, return the term's friendly name.'''
    uri = f'{terms_uri}/{term_id}'
    headers = {
        "Accept": "application/json",
        "app_id": app_id, "app_key": app_key
    }
    terms = await sis.get_items(uri, params, headers, 'terms')
    return terms[0]['name']

async def get_term_id(app_id, app_key, position='Current'):
    '''Given a temporal position of Current, Previous, or Next, return
       the corresponding term's ID.'''
    uri = terms_uri
    headers = {
        "Accept": "application/json",
        "app_id": app_id, "app_key": app_key
    }
    params = { "temporal-position": position }
    terms = await sis.get_items(uri, params, headers, 'terms')
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
    terms = await sis.get_items(uri, params, headers, 'terms')
    return terms[0]['id']

async def normalize_term_id(app_id, app_key, term_id):
    '''Convert temporal position (current, next, previous) to a numeric term id,
       or passthrough a numeric term id.'''
    if term_id.isalpha():
        term_id = await get_term_id(app_id, app_key, term_id)
    return term_id

