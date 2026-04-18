"""
Vault Page — View vault statistics, encrypted documents, and manage vault.
Uses session password from sidebar for authentication.
"""

import sys
import os
import streamlit as st
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.encryption import VaultEncryption
from services.vector_store import VectorStore
from config import Config
import plotly.graph_objects as go
from components import render_sidebar, get_session_password

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Vault — Vault-AI", page_icon="🔒", layout="wide")
render_sidebar("vault")

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container { padding-top: 2rem; max-width: 1100px; }

    .vault-header {
        background: linear-gradient(135deg, #4F46E5, #7C3AED);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 1.8rem;
        font-weight: 800;
        margin-bottom: 4px;
    }
    .stat-card {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 24px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        text-align: center;
    }
    .stat-value {
        font-size: 2rem;
        font-weight: 800;
        color: #4F46E5;
    }
    .stat-label {
        font-size: 0.8rem;
        color: #64748B;
        font-weight: 500;
        margin-top: 4px;
    }
    .doc-row {
        background: #FFFFFF;
        border-radius: 10px;
        padding: 16px 20px;
        border: 1px solid #E2E8F0;
        margin-bottom: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .doc-name {
        font-weight: 600;
        color: #1E293B;
        font-size: 0.95rem;
    }
    .doc-meta {
        font-size: 0.8rem;
        color: #64748B;
    }
    .vault-locked {
        text-align: center;
        padding: 60px 20px;
        background: #FFFFFF;
        border-radius: 12px;
        border: 2px dashed #CBD5E1;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_vector_store():
    return VectorStore()


# ── Page Content ─────────────────────────────────────────────────────────────
st.markdown('<div class="vault-header">🔒 Encrypted Vault</div>', unsafe_allow_html=True)
st.markdown(
    '<span style="color: #64748B;">View your vault statistics and uploaded documents. '
    'Set your password on the Home page to see details.</span>',
    unsafe_allow_html=True,
)
st.markdown("")

# ── Check vault existence ────────────────────────────────────────────────────
vault_path = os.path.join(Config.VAULT_DATA_DIR, "vault.enc")
vector_store = get_vector_store()
vs_stats = vector_store.get_stats()

if not os.path.exists(vault_path):
    st.markdown(
        """
        <div class="vault-locked">
            <div style="font-size: 3rem; margin-bottom: 12px;">🔐</div>
            <div style="font-size: 1.1rem; font-weight: 600; color: #1E293B; margin-bottom: 8px;">
                Vault is empty
            </div>
            <div style="font-size: 0.9rem; color: #64748B;">
                Upload a document to initialize the encrypted vault.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

# ── Check session password ───────────────────────────────────────────────────
vault_password = get_session_password()

if not vault_password:
    # Show basic stats (no decryption needed)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            f'<div class="stat-card"><div class="stat-value">{vs_stats["total_chunks"]}</div>'
            f'<div class="stat-label">Vector Chunks Stored</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        vault_size = os.path.getsize(vault_path)
        size_str = f"{vault_size / 1024:.1f} KB" if vault_size > 1024 else f"{vault_size} B"
        st.markdown(
            f'<div class="stat-card"><div class="stat-value">{size_str}</div>'
            f'<div class="stat-label">Encrypted Vault Size</div></div>',
            unsafe_allow_html=True,
        )

    st.info("🔐 Set your password on the **Home** page to view detailed statistics.")
    st.stop()

# ── Decrypt and show vault details ───────────────────────────────────────────
try:
    encryptor = VaultEncryption()
    with open(vault_path, "rb") as f:
        vault_data = encryptor.decrypt(f.read(), vault_password)
except ValueError:
    st.error("❌ Session password doesn't match the vault. Please set the correct password on the Home page.")
    st.stop()

token_mappings = vault_data.get("token_mappings", {})
documents = vault_data.get("documents", {})
metadata = vault_data.get("metadata", {})

# ── Stats Cards ──────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(
        f'<div class="stat-card"><div class="stat-value">{len(documents)}</div>'
        f'<div class="stat-label">Documents</div></div>',
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        f'<div class="stat-card"><div class="stat-value">{len(token_mappings)}</div>'
        f'<div class="stat-label">PII Tokens</div></div>',
        unsafe_allow_html=True,
    )
with c3:
    st.markdown(
        f'<div class="stat-card"><div class="stat-value">{vs_stats["total_chunks"]}</div>'
        f'<div class="stat-label">Vector Chunks</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("")

# ── Entity Type Breakdown ────────────────────────────────────────────────────
if token_mappings:
    st.markdown("#### 📊 Entity Type Breakdown")

    entity_counts = {}
    for token in token_mappings.keys():
        parts = token.rsplit("_", 1)
        if len(parts) == 2:
            entity_type = parts[0]
            entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1

    if entity_counts:
        col_chart, col_table = st.columns([1, 1])

        with col_chart:
            colors = ["#4F46E5", "#7C3AED", "#059669", "#D97706", "#DC2626",
                       "#0891B2", "#BE185D", "#6D28D9"]
            fig = go.Figure(data=[go.Pie(
                labels=list(entity_counts.keys()),
                values=list(entity_counts.values()),
                hole=0.55,
                marker=dict(colors=colors[:len(entity_counts)]),
                textfont=dict(size=12, family="Inter"),
            )])
            fig.update_layout(
                showlegend=True,
                legend=dict(font=dict(size=11, family="Inter")),
                margin=dict(t=20, b=20, l=20, r=20),
                height=300,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_table:
            import pandas as pd
            df = pd.DataFrame([
                {"Entity Type": k, "Count": v, "Percentage": f"{v/len(token_mappings)*100:.1f}%"}
                for k, v in sorted(entity_counts.items(), key=lambda x: -x[1])
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)

# ── Documents List ───────────────────────────────────────────────────────────
st.markdown("")
st.markdown("#### 📄 Uploaded Documents")

if documents:
    for doc_id, doc_info in documents.items():
        st.markdown(
            f"""
            <div class="doc-row">
                <div>
                    <div class="doc-name">📄 {doc_info.get('filename', 'Unknown')}</div>
                    <div class="doc-meta">
                        {doc_info.get('uploaded_at', 'N/A')} · 
                        {doc_info.get('entities_count', 0)} entities · 
                        {doc_info.get('word_count', 0)} words
                    </div>
                </div>
                <div style="font-size: 0.75rem; color: #94A3B8; font-family: monospace;">
                    ID: {doc_id}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
else:
    st.info("No documents in vault.")
