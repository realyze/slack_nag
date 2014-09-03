#!/usr/bin/env
# -*- coding: utf-8 -*-

""" Implementation of the hg plugin commands.
"""
import pt.errors
import pt.api
import config
import utils
import hgapi

import rb
# We're importing this for side effects too (it monkey-patches
# `rb/reviewboard.py`).
import rb.extensions

import mercurial.util as hg_util
import functools
import sys
import os


'''======================================'''
'''              Exceptions              '''
'''======================================'''

class BaseError(Exception):
    """ Base class for plugin exceptions.
    """
    def __init__(self, msg, *args, **kwargs):
        super(BaseError, self).__init__(self, *args, **kwargs)
        self._msg = msg

    def __str__(self):
        return self._msg


class ConfigError(BaseError):
    """ Configuration-related error.
    """
    pass


class InputError(BaseError):
    """ User input related error.
    """
    pass


'''======================================'''
'''              Decorators              '''
'''======================================'''
def exception_guard(fun):
    """ Decorator for command class methods (i.e., methods that implement hg
        commands).
        Wraps the guarded function in a try/catch block that catches generic
        Exception. To be used to make sure we're not leaking unhandled
        exceptions to the user.

        NOTE: We expect that the guarded fun has a Mercurial user interface
        object passed in as the first argument (after the self argument).
    """
    @functools.wraps(fun)
    def guarded_fun(self, ui, *args, **kwargs):
        try:
            return fun(self, ui, *args, **kwargs)
        except (hg_util.Abort, pt.errors.ServerError, InputError), e:
            utils.abort_plugin("%s\n" % str(e))
        except Exception, e:
            if config.DEBUG:
                import traceback
                traceback.print_exc()
            utils.abort_plugin_with_unknown_error("%s\n" % str(e))

    return guarded_fun


def ensure_consistent_repo_state(fun):
    """ Decorator for command class methods (i.e., methods that implement hg
        commands).
        If there are any uncommited changes, make sure the user has explicitly
        told us how to handle them (otherwise abort the plugin).
        If there are any unresolved conflicts, abort the plugin (user has to
        resolve them for us to allow him to continue).

        params:
            fun:    The fun to be decorated.
    """
    @functools.wraps(fun)
    def wrapper(self, ui, repo, *args, **opts):
        """ Wrapper for the decorated function.

            params:
                opts['force']:  Boolean. If True, we expect @opts to comprise
                    'force' parameter (meaning "continue regardless of any
                    uncomitted changes").

                opts['clean']:  Boolean. If True, we expect @opts to comprise
                    'clean' parameter (meaning "revert any changes before
                    continuing").
        """
        # Currying used just make the code shorter.
        wrapped = functools.partial(fun, self, ui, repo, *args, **opts)

        if self.hgapi.check_for_conflicts():
            utils.abort_plugin(
                "Unresolved conflicts found. Please resolve all "
                "conflicts before continuing.")

        repo_is_dirty = self.hgapi.are_there_uncommited_changes()

        if not repo_is_dirty:
            # We're good to go.
            return wrapped()

        should_force = opts.get('force', False)
        if should_force:
            # User has explicitly chosen to go on even though there are
            # uncommited changes.
            return wrapped()

        should_revert_changes = opts.get('clean', False)
        if should_revert_changes:
            no_backup = utils.get_from_config(
                ui, 'no_backup_files', default=False)
            # Revert changes. Abort if revert fails.
            revert_rv, _ = self.hgapi.call_hg_cmd(
                'revert', all=True, no_backup=no_backup)
            (not revert_rv) or utils.abort_plugin("Failed to revert changes.")
            return wrapped()

        # User did not explicitly handle uncommited changes. We play it safe
        # and abort.
        msg = "Outstanding uncommitted changes"
        msg_strings = []
        if 'force' in opts:
            msg_strings.append('--force to ignore outstanding changes')
        if 'clean' in opts:
            msg_strings.append('--clean to revert any changes')
        if msg_strings:
            msg += " (use " + " or ".join(msg_strings) + ")"
        msg += "."

        utils.abort_plugin(msg)

    return wrapper


