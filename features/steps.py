#!/usr/bin/env
# -*- coding: utf-8 -*-
import urllib2
import mercurial.util
from lxml import etree
import uuid

from mock import Mock, ANY
from mercurial.fancyopts import fancyopts

from freshen import Given, When, Then, Before, After, scc, run_steps

import rb
import utils
import features
import features.common as common
import commands
import ptplugin
import config
import models.story
import hgapi

import tempfile
import subprocess
import os
import shutil
import fnmatch

import mercurial.commands as hgcmd

import mercurial.ui as ui
import mercurial.hg as hg
from pyvows import expect


# Use pyVows expectations (they are more readable).


"""===================
  Fixtures & Helpers
==================="""

@Before
def setup(sc):
    scc.hg_server_pids = []

    scc.test_dir = os.path.dirname(features.__file__)

    scc.repo_dir = tempfile.mkdtemp()
    os.chdir(scc.repo_dir)
    subprocess.call(['hg', 'init'], stderr=subprocess.PIPE)
    with open('.hg/hgrc', 'w') as hgrc:
        hgrc.write(
"""
[paths]
default=https://some.default.url

[ui]
# We don't want any merge tool for the tests (otherwise we wouldn't be able to
# tell easily if there were conflicts).
merge = None
""")

    scc.ui = ui.ui()
    scc.ui.pushbuffer()
    scc.ui.readconfig("./.hg/hgrc")
    scc.repo = hg.repository(ui.ui(), ".")

    # Inital commit so that default branch is created.
    with open("./test_file.txt", "w") as f:
        f.write("Initial commit")
    scc.ui.pushbuffer()
    hgcmd.add(
        scc.ui, scc.repo, "./test_file.txt")
    hgcmd.commit(
        scc.ui, scc.repo, message="initial commit")
    scc.ui.popbuffer()
    scc.branches = set(['default'])

    # We need to mock those, since it's hard to use the original commands.
    hgcmd.push = Mock(return_value=0)
    hgcmd.pull = Mock(return_value=0)
    commands.rb.postreview = Mock(return_value=0)

    # Mock commands.abort_plugin so that we can count its calls.
    utils.abort_plugin = Mock(side_effect=utils.abort_plugin)
    scc.exceptions = []

    scc.ui.warn = Mock()

    # Mock commands.abort_plugin_with_unknown_error so that we can
    # count its calls.
    utils.abort_plugin_with_unknown_error = Mock(
        side_effect=utils.abort_plugin_with_unknown_error)

    import pt.api
    pt.api.config.pt_api_url_root = (common.TEST_SERVER_ROOT + '/services/v3')

    scc.rb_api_mock = Mock
    rb.extensions.make_rbclient = Mock(return_value=scc.rb_api_mock)

    scc.stories = []
    # Id of the currently selected story.
    scc.selected_story_id = None


@Before
def setup_reviewboard_mocks(sc):
    """ Create all the stubs/mocks we need for testing reviewboard-related code.
    """
    # ids of stories that have beeen ship-it'ed in RB.
    scc.accepted_stories = []

    def fake_get_review_requests(opts):
        # We're being clever here - we're using story id as the review request
        # id (it makes it easier to matcvh it to the story later on).
        all_story_ids = [s.id for s in scc.stories]
        if not opts.get('ship-it', None):
            return [{'id': s.id, 'branch': s.id} for s in scc.stories]
        accepted_story_ids = [story_id for story_id in scc.accepted_stories]
        if opts['ship-it'] == True:
            return [{'id': s.id, 'branch': s.id} for s in accepted_story_ids]
        elif opts['ship-it'] == True:
            return [{'id': s.id, 'branch': s.id} for id in all_story_ids if
                not id in accepted_story_ids]

    def fake_get_reviews_for_review_request(rev_req_id):
        return [{'ship_it': rev_req_id in scc.accepted_stories}]

    scc.rb_api_mock.get_review_requests = Mock(
        side_effect=fake_get_review_requests)

    scc.rb_api_mock.get_reviews_for_review_request = Mock(
        side_effect=fake_get_reviews_for_review_request)


@After
def teardown(sc):
    shutil.rmtree(scc.repo_dir)
    common.reset_server()
    scc.ui.popbuffer()


@Before("@quit_when_prompted")
def setup_quit_when_prompted(sc):
    """ Mock hg ui prompt to return 'q'.
    """
    scc.ui.prompt = Mock(return_value="q")

