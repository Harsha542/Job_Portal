
import os

import pandas as pd
import requests
import streamlit as st


st.set_page_config(
    page_title="Recruitment Analytics | CareerBridge",
    page_icon="📊",
    layout="wide",
)

API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://127.0.0.1:8000",
).rstrip("/")


def fetch_analytics():
    token = st.session_state.get("token")
    user = st.session_state.get("user")

    if not token or not user:
        st.warning("Please sign in through the main application first.")
        return None

    if user.get("role") != "admin":
        st.error("Access denied. This page is for administrators only.")
        return None

    try:
        response = requests.get(
            f"{API_BASE_URL}/analytics/dashboard",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )

        if response.status_code == 401:
            st.error("Your session has expired. Sign in again.")
            return None

        if response.status_code == 403:
            st.error("Your account does not have administrator access.")
            return None

        response.raise_for_status()
        return response.json()

    except requests.RequestException as exc:
        st.error(f"Unable to load analytics: {exc}")
        return None


st.title("📊 Recruitment Analytics")
st.caption(
    "Monitor hiring activity, application progress, and job performance."
)

if st.button("Refresh analytics"):
    st.rerun()

data = fetch_analytics()

if data is not None:
    overview = data["overview"]

    st.caption(f'Last generated: {data["generated_at"]}')

    # KPI cards
    st.subheader("Platform overview")

    row1 = st.columns(4)
    row1[0].metric("Total users", overview["total_users"])
    row1[1].metric("Candidates", overview["total_candidates"])
    row1[2].metric("Recruiters", overview["total_recruiters"])
    row1[3].metric("Total jobs", overview["total_jobs"])

    row2 = st.columns(4)
    row2[0].metric("Active jobs", overview["active_jobs"])
    row2[1].metric("Closed jobs", overview["closed_jobs"])
    row2[2].metric(
        "Applications",
        overview["total_applications"],
    )
    row2[3].metric("Hired", overview["hired_count"])

    st.metric(
        "Hiring rate",
        f'{overview["hiring_rate_percent"]:.2f}%',
        help="Hired applications divided by all applications.",
    )

    st.divider()

    # Application status chart
    left, right = st.columns(2)

    with left:
        st.subheader("Application status breakdown")

        statuses = pd.DataFrame(data["application_statuses"])

        if not statuses.empty:
            st.bar_chart(
                statuses.set_index("status"),
                y="count",
            )
            st.dataframe(
                statuses,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No application status data is available.")

    with right:
        st.subheader("Monthly application trend")

        monthly = pd.DataFrame(data["monthly_applications"])

        if not monthly.empty:
            st.line_chart(
                monthly.set_index("month"),
                y="applications",
            )
        else:
            st.info("No monthly application data is available.")

    st.divider()

    # Top jobs
    st.subheader("Jobs attracting the most applicants")

    top_jobs = pd.DataFrame(data["top_jobs"])

    if not top_jobs.empty:
        chart_data = top_jobs[
            ["title", "applicants"]
        ].copy()

        # Include the job ID to distinguish jobs with identical titles.
        chart_data["title"] = (
            top_jobs["title"]
            + " (Job "
            + top_jobs["job_id"].astype(str)
            + ")"
        )

        st.bar_chart(
            chart_data.set_index("title"),
            y="applicants",
        )

        st.dataframe(
            top_jobs,
            use_container_width=True,
            hide_index=True,
        )

        csv_data = top_jobs.to_csv(index=False).encode("utf-8")

        st.download_button(
            "Export top jobs as CSV",
            data=csv_data,
            file_name="top_jobs_analytics.csv",
            mime="text/csv",
        )
    else:
        st.info("No jobs have been posted yet.")

    st.caption(
        "Metrics are calculated from the application's current database. "
        "Monthly trends cover the latest 12 calendar months."
    )