def ensure_plugin_initialized(fun):
    """ Checks that the plugin has been initialized using the 'initflow'
        command. Quits with an error message otherwise.
    """
    @functools.wraps(fun)
    def wrapper(self, ui, repo, *args, **kwargs):
        # Do we have a 'develop' branch?
        if not self.hgapi.does_branch_exist(config.devel_branch_label):
            utils.abort_plugin(
                "You must run 'hg initflow' from the 'default' branch "
                "to initialize the plugin before you can use it.\n"
                "Sorry for the inconvenience.")
        else:
            return fun(self, ui, repo, *args, **kwargs)
    return wrapper


'''======================================'''
'''           Utility Functions          '''
'''======================================'''

# TODO(Tom): Possibly move to the `hgapi` module?
@utils.log_me
def _post_review_request(ui, repo, parent, rev='.', **kwargs):
    """ Post a review request to Review Board.

        params:
            parent: Parent changeset of the review request.

        return value:
            Review request id

        Note: We need the output from 'hg postreview' to get the review
              request id. But we also want to show it to the user, in case
              he's prompted to enter credentials. So we monkey patch ui.status
              to tee the output.
    """
    def new_status(msg, *args, **kwargs):
        """ Fake status function that tees ui.status output.
        """
        sys.stdout.write(msg)
        return old_ui_status(msg, *args, **kwargs)
    old_ui_status, ui.status = ui.status, new_status

    try:
        post_rv, _post_stdout = hgapi.api(ui, repo).call_hg_cmd(
            rb.postreview, parent=parent, rev=rev, **kwargs)
    except Exception, e:
        utils.abort_plugin("Could not post a review request: %s" % str(e))

    ui.status = old_ui_status

    (not post_rv) or utils.abort_plugin("Could not post a review request.")


'''======================================'''
'''           Plugin Commands            '''
'''======================================'''
"""
    We're using "callable classes" to implement the hg commands because they
    allow us to extract precondition checking (and other logic) out of the
    function that handles the "business logic" of the command while keeping
    the code together in one place.

    Note: Mercurial expects a type int return value, so we cannot carry out
    the required actions directly in __init__ (which returns the newly created
    object). Instead we're overriding __call__ so that the instance can act
    as a function.
"""

class workflow_command(object):
    """ Base class for the workflow plugin commands.
    """
    def __init__(self, *_args, **_kwargs):
        # Nothing interesting here... The funny stuff happens in __call__.
        self.hgapi = None

    @exception_guard
    @utils.log_me
    def __call__(self, ui, repo, *args, **kwargs):
        # Set up the reference to our hg api.
        self.hgapi = hgapi.api(ui, repo)
        # Check preconditions and initialize attrs.
        self.setup(ui, repo, *args, **kwargs)
        # Carry out the actual command.
        self.run(ui, repo, *args, **kwargs)

    def run(self, ui, repo, *args, **kwargs):
        """ The "business logic" of the command.
        """
        raise NotImplementedError(
            "'run' method must be overriden in the derived command classs!")

    def setup(self, *args, **kwargs):
        """ Check preconditions and set up attrs to be used by the command here.
        """
        raise NotImplementedError(
            "'setup' method must be overriden in the derived command classs!")

    def info(self, msg):
        """ Just a shorthand for telling the user what's up
            (printing to stdout).
        """
        self.hgapi.ui.status(
            utils.colorize_string("*Workflow*: " + msg + "\n"))