@Before("@raise_if_prompted")
def setup_prompt_error(sc):
    scc.ui.prompt = Mock(
        side_effect=Exception("User should not be prompted!"))


def abort_guard(fun):
    """ Catches Mercurial.util.Abort exception (standard way to
        quit a hg plugin), so that it does not pollute the test output
        and we can easily verify it has been raised.
    """
    def wrapper(*args, **kwargs):
        try:
            fun(*args, **kwargs)
        except mercurial.util.Abort, e:
            scc.exceptions.append(e)
    return wrapper


"""===================
        GIVENs
==================="""

@Given('I have a PT project with ID "(\w+)"')
def setup_project(project_id):
    scc.project_id = project_id


@Given("the project has the stories defined in file ([^\t]+)")
def load_fake_stories(filename):
    """ Load stories defined in @filename.
    """
    with open(os.path.join(scc.test_dir, filename), 'r') as story_file:
        lines = [l for l in story_file.read().split('\n') if l]
        headers = lines[0]
        keys = [h.strip() for h in headers.split('|')]

        def create_story_dict(line):
            values = [i.strip() for i in line.split('|')]
            return dict(zip(keys, values))

        create_fake_stories([create_story_dict(l) for l in lines[1:]])


@Given('the project has the following stories:')
def load_fake_stories_from_table(table):
    stories_dicts = [dict(zip(table.headings, row)) for row in table.rows]
    create_fake_stories(stories_dicts)

@Given('the project has no stories')
def load_no_stories_from_table():
    pass


def create_fake_stories(stories_dicts):
    # Prepare fake XML response.
    for story_dict in stories_dicts:
        story_dict["project_id"] = scc.project_id
        common.add_story_to_server(story_dict)
        # Remember the story.
        scc.stories.append(models.story.Story(**story_dict))


@Given(u'I have the following in my .hgrc file:')
def append_to_hgrc(cfg_section_string):
    hgrc = open('.hg/hgrc', 'a')
    hgrc.write(cfg_section_string)
    hgrc.close()
    scc.ui.readconfig('./.hg/hgrc')


@Given(u'there are (some|no) uncommited changes in the working copy')
def fake_status_command(changes):
    if changes == 'some':
        with open('test_file.txt', 'a') as f:
            f.write("appended a change")


@Given("the PT server returns a failure message for story id (\w+) (start|finish|deliver) request")
def mock_server_failure(story_id, state):
    response_xml = '<message>The service is temporarily down</message>'
    common.add_error_to_server(response_xml, 'stories/%s' % story_id, 'PUT')


@Given('I will type "(\w+)" when I am prompted')
def mock_input(input_value):
    scc.ui.prompt = Mock(return_value=input_value)


@Given("reverting the changes in the working directory will fail")
def mock_revert_failure():
    # rv != 0 means failure.
    hgapi.hg_commands.revert.return_value = 1


@Given("the story with id (\w+) has not been pointed")
def mock_starting_unpointed_story_server_response(story_id):
    response_xml = u'''
<errors>
    <error>Stories in the started state must be estimated.</error>
</errors>'''
    common.add_error_to_server(response_xml, 'stories/%s' % story_id, 'PUT')


@Given("branch (\S+) has been commited")
def create_branch_and_commit(branch_label, switch_to_old_branch=True):
    scc.ui.pushbuffer()

    hgcmd.branch(scc.ui, scc.repo)
    output = utils.remove_ansi_codes(scc.ui.popbuffer())
    old_branch = output.strip()

    switch_to_branch(branch_label)

    scc.ui.pushbuffer()

    hgcmd.add(scc.ui, scc.repo, common.create_random_file())
    hgcmd.commit(
        scc.ui, scc.repo, message="creating branch")

    scc.ui.popbuffer()

    if switch_to_old_branch:
        switch_to_branch(old_branch)


@Given("the (story|chore) with id (\w+) is selected")
def fake_that_story_has_been_selected(type, story_id):
    scc.ui.pushbuffer()
    types_arg = ""
    if type == "chore":
        types_arg = "--types chore"
    invoke_hg_command('ptselect', '--story %s %s' % (story_id, types_arg))
    scc.ui.popbuffer()

    scc.selected_story_id = story_id


@Given("the (story|chore) with id (\w+) has been finished")
def fake_that_story_has_been_finished(_type, story_id):
    story = [s for s in scc.stories if s.id == story_id][0]
    story.current_state = "finished"
    switch_to_branch(story_id)
    create_branch_and_commit(story_id)


