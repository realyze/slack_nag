import logging
import os

# Enable/disable detailed error output.
DEBUG = True

# Logging
enable_logging = True
log_filepath = os.path.join(os.path.expanduser("~"), '.workflow.log')
log_level = logging.DEBUG


# Pivotal Tracker
pivotal_tracker_root_url = "https://www.pivotaltracker.com"
pt_api_url_root = "%s/services/v3" % pivotal_tracker_root_url
pt_reviewed_label = 'reviewed'
pt_qa_ok_label = 'qa+'

chore_review_state_label = 'waiting-for-review'
close_branch_msg = "Closing branch."
merge_msg = "Merged %s"
version_file = 'version.txt'
release_branch_prefix = 'release-'
devel_branch_label = 'develop'
permanent_branches = [devel_branch_label, 'default']

# hgrc options
hgrc_section_name = 'workflow'
metadata_filename = 'workflow_metadata.db'
