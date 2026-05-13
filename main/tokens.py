from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        profile = getattr(user, "profile", None)
        verified = getattr(profile, "email_verified", False)
        return f"{user.pk}{timestamp}{user.email}{verified}{user.password}"


email_verification_token = EmailVerificationTokenGenerator()
