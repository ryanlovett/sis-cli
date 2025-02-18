# vim:set et sw=4 ts=4:
from datetiem import datetime
import json
import logging
import sys

import jmespath

from . import sis

# logging
logging.basicConfig(stream=sys.stdout, level=logging.WARNING)
logger = logging.getLogger(__name__)

# SIS endpoint
classes_uri = "https://gateway.api.berkeley.edu/sis/v4/courses"


async def get_courses(app_id, app_key, **kwargs):
    """Given course selection criteria, return course data."""
    headers = {"Accept": "application/json", "app_id": app_id, "app_key": app_key}
    if len(kwargs.keys()) == 0:
        return []
    uri = classes_uri
    params = kwargs
    if "sort-by" not in params:
        params["sort-by"] = "catalog-number"
    params["page-number"] = 1

    courses = await sis.get_items(uri, params, headers, "courses")
    return courses


async def get_current_courses(app_id, app_key, **kwargs):
    # Call the original get_courses function
    courses = await get_courses(app_id, app_key, **kwargs)

    # Get the current date
    current_date = datetime.now().date()

    # Filter the courses based on the current date
    filtered_courses = [
        course
        for course in courses
        if "fromDate" in course
        and "toDate" in course
        and datetime.strptime(course["fromDate"], "%Y-%m-%d").date()
        <= current_date
        <= datetime.strptime(course["toDate"], "%Y-%m-%d").date()
    ]

    return filtered_courses


def print_courses(courses):
    """Default display of courses."""
    paths = {
        "displayName": "displayName",
        "title": "title",
        "description": "description",
        "prereqs": "preparation.requiredText",
        "credit_res": "creditRestriction.restrictionText",
        "hours": "formatsOffered.description",
        "subject": "academicCareer.description",
        "units": "credit.value.fixed.units",
    }

    output = [
        {key: jmespath.search(value, course) for key, value in paths.items()}
        for course in courses
    ]

    print(json.dumps(output, indent=4))
