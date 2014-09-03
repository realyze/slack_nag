#!/usr/bin/env
# -*- coding: utf-8 -*-

"""
This Mercurial extension automates the actions required by the Salsita worklow.
"""

import sys
import os.path


# Add the root to pythonpath (otherwise we have problems importing modules).
sys.path.append(os.path.dirname(__file__))

# We need to disable demand import, it breaks urllib3 module (sometimes)
# See http://mercurial.selenic.com/bts/msg19339
from mercurial import demandimport
demandimport.disable()

import ptplugin

# TODO(tomas): Do we have to enable demandimport again? It breaks packages, so
# unless there's evidence that disabling it actually breaks something, we leave
# it disabled.

cmdtable = ptplugin.cmdtable
