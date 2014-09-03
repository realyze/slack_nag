
project_response_fake = """\
<?xml version="1.0" encoding="UTF-8"?>
<project>
  <id>%s</id>
  <name>%s</name>
  <iteration_length type="integer">1</iteration_length>
  <week_start_day>Monday</week_start_day>
  <point_scale>0,1,2,3</point_scale>
  <account>Salsita Software</account>
  <first_iteration_start_time type="datetime">2011/09/19 07:00:00 UTC</first_iteration_start_time>
  <current_iteration_number type="integer">20</current_iteration_number>
  <enable_tasks type="boolean">true</enable_tasks>
  <velocity_scheme>Average of 3 iterations</velocity_scheme>
  <current_velocity>3</current_velocity>
  <initial_velocity>10</initial_velocity>
  <number_of_done_iterations_to_show>12</number_of_done_iterations_to_show>
  <labels>adobo,architecture,chrome,sysadmin,timer</labels>
  <last_activity_at type="datetime">2012/01/31 17:15:15 UTC</last_activity_at>
  <allow_attachments>true</allow_attachments>
  <public>false</public>
  <use_https>false</use_https>
  <bugs_and_chores_are_estimatable>false</bugs_and_chores_are_estimatable>
  <commit_mode>false</commit_mode>
  <memberships type="array">
    <membership>
      <id>1231631</id>
      <person>
        <email>matthew@salsitasoft.com</email>
        <name>Matthew Gertner</name>
        <initials>MG</initials>
      </person>
      <role>Owner</role>
    </membership>
  </memberships>
  <integrations type="array">
  </integrations>
</project>
"""

stories_response_wrapper_template = """\
<?xml version="1.0" encoding="UTF-8"?>
<stories type="array" count="%(count)i" total="%(total)i" limit="1000">
%(stories)s
</stories>
"""

story_template = """\
<story>
    <id type="integer">%(id)s</id>
    <project_id type="integer">%(project_id)s</project_id>
    <story_type>%(story_type)s</story_type>
    <url>http://www.pivotaltracker.com/story/show/%(id)s</url>
    <estimate type="integer">1</estimate>
    <current_state>%(state)s</current_state>
    <description></description>
    <name>%(name)s</name>
    <labels>%(labels)s</labels>
    <requested_by>Matthew Gertner</requested_by>
    <owned_by>Matthew Gertner</owned_by>
    <created_at type="datetime">2011/09/21 08:23:24 UTC</created_at>
    <updated_at type="datetime">2011/09/23 08:50:19 UTC</updated_at>
    <accepted_at type="datetime">2011/09/23 08:50:19 UTC</accepted_at>
  </story>
"""

def generate_story_xml(id, project_id, name,
		story_type="feature", current_state="unscheduled",
		**kwargs):
    """ Generate XML for a new fake story.
    """
    # Create new (parametrized) story XML.
    return story_template % {
        "id": id,
        "project_id": project_id,
        "name": name,
        "story_type": story_type,
        "labels": kwargs.get('labels', ''),
        "state": current_state}


def generate_stories_response(stories_xml, total=None):
    """ Generate XML string for stories response.
    """
    return stories_response_wrapper_template % {
        "stories": '\n'.join(stories_xml),
        "count": len(stories_xml),
        "total": total or len(stories_xml)}

