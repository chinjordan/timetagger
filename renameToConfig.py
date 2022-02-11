# where to redirect to
redirect_uri = 'http://localhost:8080/timetagger/api/v2/oauth/github'
# github app's secret
secret = ''
# github app's id
id = ''
github_auth = f"https://github.com/login/oauth/authorize?client_id={id}&redirect_uri={redirect_uri}"
github_token = f"https://github.com/login/oauth/access_token?client_id={id}&client_secret={secret}&code="
# Only allow a few accounts to log in.
acceptable_accounts = ["boehs"]