"""
Shared sidebar component for all pages.
Shows password management, uploaded documents list, and clear data action.
"""

import streamlit as st
import os
import chromadb
from config import Config


def get_uploaded_documents() -> dict[str, int]:
    """
    Get document filenames and chunk counts from ChromaDB.
    Lightweight — does NOT load the embedding model.
    """
    try:
        persist_dir = Config.CHROMA_PERSIST_DIR
        if not os.path.exists(persist_dir):
            return {}
        client = chromadb.PersistentClient(path=persist_dir)
        try:
            collection = client.get_collection("vault_documents")
        except Exception:
            return {}

        if collection.count() == 0:
            return {}

        all_data = collection.get(include=["metadatas"])
        filenames: dict[str, int] = {}
        for meta in all_data.get("metadatas", []):
            if meta and "filename" in meta:
                fname = meta["filename"]
                filenames[fname] = filenames.get(fname, 0) + 1
        return filenames
    except Exception:
        return {}


def _vault_exists() -> bool:
    """Check if an encrypted vault file exists."""
    vault_path = os.path.join(Config.VAULT_DATA_DIR, "vault.enc")
    return os.path.exists(vault_path)


def _verify_password(password: str) -> bool:
    """Verify that a password can decrypt the existing vault."""
    vault_path = os.path.join(Config.VAULT_DATA_DIR, "vault.enc")
    if not os.path.exists(vault_path):
        return False
    try:
        from services.encryption import VaultEncryption
        enc = VaultEncryption()
        with open(vault_path, "rb") as f:
            enc.decrypt(f.read(), password)
        return True
    except ValueError:
        return False


def get_session_password() -> str | None:
    """Get the current session password (None if not set/authenticated)."""
    return st.session_state.get("_vault_password")


def render_sidebar(page_id: str = "home"):
    """
    Render the shared sidebar with password management, uploaded documents, and clear data.
    """
    with st.sidebar:
        st.markdown("### 🛡️ Vault-AI")
        st.markdown(
            '<span style="color: #64748B; font-size: 0.82rem;">'
            "Privacy-Preserving Document Intelligence"
            "</span>",
            unsafe_allow_html=True,
        )
        st.divider()

        # ── Password Status ────────────────────────────────────────
        vault_exists = _vault_exists()
        is_authenticated = st.session_state.get("_vault_authenticated", False)

        if is_authenticated and st.session_state.get("_vault_password"):
            # ── Authenticated state ──────────────────────────────────
            st.markdown(
                '<div style="background: #F0FDF4; border-radius: 8px; padding: 10px 14px; '
                'border: 1px solid #86EFAC; margin-bottom: 12px;">'
                '<div style="font-size: 0.82rem; color: #166534; font-weight: 600;">'
                '🔓 Vault Unlocked</div>'
                '<div style="font-size: 0.72rem; color: #15803D; margin-top: 2px;">'
                'Password is set for this session</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            if st.button("🔒 Lock Vault", key=f"sb_lock_{page_id}", use_container_width=True):
                st.session_state["_vault_password"] = None
                st.session_state["_vault_authenticated"] = False
                st.rerun()
        else:
            st.markdown(
                '<div style="background: #FEF2F2; border-radius: 8px; padding: 10px 14px; '
                'border: 1px solid #FECACA; margin-bottom: 12px;">'
                '<div style="font-size: 0.82rem; color: #991B1B; font-weight: 600;">'
                '🔒 Vault Locked</div>'
                '<div style="font-size: 0.72rem; color: #B91C1C; margin-top: 2px;">'
                'Set your password on the Home page</div>'
                '</div>',
                unsafe_allow_html=True,
            )

        st.divider()

        # ── Uploaded Documents ───────────────────────────────────────
        st.markdown("**📄 Uploaded Documents**")
        docs = get_uploaded_documents()
        if docs:
            for fname, chunk_count in docs.items():
                st.markdown(
                    f'<div style="background: #FFFFFF; border-radius: 8px; padding: 8px 12px; '
                    f'margin-bottom: 6px; border: 1px solid #E2E8F0; font-size: 0.82rem;">'
                    f'<div style="font-weight: 600; color: #1E293B;">📄 {fname}</div>'
                    f'<div style="color: #64748B; font-size: 0.72rem;">{chunk_count} chunks indexed</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            st.caption(f"{len(docs)} document(s) · {sum(docs.values())} total chunks")
        else:
            st.markdown(
                '<div style="text-align: center; padding: 16px; color: #94A3B8; font-size: 0.82rem;">'
                "No documents uploaded yet"
                "</div>",
                unsafe_allow_html=True,
            )

        st.divider()

        # ── Clear Data ───────────────────────────────────────────────
        with st.expander("🗑️ Clear All Data", expanded=False):
            st.warning("This will permanently delete everything.")
            if is_authenticated:
                if st.button("🗑️ Confirm Clear", key=f"sb_clear_btn_{page_id}", use_container_width=True):
                    vault_path = os.path.join(Config.VAULT_DATA_DIR, "vault.enc")
                    if os.path.exists(vault_path):
                        os.remove(vault_path)
                    try:
                        client = chromadb.PersistentClient(path=Config.CHROMA_PERSIST_DIR)
                        client.delete_collection("vault_documents")
                    except Exception:
                        pass
                    try:
                        import shutil
                        mlruns = os.path.abspath("./mlruns")
                        if os.path.exists(mlruns):
                            shutil.rmtree(mlruns)
                    except Exception:
                        pass
                    st.session_state["_vault_password"] = None
                    st.session_state["_vault_authenticated"] = False
                    st.success("✅ All data cleared")
                    st.cache_resource.clear()
                    st.rerun()
            else:
                st.info("🔐 Unlock vault first to clear data.")

        st.divider()

        # ── Footer ───────────────────────────────────────────────────
        st.markdown(
            '<span style="color: #94A3B8; font-size: 0.7rem;">'
            "Built with Presidio · AES-256 · Llama-3 · ChromaDB"
            "</span>",
            unsafe_allow_html=True,
        )