@Given("branch (\w+) exists")
def create_branch(branch_label):
    return create_branch_and_commit(branch_label)


@Given("the current branch has label (\S+)")
def switch_to_branch(branch_label):
    scc.ui.pushbuffer()
    try:
        hgcmd.branch(scc.ui, scc.repo, branch_label)
    except mercurial.util.Abort:
        hgcmd.update(scc.ui, scc.repo, branch_label)
    scc.ui.popbuffer()


@Given("the parent changeset of the current branch is")
def fake_parent_changeset(changeset_info):
    def fake_log(ui, *_args, **_kwargs):
        ui.write(changeset_info)
        return 0
    hgapi.hg_commands.log.side_effect = fake_log


@Given("there is (something|nothing) to merge")
def fake_merge_status(choice):
    pass


@Given("there will be (no|some) conflicts when merging with branch (\S+)")
def fake_conflicts(choice, branch):
    if choice == "some":
        conflicting_filename = str(uuid.uuid1())

        scc.ui.pushbuffer()
        hgcmd.branch(scc.ui, scc.repo)
        orig_branch = utils.remove_ansi_codes(scc.ui.popbuffer()).strip()

        hgcmd.update(scc.ui, scc.repo, branch)
        with file(conflicting_filename, 'w') as f:
            f.write('1')
        hgcmd.addremove(scc.ui, scc.repo)
        hgcmd.commit(scc.ui, scc.repo, message='conflict 1')

        hgcmd.update(scc.ui, scc.repo, orig_branch)
        with file(conflicting_filename, 'w') as f:
            f.write('2')
        hgcmd.addremove(scc.ui, scc.repo)
        hgcmd.commit(scc.ui, scc.repo, message='conflict 2')


@Given("review request id will be (\S+)")
def simulate_fake_review_with_id(review_request_id):
    post_plugin_output = (
    """
    Changeset 80:ea4afbd1f111
    ---------------------------
    A commit message.

    reviewboard:	https://dev.salsitasoft.com/rb/

    username: test.user
    Looking for 'dev.salsitasoft.com /rb/' cookie in /Users/test/.post-review-cookies.txt
    Loaded valid cookie -- no login required
    review request draft saved: https://dev.salsitasoft.com/rb//r/12/
    """)

    def post_side_effect(ui, _repo, *_args, **_kwargs):
        ui.write(post_plugin_output)
        return 0

    commands.rb.postreview.side_effect = post_side_effect


@Given("hg post will return the following output:")
def fake_hg_post_output(output):
    def post_side_effect(ui, _repo, *_args, **_kwargs):
        ui.write(output)
        return 0
    commands.rb.postreview.side_effect = post_side_effect


@Given("Review Board will return an error when creating a request")
def fake_rb_create_request_error():
    commands.rb.postreview.side_effect = lambda *args, **kwargs: 1


@Given("there are unresolved conflicts")
def create_unresolved_conflict():
    create_branch_and_commit('conflicting_branch', switch_to_old_branch=True)
    fake_conflicts('some', 'conflicting_branch')
    hgcmd.merge(scc.ui, scc.repo, 'conflicting_branch')


@Given("pushing to the remote repository will fail")
def fake_push_failure():
    hgapi.hg_commands.push.side_effect = mercurial.util.Abort(
        "Error message.")


@Given("we have restarted a rejected story with id (\w+)")
def create_closed_branch(branch_label):
    hgcmd.branch(scc.ui, scc.repo, branch_label)
    hgcmd.add(
        scc.ui, scc.repo, common.create_random_file())
    hgcmd.commit(
        scc.ui, scc.repo, message="new branch")
    switch_to_branch(config.devel_branch_label)


@Given("there is something to push")
def create_changeset():
    with open("test_file.txt", "a") as f:
        f.write("change")
    hgcmd.commit(scc.ui, scc.repo, message="change")


@Given("the (story|chore) with id (\w+) has been delivered partially")
def partially_deliver_story(type, story_id):
    fake_that_story_has_been_finished(type, story_id)

    ui = scc.ui
    repo = scc.repo

    hgcmd.commit(ui, repo, message=config.close_branch_msg, close_branch=True)
    switch_to_branch(config.devel_branch_label)
    hgcmd.merge(ui, repo, story_id)
    hgcmd.commit(ui, repo, message=config.merge_msg % story_id)

    switch_to_branch(story_id)

