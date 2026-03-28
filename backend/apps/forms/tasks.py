from django.conf import settings
from django.core.mail import send_mail

from config.celery import app


@app.task
def send_new_response_notification_task(owner_email, form_title, response_id):
    if not owner_email:
        return "skipped:no-owner-email"
    subject = f"New response received for '{form_title}'"
    message = f"A new response (ID: {response_id}) was submitted to your form '{form_title}'."
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [owner_email], fail_silently=True)
    return "sent"
