#!/usr/bin/env
# -*- coding: utf-8 -*-
from mock import Mock
import requests
import pickle
import test.mock_server
import uuid
from freshen import scc


def get_story_state_change_requests(story_id):
    requests = get_requests_sent_to_server()
    story_change_url = ('/services/v3/projects/%s/stories/%s' %
        (scc.project_id, story_id))

    state_changes = [r for r in requests if
        r['path'] == story_change_url and r['method'] == 'PUT']

    return state_changes


TEST_SERVER_ROOT = "http://127.0.0.1:%s" % test.mock_server.PORT


def create_mock_ui(_token=None, _project_id=None):
    """ Set up the test buffer for hg to write to.
    """
    ui_mock = Mock()
    ui_mock.test_buffer = [""]
    def test_buffer_write(msg):
        ui_mock.test_buffer[-1] += msg
    ui_mock.write = test_buffer_write

    def fake_popbuffer():
        return ui_mock.test_buffer.pop()
    ui_mock.popbuffer = fake_popbuffer

    def fake_pushbuffer():
        ui_mock.test_buffer.append("")
    ui_mock.pushbuffer = fake_pushbuffer

    return ui_mock


def add_story_to_server(story_dict):
    requests.post(TEST_SERVER_ROOT + '/stories/add', data=story_dict)

def update_story_on_server(story_dict):
    requests.post(
        TEST_SERVER_ROOT + '/stories/update/' + story_dict['id'],
        data=story_dict)


def add_error_to_server(error_xml, error_url=None, error_method=None):
    decl = u'<?xml version="1.0" encoding="UTF-8"?>'
    requests.post(
        TEST_SERVER_ROOT + '/errors/add',
        data={'error': '\n'.join([decl, error_xml]), 'url': error_url,
        'method': error_method})


def clear_server_stories():
    requests.post(TEST_SERVER_ROOT + '/stories/clear')

def reset_server():
    requests.post(TEST_SERVER_ROOT + '/reset')


def get_requests_sent_to_server():
    return pickle.loads(
        requests.get(TEST_SERVER_ROOT + '/requests').text.encode('UTF-8'))


def create_random_file():
    """ Creates a new file with random name (in the current working dir) and
        returns the name.
    """
    filename = str(uuid.uuid1())
    open(filename, "w").close()
    return filename