@Given("there are open review requests in reviewboard for story (\w+)")
def mock_open_review_requests(branch_label):
    # Nothing to do... Just assert that the story is not accepted (to prevent
    # bugs)
    assert branch_label not in scc.accepted_stories

@Given("story (\w+) has been marked as ship-it in RB")
def mark_story_as_shipit(story_id):
    scc.accepted_stories.append(story_id)

@Given("the branch with label (\w+) has (unclosed|closed) parent branch (\w+)")
def create_branch_with_parent(child_branch_label, choice, parent_branch_label):
    if parent_branch_label != config.devel_branch_label:
        create_branch_and_commit(parent_branch_label)
    switch_to_branch(parent_branch_label)
    create_branch_and_commit(child_branch_label)
    if choice == 'closed':
        # Close the parent branch.
        hgcmd.commit(
            scc.ui, scc.repo, message="Closing branch", close_branch=True)
    # Update back to the child branch.
    switch_to_branch(child_branch_label)


@Given("the repository has been initialized using the plugin")
def initialize_repo_for_plugin():
    commands.initflow()(scc.ui, scc.repo)
    # Add the development branches to our known branches.
    scc.branches.add(config.devel_branch_label)


"""===================
        WHENs
==================="""

@When(u'I issue the command: hg (\w+)(.*)')
@abort_guard
def invoke_hg_command(command_name, opt_string=""):
    # Use mercurial's fancyopts to parse the args string.
    opts = ptplugin.cmdtable[command_name][1]
    params = {}
    args = fancyopts(opt_string.split(), opts, params, True)
    cmd_instance = getattr(commands, command_name)()
    cmd_instance(scc.ui, scc.repo, *args, **params)


"""===================
        THENs
==================="""

@Then(u'I see the following (output|ANSI colorized output):')
def check_output(expected_output, choice):
    observed_output = scc.ui.popbuffer()
    if choice == "output":
        observed_output = utils.remove_ansi_codes(observed_output)
    else:
        # We need to re-encode (Freshen seems to handle unicode wrong).
        expected_output = expected_output.decode('unicode-escape').encode('utf-8')

    # We must push a new buffer, so that that teardown has a buffer to pop.
    scc.ui.pushbuffer()
    expect(observed_output.rstrip('\n')).to_be_like(expected_output)


@Then(u'I am prompted to select one of the stories')
def mock_ui_prompt():
    expect(scc.ui.prompt.call_count).to_equal(1)


@Then("Mercurial quits with (a message|an error message)")
def check_hg_aborts(_msg_type):
    expect(scc.exceptions).Not.to_be_empty()
    # Check that we haven't aborted with an unknown error (we're only
    # supposed to see known errors in our tests).
    expect(utils.abort_plugin_with_unknown_error.call_count).to_equal(0)


@Then("no branch is created")
def check_no_branch_created():
    scc.ui.pushbuffer()
    hgcmd.branches(scc.ui, scc.repo)
    output = utils.remove_ansi_codes(scc.ui.popbuffer())

    lines = [l for l in output.split('\n') if l]
    expect(len(lines)).to_equal(len(scc.branches))


@Then("all uncommited changes in the working copy have been reverted")
def check_revert_called():
    scc.ui.pushbuffer()
    hgcmd.status(scc.ui, scc.repo, modified=True)
    output = scc.ui.popbuffer()
    expect(output).to_equal("")


@Then("no backup files have been created")
def check_revert_called_no_backup():
    matches = []
    for root, _dirnames, filenames in os.walk('.'):
        for filename in fnmatch.filter(filenames, '*.orig'):
            matches.append(os.path.join(root, filename))
    expect(matches).to_be_empty()


@Then(u'a new branch called "([^"]*)" is created')
def check_branch_was_created(branch_label):
    check_current_branch(branch_label)


@Then("the current branch has label (\w+)")
def check_current_branch(branch_label):
    scc.ui.pushbuffer()
    hgcmd.branch(scc.ui, scc.repo)
    output = utils.remove_ansi_codes(scc.ui.popbuffer())

    expect(output.strip()).to_equal(branch_label)


@Then("(no|a) review request is posted to the Review Board server")
def check_review_has_been_posted(choice):
    postreview = commands.rb.postreview
    if choice == "a":
        expect(postreview.call_count).to_equal(1)
    else:
        expect(postreview.call_count).to_equal(0)


