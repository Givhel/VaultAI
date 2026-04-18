"""
Query Page — Ask questions about uploaded documents.
Retrieves context from ChromaDB, generates answers via Groq/Llama-3.
Uses session password from sidebar for decryption.
"""

import sys
import os
import time
import re
import streamlit as st
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.vector_store import VectorStore
from services.llm_service import LLMService
from services.encryption import VaultEncryption
from services.tokenizer import PIITokenizer
from services.experiment_tracker import ExperimentTracker
from config import Config
from components import render_sidebar, get_session_password

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Query — Vault-AI", page_icon="🔍", layout="wide")
render_sidebar("query")

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container { padding-top: 2rem; max-width: 1100px; }

    .query-header {
        background: linear-gradient(135deg, #4F46E5, #7C3AED);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 1.8rem;
        font-weight: 800;
        margin-bottom: 4px;
    }
    .answer-card {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 24px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        margin: 16px 0;
    }
    .answer-label {
        font-size: 0.75rem;
        font-weight: 700;
        color: #4F46E5;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 8px;
    }
    .answer-text {
        font-size: 0.95rem;
        color: #1E293B;
        line-height: 1.7;
    }
    .source-card {
        background: #F8FAFC;
        border-radius: 8px;
        padding: 14px 18px;
        border: 1px solid #E2E8F0;
        margin-bottom: 8px;
        font-size: 0.85rem;
        color: #475569;
        line-height: 1.5;
    }
    .source-badge {
        display: inline-block;
        background: #EEF2FF;
        color: #4F46E5;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 700;
        margin-bottom: 6px;
    }
    .doc-badge {
        display: inline-block;
        background: #F0FDF4;
        color: #166534;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 700;
        margin-left: 6px;
    }
    .query-metric {
        background: #FFFFFF;
        border-radius: 10px;
        padding: 14px;
        border: 1px solid #E2E8F0;
        text-align: center;
    }
    .query-metric-val {
        font-size: 1.3rem;
        font-weight: 800;
        color: #4F46E5;
    }
    .query-metric-lbl {
        font-size: 0.7rem;
        color: #64748B;
        font-weight: 500;
    }
    .token-highlight {
        background: #FEF3C7;
        color: #92400E;
        padding: 1px 6px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.88rem;
        font-family: 'Inter', monospace;
    }
    .decrypted-highlight {
        background: #D1FAE5;
        color: #065F46;
        padding: 1px 6px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.88rem;
    }
    .decrypt-banner {
        background: #FFFBEB;
        border: 1px solid #FCD34D;
        border-radius: 10px;
        padding: 14px 20px;
        margin: 12px 0;
        font-size: 0.88rem;
        color: #92400E;
    }
    .decrypted-banner {
        background: #F0FDF4;
        border: 1px solid #86EFAC;
        border-radius: 10px;
        padding: 14px 20px;
        margin: 12px 0;
        font-size: 0.88rem;
        color: #166534;
    }
</style>
""", unsafe_allow_html=True)

# ── Helper: highlight tokens in text ─────────────────────────────────────────
TOKEN_PATTERN = re.compile(r'\b([A-Z_]+_\d{3})\b')

def highlight_tokens(text: str) -> str:
    def replace_token(match):
        token = match.group(1)
        return f'<span class="token-highlight">{token}</span>'
    return TOKEN_PATTERN.sub(replace_token, text)

def highlight_decrypted(text: str, token_mappings: dict) -> str:
    result = text
    for token, original in sorted(token_mappings.items(), key=lambda x: len(x[1]), reverse=True):
        if original in result:
            result = result.replace(
                original,
                f'<span class="decrypted-highlight">{original}</span>'
            )
    return result


# ── Initialize Services ─────────────────────────────────────────────────────
@st.cache_resource
def get_vector_store():
    return VectorStore()

@st.cache_resource
def get_llm_service():
    return LLMService()


# ── Page Content ─────────────────────────────────────────────────────────────
st.markdown('<div class="query-header">🔍 Query Documents</div>', unsafe_allow_html=True)
st.markdown(
    '<span style="color: #64748B;">Ask questions about your uploaded documents. '
    "Answers show safe labels by default — enter your vault password to decrypt and reveal real values.</span>",
    unsafe_allow_html=True,
)
st.markdown("")

# ── Check prerequisites ─────────────────────────────────────────────────────
vector_store = get_vector_store()
llm = get_llm_service()

if not vector_store.has_documents():
    st.markdown(
        """
        <div style="text-align: center; padding: 60px 20px; background: #FFFFFF;
                    border-radius: 12px; border: 2px dashed #CBD5E1;">
            <div style="font-size: 3rem; margin-bottom: 12px;">📭</div>
            <div style="font-size: 1.1rem; font-weight: 600; color: #1E293B; margin-bottom: 8px;">
                No documents uploaded yet
            </div>
            <div style="font-size: 0.9rem; color: #64748B;">
                Go to the Upload page to add documents before querying.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

if not llm.is_configured:
    st.warning(
        "⚠️ **Groq API key not configured.** "
        "Set `GROQ_API_KEY` in your `.env` file. "
        "Get a free key at [console.groq.com](https://console.groq.com)"
    )
    api_key_input = st.text_input("Or enter your Groq API key here:", type="password")
    if api_key_input:
        llm = LLMService(api_key=api_key_input)
    else:
        st.stop()

# ── Query Form ───────────────────────────────────────────────────────────────
query = st.text_area(
    "Your question",
    placeholder="e.g., What are the key findings in the report? Who is mentioned in the document?",
    height=80,
    label_visibility="collapsed",
)

# ── Initialize chat history ─────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ── Submit Query ─────────────────────────────────────────────────────────────
if st.button("🚀 Ask", type="primary", use_container_width=True):
    if not query.strip():
        st.warning("Please enter a question.")
        st.stop()

    start_time = time.time()

    with st.spinner("🔍 Searching documents and generating answer..."):
        try:
            results = vector_store.query(query)

            if not results["documents"] or not results["documents"][0]:
                st.warning("No relevant documents found. Try a different query.")
                st.stop()

            retrieved_chunks = results["documents"][0]
            distances = results["distances"][0] if results.get("distances") else []
            metadatas = results["metadatas"][0] if results.get("metadatas") else []

            context = "\n\n---\n\n".join(
                f"[Source {i+1}]: {chunk}" for i, chunk in enumerate(retrieved_chunks)
            )

            raw_answer = llm.generate(query, context)
            latency = time.time() - start_time

            try:
                tracker = ExperimentTracker()
                sims = [round(1 - d, 4) for d in distances] if distances else []
                tracker.log_query(
                    query_preview=query,
                    latency=latency,
                    num_results=len(retrieved_chunks),
                    similarity_scores=sims,
                )
            except Exception:
                pass

            source_docs = []
            for j, meta in enumerate(metadatas):
                source_docs.append({
                    "filename": meta.get("filename", "Unknown"),
                    "doc_id": meta.get("doc_id", "unknown"),
                    "chunk_index": meta.get("chunk_index", j),
                })

            st.session_state.chat_history.append({
                "query": query,
                "raw_answer": raw_answer,
                "decrypted_answer": None,
                "sources_tokenized": retrieved_chunks[:],
                "sources_decrypted": None,
                "source_docs": source_docs,
                "distances": distances,
                "latency": latency,
                "is_decrypted": False,
            })

            st.rerun()

        except ValueError as e:
            st.error(f"❌ {str(e)}")
        except ConnectionError as e:
            st.error(f"🌐 {str(e)}")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

# ── Display Chat History ─────────────────────────────────────────────────────
if st.session_state.chat_history:
    for idx, entry in enumerate(reversed(st.session_state.chat_history)):
        real_idx = len(st.session_state.chat_history) - 1 - idx

        # ── Question ─────────────────────────────────────────────────
        st.markdown(
            f"""
            <div style="background: #EEF2FF; border-radius: 10px; padding: 14px 18px;
                        margin-bottom: 8px; border: 1px solid #C7D2FE;">
                <div style="font-size: 0.72rem; font-weight: 700; color: #4F46E5;
                            text-transform: uppercase; letter-spacing: 0.05em;">Your Question</div>
                <div style="font-size: 0.95rem; color: #1E293B; margin-top: 4px;">{entry['query']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Answer (tokenized or decrypted) ──────────────────────────
        if entry["is_decrypted"] and entry["decrypted_answer"]:
            st.markdown(
                '<div class="decrypted-banner">'
                '🔓 <strong>Decrypted</strong> — Real values are highlighted in green below.'
                '</div>',
                unsafe_allow_html=True,
            )

            token_mappings = entry.get("decrypt_mappings", {})
            display_answer = highlight_decrypted(entry["decrypted_answer"], token_mappings)
            st.markdown(
                f"""
                <div class="answer-card">
                    <div class="answer-label">🤖 Vault-AI Answer (Decrypted)</div>
                    <div class="answer-text">{display_answer}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            # Show tokenized answer with inline decrypt option
            display_answer = highlight_tokens(entry["raw_answer"])
            st.markdown(
                f"""
                <div class="answer-card">
                    <div class="answer-label">🤖 Vault-AI Answer (Privacy Mode)</div>
                    <div class="answer-text">{display_answer}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # ── Inline Decrypt ────────────────────────────────────────
            vault_path = os.path.join(Config.VAULT_DATA_DIR, "vault.enc")
            if os.path.exists(vault_path):
                # Try auto-decrypt if session password exists
                vault_password = get_session_password()
                if vault_password and not entry["is_decrypted"]:
                    try:
                        encryptor = VaultEncryption()
                        with open(vault_path, "rb") as f:
                            vault_data = encryptor.decrypt(f.read(), vault_password)
                        token_mappings = vault_data.get("token_mappings", {})
                        if token_mappings:
                            tokenizer = PIITokenizer()
                            tokenizer.load_mappings(token_mappings)
                            decrypted_answer = tokenizer.detokenize(entry["raw_answer"], token_mappings)
                            decrypted_sources = [
                                tokenizer.detokenize(chunk, token_mappings)
                                for chunk in entry["sources_tokenized"]
                            ]
                            st.session_state.chat_history[real_idx]["decrypted_answer"] = decrypted_answer
                            st.session_state.chat_history[real_idx]["sources_decrypted"] = decrypted_sources
                            st.session_state.chat_history[real_idx]["is_decrypted"] = True
                            st.session_state.chat_history[real_idx]["decrypt_mappings"] = token_mappings
                            st.rerun()
                    except ValueError:
                        pass  # Password mismatch, show manual input

                # Show inline password input for decryption
                if not entry["is_decrypted"]:
                    st.markdown(
                        '<div style="background: #FFFBEB; border: 1px solid #FCD34D; border-radius: 10px; '
                        'padding: 12px 18px; margin: 8px 0; font-size: 0.85rem; color: #92400E;">'
                        '🔒 Personal info is shown as safe labels '
                        '(e.g. <span class="token-highlight">PERSON_001</span>). '
                        'Enter your password below to reveal real values.'
                        '</div>',
                        unsafe_allow_html=True,
                    )
                    dc1, dc2 = st.columns([3, 1])
                    with dc1:
                        decrypt_pass = st.text_input(
                            "Vault password",
                            type="password",
                            placeholder="Enter vault password to decrypt",
                            key=f"decrypt_pass_{real_idx}",
                            label_visibility="collapsed",
                        )
                    with dc2:
                        if st.button("🔓 Decrypt", key=f"decrypt_btn_{real_idx}", use_container_width=True):
                            if not decrypt_pass or len(decrypt_pass) < 8:
                                st.warning("⚠️ Min 8 characters")
                            else:
                                try:
                                    encryptor = VaultEncryption()
                                    with open(vault_path, "rb") as f:
                                        vault_data = encryptor.decrypt(f.read(), decrypt_pass)
                                    token_mappings = vault_data.get("token_mappings", {})
                                    if token_mappings:
                                        tokenizer = PIITokenizer()
                                        tokenizer.load_mappings(token_mappings)
                                        decrypted_answer = tokenizer.detokenize(entry["raw_answer"], token_mappings)
                                        decrypted_sources = [
                                            tokenizer.detokenize(chunk, token_mappings)
                                            for chunk in entry["sources_tokenized"]
                                        ]
                                        st.session_state.chat_history[real_idx]["decrypted_answer"] = decrypted_answer
                                        st.session_state.chat_history[real_idx]["sources_decrypted"] = decrypted_sources
                                        st.session_state.chat_history[real_idx]["is_decrypted"] = True
                                        st.session_state.chat_history[real_idx]["decrypt_mappings"] = token_mappings
                                        # Save password to session for convenience
                                        st.session_state["_vault_password"] = decrypt_pass
                                        st.session_state["_vault_authenticated"] = True
                                        st.rerun()
                                    else:
                                        st.warning("No token mappings found in vault.")
                                except ValueError:
                                    st.error("❌ Wrong password.")

        # ── Metrics Row ──────────────────────────────────────────────
        mc1, mc2, mc3, mc4 = st.columns(4)
        with mc1:
            st.markdown(
                f'<div class="query-metric"><div class="query-metric-val">{entry["latency"]:.1f}s</div>'
                f'<div class="query-metric-lbl">Response Time</div></div>',
                unsafe_allow_html=True,
            )
        with mc2:
            st.markdown(
                f'<div class="query-metric"><div class="query-metric-val">{len(entry["sources_tokenized"])}</div>'
                f'<div class="query-metric-lbl">Chunks Retrieved</div></div>',
                unsafe_allow_html=True,
            )
        with mc3:
            similarity = (1 - entry["distances"][0]) * 100 if entry["distances"] else 0
            st.markdown(
                f'<div class="query-metric"><div class="query-metric-val">{similarity:.0f}%</div>'
                f'<div class="query-metric-lbl">Top Similarity</div></div>',
                unsafe_allow_html=True,
            )
        with mc4:
            unique_docs = set()
            for sd in entry.get("source_docs", []):
                unique_docs.add(sd.get("filename", "Unknown"))
            st.markdown(
                f'<div class="query-metric"><div class="query-metric-val">{len(unique_docs)}</div>'
                f'<div class="query-metric-lbl">Source Documents</div></div>',
                unsafe_allow_html=True,
            )

        # ── Source Documents ─────────────────────────────────────────
        source_docs = entry.get("source_docs", [])
        unique_filenames = set(sd.get('filename', '?') for sd in source_docs)
        num_sources = len(entry["sources_tokenized"])

        with st.expander(f"📚 Source Chunks ({num_sources} chunks from {len(unique_filenames)} document(s))", expanded=False):
            if entry["is_decrypted"]:
                show_sources = entry.get("sources_decrypted", entry["sources_tokenized"])
                for j, source in enumerate(show_sources):
                    distance = entry["distances"][j] if j < len(entry["distances"]) else None
                    score_text = f" · Similarity: {(1-distance)*100:.0f}%" if distance is not None else ""
                    doc_info = source_docs[j] if j < len(source_docs) else {}
                    filename = doc_info.get("filename", "Unknown")
                    chunk_idx = doc_info.get("chunk_index", "?")

                    display_source = highlight_decrypted(source[:500], entry.get("decrypt_mappings", {}))
                    st.markdown(
                        f'<div class="source-card">'
                        f'<span class="source-badge">SOURCE {j+1}{score_text}</span>'
                        f'<span class="doc-badge">📄 {filename} · chunk {chunk_idx}</span>'
                        f'<br><br>{display_source}{"..." if len(source) > 500 else ""}</div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(
                    '<div style="background: #FFFBEB; border-radius: 8px; padding: 10px 14px; '
                    'margin-bottom: 12px; font-size: 0.82rem; color: #92400E; border: 1px solid #FCD34D;">'
                    '🔒 Source text is hidden for privacy. Use the Decrypt button above to reveal.'
                    '</div>',
                    unsafe_allow_html=True,
                )
                for j in range(num_sources):
                    distance = entry["distances"][j] if j < len(entry["distances"]) else None
                    score_text = f" · Similarity: {(1-distance)*100:.0f}%" if distance is not None else ""
                    doc_info = source_docs[j] if j < len(source_docs) else {}
                    filename = doc_info.get("filename", "Unknown")
                    chunk_idx = doc_info.get("chunk_index", "?")

                    st.markdown(
                        f'<div class="source-card">'
                        f'<span class="source-badge">SOURCE {j+1}{score_text}</span>'
                        f'<span class="doc-badge">📄 {filename} · chunk {chunk_idx}</span>'
                        f'<br><br>'
                        f'<span style="color: #94A3B8; font-style: italic;">'
                        f'Content encrypted — decrypt above to view</span></div>',
                        unsafe_allow_html=True,
                    )

        st.divider()

    if st.button("🗑️ Clear Chat History", key="clear_chat"):
        st.session_state.chat_history = []
        st.rerun()