class ptlist(workflow_command):
    """ Displays stories from Pivotal Tracker.

Lists stories from current and backlog PT iterations.
    """

    def run(self, ui, _repo, **_opts):
        stories = pt.api.get_stories_for_project_id(self.project_id, self.token)
        stories = utils.filter_stories(
            stories, self.allowed_types, self.allowed_states)

        buf = '\n'.join([str(s) for s in stories]) + "\n"
        ui.write(buf)

    def setup(self, ui, _repo, **opts):
        # Required params.
        self.token = opts['token'] or utils.get_from_config(ui, 'token')
        self.project_id = (
            opts['project_id'] or utils.get_from_config(ui, 'project_id'))

        # Non-required params.
        self.allowed_types = utils.opt_to_list(opts['types'])
        self.allowed_states = utils.opt_to_list(opts['states'])


class ptselect(workflow_command):
    """ Starts a new story or selects an already started one.

Lists stories from current and backlog PT iterations and prompts \
you to choose one of them.The selected story is then started in \
Pivotal Tracker and a new Mercurial branch is created (or the \
current branch is updated if the branch already exists).

If the working dir contains any uncommited changes, aborts (unless
 --force or --clean option is specified)
    """

    @ensure_consistent_repo_state
    @ensure_plugin_initialized
    def run(self, ui, repo, **opts):
        story = self.get_story_to_be_selected(ui, **opts)

        if self.hgapi.does_branch_exist(branch_label=story.id):
            # This story has already been started before, just do an update.
            self.info("Switching to (already existing) branch %s." % story.id)
            try:
                self.hgapi.call_hg_cmd(
                    'update', node=story.id, clean=opts['clean'])
            except hg_util.Abort, e:
                utils.abort_plugin(
                    "Update aborted. Have you perhaps started a branch and "
                    "not yet commited any changes?\n"
                    "If you don't have any uncommited changes (except the new "
                    "branch), please use --clean to select the story.\n"
                    "(original 'hg update' message: %s" % str(e))
        else:
            # This raises an exception on failure.
            pt.api.set_story_state(
                self.project_id, story.id, self.token,
                state='started', story_type=story.story_type)

            # Create a new branch
            self.info("Creating new branch %s." % story.id)
            self.hgapi.call_hg_cmd('branch', label=story.id)

        self.info("Story started. You are in branch %s now." % story.id)

    def setup(self, ui, _repo, *_args, **opts):
        """ Checks the preconditions and sets up attributes on self.
        """
        self.token = opts['token'] or utils.get_from_config(ui, 'token')
        self.project_id = (
            opts['project_id'] or
            utils.get_from_config(ui, 'project_id'))

        # Non-required params.
        self.allowed_types = utils.opt_to_list(opts['types'])
        self.allowed_states = utils.opt_to_list(opts['states'])

        if self.hgapi.get_current_branch_label() == 'default':
            utils.abort_plugin(
                "Cannot select a story when in 'default' branch. Please "
                "update to '%s'." % config.devel_branch_label)

    def get_story_to_be_selected(self, ui, **opts):
        all_stories = pt.api.get_stories_for_project_id(
            self.project_id, self.token)
        stories = utils.filter_stories(
            all_stories, self.allowed_types, self.allowed_states)

        if not stories:
            utils.abort_plugin(
                "There are no stories to choose from (we're only listing "
                "the following types: '%s' and states: %s." %
                (self.allowed_types, self.allowed_states))

        # If '--story' opt is not used, prompt user to select a story.
        story_id = opts['story'] or (
            ptselect.prompt_user_for_a_story_id(ui, stories))

        story = next((s for s in stories if s.id == story_id), None)

        # Check for invalid story id.
        if not story:
            raise InputError(
                "Could not find a corresponding story for the id: %s."
                "\n(We're only looking for the following types: '%s' and "
                "states: %s." %
                    (story_id, self.allowed_types, self.allowed_states))

        return story

    @staticmethod
    def prompt_user_for_a_story_id(ui, stories):
        """ Asks the user to input an index to select the story with the given
            index from the list of stories.

            Checks the input for sanity and raises an InputError if check fails.
        """
        colorize = utils.colorize_string
        # Print stories (start with index 1).
        buf = '\n'.join(
            ("%i : %s" % (i + 1, colorize(s.name))
            for i, s in enumerate(stories)))
        ui.write(buf)
        ui.write("\n")

        # Prompt user to choose story index.
        index = ui.prompt("Select story (or 'q' to quit): ", 0)
        if index == "q":
            utils.abort_plugin("Operation canceled.")

        # We expect a number.
        try:
            index = int(index)
        except ValueError:
            raise InputError("Expected a number.")

        if not 0 < index <= len(stories):
            raise InputError("Invalid story index: %s." % index)

        # We're expecting input to start from 1, so we have to
        # subtract one here to get the list index.
        story_id = stories[index - 1].id

        return story_id



