"""Live side-by-side OCI compaction chatbot. Launch with ./start.sh."""
import hashlib
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from chat_flow import chat_turn, new_branch
from comparison import compare_answers
from compaction_demo import TRIP
from ui_demo import build_history

load_dotenv()
st.set_page_config(page_title="OCI compaction chat", page_icon="💬", layout="wide")
st.title("Does compaction help?")
st.write("Ask one question. Compare two live OCI answers.")
st.caption("Without compaction: send the full chat each time. With compaction: reuse a smaller context. "
           "The potential benefit is fewer input tokens on later questions. Faster answers are not guaranteed.")

with st.sidebar:
    st.header("Live OCI")
    with st.expander("OCI connection", expanded=False):
        region = st.text_input("OCI region", os.getenv("OCI_REGION", "us-chicago-1"))
        base_url = st.text_input("OCI base URL", os.getenv("OCI_BASE_URL", ""),
                                 placeholder="Leave blank to use the region")
        model = st.text_input("Model ID or model endpoint OCID", os.getenv("OCI_MODEL") or os.getenv("OCI_MODEL_ID", ""))
        project = st.text_input("Generative AI project OCID", os.getenv("OCI_OPENAI_PROJECT") or os.getenv("OCI_GENAI_PROJECT_ID", ""))
        api_key = st.text_input("OCI Generative AI API key", os.getenv("OCI_GENAI_API_KEY", ""), type="password")
    with st.expander("Advanced settings", expanded=False):
        threshold = st.number_input("Compaction threshold (tokens)", min_value=1000, value=1000, step=500)
        max_output = st.number_input("Maximum output tokens per answer", min_value=128, value=1024, step=128)
    with st.expander("Starting context", expanded=False):
        facts = st.text_area("Facts both chats should remember", TRIP, height=160)
        exchanges = st.slider("Synthetic travel exchanges for a longer test", 0, 60, 0)
        st.caption("Optional synthetic history is sent to both chats. Set to 0 for a normal conversation.")
    reset = st.button("New conversation", width="stretch")
    retry = st.button("Retry compaction next turn", width="stretch")
    st.caption("Each question normally makes two live calls. Recovery can add calls. "
               "Changing the model, connection, starting context or token settings starts a new comparison.")

endpoint = base_url.strip() or f"https://inference.generativeai.{region.strip()}.oci.oraclecloud.com/openai/v1"
# A fingerprint invalidates sessions on credential changes without storing a second copy of the key.
fingerprint = hashlib.sha256(api_key.encode()).hexdigest()
signature = (endpoint, model, project, fingerprint, facts, exchanges, threshold, max_output)
if reset or st.session_state.get("chat_signature") != signature:
    seed = build_history(facts, exchanges)[:-1] if facts.strip() or exchanges else []
    st.session_state.chat_branches = {name: new_branch(seed) for name in ("OFF", "ON")}
    st.session_state.chat_turns = []
    st.session_state.chat_signature = signature
if retry:
    st.session_state.chat_branches["ON"]["paused"] = False
    st.info("Automatic compaction will be attempted on your next question.")

prompt = st.chat_input("Ask both chats a question…", key="paired_prompt")
if prompt and prompt.strip():
    if not all((model.strip(), project.strip(), api_key.strip())):
        st.error("Enter your model, project OCID and API key in the sidebar.")
    elif not endpoint.rstrip("/").endswith("/openai/v1"):
        st.error("The OCI base URL must end in /openai/v1.")
    else:
        turn = {"prompt": prompt, "results": {}}
        # Alternate order to reduce a consistent first-call advantage. Timings
        # measure each request independently, excluding time waiting for the other.
        order = ("OFF", "ON") if len(st.session_state.chat_turns) % 2 == 0 else ("ON", "OFF")
        with st.spinner("Asking both OCI chats…"):
            try:
                with OpenAI(api_key=api_key.strip(), base_url=endpoint, project=project.strip(),
                            timeout=120.0, max_retries=0) as client:
                    for name in order:
                        state, result = chat_turn(client, model.strip(),
                            st.session_state.chat_branches[name], prompt,
                            name == "ON", threshold, max_output)
                        st.session_state.chat_branches[name] = state
                        turn["results"][name] = result
                st.session_state.chat_turns.append(turn)
            except Exception:
                # Never put credentials or raw provider bodies on the page.
                st.error("Could not initialize the OCI chats. Check your connection settings.")

turns = st.session_state.chat_turns


def number(value):
    return "—" if value is None else f"{value:,}"


