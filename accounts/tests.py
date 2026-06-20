from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status


User = get_user_model()


class AuthApiTests(TestCase):
    def test_signup_success_returns_user_and_tokens(self):
        response = self.client.post(
            reverse("auth-signup"),
            data={
                "name": "Rishabh Kumar",
                "email": "rishabh@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["message"], "Account created successfully.")
        self.assertEqual(body["data"]["user"]["name"], "Rishabh Kumar")
        self.assertEqual(body["data"]["user"]["email"], "rishabh@example.com")
        self.assertIn("access", body["data"])
        self.assertIn("refresh", body["data"])
        self.assertTrue(User.objects.filter(email="rishabh@example.com").exists())

    def test_signup_duplicate_email_rejected(self):
        User.objects.create_user(
            username="rishabh@example.com",
            email="rishabh@example.com",
            password="StrongPass123",
        )

        response = self.client.post(
            reverse("auth-signup"),
            data={
                "name": "Rishabh Kumar",
                "email": "RISHABH@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.json()["success"])
        self.assertIn("email", response.json()["errors"])

    def test_login_success_returns_user_and_tokens(self):
        User.objects.create_user(
            username="rishabh@example.com",
            email="rishabh@example.com",
            password="StrongPass123",
            first_name="Rishabh Kumar",
        )

        response = self.client.post(
            reverse("auth-login"),
            data={
                "email": "rishabh@example.com",
                "password": "StrongPass123",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["message"], "Login successful.")
        self.assertEqual(body["data"]["user"]["name"], "Rishabh Kumar")
        self.assertIn("access", body["data"])
        self.assertIn("refresh", body["data"])

    def test_login_wrong_password_rejected(self):
        User.objects.create_user(
            username="rishabh@example.com",
            email="rishabh@example.com",
            password="StrongPass123",
        )

        response = self.client.post(
            reverse("auth-login"),
            data={
                "email": "rishabh@example.com",
                "password": "WrongPass123",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.json()["success"])
        self.assertEqual(response.json()["message"], "Invalid email or password.")

    def test_me_requires_token_and_returns_user(self):
        unauthenticated = self.client.get(reverse("auth-me"))
        self.assertEqual(unauthenticated.status_code, status.HTTP_401_UNAUTHORIZED)

        signup = self.client.post(
            reverse("auth-signup"),
            data={
                "name": "Rishabh Kumar",
                "email": "rishabh@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
            },
            content_type="application/json",
        )
        token = signup.json()["data"]["access"]

        authenticated = self.client.get(
            reverse("auth-me"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(authenticated.status_code, status.HTTP_200_OK)
        self.assertEqual(authenticated.json()["data"]["email"], "rishabh@example.com")
