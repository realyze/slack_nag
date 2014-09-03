# -*- coding: utf-8 -*-
from freshen import Given, When, Then, Before, After, scc, run_steps
import mercurial.commands as hgcmd
from pyvows import expect
from utils import remove_ansi_codes
import features.steps as steps
import features.common as common
import utils
from lxml import etree

import os

import config


@Given("there is (no|a) ([^ \t]+) file in the repo root")
def create_file_in_repo_root(choice, filename):
    path = os.path.join(scc.repo.path, '../%s' % filename)
    if choice == 'a':
        # Create the file.
        open(path, 'w').close()
    else:
        # Delete the file.
        os.path.isfile(path) and os.remove(path)

@Given("stories (\S+) are ready to be released")
def make_stories_releasable(stories_string):
    # Remember the current branch.
    scc.ui.pushbuffer()
    hgcmd.branch(scc.ui, scc.repo)
    output = utils.remove_ansi_codes(scc.ui.popbuffer())
    old_branch = output.strip()

    steps.switch_to_branch(config.devel_branch_label)

    # Add the PT labels necessary for a story to be released.
    for story_id in [s.strip() for s in stories_string.split(',')]:
        update_story_with_release_labels(story_id)
        steps.create_branch_and_commit(story_id, switch_to_old_branch=True)

    steps.switch_to_branch(old_branch)


def update_story_with_release_labels(story_id):
    story = next((s for s in scc.stories if s.id == story_id), None)
    story.labels = '%s,%s' % (config.pt_reviewed_label, config.pt_qa_ok_label)
    common.update_story_on_server(story.__dict__)


@Then("a new release ([^ \t]+) is initiated")
def check_release_started(release_version):
    run_steps('a new branch called "%s%s" is created' %
        (config.release_branch_prefix, release_version))
    version_file = os.path.join(scc.repo.path, '../%s' % config.version_file)
    with open(version_file, 'r') as f:
        # Check that we've bumped the version file.
        expect(f.read()).to_equal(release_version)


@Then("tip of branch (\w+) is tagged as ([^ \t]+)")
def check_branch_tip_tag(branch_label, tag):
    scc.ui.pushbuffer()
    hgcmd.log(
        scc.ui, scc.repo,
        rev=['max(branch(%s))^' % branch_label],
        user=[], date=None,
        template='{tags}')
    output = remove_ansi_codes(scc.ui.popbuffer())
    tags = output.split()
    expect(tags).to_include(tag)

@Then("release (\S+) is successfully finished")
def check_release_success(version):
    run_steps(
        """
        Then branch %(prefix)s%(version)s is merged into develop
        And branch %(prefix)s%(version)s is merged into default
        And tip of branch default is tagged as %(version)s
        """ % {'prefix': config.release_branch_prefix, 'version': version})


@Then("a label (\S+) is added to stories (\S+)")
def check_PT_label_added(label, stories_string):
    story_ids = stories_string.split(',')
    for sid in story_ids:
        labels = ''
        for r in common.get_story_state_change_requests(sid):
            root = etree.fromstring(r['data'])
            # Get labels.
            labels_elems = root.xpath('/story/labels')
            labels = (labels_elems[0].text or '') if labels_elems else ''
        expect(labels.split(',')).to_include(label)
