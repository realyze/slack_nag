#!/usr/bin/env
# -*- coding: utf-8 -*-

import requests
from lxml import etree

# Project configuration.
import config
import pt.errors
import logging
import functools

from models.story import Story

LOGGER = logging.getLogger('workflow')

# Pivotal tracker web API root URL.
_PT_ROOT_URL = "%s/services/v3" % config.pivotal_tracker_root_url


def log_http_call(fun):
    @functools.wraps(fun)
    def wrapper(*args, **kwargs):
        LOGGER.debug(
            "Sending %s request. Locals: %s" % (fun.__name__, locals()))
        response = fun(*args, **kwargs)
        LOGGER.debug(
            "response code: %s, body: '%s'" %
                (response.status_code, response.text))
        return response
    return wrapper

requests.get = log_http_call(requests.get)
requests.put = log_http_call(requests.put)


def _parse_response(
        xml_response, parse_selector, success_fun, check_selector=None):
    """
        Parameters:
            xml_response: string with the XML response
            parse_selector: Used to parse out elements passed to @success_fun.
            success_fun: Function that accepts one parameters - a list of nodes
                parsed from the xml using parse_selector
            [optional] check_selector: XPath selector. If not found
                in the xml response, a ServerError is raised. If left out,
                @parse_selector is used to check.
    """
    check_selector = check_selector or parse_selector
    root = etree.fromstring(xml_response.encode("utf-8"))

    if not root.xpath(check_selector):
        # Server returned an error.
        error_elem = root.xpath('/message') or root.xpath('/errors/error')
        if not error_elem:
            raise pt.errors.UnknownServerError("Unknown server error.")
        else:
            raise pt.errors.ServerError(error_elem[0].text)

    return success_fun(root.xpath(parse_selector))


def get_all_user_projects(token):
    url = '%s/projects/' % config.pt_api_url_root
    headers = {"X-TrackerToken": token}
    response = requests.get(url, headers=headers)
    def get_project_ids(elems):
        return [p.xpath('id').pop().text for p in elems]
    return _parse_response(
        response.text, '//projects/project',
        get_project_ids, '//projects')



def get_stories_for_project_id(project_id, token, limit_iterations=True):
    """ Connects to the PT web API and gets all the stories for a project
        with the given id.

        Parameters:
            limit_iterations: If True, only load stories from current & backlog.

        Return value:
            The result is a list of python Story objects.
            Raises an exception on failure.
    """
    project_url = ("%s/projects/%s/" %
        (config.pt_api_url_root, project_id))

    if limit_iterations:
        url = project_url + "iterations/current_backlog"
    else:
        url = project_url + "stories"

    headers = {"X-TrackerToken": token}
    # Get the stories.
    response = requests.get(url, headers=headers)

    def create_stories(elems):
        # Create our story models.
        stories = [Story.from_xml_elem(s) for s in elems]
        return stories

    return _parse_response(
        response.text, "//stories/story", create_stories,
        check_selector="//stories")


def append_label_to_a_story(project_id, story_id, token, label):
    """ Adds a label to a Pivotal Tracker story with id `story_id`.
    """
    return _label_worker(project_id, story_id, token, label, 'append')


def remove_label_from_a_story(project_id, story_id, token, label):
    """ Removes a label from a Pivotal Tracker story with id `story_id`.
    """
    return _label_worker(project_id, story_id, token, label, 'remove')

def replace_labels_in_a_story(project_id, story_id, token, labels):
    return _label_worker(project_id, story_id, token, labels, 'replace')

def _label_worker(project_id, story_id, token, label, action):
    """ Helper function that allows us to share code that appends/removes labels
        to/from a PT story.
    """
    url = ("%s/projects/%s/stories/%s" %
        (config.pt_api_url_root, project_id, story_id))

    story = get_story(project_id, token, story_id)
    headers = {"X-TrackerToken": token, "Content-type": "Application/xml"}
    try:
        # Carry out the action (either 'append' or 'remove').
	if action == 'replace':
            story.labels = label
	else:
            getattr(story.labels, action)(label)
    except ValueError:
        LOGGER.debug(
            "Trying to remove nonexistent label '%s' from story %s." %
            (label, story_id))
        return story
    response = requests.put(
        url,
        data='<story><labels>%s</labels></story>' % ','.join(story.labels),
        headers=headers)
    return _parse_response(response.text, "/story", _create_story)


def set_story_state(project_id, story_id, token, state, story_type):
    """ Connects to the Pivotal Tracker server and sends a request
        to change the state of a story with id @story_id to @state.

        Parameters:
            state: String. New state of the story.
            story_type: String. Type of the story (feature, bug or chore).

        Return value:
            Story model object of the updated story on success.
            Raises an exception on failure.
    """
    assert state in ('finished', 'started', 'delivered')
    assert story_type in ('feature', 'bug', 'chore')

    url = ("%s/projects/%s/stories/%s" %
        (config.pt_api_url_root, project_id, story_id))

    def get_finish_chore_payload():
        story = get_story(project_id, token, story_id)
        labels = ','.join(story.labels)
        # Add waiting-for-review label (PT lacks "finished" state for chores).
        payload = ('<story><labels>%s</labels></story>' %
            ','.join([labels, config.chore_review_state_label]).strip(','))
        return payload

    def get_deliver_chore_payload():
        story = get_story(project_id, token, story_id)
        if config.chore_review_state_label in story.labels:
            story.labels.remove(config.chore_review_state_label)
        # Remove waiting-for-review label and set state to "accepted" (which
        # means the chore is finished and done).
        payload = (
            '<story><labels>%s</labels>'
            '<current_state>%s</current_state></story>' %
                (','.join(story.labels), 'accepted'))
        return payload

    if story_type == 'chore' and state == 'finished':
        payload = get_finish_chore_payload()
    elif story_type == 'chore' and state == 'delivered':
        payload = get_deliver_chore_payload()
    else:
        payload = '<story><current_state>%s</current_state></story>' % state

    headers = {"X-TrackerToken": token, "Content-type": "Application/xml"}
    response = requests.put(url, data=payload, headers=headers)

    def check_state_set(elems):
        try:
            story = elems[0]
        except IndexError:
            raise pt.errors.ServerError("Invalid server response.")

        state = story.find("current_state")
        if state is None:
            raise pt.errors.ServerError(
                "Server returned no state for story %s." % story_id)

        return Story.from_xml_elem(story)

    return _parse_response(response.text, "/story", check_state_set)


def get_story(project_id, token, story_id):
    """ Returns a story model (requests the story data from the
        Pivotal Tracker server).
    """
    project_url = ("%s/projects/%s" % (config.pt_api_url_root, project_id))

    url = '%s/stories/%s' % (project_url, story_id)

    headers = {"X-TrackerToken": token}
    # Get the story.
    response = requests.get(url, headers=headers)

    return _parse_response(response.text, "/story", _create_story)


def _create_story(elems):
    story = next((Story.from_xml_elem(s) for s in elems), None)
    if not story:
        raise pt.errors.ServerError("Invalid server response.")
    else:
        return story
