from datetime import date, datetime, time as dt_time, timedelta, timezone

import streamlit as st

from api_client import APIClient


st.set_page_config(
    page_title="CareerBridge | Job Portal",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)


# -------------------------
# Session and API helpers
# -------------------------

if "token" not in st.session_state:
    st.session_state.token = None

if "user" not in st.session_state:
    st.session_state.user = None


def get_client():
    return APIClient(st.session_state.token)


def show_error(error):
    st.error(str(error))


def money(value):
    if value is None:
        return "Not specified"
    return f"₹{value:,.0f}"


def show_salary(job):
    minimum = job.get("salary_min")
    maximum = job.get("salary_max")

    if minimum is None and maximum is None:
        return "Salary not specified"

    if minimum is not None and maximum is not None:
        return f"{money(minimum)} – {money(maximum)}"

    if minimum is not None:
        return f"From {money(minimum)}"

    return f"Up to {money(maximum)}"


def make_interview_datetime(interview_date, interview_time):
    # The project is using Indian Standard Time (UTC+05:30).
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.combine(
        interview_date,
        interview_time,
    ).replace(tzinfo=ist).isoformat()


def display_datetime(value):
    if not value:
        return "Not specified"

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone(timedelta(hours=5, minutes=30)))
        return parsed.strftime("%d %b %Y, %I:%M %p IST")
    except (TypeError, ValueError):
        return str(value)


def interview_local_datetime(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    ist = timezone(timedelta(hours=5, minutes=30))
    # SQLite may return a timezone-naive datetime even when the API input
    # included an offset. In this project, naive interview values are IST.
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=ist)
    return parsed.astimezone(ist)


def logout():
    st.session_state.token = None
    st.session_state.user = None
    st.rerun()


# -------------------------
# Login and registration
# -------------------------

def authentication_page():
    st.title("💼 CareerBridge")
    st.subheader("Your next opportunity starts here")
    st.write(
        "Discover jobs, manage applications, and simplify recruitment."
    )

    login_tab, register_tab = st.tabs(
        ["Sign in", "Create account"]
    )

    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email address")
            password = st.text_input(
                "Password",
                type="password",
            )
            submitted = st.form_submit_button(
                "Sign in",
                use_container_width=True,
            )

        if submitted:
            if not email.strip() or not password:
                st.warning("Enter your email and password.")
            else:
                try:
                    client = APIClient()
                    user = client.login(email.strip(), password)

                    st.session_state.token = client.token
                    st.session_state.user = user

                    st.success("Login successful.")
                    st.rerun()
                except Exception as error:
                    show_error(error)

    with register_tab:
        with st.form("register_form"):
            full_name = st.text_input("Full name")
            new_email = st.text_input("Email address")
            new_password = st.text_input(
                "Password (at least 8 characters)",
                type="password",
            )
            confirm_password = st.text_input(
                "Confirm password",
                type="password",
            )
            role = st.selectbox(
                "Create account as",
                ["candidate", "recruiter"],
                format_func=lambda value: value.title(),
            )

            register_submitted = st.form_submit_button(
                "Create account",
                use_container_width=True,
            )

        if register_submitted:
            if not full_name.strip() or not new_email.strip():
                st.warning("Please complete all required fields.")
            elif len(new_password) < 8:
                st.warning("Password must contain at least 8 characters.")
            elif new_password != confirm_password:
                st.warning("Passwords do not match.")
            else:
                try:
                    APIClient().register(
                        full_name.strip(),
                        new_email.strip(),
                        new_password,
                        role,
                    )
                    st.success(
                        "Account created. Sign in using your new credentials."
                    )
                except Exception as error:
                    show_error(error)


# -------------------------
# Candidate dashboard
# -------------------------

