Using step definitions from: 'steps', 'release_steps'

Feature: Command release --finish
    In order to make it easier to finalize an upcoming release
    As a user
    I want the plugin to support finishing a release

    Background:
        Given I have a PT project with ID "testid"
        And the repository has been initialized using the plugin
        And I have the following in my .hgrc file:
          """
          [workflow]
          project_id = testid
          token = testtoken
          """
        And the project has the following stories:
          | id | name                                   | iteration | story_type | current_state | labels |
          | 42 | As a user1, I want bar1, so that baz1. | current   | feature    | finished      | 0.0.1  |


    ########################
    # Successful scenarios #
    ########################

    Scenario: Finishing the release from the release branch
        Given branch release-0.0.1 has been commited
        And the current branch has label release-0.0.1
        When I issue the command: hg release --finish
        Then release 0.0.1 is successfully finished

    Scenario: Released stories are delivered.
        Given branch release-0.0.1 has been commited
        And the current branch has label release-0.0.1
        When I issue the command: hg release --finish
	Then the story with id 42 is delivered in PT

    Scenario: Redelivering after merge conflicts with the development branch
        Given branch release-0.0.1 has been commited
        And the current branch has label release-0.0.1
        And there will be some conflicts when merging with branch develop
        When I issue the command: hg release --finish
        And I resolve the conflict
        And I update to branch release-0.0.1
        And I issue the command: hg release --finish
        Then release 0.0.1 is successfully finished

    Scenario: Redelivering after merge conflicts with production
        Given branch release-0.0.1 has been commited
        And the current branch has label release-0.0.1
        And there will be some conflicts when merging with branch default
        When I issue the command: hg release --finish
        And I resolve the conflict
        And I update to branch release-0.0.1
        And I issue the command: hg release --finish
        Then release 0.0.1 is successfully finished


    ###################
    # Error scenarios #
    ###################

    Scenario: Finishing the release from a non-release branch is an error
        Given branch release-0.0.1 has been commited
        And the current branch has label the-fish-slapping-dance-branch
        When I issue the command: hg release --finish
        Then Mercurial quits with a message

