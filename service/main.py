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
import ConfigParser
import dateutil.parser
import datetime

from slacker import Slacker
from dateutil.tz import tzlocal
from dateutil.relativedelta import relativedelta as delta
from dateutil import rrule

CFG_FILE = '%s/.workflow.cfg' % os.environ['HOME']


class RB_daemon_error(Exception):
    pass


def try_except(fn):
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception, e:
            et, ei, tb = sys.exc_info()
            raise RB_daemon_error, RB_daemon_error(e), tb
    return wrapped


@try_except
def notify_user(auth, user_obj, req):
    rb_user = rb.extensions.get_user_data(auth, user_obj['href'])
    if not rb_user:
        return

    pt_user = _slack_email_dict.get(rb_user['email'], None)
    if not pt_user:
        return

    last_updated = dateutil.parser.parse(req['last_updated'])
    now = datetime.datetime.now(tzlocal())
    idle_days = delta(now, last_updated).days
    idle_hours = delta(now, last_updated).hours + 24 * idle_days

    if idle_hours < 20:
        print ("review request %s from %s has been idle for %s hours => not nagging" % 
            (req['id'], pt_user['profile']['real_name'], idle_hours))
        return

    msg = ("%s, you have a lonely review request from %s (repo %s) waiting on your action at: " +
          "https://review.salsitasoft.com/r/%s .") % (
                  pt_user['profile']['real_name'],
                  req['links']['submitter']['title'],
                  req['links']['repository']['title'],
                  req['id'])

    if idle_days > 2:
        msg += ("*This is getting serious*. " +
            "It's been lying there for *%s days* now!" % (idle_days,))

    print " >>> %s" % (msg,)
    print " >>> idle for: %s days" % (idle_days,)

    #_slack.chat.post_message('@' + pt_user['name'], msg)


def get_work_days_diff(a, b):
    return len(list(rrule.rrule(rrule.DAILY,
        dtstart=a,
        until=b,
        byweekday=(rrule.MO, rrule.TU, rrule.WE, rrule.TH, rrule.FR))))


_slack = None
_slack_email_dict = {}

def main():
    global _slack
    global _slack_email_dict

    # Read the sensitive data from a config file.
    config = ConfigParser.RawConfigParser()
    config.read(CFG_FILE)

    pt_token = config.get('auth', 'pt_token')
    rb_user = config.get('auth', 'rb_user')
    rb_pwd = config.get('auth', 'rb_pwd')
    slack_token = config.get('auth', 'slack_token')

    # HACK: Set the gobal vars.
    _slack = Slacker(slack_token)
    members = _slack.users.list().body['members']
    _slack_email_dict = dict([[u['profile']['email'], u] for u in members])

    auth = {'username': rb_user, 'password': rb_pwd}

    # Returns all published unshipped requests.
    reqs = rb.extensions.get_review_requests2(
        {'max-results': 200, 'ship-it': 0}, auth)

    for req in reqs:
        added = dateutil.parser.parse(req['time_added'])
        # Check review request is at least two days old.
        days_delta = get_work_days_diff(added, datetime.datetime.now(tzlocal()))
        if days_delta >= 2:
            last_update = rb.extensions.get_last_update_info(auth, req['id'])

            print 'processing rid', req['id'], last_update['type']

            if last_update['type'] == 'review-request':
                for reviewer in req['target_people']:
                    notify_user(auth, reviewer, req)
                continue

            if last_update['type'] == 'diff':
                for reviewer in req['target_people']:
                    notify_user(auth, reviewer, req)
                continue

            if last_update['type'] == 'reply' or last_update['type'] == 'review':
                if last_update['user']['links']['self']['href'] == req['links']['submitter']['href']:
                    # Last review came from request submitter, now it's reviewer's turn.
                    for reviewer in req['target_people']:
                        notify_user(auth, reviewer, req)
                else:
                    notify_user(auth, req['links']['submitter'], req)
                continue


if __name__ == '__main__':
    main()