class ptfinish(workflow_command):
    """ Finishes the currently selected story.

This command finishes the curently selected story (it requires the "postreview"
hg extension). Finishing the story comprises:\n
 1) The changesets in the current branch are pushed to the remote repo.
 2) The story in Pivotal Tracker is marked as "Finished" (button says "Deliver").
 3) A new review request is posted to our Review Board server (containing every\
 changeset in the feature branch).
    """

    @ensure_consistent_repo_state
    @ensure_plugin_initialized
    def run(self, ui, repo, *args, **_opts):
        if self.hgapi.get_current_branch_label() is not self.finished_branch:
            self.hgapi.update_to_branch(self.finished_branch, check=True)

        assert self.hgapi.get_current_branch_label() == self.finished_branch

        # Close the feature branch and switch to the develop branch.
        self.info("Closing the feature branch...")
        self.hgapi.close_branch()
        self.hgapi.update_to_branch(config.devel_branch_label)

        # Push the feature branch to the remote repository.
        self.info("Pushing the feature branch...")
        self.hgapi.push_branch_to_repo(self.finished_branch)

        # Pull & update the development branch.
        self.info("Updating the development branch...")
        self.hgapi.call_hg_cmd('pull', update=True)
        if self.hgapi.check_for_conflicts():
            utils.abort_plugin(
                "Conflicts during updating the '%(dev)s' branch.\n"
                "Please resolve the conflicts and resume by running: "
                "hg ptfinish -s %(feature)s' from the %(dev)s branch." %
                {'dev': config.devel_branch_label,
                'feature': self.finished_branch})

        # Merging aborts if there are conflicts.
        self.info("Merging %s into the development branch..." %
            self.finished_branch)
        merge_rv = self.hgapi.merge_branch(self.finished_branch)
        if not merge_rv:
            utils.abort_plugin(
                "Please commit the changes introduced by merging. You can "
                "resume later by running: 'hg ptfinish -s %s' from the %s "
                "branch." % (self.finished_branch, config.devel_branch_label))

        # Push the development branch to the remote repository.
        self.info("Pushing the development branch...")
        self.hgapi.push_branch_to_repo(config.devel_branch_label)

        story = pt.api.get_story(
            self.project_id, self.token, self.finished_story_id)

        self.info("Finishing the story in Pivotal Tracker...")
        # Update story state in PT to 'finished'.
        pt.api.set_story_state(
            self.project_id, self.finished_story_id, self.token,
            state='finished', story_type=story.story_type)

        self.info("Posting a review request...")
        self.post_review(repo, ui, summary=story.name)

        # TODO(Tom): Submit a job request to Jenkins.

    def setup(self, ui, _repo, *_args, **opts):
        """ Checks the preconditions and sets up attributes on self.
        """
        self.token = opts['token'] or utils.get_from_config(ui, 'token')
        self.project_id = (
            opts['project_id'] or
            utils.get_from_config(ui, 'project_id'))

        self.finished_story_id = self.determine_story_id(opts)
        self.finished_branch = self.finished_story_id

        # Check RB mandatory params.
        for key in ('server', 'repoid'):
            utils.get_from_config(ui, key, section='reviewboard')

    def post_review(self, repo, ui, summary):
        branch_parent_changeset_hash = self.hgapi.get_branch_parent_hash(
            branch_label=self.finished_branch)
        # Get the tip of the branch.
        _rv, tip = self.hgapi.call_hg_cmd(
            'log', rev=['max(branch(%s))' % self.finished_branch],
            user=[], template='{node|short}', date=None)
        try:
            _post_review_request(
                ui, repo, parent=branch_parent_changeset_hash,
                rev=tip, summary=summary)
        except Exception, e:
            ui.warn("\n***\n")
            ui.warn(utils.colorize_string("*WARNING* :") + str(e) + "\n")
            ui.warn("Please post the review request manually.\n")
            ui.warn("\n***\n")

    def determine_story_id(self, opts):
        """ Returns story id of the story we are delivering (it's the same as
            the branch label).
        """
        # Get to-be-merged branch label.
        branch_label = self.hgapi.get_current_branch_label()

        if opts['story'] and branch_label != config.devel_branch_label:
            # TODO(Tom): This constraint is not really necessary, but it makes
            # reasoning about the plugin easier, so let's stick to that in the
            # beta.
            utils.abort_plugin(
                "Error: --story option can currently only be used from the "
                "%s branch (and you're in branch %s)." %
                (config.devel_branch_label, branch_label))

        if branch_label == config.devel_branch_label and not opts['story']:
            utils.abort_plugin(
                "Cannot deliver a story from the %s branch "
                "unless '--story' is specified" % config.devel_branch_label)

        if branch_label == config.devel_branch_label:
            # We assume we're re-delivering after conflicts have been resolved.
            branch_label = opts['story']

        assert branch_label, "Story id should always be be set here!"

        return branch_label


