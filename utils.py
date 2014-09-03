#!/usr/bin/env
# -*- coding: utf-8 -*-
import re
import config
import logging
import functools
import logging.handlers
import mercurial.util as hg_util


termcolor = None
try:
    import termcolor
except ImportError:
    pass


def initialize_logging():
    if not config.enable_logging:
        return
    file_logger = logging.handlers.RotatingFileHandler(
        filename=config.log_filepath,
        maxBytes=256*1024, backupCount=1)

    logging.getLogger('workflow').addHandler(file_logger)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    file_logger.setFormatter(formatter)
    logger = logging.getLogger('workflow')
    # Do not propagate log to stdout.
    logger.propagate = False
    logger.setLevel(config.log_level)


def log_me(fun):
    """ Logs wrapped function calls.
    """
    @functools.wraps(fun)
    def wrapped(*args, **kwargs):
        logging.getLogger('workflow').debug(
            "Calling '%s' with args: %s and kwargs: %s" % (fun, args, kwargs))
        try:
            rv = fun(*args, **kwargs)
        except hg_util.Abort, e:
            logging.getLogger('workflow').debug(
                "Plugin aborting with message: %s" % str(e))
            raise
        except Exception, e:
            logging.getLogger('workflow').error(
                "Exception thrown! Type: %s, message: %s" % (type(e), str(e)))
            raise
        else:
            logging.getLogger('workflow').debug(
                "Function '%s' return value: %s" % (fun, rv))
            return rv
    return wrapped


def abort_plugin(msg):
    """ Quits the plugin.
        To be called to abort the plugin because of a known reason (such as
        user input invalid story id etc.)
    """
    raise hg_util.Abort(msg)


def abort_plugin_with_unknown_error(msg):
    """ Quits the plugin.
        To be called when an unknown error occurs.
    """
    raise hg_util.Abort(msg)


def colorize_string(string):
    """ Use ANSI color codes to emulate a simple subset of textile formatting.
        We're supporting '*' (bold).

        Note: Requires 'termcolor' Python module. If not installed, this
        function just returns the string passed in.
    """
    if not termcolor:
        return string
    else:
        # Remove escaped parts.
        tmp = re.sub('==.*==', '', string)
        bolds = re.findall('\*.+\*', tmp)
        for bold in bolds:
            stripped_asterisks = bold.replace('*', '')
            tmp = tmp.replace(
                bold, termcolor.colored(stripped_asterisks, attrs=['bold']))
        return tmp


def filter_stories(stories, allowed_types=[], allowed_states=[]):
    """ Returns only stories that have one of the types specified
        @allowed_types and one of the states listed in @allowed_states.

        Parameters:
            stories: List of Story models.
            allowed_types: List of allowed story types. E.g.: ['bug', 'chore']
            allowed_types: List of allowed story states.
                E.g.: ['started', 'unscheduled']

        Doctest:
            >>> from models.story import Story
            >>> stories = [
            ...  Story(
            ...       'id1', 'pid', 'name', story_type='feature',
            ...       current_state='unscheduled'),
            ...   Story(
            ...       'id2', 'pid', 'name', story_type='feature',
            ...       current_state='started'),
            ...   Story(
            ...       'id3', 'pid', 'name', story_type='bug',
            ...       current_state='started'),
            ...   Story(
            ...       'id4', 'pid', 'name', story_type='chore',
            ...       current_state='unscheduled')]
            >>> res = filter_stories(
            ...     stories, allowed_types=['bug', 'feature'],
            ...     allowed_states=['started'])
            >>> len(res)
            2
            >>> res[0].id
            'id2'
            >>> res[1].id
            'id3'
    """
    return [s for s in stories if
        s.story_type in allowed_types and
        s.state in allowed_states]


def get_from_config(ui, key, section=config.hgrc_section_name, default=None):
    """ Returns the value of @key from .hgrc.
        If not found and @default is specified (i.e., not None),
        returns @default.
        Otherwise raises a ConfigError.
    """
    option_val = ui.config(section, key, default=default)
    if option_val is None:
        raise commands.ConfigError(
            "Please set '%s' in your .hgrc file (section '%s')." %
            (key, section))

    return option_val if option_val is not None else default


def opt_to_list(opt_string, delimiter=','):
    """ Convert @opt_string to Python list.
    """
    return [o.strip() for o in opt_string.split(delimiter)]


def remove_ansi_codes(string):
    """ Strips ANSI terminal color codes from @string.
    """
    return re.sub('\x1b[^m]*m', '', string)


def get_version_from_release_branch_label(branch_label):
    """ Parses the version string from the release breanch label.
    """
    # Assert we're using the expected format of release branch labels.
    assert '-' in branch_label
    version_string = branch_label.split('-')[1]
    return version_string


# Importing at the end of the module to break circular dependency.
import commands
