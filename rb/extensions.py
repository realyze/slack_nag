"""
Extensions and utility functions for Python Review Board API.
"""

import urllib
from .reviewboard import Api20Client, make_rbclient


def get_review_requests2(options, auth):
    rb_api = make_rbclient("https://review.salsitasoft.com/", auth['username'], auth['password'])
    review_reqs = rb_api.get_review_requests(options)
    return review_reqs

def get_user_data(auth, url):
    rb_api = make_rbclient("https://review.salsitasoft.com/", auth['username'], auth['password'])
    res = rb_api._api_request('GET', url)
    if res['stat'] != 'ok':                                                                              
         print 'ERROR when getting user: ' + res
         return None
    return res['user']    


def get_last_update_info(auth, rid):
    rb_api = make_rbclient("https://review.salsitasoft.com/", auth['username'], auth['password'])
    res = rb_api._api_request(
            'GET',
            '/api/review-requests/%s/last-update/' % (rid,))
    if res['stat'] != 'ok':
        return None
    return res['last_update']


def is_story_approved(rb_server_url, story_id, auth=None):
    if not auth:
        auth = {'username': '', 'password': ''}
    rb_api = make_rbclient(rb_server_url, auth['username'], auth['password'])

    review_reqs = rb_api.get_review_requests()
    reviews_for_branch = [r for r in review_reqs
                            if r['branch'] == story_id
                            or r['branch'].startswith('feature/' + str(story_id))
			    or r['branch'].startswith('hotfix/'  + str(story_id))]

    def is_shipited(review_request):
        # Get all the reviews for review requestr with id @review_request.
        reviews = rb_api.get_reviews_for_review_request(
            review_request['id'])
	print reviews
        # Return True if the review has been approved.
        return len(reviews) > 0 and bool(reviews[-1]['ship_it'])

    return (len(reviews_for_branch) > 0 and
        all(is_shipited(r) for r in reviews_for_branch))


def get_reviews_for_review_request(auth, rev_req_id):
    rb_api = make_rbclient("https://review.salsitasoft.com/", auth['username'], auth['password'])
    rsp = rb_api._api_request(
        'GET', '/api/review-requests/%s/reviews/?max-results=200' % rev_req_id)
    return rsp['reviews']

Api20Client.get_reviews_for_review_request = get_reviews_for_review_request


def get_review_requests(self, options=None):
    options = options or {}
    rsp = self._api_request(
        'GET', '/api/review-requests/?%s' % urllib.urlencode(options))
    if rsp['stat'] != 'ok':
        print 'ERROR: ' + rsp['stat']
        return []
    start = options.get('start', 0)
    result = rsp['review_requests']
    if (rsp['total_results'] > start):
        print 'requesting another chunk, start at %s, total %s' % (start + 200, rsp['total_results'])
        options.update({'max-results': 200, 'start': start + 200})
        result = result + self.get_review_requests(options)
    return result

Api20Client.get_review_requests = get_review_requests
