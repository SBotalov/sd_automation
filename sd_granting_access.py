from jira import JIRA
import re
import json

import requests
import browser_cookie3

import creds as creds 

#connect to jira instance
jiraOptions = {'server' : creds.url
               }
jira = JIRA(server=jiraOptions, token_auth=creds.api_token)

#get list of issues
issues = []
def getIssues():
    print('Searhing for issues..')
    for singleIssue in jira.search_issues(jql_str='project = SD and issuetype = "Business Systems and Services" AND assignee = "stepan.botalov@dxc.com" and status = Approved'):
        issues.append(singleIssue.key)
    return issues

#get approval comments
approval_comments = []
def getComments(issues):
    print('Getting approval comments..')

    for issue in issues:  
        comments =  jira.comments(issue)
        for comment in comments:
            comment_dict = {}
            if comment.author.displayName == 'SD Robot' and 'The request has been sent for approval to' in comment.body:
                comment_dict['key'] = issue
                comment_dict['body'] = comment.body
                approval_comments.append(comment_dict)
    return approval_comments

cookies = browser_cookie3.chrome(domain_name='lp-uat.luxoft.com') #get current cookies_dict from the browser
cookies_dict = requests.utils.dict_from_cookiejar(cookies) #convert cookies_dict to dict

#get project code, project role, and username to grant access
code_role_user = []
def getProjectCode(approval_comments):
    print('Parsing approval comments..')

    for comment in approval_comments:
        approval_dict = {}

        project_code = re.search(r'([A-Z]){3,10}|([A-Z0-9]){3,10}', comment['body'])
        reporter = re.findall(r'[a-zA-Z.]+[0-9]?@dxc.com', comment['body'])
        project_role = re.search(r'project-manager|analyst|developer|tester|test-manager|customer|dev-lead|ci-engineer', comment['body'], re.IGNORECASE)
        
        approval_dict['key'] = comment['key']
        try:
            approval_dict['project_code'] = project_code.group()
        except (AttributeError):
            continue
        
        try: #adding username to a dict
            payload = {"search":reporter[1], #email
               "directoryIds":[360449],
               "avatarSizeHint":128}
            
            crowd_url = 'https://lp-uat.luxoft.com/crowd/rest/admin/latest/users/search?limit=50&start=0'
            r = requests.post(crowd_url, json=payload, cookies=cookies_dict) #search for a user using crowd api
            username = json.loads(r.text)['values'][0]['username'] # extracting username from response

            approval_dict['reporter'] = username

        except (IndexError):
            continue

        approval_dict['project_role'] = project_role.group()        

        code_role_user.append(approval_dict)      
        #print(approval_dict)
    return code_role_user


#send post request to add user to a project
console_url = 'https://lp-uat.luxoft.com/console/rest/project/nested-member'
def grantAccess(project_code, reporter, project_role):
    payload = {"projectCode":"",
               "userProjectRoles":[],
               "username":""}
    
    payload["projectCode"] = project_code
    payload["userProjectRoles"] = project_role
    payload["username"] = reporter
    
    r = requests.post(console_url, json=payload, cookies=cookies_dict)

    return r.status_code

def resolveIssue(key):
    comment = '''
    Access is granted
    Please check in 15 minutes.

    Regards,
    Stepan
    '''
    jira.transition_issue(issue=key, transition=61, resolution={'id': '1'}, worklog='20', comment=comment)

getIssues()
if len(issues) == 0:
    print('There is no requests in Approved status')
else:
    print(str(len(issues)) + ' issue(s) in Approved status - ' + str(issues))   
    getComments(issues)
    if len(approval_comments) == 0:
        print('No valid approval comments detected')
    else:
        getProjectCode(approval_comments)
        print(code_role_user)
        for x in code_role_user:
            print('Granting access to ' + x['reporter'] + ' to ' + x['project_code'] + ' project in the scope of ' + x['key'] + ' request')
            r = grantAccess(x['project_code'], x['reporter'], x['project_role'])
            print(r)
            if str(r) == '201':
                print('Access to ' + x['reporter'] + ' to ' + x['project_code'] + ' project successfully granted')
                resolveIssue(x['key'])
            else:
                print('post request got failed')
