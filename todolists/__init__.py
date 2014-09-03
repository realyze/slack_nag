'''Manage todos from basecamp.
   Version 1.0.1
'''

import os, errno, re, string, json
from mercurial import cmdutil, hg, ui, util, commands
from mercurial.i18n import _
from todolists import BasecampAPI

class CompletedError(Exception):
  pass

class SelectTodoException(Exception):
  messages = {
    0 : "Unknown error",
    1 : "Could not load XML",
    2 : "Empty list",
    3 : "Input invalid",
    4 : "Default selected",
    5 : "Item not found"
  }
  def __init__(self, code = -1):
    self.code = code
    try:
      self.msg = SelectTodoException.messages[code]
    except KeyError:
      self.msg = SelectTodoException.messages[0]

  def __str__(self):
    return self.msg

class SelectTodoListException(SelectTodoException):
  pass

class TodoItem():
  def __init__(self, todoList, myNode):
    self.todoList = todoList
    self.id = int(myNode.getElementsByTagName("id")[0].firstChild.nodeValue)
    self.content = myNode.getElementsByTagName("content")[0].firstChild.nodeValue
    if "false" != myNode.getElementsByTagName("completed")[0].firstChild.nodeValue:
      raise CompletedError()

  def __str__(self):
    return "%s (%stodo_items/%d)" % (self.content, self.todoList.API.url, self.id)

class TodoList():
  def __init__(self, API, projectID, myNode):
    self.API = API
    self.projectID = projectID
    self.id = int(myNode.getElementsByTagName("id")[0].firstChild.nodeValue)
    self.name = myNode.getElementsByTagName("name")[0].firstChild.nodeValue
    self.completedCount = int(myNode.getElementsByTagName("completed-count")[0].firstChild.nodeValue)
    self.uncompletedCount = int(myNode.getElementsByTagName("uncompleted-count")[0].firstChild.nodeValue)
    self.itemCount = self.completedCount + self.uncompletedCount
    self.todos = {}

  def addItems(self, nodeList):
    i = 1
    for node in nodeList:
      try:
        self.todos[i] = TodoItem(self, node)
        i += 1
      except TypeError:
        pass
      except IndexError:
        pass
      except CompletedError:
        pass

  def __str__(self):
    return "%s (%sprojects/%d/todo_lists/%d)" % (self.name, self.API.url, self.projectID, self.id)

