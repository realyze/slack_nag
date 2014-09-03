Using step definitions from: 'steps', 'release_steps'

Feature: Command release --start
    In order to make it easier to prepare the codebase for an upcoming release
    As a user
    I want the plugin to support creating the release branches

    Background:
        Given I have a PT project with ID "testid"
        And the repository has been initialized using the plugin
        And the project has the following stories:
          | id | name                                      | iteration | story_type | current_state |
          | 42 | As a user1, I want bar1, so that baz1.    | current   | feature    | finished      |
          | 43 | As a user2, I want bar2, so that baz2.    | current   | chore      | finished      |
          | 44 | As a user3, I want bar3, so that baz3.    | current   | chore      | finished      |
        And I have the following in my .hgrc file:
          """
          [workflow]
          project_id = testid
          token = testtoken
          """


    ########################
    # Successful scenarios #
    ########################
    Scenario: Listing stories - no blocked stories
        Given there is a version.txt file in the repo root
        And stories 42,43 are ready to be released
        And I will type "n" when I am prompted
        When I issue the command: hg release --start 0.0.1
        Then I see the following output:
            """
Releasable stories:
42 (As a user1, I want bar1, so that baz1.)
43 (As a user2, I want bar2, so that baz2.)

Blocked stories:
            """

    Scenario: Listing stories - blocked stories
        Given there is a version.txt file in the repo root
        # Order is important here!
        And the branch with label 43 has closed parent branch 42
        And the branch with label 44 has unclosed parent branch 43
	And the current branch has label develop
        And stories 42,44 are ready to be released
        And I will type "n" when I am prompted
        When I issue the command: hg release --start 0.0.1
        Then I see the following output:
            """
Releasable stories:
42 (As a user1, I want bar1, so that baz1.)

Blocked stories:
44 (As a user3, I want bar3, so that baz3.) (blocked by stories: ['43'])
            """

    Scenario: Starting release successfully
        Given there is a version.txt file in the repo root
        And stories 42,43 are ready to be released
        And I will type "y" when I am prompted
        When I issue the command: hg release --start 0.0.1
        Then a new branch called "release-0.0.1" is created
        And a label 0.0.1 is added to stories 42,43
	And branch release-0.0.1 is pushed to the central repository



    ###################
    # Error scenarios #
    ###################
    # TODO(Tom): This scenario will be obsolete in close future.
    Scenario: Not specyfing the release number is an error
        When I issue the command: hg release --start
        Then Mercurial quits with an error message

    Scenario: Missing version file is an error.
        Given there is no 'version.txt' file in the repo root
        When I issue the command: hg release --start 0.1.1
        Then Mercurial quits with an error message

    Scenario: Releasin from other branch than 'develop' is an error
    	Given the current branch has label 'default'
        When I issue the command: hg release --start
        Then Mercurial quits with an error message

