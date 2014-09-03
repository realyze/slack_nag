# -*- coding: utf-8 -*-
from freshen import Given, When, Then, Before, After, scc, run_steps

import commands
import mercurial.commands as hgcmd
import utils

# Use pyVows expectations (they are more readable).
from pyvows import expect


@Given("there is no (\S+) branch")
def ensure_branch_not_exists(branch_label):
    scc.ui.pushbuffer()
    hgcmd.branches(scc.ui, scc.repo)
    branches = utils.remove_ansi_codes(scc.ui.popbuffer()).strip()

    assert branch_label not in branches