def candidate_dashboard(client):
    st.title("Candidate Dashboard")
    st.write("Find opportunities and track your applications.")

    jobs_tab, applications_tab, interviews_tab = st.tabs(
        ["Find jobs", "My applications", "My interviews"]
    )

    with jobs_tab:
        st.subheader("Explore open positions")

        col1, col2, col3 = st.columns(3)

        with col1:
            search = st.text_input(
                "Job title or keyword",
                key="candidate_search",
            )
        with col2:
            location = st.text_input(
                "Location",
                key="candidate_location",
            )
        with col3:
            skills = st.text_input(
                "Skills",
                key="candidate_skills",
            )

        try:
            jobs = client.list_jobs(
                search=search,
                location=location,
                skills=skills,
                limit=100,
            )

            if not jobs:
                st.info("No active jobs match your search.")

            for job in jobs:
                with st.container(border=True):
                    left, right = st.columns([4, 1])

                    with left:
                        st.subheader(job["title"])
                        st.caption(
                            f'{job["location"]} · '
                            f'{show_salary(job)}'
                        )
                        st.write(
                            "**Required skills:** "
                            + job["required_skills"]
                        )
                        st.write(job["description"])

                    with right:
                        st.write(
                            f'**Job ID:** {job["id"]}'
                        )

                        with st.popover(
                            "Apply now",
                            use_container_width=True,
                        ):
                            st.write(
                                "Upload your resume as a PDF or DOCX "
                                "(maximum 5 MB)."
                            )

                            resume = st.file_uploader(
                                "Choose resume",
                                type=["pdf", "docx"],
                                key=f'resume_{job["id"]}',
                            )

                            if st.button(
                                "Submit application",
                                key=f'apply_{job["id"]}',
                                use_container_width=True,
                            ):
                                if resume is None:
                                    st.warning(
                                        "Choose a resume before applying."
                                    )
                                else:
                                    try:
                                        client.apply_for_job(
                                            job["id"],
                                            resume.name,
                                            resume.getvalue(),
                                            resume.type
                                            or "application/octet-stream",
                                        )
                                        st.success(
                                            "Application submitted successfully."
                                        )
                                        st.rerun()
                                    except Exception as error:
                                        show_error(error)

        except Exception as error:
            show_error(error)

    with applications_tab:
        st.subheader("Application history")

        try:
            applications = client.get_my_applications()

            if not applications:
                st.info(
                    "You have not applied for any jobs yet."
                )
            else:
                st.metric(
                    "Total applications",
                    len(applications),
                )

                for application in applications:
                    with st.container(border=True):
                        st.markdown(
                            f'**{application["job_title"]}**'
                        )
                        st.write(
                            f'Location: {application["job_location"]}'
                        )
                        st.write(
                            f'Status: **{application["status"]}**'
                        )
                        st.caption(
                            f'Applied at: {application["applied_at"]}'
                        )

                        if application["resume_available"]:
                            if st.button(
                                "Download my resume",
                                key=f'my_resume_{application["id"]}',
                            ):
                                try:
                                    resume_bytes = client.download_resume(
                                        application["id"]
                                    )
                                    st.download_button(
                                        "Save resume",
                                        data=resume_bytes,
                                        file_name="my_resume",
                                        key=(
                                            f'save_my_resume_'
                                            f'{application["id"]}'
                                        ),
                                    )
                                except Exception as error:
                                    show_error(error)

        except Exception as error:
            show_error(error)

    with interviews_tab:
        st.subheader("My interviews")
        st.write("Review interview schedules shared by recruiters.")

        try:
            interviews = client.get_my_interviews()

            if not interviews:
                st.info("You do not have any interviews scheduled yet.")
            else:
                st.metric("Total interviews", len(interviews))

                for interview in interviews:
                    with st.container(border=True):
                        st.markdown(f'### {interview["job_title"]}')
                        st.write(
                            f'**Date and time:** '
                            f'{display_datetime(interview.get("scheduled_at"))}'
                        )
                        st.write(
                            f'**Interview type:** '
                            f'{interview.get("interview_type", "Not specified")}'
                        )
                        st.write(
                            f'**Status:** {interview.get("status", "Unknown")}'
                        )
                        meeting_details = interview.get("meeting_details")
                        if meeting_details:
                            st.write(f"**Meeting details:** {meeting_details}")

                        notes = interview.get("notes")
                        if notes:
                            st.write(f"**Notes:** {notes}")

        except Exception as error:
            show_error(error)


# -------------------------
# Recruiter dashboard
# -------------------------

