Feature: Command ptlist
    In order to make it easier to list stories from PT
    As a user
    I want to have a 'hg ptlist' command

    Background:
      Given I have a PT project with ID "testid"


    Scenario: List only unscheduled and started features and bugs from current & backlog by default
      Given the project has the stories defined in file stories.txt
      When I issue the command: hg ptlist --project_id testid --token testtoken
      Then I see the following output:
        """
        42 : As a user1, I want bar1, so that baz1.
        43 : As a user2, I want bar2, so that baz2.
        60 : As a user5, I want bar5, so that baz5.
        61 : As a user6, I want bar6, so that baz6.
        """

    Scenario: List started bugs from current & backlog only
      Given the project has the stories defined in file stories.txt
      When I issue the command: hg ptlist --project_id testid --token testtoken --types bug --states started
      Then I see the following output:
        """
        61 : As a user6, I want bar6, so that baz6.
        """

    Scenario: Empty project.
      # Override stories.
      Given the project has no stories
      When I issue the command: hg ptlist --project_id testid --token testtoken
      Then I see the following output:
        """

        """

    Scenario: Config loaded from .hgrc.
      Given the project has the stories defined in file stories.txt
      And I have the following in my .hgrc file:
        """
        [workflow]
        project_id = testid
        token = testtoken
        """
      When I issue the command: hg ptlist
      Then I see the following output:
        """
        42 : As a user1, I want bar1, so that baz1.
        43 : As a user2, I want bar2, so that baz2.
        60 : As a user5, I want bar5, so that baz5.
        61 : As a user6, I want bar6, so that baz6.
        """

