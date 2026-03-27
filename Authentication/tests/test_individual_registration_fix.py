"""
Test suite for individual user registration import fix
Verifies that the generate_activation_token import is working correctly
"""
import json
from unittest.mock import MagicMock, patch

from django.test import TestCase, RequestFactory
from django.contrib.auth.hashers import check_password

from Authentication.models import CustomUser
from Authentication.models.role import Role
from Authentication.views.individual_registration import register_individual_user
from Authentication.views.email_activation import (
    generate_activation_token,
    activate_account,
    resend_activation_email,
)
from OrgAuth.models import Corporate, CorporateUser


class IndividualRegistrationImportFixTest(TestCase):
    """Test that the import fix for generate_activation_token works correctly"""

    def setUp(self):
        self.factory = RequestFactory()
        
        # Create SUPERADMIN role
        self.superadmin_role = Role.objects.create(
            name="SUPERADMIN",
            description="Super Administrator"
        )

    def test_generate_activation_token_import(self):
        """Test that generate_activation_token can be imported correctly"""
        from Authentication.views.email_activation import generate_activation_token
        
        # Test the function works
        token = generate_activation_token("test-user-id", "test@example.com")
        self.assertIsNotNone(token)
        self.assertIsInstance(token, str)
        self.assertTrue(len(token) > 0)

    @patch('Authentication.views.individual_registration.NotificationServiceHandler')
    def test_individual_registration_creates_user(self, mock_notification):
        """Test that individual registration creates user and corporate successfully"""
        # Mock notification service
        mock_service = MagicMock()
        mock_service.createIndividualActivationEmail.return_value = "<html>Test Email</html>"
        mock_service.send_notification.return_value = None
        mock_notification.return_value = mock_service

        # Create registration request
        request_data = {
            "username": "testuser",
            "email": "testuser@example.com",
            "password": "SecurePass123!",
            "plan_tier": "starter",
            "frontend_url": "https://stage.quidpath.com"
        }
        
        request = self.factory.post(
            '/register-individual/',
            data=json.dumps(request_data),
            content_type='application/json'
        )

        # Call registration endpoint
        response = register_individual_user(request)
        response_data = json.loads(response.content)

        # Verify response
        self.assertEqual(response.status_code, 201)
        self.assertIn("message", response_data)
        self.assertTrue(response_data.get("email_sent"))
        self.assertIn("corporate_id", response_data)

        # Verify user was created
        user = CustomUser.objects.get(email="testuser@example.com")
        self.assertEqual(user.username, "testuser")
        self.assertFalse(user.is_active)  # Should be inactive until email verified
        
        # Verify password was hashed
        self.assertTrue(check_password("SecurePass123!", user.password))

        # Verify corporate was created
        corporate = Corporate.objects.get(email="testuser@example.com")
        self.assertEqual(corporate.name, "testuser Organization")
        self.assertTrue(corporate.is_approved)
        self.assertFalse(corporate.is_active)  # Inactive until payment
        self.assertFalse(corporate.is_verified)

        # Verify activation token was generated and stored
        corp_user = CorporateUser.objects.get(id=user.id)
        self.assertIsNotNone(corp_user.metadata)
        self.assertIn("activation_token", corp_user.metadata)
        self.assertIn("activation_token_created", corp_user.metadata)
        self.assertEqual(corp_user.metadata.get("plan_tier"), "starter")

        # Verify notification was sent
        mock_service.createIndividualActivationEmail.assert_called_once()
        mock_service.send_notification.assert_called_once()

    @patch('Authentication.views.email_activation.NotificationServiceHandler')
    def test_activation_token_generation_consistency(self, mock_notification):
        """Test that activation tokens are generated consistently"""
        user_id = "test-user-123"
        email = "test@example.com"
        
        # Generate two tokens at different times
        token1 = generate_activation_token(user_id, email)
        token2 = generate_activation_token(user_id, email)
        
        # Tokens should be different (includes timestamp)
        self.assertNotEqual(token1, token2)
        
        # Both should be valid SHA256 hashes (64 characters)
        self.assertEqual(len(token1), 64)
        self.assertEqual(len(token2), 64)

    @patch('Authentication.views.individual_registration.NotificationServiceHandler')
    def test_duplicate_username_rejected(self, mock_notification):
        """Test that duplicate usernames are rejected"""
        # Create first user
        CustomUser.objects.create(
            username="existinguser",
            email="existing@example.com",
            password="password123"
        )

        # Try to register with same username
        request_data = {
            "username": "existinguser",
            "email": "newemail@example.com",
            "password": "SecurePass123!"
        }
        
        request = self.factory.post(
            '/register-individual/',
            data=json.dumps(request_data),
            content_type='application/json'
        )

        response = register_individual_user(request)
        response_data = json.loads(response.content)

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response_data)
        self.assertIn("Username already taken", response_data["error"])

    @patch('Authentication.views.individual_registration.NotificationServiceHandler')
    def test_duplicate_email_rejected(self, mock_notification):
        """Test that duplicate emails are rejected"""
        # Create first user
        CustomUser.objects.create(
            username="user1",
            email="duplicate@example.com",
            password="password123"
        )

        # Try to register with same email
        request_data = {
            "username": "user2",
            "email": "duplicate@example.com",
            "password": "SecurePass123!"
        }
        
        request = self.factory.post(
            '/register-individual/',
            data=json.dumps(request_data),
            content_type='application/json'
        )

        response = register_individual_user(request)
        response_data = json.loads(response.content)

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response_data)
        self.assertIn("Email already registered", response_data["error"])

    @patch('Authentication.views.individual_registration.NotificationServiceHandler')
    def test_missing_required_fields(self, mock_notification):
        """Test that missing required fields are rejected"""
        test_cases = [
            {"email": "test@example.com", "password": "pass123"},  # Missing username
            {"username": "testuser", "password": "pass123"},  # Missing email
            {"username": "testuser", "email": "test@example.com"},  # Missing password
        ]

        for request_data in test_cases:
            request = self.factory.post(
                '/register-individual/',
                data=json.dumps(request_data),
                content_type='application/json'
            )

            response = register_individual_user(request)
            response_data = json.loads(response.content)

            self.assertEqual(response.status_code, 400)
            self.assertIn("error", response_data)

    @patch('Authentication.views.email_activation.NotificationServiceHandler')
    def test_account_activation_flow(self, mock_notification):
        """Test the complete account activation flow"""
        # Mock notification service
        mock_service = MagicMock()
        mock_service.createIndividualActivatedEmail.return_value = "<html>Activated</html>"
        mock_service.send_notification.return_value = None
        mock_notification.return_value = mock_service

        # Create inactive user with activation token
        corporate = Corporate.objects.create(
            name="Test Org",
            email="activate@example.com",
            is_approved=True,
            is_active=False
        )

        user = CorporateUser.objects.create(
            username="activateuser",
            email="activate@example.com",
            password="password123",
            corporate=corporate,
            role=self.superadmin_role,
            is_active=False
        )

        # Generate activation token
        from django.utils import timezone
        activation_token = generate_activation_token(str(user.id), user.email)
        user.metadata = {
            "activation_token": activation_token,
            "activation_token_created": timezone.now().isoformat(),
            "plan_tier": "starter"
        }
        user.save()

        # Activate account
        request_data = {
            "token": activation_token,
            "email": "activate@example.com"
        }
        
        request = self.factory.post(
            '/activate-account/',
            data=json.dumps(request_data),
            content_type='application/json'
        )

        response = activate_account(request)
        response_data = json.loads(response.content)

        # Verify activation response
        self.assertEqual(response.status_code, 200)
        self.assertIn("message", response_data)
        self.assertTrue(response_data.get("payment_required"))
        self.assertEqual(response_data.get("username"), "activateuser")

        # Verify user is now active
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertIn("activated_at", user.metadata)

    def test_email_template_methods_exist(self):
        """Test that all required email template methods exist"""
        from quidpath_backend.core.utils.email import NotificationServiceHandler
        
        handler = NotificationServiceHandler()
        
        # Verify methods exist
        self.assertTrue(hasattr(handler, 'createIndividualActivationEmail'))
        self.assertTrue(hasattr(handler, 'createIndividualActivatedEmail'))
        self.assertTrue(hasattr(handler, 'createIndividualActivationResendEmail'))
        
        # Verify methods are callable
        self.assertTrue(callable(handler.createIndividualActivationEmail))
        self.assertTrue(callable(handler.createIndividualActivatedEmail))
        self.assertTrue(callable(handler.createIndividualActivationResendEmail))

    def test_email_templates_generate_html(self):
        """Test that email templates generate valid HTML"""
        from quidpath_backend.core.utils.email import NotificationServiceHandler
        
        handler = NotificationServiceHandler()
        
        # Test activation email
        activation_email = handler.createIndividualActivationEmail(
            username="testuser",
            activation_link="https://stage.quidpath.com/activate?token=abc123"
        )
        self.assertIn("<html>", activation_email)
        self.assertIn("testuser", activation_email)
        self.assertIn("https://stage.quidpath.com/activate?token=abc123", activation_email)
        
        # Test activated email
        activated_email = handler.createIndividualActivatedEmail(
            username="testuser"
        )
        self.assertIn("<html>", activated_email)
        self.assertIn("testuser", activated_email)
        
        # Test resend email
        resend_email = handler.createIndividualActivationResendEmail(
            username="testuser",
            activation_link="https://stage.quidpath.com/activate?token=xyz789"
        )
        self.assertIn("<html>", resend_email)
        self.assertIn("testuser", resend_email)
        self.assertIn("https://stage.quidpath.com/activate?token=xyz789", resend_email)


