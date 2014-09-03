#!/usr/bin/env
# -*- coding: utf-8 -*-

def _simple_xml_to_dict(element):
    """ Turns an XML tree into a Python dict.

        Note that this is a very simple implementation, so it does not
        handle sibling elements (it always takes the last one) or attributes.
        But we don't need that now (and perhaps we won't need it at all), so
        this is enough for the time being.
    """
    def _xml2dict(elem):
        return (elem.tag, dict(map(_xml2dict, elem)) or elem.text)
    return _xml2dict(element)[1]


class Story(object):
    """ A model class for Pivotal Tracker story.
    """

    @classmethod
    def from_xml_elem(cls, story_elem):
        """ Create a new story from provided "story" DOM element.

            Usage:
            >>> import test.storyxmlgen as xmlgen
            >>> from lxml import etree
            >>> from models.story import Story
            >>> # Create a fake story XML.
            >>> test_xml = xmlgen.generate_story_xml(
            ...     id=1,
            ...     project_id="testid",
            ...     name="test name",
            ...     labels="test label1, test label2")
            >>> test_xml = '<?xml version="1.0" encoding="UTF-8"?>' + test_xml
            >>> story_elem = etree.fromstring(test_xml)
            >>> # Now create the story model.
            >>> story = Story.from_xml_elem(story_elem)
            >>> story.project_id
            'testid'
        """
        story_dict = _simple_xml_to_dict(story_elem)
        return Story(**story_dict)


    def __init__(
            self, id, project_id, name, story_type='feature',
            current_state='unscheduled', labels='', **_kwargs):
        self.project_id = project_id
        self.id = id
        self.name = name
        self.story_type = story_type
        self.state = current_state
        # `labels` have a default value, but unfortunately it's not
        # used, because parser returns None for an empty string. So we use 'or'
        # to make sure `labels` is a string.
        # TODO(Tom): Investigate how this could be improved.
        self.labels = [l for l in (labels or '').split(',') if l]

    def __str__(self):
        return "%s : %s" % (self.id, self.name)

