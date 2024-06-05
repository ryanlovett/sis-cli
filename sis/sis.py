# vim:set et sw=4 ts=4:
import logging
import sys

import aiohttp

# logging
logging.basicConfig(stream=sys.stdout, level=logging.WARNING)
logger = logging.getLogger(__name__)

async def get_items(url, params, headers, item_type):
    '''Recursively get a list of items (enrollments, ) from the SIS.'''
    logger.info(f"get_items: getting {item_type}")
    data = []
    logger.debug(f"url: {url} | headers: {headers} | params: {params}")
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as r:
            if r.status == 404:
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

    # apiResponse node was removed from Terms API in 2/2024
    if 'apiResponse' in data:
        data = data['apiResponse']
    else:
        logger.debug("'apiResponse' not in data")

    # Return if there is no response (e.g. 404)
    if "response" not in data:
        logger.debug("get_items: response not in data")
        logger.debug(f"get_items: returning: {data}")
        return []
    # Return the whole response if no item_type is specified
    elif item_type in [None, ""]:
        return data["response"]
    # Return if the UID has no items
    elif item_type not in data["response"]:
        logger.debug(f"get_items: No {item_type} in response")
        return []
    # Get this page's items
    items = data["response"][item_type]

    # If we are not paginated, just return the items
    if 'page-number' not in params:
        logger.debug('no other pages')
        return items
    # Get the next page's items
    params['page-number'] += 1
    items += await get_items(url, params, headers, item_type)
    num = len(items)
    logger.debug(f'There are {num} items of type {item_type}')
    return items
