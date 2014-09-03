import os, errno, re
import urllib2
from mercurial.i18n import _
from urlparse import urljoin, urlparse
from xml.dom.minidom import parseString

class APIError(Exception):
  pass

class BasecampError(Exception):
  def __init__(self):
    self.msg = None
    self.code = None
    self.tags = {}


  def __str__(self):
    if self.msg:
      return ("%s (%s)" % (self.msg, self.code)) + \
          ''.join([("\n%s: %s" % (k, v)) for k,v in self.tags.items()])
    else:
      return Exception.__str__(self)

class ApiRequest(urllib2.Request):
  def __init__(self, method, *args, **kwargs):
    self._method = method
    urllib2.Request.__init__(self, *args, **kwargs)

  def get_method(self):
    return self._method

class BasecampHTTPPasswordMgr(urllib2.HTTPPasswordMgr):
  def __init__(self, url, userToken):
    self.url = url
    self.userToken = userToken

  def find_user_password(self, realm, uri):
    if uri.startswith(self.url):
      return self.userToken, "X"
    else:
      return urllib2.HTTPPasswordMgr.find_user_password(self, realm, uri)


class HttpErrorHandler(urllib2.HTTPDefaultErrorHandler):
  def http_error_default(self, req, fp, code, msg, hdrs):
    if code >= 400:
      return urllib2.HTTPDefaultErrorHandler.http_error_default(self,
          req, fp, code, msg, hdrs)
    else:
      result = urllib2.HTTPError( req.get_full_url(), code, msg, hdrs, fp)
      result.status = code
      return result

class BasecampAPI():
  def __init__(self, url, userToken):
    self.userToken = userToken

    if not url.endswith('/'):
        url = url + '/'
    self.url       = url

    self._password_mgr = BasecampHTTPPasswordMgr(self.url, self.userToken)
    self._opener = opener = urllib2.build_opener(
                    urllib2.UnknownHandler(),
                    urllib2.HTTPHandler(),
                    HttpErrorHandler(),
                    urllib2.HTTPErrorProcessor(),
                    urllib2.HTTPBasicAuthHandler(self._password_mgr),
                    urllib2.HTTPDigestAuthHandler(self._password_mgr)
                    )
    urllib2.install_opener(self._opener)

  def _http_request(self, method, path, data):
    if path.startswith('/'):
        path = path[1:]
    url = urljoin(self.url, path)
    headers = {"Content-Type" : "application/xml", "Accept" : "application/xml"}

    try:
      r = ApiRequest(method, url, data, headers)
      data = urllib2.urlopen(r).read()
      return data
    except urllib2.URLError, e:
      if not hasattr(e, 'code'):
        raise
      if e.code >= 400:
        raise BasecampError(e.read())
      else:
        return ""
    except urllib2.HTTPError, e:
      raise BasecampError(e.read())

  def api_request(self, method, url, data=None):
    try:
      rsp = self._http_request(method, url, data)
      if rsp:
        return parseString(rsp)
      else:
        return None
    except APIError, e:
      rsp, = e.args
      raise BasecampError(rsp)

