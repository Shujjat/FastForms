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

    def test_owner_can_clear_all_responses(self):
        self._login("creator1")
        form_id = self.client.post("/api/forms", {"title": "Clearable", "description": "d"}, format="json").data["id"]
        q = self.client.post(
            f"/api/forms/{form_id}/questions",
            {"order_index": 0, "question_type": "short_text", "text": "Q1", "required": False},
            format="json",
        ).data
        self.client.post(f"/api/forms/{form_id}/publish", format="json")
        self._login("resp1")
        self.client.post(f"/api/forms/{form_id}/submit", {"answers": {str(q["id"]): "x"}}, format="json")
        self._login("creator1")
        clear = self.client.post(f"/api/forms/{form_id}/responses/clear", {}, format="json")
        self.assertEqual(clear.status_code, status.HTTP_200_OK)
        self.assertEqual(clear.data.get("deleted_count"), 1)
        remaining = self.client.get(f"/api/forms/{form_id}/responses")
        self.assertEqual(remaining.status_code, status.HTTP_200_OK)
        self.assertEqual(remaining.data, [])

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

    def test_list_form_templates_public(self):
        res = self.client.get("/api/form-templates")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res.data), 16)
        ids = {row["id"] for row in res.data}
        self.assertIn("contact_basic", ids)

    def test_create_from_template_requires_creator(self):
        self._login("resp1")
        res = self.client.post("/api/forms/from_template", {"template_id": "contact_basic"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_from_template(self):
        self._login("creator1")
        res = self.client.post("/api/forms/from_template", {"template_id": "contact_basic"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["title"], "Contact us")
        self.assertEqual(len(res.data.get("questions") or []), 3)
        self.assertIsInstance(res.data.get("appearance"), dict)

    def test_duplicate_form_creates_draft_copy(self):
        self._login("creator1")
        fid = self.client.post("/api/forms", {"title": "Original", "description": "d"}, format="json").data["id"]
        self.client.post(
            f"/api/forms/{fid}/questions",
            {"order_index": 0, "question_type": "short_text", "text": "Q1", "required": False},
            format="json",
        )
        dup = self.client.post(f"/api/forms/{fid}/duplicate", {}, format="json")
        self.assertEqual(dup.status_code, status.HTTP_201_CREATED)
        self.assertEqual(dup.data["status"], "draft")
        self.assertIn("(copy)", dup.data["title"])
        self.assertEqual(len(dup.data.get("questions") or []), 1)

    def test_owner_can_change_visibility_editor_cannot(self):
        User.objects.create_user(
            username="creator2", email="c2@example.com", password="Password123!", role="creator"
        )
        self._login("creator1")
        form_id = self.client.post("/api/forms", {"title": "Vis", "description": ""}, format="json").data["id"]
        patch = self.client.patch(f"/api/forms/{form_id}", {"visibility": "private"}, format="json")
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(patch.data.get("visibility"), "private")

        self.client.post(
            f"/api/forms/{form_id}/collaborators",
            {"username": "creator2", "role": "editor"},
            format="json",
        )
        self._login("creator2")
        bad = self.client.patch(f"/api/forms/{form_id}", {"visibility": "public"}, format="json")
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("visibility", bad.data)

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
        self.assertIn("avatar_url", add.data)

    def test_owner_collaborator_search_returns_matching_users(self):
        self._login("creator1")
        form_id = self.client.post("/api/forms", {"title": "Search collab", "description": ""}, format="json").data["id"]
        res = self.client.get(f"/api/forms/{form_id}/collaborator_search", {"q": "anal"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("results", res.data)
        usernames = {r["username"] for r in res.data["results"]}
        self.assertIn("analyst1", usernames)
        for row in res.data["results"]:
            self.assertIn("avatar_url", row)
            self.assertIn("display_name", row)

    def test_owner_collaborator_candidates_lists_users(self):
        self._login("creator1")
        form_id = self.client.post("/api/forms", {"title": "Cand", "description": ""}, format="json").data["id"]
        res = self.client.get(f"/api/forms/{form_id}/collaborator_candidates")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("results", res.data)
        usernames = {r["username"] for r in res.data["results"]}
        self.assertIn("analyst1", usernames)
        self.assertNotIn("creator1", usernames)

    def test_collaborator_search_short_query_returns_empty(self):
        self._login("creator1")
        form_id = self.client.post("/api/forms", {"title": "Q", "description": ""}, format="json").data["id"]
        res = self.client.get(f"/api/forms/{form_id}/collaborator_search", {"q": "a"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["results"], [])

    def test_non_owner_cannot_collaborator_search(self):
        self._login("creator1")
        form_id = self.client.post("/api/forms", {"title": "Own", "description": ""}, format="json").data["id"]
        self.client.post(
            f"/api/forms/{form_id}/collaborators",
            {"username": "analyst1", "role": "editor"},
            format="json",
        )
        self._login("analyst1")
        res = self.client.get(f"/api/forms/{form_id}/collaborator_search", {"q": "crea"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

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

    def test_list_forms_only_owned_collaborated_or_submitted(self):
        self._login("creator1")
        mine = self.client.post("/api/forms", {"title": "Mine", "description": ""}, format="json").data
        # Owned by analyst so creator1 and respondent are neither owner nor collaborator until submit.
        other = Form.objects.create(owner=self.analyst, title="Someone else public", status="published", visibility="public")
        Question.objects.create(form=other, order_index=0, question_type="short_text", text="Q", required=False)

        res = self.client.get("/api/forms")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ids = [f["id"] for f in (res.data.get("results") or res.data)]
        self.assertIn(mine["id"], ids)
        self.assertNotIn(other.id, ids)

        self._login("resp1")
        self.client.post(
            f"/api/forms/{other.id}/submit",
            {"answers": {str(other.questions.first().id): "hello"}},
            format="json",
        )
        res2 = self.client.get("/api/forms")
        ids2 = [f["id"] for f in (res2.data.get("results") or res2.data)]
        self.assertIn(other.id, ids2)
        self.assertEqual(
            next(f for f in (res2.data.get("results") or res2.data) if f["id"] == other.id).get("my_role"),
            "respondent",
        )

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

    def test_answer_validation_format_email(self):
        form = Form.objects.create(owner=self.creator, title="Email form", status="published")
        q = Question.objects.create(
            form=form,
            order_index=0,
            question_type="short_text",
            text="Work email",
            required=True,
            validation={"format": "email"},
        )
        self._login("resp1")
        bad = self.client.post(f"/api/forms/{form.id}/submit", {"answers": {str(q.id): "not-an-email"}}, format="json")
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        ok = self.client.post(
            f"/api/forms/{form.id}/submit",
            {"answers": {str(q.id): "user@example.com"}},
            format="json",
        )
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED)

    def test_answer_validation_format_phone_digits(self):
        form = Form.objects.create(owner=self.creator, title="Phone form", status="published")
        q = Question.objects.create(
            form=form,
            order_index=0,
            question_type="short_text",
            text="Phone",
            required=True,
            validation={"format": "phone"},
        )
        self._login("resp1")
        bad = self.client.post(f"/api/forms/{form.id}/submit", {"answers": {str(q.id): "123"}}, format="json")
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        ok = self.client.post(
            f"/api/forms/{form.id}/submit",
            {"answers": {str(q.id): "+1 (555) 123-4567"}},
            format="json",
        )
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED)

    def test_disabled_required_question_not_required_on_submit(self):
        form = Form.objects.create(owner=self.creator, title="Disabled Q", status="published")
        q_active = Question.objects.create(
            form=form,
            order_index=0,
            question_type="short_text",
            text="Active",
            required=True,
            disabled=False,
        )
        Question.objects.create(
            form=form,
            order_index=1,
            question_type="short_text",
            text="Hidden but required in editor",
            required=True,
            disabled=True,
        )
        self._login("resp1")
        ok = self.client.post(
            f"/api/forms/{form.id}/submit",
            {"answers": {str(q_active.id): "only active"}},
            format="json",
        )
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED)

    def test_submit_rejects_answer_for_disabled_question(self):
        form = Form.objects.create(owner=self.creator, title="No disabled answers", status="published")
        q_active = Question.objects.create(
            form=form,
            order_index=0,
            question_type="short_text",
            text="Active",
            required=True,
            disabled=False,
        )
        q_disabled = Question.objects.create(
            form=form,
            order_index=1,
            question_type="short_text",
            text="Disabled",
            required=True,
            disabled=True,
        )
        self._login("resp1")
        bad = self.client.post(
            f"/api/forms/{form.id}/submit",
            {"answers": {str(q_active.id): "ok", str(q_disabled.id): "should not send"}},
            format="json",
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

    def test_creator_can_set_fill_mode(self):
        self._login("creator1")
        created = self.client.post("/api/forms", {"title": "Wizard form", "fill_mode": "wizard"}, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.data.get("fill_mode"), "wizard")
        fid = created.data["id"]
        patched = self.client.patch(f"/api/forms/{fid}", {"fill_mode": "all_at_once"}, format="json")
        self.assertEqual(patched.status_code, status.HTTP_200_OK)
        self.assertEqual(patched.data.get("fill_mode"), "all_at_once")

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