class TodolistHander():

  def selectTodo(self, ui, todoItemList):

    fullTodoList = {}
    itemList = []

    i = 1
    for todoList in todoItemList:
      path = "/todo_lists/%d.xml" % todoList.id
      xml = self.API.api_request("GET", path)
      if None != xml:
        todoList.addItems(xml.getElementsByTagName("todo-item"))
        # special treatment for todo-lists with only one item
        # they will not be shown so put them to final list now
        if 1 == len(todoList.todos):
          for k,v in todoList.todos.iteritems():
            itemList.append(v)
        else:
          for k,v in todoList.todos.iteritems():
            fullTodoList[i] = v
            i += 1
    # if full list is empty and final list is empty throw
    if 0 == len(fullTodoList) and 0 == len(itemList):
      raise SelectTodoException(2)

    if len(fullTodoList) > 0:
      ui.status('\nTodos:\n')
      currentList = None
      for k,v in fullTodoList.iteritems():
        if currentList != v.todoList:
          ui.status(' %s:\n' % v.todoList.name )
          currentList = v.todoList
        status = '  [%s] %s\n' % (k, v.content)
        ui.status(status.encode("utf-8"))
      val = ui.prompt('\nSelect todos (space separated, leave empty for all items):', "")
      if "" == val:
        # empty input: append whole list
        for k, v in fullTodoList.iteritems():
          itemList.append(v)
      else:
        # split input and append each item
        vals = string.split(val)
        for k in vals:
          try:
            kI = int(k)
            if kI in fullTodoList.keys():
              itemList.append(fullTodoList[kI])
          except TypeError:
            pass
          except ValueError:
            pass
    if 0 == len(itemList):
      raise SelectTodoListException(2)

    return itemList


  def selectTodoList(self, ui):
    ui.status('\nTodo-Lists:\n')
    path = "/projects/%d/todo_lists.xml?filter=pending" % self.project
    xml = self.API.api_request("GET", path)
    if None == xml:
      raise SelectTodoListException(1)

    self.todoLists = {}
    nodeList = xml.getElementsByTagName("todo-list")
    i = 1
    for node in nodeList:
      try:
        todoList = TodoList(self.API, self.project, node)
        if 0 != todoList.uncompletedCount:
          self.todoLists[i] = todoList
          i += 1
      except TypeError:
        pass
      except IndexError:
        pass

    if 0 == len(self.todoLists):
      raise SelectTodoListException(2)

    for k,v in self.todoLists.iteritems():
      ui.status(' [%s] %s\n' % (k, v.name) )

    val = ui.prompt('\nSelect list (space separated, leave empty for all items):', "")
    itemList = []
    if "" == val:
      # empty input: append whole list
      for k, v in self.todoLists.iteritems():
        itemList.append(v)
    else:
      # split input and append each item
      vals = string.split(val)
      for k in vals:
        try:
          kI = int(k)
          if kI in self.todoLists.keys():
            itemList.append(self.todoLists[kI])
        except TypeError:
          pass
        except ValueError:
          pass
    if 0 == len(itemList):
      raise SelectTodoListException(2)
    return self.selectTodo(ui, itemList)

  def cmdDone(self, ui, repo, args, project, opts):
    try:
      allTodos = self.selectTodoList(ui)
    except SelectTodoException, e:
      raise util.Abort(e)
    except SelectTodoListException, e:
      raise util.Abort(e)

    msgItem = {"todos" : []}
    allTodosHr = []
    for v in allTodos:
      #msgItem["todos"].append({"id" : v.id, "list" : v.todoList.id})
      allTodosHr.append(v.content.encode("utf-8"))

    if "message" in opts:
      msgItem["message"] = opts["message"]
    if len(allTodosHr) > 1:
      msgHr = " +\n".join(allTodosHr)
    else:
      msgHr = allTodosHr[0]

    opts["message"] = msgHr + "\n\nJSON:\n" + json.dumps(msgItem)
    commands.commit(ui, repo, *args, **opts)

  def __init__(self, ui, repo, project, listsonly):
    self.listsonly = listsonly
    self.project = project
    self.todoLists = {}

    token = ui.config('todolists', 'token')
    if not token:
      raise util.Abort(
            _('Please specify a basecamp token in your .hgrc file') )

    server = ui.config('todolists', 'server')
    if not server:
      raise util.Abort(
            _('Please specify a basecamp server in your .hgrc file') )

    if 0 == self.project:
      raise util.Abort(
            _('Please specify a basecamp project-id in your hgrc file') )

    self.API = BasecampAPI(server, token)

    if not self.API:
      raise util.Abort(
            _('Missing basecamp API.') )


def cmdCommitDone(ui, repo, *args, **opts):
  """Commit a finished todo
  Options are like normal commit options (except -l).
  There is one extra option (-p) that let's you select
  a project. But usually you put the project id in your
  repositorys hgrc-file.

  The selected todos are compiled in the commit message together
  with the message you enter (if any) in json format.

  All options are optional.

  """
  listsonly = ui.configbool('todolists', 'listsonly', False)
  commitMsg = opts['message']
  project = opts['project'] or ui.config('todolists', 'project')
  try:
    project = int(project)
  except TypeError:
    raise util.Abort(_('invalid or missing basecamp project-id'))
  except ValueError:
    raise util.Abort(_('invalid or missing basecamp project-id'))
  del opts['project']

  optsCommit = {}
  for k,v in opts.iteritems():
    if None != v and '' != v:
      optsCommit[k] = v
  todolist = TodolistHander(ui, repo, project, listsonly)
  todolist.cmdDone(ui, repo, args, project, optsCommit)

def cmdRenderTodos(ui, repo, **opts):
  ctx = repo[None]
  #print ctx.description()
  #optsHG = {"date" : None, "rev" : None, "user" : None}
  #commands.log(ui, repo, **optsHG)

cmdtable = {
  "commit-done" :
    (cmdCommitDone, [
      ('p','project',0,'Project ID: If not set it is taken from hgrc in current repo'),
      ('A','addremove',None,'see hg commit'),
      ('','close-branch',None,'see hg commit'),
      ('I','include','','see hg commit'),
      ('X','exclude','','see hg commit'),
      ('m','message','','see hg commit'),
      ('d','date','','see hg commit'),
      ('u','user','','see hg commit')
    ],
    "[options]")}
