"""
Centralized email templates for all Quidpath notifications.
- Dynamic year in footer (never hard-coded)
- Consistent brand colours and layout across every template
- OTP template included
"""
from datetime import datetime


def _year() -> str:
    return str(datetime.now().year)


class EmailTemplates:

    # ── Shared helpers ────────────────────────────────────────────────────────

    @staticmethod
    def replace_tags(template: str, **kwargs) -> str:
        try:
            for key, value in kwargs.items():
                template = template.replace(f"[{key}]", str(value))
            return template
        except Exception as e:
            print(f"replace_tags error: {e}")
            return template

    @staticmethod
    def _style() -> str:
        return """<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Segoe UI',Arial,sans-serif;background:#f0fdf4;color:#1a1a1a}
  .wrap{max-width:600px;margin:40px auto;background:#fff;border-radius:10px;
        overflow:hidden;box-shadow:0 4px 16px rgba(0,0,0,.08)}
  .hdr{background:linear-gradient(135deg,#1b5e20 0%,#2e7d32 60%,#43a047 100%);
       padding:32px 40px;text-align:center}
  .hdr img{height:36px;margin-bottom:12px}
  .hdr h1{color:#fff;font-size:22px;font-weight:700;letter-spacing:.3px}
  .body{padding:36px 40px}
  .body p{font-size:15px;line-height:1.7;color:#374151;margin-bottom:14px}
  .body h2{font-size:18px;color:#1b5e20;margin-bottom:16px;font-weight:700}
  .creds{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;
         padding:20px 24px;margin:20px 0}
  .creds p{margin-bottom:8px;font-size:15px}
  .creds strong{color:#1b5e20}
  .otp-box{background:#f0fdf4;border:2px solid #4ade80;border-radius:10px;
           padding:24px;text-align:center;margin:24px 0}
  .otp-code{font-size:40px;font-weight:800;letter-spacing:10px;color:#1b5e20;
            font-family:'Courier New',monospace}
  .otp-note{font-size:13px;color:#6b7280;margin-top:10px}
  .btn{display:inline-block;background:#1b5e20;color:#fff!important;
       padding:13px 28px;border-radius:8px;text-decoration:none;
       font-weight:700;font-size:15px;margin:8px 0}
  .divider{border:none;border-top:1px solid #e5e7eb;margin:24px 0}
  .note{font-size:13px;color:#6b7280;font-style:italic}
  .ftr{background:#f0fdf4;border-top:1px solid #d1fae5;padding:18px 40px;
       text-align:center;font-size:13px;color:#4b7a52}
  ul{padding-left:20px;margin-bottom:14px}
  ul li{font-size:15px;line-height:1.7;color:#374151;margin-bottom:4px}
</style>"""

    @classmethod
    def _wrap(cls, header_title: str, body_html: str) -> str:
        """Wraps content in the standard Quidpath email shell."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  {cls._style()}
</head>
<body>
<div class="wrap">
  <div class="hdr">
    <h1>{header_title}</h1>
  </div>
  <div class="body">
    {body_html}
  </div>
  <div class="ftr">
    &copy; {_year()} Quidpath. All rights reserved.
  </div>
</div>
</body>
</html>"""

    # ── OTP ───────────────────────────────────────────────────────────────────

    @classmethod
    def otp(cls, **kwargs):
        """One-Time Password email — used for login verification."""
        body = """
<h2>Your One-Time Password</h2>
<p>Hello <strong>[username]</strong>,</p>
<p>Use the code below to complete your sign-in to Quidpath. This code is valid for <strong>24 hours</strong>.</p>
<div class="otp-box">
  <div class="otp-code">[otp_code]</div>
  <p class="otp-note">Do not share this code with anyone.</p>
</div>
<p>If you did not attempt to sign in, please ignore this email — your account remains secure.</p>
<p class="note">For security, this code expires after 24 hours.</p>"""
        return cls.replace_tags(cls._wrap("Sign-In Verification", body), **kwargs)

    # ── Corporate ─────────────────────────────────────────────────────────────

    @classmethod
    def corporate_created(cls, **kwargs):
        body = """
<h2>Application Received</h2>
<p>Dear <strong>[corporate_name]</strong>,</p>
<p>Thank you for registering with Quidpath. Your application has been successfully submitted and is currently under review.</p>
<p>You will receive a confirmation email once your organisation is approved — usually within 24–48 hours.</p>
<p>Thank you for choosing Quidpath!</p>"""
        return cls.replace_tags(cls._wrap("Welcome to Quidpath", body), **kwargs)

    @classmethod
    def corporate_approval(cls, **kwargs):
        body = """
<h2>Your Organisation Has Been Approved!</h2>
<p>Congratulations, <strong>[corporate_name]</strong>! Your Quidpath account is now active.</p>
<div class="creds">
  <p><strong>Your login credentials</strong></p>
  <p>Username: <strong>[username]</strong></p>
  <p>Password: <strong>[password]</strong></p>
  <p class="note">Please change your password after your first login.</p>
</div>
<hr class="divider"/>
<p><strong>Your 30-day free trial starts now.</strong> Explore all features at no cost.</p>
<p style="text-align:center;margin-top:20px">
  <a href="[billing_url]" class="btn">Set Up Billing &amp; Start Trial</a>
</p>
<p class="note">After your trial ends, a subscription payment will be required to continue.</p>"""
        return cls.replace_tags(cls._wrap("Organisation Approved!", body), **kwargs)

    @classmethod
    def corporate_disapproval(cls, **kwargs):
        body = """
<h2>Application Status Update</h2>
<p>Dear <strong>[corporate_name]</strong>,</p>
<p>We regret to inform you that your organisation application has not been approved at this time.</p>
<p>If you believe this is an error or would like more information, please contact our support team.</p>
<p>Thank you for your interest in Quidpath.</p>"""
        return cls.replace_tags(cls._wrap("Application Update", body), **kwargs)

    @classmethod
    def corporate_suspended(cls, **kwargs):
        body = """
<h2>Account Suspended</h2>
<p>Dear <strong>[corporate_name]</strong>,</p>
<p>Your Quidpath corporate account has been suspended.</p>
<p>If you believe this is a mistake, please contact our support team immediately.</p>"""
        return cls.replace_tags(cls._wrap("Account Suspended", body), **kwargs)

    @classmethod
    def corporate_profile_updated(cls, **kwargs):
        body = """
<h2>Profile Updated</h2>
<p>Dear <strong>[corporate_name]</strong>,</p>
<p>Your corporate profile has been successfully updated.</p>
<p>Fields changed: <strong>[fields]</strong></p>
<p>If you did not authorise this change, please contact support immediately.</p>"""
        return cls.replace_tags(cls._wrap("Profile Updated", body), **kwargs)

    @classmethod
    def corporate_deleted(cls, **kwargs):
        body = """
<h2>Account Deleted</h2>
<p>Dear <strong>[corporate_name]</strong>,</p>
<p>Your Quidpath organisation account has been permanently deleted.</p>
<p>If this was unexpected, please contact our support team.</p>"""
        return cls.replace_tags(cls._wrap("Account Deleted", body), **kwargs)

    # ── Users ─────────────────────────────────────────────────────────────────

    @classmethod
    def user_welcome(cls, **kwargs):
        body = """
<h2>Welcome to the Team!</h2>
<p>Hello <strong>[username]</strong>,</p>
<p>You have been added to <strong>[corporate_name]</strong> on Quidpath.</p>
<div class="creds">
  <p><strong>Your login credentials</strong></p>
  <p>Username: <strong>[username]</strong></p>
  <p>Password: <strong>[password]</strong></p>
  <p class="note">Please change your password after your first login for security.</p>
</div>
<p style="text-align:center;margin-top:20px">
  <a href="[login_url]" class="btn">Log In to Quidpath</a>
</p>
<p>If you have any questions, reach out to your organisation administrator.</p>"""
        return cls.replace_tags(cls._wrap("Welcome to Quidpath!", body), **kwargs)

    @classmethod
    def user_deleted(cls, **kwargs):
        body = """
<h2>Account Removed</h2>
<p>Hello <strong>[username]</strong>,</p>
<p>Your account has been permanently removed from the Quidpath platform.</p>
<p>If you believe this was done in error, please contact your organisation administrator.</p>"""
        return cls.replace_tags(cls._wrap("Account Removed", body), **kwargs)

    @classmethod
    def user_updated(cls, **kwargs):
        body = """
<h2>Account Updated</h2>
<p>Hello <strong>[username]</strong>,</p>
<p>Your account details have been updated successfully.</p>
<p>If you did not request this change, please contact your administrator immediately.</p>"""
        return cls.replace_tags(cls._wrap("Account Updated", body), **kwargs)

    @classmethod
    def user_suspended(cls, **kwargs):
        body = """
<h2>Account Suspended</h2>
<p>Hello <strong>[username]</strong>,</p>
<p>Your Quidpath account has been suspended by your organisation administrator.</p>
<p>If you believe this is an error, please contact your administrator.</p>"""
        return cls.replace_tags(cls._wrap("Account Suspended", body), **kwargs)

    @classmethod
    def user_unsuspended(cls, **kwargs):
        body = """
<h2>Account Reactivated</h2>
<p>Hello <strong>[username]</strong>,</p>
<p>Your Quidpath account has been reactivated. You can now log in and continue using the platform.</p>
<p>If you experience any issues, please contact your administrator.</p>"""
        return cls.replace_tags(cls._wrap("Welcome Back!", body), **kwargs)

    # ── Individual account ────────────────────────────────────────────────────

    @classmethod
    def individual_activation(cls, **kwargs):
        body = """
<h2>Activate Your Account</h2>
<p>Hello <strong>[username]</strong>,</p>
<p>Thank you for registering with Quidpath. Click the button below to activate your account.</p>
<p style="text-align:center;margin-top:20px">
  <a href="[activation_link]" class="btn">Activate Account</a>
</p>
<p>Or copy and paste this link into your browser:</p>
<p style="word-break:break-all;font-size:13px;color:#6b7280">[activation_link]</p>
<p class="note">This link expires in 24 hours. If you did not create this account, you can safely ignore this email.</p>"""
        return cls.replace_tags(cls._wrap("Activate Your Account", body), **kwargs)

    @classmethod
    def individual_activation_resend(cls, **kwargs):
        body = """
<h2>New Activation Link</h2>
<p>Hello <strong>[username]</strong>,</p>
<p>Here is your new account activation link:</p>
<p style="text-align:center;margin-top:20px">
  <a href="[activation_link]" class="btn">Activate Account</a>
</p>
<p>Or copy and paste this link into your browser:</p>
<p style="word-break:break-all;font-size:13px;color:#6b7280">[activation_link]</p>
<p class="note">This link expires in 24 hours.</p>"""
        return cls.replace_tags(cls._wrap("New Activation Link", body), **kwargs)

    @classmethod
    def individual_activated(cls, **kwargs):
        body = """
<h2>Account Activated!</h2>
<p>Hello <strong>[username]</strong>,</p>
<p>Your Quidpath account has been successfully activated.</p>
<p>You can now log in and start using the platform.</p>
<p>Thank you for choosing Quidpath!</p>"""
        return cls.replace_tags(cls._wrap("Account Activated!", body), **kwargs)
