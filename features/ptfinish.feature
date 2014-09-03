Using step definitions from: 'steps', 'finish_steps'

Feature: Command ptfinish
    In order to make it easier to finish working on a story
    As a user
    I want to have a 'hg ptfinish' command

    Background:
      Given I have a PT project with ID "testid"
      And the repository has been initialized using the plugin
      And the project has the following stories:
        | id        | name                                      | iteration | story_type |
        | 42        | As a user1, I want bar1, so that baz1.    | current   | feature    |
        | 43        | As a user2, I want bar2, so that baz2.    | current   | chore      |
      And I have the following in my .hgrc file:
        """
        [reviewboard]
        server = https://test.server.foo/
        repoid = https://test.rb.foo

        [workflow]
        project_id = testid
        token = testtoken
        """
      And review request id will be 123

    Scenario: Finishing a feature/bug
        Given the story with id 42 is selected
        And branch 42 has been commited
        And I will type "y" when I am prompted
        When I issue the command: hg ptfinish
        Then story 42 is successfully finished

    Scenario: Review request contains all the changesets in the feature branch
        Given the story with id 42 is selected
        And branch 42 has been commited
        And I will type "y" when I am prompted
        When I issue the command: hg ptfinish
        Then the parent changeset of the review request is the parent changeset of branch 42
        And the review request tip is the tip of branch 42

    Scenario: Finishing a chore
        Given the chore with id 43 is selected
        And branch 43 has been commited
        And I will type "y" when I am prompted
        When I issue the command: hg ptfinish
        Then chore 43 is successfully finished

    @raise_if_prompted
    Scenario: Finishing a story after resolving merge conflicts
        Given the story with id 42 is selected
        And branch 42 has been commited
        And there will be some conflicts when merging with branch develop
        When I issue the command: hg ptfinish
        And I resolve the conflict
        And I update to branch develop
        And I issue the command: hg ptfinish --story 42
        Then story 42 is successfully finished

    Scenario: Uncommited changes
        Given the story with id 42 is selected
        And there are some uncommited changes in the working copy
        When I issue the command: hg ptfinish
        Then Mercurial quits with a message
        And branch 42 is not pushed to the central repository
        And no review request is posted to the Review Board server
        And the story with id 42 is not finished in PT


    Scenario: Reviewboard returns failure
        Given the story with id 42 is selected
        And branch 42 has been commited
        And Review Board will return an error when creating a request
        And I will type "y" when I am prompted
        When I issue the command: hg ptfinish
        Then branch 42 is pushed to the central repository
        And the story with id 42 is finished in PT


    Scenario: Pivotal Tracker returns failure
        Given the story with id 42 is selected
        And branch 42 has been commited
        And the PT server returns a failure message for story id 42 finish request
        And I will type "y" when I am prompted
        When I issue the command: hg ptfinish
        Then branch 42 is pushed to the central repository
        And no review request is posted to the Review Board server
        But Mercurial quits with an error message


    Scenario: Pushing to remote repo fails
        Given the story with id 42 is selected
        And branch 42 has been commited
        And pushing to the remote repository will fail
        And I will type "y" when I am prompted
        When I issue the command: hg ptfinish
        Then no review request is posted to the Review Board server
        And the story with id 42 is not finished in PT
        And Mercurial quits with an error message


    Scenario: Conflicts during merging
        Given the story with id 42 is selected
        And branch 42 has been commited
        And there will be some conflicts when merging with branch develop
        When I issue the command: hg ptfinish
        Then branch 42 is closed
        And the current branch is updated to develop
        But the story with id 42 is not finished in PT
        And no review request is posted to the Review Board server
        And Mercurial quits with a message

