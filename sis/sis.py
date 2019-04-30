# vim:set et sw=4 ts=4:
import logging
import sys

import aiohttp

# logging
logging.basicConfig(stream=sys.stdout, level=logging.WARNING)
logger = logging.getLogger(__name__)

async def get_items(url, params, headers, item_type):
    '''Recursively get a list of items (enrollments, ) from the SIS.'''
    logger.info(f"getting {item_type}")
    data = []
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as r:
            if r.status == 404:
                logger.warning("http 404")
                return data # api returns 404 at end of pagination
            elif r.status in [401]:
                retval = {
                    'error': r.status,
                    'url': url,
                    'headers': headers,
                    'params': params
                }
                raise Exception(f"HTTP error {retval}")
            try:
                data = await r.json()
            except aiohttp.client_exceptions.ContentTypeError as e:
                data = await r.read()
                logger.error("Did not receive JSON.")
                logger.error(data)
                logger.error(f"status: {r.status}")
                logger.error(f"headers: {headers}")
                raise
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
    items += await get_items(url, params, headers, item_type)
    num = len(items)
    logger.debug(f'There are {num} items of type {item_type}')
    return items
