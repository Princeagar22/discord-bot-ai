import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

def main():
    creds = None
    
    # We use credentials.json to get authorization.
    if not os.path.exists('credentials.json'):
        print("ERROR: credentials.json not found! Please make sure it's in this folder.")
        return

    # Let's prompt the user to login in the browser
    print("Starting YouTube login...")
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    
    # This will open the web browser to authorize
    creds = flow.run_local_server(port=0)
    
    # Save the credentials for the next run
    with open('token.json', 'w') as token:
        token.write(creds.to_json())
        
    print("\nSUCCESS! You have successfully signed in!")
    print("The token.json file has been created. The bot will now use this to send messages.")

if __name__ == '__main__':
    main()