def render_answers(turn):
    columns = st.columns(2, gap="large")
    for name, column in zip(("OFF", "ON"), columns):
        result = turn["results"][name]
        with column, st.container(border=True):
            st.subheader("Without compaction" if name == "OFF" else "With compaction")
            if result["error"]:
                st.caption("Request failed")
            elif name == "ON":
                if result["used_compacted_context"]:
                    st.caption("✓ Used compacted context")
                elif not result["effective_enabled"]:
                    st.caption("⚠ Full history used as fallback")
                elif result["compaction_observed"]:
                    st.caption("Context ready for the next question")
                else:
                    st.caption("Waiting for compaction to trigger")
            else:
                st.caption("Full conversation history")
            if result["error"]:
                st.error(result["error"])
            else:
                st.markdown(result["answer"] or "No text answer returned.")
            if result["incomplete"]:
                st.warning("Answer incomplete. Increase the output limit in Advanced settings.")


if not turns:
    st.info("Ask a question below to begin. Then ask follow-ups to see how the amount of history changes.")
    columns = st.columns(2, gap="large")
    for title, column in zip(("Without compaction", "With compaction"), columns):
        with column, st.container(border=True):
            st.subheader(title)
            st.caption("Your answer will appear here.")
    st.write("Try: **Plan a relaxed first day in Kyoto.** Then: **What food restrictions must you remember?**")
else:
    latest = turns[-1]
    off, on = latest["results"]["OFF"], latest["results"]["ON"]
    comparison = compare_answers(off, on)
    st.subheader("Did compaction help on this question?")
    if comparison["eligible"]:
        st.success(comparison["message"])
        a, b, c = st.columns(3)
        a.metric("Input tokens · with compaction", comparison["input"])
        b.metric("Total tokens · with compaction", comparison["total"])
        c.metric("Answer time · with compaction", comparison["time"])
        st.caption("Compared with the answer without compaction. Results vary with answer length and service load.")
    elif comparison["status"] == "fallback":
        st.warning(comparison["message"])
        st.caption("OCI rejected compaction. The right chat recovered with full history. "
                   "Use Retry compaction next turn in the sidebar to try again.")
    else:
        st.info(comparison["message"])

    st.table(pd.DataFrame([
        {"Measure": "Input tokens (history + question)", "Without compaction": number(off["input_tokens"]), "With compaction": number(on["input_tokens"])},
        {"Measure": "Total tokens (input + output)", "Without compaction": number(off["total_tokens"]), "With compaction": number(on["total_tokens"])},
        {"Measure": "Answer time", "Without compaction": f"{off['seconds']:.2f} s", "With compaction": f"{on['seconds']:.2f} s"},
    ]).set_index("Measure"))
    if not comparison["eligible"]:
        st.caption("Numbers above are the two actual runs. Differences are not evidence of a compaction benefit for this question.")
    st.markdown(f"**Question {len(turns)}:** " + latest["prompt"])
    render_answers(latest)
    st.caption("Check that both answers still remember the important facts. Fewer tokens only help if the answer stays useful.")

    if len(turns) > 1:
        with st.expander(f"Earlier questions ({len(turns) - 1})", expanded=False):
            for index, turn in enumerate(turns[:-1], 1):
                st.markdown(f"**Question {index}:** " + turn["prompt"])
                render_answers(turn)

    with st.expander("Charts, totals and request details", expanded=False):
        rows = []
        for index, turn in enumerate(turns, 1):
            for name in ("OFF", "ON"):
                result = turn["results"][name]
                rows.append({"Question": index, "Chat": "Without compaction" if name == "OFF" else "With compaction",
                             "Input tokens": result["input_tokens"], "Output tokens": result["output_tokens"],
                             "Total tokens": result["total_tokens"], "Answer time (s)": result["seconds"],
                             "Used compacted context": result["used_compacted_context"],
                             "Compaction returned": result["compaction_observed"],
                             "Fallback / paused": name == "ON" and not result["effective_enabled"],
                             "Successful": result["error"] is None})
        data = pd.DataFrame(rows)
        st.caption("Reported tokens across the conversation · Failed-request usage is unknown and excluded.")
        st.dataframe(data.groupby("Chat")[["Input tokens", "Output tokens", "Total tokens"]].sum(min_count=1), width="stretch")
        left, right = st.columns(2)
        with left:
            st.caption("Input tokens per question")
            st.line_chart(data, x="Question", y="Input tokens", color="Chat")
        with right:
            st.caption("Time per question")
            st.line_chart(data, x="Question", y="Answer time (s)", color="Chat")
        st.dataframe(data, hide_index=True, width="stretch")
        st.download_button("Download measurements (CSV)", data.to_csv(index=False).encode(),
                           "oci-chat-measurements.csv", "text/csv")
        st.write("Latest request attempts")
        for name in ("OFF", "ON"):
            result = latest["results"][name]
            st.caption("Without compaction" if name == "OFF" else "With compaction")
            for notice in result["notices"]:
                st.write(notice)
            st.dataframe(result["attempts"], hide_index=True, width="stretch")

st.caption("Live OCI only. Each question makes two requests; recovery can add a request. "
           "Time measures the complete request, including recovery. Token counts cover successful responses only. "
           "The chats generate independent answers, so this is an exploratory comparison, not a controlled benchmark.")
