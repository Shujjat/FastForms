from django.contrib.auth import get_user_model
from django.core import mail
from rest_framework import status
from rest_framework.test import APITestCase

from apps.forms.models import Form, Question

User = get_user_model()


class FastFormsApiTests(APITestCase):
    def setUp(self):
        self.creator = User.objects.create_user(
            username="creator1", email="creator@example.com", password="Password123!", role="creator"
        )
        self.respondent = User.objects.create_user(
            username="resp1", email="resp@example.com", password="Password123!", role="respondent"
        )
        self.analyst = User.objects.create_user(
            username="analyst1", email="analyst@example.com", password="Password123!", role="analyst"
        )

    def _login(self, username, password="Password123!"):
        res = self.client.post("/api/auth/login", {"username": username, "password": password}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    def test_register_endpoint(self):
        res = self.client.post(
            "/api/auth/register",
            {"username": "newuser", "email": "new@example.com", "password": "Password123!", "role": "creator"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_creator_can_create_publish_and_submit_flow(self):
        self._login("creator1")
        create = self.client.post("/api/forms", {"title": "Survey 1", "description": "Desc"}, format="json")
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        form_id = create.data["id"]

        q1 = self.client.post(
            f"/api/forms/{form_id}/questions",
            {"order_index": 0, "question_type": "short_text", "text": "Your name?", "required": True},
            format="json",
        )
        self.assertEqual(q1.status_code, status.HTTP_201_CREATED)
        qid = q1.data["id"]

        publish = self.client.post(f"/api/forms/{form_id}/publish", format="json")
        self.assertEqual(publish.status_code, status.HTTP_200_OK)

        self._login("resp1")
        submit = self.client.post(
            f"/api/forms/{form_id}/submit",
            {"answers": {str(qid): "Alice"}},
            format="json",
        )
        self.assertEqual(submit.status_code, status.HTTP_201_CREATED)

    def test_required_answer_validation(self):
        form = Form.objects.create(owner=self.creator, title="Req Form", status="published")
        Question.objects.create(form=form, order_index=0, question_type="short_text", text="Q1", required=True)
        self._login("resp1")
        res = self.client.post(f"/api/forms/{form.id}/submit", {"answers": {}}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_one_response_per_user_enforced(self):
        form = Form.objects.create(owner=self.creator, title="One Response", status="published", one_response_per_user=True)
        q = Question.objects.create(form=form, order_index=0, question_type="short_text", text="Q1", required=False)

        self._login("resp1")
        first = self.client.post(f"/api/forms/{form.id}/submit", {"answers": {str(q.id): "one"}}, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second = self.client.post(f"/api/forms/{form.id}/submit", {"answers": {str(q.id): "two"}}, format="json")
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)

    def test_analyst_cannot_create_form(self):
        self._login("analyst1")
        res = self.client.post("/api/forms", {"title": "Nope", "description": ""}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_export_responses(self):
        self._login("creator1")
        form = self.client.post("/api/forms", {"title": "Exportable", "description": "d"}, format="json").data
        form_id = form["id"]
        q = self.client.post(
            f"/api/forms/{form_id}/questions",
            {"order_index": 0, "question_type": "short_text", "text": "Q1", "required": False},
            format="json",
        ).data
        self.client.post(f"/api/forms/{form_id}/publish", format="json")

        self._login("resp1")
        self.client.post(f"/api/forms/{form_id}/submit", {"answers": {str(q['id']): "value"}}, format="json")

        self._login("creator1")
        export_json = self.client.get(f"/api/forms/{form_id}/export?export_format=json")
        self.assertEqual(export_json.status_code, status.HTTP_200_OK)

        export_csv = self.client.get(f"/api/forms/{form_id}/export?export_format=csv")
        self.assertEqual(export_csv.status_code, status.HTTP_200_OK)
        self.assertIn("text/csv", export_csv["Content-Type"])

    def test_owner_can_add_collaborator_editor(self):
        self._login("creator1")
        form_id = self.client.post("/api/forms", {"title": "Shared", "description": "d"}, format="json").data["id"]
        add = self.client.post(
            f"/api/forms/{form_id}/collaborators",
            {"username": "analyst1", "role": "editor"},
            format="json",
        )
        self.assertEqual(add.status_code, status.HTTP_201_CREATED)
        self.assertEqual(add.data["role"], "editor")

    def test_analyst_editor_collaborator_still_cannot_add_questions(self):
        self._login("creator1")
        form_id = self.client.post("/api/forms", {"title": "Edit Shared", "description": "d"}, format="json").data["id"]
        self.client.post(
            f"/api/forms/{form_id}/collaborators",
            {"username": "analyst1", "role": "editor"},
            format="json",
        )

        self._login("analyst1")
        q = self.client.post(
            f"/api/forms/{form_id}/questions",
            {"order_index": 0, "question_type": "short_text", "text": "Shared Q", "required": False},
            format="json",
        )
        self.assertEqual(q.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_access_form_actions(self):
        owned_form = Form.objects.create(owner=self.creator, title="Locked", status="published")
        Question.objects.create(form=owned_form, order_index=0, question_type="short_text", text="Q1", required=False)

        list_forms = self.client.get("/api/forms")
        self.assertEqual(list_forms.status_code, status.HTTP_401_UNAUTHORIZED)

        get_form = self.client.get(f"/api/forms/{owned_form.id}")
        self.assertEqual(get_form.status_code, status.HTTP_401_UNAUTHORIZED)

        submit = self.client.post(f"/api/forms/{owned_form.id}/submit", {"answers": {}}, format="json")
        self.assertEqual(submit.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_responses_search_filter(self):
        self._login("creator1")
        form = self.client.post("/api/forms", {"title": "Filter Form", "description": ""}, format="json").data
        form_id = form["id"]
        q = self.client.post(
            f"/api/forms/{form_id}/questions",
            {"order_index": 0, "question_type": "short_text", "text": "Name", "required": True},
            format="json",
        ).data
        self.client.post(f"/api/forms/{form_id}/publish", format="json")
        self._login("resp1")
        self.client.post(f"/api/forms/{form_id}/submit", {"answers": {str(q["id"]): "unique-xyz-answer"}}, format="json")

        self._login("creator1")
        all_res = self.client.get(f"/api/forms/{form_id}/responses")
        self.assertEqual(len(all_res.data), 1)
        filtered = self.client.get(f"/api/forms/{form_id}/responses?search=unique-xyz")
        self.assertEqual(len(filtered.data), 1)
        none_match = self.client.get(f"/api/forms/{form_id}/responses?search=nomatch999")
        self.assertEqual(len(none_match.data), 0)

    def test_answer_validation_min_length(self):
        form = Form.objects.create(owner=self.creator, title="Val Form", status="published")
        q = Question.objects.create(
            form=form,
            order_index=0,
            question_type="short_text",
            text="Code",
            required=True,
            validation={"min_length": 4},
        )
        self._login("resp1")
        bad = self.client.post(f"/api/forms/{form.id}/submit", {"answers": {str(q.id): "ab"}}, format="json")
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        ok = self.client.post(f"/api/forms/{form.id}/submit", {"answers": {str(q.id): "abcd"}}, format="json")
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED)

    def test_invite_requires_published_form(self):
        self._login("creator1")
        form = self.client.post("/api/forms", {"title": "Draft Invite", "description": ""}, format="json").data
        res = self.client.post(f"/api/forms/{form['id']}/invite", {"emails": ["a@example.com"]}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invite_sends_emails_when_published(self):
        self._login("creator1")
        form = self.client.post("/api/forms", {"title": "Invite Form", "description": "Desc"}, format="json").data
        fid = form["id"]
        self.client.post(f"/api/forms/{fid}/publish", format="json")
        mail.outbox.clear()
        res = self.client.post(
            f"/api/forms/{fid}/invite",
            {"emails": ["inv1@example.com", "inv2@example.com"], "message": "Please complete this."},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["sent"], 2)
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("Invite Form", mail.outbox[0].subject)
