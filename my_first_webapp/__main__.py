"""
WebApp to enable "tracking" feature on GitHib feature branches.

Effect : whenever new commits are pushed to the "tracked" branch,
create a PR from "tracked" branch onto "tracking".

Typical use: "master" is tracked --> "<some-feature-branch>"

"""
import datetime
import os

import requests

import tornado.httpserver
import tornado.ioloop
import tornado.web


#
# TODOs:
#  * response strings should be sanitised ??
#  * work out how to get own github repo url for referencing ?
#  * translate main (github www) repo-url into api-url (currently fudged).
#  * log errors in operation + make log visible / clearable.
#


def handle_get_for_browsertest(request, application):
    time_str = datetime.datetime.now().isoformat()
    application.n_gets += 1
    msg = "Hello!  TIME={}  #GETS={}"
    return msg.format(time_str, application.n_gets)


def expect_element(item_dict, item_name, element_name):
    if element_name in item_dict:
        value = item_dict[element_name]
        result = value, None
    else:
        error = '{} contains no "{!s}" element ?'
        error = error.format(item_name, element_name)
        result = None, error
    return result


def create_update_pr(repo_url, tracked_branch_name, tracking_branch_name,
                     own_url=None):
    token_string = os.environ['GITHUB_ACCESS_TOKEN']
    # Convert the main access url to an api url - probably a bit dodgy?
    repo_api_url = repo_url.replace('github.com', 'api.github.com/repos')
    headers = {'Authorization': 'token {}'.format(token_string),
               'Accept': 'application/vnd.github.v3+json'}
    if own_url is None:
        own_url = "https://github.com/pp-mo/github_branches_follow"
    msg = 'Automatic branch-tracking PR, generated by htpps://{!r}\n'
    body = msg.format(own_url)
    title = 'FEATURE-FOLLOWING: Merge branch "{}" into "{}".'
    title = title.format(tracked_branch_name, tracking_branch_name)
    params = {
        'title': title,
        'head': tracked_branch_name,
        'base': tracking_branch_name,
        'body': body
        }
    url = repo_api_url + '/pulls'
    pr_post_response = requests.post(url, json=params, headers=headers)
    ppr_head = str(pr_post_response)
    ppr_content = tornado.escape.json_decode(pr_post_response.content)
    response = 'PR-create({!s}:{!r})'.format(ppr_head, ppr_content)
    return response


def handle_post_for_webhook(request, app):
    headers = request.headers
    event_type, err = expect_element(headers, 'headers', 'X-GitHub-Event')
    if err:
        err += '... headers-keys={!r}'.format(headers.keys())
        return err

    if event_type != 'push':
        agent = headers.get('User-Agent', '(?no "User-Agent")')
        response = ('Unrecognised event type: '
                    '"User-Agent"={!s}, "X-GitHub-Event"={!s}')
        response = response.format(agent, event_type)
        return response

    body = tornado.escape.json_decode(request.body)
    repo, err = expect_element(body, 'body', 'repository')
    if err:
        return err

    repo_url, err = expect_element(repo, 'body[repository]', 'url')
    if err:
        return err

    ref_path, err = expect_element(body, 'body', 'ref')
    if err:
        return err

    ref_path_els = ref_path.split('/')
    if (len(ref_path_els) != 3 or
            ref_path_els[:2] != ['refs', 'heads']):
        response = 'Ref path "{}" not of form "refs/heads/xxx"'
        response = response.format(ref_path)
        return response
    else:
        push_branch_name = ref_path_els[2]

    response = ''
    for repo, tracked, tracking in app.recognised_branches:
        if (repo == repo_url and tracked == push_branch_name):
            pulls_info = create_update_pr(
                repo, tracked, tracking,
                own_url=request.headers['Host'])
            msg = '  In({!s}):track({!s}-->{!s})=<<{!s}>> '
            msg = msg.format(repo, tracked, tracking, pulls_info)
            response += msg

    if not response:
        response = 'Repo::branch "{!s}"::"{!s}" is not tracked.'
        response = response.format(repo_url, push_branch_name)

    return response


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        response = handle_get_for_browsertest(
            self.request, self.application)
        self.write(response)

    def post(self):
        response = handle_post_for_webhook(self.request, self.application)
        self.write(response)


def configure_application(app):
    """
    Define global values on the app.

    Especially as we can't use global variables.

    """
    # Just for fun, shows a count in the "GET" response.
    app.n_gets = 0
    # Configure which branches track which others in which repos...
    app.recognised_branches = [
        # *[(repo-url, main-branch-name, tracking-branch-name)]
        ("https://github.com/pp-mo/github_trial", "master", "feature_branch"),
    ]


def main():
    application = tornado.web.Application([
        (r"/", MainHandler),
    ])
    configure_application(application)
    http_server = tornado.httpserver.HTTPServer(application)
    PORT = os.environ.get('PORT', 8080)
    http_server.listen(PORT)
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
