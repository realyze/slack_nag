#!/usr/bin/env
# -*- coding: utf-8 -*-

from flask import Flask, request
import test.storyxmlgen as xmlgen
from collections import deque
import pickle
from lxml import etree
import functools

app = Flask(__name__)

PORT = 5042


stories = []
errors = deque()
requests = []


def check_error(fun):
    @functools.wraps(fun)
    def wrapper(*args, **kwargs):
        global errors
        valid_errs = [err for err in errors if
            request.url.endswith(err['url']) and err['method'] == request.method]
        if not valid_errs:
            return fun(*args, **kwargs)
        else:
            errors.remove(valid_errs[0])
            return valid_errs[0]['msg']
    return wrapper


def rememeber_request(fun):
    @functools.wraps(fun)
    def wrapper(*args, **kwargs):
        global requests
        requests.append({
            'path': request.path,
            'method': request.method,
            'data': request.data
        })
        return fun(*args, **kwargs)
    return wrapper


@app.route("/services/v3/projects/<pid>/stories", methods=['GET'])
@rememeber_request
@check_error
def handle_stories(pid):
    response = xmlgen.generate_stories_response(
        [xmlgen.generate_story_xml(**s) for s in stories])
    return response


@app.route("/services/v3/projects/<pid>/stories/<story_id>", methods=['GET'])
@rememeber_request
@check_error
def handle_story_get_info(pid, story_id):
    """ Returns data for a single story.
    """
    matches = [s for s in stories if s["id"] == story_id]
    if not matches:
        return "error: no matching story"
    story = matches[0]

    response = xmlgen.generate_story_xml(**story)
    return response


@app.route("/services/v3/projects/<pid>/stories/<story_id>", methods=['PUT'])
@rememeber_request
@check_error
def handle_story_update(pid, story_id):
    """ Updates a story.
    """
    global stories
    matches = [s for s in stories if s["id"] == story_id]
    if not matches:
        return "error: no matching story"
    story = matches[0]

    root = etree.fromstring(request.data)
    labels = root.xpath('labels')
    if labels:
        story['labels'] = labels[0].text
    state = root.xpath('current_state')
    if state:
        story['current_state'] = state[0].text

    response = xmlgen.generate_story_xml(**story)
    return response


@app.route("/services/v3/projects/<pid>/iterations/<iteration>", methods=['GET'])
@rememeber_request
@check_error
def handle_iteration(pid, iteration):
    if iteration == "current_backlog":
        # Only return stories from current & backlog.
        selected_stories = [s for s in stories if
            s["iteration"] in iteration.split('_')]
    else:
        # Return all stories.
        selected_stories = stories
    response = xmlgen.generate_stories_response(
        [xmlgen.generate_story_xml(**s) for s in selected_stories])
    return response


@app.route('/stories/add', methods=['POST'])
def add_story():
    global stories
    stories.append(dict(request.form.items()))
    return "ok"


@app.route('/stories/update/<story_id>', methods=['POST'])
def update_story(story_id):
    global stories
    s = [s for s in stories if s['id'] == story_id][0]
    for key in request.form.keys():
        s[key] = request.form[key]
    return "ok"


@app.route('/errors/add', methods=['POST'])
def add_error():
    global errors
    errors.append({
        'msg': request.form['error'],
        'url': request.form['url'],
        'method': request.form['method']})
    return "ok"


@app.route("/stories/clear", methods=['POST'])
def clear_stories():
    global stories
    del stories[:]
    return "ok"


@app.route("/reset", methods=['POST'])
def reset_server():
    clear_stories()
    global errors
    errors.clear()
    global requests
    del requests[:]
    return "ok"


@app.route("/requests", methods=['GET'])
def get_requests():
    return pickle.dumps(requests)


if __name__ == "__main__":
    app.run(debug=True, port=PORT)

