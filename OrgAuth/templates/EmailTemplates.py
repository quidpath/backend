"""
Centralized email templates for all notification emails.
All email HTML should be defined here to maintain consistency and ease of maintenance.
"""


class EmailTemplates:
    """Base class for email template management with tag replacement"""
    
    @staticmethod
    def replace_tags(template_string, **kwargs):
        """
        Replaces all occurrences of [tag_name] with provided values.
        """
        try:
            for key, value in kwargs.items():
                template_string = template_string.replace(f"[{key}]", str(value))
            return template_string
        except Exception as e:
            print(f"replace_tags Exception: {e}")
            return template_string

    @staticmethod
    def get_base_style():
        """Common CSS styles for all emails"""
        return """
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f1fdf3;
                margin: 0;
                padding: 0;
            }
            .container {
                max-width: 600px;
                margin: 40px auto;
                padding: 0;
                background-color: #ffffff;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
            }
            .header {
                background-color: #a7c0ba;
                padding: 20px;
                text-align: center;
            }
            .content {
                padding: 30px;
                background-color: #ffffff;
            }
            .content h1 {
                color: #064e3b;
                margin-bottom: 10px;
            }
            .content h3 {
                color: #065f46;
                margin-top: 20px;
                margin-bottom: 10px;
            }
            .content p {
                color: #333333;
                line-height: 1.6;
                font-size: 16px;
            }
            .credentials {
                background-color: #f0fdf4;
                padding: 15px;
                border-radius: 6px;
                margin: 15px 0;
            }
            .cta-button {
                display: inline-block;
                background-color: #000000;
                color: white !important;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 8px;
                margin: 15px 0;
            }
            .footer {
                background-color: #d1fae5;
                padding: 15px;
                text-align: center;
                font-size: 13px;
                color: #065f46;
            }
            ul {
                list-style-type: none;
                padding-left: 0;
            }
            ul li {
                margin: 8px 0;
            }
        </style>
        """

    @classmethod
    def corporate_created(cls, **kwargs):
        """Template for corporate creation confirmation"""
        template = """<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
[base_style]
</head>
<body>
<div class="container">
<div class="header">
<h1>Welcome</h1>
</div>
<div class="content">
<h1>Organization Created</h1>
<p>Dear <strong>[corporate_name]</strong>,</p>
<p>Your application has been successfully submitted. We are currently reviewing your request.</p>
<p>You will receive a confirmation email once your organization is approved.</p>
<p>Thank you for choosing our platform!</p>
</div>
<div class="footer">
&copy; 2025 Quidpath. All rights reserved.
</div>
</div>
</body>
</html>"""
        return cls.replace_tags(template, base_style=cls.get_base_style(), **kwargs)

    @classmethod
    def corporate_approval(cls, **kwargs):
        """Template for corporate approval with trial and billing"""
        template = """
        <html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
            [base_style]
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to Quidpath ERP</h1>
                </div>
                <div class="content">
                    <h1>Your Organisation Has Been Approved!</h1>
                    <p>Congratulations! <strong>[corporate_name]</strong> has been approved on Quidpath ERP.</p>
                    
                    <div class="credentials">
                        <p><strong>Your login credentials:</strong></p>
                        <p>Username: <strong>[username]</strong></p>
                        <p>Password: <strong>[password]</strong></p>
                        <p style="font-size: 14px; color: #666;">Please change your password after first login.</p>
                    </div>
                    
                    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;" />
                    
                    <h3>Your 14-Day Free Trial Has Started</h3>
                    <p>You have a <strong>14-day free trial</strong> to explore all features.</p>
                    <p>To activate your account and start your trial, please enter your billing details:</p>
                    <p style="text-align: center;">
                        <a href="[billing_url]" class="cta-button">Set Up Billing</a>
                    </p>
                    <p>After your trial ends, you will receive an M-Pesa STK push to continue your subscription.</p>
                    <p style="color: #dc2626;"><strong>Without payment, access to the system will be restricted.</strong></p>
                </div>
                <div class="footer">
                    &copy; 2025 Quidpath. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """
        return cls.replace_tags(template, base_style=cls.get_base_style(), **kwargs)

    @classmethod
    def corporate_disapproval(cls, **kwargs):
        """Template for corporate disapproval"""
        template = """
        <html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
            [base_style]
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Application Update</h1>
                </div>
                <div class="content">
                    <h1>Application Status</h1>
                    <p>Dear <strong>[corporate_name]</strong>,</p>
                    <p>We regret to inform you that your organisation has not been approved at this time.</p>
                    <p>Thank you for your interest in Quidpath ERP.</p>
                </div>
                <div class="footer">
                    &copy; 2025 Quidpath. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """
        return cls.replace_tags(template, base_style=cls.get_base_style(), **kwargs)

    @classmethod
    def corporate_suspended(cls, **kwargs):
        """Template for corporate suspension"""
        template = """
        <html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
            [base_style]
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Account Suspended</h1>
                </div>
                <div class="content">
                    <h1>Your Account Has Been Suspended</h1>
                    <p>Dear <strong>[corporate_name]</strong>,</p>
                    <p>We regret to inform you that your corporate account has been suspended.</p>
                    <p>If you believe this is a mistake, please contact support.</p>
                </div>
                <div class="footer">
                    &copy; 2025 Quidpath. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """
        return cls.replace_tags(template, base_style=cls.get_base_style(), **kwargs)

    @classmethod
    def corporate_profile_updated(cls, **kwargs):
        """Template for corporate profile update"""
        template = """
        <html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
            [base_style]
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Profile Updated</h1>
                </div>
                <div class="content">
                    <h1>Corporate Profile Updated</h1>
                    <p>Dear <strong>[corporate_name]</strong>,</p>
                    <p>Your corporate profile has been successfully updated.</p>
                    <p>Fields updated: [fields]</p>
                    <p>If this was unexpected, please contact support.</p>
                </div>
                <div class="footer">
                    &copy; 2025 Quidpath. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """
        return cls.replace_tags(template, base_style=cls.get_base_style(), **kwargs)

    @classmethod
    def corporate_deleted(cls, **kwargs):
        """Template for corporate deletion"""
        template = """
        <html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
            [base_style]
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Account Deleted</h1>
                </div>
                <div class="content">
                    <h1>Account Deletion Confirmation</h1>
                    <p>Dear <strong>[corporate_name]</strong>,</p>
                    <p>Your organisation account has been deleted from our system.</p>
                    <p>If this was unexpected, kindly contact support.</p>
                </div>
                <div class="footer">
                    &copy; 2025 Quidpath. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """
        return cls.replace_tags(template, base_style=cls.get_base_style(), **kwargs)

    @classmethod
    def user_welcome(cls, **kwargs):
        """Template for new user welcome with credentials"""
        template = """
        <html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
            [base_style]
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to Quidpath!</h1>
                </div>
                <div class="content">
                    <h1>Welcome to the Team!</h1>
                    <p>Hello <strong>[username]</strong>,</p>
                    <p>You have been added to the corporate account: <strong>[corporate_name]</strong>.</p>
                    
                    <div class="credentials">
                        <p><strong>Your login credentials:</strong></p>
                        <ul>
                            <li><strong>Username:</strong> [username]</li>
                            <li><strong>Password:</strong> [password]</li>
                        </ul>
                    </div>
                    
                    <p style="text-align: center;">
                        <a href="[login_url]" class="cta-button">Login to Quidpath</a>
                    </p>
                    <p><strong>Important:</strong> Please change your password after your first login for security.</p>
                    <p>Regards,<br/>Quidpath Team</p>
                </div>
                <div class="footer">
                    &copy; 2025 Quidpath. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """
        return cls.replace_tags(template, base_style=cls.get_base_style(), **kwargs)

    @classmethod
    def user_deleted(cls, **kwargs):
        """Template for user deletion notification"""
        template = """
        <html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
            [base_style]
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Account Deleted</h1>
                </div>
                <div class="content">
                    <h1>Account Deletion</h1>
                    <p>Hello <strong>[username]</strong>,</p>
                    <p>Your account has been permanently deleted from our corporate platform.</p>
                    <p>We're sorry to see you go. If this was a mistake or you'd like to rejoin, please reach out to your administrator.</p>
                    <p>Best regards,<br/>Quidpath Team</p>
                </div>
                <div class="footer">
                    &copy; 2025 Quidpath. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """
        return cls.replace_tags(template, base_style=cls.get_base_style(), **kwargs)

    @classmethod
    def user_updated(cls, **kwargs):
        """Template for user profile update"""
        template = """
        <html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
            [base_style]
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Profile Updated</h1>
                </div>
                <div class="content">
                    <h1>Account Updated</h1>
                    <p>Hello <strong>[username]</strong>,</p>
                    <p>Your account details have been updated successfully.</p>
                    <p>If you did not request this change, please contact your administrator.</p>
                    <p>Regards,<br/>Quidpath Team</p>
                </div>
                <div class="footer">
                    &copy; 2025 Quidpath. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """
        return cls.replace_tags(template, base_style=cls.get_base_style(), **kwargs)

    @classmethod
    def user_suspended(cls, **kwargs):
        """Template for user suspension"""
        template = """
        <html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
            [base_style]
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Account Suspended</h1>
                </div>
                <div class="content">
                    <h1>Account Suspension</h1>
                    <p>Hello <strong>[username]</strong>,</p>
                    <p>Your account has been suspended by your administrator.</p>
                    <p>If you believe this is an error, please contact your system administrator.</p>
                    <p>Regards,<br/>Quidpath Team</p>
                </div>
                <div class="footer">
                    &copy; 2025 Quidpath. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """
        return cls.replace_tags(template, base_style=cls.get_base_style(), **kwargs)

    @classmethod
    def user_unsuspended(cls, **kwargs):
        """Template for user reactivation"""
        template = """
        <html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
            [base_style]
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Account Reactivated</h1>
                </div>
                <div class="content">
                    <h1>Welcome Back!</h1>
                    <p>Hello <strong>[username]</strong>,</p>
                    <p>Your account has been reactivated. You can now log in and continue using the platform.</p>
                    <p>If you experience any issues, please contact your administrator.</p>
                    <p>Regards,<br/>Quidpath Team</p>
                </div>
                <div class="footer">
                    &copy; 2025 Quidpath. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """
        return cls.replace_tags(template, base_style=cls.get_base_style(), **kwargs)

    @classmethod
    def individual_activation(cls, **kwargs):
        """Template for individual user activation email"""
        template = """
        <html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
            [base_style]
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to Quidpath!</h1>
                </div>
                <div class="content">
                    <h1>Activate Your Account</h1>
                    <p>Hello <strong>[username]</strong>,</p>
                    <p>Thank you for registering with Quidpath ERP.</p>
                    <p>Please click the button below to activate your account:</p>
                    <p style="text-align: center;">
                        <a href="[activation_link]" class="cta-button">Activate Account</a>
                    </p>
                    <p>Or copy and paste this link in your browser:</p>
                    <p style="word-break: break-all;">[activation_link]</p>
                    <p>This link will expire in 24 hours.</p>
                    <p>After activation, you will be prompted to complete your subscription payment before accessing the system.</p>
                    <p>If you didn't create this account, please ignore this email.</p>
                </div>
                <div class="footer">
                    &copy; 2025 Quidpath. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """
        return cls.replace_tags(template, base_style=cls.get_base_style(), **kwargs)

    @classmethod
    def individual_activation_resend(cls, **kwargs):
        """Template for resending activation link"""
        template = """
        <html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
            [base_style]
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Activation Link Resent</h1>
                </div>
                <div class="content">
                    <h1>New Activation Link</h1>
                    <p>Hello <strong>[username]</strong>,</p>
                    <p>Here is your new activation link:</p>
                    <p style="text-align: center;">
                        <a href="[activation_link]" class="cta-button">Activate Account</a>
                    </p>
                    <p>Or copy and paste this link in your browser:</p>
                    <p style="word-break: break-all;">[activation_link]</p>
                    <p>This link will expire in 24 hours.</p>
                </div>
                <div class="footer">
                    &copy; 2025 Quidpath. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """
        return cls.replace_tags(template, base_style=cls.get_base_style(), **kwargs)

    @classmethod
    def individual_activated(cls, **kwargs):
        """Template for account activation confirmation"""
        template = """
        <html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
            [base_style]
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Account Activated!</h1>
                </div>
                <div class="content">
                    <h1>Welcome Aboard!</h1>
                    <p>Hello <strong>[username]</strong>,</p>
                    <p>Your account has been successfully activated.</p>
                    <p>Please complete your subscription payment to start using Quidpath.</p>
                    <p>Thank you for choosing Quidpath!</p>
                </div>
                <div class="footer">
                    &copy; 2025 Quidpath. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """
        return cls.replace_tags(template, base_style=cls.get_base_style(), **kwargs)
