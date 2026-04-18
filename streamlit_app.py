"""
Vault-AI: Privacy-Preserving Document Intelligence
Main Streamlit application — Home page with user-oriented guide.
"""

import streamlit as st
from components import render_sidebar

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Vault-AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }

    /* Hero section */
    .hero-container {
        background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 50%, #6D28D9 100%);
        border-radius: 16px;
        padding: 48px 40px;
        margin-bottom: 32px;
        color: white;
        position: relative;
        overflow: hidden;
    }
    .hero-container::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -20%;
        width: 400px;
        height: 400px;
        background: rgba(255,255,255,0.05);
        border-radius: 50%;
    }
    .hero-title {
        font-size: 2.5rem;
        font-weight: 800;
        margin-bottom: 8px;
        letter-spacing: -0.02em;
    }
    .hero-subtitle {
        font-size: 1.1rem;
        opacity: 0.9;
        font-weight: 400;
        max-width: 600px;
        line-height: 1.6;
    }
    .hero-badge {
        display: inline-block;
        background: rgba(255,255,255,0.15);
        backdrop-filter: blur(10px);
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-bottom: 16px;
        letter-spacing: 0.05em;
    }

    /* Step cards */
    .step-card {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 24px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        height: 100%;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .step-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }
    .step-number {
        display: inline-block;
        background: #EEF2FF;
        color: #4F46E5;
        width: 32px;
        height: 32px;
        border-radius: 50%;
        text-align: center;
        line-height: 32px;
        font-weight: 800;
        font-size: 0.9rem;
        margin-bottom: 12px;
    }
    .step-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 8px;
    }
    .step-desc {
        font-size: 0.88rem;
        color: #64748B;
        line-height: 1.5;
    }

    /* Info box */
    .info-box {
        background: #FFFBEB;
        border: 1px solid #FCD34D;
        border-radius: 10px;
        padding: 16px 20px;
        margin: 16px 0;
        font-size: 0.9rem;
        color: #92400E;
        line-height: 1.6;
    }
    .privacy-box {
        background: #F0FDF4;
        border: 1px solid #86EFAC;
        border-radius: 10px;
        padding: 16px 20px;
        margin: 16px 0;
        font-size: 0.9rem;
        color: #166534;
        line-height: 1.6;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        font-size: 0.9rem;
    }

    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        font-family: 'Inter', sans-serif;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
    }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────────────────
render_sidebar("home")

# ── Hero Section ─────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="hero-container">
        <div class="hero-badge">🔐 YOUR DOCUMENTS, YOUR PRIVACY</div>
        <div class="hero-title">Vault-AI</div>
        <div class="hero-subtitle">
            Upload sensitive documents, and we'll automatically find and protect
            personal information — names, emails, phone numbers, and more.
            Ask questions about your documents safely, without exposing private data.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Set Your Password Section ────────────────────────────────────────────────
import os
import chromadb
from config import Config

vault_path = os.path.join(Config.VAULT_DATA_DIR, "vault.enc")
vault_exists = os.path.exists(vault_path)
is_authenticated = st.session_state.get("_vault_authenticated", False)
current_password = st.session_state.get("_vault_password")

