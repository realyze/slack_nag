#!/usr/bin/env
# -*- coding: utf-8 -*-

class PTBaseError(Exception):
    """ Base class for Pivotal Tracker related errors.
    """
    def __init__(self, msg, *args, **kwargs):
        super(PTBaseError, self).__init__(self, *args, **kwargs)
        self._msg = msg

    def __str__(self):
        return self._msg


class ServerError(PTBaseError):
    """ Server returned an error.
    """
    pass

class UnknownServerError(PTBaseError):
    """ Server returned an unknown message.
    """
    pass
