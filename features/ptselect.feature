Feature: Command ptselect
    In order to make it easier to start working on a new story
    As a user
    I want to have a 'hg select' command

    Background:
        Given I have a PT project with ID "testid"
        And the repository has been initialized using the plugin


    Scenario: Empty project.
      # Override stories.
      Given the project has no stories
      When I issue the command: hg ptselect --project_id testid --token testtoken
      Then Mercurial quits with an error message


    Scenario: Uncommited changes
        Given there are some uncommited changes in the working copy
        When I issue the command: hg ptselect --project_id testid --token testtoken
        Then Mercurial quits with a message


    @quit_when_prompted
    Scenario: List only unscheduled and started features and bugs from current & backlog by default
        Given there are no uncommited changes in the working copy
        And the project has the stories defined in file stories.txt
        When I issue the command: hg ptselect --project_id testid --token testtoken
        Then I see the following output:
            """
            1 : As a user1, I want bar1, so that baz1.
            2 : As a user2, I want bar2, so that baz2.
            3 : As a user5, I want bar5, so that baz5.
            4 : As a user6, I want bar6, so that baz6.
            """
        And I am prompted to select one of the stories.


     Scenario: List started bugs from current & backlog only
      Given the project has the stories defined in file stories.txt
      When I issue the command: hg ptlist --project_id testid --token testtoken --types bug --states started
      Then I see the following output:
        """
        61 : As a user6, I want bar6, so that baz6.
        """


     Scenario: List unscheduled chores and bugs from current & backlog only.
      Given the project has the stories defined in file stories.txt
      When I issue the command: hg ptlist --project_id testid --token testtoken --types bug,chore --states unscheduled
      Then I see the following output:
        """
        43 : As a user2, I want bar2, so that baz2.
        62 : As a user7, I want bar7, so that baz7.
        """


    @quit_when_prompted
    Scenario: Forcing select when there are outstanding uncommited changes
        Given there are some uncommited changes in the working copy
        And the project has the stories defined in file stories.txt
        When I issue the command: hg ptselect --force --project_id testid --token testtoken
        Then I see the following output:
            """
            1 : As a user1, I want bar1, so that baz1.
            2 : As a user2, I want bar2, so that baz2.
            3 : As a user5, I want bar5, so that baz5.
            4 : As a user6, I want bar6, so that baz6.
            """
        And I am prompted to select one of the stories.


    @quit_when_prompted
    Scenario: Cleaning working dir when there are outstanding uncommited changes
        Given there are some uncommited changes in the working copy
        And the project has the stories defined in file stories.txt
        When I issue the command: hg ptselect --clean --project_id testid --token testtoken
        Then I see the following output:
            """
            1 : As a user1, I want bar1, so that baz1.
            2 : As a user2, I want bar2, so that baz2.
            3 : As a user5, I want bar5, so that baz5.
            4 : As a user6, I want bar6, so that baz6.
            """
        And I am prompted to select one of the stories
        And all uncommited changes in the working copy have been reverted.


    @quit_when_prompted
    Scenario: Cleaning with no backup files.
        Given there are some uncommited changes in the working copy
        And the project has the stories defined in file stories.txt
        And I have the following in my .hgrc file:
            """
            [workflow]
            no_backup_files = True
            """
        When I issue the command: hg ptselect --clean --project_id testid --token testtoken
        Then I see the following output:
            """
            1 : As a user1, I want bar1, so that baz1.
            2 : As a user2, I want bar2, so that baz2.
            3 : As a user5, I want bar5, so that baz5.
            4 : As a user6, I want bar6, so that baz6.
            """
        And I am prompted to select one of the stories
        And all uncommited changes in the working copy have been reverted
        And no backup files have been created


    Scenario: Cleaning fails.
        Given there are some uncommited changes in the working copy
        And reverting the changes in the working directory will fail
        When I issue the command: hg ptselect --clean --project_id testid --token testtoken
        Then Mercurial quits with an error message
        And no branch is created


    Scenario: Creating a branch
        Given there are no uncommited changes in the working copy
        And the project has the stories defined in file stories.txt
        # This is stupid...I have to figure out a way to mock blocking
        # wait for input.
        And I will type "1" when I am prompted
        When I issue the command: hg ptselect --project_id testid --token testtoken
        Then a new branch called "42" is created
        And the story with id 42 is started in PT


    Scenario: Selecting last story
        Given there are no uncommited changes in the working copy
        And the project has the following stories:
        | id        | name                                      | iteration | story_type |
        | 42        | As a user1, I want bar1, so that baz1.    | current   | feature    |
        | 43        | As a user1, I want bar1, so that baz1.    | current   | bug    |
        And I will type "2" when I am prompted
        When I issue the command: hg ptselect --project_id testid --token testtoken
        Then a new branch called "43" is created
        And the story with id 43 is started in PT


    Scenario: Selecting index 0
        Given there are no uncommited changes in the working copy
        And the project has the following stories:
        | id        | name                                      | iteration | story_type |
        | 42        | As a user1, I want bar1, so that baz1.    | current   | feature    |
        | 43        | As a user1, I want bar1, so that baz1.    | current   | bug    |
        And I will type "0" when I am prompted
        When I issue the command: hg ptselect --project_id testid --token testtoken
        Then Mercurial quits with an error message
        And no branch is created


    Scenario: Invalid input value
        Given there are no uncommited changes in the working copy
        And the project has the stories defined in file stories.txt
        # This is stupid...I have to figure out a way to mock blocking
        # wait for input.
        And I will type "invalid" when I am prompted
        When I issue the command: hg ptselect --project_id testid --token testtoken
        Then Mercurial quits with an error message


    Scenario: Pivotal Tracker returns an error when starting a story.
        Given there are no uncommited changes in the working copy
        And the project has the stories defined in file stories.txt
        And the PT server returns a failure message for story id 42 start request
        # This is stupid...I have to figure out a way to mock blocking
        # wait for input.
        And I will type "1" when I am prompted
        When I issue the command: hg ptselect --project_id testid --token testtoken
        Then Mercurial quits with an error message
        And no branch is created


    Scenario: Select a story by id.
        Given there are no uncommited changes in the working copy
        And the project has the stories defined in file stories.txt
        When I issue the command: hg ptselect --story 42 --project_id testid --token testtoken
        Then a new branch called "42" is created
        And the story with id 42 is started in PT


    Scenario: Trying to select an unpointed story.
        Given there are no uncommited changes in the working copy
        And the project has the stories defined in file stories.txt
        And the story with id 42 has not been pointed
        When I issue the command: hg ptselect --story 42 --project_id testid --token testtoken
        Then Mercurial quits with an error message
        And no branch is created


    Scenario: Select a story by id using a nonexistent id.
        Given there are no uncommited changes in the working copy
        And the project has the stories defined in file stories.txt
        When I issue the command: hg ptselect --story 7345 --project_id testid --token testtoken
        Then Mercurial quits with an error message
        And no branch is created


    Scenario: Selecting a story for which a branch already exists.
        Given there are no uncommited changes in the working copy
        And the project has the stories defined in file stories.txt
        And branch 42 exists
        And the current branch has label develop
        When I issue the command: hg ptselect --story 42 --project_id testid --token testtoken
        Then the current branch has label 42


    Scenario: Selecting a story from 'default'
        Given there are no uncommited changes in the working copy
        And the project has the stories defined in file stories.txt
        And branch 42 exists
        And the current branch has label default
        When I issue the command: hg ptselect --story 42 --project_id testid --token testtoken
        Then Mercurial quits with an error message


    @quit_when_prompted
    Scenario: Colored output.
        Given there are no uncommited changes in the working copy
        And the project has the following stories:
        | id        | name                                      | iteration | story_type |
        | 42        | As a user1, I *want bar1*, so that baz1.  | current   | feature    |
        When I issue the command: hg ptselect --project_id testid --token testtoken
        Then I see the following ANSI colorized output:
            """
            1 : As a user1, I \x1b[1mwant bar1\x1b[0m, so that baz1.
            """
        And I am prompted to select one of the stories


    Scenario: Stories with closed branch can be selected.
        Given there are no uncommited changes in the working copy
        And the project has the stories defined in file stories.txt
        And we have restarted a rejected story with id 42
        When I issue the command: hg ptselect --project_id testid --token testtoken --story 42
        Then the current branch has label 42
