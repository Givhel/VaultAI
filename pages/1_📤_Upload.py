"""
Upload Page — Process documents through the privacy pipeline.
Phase 1: Detect PII & preview tokenized text (NO password needed).
Phase 2: Encrypt vault & store in ChromaDB (uses session password from sidebar).
Real PII values are NEVER shown — only token labels like PERSON_001.
"""

import sys
import os
import time
import json
import hashlib
import streamlit as st
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.pii_detector import PIIDetector
from services.tokenizer import PIITokenizer
from services.encryption import VaultEncryption
from services.differential_privacy import DifferentialPrivacy
from services.document_processor import DocumentProcessor
from services.vector_store import VectorStore
from services.experiment_tracker import ExperimentTracker
from config import Config
import numpy as np
from components import render_sidebar, get_session_password

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Upload — Vault-AI", page_icon="📤", layout="wide")
render_sidebar("upload")

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container { padding-top: 2rem; max-width: 1100px; }

    .upload-header {
        background: linear-gradient(135deg, #4F46E5, #7C3AED);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 1.8rem;
        font-weight: 800;
        margin-bottom: 4px;
    }
    .entity-chip {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
        margin: 3px;
    }
    .entity-PERSON { background: #DBEAFE; color: #1D4ED8; }
    .entity-EMAIL_ADDRESS { background: #FCE7F3; color: #BE185D; }
    .entity-PHONE_NUMBER { background: #D1FAE5; color: #047857; }
    .entity-CREDIT_CARD { background: #FEE2E2; color: #B91C1C; }
    .entity-LOCATION { background: #FEF3C7; color: #92400E; }
    .entity-DATE_TIME { background: #E0E7FF; color: #3730A3; }
    .entity-default { background: #F1F5F9; color: #475569; }

    .result-card {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        margin-bottom: 16px;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 800;
        color: #4F46E5;
    }
    .metric-label {
        font-size: 0.8rem;
        color: #64748B;
        font-weight: 500;
    }
    .success-banner {
        background: linear-gradient(135deg, #059669, #10B981);
        color: white;
        padding: 16px 24px;
        border-radius: 10px;
        font-weight: 600;
        margin: 16px 0;
    }
    .phase-banner {
        background: #EEF2FF;
        border: 1px solid #C7D2FE;
        border-radius: 10px;
        padding: 14px 20px;
        margin: 12px 0;
        font-size: 0.88rem;
        color: #4338CA;
    }
    .info-banner {
        background: #FFFBEB;
        border: 1px solid #FCD34D;
        border-radius: 10px;
        padding: 14px 20px;
        margin: 12px 0;
        font-size: 0.88rem;
        color: #92400E;
    }
</style>
""", unsafe_allow_html=True)


# ── Initialize Services (cached) ────────────────────────────────────────────
@st.cache_resource
def get_pii_detector():
    return PIIDetector()

@st.cache_resource
def get_vector_store():
    return VectorStore()

def get_entity_chip(entity_type: str, token_label: str) -> str:
    """Generate colored chip HTML for an entity (shows token label, not real value)."""
    css_class = f"entity-{entity_type}" if entity_type in [
        "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "LOCATION", "DATE_TIME"
    ] else "entity-default"
    return f'<span class="entity-chip {css_class}">{token_label}</span>'


# ── Page Content ─────────────────────────────────────────────────────────────
st.markdown('<div class="upload-header">📤 Upload Document</div>', unsafe_allow_html=True)
st.markdown(
    '<span style="color: #64748B;">Upload a document to detect and mask personal information. '
    'Enter your vault password after processing to encrypt and store.</span>',
    unsafe_allow_html=True,
)
st.markdown("")

# ── Upload Form ──────────────────────────────────────────────────────────────
uploaded_file = st.file_uploader(
    "Choose a document",
    type=["pdf", "txt", "md"],
    help="Supported formats: PDF, TXT, Markdown",
)

# ════════════════════════════════════════════════════════════════════════════
# PHASE 1: Detect & Preview PII (NO password needed)
# ════════════════════════════════════════════════════════════════════════════
if uploaded_file:
    # Check if we already processed this file (avoid reprocessing on every rerun)
    file_key = f"{uploaded_file.name}_{uploaded_file.size}"

    if st.session_state.get("_processed_file_key") != file_key:
        # Clear previous results when a new file is uploaded
        for key in ["_processed_file_key", "_processed_text", "_processed_entities",
                     "_processed_tokenized", "_processed_mappings", "_processed_stats",
                     "_processed_doc_stats", "_vault_stored"]:
            st.session_state.pop(key, None)

    # Phase 1 button
    if "_processed_text" not in st.session_state or st.session_state.get("_processed_file_key") != file_key:
        if st.button("🔍 Detect & Preview PII", type="primary", use_container_width=True):
            progress = st.progress(0, text="Initializing pipeline...")

            try:
                # ── Step 1: Extract text ─────────────────────────────────
                progress.progress(15, text="📄 Extracting text from document...")
                processor = DocumentProcessor()
                file_bytes = uploaded_file.read()
                text = processor.extract_text(file_bytes, uploaded_file.name)
                doc_stats = processor.get_document_stats(text)

                if not text.strip():
                    st.error("❌ Could not extract text from the document.")
                    st.stop()

                # ── Step 2: Detect PII ───────────────────────────────────
                progress.progress(40, text="🔍 Detecting personal information...")
                detector = get_pii_detector()
                entities = detector.detect(text)
                entity_summary = detector.get_entity_summary(entities)

                # ── Step 3: Tokenize ─────────────────────────────────────
                progress.progress(70, text="🔄 Replacing PII with safe labels...")
                tokenizer = PIITokenizer()
                tokenized_text, new_mappings = tokenizer.tokenize(text, entities)

                progress.progress(100, text="✅ Done! Personal info detected and masked.")
                time.sleep(0.5)
                progress.empty()

                # Save to session state for Phase 2
                st.session_state["_processed_file_key"] = file_key
                st.session_state["_processed_text"] = text
                st.session_state["_processed_entities"] = entities
                st.session_state["_processed_tokenized"] = tokenized_text
                st.session_state["_processed_mappings"] = new_mappings
                st.session_state["_processed_stats"] = entity_summary
                st.session_state["_processed_doc_stats"] = doc_stats
                st.session_state["_vault_stored"] = False

                st.rerun()

            except Exception as e:
                progress.empty()
                st.error(f"❌ Error: {str(e)}")

    # ── Show Preview Results (if processed) ──────────────────────────────────
    if "_processed_text" in st.session_state and st.session_state.get("_processed_file_key") == file_key:
        entities = st.session_state["_processed_entities"]
        tokenized_text = st.session_state["_processed_tokenized"]
        new_mappings = st.session_state["_processed_mappings"]
        doc_stats = st.session_state["_processed_doc_stats"]

        st.markdown(
            '<div class="phase-banner">'
            '🔍 <strong>Preview</strong> — Personal info has been detected and replaced with safe labels '
            '(e.g. <code>PERSON_001</code>). No real data is shown.'
            '</div>',
            unsafe_allow_html=True,
        )

        # Metrics row
        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(
                f'<div class="result-card"><div class="metric-value">{len(entities)}</div>'
                f'<div class="metric-label">PII Items Found</div></div>',
                unsafe_allow_html=True,
            )
        with m2:
            st.markdown(
                f'<div class="result-card"><div class="metric-value">{len(new_mappings)}</div>'
                f'<div class="metric-label">Unique Labels</div></div>',
                unsafe_allow_html=True,
            )
        with m3:
            st.markdown(
                f'<div class="result-card"><div class="metric-value">{doc_stats["word_count"]}</div>'
                f'<div class="metric-label">Words</div></div>',
                unsafe_allow_html=True,
            )

        # Detected entities (show token labels instead of real values)
        if entities:
            st.markdown("#### 🔍 Detected PII")
            original_to_token = {v: k for k, v in new_mappings.items()}

            chips = []
            for e in entities:
                token_label = original_to_token.get(e["text"], e["type"])
                chips.append(get_entity_chip(e["type"], token_label))
            st.markdown(f"<div>{' '.join(chips)}</div>", unsafe_allow_html=True)
            st.markdown("")

            # Entity table — shows token labels, NOT real values
            with st.expander("View entity details", expanded=False):
                import pandas as pd
                rows = []
                for e in entities:
                    token_label = original_to_token.get(e["text"], e["type"])
                    rows.append({
                        "Entity Type": e["type"],
                        "Token Label": token_label,
                        "Confidence": e["score"],
                    })
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True, hide_index=True)

        # Tokenized preview
        st.markdown("#### 🔄 Masked Text Preview")
        with st.expander("View masked text", expanded=False):
            st.code(tokenized_text[:2000] + ("..." if len(tokenized_text) > 2000 else ""), language=None)

        # Token mapping — show only token labels, no real values
        if new_mappings:
            st.markdown("#### 🗺️ Label Mapping")
            st.markdown(
                '<div class="info-banner">'
                '🔒 Real values are hidden. They will be encrypted in your vault. '
                'Only safe labels are shown here.'
                '</div>',
                unsafe_allow_html=True,
            )
            with st.expander("View labels", expanded=False):
                for token in new_mappings.keys():
                    parts = token.rsplit("_", 1)
                    entity_type = parts[0] if len(parts) == 2 else "UNKNOWN"
                    st.markdown(f"- `{token}` → *{entity_type} value (encrypted in vault)*")

        # ════════════════════════════════════════════════════════════════
        # PHASE 2: Encrypt & Store (inline password entry)
        # ════════════════════════════════════════════════════════════════
        if not st.session_state.get("_vault_stored"):
            st.markdown("---")
            st.markdown(
                '<div style="background: #EEF2FF; border: 1px solid #C7D2FE; border-radius: 10px; '
                'padding: 14px 20px; margin-bottom: 16px; font-size: 0.88rem; color: #4338CA;">'
                '🔐 <strong>Enter your vault password</strong> to encrypt and store this document securely.'
                '</div>',
                unsafe_allow_html=True,
            )

            # Use session password if already set, otherwise ask for it
            vault_password = get_session_password()

            if not vault_password:
                vault_password_input = st.text_input(
                    "Vault password",
                    type="password",
                    placeholder="Enter your vault password",
                    key="upload_vault_pass",
                    label_visibility="collapsed",
                )
            else:
                vault_password_input = vault_password

            if st.button("🔐 Encrypt & Store in Vault", type="primary", use_container_width=True):
                # Validate password
                if not vault_password and (not vault_password_input or len(vault_password_input) < 8):
                    st.warning("⚠️ Please enter a password (min 8 characters). Set one on the **Home** page first.")
                    st.stop()

                use_password = vault_password_input
                start_time = time.time()
                progress = st.progress(0, text="Encrypting and storing...")
                epsilon = Config.DP_EPSILON  # Use default from config

                try:
                    text = st.session_state["_processed_text"]
                    tokenized_text = st.session_state["_processed_tokenized"]
                    entities = st.session_state["_processed_entities"]
                    new_mappings = st.session_state["_processed_mappings"]
                    doc_stats = st.session_state["_processed_doc_stats"]

                    # ── Step 1: Load existing vault & merge ──────────────
                    progress.progress(10, text="🔐 Loading existing vault...")
                    vault_dir = Config.VAULT_DATA_DIR
                    vault_path = os.path.join(vault_dir, "vault.enc")
                    encryptor = VaultEncryption()

                    tokenizer = PIITokenizer()
                    existing_mappings = {}
                    if os.path.exists(vault_path):
                        try:
                            with open(vault_path, "rb") as f:
                                existing_mappings = encryptor.decrypt(f.read(), use_password)
                            tokenizer.load_mappings(existing_mappings.get("token_mappings", {}))
                        except ValueError:
                            st.error("❌ Wrong password. The password doesn't match your existing vault.")
                            progress.empty()
                            st.stop()

                    # Save password to session for convenience
                    st.session_state["_vault_password"] = use_password
                    st.session_state["_vault_authenticated"] = True

                    # Re-tokenize with existing mappings for consistency
                    tokenizer_final = PIITokenizer()
                    if existing_mappings.get("token_mappings"):
                        tokenizer_final.load_mappings(existing_mappings["token_mappings"])
                    tokenized_text_final, new_mappings_final = tokenizer_final.tokenize(text, entities)

                    # ── Step 2: Encrypt vault ────────────────────────────
                    progress.progress(30, text="🔐 Encrypting vault...")
                    all_mappings = tokenizer_final.get_all_mappings()

                    vault_data = {
                        "token_mappings": all_mappings,
                        "documents": existing_mappings.get("documents", {}),
                        "metadata": {
                            "total_entities": len(all_mappings),
                            "epsilon": epsilon,
                        },
                    }

                    doc_id = hashlib.sha256(f"{uploaded_file.name}_{time.time()}".encode()).hexdigest()[:12]
                    vault_data["documents"][doc_id] = {
                        "filename": uploaded_file.name,
                        "uploaded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "entities_count": len(new_mappings_final),
                        "word_count": doc_stats["word_count"],
                    }

                    os.makedirs(vault_dir, exist_ok=True)
                    encrypted_vault = encryptor.encrypt(vault_data, use_password)
                    with open(vault_path, "wb") as f:
                        f.write(encrypted_vault)

                    # ── Step 3: Chunk text ───────────────────────────────
                    progress.progress(50, text="✂️ Chunking text...")
                    processor = DocumentProcessor()
                    chunks = processor.chunk_text(tokenized_text_final)

                    # ── Step 4: Embed + DP noise ─────────────────────────
                    progress.progress(65, text="🧠 Generating embeddings...")
                    vector_store = get_vector_store()
                    raw_embeddings = vector_store.generate_embeddings(chunks)

                    dp = DifferentialPrivacy(epsilon=epsilon)
                    noisy_embeddings = [dp.add_noise(emb).tolist() for emb in raw_embeddings]

                    # ── Step 5: Store in ChromaDB ────────────────────────
                    progress.progress(80, text="💾 Storing securely...")
                    vector_store.add_documents(
                        doc_id=doc_id,
                        chunks=chunks,
                        embeddings=noisy_embeddings,
                        metadata={"filename": uploaded_file.name},
                    )

                    # ── Step 6: Log to MLflow ────────────────────────────
                    progress.progress(90, text="📊 Logging metrics...")
                    processing_time = time.time() - start_time
                    try:
                        tracker = ExperimentTracker()
                        tracker.log_upload(
                            doc_name=uploaded_file.name,
                            num_entities=len(entities),
                            processing_time=processing_time,
                            num_chunks=len(chunks),
                            epsilon=epsilon,
                            doc_stats=doc_stats,
                            entity_scores=[e["score"] for e in entities],
                            embedding_model=Config.EMBEDDING_MODEL,
                        )
                    except Exception:
                        pass

                    progress.progress(100, text="✅ Complete!")
                    time.sleep(0.5)
                    progress.empty()

                    st.session_state["_vault_stored"] = True

                    st.markdown(
                        '<div class="success-banner">'
                        f"✅ Document encrypted and stored successfully in {processing_time:.1f}s"
                        "</div>",
                        unsafe_allow_html=True,
                    )

                    s1, s2 = st.columns(2)
                    with s1:
                        st.markdown(
                            f'<div class="result-card"><div class="metric-value">{len(chunks)}</div>'
                            f'<div class="metric-label">Chunks Stored</div></div>',
                            unsafe_allow_html=True,
                        )
                    with s2:
                        st.markdown(
                            f'<div class="result-card"><div class="metric-value">AES-256</div>'
                            f'<div class="metric-label">Encryption</div></div>',
                            unsafe_allow_html=True,
                        )

                except Exception as e:
                    progress.empty()
                    st.error(f"❌ Error: {str(e)}")
        else:
            st.markdown("---")
            st.markdown(
                '<div class="success-banner">'
                "✅ Document has been encrypted and stored in the vault."
                "</div>",
                unsafe_allow_html=True,
            )
            st.info("📄 Upload a new document or go to the **Query** page to ask questions.")

elif not uploaded_file:
    st.markdown("")
    st.markdown(
        """
        <div style="text-align: center; padding: 60px 20px; background: #FFFFFF;
                    border-radius: 12px; border: 2px dashed #CBD5E1;">
            <div style="font-size: 3rem; margin-bottom: 12px;">📄</div>
            <div style="font-size: 1.1rem; font-weight: 600; color: #1E293B; margin-bottom: 8px;">
                Drop your document here
            </div>
            <div style="font-size: 0.9rem; color: #64748B;">
                Supports PDF, TXT, and Markdown files
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
