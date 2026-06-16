"""Diagnostic: test st.markdown HTML rendering limits in Streamlit 1.49."""
import streamlit as st

st.set_page_config(page_title="HTML Test", layout="wide")

# Test 1: single st.markdown with multiple HTML blocks (current approach)
cards_html = ""
for i in range(5):
    cards_html += f'<div style="padding:8px;margin:4px;border:1px solid white;color:white;">Card {i}</div>'

st.subheader("Test 1: Single st.markdown with joined HTML")
st.markdown(f"<div>{cards_html}</div>", unsafe_allow_html=True)

# Test 2: same but with st.html
st.subheader("Test 2: st.html with same joined HTML")
st.html(f"<div>{cards_html}</div>")

# Test 3: large HTML block (like signal engine)
big_html = ""
for i in range(5):
    big_html += f"""
    <article style="padding:10px;margin:6px;border:1px solid #4F8CFF;border-radius:12px;color:white;">
        <div>
            <div>
                <span style="color:gray;">TICKER{i}</span>
                <strong>BUY</strong>
            </div>
            <em>BUY</em>
        </div>
        <div>
            <div><span>Score</span><strong>0.{i}00</strong></div>
            <div><span>Headlines</span><strong>{i*3}</strong></div>
        </div>
    </article>
    """

st.subheader("Test 3: st.markdown with big multi-element HTML")
st.markdown(f"<div>{big_html}</div>", unsafe_allow_html=True)

st.subheader("Test 4: st.html with big multi-element HTML")
st.html(f"<div>{big_html}</div>")
