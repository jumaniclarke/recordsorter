import os
import streamlit as st
from authlib.integrations.requests_client import OAuth2Session

SCOPES = ['openid', 'email', 'profile']

def get_google_oauth_config():
    """Get Google OAuth configuration from secrets or environment."""
    try:
        cfg = st.secrets.get("google_oauth", {})
        client_id = cfg["client_id"]
        client_secret = cfg["client_secret"]
        authorized_users = cfg.get("authorized_users", [])
    except Exception:
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

def create_oauth_session():
    """Create Authlib OAuth2 session for Google."""
    client_id, client_secret, _ = get_google_oauth_config()
    redirect_uri = get_redirect_uri()
    client = OAuth2Session(
        client_id=client_id,
        client_secret=client_secret,
        scope=" ".join(SCOPES),
        redirect_uri=redirect_uri,
    )
    # Google OpenID Connect endpoints
    auth_endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
    token_endpoint = "https://oauth2.googleapis.com/token"
    userinfo_endpoint = "https://openidconnect.googleapis.com/v1/userinfo"
    return client, auth_endpoint, token_endpoint, userinfo_endpoint

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
            client, auth_endpoint, _, _ = create_oauth_session()
            authorization_url, state = client.create_authorization_url(
                auth_endpoint,
                code_challenge_method="S256",
                prompt='select_account',
                access_type='offline',
                include_granted_scopes='true',
            )
            st.session_state.oauth_state = state
            st.session_state.oauth_code_verifier = getattr(client, "code_verifier", None)
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
            client, _, token_endpoint, userinfo_endpoint = create_oauth_session()
            token = client.fetch_token(
                token_endpoint,
                code=code,
                code_verifier=st.session_state.get("oauth_code_verifier"),
            )

            # Fetch user info via OIDC userinfo endpoint
            resp = client.get(userinfo_endpoint)
            data = resp.json() if resp and resp.content else {}
            email = data.get('email')
            name = data.get('name') or data.get('given_name')
            picture = data.get('picture')
            
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
