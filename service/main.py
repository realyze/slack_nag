""" This is a service intended to be run periodically as a CRON job.

    It's purpose is to scan Pivotal Tracker and ReviewBoard and append
    a 'reviewed' label to any story that is finished and all its review requests
    have been approved (there must be at least 1 review request for the story in
    order for the service to notice it).

    The service expects a '${HOME}/.workflow.cfg' file with the following
    structure:

    [auth]
    pt_token = <PT_token>
    rb_user = <reviewboard username>
    rb_pwd = <password for the reviewboard user>

    The users (in PT & RB) should have access to all the projects (otherwise the
    service will not be able to update all the stories).
"""

import os
import sys
import re
import rb.extensions
import pt.api
import config
import ConfigParser
import dateutil.parser
import dateutil.relativedelta
import datetime
from slacker import Slacker

CFG_FILE = '%s/.workflow.cfg' % os.environ['HOME']


def is_story_approved(story_id, rb_auth):
    return rb.extensions.is_story_approved(
        'https://review.salsitasoft.com', story_id, rb_auth)


def iter_unprocessed(stories):
    for story in stories:
        if 'reviewed' in story.labels:
            # Skip stories that have already been processed by us.
            continue
        if (story.story_type in ['feature', 'bug']) and story.state == 'finished':
            # Handle finished features and bugs.
            yield story


def iter_rejected(stories):
    for story in stories:
        if (story.story_type in ['feature', 'bug']) and story.state == 'rejected':
            print str(story.id) + ' is rejected'
            yield story


def process_project(pt_token, project_id, rb_auth):
    # We're only interested in stories that are finished and don't have the
    # 'reviewed' label.
    stories = pt.api.get_stories_for_project_id(project_id, pt_token)

    # Filter out stories that have any open review requests.
    approved_stories = [s for s in iter_unprocessed(stories) if
        is_story_approved(s.id, rb_auth)]

    # Add a 'reviewed' label to the stories that survived our filtering.
    for s in approved_stories:
        pt.api.append_label_to_a_story(
            project_id, s.id, pt_token, config.pt_reviewed_label)

    for s in iter_rejected(stories):
        version = get_release(s)
        if version:
            labels = [l for l in s.labels if
                not re.match('release-[0-9]+(.[0-9]+){2}$', l)]
            labels.append('rejected-' + version)
            pt.api.replace_labels_in_a_story(
                project_id, s.id, pt_token, labels)


def get_release(story):
    for label in story.labels:
        m = re.match('release-([0-9]+([.][0-9]+){2})$', label)
        if m:
            return m.groups()[0]


def process_stories(pt_token, rb_auth):
    project_ids = pt.api.get_all_user_projects(pt_token)
    for project_id in project_ids:
        process_project(pt_token, project_id, rb_auth)


def notify_user(auth, user_obj, req):
    try:
        rb_user = rb.extensions.get_user_data(auth, user_obj['href'])
        if not rb_user:
            return

        pt_user = _slack_email_dict.get(rb_user['email'], None)
        if not pt_user:
            return

        if pt_user['name'] == u"tomas.brambora":
            msg = ("%s, you have a lonely review request waiting on your action at: " +
                  "https://review.salsitasoft.com/r/%s") % (pt_user['profile']['real_name'], req['id'])
            _slack.chat.post_message('@' + pt_user['name'], msg)
    except:
        print 'ERROR when notifying user', sys.exc_info()[0]


_slack = None
_slack_email_dict = {}

def main():
    # Read the sensitive data from a config file.
    config = ConfigParser.RawConfigParser()
    config.read(CFG_FILE)
    pt_token = config.get('auth', 'pt_token')
    rb_user = config.get('auth', 'rb_user')
    rb_pwd = config.get('auth', 'rb_pwd')
    slack_token = config.get('auth', 'slack_token')

    _slack = Slacker(slack_token)
    members = _slack.users.list().body['members']
    _slack_email_dict = dict([[u['profile']['email'], u] for u in members])

    #process_stories(pt_token, {'username': rb_user, 'password': rb_pwd})
    auth = {'username': rb_user, 'password': rb_pwd}
    reqs = rb.extensions.get_review_requests2(
        {'max-results': 200, 'ship-it': 0}, auth)
    for req in reqs:
        updated = dateutil.parser.parse(req['last_updated'])
        updated = updated + dateutil.relativedelta.relativedelta(days=+2)
        if updated.replace(tzinfo=None) < datetime.datetime.now():
            last_update = rb.extensions.get_last_update_info(auth, req['id'])
            print "last update %s: %s" %(req['id'], str(last_update))
            if last_update['type'] == 'review-request':
                notify_user(auth, req['target_people'][0], req)
                continue
            if last_update['type'] == 'diff':
                notify_user(auth, req['target_people'][0], req)
                continue
            if last_update['type'] == 'reply':
                if last_update['user']['links']['self']['href'] == req['links']['submitter']['href']:
                    # Last review came from request submitter, now it's reviewer's turn.
                    notify_user(auth, req['target_people'][0], req)
                else:
                    notify_user(auth, req['links']['submitter'], req)
                continue
            if last_update['type'] == 'review':
                notify_user(auth, req['links']['submitter'], req)
                continue


if __name__ == '__main__':
    main()