@Then("the (story|chore) with id (\S+) is (started|finished|delivered) in PT")
def check_story_state_changed(story_type, story_id, expected_state):
    """ Checks whether the last request that changed the state of story with
        id == @story_id set its state to @expected_state.
    """
    requests = common.get_story_state_change_requests(story_id)

    labels = ''
    state = ''

    for r in requests:
        root = etree.fromstring(r['data'])
        # Get labels.
        labels_elems = root.xpath('/story/labels[last()]')
        labels = labels_elems[0].text or '' if labels_elems else ''
        # Get state.
        state_elems = root.xpath('/story/current_state[last()]')
        state = state_elems[0].text or '' if state_elems else ''

    if story_type == 'chore' and expected_state == 'finished':
        # Check for requests to finish a chore (setting a label).
        expect(labels).to_include(config.chore_review_state_label)

    elif story_type == 'chore' and expected_state == 'delivered':
        # Check for requests to deliver a chore (removing a label and setting
        # state to "accepted").
        expect(labels).Not.to_include(config.chore_review_state_label)
        expect(state).to_include('accepted')
    else:
        expect(state).to_include(expected_state)


@Then("the story with id (\w+) is not (started|finished|delivered) in PT")
def check_story_state_not_changed(story_id, state):
    requests = common.get_story_state_change_requests(story_id)
    state_changes = [r for r in requests if
        r['data'].find('<current_state>%s</current_state>' % state) >= 0]
    expect(state_changes).to_be_empty()


@Then("the current branch is (updated|not updated) to (\w+)")
def check_branch_update(status, target):
    scc.ui.pushbuffer()
    hgcmd.branch(scc.ui, scc.repo)
    output = utils.remove_ansi_codes(scc.ui.popbuffer())

    if status == "updated":
        expect(output.strip()).to_equal(target)
    else:
        expect(output.strip()).Not.to_equal(target)


@Then("branch (\S+) is (merged|not merged) into (\w+)")
def check_branch_merge(merged_branch_label, status, target_branch_label):
    scc.ui.pushbuffer()
    # Get log output for all the merge changesets between @merged_branch_label
    # and @target_branch_label.
    hgcmd.log(
        scc.ui, scc.repo,
        rev=['merge() and (branch(%s) and children(branch("%s")))' %
            (target_branch_label, merged_branch_label)],
        date=None, user=[])
    logs = scc.ui.popbuffer()
    if status == 'merged':
        # There should be (at least) one merge changeset.
        expect(logs).Not.to_be_empty()
    else:
        # There shouldn't be any merge changesets.
        expect(logs).to_be_empty()


@Then("branch (\S+) is pushed to the central repository")
def check_branch_pushed(branch_label):
    hgapi.hg_commands.push.assert_any_call(
        ANY, ANY, new_branch=True, branch=[branch_label], dest=None)


@Then("branch (\S+) is not pushed to the central repository")
def check_branch_not_pushed(branch_label):
    for args, kwargs in hgapi.hg_commands.push.call_args_list:
        expect(kwargs.items()).Not.to_include(('branch', branch_label))


@Then("branch (\w+) is (closed|not closed)")
def check_branch_closing(branch_label, status):
    scc.ui.pushbuffer()
    hgcmd.branches(scc.ui, scc.repo, closed=(status == "closed"))
    output = utils.remove_ansi_codes(scc.ui.popbuffer())
    if status == "closed":
        output = '\n'.join([line for line in output.strip().split('\n') if
            "closed" in line])
    expect(output).to_include(branch_label)


@Then("closed branches are included in the listing")
def check_closed_branches_are_not_skipped():
    hgapi.hg_commands.branches.assert_called_with(ANY, ANY, closed=True)

@Then("the (story|chore) with id (\w+) is successfully delivered")
def check_deliver_success(type, story_id):
    # Check there was no error.
    expect(scc.exceptions).to_be_empty()
    run_steps(
        """
        Then branch %(id)s is closed
        And the current branch is updated to develop
        And branch %(id)s is merged into develop
        And branch develop is pushed to the staging repository
        And the %(type)s with id %(id)s is delivered
        And the relevant review request in Review Board is closed
        """ % {"type": type, "id": story_id})


@Then("(\S+) branch is pulled and updated")
def check_branch_pulled_and_updated(branch_label):
    hgcmd.pull.assert_called_with(ANY, ANY, update=True)


@When("I resolve the conflict")
def resolve_conflict():
    hgcmd.resolve(scc.ui, scc.repo, mark=True)
    hgcmd.commit(scc.ui, scc.repo, message="resolved")


@When("I update to branch (\S+)")
def update_to_branch(branch_label):
    switch_to_branch(branch_label)
