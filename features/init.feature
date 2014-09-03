Using step definitions from: 'steps', 'init'

Feature: Command workflow
    In order to make it easier to initialize everything required for gitflow
    As a user
    I want to have a 'hg workflow --init' command

    Background:
        Given I have the following in my .hgrc file:
          """
          [reviewboard]
          server = https://test.server.foo/
          repoid = https://test.rb.foo

          [workflow]
          project_id = testid
          token = testtoken
          """


    Scenario: Creating the development branch
        Given there is no develop branch
        And the current branch has label default
        When I issue the command: hg initflow
        Then a new branch called "develop" is created

    Scenario: Creating the development branch from non-default branch is an error
        Given there is no develop branch
        And the current branch has label 'passion_fruit'
        When I issue the command: hg initflow
        Then Mercurial quits with a message
        And no branch is created

    Scenario: Calling ptselect without initializing the plugin is an error
        Given there is no develop branch
        And the current branch has label default
        When I issue the command: hg ptselect
        Then Mercurial quits with a message

    Scenario: Calling ptfinish without initializing the plugin is an error
        Given there is no develop branch
        And the current branch has label default
        When I issue the command: hg ptfinish
        Then Mercurial quits with a message

    Scenario: Calling 'hg release' without initializing the plugin is an error
        Given there is no develop branch
        And the current branch has label default
        When I issue the command: hg release
        Then Mercurial quits with a message