class release(workflow_command):
    """ Starts or finishes a release.
'hg release --start <version_string>' will create a 'release-<version_string>'
branch, write the version_string into the version.txt file and commit the file
(if the file is missing, the plugin quits with an error message).

'hg release --finish' closes the release branch and merges the release branch
into development and production branches.
In case there are unresolved conflicts, resolve them, commit and re-run 'hg
release --finish'.
This command has to be called on the release branch we are about to finish.
    """

    class _release_init(workflow_command):
        @ensure_consistent_repo_state
        @ensure_plugin_initialized
        def run(self, ui, repo, *args, **_opts):
            (releasable, blocked) = self.get_stories_for_release().values()
            self.print_stories_for_release(ui, releasable, blocked)
            input = ui.prompt(
                "Continue with the release process? (default: 'n')?",
                default='n')
            if input != 'y':
                utils.abort_plugin('Quitting...')

            release_branch_label = ('%s%s' %
                (config.release_branch_prefix, self.release_version))

            # Create the release branch.
            self.info("Creating release branch '%s'..." %
                release_branch_label)
            (rv, _) = self.hgapi.call_hg_cmd('branch', release_branch_label)
            (not rv) or utils.abort_plugin("Failed to create release branch.")

            # Write the version string into the version file and commit
            # the branch.
            self.info("Bumping version in version.txt...")
            with open(self.version_file, 'w') as f:
                f.write(self.release_version)
            self.hgapi.call_hg_cmd('commit', message="Bumped version.")

            # Push the release branch.
            self.hgapi.push_branch_to_repo(release_branch_label)

            for story in releasable:
                pt.api.append_label_to_a_story(
                    self.project_id, story.id, self.token, self.release_version)

        def setup(self, ui, repo, *args, **opts):
            # Required params.
            self.token = opts['token'] or utils.get_from_config(ui, 'token')
            self.project_id = (
                opts['project_id'] or utils.get_from_config(ui, 'project_id'))

            if (self.hgapi.get_current_branch_label() !=
                    config.devel_branch_label):
                utils.abort_plugin(
                    "You must start a release from the '%s' branch." %
                        config.devel_branch_label)

            self.version_file = os.path.join(
                repo.path, '../%s' % config.version_file)

            if not args:
                # TODO(Tom): This should not be necessary, the plugin should be
                # able to calculate the release string itself (well, in most
                # cases at least).
                utils.abort_plugin("You must specify a release version.")
            else:
                self.release_version = args[0]
            if not os.path.isfile(self.version_file):
                utils.abort_plugin(
                    "You must have a '%s' file in your repository "
                    "root in order to create a release." % config.version_file)

        def get_stories_for_release(self):
            """ Returns an object with two attributes:
                'releasable': List of stories that can be released
                'blocked': List of tuples (s, b) where `s` is a done story
                blocked by a list of unreleasable stories (`b`).

                The stories returned are our story models.
            """
            stories = pt.api.get_stories_for_project_id(
                self.project_id, self.token)
            finished = [s for s in stories if s.state == 'finished']
            labeled = set([s for s in finished if
                self.story_has_release_labels_set(s)])
            # Only check blocking dependencies on stories from current and backlog.
            # TODO(Tom): Is that enough? What about iceboxed stories? But then
            # again, no story should depend on a story from icebox...
            stories_and_blockers = [(s, self.get_story_blockers(s, stories))
                for s in labeled]
            return {
                'releasable': [s for (s, blockers) in
                    stories_and_blockers if not blockers],
                'blocked': [(s, blockers) for (s, blockers) in
                    stories_and_blockers if blockers]
            }

        def story_has_release_labels_set(self, story):
            """ Returns True iff the story in PT has all the required labels.
            """
            required_labels = [config.pt_reviewed_label, config.pt_qa_ok_label]
            return set(required_labels).issubset(set(story.labels))

        def get_story_blockers(self, story, active_stories):
            """ Returns a list of stories blocking `story`.

            Blocking happens when an earlier story is not releasable but has
            beeen merged into 'develop' branch before the current story has
            been started.
            This happens e.g. when a code review is done out of sequence, so a
            newer story is releasable before an older one.
            """
            def get_blocking_ancestors(ancestors):
                return [s for s in ancestors if
                    not (
                        s.state in ('delivered', 'accepted') or
                        self.story_has_release_labels_set(s))]

            # Get branches for all the story's ancestor changesets (there will
            # be duplicates).
            _, output = self.hgapi.call_hg_cmd(
                'log',
                rev=['ancestors(%s)' % story.id],
                date=None, user=[], template='{branch}\n')
            # Get unique ancestor branch labels.
            story_ids = set(output.split('\n'))
            # We're only interested in stories from current and backlog.
            active_ancestor_stories = set([
                s for s in active_stories if s.id in story_ids])

            return get_blocking_ancestors(active_ancestor_stories)

        def print_stories_for_release(self, ui, releasable, blocked):
            """ Print a list of stories - both stories that can be part of the
                release and stories that cannot be delivered because of another
                story.
            """
            # Print stories that can be part of the release.
            buf = "*Releasable stories*:\n"
            releasable_sorted = sorted(releasable, key=lambda story: story.id)
            buf += '\n'.join(
                ("%s (%s)" % (s.id, s.name) for s in releasable_sorted))

            # Print stories that are themselves deliverable but blocked by an
            # undeliverable story.
            buf += "\n\n*Blocked stories*:\n"
            # We're sorting the stories here, which is not strictly necessary,
            # but it makes the ordering unambigous (which is good for testing).
            blocked_sorted = [(s, sorted(b, key=lambda story: story.id))
                for (s, b) in blocked]
            buf += '\n'.join(
                ("%s (%s) (blocked by stories: %s)" %
                    (s[0].id, s[0].name, [b.id for b in s[1]])
                for s in blocked_sorted))

            ui.write(utils.colorize_string(buf))
            ui.write("\n")


    class _release_finish(workflow_command):
        @ensure_consistent_repo_state
        @ensure_plugin_initialized
        def run(self, ui, repo, *args, **_opts):
            # Ensure we're in a release branch.
            assert self.hgapi.get_current_branch_label().startswith(
                config.release_branch_prefix)

            self.info("Closing the release branch...")
            # Close the release branch.
            self.hgapi.close_branch()

            self.info("Updating to '%s'..." % config.devel_branch_label)
            # Merge the release branch to the development branch.
            self.hgapi.update_to_branch(config.devel_branch_label)
            # Note: We're not allowing prompting on merge, so we don't have to
            # check the return value of the following merge calls.
            self.info("Merging the release branch into '%s'..." %
                config.devel_branch_label)
            self.hgapi.merge_branch(self.release_branch, should_prompt=False)

            self.info("Updating to 'default'...")
            # Merge the release branch to the production branch.
            self.hgapi.update_to_branch('default')
            self.info("Merging the release branch into 'default'...")
            self.hgapi.merge_branch(self.release_branch, should_prompt=False)

            # Tag the tip of the production branch (new release).
            version = self.release_branch.lstrip(config.release_branch_prefix)
            self.info("Tagging 'default's tip as '%s'" % version)
            rv, _ = self.hgapi.call_hg_cmd('tag', version)
            (not rv) or utils.abort_plugin(
                "Failed to tag production release with tag %s" % version)

            # Push develop and production to the remote repository.
            self.info("Pushing into remote repository...")
            self.hgapi.push_branch_to_repo(config.devel_branch_label)
            self.hgapi.push_branch_to_repo('default')

            self.info("Delivering released stories in Pivotal Tracker...")
            # Deliver all the released stories in PT.
            for s in self.get_released_stories():
                pt.api.set_story_state(
                    self.project_id, s.id, self.token, 'delivered',
                    s.story_type)

            # Update back to 'develop' (that's arguably what's wanted, because
            # ending up in 'default' might just confuse the user).
            self.info("Updating back to '%s'..." % config.devel_branch_label)
            self.hgapi.update_to_branch(config.devel_branch_label)

        def setup(self, ui, _repo, *_args, **opts):
            self.token = opts['token'] or utils.get_from_config(ui, 'token')
            self.project_id = (
                opts['project_id'] or utils.get_from_config(ui, 'project_id'))

            # Make sure we're in a release branch.
            current_branch = self.hgapi.get_current_branch_label()
            if not current_branch.startswith(config.release_branch_prefix):
                utils.abort_plugin(
                    "Finishing a release is possible from the release "
                    "branch only.")
            self.release_branch = current_branch

        def get_released_stories(self):
            stories = pt.api.get_stories_for_project_id(
                self.project_id, self.token)

            version_string = utils.get_version_from_release_branch_label(
                self.release_branch)

            # Get the version and filter out stories that do not have the
            # version label.
            return [s for s in stories if version_string in s.labels]


    def __call__(self, ui, repo, *args, **opts):
        handler = None

        if opts['start']:
            handler = self._release_init()
        elif opts['finish']:
            handler = self._release_finish()
        else:
            utils.abort_plugin("Unknown command.")

        handler(ui, repo, *args, **opts)


class initflow(workflow_command):
    """ Initialize workflow.

Must be called before you start using this plugin.
    """
    @ensure_consistent_repo_state
    def run(self, ui, repo, *args, **_opts):
        if not self.hgapi.does_branch_exist(config.devel_branch_label):
            # Create the development branch and commit it (so that it is really
            # created).
            self.hgapi.call_hg_cmd(
                'branch', config.devel_branch_label)
            self.hgapi.call_hg_cmd(
                'commit', message="Created the development branch.")

    def setup(self, _ui, _repo, *args, **kwargs):
        label = self.hgapi.get_current_branch_label()
        if label != 'default':
            utils.abort_plugin("Must be called from the 'default' branch.")
