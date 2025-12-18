# Google OAuth Setup Instructions

## Step 1: Create Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google+ API:
   - Go to "APIs & Services" > "Library"
   - Search for "Google+ API"
   - Click "Enable"

4. Create OAuth 2.0 credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Select "Web application"
   - Add authorized redirect URIs:
     - For local development: `http://localhost:8501`
     - For Streamlit Cloud: `https://your-app-name.streamlit.app` (update after deployment)
   - Click "Create"

5. Copy the Client ID and Client Secret

## Step 2: Configure Local Environment

1. Edit `.streamlit/secrets.toml`:
   ```toml
   [google_oauth]
   client_id = "YOUR_CLIENT_ID.apps.googleusercontent.com"
   client_secret = "YOUR_CLIENT_SECRET"
   authorized_users = []  # Leave empty to allow all, or add specific emails
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Step 3: Test Locally

1. Run the app:
   ```bash
   streamlit run app.py
   ```

2. The app should open at `http://localhost:8501`
3. Click "Sign in with Google"
4. Authenticate with your Google account
5. You should be redirected back to the app

## Step 4: Deploy to Streamlit Cloud

1. Push your code to GitHub (but **exclude** `.streamlit/secrets.toml`)
2. Go to [Streamlit Cloud](https://share.streamlit.io/)
3. Deploy your app
4. Add secrets in Streamlit Cloud:
   - Go to your app settings
   - Click "Secrets"
   - Add the same content from `.streamlit/secrets.toml`
   - Update the redirect URI in Google Console to match your Streamlit Cloud URL

5. Update `.streamlit/secrets.toml` on Streamlit Cloud:
   ```toml
   [google_oauth]
   client_id = "YOUR_CLIENT_ID.apps.googleusercontent.com"
   client_secret = "YOUR_CLIENT_SECRET"
   authorized_users = ["allowed-user@example.com"]  # Optional: restrict access
   redirect_uri = "https://your-app-name.streamlit.app"
   ```

## Security Notes

- **Never commit** `.streamlit/secrets.toml` to GitHub
- Add `.streamlit/secrets.toml` to `.gitignore`
- Use `authorized_users` to restrict access to specific email addresses
- Keep your Client Secret secure

## Troubleshooting

- **Redirect URI mismatch**: Make sure the redirect URI in Google Console matches exactly
- **Invalid credentials**: Double-check Client ID and Client Secret
- **Access denied**: Check if user email is in `authorized_users` list (if specified)