if is_authenticated and current_password:
    # ── Already authenticated — show status ──────────────────────────────
    st.markdown(
        """
        <div style="background: linear-gradient(135deg, #059669, #10B981);
                    border-radius: 12px; padding: 20px 28px; margin-bottom: 28px;
                    color: white; display: flex; align-items: center; gap: 16px;">
            <div style="font-size: 2rem;">🔓</div>
            <div>
                <div style="font-size: 1.1rem; font-weight: 700;">Vault Unlocked</div>
                <div style="font-size: 0.88rem; opacity: 0.9;">
                    Your password is set for this session. You're ready to upload, query, and decrypt documents.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    # ── Password Card ────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="background: #FFFFFF; border-radius: 14px; padding: 28px 32px;
                    border: 2px solid #C7D2FE; box-shadow: 0 4px 16px rgba(79,70,229,0.08);
                    margin-bottom: 28px;">
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 4px;">
                <div style="background: #EEF2FF; width: 44px; height: 44px; border-radius: 50%;
                            display: flex; align-items: center; justify-content: center; font-size: 1.3rem;">🔐</div>
                <div>
                    <div style="font-size: 1.15rem; font-weight: 700; color: #1E293B;">
                        Create Your Vault Password
                    </div>
                    <div style="font-size: 0.82rem; color: #64748B;">
                        This password encrypts all your PII data. You'll need it for every task.
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Always show a clean "Create Password" form
    col_a, col_b = st.columns(2)
    with col_a:
        new_pass = st.text_input(
            "Create a password",
            type="password",
            placeholder="Min 8 characters",
            key="home_new_pass",
        )
    with col_b:
        confirm_pass = st.text_input(
            "Confirm password",
            type="password",
            placeholder="Re-enter password",
            key="home_confirm_pass",
        )

    if st.button("🔐 Set Password & Get Started", key="home_set_pass_btn", type="primary", use_container_width=True):
        if not new_pass or len(new_pass) < 8:
            st.warning("⚠️ Password must be at least 8 characters.")
        elif new_pass != confirm_pass:
            st.error("❌ Passwords don't match. Please try again.")
        else:
            # If an old vault exists, clear it and start fresh with the new password
            if vault_exists:
                try:
                    os.remove(vault_path)
                except OSError:
                    pass
                try:
                    client = chromadb.PersistentClient(path=Config.CHROMA_PERSIST_DIR)
                    client.delete_collection("vault_documents")
                except Exception:
                    pass

            st.session_state["_vault_password"] = new_pass
            st.session_state["_vault_authenticated"] = True
            st.success("✅ Password set! You're ready to upload documents.")
            st.cache_resource.clear()
            st.rerun()

    # If old vault data exists, show a subtle note
    if vault_exists:
        st.markdown(
            """
            <div style="background: #FFFBEB; border: 1px solid #FCD34D; border-radius: 10px;
                        padding: 12px 18px; margin-top: 12px; font-size: 0.84rem; color: #92400E;
                        line-height: 1.5;">
                ⚠️ <strong>Previous vault data found.</strong>
                Setting a new password will clear old encrypted data and start fresh.
                If you remember your old password, you can enter it here to keep your data.
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.expander("🔑 I remember my old password — unlock existing vault", expanded=False):
            old_pass = st.text_input(
                "Old vault password",
                type="password",
                placeholder="Enter your previous password",
                key="home_old_pass",
                label_visibility="collapsed",
            )
            if st.button("🔓 Unlock Existing Vault", key="home_unlock_old_btn", use_container_width=True):
                if not old_pass or len(old_pass) < 8:
                    st.warning("⚠️ Password must be at least 8 characters.")
                else:
                    try:
                        from services.encryption import VaultEncryption
                        enc = VaultEncryption()
                        with open(vault_path, "rb") as f:
                            enc.decrypt(f.read(), old_pass)
                        st.session_state["_vault_password"] = old_pass
                        st.session_state["_vault_authenticated"] = True
                        st.success("✅ Vault unlocked with your existing password!")
                        st.rerun()
                    except ValueError:
                        st.error("❌ That password doesn't match the vault. You can set a new password above instead.")

# ── How It Works ─────────────────────────────────────────────────────────────
st.markdown("### 🚀 How to Use Vault-AI")
st.markdown("")

cols = st.columns(3)

steps = [
    (
        "1",
        "📤 Set Password & Upload",
        "Set your vault password in the sidebar (just once). Then go to the <b>Upload</b> page and drop in your document. "
        "We'll scan it and replace all personal info with safe labels like <code>PERSON_001</code>.",
    ),
    (
        "2",
        "🔍 Ask Questions",
        "Go to the <b>Query</b> page and ask anything about your documents. "
        "You'll see answers with privacy labels. Hit <b>Decrypt</b> to reveal real names and details — only you can.",
    ),
    (
        "3",
        "🔒 Stay in Control",
        "Your vault password protects everything. Change it anytime from the sidebar. "
        "Without the password, no one — not even the system — can see your private data.",
    ),
]

for i, (num, title, desc) in enumerate(steps):
    with cols[i]:
        st.markdown(
            f"""
            <div class="step-card">
                <div class="step-number">{num}</div>
                <div class="step-title">{title}</div>
                <div class="step-desc">{desc}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("")

# ── What Gets Protected ─────────────────────────────────────────────────────
st.markdown("### 🛡️ What We Protect")

st.markdown(
    """
    <div class="privacy-box">
        <strong>Vault-AI automatically detects and masks:</strong><br>
        👤 <b>Names</b> — first, last, and full names<br>
        📧 <b>Emails</b> — personal and work email addresses<br>
        📱 <b>Phone Numbers</b> — mobile and landline<br>
        💳 <b>Financial Data</b> — credit cards, bank accounts, SSNs<br>
        📍 <b>Locations</b> — addresses, cities, countries<br>
        📅 <b>Dates</b> — birthdates, appointment dates<br>
        🆔 <b>IDs</b> — passport, driver's license, and more
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Quick Tips ───────────────────────────────────────────────────────────────
st.markdown("")
st.markdown("### 💡 Quick Tips")

st.markdown(
    """
    <div class="info-box">
        <b>🔑 Remember your password</b> — It's the only way to decrypt your data. We don't store it anywhere.<br><br>
        <b>📄 Supported files</b> — PDF, TXT, and Markdown (.md) files.<br><br>
        <b>🔒 Privacy first</b> — Your original text with personal info is never stored. Only the masked version is saved.
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Footer ───────────────────────────────────────────────────────────────────
st.markdown("")
st.divider()
st.markdown(
    '<div style="text-align: center; color: #94A3B8; font-size: 0.8rem;">'
    "Vault-AI — Privacy-Preserving Document Intelligence"
    "</div>",
    unsafe_allow_html=True,
)
