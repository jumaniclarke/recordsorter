import streamlit as st
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests
import os
import json

SCOPES = ['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']

def get_google_oauth_config():
    """Get Google OAuth configuration from secrets or environment."""
    try:
        client_id = st.secrets["google_oauth"]["client_id"]
        client_secret = st.secrets["google_oauth"]["client_secret"]
        authorized_users = st.secrets["google_oauth"].get("authorized_users", [])
    except (KeyError, FileNotFoundError):
        st.error("Google OAuth credentials not configured. Please set up .streamlit/secrets.toml")
        st.stop()
    
    return client_id, client_secret, authorized_users

def get_redirect_uri():
    """Get the redirect URI based on environment."""
    # Prefer explicit overrides in secrets
    try:
        # Allow either [google_oauth] or [auth] to specify redirect_uri
        nested = st.secrets.get("google_oauth", {})
        if isinstance(nested, dict) and nested.get("redirect_uri"):
            return nested["redirect_uri"]
        nested = st.secrets.get("auth", {})
        if isinstance(nested, dict) and nested.get("redirect_uri"):
            return nested["redirect_uri"]
    except Exception:
        pass

    # Derive from env if running locally with a specific host/port
    addr = os.getenv("STREAMLIT_SERVER_ADDRESS")
    port = os.getenv("STREAMLIT_SERVER_PORT", "8501")
    proto = os.getenv("STREAMLIT_SERVER_PROTOCOL", "http")
    if addr:
        return f"{proto}://{addr}:{port}"

    # Default
    return "http://localhost:8501"

def create_flow():
    """Create OAuth flow."""
    client_id, client_secret, _ = get_google_oauth_config()
    redirect_uri = get_redirect_uri()
    
    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }
    
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    return flow

def is_user_authorized(email):
    """Check if user email is authorized."""
    _, _, authorized_users = get_google_oauth_config()
    
    # If no authorized users specified, allow all
    if not authorized_users:
        return True
    
    return email in authorized_users

def show_login_page():
    """Display login page."""
    st.title("🔐 Student Record Browser")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        ### Welcome
        
        Please sign in with your Google account to access the student record browser.
        
        This application allows you to:
        - Browse student records
        - View academic progress
        - Check programme requirements
        - Annotate student records
        """)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("🔑 Sign in with Google", use_container_width=True, type="primary"):
            flow = create_flow()
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='select_account'
            )
            st.session_state.oauth_state = state
            st.markdown(f'<meta http-equiv="refresh" content="0;url={authorization_url}">', unsafe_allow_html=True)
            st.markdown(f"[Click here if not redirected automatically]({authorization_url})")

def handle_oauth_callback():
    """Handle OAuth callback after Google authentication."""
    query_params = st.query_params

    def _first(val):
        if isinstance(val, (list, tuple)):
            return val[0] if val else None
        return val

    code = _first(query_params.get("code"))
    state = _first(query_params.get("state"))

    if code and state:
        expected_state = st.session_state.get("oauth_state")
        # If session state was lost (e.g., new browser tab/host), accept this state once and persist it.
        if not expected_state:
            st.session_state.oauth_state = state
            expected_state = state

        # Verify state
        if state != expected_state:
            st.error("Invalid state parameter. Please try logging in again.")
            return False
        
        try:
            flow = create_flow()
            flow.fetch_token(code=code)
            
            credentials = flow.credentials
            request = requests.Request()
            
            # Verify the token and get user info
            id_info = id_token.verify_oauth2_token(
                credentials.id_token,
                request,
                get_google_oauth_config()[0]
            )
            
            email = id_info.get('email')
            name = id_info.get('name')
            picture = id_info.get('picture')
            
            # Check if user is authorized
            if not is_user_authorized(email):
                st.error(f"Access denied. The email {email} is not authorized to use this application.")
                if st.button("Try another account"):
                    logout()
                return False
            
            # Store user info in session
            st.session_state.authenticated = True
            st.session_state.user_email = email
            st.session_state.user_name = name
            st.session_state.user_picture = picture
            
            # Clear query params
            st.query_params.clear()
            st.rerun()
            return True
            
        except Exception as e:
            st.error(f"Authentication failed: {str(e)}")
            return False
    
    return False

def logout():
    """Clear authentication state and logout."""
    keys_to_clear = ['authenticated', 'user_email', 'user_name', 'user_picture', 'oauth_state']
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.query_params.clear()
    st.rerun()

def is_authenticated():
    """Check if user is authenticated."""
    return st.session_state.get('authenticated', False)

def get_user_info():
    """Get authenticated user information."""
    return {
        'email': st.session_state.get('user_email', ''),
        'name': st.session_state.get('user_name', ''),
        'picture': st.session_state.get('user_picture', '')
    }

def show_user_info_sidebar():
    """Display user info and logout button in sidebar."""
    user_info = get_user_info()
    
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 👤 Logged in as")
        
        if user_info['picture']:
            col1, col2 = st.columns([1, 3])
            with col1:
                st.image(user_info['picture'], width=50)
            with col2:
                st.markdown(f"**{user_info['name']}**")
                st.caption(user_info['email'])
        else:
            st.markdown(f"**{user_info['name']}**")
            st.caption(user_info['email'])
        
        if st.button("🚪 Logout", use_container_width=True):
            logout()