class EmailTemplateIntegrationTest(TestCase):
    """Integration tests for email template system"""

    def test_no_inline_html_in_registration_views(self):
        """Verify that registration views don't contain inline HTML"""
        import inspect
        from Authentication.views import individual_registration, email_activation
        
        # Get source code
        reg_source = inspect.getsource(individual_registration)
        activation_source = inspect.getsource(email_activation)
        
        # Check for common HTML patterns that shouldn't be inline
        html_patterns = [
            '<html>',
            '<body>',
            '<div class="container">',
            'background-color:',
            '<style>',
        ]
        
        for pattern in html_patterns:
            self.assertNotIn(pattern, reg_source, 
                f"Found inline HTML pattern '{pattern}' in individual_registration.py")
            self.assertNotIn(pattern, activation_source,
                f"Found inline HTML pattern '{pattern}' in email_activation.py")

    def test_all_emails_use_template_system(self):
        """Verify all email sends use the centralized template system"""
        import inspect
        from Authentication.views import individual_registration, email_activation
        
        reg_source = inspect.getsource(individual_registration)
        activation_source = inspect.getsource(email_activation)
        
        # Verify they use NotificationServiceHandler
        self.assertIn("NotificationServiceHandler", reg_source)
        self.assertIn("NotificationServiceHandler", activation_source)
        
        # Verify they call template methods
        self.assertIn("createIndividualActivationEmail", reg_source)
        self.assertIn("createIndividualActivatedEmail", activation_source)
        self.assertIn("createIndividualActivationResendEmail", activation_source)
