#!/usr/bin/env
# -*- coding: utf-8 -*-

from pyvows import Vows, expect
from lxml import etree

from models.story import Story
import test.storyxmlgen as storyxmlgen

@Vows.batch
class StoryModel(Vows.Context):

    class WhenParsingAValidStoryElementXml(Vows.Context):

        def topic(self):
            project_id="test project id"
            story_xml = storyxmlgen.generate_story_xml(
                project_id=project_id,
                story_id=1,
                name="As a someone, I want bar, so that foo.")
            return Story.from_xml_elem(etree.fromstring(story_xml))

        def we_get_a_story(self, topic):
            expect(topic).Not.to_be_null()

        def and_the_story_has_correct_attributes(self, topic):
            expect(topic.project_id).to_equal("test project id")
            expect(topic.id).to_equal("1")
            expect(topic.name).to_equal(
                "As a someone, I want bar, so that foo.")

    class WhenParsingAUnicodeString(Vows.Context):
        def topic(self):
            project_id="test project id"
            story_xml = storyxmlgen.generate_story_xml(
                project_id=project_id,
                story_id=1,
                name="Unicode string ěščřž")
            return Story.from_xml_elem(etree.fromstring(story_xml))

        def it_has_correct_attributes(self, topic):
            expect(topic.project_id).to_equal("test project id")
            expect(topic.id).to_equal("1")
            expect(topic.name).to_equal(u"Unicode string ěščřž")

