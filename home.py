import streamlit as st

st.title("Authentication")

if not st.user.is_logged_in:
    if st.button("Authentication"):
        st.login("google")
else:
    if st.button("Logout"):
        st.logout()
    st.image(st.user.picture)

st.write(st.user)
st.write("You are logged in as " + st.user.name if st.user.is_logged_in else "You are not logged in.")

