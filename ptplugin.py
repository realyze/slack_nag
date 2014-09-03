#!/usr/bin/env
# -*- coding: utf-8 -*-

import config

import utils
utils.initialize_logging()


# Clearly mark new plugin call in the log.
import logging
logger = logging.getLogger('workflow')
logger.debug("----------------------------------------\n")
logger.debug("Plugin started\n")
logger.debug("----------------------------------------")


import commands


# Consts for commonly used options (to keep things DRY).
STORY_TYPES_PARAM = (
    't', 'types', "feature,bug", (
        "Story types to display (comma separated list of values from: "
        "feature,bug,chore,release'"))
STORY_STATES_PARAM = (
    '', 'states', "unscheduled,started,unstarted", (
        "Story states to display (comma separated list of values from: "
        "unscheduled,started,finished,delivered'"))
PID_PARAM = ('', 'project_id', "", 'PT project id')
TOKEN_PARAM = ('', 'token', "", 'PT token')
FORCE_PARAM = (
    'f', 'force', False,
    'Force selecting a story (ignore uncommited changes).')
CLEAN_PARAM = ('', 'clean', False, 'Revert any changes in the repository.')


# Mercurial command table.
cmdtable = {
    "ptlist": (commands.ptlist(),
        [
            PID_PARAM,
            TOKEN_PARAM,
            STORY_TYPES_PARAM,
            STORY_STATES_PARAM,
        ],
        "[options]"),

    "ptselect": (commands.ptselect(),
        [
            PID_PARAM,
            TOKEN_PARAM,
            STORY_TYPES_PARAM,
            STORY_STATES_PARAM,
            FORCE_PARAM,
            CLEAN_PARAM,
            ('s', 'story', '', 'Select a story by its id.'),
        ],
        "[options]"),

    "ptfinish": (commands.ptfinish(),
        [
            PID_PARAM,
            TOKEN_PARAM,
            CLEAN_PARAM,
            ('s', 'story', '',
                'Deliver story with specified id (can only be '
                'used when in the %s branch)' % config.devel_branch_label),
        ],
        "[options]"),

    "initflow": (commands.initflow(), [], ""),

    "release": (commands.release(),
        [
            PID_PARAM,
            TOKEN_PARAM,
            ('', 'start', False, 'Start a release branch'),
            ('', 'finish', False,
                'Finish a release branch (can only be called '
                'from the release branch)')],
        "[options]")
}
