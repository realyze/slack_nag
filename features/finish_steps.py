
from freshen import Given, When, Then, Before, After, scc, run_steps

# Use pyVows expectations (they are more readable).
from pyvows import expect

import mercurial.commands as hgcmd
import commands
import utils

@Then("(story|chore) (\S+) is successfully finished")
def check_story_finished(pt_type, story_id):
    run_steps(
        """
        Then a review request is posted to the Review Board server
        And branch %(sid)s is closed
        And branch %(sid)s is pushed to the central repository
        And develop branch is pulled and updated
        And branch %(sid)s is merged into develop
        And branch develop is pushed to the central repository
        And the %(type)s with id %(sid)s is finished in PT
        """ % {'sid': story_id, 'type': pt_type})


@Then("the parent changeset of the review request is the parent changeset of branch (\w+)")
def check_review_parent(branch_label):
    scc.ui.pushbuffer()
    hgcmd.log(
        scc.ui, scc.repo, date=None,
        rev=['p1(min(branch(%s)))' % branch_label],
        user=[],
        template='{node}')
    parent_changeset = utils.remove_ansi_codes(scc.ui.popbuffer())
    request_parent = commands.rb.postreview.call_args[1].get('parent')

    expect(parent_changeset).to_equal(request_parent)


@Then("the review request tip is the tip of branch (\S+)")
def check_review_tip(branch_label):
    scc.ui.pushbuffer()
    hgcmd.log(
        scc.ui, scc.repo, date=None,
        rev=['max(branch(%s))' % branch_label],
        user=[],
        template='{node|short}')
    tip = utils.remove_ansi_codes(scc.ui.popbuffer())
    request_tip = commands.rb.postreview.call_args[1].get('rev')

    expect(tip).to_equal(request_tip)


