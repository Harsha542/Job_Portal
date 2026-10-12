
import os

import requests


API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://127.0.0.1:8000",
)


class APIClient:
    def __init__(self, token=None):
        self.base_url = API_BASE_URL.rstrip("/")
        self.token = token

    def request(self, method, path, **kwargs):
        headers = kwargs.pop("headers", {}).copy()

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            response = requests.request(
                method=method,
                url=f"{self.base_url}{path}",
                headers=headers,
                timeout=30,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise RuntimeError(
                "Cannot connect to FastAPI. Make sure the backend "
                "is running at " + self.base_url
            ) from exc

        if not response.ok:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text

            if isinstance(detail, list):
                detail = "; ".join(
                    str(item.get("msg", item))
                    if isinstance(item, dict)
                    else str(item)
                    for item in detail
                )

            raise RuntimeError(
                f"API error {response.status_code}: {detail}"
            )

        if response.status_code == 204 or not response.content:
            return None

        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()

        return response.content

    # ---------------- AUTHENTICATION ----------------

    def register(self, full_name, email, password, role):
        return self.request(
            "POST",
            "/auth/register",
            json={
                "full_name": full_name,
                "email": email,
                "password": password,
                "role": role,
            },
        )

    def login(self, email, password):
        result = self.request(
            "POST",
            "/auth/login",
            data={
                "username": email,
                "password": password,
            },
        )
        self.token = result["access_token"]
        return self.get_profile()

    def get_profile(self):
        return self.request("GET", "/auth/me")

    # ---------------- JOBS ----------------

    def list_jobs(
        self,
        search="",
        location="",
        skills="",
        skip=0,
        limit=100,
    ):
        params = {
            "skip": skip,
            "limit": limit,
        }

        if search.strip():
            params["q"] = search.strip()
        if location.strip():
            params["location"] = location.strip()
        if skills.strip():
            params["skills"] = skills.strip()

        return self.request("GET", "/jobs", params=params)

    def get_job(self, job_id):
        return self.request("GET", f"/jobs/{job_id}")

    def create_job(self, job_data):
        return self.request("POST", "/jobs", json=job_data)

    def get_my_jobs(self):
        return self.request("GET", "/jobs/my")

    def update_job(self, job_id, job_data):
        return self.request(
            "PUT",
            f"/jobs/{job_id}",
            json=job_data,
        )

    def close_job(self, job_id):
        return self.request("PATCH", f"/jobs/{job_id}/close")

    # ---------------- APPLICATIONS ----------------

    def apply_for_job(self, job_id, filename, file_bytes, mime_type):
        return self.request(
            "POST",
            f"/applications/jobs/{job_id}/apply",
            files={
                "resume": (
                    filename,
                    file_bytes,
                    mime_type,
                )
            },
        )

    def get_my_applications(self):
        return self.request("GET", "/applications/my")

    def get_applicants(self, job_id):
        return self.request(
            "GET",
            f"/applications/jobs/{job_id}",
        )

    def update_application_status(self, application_id, new_status):
        return self.request(
            "PATCH",
            f"/applications/{application_id}/status",
            json={"status": new_status},
        )

    def download_resume(self, application_id):
        return self.request(
            "GET",
            f"/applications/{application_id}/resume",
        )

    # ---------------- INTERVIEWS ----------------

    def schedule_interview(
        self,
        application_id,
        scheduled_at,
        interview_type="Online",
        meeting_details="",
        notes="",
    ):
        return self.request(
            "POST",
            f"/interviews/applications/{application_id}",
            json={
                "scheduled_at": scheduled_at,
                "interview_type": interview_type,
                "meeting_details": meeting_details or None,
                "notes": notes or None,
            },
        )

    def get_my_interviews(self):
        return self.request("GET", "/interviews/my")

    def get_application_interviews(self, application_id):
        return self.request(
            "GET",
            f"/interviews/applications/{application_id}",
        )

    def update_interview(self, interview_id, updates):
        return self.request(
            "PATCH",
            f"/interviews/{interview_id}",
            json=updates,
        )

    def cancel_interview(self, interview_id):
        return self.request(
            "POST",
            f"/interviews/{interview_id}/cancel",
        )