from google_auth_oauthlib.flow import InstalledAppFlow
import pickle
import os

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

SCOPES = ['https://www.googleapis.com/auth/calendar']

flow = InstalledAppFlow.from_client_secrets_file(
    'credentials.json',
    SCOPES,
    redirect_uri='urn:ietf:wg:oauth:2.0:oob'
)

auth_url, _ = flow.authorization_url(
    prompt='consent',
    login_hint='pillowtalk151@gmail.com',
    access_type='offline'
)

print("\nOpen this URL in your browser:")
print(auth_url)
print("\nAfter authorizing, Google will show you a code.")
print("Paste that code here:")
code = input("> ")

flow.fetch_token(code=code)
creds = flow.credentials

with open('token.pickle', 'wb') as f:
    pickle.dump(creds, f)
print('Authentication successful!')