def recruiter_dashboard(client):
    st.title("Recruiter Dashboard")
    st.write(
        "Create job postings and manage your recruitment pipeline."
    )

    create_tab, jobs_tab = st.tabs(
        ["Create a job", "My jobs and applicants"]
    )

    with create_tab:
        st.subheader("Publish a job opening")

        with st.form("create_job_form"):
            title = st.text_input("Job title")
            location = st.text_input("Job location")
            skills = st.text_input(
                "Required skills",
                placeholder="Python, SQL, FastAPI",
            )
            description = st.text_area(
                "Job description",
                height=160,
            )

            salary_enabled = st.checkbox(
                "Specify a salary range"
            )

            salary_min = None
            salary_max = None

            if salary_enabled:
                salary_col1, salary_col2 = st.columns(2)

                with salary_col1:
                    salary_min = st.number_input(
                        "Minimum salary (₹)",
                        min_value=0.0,
                        value=0.0,
                        step=1000.0,
                    )

                with salary_col2:
                    salary_max = st.number_input(
                        "Maximum salary (₹)",
                        min_value=0.0,
                        value=0.0,
                        step=1000.0,
                    )

            publish = st.form_submit_button(
                "Publish job",
                use_container_width=True,
            )

        if publish:
            if not title.strip() or not location.strip():
                st.warning("Job title and location are required.")
            elif len(description.strip()) < 20:
                st.warning(
                    "Please provide a description of at least 20 characters."
                )
            elif len(skills.strip()) < 2:
                st.warning("Enter the required skills.")
            elif (
                salary_enabled
                and salary_max < salary_min
            ):
                st.warning(
                    "Maximum salary must be at least the minimum salary."
                )
            else:
                job_data = {
                    "title": title.strip(),
                    "location": location.strip(),
                    "required_skills": skills.strip(),
                    "description": description.strip(),
                    "salary_min": salary_min if salary_enabled else None,
                    "salary_max": salary_max if salary_enabled else None,
                }

                try:
                    created_job = client.create_job(job_data)
                    st.success(
                        f'Job published successfully. ID: {created_job["id"]}'
                    )
                except Exception as error:
                    show_error(error)

    with jobs_tab:
        st.subheader("Your job postings")

        try:
            jobs = client.get_my_jobs()

            if not jobs:
                st.info(
                    "You have not published any jobs yet."
                )

            for job in jobs:
                with st.container(border=True):
                    st.markdown(f'### {job["title"]}')
                    st.write(
                        f'{job["location"]} · {show_salary(job)}'
                    )
                    st.write(
                        f'Status: **{"Open" if job["is_active"] else "Closed"}**'
                    )
                    st.caption(f'Job ID: {job["id"]}')

                    if job["is_active"]:
                        with st.expander("Edit job"):
                            with st.form(f'edit_job_{job["id"]}'):
                                edit_title = st.text_input(
                                    "Title",
                                    value=job["title"],
                                )
                                edit_location = st.text_input(
                                    "Location",
                                    value=job["location"],
                                )
                                edit_skills = st.text_input(
                                    "Required skills",
                                    value=job["required_skills"],
                                )
                                edit_description = st.text_area(
                                    "Description",
                                    value=job["description"],
                                )
                                edit_min = st.number_input(
                                    "Minimum salary (₹); 0 means unspecified",
                                    min_value=0.0,
                                    value=float(job["salary_min"] or 0),
                                    step=1000.0,
                                )
                                edit_max = st.number_input(
                                    "Maximum salary (₹); 0 means unspecified",
                                    min_value=0.0,
                                    value=float(job["salary_max"] or 0),
                                    step=1000.0,
                                )

                                save_changes = st.form_submit_button(
                                    "Save changes"
                                )

                            if save_changes:
                                if (
                                    len(edit_title.strip()) < 3
                                    or len(edit_description.strip()) < 20
                                    or len(edit_location.strip()) < 2
                                    or len(edit_skills.strip()) < 2
                                ):
                                    st.warning(
                                        "Please complete all job fields correctly."
                                    )
                                elif (
                                    edit_min > 0
                                    and edit_max > 0
                                    and edit_max < edit_min
                                ):
                                    st.warning(
                                        "Maximum salary cannot be lower than minimum salary."
                                    )
                                else:
                                    update_data = {
                                        "title": edit_title.strip(),
                                        "location": edit_location.strip(),
                                        "required_skills": edit_skills.strip(),
                                        "description": edit_description.strip(),
                                        "salary_min": edit_min or None,
                                        "salary_max": edit_max or None,
                                    }

                                    try:
                                        client.update_job(
                                            job["id"],
                                            update_data,
                                        )
                                        st.success("Job updated.")
                                        st.rerun()
                                    except Exception as error:
                                        show_error(error)

                    action_col, applicants_col = st.columns(2)

                    with action_col:
                        if job["is_active"]:
                            if st.button(
                                "Close job",
                                key=f'close_job_{job["id"]}',
                            ):
                                try:
                                    client.close_job(job["id"])
                                    st.success("Job closed.")
                                    st.rerun()
                                except Exception as error:
                                    show_error(error)

                    with applicants_col:
                        if st.button(
                            "View applicants",
                            key=f'view_applicants_{job["id"]}',
                        ):
                            st.session_state.selected_job_id = job["id"]

                    if st.session_state.get("selected_job_id") == job["id"]:
                        st.markdown("#### Applicants")

                        try:
                            applicants = client.get_applicants(job["id"])

                            if not applicants:
                                st.info(
                                    "No candidates have applied for this job yet."
                                )

                            for applicant in applicants:
                                with st.container(border=True):
                                    st.markdown(
                                        f'**{applicant["candidate_name"]}**'
                                    )
                                    st.write(applicant["candidate_email"])
                                    st.write(
                                        f'Current status: {applicant["status"]}'
                                    )
                                    st.caption(
                                        f'Application ID: {applicant["id"]}'
                                    )

                                    if applicant["resume_available"]:
                                        try:
                                            resume_bytes = client.download_resume(
                                                applicant["id"]
                                            )
                                            st.download_button(
                                                "Download resume",
                                                data=resume_bytes,
                                                file_name=(
                                                    f'resume_'
                                                    f'{applicant["candidate_id"]}'
                                                ),
                                                key=(
                                                    f'download_resume_'
                                                    f'{applicant["id"]}'
                                                ),
                                            )
                                        except Exception as error:
                                            show_error(error)

                                    statuses = [
                                        "Applied",
                                        "Shortlisted",
                                        "Interview",
                                        "Rejected",
                                        "Hired",
                                    ]

                                    selected_status = st.selectbox(
                                        "Update application status",
                                        statuses,
                                        index=statuses.index(
                                            applicant["status"]
                                        ),
                                        key=f'status_{applicant["id"]}',
                                    )

                                    if st.button(
                                        "Save status",
                                        key=f'save_status_{applicant["id"]}',
                                    ):
                                        try:
                                            client.update_application_status(
                                                applicant["id"],
                                                selected_status,
                                            )
                                            st.success("Status updated.")
                                            st.rerun()
                                        except Exception as error:
                                            show_error(error)

                                    with st.expander("Interview management"):
                                        st.markdown("##### Schedule an interview")
                                        if applicant["status"] in ("Rejected", "Hired"):
                                            st.info(
                                                "Interview scheduling is unavailable "
                                                "for rejected or hired applications."
                                            )
                                        else:
                                            with st.form(
                                                f'schedule_interview_{applicant["id"]}'
                                            ):
                                                interview_date = st.date_input(
                                                    "Interview date",
                                                    value=date.today() + timedelta(days=1),
                                                    min_value=date.today(),
                                                    key=f'interview_date_{applicant["id"]}',
                                                )
                                                interview_time = st.time_input(
                                                    "Interview time (IST)",
                                                    value=dt_time(10, 0),
                                                    key=f'interview_time_{applicant["id"]}',
                                                )
                                                interview_type = st.selectbox(
                                                    "Interview type",
                                                    ["Online", "In-person", "Phone"],
                                                    key=f'interview_type_{applicant["id"]}',
                                                )
                                                meeting_details = st.text_input(
                                                    "Meeting link or location",
                                                    key=f'meeting_details_{applicant["id"]}',
                                                )
                                                interview_notes = st.text_area(
                                                    "Interview notes",
                                                    key=f'interview_notes_{applicant["id"]}',
                                                )
                                                schedule_submitted = st.form_submit_button(
                                                    "Schedule interview",
                                                    use_container_width=True,
                                                )

                                            if schedule_submitted:
                                                scheduled_at = make_interview_datetime(
                                                    interview_date,
                                                    interview_time,
                                                )
                                                try:
                                                    client.schedule_interview(
                                                        applicant["id"],
                                                        scheduled_at,
                                                        interview_type,
                                                        meeting_details,
                                                        interview_notes,
                                                    )
                                                    st.success("Interview scheduled.")
                                                    st.rerun()
                                                except Exception as error:
                                                    show_error(error)

                                        st.markdown("##### Existing interviews")
                                        try:
                                            interviews = client.get_application_interviews(
                                                applicant["id"]
                                            )

                                            if not interviews:
                                                st.caption(
                                                    "No interviews have been scheduled "
                                                    "for this application."
                                                )

                                            for interview in interviews:
                                                interview_id = interview["id"]
                                                st.markdown(
                                                    f'**Interview #{interview_id} — '
                                                    f'{interview.get("status", "Unknown")}**'
                                                )
                                                st.write(
                                                    display_datetime(
                                                        interview.get("scheduled_at")
                                                    )
                                                )
                                                st.caption(
                                                    f'Type: {interview.get("interview_type", "Not specified")}'
                                                )
                                                if interview.get("meeting_details"):
                                                    st.write(
                                                        "Meeting details: "
                                                        + interview["meeting_details"]
                                                    )
                                                if interview.get("notes"):
                                                    st.write(
                                                        "Notes: " + interview["notes"]
                                                    )

                                                if interview.get("status") == "Scheduled":
                                                    current_interview_dt = interview_local_datetime(
                                                        interview["scheduled_at"]
                                                    )
                                                    with st.form(
                                                        f'update_interview_{interview_id}'
                                                    ):
                                                        reschedule = st.checkbox(
                                                            "Change interview date/time",
                                                            value=False,
                                                            key=f'reschedule_interview_{interview_id}',
                                                        )
                                                        new_interview_date = None
                                                        new_interview_time = None

                                                        if reschedule:
                                                            default_date = max(
                                                                date.today(),
                                                                current_interview_dt.date(),
                                                            )
                                                            new_interview_date = st.date_input(
                                                                "New date",
                                                                value=default_date,
                                                                min_value=date.today(),
                                                                key=f'update_interview_date_{interview_id}',
                                                            )
                                                            new_interview_time = st.time_input(
                                                                "New time (IST)",
                                                                value=current_interview_dt.time().replace(
                                                                    tzinfo=None,
                                                                    second=0,
                                                                    microsecond=0,
                                                                ),
                                                                key=f'update_interview_time_{interview_id}',
                                                            )

                                                        new_interview_type = st.selectbox(
                                                            "Interview type",
                                                            ["Online", "In-person", "Phone"],
                                                            index=["Online", "In-person", "Phone"].index(
                                                                interview.get("interview_type", "Online")
                                                            ),
                                                            key=f'update_interview_type_{interview_id}',
                                                        )
                                                        new_meeting_details = st.text_input(
                                                            "Meeting link or location",
                                                            value=interview.get("meeting_details") or "",
                                                            key=f'update_meeting_details_{interview_id}',
                                                        )
                                                        new_notes = st.text_area(
                                                            "Notes",
                                                            value=interview.get("notes") or "",
                                                            key=f'update_interview_notes_{interview_id}',
                                                        )
                                                        new_status = st.selectbox(
                                                            "Interview status",
                                                            ["Scheduled", "Completed"],
                                                            index=0,
                                                            key=f'update_interview_status_{interview_id}',
                                                        )
                                                        update_submitted = st.form_submit_button(
                                                            "Save interview changes",
                                                            use_container_width=True,
                                                        )

                                                    if update_submitted:
                                                        updates = {
                                                            "interview_type": new_interview_type,
                                                            "meeting_details": new_meeting_details or None,
                                                            "notes": new_notes or None,
                                                            "status": new_status,
                                                        }
                                                        if reschedule:
                                                            updates["scheduled_at"] = make_interview_datetime(
                                                                new_interview_date,
                                                                new_interview_time,
                                                            )
                                                        try:
                                                            client.update_interview(
                                                                interview_id,
                                                                updates,
                                                            )
                                                            st.success("Interview updated.")
                                                            st.rerun()
                                                        except Exception as error:
                                                            show_error(error)

                                                    if st.button(
                                                        "Cancel interview",
                                                        key=f'cancel_interview_{interview_id}',
                                                    ):
                                                        try:
                                                            client.cancel_interview(interview_id)
                                                            st.success("Interview cancelled.")
                                                            st.rerun()
                                                        except Exception as error:
                                                            show_error(error)

                                        except Exception as error:
                                            show_error(error)

                        except Exception as error:
                            show_error(error)

        except Exception as error:
            show_error(error)


# -------------------------
# Main application
# -------------------------

if not st.session_state.token or not st.session_state.user:
    authentication_page()
else:
    user = st.session_state.user
    client = get_client()

    with st.sidebar:
        st.title("💼 CareerBridge")
        st.write(f'**{user["full_name"]}**')
        st.caption(user["email"])
        st.write(f'Role: {user["role"].title()}')
        st.divider()

        if st.button("Refresh dashboard", use_container_width=True):
            st.rerun()

        if st.button("Sign out", use_container_width=True):
            logout()

    if user["role"] == "candidate":
        candidate_dashboard(client)
    elif user["role"] == "recruiter":
        recruiter_dashboard(client)
    elif user["role"] == "admin":
        st.title("Admin Dashboard")
        st.info(
            "Admin authentication is supported. "
            "The admin analytics and user-management interface "
            "will be added in a later block."
        )
    else:
        st.error("Your account has an unsupported role.")
        logout()