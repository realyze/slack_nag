# -*- coding: utf-8 -*-

import mercurial.commands as hg_commands

import utils
import config


class api(object):
    """ Our extensions to Mercurial Python API.

        This class provides shortcuts to some common hg actions and wraps the
        original API so that we don't have to deal with low-level stuff.
    """

    def __init__(self, ui, repo):
        self._ui = ui
        self._repo = repo

    @property
    def ui(self):
        return self._ui

    @utils.log_me
    def call_hg_cmd(self, cmd_fun, *args, **kwargs):
        """ Runs a Mercurial command function (@cmd_fun). Standard output is
            captured when the command is executed, so no output is printed.

            kwargs may contain a 'keep_ansi' boolean parameter that specifies
            whether ANSI color codes should be stripped from the output or not.
            It defaults to False (i.e., color codes should be stripped)

            Returns:
                (rv, output) tuple where rv is the return value of the Mercurial
                command and output is the captured standard output.
        """
        keep_ansi = kwargs.get('keep_ansi', None) and kwargs.pop('keep_ansi')
        if type(cmd_fun) is str:
            try:
                cmd_fun = getattr(hg_commands, cmd_fun)
            except AttributeError:
                utils.abort_plugin("Unknown Mercurial command: '%s'." % cmd_fun)

        self._ui.pushbuffer()
        return_value = cmd_fun(self._ui, self._repo, *args, **kwargs)
        output = self._ui.popbuffer()

        if not keep_ansi:
            output = utils.remove_ansi_codes(output)

        return (return_value, output)


    def get_branch_label_for_changeset(self, changeset):
        """ Returns the branch label that @changeset belongs to.
        """
        _rv, output = self.call_hg_cmd(
            hg_commands.log,
            rev=['min(branch(%s))' % changeset],
            date=None,
            user=[],
            template='{branch}')
        return output


    def get_branch_parent_hash(self, branch_label='.'):
        # Get the log info for the parent changeset of @branch_label.
        _log_rv, branch_parent_hash = self.call_hg_cmd(
            hg_commands.log, rev=['p1(min(branch(%s)))' % branch_label],
            date=None,
            user=[],
            template='{node}')
        return branch_parent_hash.strip()


    def close_branch(self):
        """ Closes the current branch. If called on an already closed branch,
            just returns.
        """
        label = self.get_current_branch_label()
        # Assert we're not closing any permanent branch.
        assert label not in config.permanent_branches
        if not self.is_branch_closed(label):
            self.call_hg_cmd(
                hg_commands.commit, close_branch=True,
                message=config.close_branch_msg)


    def update_to_branch(self, branch_label, **kwargs):
        # Call update.
        rv, _out = self.call_hg_cmd(
            hg_commands.update, branch_label, **kwargs)
        (not rv ) or utils.abort_plugin(
            "Conflicts during updating to branch %s" % branch_label)


    def get_current_branch_label(self):
        """ Returns the label of the current branch.
        """
        _rv, branch_output = self.call_hg_cmd(hg_commands.branch)
        return branch_output.strip()


    def check_for_conflicts(self):
        """ Return True iff there are any unresolved conflict in the working
            directory.
        """
        _rv, output = self.call_hg_cmd(hg_commands.resolve, list=True)
        lines = output.strip().split('\n')
        return any((l.strip()[0] == 'U' for l in lines if l))


    def push_branch_to_repo(self, branch_label, dest=None, new_branch=True):
        """ Pushes branch with label @branch_label to remote repo with
            URL @repo_url. If repo_url is not set, use the .hgrc default.
        """
        rv, output = self.call_hg_cmd(
            hg_commands.push, branch=[branch_label], dest=dest,
            new_branch=new_branch)
        return (rv, output)


    @utils.log_me
    def merge_branch(self, branch_label, should_prompt=True):
        """ Tries to merge @branch_label into the current branch.
            Aborts the plugin if there are any unresolved conflicts.

            Return value:
                True if there was nothing to merge or if the user chose to
                    continue when prompted.
                False if the code was merged but user chose not to continue.
        """
        # Use "hg merge --preview" to see if there's anything to merge (calling
        # merge would abort in that case).
        rv, merge_preview_output = self.call_hg_cmd(
            hg_commands.merge, branch_label, preview=True)

        cleaned_output = merge_preview_output.strip()
        if not cleaned_output:
            # Nothing to merge (branches have already been merged).
            return True

        # There is something to merge into the current branch => do the merge.
        rv, merge_output = self.call_hg_cmd(hg_commands.merge, branch_label)
        unresolved_conflicts = bool(rv)

        if unresolved_conflicts:
            utils.abort_plugin(
                "Conflicts during merging:\n%s" % merge_output)
        elif should_prompt:
            # This means that either no conflicts occured at all or that we
            # resolved them using a merge tool during merging.
            input = self._ui.prompt(
                "Merging your story branch might have introduced bugs. "
                "We recommend that you test your code before you finalize the "
                "process.\n"
                "Continue delivering [y/n] (default: 'n')?", default='n')
            if input == 'n':
                return False

        # This won't do anything if there was no change to be commited
        # (which may happen if our merge attempt did not really merge
        # anything).
        self.call_hg_cmd(
            hg_commands.commit, message=config.merge_msg % branch_label)
        return True


    def are_there_uncommited_changes(self):
        """ Returns true iff there are outstanding uncommited changes
            in the repo.
        """
        _rv, output = self.call_hg_cmd(hg_commands.status)

        # Look for any line than begins with something else than '?'.
        any_dirty_files = any(op[0] != '?' for op in output.split("\n") if op)
        return any_dirty_files


    def is_branch_closed(self, branch_label):
        """ Return True iff the branch with label @branch_label is closed
        """
        _rv, output = self.call_hg_cmd(hg_commands.branches, closed=False)

        labels = [line.split()[0] for line in output.strip().split('\n')]
        return branch_label not in labels


    def does_branch_exist(self, branch_label):
        """ Returns True iff there is a branch with label @branch_label.
        """
        _rv, output = self.call_hg_cmd(hg_commands.branches, closed=True)
        labels = [line.split()[0] for line in output.strip().split('\n') if line]
        return branch_label in labels
